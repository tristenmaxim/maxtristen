# Only Transcribing!!!
#!/usr/bin/env python3
# Enhanced Lecture Transcriber with Audio Chunking Support

import os
import numpy as np
import tempfile
from pathlib import Path
import json
import time
import re
from openai import OpenAI
from datetime import datetime
import nltk
from nltk.tokenize import sent_tokenize
import subprocess
# pyannote imports removed - replaced with GPT hybrid approach
# from dotenv import load_dotenv

# Load environment variables from .env file  
# load_dotenv()

# Download necessary NLTK data for sentence tokenization
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')
    
# Fallback for older NLTK versions
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class GPTSpeakerAnalyzer:
    """
    Hybrid GPT-4o-mini speaker diarization analyzer.
    Analyzes segment boundaries from Whisper to determine speaker changes.
    Uses batching for token economy and provides detailed quality control.
    """
    
    def __init__(self, client, verbose=False):
        """
        Initialize GPT Speaker Analyzer.
        
        Args:
            client: OpenAI client instance
            verbose (bool): Enable detailed logging
        """
        self.client = client
        self.verbose = verbose
        
        # Initialize tiktoken for token counting
        try:
            import tiktoken
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")
            self.tiktoken_available = True
        except ImportError:
            print("Warning: tiktoken not installed. Token counting will be estimated.")
            self.tokenizer = None
            self.tiktoken_available = False
        
        # Token economy settings
        self.max_tokens_per_request = 3000  # Safe limit for gpt-4o
        self.model_name = "gpt-4o"
        
        # Cost tracking
        self.input_token_cost = 0.0025 / 1000  # $0.0025 per 1K tokens for gpt-4o
        self.output_token_cost = 0.01 / 1000  # $0.01 per 1K tokens for gpt-4o
        
        # Metrics
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0
        self.total_cost = 0.0
    
    def log(self, message):
        """Print log message if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[GPTAnalyzer] [{timestamp}] {message}")
    
    def count_tokens(self, text):
        """
        Count tokens in text using tiktoken.
        
        Args:
            text (str): Text to count tokens for
            
        Returns:
            int: Number of tokens
        """
        if self.tiktoken_available and self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback estimation: ~4 characters per token
            return len(text) // 4
    
    def create_boundary_analysis_prompt(self, segments_batch):
        """
        Create prompt for analyzing speaker boundaries in a batch of segments.
        
        Args:
            segments_batch (list): List of consecutive Whisper segments
            
        Returns:
            str: Formatted prompt for GPT analysis
        """
        prompt = """You are a speech analysis expert. Analyze this dialogue to identify natural speaker boundaries.

CORE PRINCIPLE: Identify speaker changes based on content and context, not arbitrary limits.

ANALYSIS APPROACH:
1. CONTEXT AWARENESS: Look at the overall flow of conversation
2. DIALOGUE PATTERNS: Identify question-answer exchanges  
3. SPEAKER CONSISTENCY: Same person can speak for minutes without interruption
4. NATURAL BREAKS: Only mark changes at obvious conversational boundaries

CRITERIA for speaker_change=true:
✓ Mark TRUE when you detect genuine speaker changes:
- Clear interviewer question → interviewee answer pattern
- Obvious role switch (host introduces, guest responds)
- Dramatic change in speaking style/pace/vocabulary
- Direct response to a question: "Yes, that's exactly right..."
- Interruption with different perspective: "Actually, I disagree..."
- New voice joins the conversation
- Return to previous speaker after interruption

✗ NEVER mark speaker_change=true for:
- Same person continuing their explanation
- Pauses, hesitations, or thinking moments
- Same person giving examples or elaborating
- Transition phrases like "So...", "Now...", "The thing is..."
- Filler words or speech patterns
- Same person answering follow-up questions
- Monologue segments (one person can talk for extended periods)

REMEMBER: 
- Focus on actual speaker changes, not artificial limits
- Some content has many speakers, some has few
- Long explanations by one speaker are completely normal
- When uncertain, always choose speaker_change=false

SEGMENTS TO ANALYZE:
"""
        
        # Add segments with clear numbering
        for i, segment in enumerate(segments_batch):
            start_time = self.format_timestamp(segment.get("start", 0))
            end_time = self.format_timestamp(segment.get("end", 0))
            text = segment.get("text", "").strip()
            prompt += f"Segment {i}: [{start_time}-{end_time}] \"{text}\"\n"
        
        prompt += f"""

TASK: Analyze boundaries 0-{len(segments_batch)-2} (total: {len(segments_batch)-1} boundaries)
Boundary N = between segment N and segment N+1

THINK CAREFULLY: 
- Is this likely the same person continuing to speak?
- Or is this a clear speaker change (different person responding)?
- When in doubt, choose speaker_change=false

OUTPUT ONLY valid JSON array:
[
  {{"boundary": 0, "speaker_change": false, "confidence": "high"}},
  {{"boundary": 1, "speaker_change": true, "confidence": "high"}},
  {{"boundary": 2, "speaker_change": false, "confidence": "medium"}}
]
"""
        
        return prompt
    
    def format_timestamp(self, seconds):
        """Convert seconds to MM:SS format."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def batch_boundary_analysis(self, segments):
        """
        Analyze speaker boundaries in batches for token economy.
        
        Args:
            segments (list): List of Whisper segments with timestamps and text
            
        Returns:
            list: Speaker change decisions for each boundary
        """
        if not segments or len(segments) < 2:
            self.log("Not enough segments for boundary analysis")
            return []
        
        self.log(f"Analyzing {len(segments)} segments for speaker boundaries")
        
        all_decisions = []
        current_batch = []
        current_tokens = 0
        
        # Base prompt token count (estimated)
        base_prompt_tokens = self.count_tokens(self.create_boundary_analysis_prompt([]))
        
        for i, segment in enumerate(segments):
            # Estimate tokens for this segment
            segment_text = f"Segment {i}: [{self.format_timestamp(segment.get('start', 0))}-{self.format_timestamp(segment.get('end', 0))}] \"{segment.get('text', '').strip()}\"\n"
            segment_tokens = self.count_tokens(segment_text)
            
            # Check if adding this segment would exceed token limit
            if current_tokens + segment_tokens + base_prompt_tokens > self.max_tokens_per_request and current_batch:
                # Process current batch
                self.log(f"Processing batch of {len(current_batch)} segments (~{current_tokens} tokens)")
                batch_decisions = self._analyze_batch(current_batch)
                all_decisions.extend(batch_decisions)
                
                # Start new batch
                current_batch = [segment]
                current_tokens = segment_tokens
            else:
                current_batch.append(segment)
                current_tokens += segment_tokens
        
        # Process final batch
        if current_batch:
            self.log(f"Processing final batch of {len(current_batch)} segments (~{current_tokens} tokens)")
            batch_decisions = self._analyze_batch(current_batch)
            all_decisions.extend(batch_decisions)
        
        self.log(f"Completed boundary analysis: {len(all_decisions)} decisions from {self.total_requests} API calls")
        return all_decisions
    
    def _analyze_batch(self, segments_batch):
        """
        Analyze a single batch of segments.
        
        Args:
            segments_batch (list): Batch of segments to analyze
            
        Returns:
            list: Speaker change decisions for this batch
        """
        if len(segments_batch) < 2:
            return []
        
        # Create prompt
        prompt = self.create_boundary_analysis_prompt(segments_batch)
        
        # Count tokens
        input_tokens = self.count_tokens(prompt)
        self.log(f"Sending batch with {input_tokens} input tokens")
        
        try:
            # Make API call with more output tokens for complex JSON
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a precise speaker diarization analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=1500   # Increased for larger JSON arrays
            )
            
            # Update metrics
            self.total_requests += 1
            self.total_input_tokens += input_tokens
            
            # Get response and count output tokens
            response_text = response.choices[0].message.content.strip()
            output_tokens = self.count_tokens(response_text)
            self.total_output_tokens += output_tokens
            
            # Update cost tracking
            batch_cost = (input_tokens * self.input_token_cost) + (output_tokens * self.output_token_cost)
            self.total_cost += batch_cost
            
            self.log(f"Response: {output_tokens} output tokens, cost: ${batch_cost:.6f}")
            
            # Parse response
            decisions = self.parse_gpt_speaker_decisions(response_text, len(segments_batch) - 1)
            return decisions
            
        except Exception as e:
            self.log(f"Error in batch analysis: {str(e)}")
            # Fallback: assume speaker changes at reasonable intervals
            return self._fallback_decisions(len(segments_batch) - 1)
    
    def parse_gpt_speaker_decisions(self, response_text, expected_boundaries):
        """
        Parse GPT response into speaker change decisions.
        
        Args:
            response_text (str): Raw GPT response
            expected_boundaries (int): Expected number of boundary decisions
            
        Returns:
            list: Parsed speaker change decisions
        """
        try:
            # Clean response - remove markdown formatting if present
            cleaned_response = response_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            
            # Additional cleaning for incomplete JSON
            cleaned_response = cleaned_response.strip()
            
            # Try to fix incomplete JSON by adding missing closing brackets
            if not cleaned_response.endswith(']'):
                # Count open vs closed brackets
                open_brackets = cleaned_response.count('[')
                close_brackets = cleaned_response.count(']') 
                
                if open_brackets > close_brackets:
                    # Find last complete object
                    last_complete = cleaned_response.rfind('}')
                    if last_complete != -1:
                        cleaned_response = cleaned_response[:last_complete + 1] + ']'
            
            # Parse JSON
            decisions_raw = json.loads(cleaned_response.strip())
            
            # Validate and normalize decisions
            decisions = []
            for i in range(expected_boundaries):
                if i < len(decisions_raw):
                    decision = decisions_raw[i]
                    speaker_change = decision.get("speaker_change", False)
                    confidence = decision.get("confidence", "medium")
                else:
                    # Missing decision - use conservative fallback
                    speaker_change = False  # Default to no change
                    confidence = "low"
                
                decisions.append({
                    "boundary": i,
                    "speaker_change": speaker_change,
                    "confidence": confidence
                })
            
            self.log(f"Parsed {len(decisions)} boundary decisions")
            return decisions
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.log(f"Error parsing GPT response: {str(e)}")
            self.log(f"Raw response: {response_text[:200]}...")
            return self._fallback_decisions(expected_boundaries)
    
    def _fallback_decisions(self, num_boundaries):
        """
        Generate fallback speaker change decisions.
        Ultra-conservative approach for natural dialogue.
        
        Args:
            num_boundaries (int): Number of boundaries to decide on
            
        Returns:
            list: Fallback decisions
        """
        self.log(f"Using ultra-conservative fallback decisions for {num_boundaries} boundaries")
        decisions = []
        
        # Conservative approach: let natural patterns emerge
        # Base speaker changes on content length and natural breaks
        if num_boundaries < 20:  # Very short audio - minimal changes
            total_changes = max(0, num_boundaries // 20)
        elif num_boundaries < 100:  # Short to medium audio
            total_changes = max(1, num_boundaries // 25)
        else:  # Longer audio - allow more natural speaker changes
            total_changes = max(2, num_boundaries // 30)
        
        if total_changes > 0:
            # Place changes at strategic positions (roughly 1/3 and 2/3 through)
            change_positions = []
            for i in range(1, total_changes + 1):
                pos = (num_boundaries * i) // (total_changes + 1)
                change_positions.append(pos)
        else:
            change_positions = []
        
        for i in range(num_boundaries):
            speaker_change = i in change_positions
            decisions.append({
                "boundary": i,
                "speaker_change": speaker_change,
                "confidence": "low"
            })
        
        self.log(f"Fallback: created {total_changes} speaker changes at positions {change_positions}")
        return decisions
    
    def apply_speaker_labels(self, segments, boundary_decisions):
        """
        Apply speaker labels to segments based on boundary decisions with post-processing.
        
        Args:
            segments (list): Original Whisper segments
            boundary_decisions (list): Speaker change decisions
            
        Returns:
            list: Segments with speaker labels added
        """
        if not segments:
            return segments
        
        # Step 1: Apply initial speaker labels
        labeled_segments = []
        current_speaker = 1  # Start with SPEAKER_1
        
        for i, segment in enumerate(segments):
            # Copy segment and add speaker
            labeled_segment = segment.copy()
            labeled_segment["speaker"] = f"SPEAKER_{current_speaker}"
            labeled_segments.append(labeled_segment)
            
            # Check if we should change speaker after this segment
            if i < len(boundary_decisions):
                decision = boundary_decisions[i]
                if decision.get("speaker_change", False):
                    current_speaker += 1
        
        # Step 2: Post-process to reduce speaker switching
        labeled_segments = self._post_process_speaker_labels(labeled_segments)
        
        unique_speakers = set(seg["speaker"] for seg in labeled_segments)
        self.log(f"Applied {len(unique_speakers)} speaker labels to {len(labeled_segments)} segments")
        
        return labeled_segments
    
    def _post_process_speaker_labels(self, segments):
        """
        Post-process speaker labels to reduce excessive switching and group logical speakers.
        
        Args:
            segments (list): Segments with initial speaker labels
            
        Returns:
            list: Segments with optimized speaker labels
        """
        if len(segments) < 3:
            return segments
        
        self.log("Post-processing speaker labels to reduce excessive switching")
        
        # Rule 1: Merge very short speaker segments (< 5 seconds) with adjacent speakers
        for i in range(1, len(segments) - 1):
            current = segments[i]
            prev_speaker = segments[i-1]["speaker"]
            next_speaker = segments[i+1]["speaker"]
            
            # Calculate duration of current segment
            duration = current.get("end", 0) - current.get("start", 0)
            
            # If current segment is very short and surrounded by same speaker, merge it
            if duration < 5 and prev_speaker == next_speaker:
                current["speaker"] = prev_speaker
                self.log(f"Merged short segment {i} (${duration:.1f}s) with adjacent speaker {prev_speaker}")
        
        # Rule 2: Merge very short segments to reduce noise
        # Remove speakers who speak for less than 5 seconds total
        total_duration = segments[-1].get("end", 0) if segments else 0
        unique_speakers = list(set(seg["speaker"] for seg in segments))
        
        # Calculate speaking time for each speaker
        speaker_counts = {}
        for seg in segments:
            speaker = seg["speaker"]
            duration = seg.get("end", 0) - seg.get("start", 0)
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + duration
        
        # Only remove speakers who speak for less than 5 seconds total
        min_speaking_time = 5.0  # 5 seconds minimum
        valid_speakers = [speaker for speaker, duration in speaker_counts.items() if duration >= min_speaking_time]
        
        if len(valid_speakers) < len(unique_speakers):
            self.log(f"Removing {len(unique_speakers) - len(valid_speakers)} speakers with less than {min_speaking_time}s speaking time")
            
            # Reassign short speakers to nearest valid speakers
            for i, seg in enumerate(segments):
                if seg["speaker"] not in valid_speakers:
                    # Find nearest valid speaker in time
                    best_speaker = valid_speakers[0]  # Default to most frequent
                    min_distance = float('inf')
                    
                    for j, other_seg in enumerate(segments):
                        if other_seg["speaker"] in valid_speakers:
                            distance = abs(i - j)
                            if distance < min_distance:
                                min_distance = distance
                                best_speaker = other_seg["speaker"]
                    
                    seg["speaker"] = best_speaker
        
        # Rule 3: Rename speakers to be consecutive (SPEAKER_1, SPEAKER_2, etc.)
        segments = self._renumber_speakers(segments)
        
        return segments
    
    def _renumber_speakers(self, segments):
        """
        Renumber speakers to be consecutive starting from SPEAKER_1.
        
        Args:
            segments (list): Segments with speaker labels
            
        Returns:
            list: Segments with renumbered speakers
        """
        if not segments:
            return segments
        
        # Get unique speakers in order of first appearance
        seen_speakers = []
        for seg in segments:
            speaker = seg["speaker"]
            if speaker not in seen_speakers:
                seen_speakers.append(speaker)
        
        # Create mapping to consecutive numbers
        speaker_mapping = {}
        for i, speaker in enumerate(seen_speakers):
            speaker_mapping[speaker] = f"SPEAKER_{i + 1}"
        
        # Apply mapping
        for seg in segments:
            seg["speaker"] = speaker_mapping[seg["speaker"]]
        
        return segments
    
    def get_usage_report(self):
        """
        Get detailed usage and cost report.
        
        Returns:
            dict: Usage statistics and cost breakdown
        """
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": self.total_cost,
            "input_cost": self.total_input_tokens * self.input_token_cost,
            "output_cost": self.total_output_tokens * self.output_token_cost,
            "average_tokens_per_request": (self.total_input_tokens + self.total_output_tokens) / max(1, self.total_requests),
            "model_used": self.model_name
        }


class EnhancedLectureTranscriber:
    """Advanced tool for transcribing lectures with speaker diarization and punctuation."""
    
    def __init__(self, api_key=None, hf_token=None, verbose=False):
        """
        Initialize the Enhanced Lecture Transcriber.
        
        Args:
            api_key (str, optional): OpenAI API key. If not provided, uses OPENAI_API_KEY env variable.
            hf_token (str, optional): HuggingFace API token for speaker diarization.
            verbose (bool): Whether to print detailed logs.
        """
        try:
            self.client = OpenAI(api_key=api_key)
            print(">>> Debug: Successfully initialized OpenAI client")
        except Exception as e:
            print(f">>> Debug: Error initializing OpenAI client: {str(e)}")
            raise
            
        self.verbose = verbose
        self.temp_dir = Path(tempfile.mkdtemp())
        self.hf_token = hf_token
        
        # Initialize speaker diarization if token is provided
        self.diarization_pipeline = None
        if self.hf_token:
            try:
                self.diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1", 
                    use_auth_token=self.hf_token
                )
                print(">>> Debug: Successfully initialized speaker diarization pipeline")
            except Exception as e:
                print(f">>> Debug: Error initializing speaker diarization: {str(e)}")
                print(">>> Speaker diarization will be disabled")
        
        # Initialize GPT Speaker Analyzer for hybrid approach
        self.gpt_analyzer = GPTSpeakerAnalyzer(self.client, verbose=self.verbose)
        self.log("GPT Speaker Analyzer initialized")
        
        # Track processing metrics
        self.metrics = {
            "audio_duration": 0,
            "processing_time": 0,
            "speakers_detected": 0,
            "chunks_processed": 0
        }
        
        # Set Whisper API size limit in bytes (25MB)
        self.max_file_size = 25 * 1024 * 1024
        
        if self.verbose:
            print(f"Created temporary directory at {self.temp_dir}")
    
    def log(self, message):
        """Print log message if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {message}")
    
    def extract_audio(self, video_path):
        """
        Extract audio from video file.
        
        Args:
            video_path (str): Path to the video file.
            
        Returns:
            str: Path to the extracted audio file.
        """
        self.log(f"Extracting audio from {video_path}")
        audio_path = self.temp_dir / "audio.wav"
        
        # Check if video file exists
        if not os.path.exists(video_path):
            self.log(f"Error: Video file not found at {video_path}")
            return None
        
        # Use ffmpeg to extract audio with high quality for better transcription
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(audio_path), "-y"  # Mono 16kHz WAV, overwrite if exists
        ]
        
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.log("Audio extraction successful")
            
            # Get audio duration
            duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                           "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
            duration_result = subprocess.run(duration_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            duration = float(duration_result.stdout.decode().strip())
            self.metrics["audio_duration"] = duration
            self.log(f"Audio duration: {duration:.2f} seconds")
            
            return audio_path if audio_path.exists() else None
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else str(e)
            self.log(f"Error extracting audio: {stderr}")
            
            # Check if the video has no audio stream
            if "Stream specifier 'a' in filtergraph" in stderr or "Invalid data found" in stderr:
                self.log("This video may not have an audio stream")
            return None
        except Exception as e:
            self.log(f"Unexpected error extracting audio: {str(e)}")
            return None
    
    def check_file_size(self, file_path):
        """
        Check if the file size exceeds OpenAI's API limit.
        
        Args:
            file_path (Path or str): Path to the file to check.
            
        Returns:
            bool: True if file size is below the limit, False otherwise.
        """
        file_size = os.path.getsize(file_path)
        self.log(f"File size: {file_size / (1024 * 1024):.2f} MB")
        return file_size <= self.max_file_size
    
    def split_audio(self, audio_path, chunk_duration=600):
        """
        Split audio file into smaller chunks that meet API size limits.
        
        Args:
            audio_path (Path or str): Path to the audio file.
            chunk_duration (int): Maximum duration of each chunk in seconds.
                                 Default is 10 minutes (600 seconds).
            
        Returns:
            list: List of paths to audio chunks.
        """
        self.log(f"Checking if audio needs to be split")
        
        # If file is small enough, return the original path
        if self.check_file_size(audio_path):
            self.log("Audio file is below size limit, no splitting needed")
            return [audio_path]
        
        self.log(f"Audio file exceeds size limit. Splitting into chunks of {chunk_duration} seconds")
        
        # Get total duration
        duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                       "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
        duration_result = subprocess.run(duration_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        total_duration = float(duration_result.stdout.decode().strip())
        
        # Calculate number of chunks needed
        num_chunks = int(np.ceil(total_duration / chunk_duration))
        self.log(f"Splitting {total_duration:.2f} seconds into {num_chunks} chunks")
        
        chunk_paths = []
        
        # Create each chunk with ffmpeg
        for i in range(num_chunks):
            start_time = i * chunk_duration
            
            # Chunk file path
            chunk_path = self.temp_dir / f"chunk_{i:03d}.wav"
            chunk_paths.append(chunk_path)
            
            # FFmpeg command to extract chunk
            cmd = [
                "ffmpeg", "-i", str(audio_path),
                "-ss", str(start_time),  # Start time
                "-t", str(chunk_duration),  # Duration
                "-c:a", "pcm_s16le",  # Audio codec
                "-ar", "16000",  # Sample rate
                "-ac", "1",  # Mono
                str(chunk_path),
                "-y"  # Overwrite if exists
            ]
            
            self.log(f"Creating chunk {i+1}/{num_chunks} starting at {self.format_timestamp(start_time)}")
            
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Verify the chunk size
                chunk_size = os.path.getsize(chunk_path)
                if chunk_size > self.max_file_size:
                    # If still too large, try with shorter duration (recursive halving approach)
                    self.log(f"Chunk {i+1} still too large ({chunk_size / (1024 * 1024):.2f} MB). Further splitting required.")
                    os.remove(chunk_path)  # Remove the oversized chunk
                    
                    # Recalculate chunk duration for the entire split operation
                    return self.split_audio(audio_path, chunk_duration // 2)
                
                self.log(f"Chunk {i+1} created: {chunk_size / (1024 * 1024):.2f} MB")
            except Exception as e:
                self.log(f"Error creating chunk {i+1}: {str(e)}")
                # Continue with other chunks if possible
        
        self.metrics["chunks_processed"] = len(chunk_paths)
        return chunk_paths
    
    def merge_transcriptions(self, chunk_transcriptions):
        """
        Merge transcriptions from multiple chunks into a single transcription.
        
        Args:
            chunk_transcriptions (list): List of transcription dictionaries or OpenAI response objects.
            
        Returns:
            dict: Merged transcription.
        """
        if not chunk_transcriptions:
            self.log("No transcription chunks to merge")
            return {"text": "", "segments": []}
        
        self.log(f"Merging {len(chunk_transcriptions)} transcription chunks")
        
        merged = {
            "text": "",
            "segments": []
        }
        
        # Track the last segment ID
        last_segment_id = 0
        last_end_time = 0
        
        # Concatenate text and adjust segments
        for i, chunk in enumerate(chunk_transcriptions):
            try:
                self.log(f"Processing chunk {i+1}/{len(chunk_transcriptions)} for merge")
                
                # Convert OpenAI response object to dict if needed
                chunk_data = chunk
                
                # Extract text and segments, handling different response formats
                chunk_text = ""
                chunk_segments = []
                
                # Try to access text attribute (OpenAI response object)
                if hasattr(chunk_data, 'text'):
                    chunk_text = chunk_data.text
                    self.log(f"Found text in chunk {i+1} (length: {len(chunk_text)})")
                elif isinstance(chunk_data, dict) and "text" in chunk_data:
                    chunk_text = chunk_data.get("text", "")
                    self.log(f"Found text in chunk dict {i+1} (length: {len(chunk_text)})")
                    
                # Try to access segments
                if hasattr(chunk_data, 'segments'):
                    chunk_segments = chunk_data.segments
                    self.log(f"Found {len(chunk_segments)} segments in chunk {i+1}")
                elif isinstance(chunk_data, dict) and "segments" in chunk_data:
                    chunk_segments = chunk_data.get("segments", [])
                    self.log(f"Found {len(chunk_segments)} segments in chunk dict {i+1}")
                
                # If no segments, try to create a single segment from the whole text
                if not chunk_segments and chunk_text:
                    self.log(f"No segments found in chunk {i+1}, creating a single segment from text")
                    chunk_segments = [{
                        "id": 0,
                        "start": 0,
                        "end": 10,  # Arbitrary duration
                        "text": chunk_text
                    }]
                
                # Add the text with a space
                if merged["text"] and chunk_text:
                    merged["text"] += " "
                merged["text"] += chunk_text
                
                # Debug information about segments
                if hasattr(chunk_segments, '__iter__'):
                    self.log(f"Chunk {i+1} has {len(list(chunk_segments))} iterable segments")
                else:
                    self.log(f"Chunk {i+1} has non-iterable segments of type: {type(chunk_segments)}")
                
                # Adjust segment timestamps based on chunk position
                chunk_start_time = last_end_time
                
                # Process all segments in this chunk
                for segment in chunk_segments:
                    try:
                        # Handle different segment formats
                        segment_dict = segment
                        if not isinstance(segment, dict):
                            # Try to convert OpenAI segment object to dict
                            segment_dict = {
                                "id": getattr(segment, "id", i),
                                "start": getattr(segment, "start", 0),
                                "end": getattr(segment, "end", 10),
                                "text": getattr(segment, "text", "")
                            }
                        
                        # Create a new segment with adjusted values
                        new_segment = {
                            "id": last_segment_id,
                            "start": chunk_start_time + segment_dict.get("start", 0),
                            "end": chunk_start_time + segment_dict.get("end", 10),
                            "text": segment_dict.get("text", "")
                        }
                        
                        # Increment segment ID
                        last_segment_id += 1
                        
                        # Add to merged segments
                        merged["segments"].append(new_segment)
                    except Exception as e:
                        self.log(f"Error processing segment in chunk {i+1}: {str(e)}")
                        continue
                
                # Update the last end time if we added segments
                if merged["segments"]:
                    last_segment = merged["segments"][-1]
                    last_end_time = last_segment["end"]
                    self.log(f"Updated last_end_time to {last_end_time}")
                    
            except Exception as e:
                self.log(f"Error merging chunk {i+1}: {str(e)}")
                # Continue with other chunks
        
        self.log(f"Merge complete. Output has {len(merged['segments'])} segments and text length {len(merged['text'])}")
        return merged
    
    def transcribe_with_openai(self, audio_path, speaker_segments=None):
        """
        Transcribe audio using OpenAI's Whisper model.
        If speaker_segments is provided, segments the transcription by speaker.
        Handles large files by splitting into chunks.
        
        Args:
            audio_path (str): Path to the audio file.
            speaker_segments (list, optional): List of speaker segments from diarization.
            
        Returns:
            dict: The transcription result with timestamps and speakers.
        """
        if not audio_path or not Path(audio_path).exists():
            self.log("No audio file found for transcription")
            return {"text": ""}
            
        self.log(f"Transcribing audio from {audio_path}")
        
        try:
            # Split audio into chunks if necessary
            audio_chunks = self.split_audio(audio_path)
            
            # If we have multiple chunks
            if len(audio_chunks) > 1:
                self.log(f"Transcribing {len(audio_chunks)} audio chunks sequentially")
                
                # Process each chunk
                chunk_transcriptions = []
                for i, chunk_path in enumerate(audio_chunks):
                    self.log(f"Transcribing chunk {i+1}/{len(audio_chunks)}")
                    
                    try:
                        # Process chunk
                        with open(chunk_path, "rb") as audio_file:
                            chunk_response = self.client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                response_format="verbose_json",
                                timestamp_granularities=["segment"]
                            )
                        
                        # Convert OpenAI response to a standard dictionary we can work with
                        chunk_transcription = {
                            "text": chunk_response.text if hasattr(chunk_response, 'text') else "",
                            "segments": []
                        }
                        
                        # Process segments
                        if hasattr(chunk_response, 'segments'):
                            for segment in chunk_response.segments:
                                segment_data = {
                                    "id": segment.id if hasattr(segment, 'id') else 0,
                                    "start": segment.start if hasattr(segment, 'start') else 0,
                                    "end": segment.end if hasattr(segment, 'end') else 0,
                                    "text": segment.text if hasattr(segment, 'text') else ""
                                }
                                chunk_transcription["segments"].append(segment_data)
                        
                        # Store the result
                        chunk_transcriptions.append(chunk_transcription)
                        self.log(f"Successfully transcribed chunk {i+1} with {len(chunk_transcription['segments'])} segments")
                    except Exception as e:
                        self.log(f"Error transcribing chunk {i+1}: {str(e)}")
                        # Continue with other chunks
                
                # Merge the transcription chunks
                self.log("Merging transcriptions from all chunks")
                merged_transcription = self.merge_transcriptions(chunk_transcriptions)
                
                if not merged_transcription or not merged_transcription.get("text"):
                    self.log("Merge resulted in empty transcription")
                    if chunk_transcriptions:
                        # If merge failed but we have individual transcriptions, concatenate texts as fallback
                        fallback_text = " ".join(chunk["text"] for chunk in chunk_transcriptions if chunk.get("text"))
                        self.log(f"Created fallback transcription from concatenated texts: {len(fallback_text)} characters")
                        merged_transcription = {
                            "text": fallback_text,
                            "segments": []
                        }
                
                # Add speaker information if available
                if speaker_segments and merged_transcription.get("segments"):
                    if speaker_segments == "USE_GPT_HYBRID":
                        # Use GPT-4o-mini hybrid approach
                        self.apply_gpt_speaker_analysis(merged_transcription)
                    else:
                        # Use traditional pyannote-based approach
                        self.assign_speakers_to_segments(merged_transcription, speaker_segments)
                
                return merged_transcription
            else:
                # Single chunk processing (original path)
                self.log("Processing single audio file")
                with open(audio_path, "rb") as audio_file:
                    transcription_response = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"]
                    )
                
                # Get the segments with timestamps
                result = {
                    "text": transcription_response.text if hasattr(transcription_response, 'text') else "",
                    "segments": []
                }
                
                # Process segments
                if hasattr(transcription_response, 'segments'):
                    for segment in transcription_response.segments:
                        segment_data = {
                            "id": segment.id if hasattr(segment, 'id') else 0,
                            "start": segment.start if hasattr(segment, 'start') else 0,
                            "end": segment.end if hasattr(segment, 'end') else 0,
                            "text": segment.text if hasattr(segment, 'text') else ""
                        }
                        
                        result["segments"].append(segment_data)
                
                # Add speaker information if available
                if speaker_segments and result.get("segments"):
                    if speaker_segments == "USE_GPT_HYBRID":
                        # Use GPT-4o-mini hybrid approach
                        self.apply_gpt_speaker_analysis(result)
                    else:
                        # Use traditional pyannote-based approach
                        self.assign_speakers_to_segments(result, speaker_segments)
                
                self.log(f"Transcription successful: {len(result['segments'])} segments")
                return result
                
        except Exception as e:
            self.log(f"Error transcribing audio: {str(e)}")
            return {"text": "", "segments": []}
    
    def perform_speaker_diarization(self, audio_path, use_gpt=False):
        """
        Perform speaker diarization to identify different speakers.
        
        Args:
            audio_path (Path): Path to the audio file.
            use_gpt (bool): Use GPT-4o-mini hybrid approach instead of pyannote.
            
        Returns:
            dict: Speaker diarization results with timestamps.
        """
        # GPT-4o-mini hybrid approach
        if use_gpt:
            self.log("GPT hybrid approach: Speaker analysis will be integrated with transcription")
            # In GPT hybrid mode, speaker analysis happens after Whisper transcription
            # Return a special marker to indicate GPT mode should be used
            return "USE_GPT_HYBRID"
        
        # Use original pyannote pipeline
        if not self.diarization_pipeline:
            self.log("Speaker diarization not available - HF token not provided")
            return None
            
        self.log(f"Performing pyannote speaker diarization on {audio_path}")
        
        try:
            # Run the diarization pipeline
            diarization = self.diarization_pipeline(audio_path)
            
            # Process the output into usable speaker segments
            speaker_segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speaker_segments.append({
                    "speaker": speaker,
                    "start": turn.start,
                    "end": turn.end
                })
            
            # Count unique speakers
            unique_speakers = set(segment["speaker"] for segment in speaker_segments)
            self.metrics["speakers_detected"] = len(unique_speakers)
            
            self.log(f"Pyannote: Detected {len(unique_speakers)} unique speakers with {len(speaker_segments)} segments")
            return speaker_segments
        except Exception as e:
            self.log(f"Error in pyannote diarization: {str(e)}")
            # Fallback to lightweight if pyannote fails
            self.log("Falling back to lightweight diarization due to error")
            return self.perform_speaker_diarization(audio_path, use_lightweight=True)
    
    def assign_speakers_to_segments(self, transcription, speaker_segments):
        """
        Assign speakers to transcription segments.
        
        Args:
            transcription (dict): Transcription with segments.
            speaker_segments (list): Speaker diarization segments.
            
        Returns:
            None: Modifies transcription in place.
        """
        for segment in transcription["segments"]:
            # Find the speaker who speaks the most during this segment
            speakers_during_segment = {}
            segment_start, segment_end = segment["start"], segment["end"]
            
            for speaker_segment in speaker_segments:
                s_start, s_end = speaker_segment["start"], speaker_segment["end"]
                
                # Check for overlap
                if s_end > segment_start and s_start < segment_end:
                    # Calculate overlap duration
                    overlap_start = max(segment_start, s_start)
                    overlap_end = min(segment_end, s_end)
                    overlap_duration = overlap_end - overlap_start
                    
                    # Add to speaker's total time
                    speaker = speaker_segment["speaker"]
                    if speaker in speakers_during_segment:
                        speakers_during_segment[speaker] += overlap_duration
                    else:
                        speakers_during_segment[speaker] = overlap_duration
            
            # Assign the dominant speaker
            if speakers_during_segment:
                dominant_speaker = max(speakers_during_segment, key=speakers_during_segment.get)
                segment["speaker"] = dominant_speaker

    def apply_gpt_speaker_analysis(self, transcription):
        """
        Apply GPT-4o-mini speaker analysis to transcription segments.
        
        Args:
            transcription (dict): Transcription with segments from Whisper
            
        Returns:
            dict: Usage report and validation results from GPT analysis
        """
        if not transcription.get("segments"):
            self.log("No segments available for GPT speaker analysis")
            return None
        
        segments = transcription["segments"]
        self.log(f"Starting GPT speaker analysis on {len(segments)} segments")
        
        # Store original segments for accuracy validation
        original_segments = [seg.copy() for seg in segments]
        
        try:
            # Analyze boundaries between segments
            boundary_decisions = self.gpt_analyzer.batch_boundary_analysis(segments)
            
            if not boundary_decisions:
                self.log("GPT analysis returned no boundary decisions")
                return None
            
            # Apply speaker labels based on decisions
            labeled_segments = self.gpt_analyzer.apply_speaker_labels(segments, boundary_decisions)
            
            # Update the transcription with labeled segments
            transcription["segments"] = labeled_segments
            
            # Get usage report
            usage_report = self.gpt_analyzer.get_usage_report()
            
            # Validate processing quality
            validation_results = self.validate_processing_quality(
                original_segments, 
                labeled_segments, 
                usage_report
            )
            
            unique_speakers = set(seg["speaker"] for seg in labeled_segments if "speaker" in seg)
            self.log(f"GPT analysis complete: {len(unique_speakers)} speakers detected")
            self.log(f"Token usage: {usage_report['total_tokens']} tokens, cost: ${usage_report['total_cost']:.6f}")
            
            # Critical validation check
            if not validation_results["accuracy_pass"]:
                self.log("🚨 CRITICAL: Text accuracy validation failed! GPT may have modified Whisper text.")
                # In production, might want to revert to original segments
            
            # Store validation results for later use
            transcription["_gpt_validation"] = validation_results
            
            return {
                "usage_report": usage_report,
                "validation_results": validation_results,
                "speakers_detected": len(unique_speakers)
            }
            
        except Exception as e:
            self.log(f"Error in GPT speaker analysis: {str(e)}")
            return None
    
    def calculate_text_accuracy(self, original_segments, processed_segments):
        """
        Calculate text accuracy between original Whisper and processed segments.
        
        Args:
            original_segments (list): Original segments from Whisper
            processed_segments (list): Processed segments with speaker labels
            
        Returns:
            dict: Accuracy metrics at character and word level
        """
        if not original_segments or not processed_segments:
            return {"char_accuracy": 0.0, "word_accuracy": 0.0, "error": "Empty segments"}
        
        # Extract text from segments
        original_text = " ".join(seg.get("text", "").strip() for seg in original_segments)
        processed_text = " ".join(seg.get("text", "").strip() for seg in processed_segments)
        
        # Character-level accuracy
        char_matches = sum(1 for a, b in zip(original_text, processed_text) if a == b)
        char_total = max(len(original_text), len(processed_text))
        char_accuracy = (char_matches / char_total * 100) if char_total > 0 else 0.0
        
        # Word-level accuracy
        original_words = original_text.split()
        processed_words = processed_text.split()
        
        word_matches = sum(1 for a, b in zip(original_words, processed_words) if a == b)
        word_total = max(len(original_words), len(processed_words))
        word_accuracy = (word_matches / word_total * 100) if word_total > 0 else 0.0
        
        # Segment count check
        segment_count_matches = len(original_segments) == len(processed_segments)
        
        accuracy_report = {
            "char_accuracy": char_accuracy,
            "word_accuracy": word_accuracy,
            "char_matches": char_matches,
            "char_total": char_total,
            "word_matches": word_matches,
            "word_total": word_total,
            "original_segments": len(original_segments),
            "processed_segments": len(processed_segments),
            "segment_count_matches": segment_count_matches,
            "is_perfect": char_accuracy == 100.0 and word_accuracy == 100.0 and segment_count_matches
        }
        
        return accuracy_report
    
    def calculate_token_costs(self, gpt_usage_report=None):
        """
        Calculate detailed token usage and cost breakdown.
        
        Args:
            gpt_usage_report (dict): Usage report from GPT analyzer
            
        Returns:
            dict: Detailed cost analysis
        """
        if not gpt_usage_report:
            return {
                "error": "No GPT usage data available",
                "total_cost": 0.0,
                "token_efficiency": "N/A"
            }
        
        # Calculate theoretical cost if each boundary was analyzed individually
        total_boundaries = gpt_usage_report.get("total_requests", 1) * 10  # Estimate ~10 boundaries per batch
        individual_cost_estimate = total_boundaries * 0.002  # Rough estimate per individual request
        
        actual_cost = gpt_usage_report.get("total_cost", 0.0)
        savings_percentage = ((individual_cost_estimate - actual_cost) / individual_cost_estimate * 100) if individual_cost_estimate > 0 else 0
        
        cost_breakdown = {
            "total_cost": actual_cost,
            "input_cost": gpt_usage_report.get("input_cost", 0.0),
            "output_cost": gpt_usage_report.get("output_cost", 0.0),
            "total_requests": gpt_usage_report.get("total_requests", 0),
            "total_input_tokens": gpt_usage_report.get("total_input_tokens", 0),
            "total_output_tokens": gpt_usage_report.get("total_output_tokens", 0),
            "total_tokens": gpt_usage_report.get("total_tokens", 0),
            "average_tokens_per_request": gpt_usage_report.get("average_tokens_per_request", 0),
            "estimated_individual_cost": individual_cost_estimate,
            "savings_percentage": savings_percentage,
            "cost_per_minute": actual_cost / (self.metrics.get("audio_duration", 60) / 60) if self.metrics.get("audio_duration", 0) > 0 else 0
        }
        
        return cost_breakdown
    
    def generate_quality_report(self, accuracy_report=None, cost_breakdown=None, gpt_usage=None):
        """
        Generate detailed quality report for transcript header.
        
        Args:
            accuracy_report (dict): Text accuracy metrics
            cost_breakdown (dict): Token cost analysis
            gpt_usage (dict): GPT usage statistics
            
        Returns:
            str: Formatted quality report for file header
        """
        report_lines = []
        
        # Text Accuracy Section
        if accuracy_report:
            report_lines.append("🔍 TEXT ACCURACY REPORT:")
            if accuracy_report.get("is_perfect", False):
                report_lines.append(f"✅ Character accuracy: {accuracy_report['char_accuracy']:.2f}% ({accuracy_report['char_matches']}/{accuracy_report['char_total']} chars match)")
                report_lines.append(f"✅ Word accuracy: {accuracy_report['word_accuracy']:.2f}% ({accuracy_report['word_matches']}/{accuracy_report['word_total']} words match)")
                report_lines.append(f"✅ Segment count: {accuracy_report['original_segments']} → {accuracy_report['processed_segments']} (preserved)")
            else:
                report_lines.append(f"❌ Character accuracy: {accuracy_report['char_accuracy']:.2f}% ({accuracy_report['char_matches']}/{accuracy_report['char_total']} chars match)")
                report_lines.append(f"❌ Word accuracy: {accuracy_report['word_accuracy']:.2f}% ({accuracy_report['word_matches']}/{accuracy_report['word_total']} words match)")
                report_lines.append(f"⚠️ Segment count: {accuracy_report['original_segments']} → {accuracy_report['processed_segments']} (changed)")
            
            report_lines.append("✅ Speaker detection: GPT-4o-mini boundary analysis")
        
        # Token Usage Section
        if cost_breakdown:
            report_lines.append("")
            report_lines.append("💰 TOKEN USAGE REPORT:")
            report_lines.append(f"📤 Input tokens: {cost_breakdown['total_input_tokens']:,} (~${cost_breakdown['input_cost']:.4f})")
            report_lines.append(f"📥 Output tokens: {cost_breakdown['total_output_tokens']:,} (~${cost_breakdown['output_cost']:.4f})")
            report_lines.append(f"💵 Total cost: ~${cost_breakdown['total_cost']:.4f}")
            report_lines.append(f"⚡ Batches used: {cost_breakdown['total_requests']} (vs ~{cost_breakdown['total_requests'] * 10} individual requests)")
            if cost_breakdown['savings_percentage'] > 0:
                report_lines.append(f"🎯 Savings: {cost_breakdown['savings_percentage']:.0f}% vs individual calls")
            
            if cost_breakdown['cost_per_minute'] > 0:
                report_lines.append(f"⏱️ Cost per minute: ${cost_breakdown['cost_per_minute']:.4f}")
        
        return "\n".join(report_lines)
    
    def validate_processing_quality(self, original_segments, processed_segments, gpt_usage_report=None):
        """
        Validate that processing meets quality standards.
        
        Args:
            original_segments (list): Original Whisper segments
            processed_segments (list): Processed segments with speakers
            gpt_usage_report (dict): GPT usage statistics
            
        Returns:
            dict: Validation results with pass/fail status
        """
        # Calculate accuracy
        accuracy_report = self.calculate_text_accuracy(original_segments, processed_segments)
        
        # Calculate costs
        cost_breakdown = self.calculate_token_costs(gpt_usage_report)
        
        # Generate report
        quality_report = self.generate_quality_report(accuracy_report, cost_breakdown, gpt_usage_report)
        
        # Validation criteria
        validation_results = {
            "accuracy_pass": accuracy_report.get("is_perfect", False),
            "cost_reasonable": cost_breakdown.get("total_cost", 999) < 0.10,  # Max $0.10 per processing
            "accuracy_report": accuracy_report,
            "cost_breakdown": cost_breakdown,
            "quality_report": quality_report,
            "overall_pass": False
        }
        
        # Overall validation
        validation_results["overall_pass"] = (
            validation_results["accuracy_pass"] and 
            validation_results["cost_reasonable"]
        )
        
        # Detailed logging
        if validation_results["accuracy_pass"]:
            self.log("✅ Text accuracy validation: PASSED (100% accuracy maintained)")
        else:
            self.log("❌ Text accuracy validation: FAILED (text was modified)")
        
        if validation_results["cost_reasonable"]:
            self.log(f"✅ Cost validation: PASSED (${cost_breakdown.get('total_cost', 0):.4f} < $0.10)")
        else:
            self.log(f"❌ Cost validation: FAILED (${cost_breakdown.get('total_cost', 0):.4f} >= $0.10)")
        
        return validation_results
    
    def add_punctuation(self, text):
        """
        Add missing punctuation to text using NLP techniques.
        
        Args:
            text (str): Text to process.
            
        Returns:
            str: Text with added punctuation.
        """
        if not text:
            return text
            
        self.log("Adding punctuation to transcript")
        
        try:
            # Pattern for detecting existing sentence endings
            sentence_end_pattern = r'(?<=[.!?])\s+'
            
            # Capitalize the first letter of the text if it's lowercase
            if text and text[0].islower():
                text = text[0].upper() + text[1:]
            
            # Basic preprocessing - normalize spaces
            text = re.sub(r'\s+', ' ', text).strip()
            
            # 1. Add periods where there are clear sentence boundaries
            # Look for lowercase word followed by capitalized word
            text = re.sub(r'(?<=[a-z])\s+(?=[A-Z])', '. ', text)
            
            # 2. Use NLTK to find potential sentence boundaries and add periods
            # This is more conservative to avoid overriding existing punctuation
            potential_sentences = sent_tokenize(text)
            
            # Only modify if NLTK found more than one sentence
            if len(potential_sentences) > 1:
                # Reconstruct text with proper sentence endings
                processed_text = ""
                for sentence in potential_sentences:
                    # Check if the sentence already ends with punctuation
                    if not sentence.strip().endswith(('.', '!', '?')):
                        sentence += '.'
                    processed_text += sentence + " "
                text = processed_text.strip()
            
            # 3. Add question marks based on question words
            # Find sentences that start with question words but don't end with ?
            question_words = ['Why', 'What', 'Who', 'Where', 'When', 'How', 'Is', 'Are', 'Can', 'Could', 'Would', 'Will', 'Do', 'Does', 'Did']
            for word in question_words:
                # Fixed-width lookbehind pattern
                pattern = rf'(?<=\. )({word}[^.!?]*[^?\s])\s+(?=[A-Z]|$)'
                text = re.sub(pattern, r'\1? ', text, flags=re.IGNORECASE)
                # Also check for sentence start
                pattern = rf'^({word}[^.!?]*[^?\s])\s+(?=[A-Z]|$)'
                text = re.sub(pattern, r'\1? ', text, flags=re.IGNORECASE | re.MULTILINE)
            
            # 4. Add commas for natural pauses
            # After introductory phrases
            intro_phrases = ["However", "Therefore", "Meanwhile", "Nevertheless", 
                           "Moreover", "Furthermore", "In addition", "As a result", 
                           "For example", "In fact", "On the other hand"]
            for phrase in intro_phrases:
                text = re.sub(fr'\b{phrase}\b(?!,)', f'{phrase},', text)
            
            # Add commas before conjunctions joining independent clauses
            conj_pattern = r'(?<=[a-z])\s+(and|but|or|so|for|nor|yet)\s+(?=[A-Z])'
            text = re.sub(conj_pattern, lambda m: f', {m.group(1)} ', text)
            
            # 5. Add missing periods at the end of text if needed
            if text and not text.strip().endswith(('.', '!', '?')):
                text += '.'
            
            return text
        
        except Exception as e:
            self.log(f"Error adding punctuation: {str(e)}")
            return text  # Return original text if something goes wrong
    
    def enhance_transcription(self, segments):
        """
        Enhance the transcription by adding punctuation to each segment.
        
        Args:
            segments (list): List of transcription segments.
            
        Returns:
            list: Enhanced segments with punctuation.
        """
        enhanced_segments = []
        
        for segment in segments:
            segment_copy = segment.copy()
            segment_copy["text"] = self.add_punctuation(segment["text"])
            enhanced_segments.append(segment_copy)
        
        return enhanced_segments
    
    def merge_speaker_segments(self, segments):
        """
        Merge consecutive segments from the same speaker into single blocks.
        
        Args:
            segments (list): List of segments with speaker information.
            
        Returns:
            list: Merged segments with combined text and time ranges.
        """
        if not segments:
            return segments
            
        merged_segments = []
        current_group = None
        
        for segment in segments:
            speaker = segment.get("speaker", "Unknown")
            
            # If it's the same speaker as the current group, merge
            if (current_group and 
                current_group.get("speaker") == speaker and
                # Only merge if segments are close in time (within 2 seconds gap)
                segment["start"] - current_group["end"] <= 2.0):
                
                # Extend the current group
                current_group["end"] = segment["end"]
                current_group["text"] += " " + segment["text"]
                
            else:
                # Save the previous group if it exists
                if current_group:
                    merged_segments.append(current_group)
                
                # Start a new group
                current_group = {
                    "id": len(merged_segments),
                    "start": segment["start"],
                    "end": segment["end"],
                    "speaker": speaker,
                    "text": segment["text"]
                }
        
        # Don't forget the last group
        if current_group:
            merged_segments.append(current_group)
            
        return merged_segments

    def merge_time_segments(self, segments, max_gap=0.5, max_duration=10.0):
        """
        Merge consecutive segments that are close in time (for non-speaker cases).
        
        Args:
            segments (list): List of segments.
            max_gap (float): Maximum gap in seconds to consider segments as consecutive.
            max_duration (float): Maximum duration for a merged segment.
            
        Returns:
            list: Merged segments based on time proximity.
        """
        if not segments:
            return segments
            
        merged_segments = []
        current_group = None
        
        for segment in segments:
            # If we can merge with current group
            if (current_group and 
                segment["start"] - current_group["end"] <= max_gap and
                current_group["end"] - current_group["start"] < max_duration):
                
                # Extend the current group
                current_group["end"] = segment["end"]
                current_group["text"] += " " + segment["text"]
                
            else:
                # Save the previous group if it exists
                if current_group:
                    merged_segments.append(current_group)
                
                # Start a new group
                current_group = {
                    "id": len(merged_segments),
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"]
                }
        
        # Don't forget the last group
        if current_group:
            merged_segments.append(current_group)
            
        return merged_segments

    def format_transcript(self, transcription, with_speakers=True, with_timestamps=True, merge_speakers=True):
        """
        Format the transcription for readability.
        
        Args:
            transcription (dict): Transcription results with segments.
            with_speakers (bool): Whether to include speaker labels.
            with_timestamps (bool): Whether to include timestamps.
            merge_speakers (bool): Whether to merge consecutive segments from same speaker.
            
        Returns:
            str: Formatted transcript text.
        """
        if not transcription or "segments" not in transcription or not transcription["segments"]:
            return ""
        
        segments = transcription["segments"]
        
        # Merge segments if requested
        if merge_speakers:
            if any("speaker" in seg for seg in segments):
                # Use speaker-based merging if speaker info is available
                segments = self.merge_speaker_segments(segments)
            else:
                # Use time-based merging if no speaker info (merge close segments)
                segments = self.merge_time_segments(segments)
        
        formatted_lines = []
        
        for segment in segments:
            line = ""
            
            # Add timestamp(s) if requested
            if with_timestamps:
                if merge_speakers and segment["end"] - segment["start"] > 1.0:
                    # Show time range for merged segments
                    start_time = self.format_timestamp(segment["start"])
                    end_time = self.format_timestamp(segment["end"])
                    line += f"[{start_time} - {end_time}] "
                else:
                    # Show single timestamp for short segments
                    start_time = self.format_timestamp(segment["start"])
                    line += f"[{start_time}] "
            
            # Add speaker if available and requested
            if with_speakers and "speaker" in segment:
                speaker = segment["speaker"]
                line += f"{speaker}: "
            
            # Add the text
            line += segment["text"]
            
            formatted_lines.append(line)
        
        return "\n".join(formatted_lines)
    
    def format_timestamp(self, seconds):
        """Convert seconds to HH:MM:SS format."""
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def to_srt_timestamp(self, seconds):
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        millisecs = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def transcribe_lecture(self, video_path, add_punctuation=True, with_diarization=True, output_format="txt", chunk_duration=600, use_gpt=False):
        """
        Complete pipeline to transcribe a lecture.
        
        Args:
            video_path (str): Path to the video/audio file.
            add_punctuation (bool): Whether to add punctuation to the transcript.
            with_diarization (bool): Whether to perform speaker diarization.
            output_format (str): Format for the output ("txt", "json", or "srt").
            chunk_duration (int): Maximum duration in seconds for each audio chunk.
            use_gpt (bool): Use GPT-4o-mini hybrid approach instead of pyannote.
            
        Returns:
            dict: Results of the transcription with metadata.
        """
        results = {
            "source_path": video_path,
            "transcript": "",
            "enhanced_transcript": "",
            "formatted_transcript": "",
            "speakers_detected": 0,
            "processing_time": 0,
            "chunks_processed": 0,
            "output_file": None
        }
        
        start_time = time.time()
        
        try:
            # Verify the file exists
            if not os.path.exists(video_path):
                self.log(f"Error: File not found at {video_path}")
                results["error"] = f"File not found at {video_path}"
                return results
            
            # 1. Extract audio (if it's a video file)
            self.log(f"Starting audio extraction from {video_path}")
            audio_path = None
            
            if video_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                audio_path = self.extract_audio(video_path)
                if not audio_path:
                    self.log("Error: Failed to extract audio from video")
                    results["error"] = "Failed to extract audio from video"
                    results["processing_time"] = time.time() - start_time
                    return results
            else:
                # Assume it's already an audio file
                audio_path = video_path
                
            self.log(f"Audio ready for processing: {audio_path}")
            
            # 2. Perform speaker diarization if requested and available
            speaker_segments = None
            if with_diarization:
                self.log("Starting speaker diarization")
                speaker_segments = self.perform_speaker_diarization(
                    audio_path, 
                    use_gpt=use_gpt
                )
                if speaker_segments:
                    results["speakers_detected"] = self.metrics["speakers_detected"]
                else:
                    self.log("Speaker diarization produced no results")
            
            # 3. Transcribe audio with OpenAI (handles chunking internally)
            self.log("Starting transcription with OpenAI")
            transcription = self.transcribe_with_openai(audio_path, speaker_segments)
            
            if not transcription or not transcription.get("text"):
                self.log("Error: Transcription failed or returned empty result")
                results["error"] = "Transcription failed or returned empty result"
                results["processing_time"] = time.time() - start_time
                return results
                
            results["transcript"] = transcription["text"]
            results["chunks_processed"] = self.metrics["chunks_processed"]
            
            # 4. Enhance transcription with punctuation if requested
            if add_punctuation and transcription.get("segments"):
                self.log("Enhancing transcription with punctuation")
                enhanced_segments = self.enhance_transcription(transcription["segments"])
                transcription["segments"] = enhanced_segments
                
                # Regenerate full text from enhanced segments
                enhanced_text = " ".join([segment["text"] for segment in enhanced_segments])
                results["enhanced_transcript"] = enhanced_text
            
            # 5. Format transcript for output
            self.log("Formatting transcript with speakers and timestamps")
            has_speakers = any("speaker" in segment for segment in transcription.get("segments", []))
            formatted_transcript = self.format_transcript(
                transcription, 
                with_speakers=has_speakers, 
                with_timestamps=True
            )
            results["formatted_transcript"] = formatted_transcript
            
            # 6. Save to file based on requested format
            self.log(f"Saving transcript in {output_format.upper()} format")
            file_path = self.save_transcript(
                transcription,
                output_format=output_format,
                base_name=os.path.splitext(os.path.basename(video_path))[0]
            )
            
            if file_path:
                results["output_file"] = str(file_path)
                self.log(f"Saved transcript to {file_path}")
            
            # Calculate processing time
            results["processing_time"] = time.time() - start_time
            self.log(f"Transcription completed in {results['processing_time']:.2f} seconds")
            
            return results
            
        except Exception as e:
            self.log(f"Unhandled exception in transcribe_lecture: {str(e)}")
            results["error"] = str(e)
            results["processing_time"] = time.time() - start_time
            return results
    
    def save_transcript(self, transcription, output_format="txt", base_name="transcript"):
        """
        Save transcript to file in various formats.
        
        Args:
            transcription (dict): Transcription data with segments.
            output_format (str): Format to save ("txt", "json", or "srt").
            base_name (str): Base name for the output file.
            
        Returns:
            Path: Path to the saved file.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            if output_format.lower() == "txt":
                # Save as plain text with formatting
                output_path = Path(f"{base_name}_transcript_{timestamp}.txt")
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write("===== Lecture Transcript =====\n\n")
                    f.write(f"Source: {base_name}\n")
                    f.write(f"Transcription date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Duration: {self.metrics.get('audio_duration', 0):.2f} seconds\n")
                    
                    if self.metrics.get("chunks_processed", 0) > 1:
                        f.write(f"Audio processed in {self.metrics['chunks_processed']} chunks\n")
                    
                    if self.metrics.get("speakers_detected", 0) > 1:
                        f.write(f"Speakers detected: {self.metrics['speakers_detected']}\n")
                    
                    # Add GPT validation report if available
                    gpt_validation = transcription.get("_gpt_validation")
                    if gpt_validation and gpt_validation.get("quality_report"):
                        f.write(f"\n{gpt_validation['quality_report']}\n")
                    
                    f.write("\n----- Transcript -----\n\n")
                    
                    # Write formatted transcript
                    has_speakers = any("speaker" in segment for segment in transcription.get("segments", []))
                    formatted_text = self.format_transcript(
                        transcription, 
                        with_speakers=has_speakers, 
                        with_timestamps=True
                    )
                    f.write(formatted_text)
                
            elif output_format.lower() == "json":
                # Save as JSON with all metadata
                output_path = Path(f"{base_name}_transcript_{timestamp}.json")
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "metadata": {
                            "source": base_name,
                            "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "duration": self.metrics.get('audio_duration', 0),
                            "chunks_processed": self.metrics.get("chunks_processed", 0),
                            "speakers_detected": self.metrics.get("speakers_detected", 0)
                        },
                        "transcript": transcription
                    }, f, indent=2)
                    
            elif output_format.lower() == "srt":
                # Save as SubRip subtitle format
                output_path = Path(f"{base_name}_transcript_{timestamp}.srt")
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    for i, segment in enumerate(transcription.get("segments", []), 1):
                        # Convert timestamps to SRT format (HH:MM:SS,mmm)
                        start_time = self.to_srt_timestamp(segment["start"])
                        end_time = self.to_srt_timestamp(segment["end"])
                        
                        # Format the text (with speaker if available)
                        text = segment["text"]
                        if "speaker" in segment:
                            text = f"{segment['speaker']}: {text}"
                        
                        # Write SRT entry
                        f.write(f"{i}\n")
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{text}\n\n")
            
            else:
                self.log(f"Unsupported output format: {output_format}")
                return None
                
            return output_path
            
        except Exception as e:
            self.log(f"Error saving transcript: {str(e)}")
            return None
    
    def cleanup(self):
        """Remove temporary files."""
        self.log("Cleaning up temporary files")
        try:
            for file_path in self.temp_dir.glob("*"):
                try:
                    file_path.unlink()
                except Exception as e:
                    self.log(f"Error removing file {file_path}: {str(e)}")
            
            try:
                self.temp_dir.rmdir()
                self.log(f"Removed temporary directory {self.temp_dir}")
            except Exception as e:
                self.log(f"Error removing directory {self.temp_dir}: {str(e)}")
        except Exception as e:
            self.log(f"Error during cleanup: {str(e)}")


def main():
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Enhanced Lecture Transcription Tool")
    parser.add_argument("video_path", help="Path to the lecture video or audio file")
    parser.add_argument("--openai-key", help="OpenAI API key (optional, can use env var OPENAI_API_KEY)")
    parser.add_argument("--hf-token", help="HuggingFace API token for speaker diarization")
    parser.add_argument("--no-punctuation", action="store_true", help="Disable punctuation enhancement")
    parser.add_argument("--no-diarization", action="store_true", help="Disable speaker diarization")
    parser.add_argument("--format", choices=["txt", "json", "srt"], default="txt", help="Output format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--chunk-size", type=int, default=600, help="Maximum duration in seconds for each audio chunk (default: 600)")
    parser.add_argument("--gpt-diarization", action="store_true", help="Use GPT-4o-mini hybrid approach for speaker diarization")
    
    args = parser.parse_args()
    
    print(f"Starting enhanced transcription for: {args.video_path}")
    
    # Get HF token from argument or environment variable
    hf_token = args.hf_token or os.getenv('HF_TOKEN')
    
    transcriber = EnhancedLectureTranscriber(
        api_key=args.openai_key, 
        hf_token=hf_token,
        verbose=args.verbose
    )

    # Transcribe the lecture
    results = transcriber.transcribe_lecture(
        args.video_path,
        add_punctuation=not args.no_punctuation,
        with_diarization=not args.no_diarization,
        output_format=args.format,
        chunk_duration=args.chunk_size,
        use_gpt=args.gpt_diarization
    )

    # Print results to console
    print("\n===== Lecture Transcription Results =====")
    print(f"Source: {results['source_path']}")
    print(f"Processed in {results['processing_time']:.2f} seconds")
    
    if results.get("chunks_processed", 0) > 1:
        print(f"Audio processed in {results['chunks_processed']} chunks")
        
    if results.get("speakers_detected", 0) > 1:
        print(f"Detected {results['speakers_detected']} speakers")
            
    if "error" in results:
        print(f"\nError: {results['error']}")
    
    if results.get("output_file"):
        print(f"\nTranscript saved to: {results['output_file']}")

    # Cleanup temp files
    transcriber.cleanup()

if __name__ == "__main__":
    main()
