let player;
const playlistId = window.APP_CONFIG.PLAYLIST_ID;
const YOUTUBE_API_KEY = window.APP_CONFIG.YOUTUBE_API_KEY;
let progressInterval;

// Timer variables
let timerInterval;
let timerStartTime = null;
let timerElapsedTime = 0;
let isTimerRunning = false;

// Track list variables
let currentTrackIndex = -1;
let isTrackListVisible = false;
let currentlyPlayingIndex = -1;
let isUserActivelyListening = false;
let isShuffleEnabled = false; // Shuffle state
let shuffledPlaylist = null; // Shuffled version of playlist

// Audio control variables
let currentVolume = 100;
let isMuted = false;
let previousVolume = 100; // Store volume before muting

// This function is called when the YouTube Iframe API is ready.
function onYouTubeIframeAPIReady() {
    console.log('YouTube API ready - starting player');

    // Create player without preloading
    preloadPlayer();
}



function preloadPlayer() {
    console.log('Preloading player in background...');
    
    // Create hidden, muted player ready for instant playback
    player = new YT.Player('youtube-player', {
        height: '0',
        width: '0',
        playerVars: {
            listType: 'playlist',
            list: playlistId,
            autoplay: 0,
            mute: 1
        },
        events: {
            'onReady': onPreloadPlayerReady,
            'onStateChange': onPlayerStateChange
        }
    });
}

function onPreloadPlayerReady(event) {
    console.log('Player ready!');

    setTimeout(() => {
        enableBackgroundPlayback();
        setupMediaSession();
        preventAutoPause();

        // Enable start button after player is fully ready
        const startBtn = document.getElementById('start-btn');
        startBtn.classList.remove('disabled');
        startBtn.style.cursor = 'pointer';
    }, 100);
}

// This function will be called when the user clicks the "start" text.
function startPlayer() {
    document.getElementById('start-btn').style.display = 'none';
    
    console.log('Starting preloaded player - instant playback!');
    
    // Player is already loaded, just unmute and show controls
    if (player) {
        player.unMute();
        player.setVolume(100);
        player.playVideo(); // Start playing immediately
        
        // Show the controls
        document.getElementById('player-controls').classList.remove('hidden');

        // Set up control event listeners (only once)
        setupPlayerControls();
    }
}

document.getElementById('start-btn').addEventListener('click', startPlayer);

function setupPlayerControls() {
    console.log('Setting up player controls...');
    
    // Set up the control event listeners
    document.getElementById('play-pause-btn').addEventListener('click', () => {
        const state = player.getPlayerState();
        if (state === YT.PlayerState.PLAYING) {
            player.pauseVideo();
        } else {
            player.playVideo();
        }
    });

    document.getElementById('next-btn').addEventListener('click', () => {
        player.nextVideo();
    });

    document.getElementById('prev-btn').addEventListener('click', () => {
        player.previousVideo();
    });

    document.getElementById('progress-bar-container').addEventListener('click', (e) => {
        const progressBar = document.getElementById('progress-bar-container');
        const clickPosition = e.offsetX;
        const barWidth = progressBar.offsetWidth;
        const duration = player.getDuration();
        
        if (duration > 0) {
            const seekTime = (clickPosition / barWidth) * duration;
            player.seekTo(seekTime, true);
            
            // Immediately update progress bar for instant feedback
            const progress = Math.min((seekTime / duration) * 100, 100);
            document.getElementById('progress-bar').style.width = `${progress}%`;
        }
    });
    
    // Set up track list toggle button
    document.getElementById('tracklist-toggle').addEventListener('click', toggleTrackList);

    // Set up shuffle toggle
    document.getElementById('shuffle-toggle').addEventListener('click', toggleShuffle);

    // Set up audio controls
    setupAudioControls();
    

    // Note: We handle shuffle client-side, not through YouTube player

    // player.getPlaylist() populates asynchronously after onReady — YouTube
    // fetches the playlist contents in the background, so it's often still
    // empty right here. Poll briefly instead of assuming it's ready.
    waitForPlaylist();

    // Note: Track titles will be loaded as tracks are played
}

function waitForPlaylist(attempt = 0) {
    const playlist = player.getPlaylist();

    if (playlist && playlist.length > 0) {
        document.getElementById('track-count').textContent = `${playlist.length} tracks`;
        console.log('Playlist loaded, count:', playlist.length);
        renderTrackList();
        return;
    }

    if (attempt >= 20) { // ~5s at 250ms intervals
        console.log('Playlist still empty after retries, giving up');
        document.getElementById('track-count').textContent = 'No tracks';
        return;
    }

    setTimeout(() => waitForPlaylist(attempt + 1), 250);
}

function onPlayerStateChange(event) {
    console.log("Player State Changed: ", event.data);
    const playPauseBtn = document.getElementById('play-pause-btn');

    switch (event.data) {
        case YT.PlayerState.CUED:
            // This happens when a video is loaded but not playing.
            // This is a good time to update the track info for the first time.
            updateTrackInfo();
            break;
        case YT.PlayerState.PLAYING:
            playPauseBtn.textContent = 'Pause';
            updateTrackInfo(); // Ensure info is updated when play starts
            progressInterval = setInterval(updateProgressBar, 500); // Update every 500ms for smoother progress
            console.log('Music started playing - calling startTimer()');
            startTimer(); // Start timer when music starts playing
            
            // Mark user as actively listening
            isUserActivelyListening = true;
            
            // Update current track highlighting
            const playlistIndex = player.getPlaylistIndex();
            if (playlistIndex >= 0) {
                currentlyPlayingIndex = playlistIndex;
                updateCurrentTrackHighlight(playlistIndex);

                // If shuffle is enabled, recreate shuffled playlist to maintain consistency
                if (isShuffleEnabled && player.getPlaylist) {
                    const originalPlaylist = player.getPlaylist();
                    if (originalPlaylist && originalPlaylist.length > 0) {
                        shuffledPlaylist = [...originalPlaylist].sort(() => Math.random() - 0.5);
                    }
                }
            }
            
            break;
        case YT.PlayerState.PAUSED:
            playPauseBtn.textContent = 'Play';
            clearInterval(progressInterval);
            pauseTimer(); // Pause timer when music is paused
            
            // Mark user as not actively listening
            isUserActivelyListening = false;
            
            break;
        case YT.PlayerState.ENDED:
            // The playlist will automatically play the next video,
            // which will trigger a new PLAYING state.
            playPauseBtn.textContent = 'Play';
            clearInterval(progressInterval);
            // Don't pause timer on track end, as next track will auto-play
            break;
        default:
            clearInterval(progressInterval);
            break;
    }
}

function updateTrackInfo() {
    if (player && typeof player.getVideoData === 'function') {
        const trackInfo = document.getElementById('track-info');
        const videoData = player.getVideoData();
        if (videoData && videoData.title) {
            trackInfo.querySelector('p').innerHTML = `${videoData.title}<br><br>${videoData.author}`;
        }
    }
}



function updateProgressBar() {
    if (player && typeof player.getCurrentTime === 'function' && typeof player.getDuration === 'function') {
        const progressBar = document.getElementById('progress-bar');
        const currentTime = player.getCurrentTime();
        const duration = player.getDuration();
        
        if (duration > 0) {
            const progress = Math.min((currentTime / duration) * 100, 100);
            progressBar.style.width = `${progress}%`;
            
            // Update time display in progress bar area (optional enhancement)
            const timeText = `${formatTime(Math.floor(currentTime))} / ${formatTime(Math.floor(duration))}`;
            progressBar.setAttribute('title', timeText);
        } else {
            // Handle case where duration is not available yet
            progressBar.style.width = '0%';
        }
    }
}

// Timer functions
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function updateTimerDisplay() {
    const timerDisplay = document.getElementById('timer-display');
    const currentTime = Math.floor(timerElapsedTime / 1000);
    const timeString = formatTime(currentTime);
    timerDisplay.textContent = timeString;
    
    // Only update title when timer is running
    if (isTimerRunning && currentTime > 0) {
        document.title = timeString;
    } else {
        document.title = "Background Music Player";
    }
}

function startTimer() {
    console.log('startTimer called, isTimerRunning:', isTimerRunning);
    if (!isTimerRunning) {
        timerStartTime = Date.now() - timerElapsedTime;
        isTimerRunning = true;
        console.log('Timer started at:', new Date());
        
        // Use a combination of setInterval and Date.now() for reliable timing
        timerInterval = setInterval(() => {
            if (isTimerRunning) {
                timerElapsedTime = Date.now() - timerStartTime;
                updateTimerDisplay();
            }
        }, 1000);
    }
}

function pauseTimer() {
    if (isTimerRunning) {
        isTimerRunning = false;
        clearInterval(timerInterval);
    }
}

function resetTimer() {
    isTimerRunning = false;
    clearInterval(timerInterval);
    timerElapsedTime = 0;
    timerStartTime = null;
    updateTimerDisplay();
}



// Shuffle functions
function toggleShuffle() {
    isShuffleEnabled = !isShuffleEnabled;
    const button = document.getElementById('shuffle-toggle');

    // Update button text and appearance
    if (isShuffleEnabled) {
        button.textContent = '🔀 Shuffle: ON';
        button.classList.add('active');

        // Create shuffled playlist
        if (player && typeof player.getPlaylist === 'function') {
            const originalPlaylist = player.getPlaylist();
            if (originalPlaylist && originalPlaylist.length > 0) {
                shuffledPlaylist = [...originalPlaylist].sort(() => Math.random() - 0.5);
                console.log('Tracklist shuffled - displaying random order');
            }
        }
    } else {
        button.textContent = '🔀 Shuffle: OFF';
        button.classList.remove('active');

        // Clear shuffled playlist
        shuffledPlaylist = null;
        console.log('Tracklist unshuffled - displaying original order');
    }

    // Re-render the tracklist with new order
    if (isTrackListVisible) {
        renderTrackList();
    }
}

// Track list functions

function renderTrackList() {
    const trackListElement = document.getElementById('tracklist');
    trackListElement.innerHTML = '';

    // Get playlist from player
    if (!player || typeof player.getPlaylist !== 'function') {
        trackListElement.innerHTML = '<div class="track-item">Player not ready</div>';
        return;
    }

    const originalPlaylist = player.getPlaylist();

    if (!originalPlaylist || originalPlaylist.length === 0) {
        trackListElement.innerHTML = '<div class="track-item">No tracks available</div>';
        return;
    }

    // Use shuffled playlist if shuffle is enabled, otherwise use original
    const playlist = isShuffleEnabled ? (shuffledPlaylist || originalPlaylist) : originalPlaylist;

    // Update track count
    document.getElementById('track-count').textContent = `${originalPlaylist.length} tracks`;

    playlist.forEach((videoId, displayIndex) => {
        const trackElement = document.createElement('div');
        trackElement.className = 'track-item';
        trackElement.dataset.index = displayIndex;
        trackElement.dataset.videoId = videoId;

        // Find original index for playback
        const originalIndex = originalPlaylist.indexOf(videoId);

        trackElement.innerHTML = `
            <div class="track-title">Loading...</div>
            <div class="track-channel">ID: ${videoId}</div>
        `;

        // Load track title asynchronously (without caching)
        loadTrackTitle(videoId, trackElement, displayIndex + 1);

        trackElement.addEventListener('click', () => playTrackByIndex(originalIndex));
        trackListElement.appendChild(trackElement);
    });
}

function loadTrackTitle(videoId, trackElement, trackNumber) {
    // Load track title from YouTube API without caching
    const url = `https://www.googleapis.com/youtube/v3/videos?part=snippet&id=${videoId}&key=${YOUTUBE_API_KEY}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.items && data.items.length > 0) {
                const title = data.items[0].snippet.title;
                const channel = data.items[0].snippet.channelTitle;

                trackElement.innerHTML = `
                    <div class="track-title">${title}</div>
                    <div class="track-channel">${channel}</div>
                `;
            } else {
                trackElement.innerHTML = `
                    <div class="track-title">Track ${trackNumber}</div>
                    <div class="track-channel">Unknown</div>
                `;
            }
        })
        .catch(error => {
            console.log('Failed to load track title:', error);
            trackElement.innerHTML = `
                <div class="track-title">Track ${trackNumber}</div>
                <div class="track-channel">ID: ${videoId}</div>
            `;
        });
}

function playTrackByIndex(index) {
    if (player) {
        console.log(`Playing track ${index}`);
        player.playVideoAt(index);
        updateCurrentTrackHighlight(index);
    }
}

function updateCurrentTrackHighlight(index = null) {
    // Clear all current highlights
    document.querySelectorAll('.track-item').forEach(item => {
        item.classList.remove('current');
    });

    // If index provided, highlight that track
    if (index !== null && index >= 0) {
        // When shuffle is enabled, we need to find the track in the shuffled list
        if (isShuffleEnabled && shuffledPlaylist && player) {
            const currentVideoId = player.getPlaylist()[index];
            const shuffledIndex = shuffledPlaylist.indexOf(currentVideoId);

            if (shuffledIndex >= 0) {
                const trackElement = document.querySelector(`[data-index="${shuffledIndex}"]`);
                if (trackElement) {
                    trackElement.classList.add('current');
                    trackElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        } else {
            // Normal mode - use original index
            const trackElement = document.querySelector(`[data-index="${index}"]`);
            if (trackElement) {
                trackElement.classList.add('current');
                trackElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
        currentTrackIndex = index;
    }
}

function toggleTrackList() {
    const container = document.getElementById('tracklist-container');
    const button = document.getElementById('tracklist-toggle');

    isTrackListVisible = !isTrackListVisible;

    if (isTrackListVisible) {
        container.classList.remove('hidden');
        button.textContent = 'Hide';
        renderTrackList(); // Load track names dynamically
    } else {
        container.classList.add('hidden');
        button.textContent = 'Tracks';
    }
}


// Audio control functions
function setupAudioControls() {
    const volumeSlider = document.getElementById('volume-slider');
    const muteBtn = document.getElementById('mute-btn');
    const volumeDisplay = document.getElementById('volume-display');

    // Volume slider event listener
    volumeSlider.addEventListener('input', (e) => {
        const volume = parseInt(e.target.value);
        setVolume(volume);
    });
    
    // Mute button event listener
    muteBtn.addEventListener('click', toggleMute);
    
    // Update initial display
    updateVolumeDisplay();
}

function setVolume(volume) {
    currentVolume = volume;
    if (player && player.setVolume) {
        player.setVolume(volume);
    }
    
    // Update UI elements
    document.getElementById('volume-slider').value = volume;
    updateVolumeDisplay();

    // Update mute state if volume is 0
    if (volume === 0) {
        isMuted = true;
        updateMuteButton();
    } else if (isMuted && volume > 0) {
        isMuted = false;
        updateMuteButton();
    }
}

function toggleMute() {
    if (isMuted) {
        // Unmute: restore previous volume
        isMuted = false;
        currentVolume = previousVolume > 0 ? previousVolume : 50;
        setVolume(currentVolume);
    } else {
        // Mute: store current volume and set to 0
        isMuted = true;
        previousVolume = currentVolume;
        setVolume(0);
    }
    updateMuteButton();
}

function updateMuteButton() {
    const muteBtn = document.getElementById('mute-btn');
    if (isMuted || currentVolume === 0) {
        muteBtn.textContent = '🔇';
        muteBtn.classList.add('muted');
        muteBtn.title = 'Unmute';
    } else {
        muteBtn.textContent = '🔊';
        muteBtn.classList.remove('muted');
        muteBtn.title = 'Mute';
    }
}

function updateVolumeDisplay() {
    const volumeDisplay = document.getElementById('volume-display');
    volumeDisplay.textContent = `${currentVolume}%`;
}





// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Prevent shortcuts when typing in input fields
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    
    switch (e.code) {
        case 'Space':
            e.preventDefault();
            // Toggle play/pause
            if (player) {
                const state = player.getPlayerState();
                if (state === YT.PlayerState.PLAYING) {
                    player.pauseVideo();
                } else {
                    player.playVideo();
                }
            }
            break;
            
        case 'KeyM':
            e.preventDefault();
            toggleMute();
            break;
            
        case 'ArrowUp':
            e.preventDefault();
            // Increase volume by 10
            const newVolumeUp = Math.min(currentVolume + 10, 100);
            setVolume(newVolumeUp);
            break;
            
        case 'ArrowDown':
            e.preventDefault();
            // Decrease volume by 10
            const newVolumeDown = Math.max(currentVolume - 10, 0);
            setVolume(newVolumeDown);
            break;
            
            
        case 'KeyN':
            e.preventDefault();
            if (player) player.nextVideo();
            break;
            
        case 'KeyP':
            e.preventDefault();
            if (player) player.previousVideo();
            break;
            
    }
});

// Handle page visibility changes to prevent timer pausing when tab is inactive
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        console.log('Tab became hidden - keeping playback active');

        // Store the current time when tab becomes hidden
        if (isTimerRunning) {
            timerElapsedTime = Date.now() - timerStartTime;
        }

        // Aggressively prevent pausing - multiple checks
        if (player && isTimerRunning) {
            // Immediate check
            setTimeout(() => {
                const state = player.getPlayerState();
                if (state === YT.PlayerState.PAUSED) {
                    console.log('Detected pause in background - forcing resume');
                    player.playVideo();
                }
            }, 100);

            // Multiple checks in first minute
            for (let i = 1; i <= 6; i++) {
                setTimeout(() => {
                    const state = player.getPlayerState();
                    if (state === YT.PlayerState.PAUSED && isTimerRunning) {
                        console.log(`Pause detection ${i} - forcing resume`);
                        player.playVideo();
                    }
                }, i * 10000); // Every 10 seconds for first minute
            }

            // Continue checking every 30 seconds
            const backgroundCheck = setInterval(() => {
                if (document.hidden && isTimerRunning) {
                    const state = player.getPlayerState();
                    if (state === YT.PlayerState.PAUSED) {
                        console.log('Periodic background pause detection - forcing resume');
                        player.playVideo();
                    }
                } else {
                    clearInterval(backgroundCheck);
                }
            }, 30000);
        }

    } else {
        console.log('Tab became visible - syncing timer and player');

        // Sync timer when tab becomes visible again
        if (isTimerRunning) {
            timerStartTime = Date.now() - timerElapsedTime;
            updateTimerDisplay();
        }

        // Ensure player is still playing
        if (player && isTimerRunning) {
            const playerState = player.getPlayerState();
            if (playerState !== YT.PlayerState.PLAYING && playerState !== YT.PlayerState.BUFFERING) {
                console.log('Player was paused in background, resuming...');
                player.playVideo();
            }
        }
    }
});

// Initialize timer display when page loads
document.addEventListener('DOMContentLoaded', function() {
    updateTimerDisplay();
    
    // Keep-alive mechanism to prevent background tab throttling
    setInterval(() => {
        if (isTimerRunning && document.hidden) {
            // Force timer update even in background
            timerElapsedTime = Date.now() - timerStartTime;
        }
    }, 5000); // Check every 5 seconds
});

// Prevent YouTube player from pausing in background tabs
function enableBackgroundPlayback() {
    if (player) {
        try {
            console.log('Enabling advanced background playback prevention...');
            
            // Create Web Audio context to keep audio active
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Keep audio context alive to prevent auto-pause
            const keepAlive = () => {
                if (audioContext.state === 'suspended') {
                    audioContext.resume().catch(() => {});
                }
            };
            
            // Check every 2 seconds and on visibility change
            setInterval(keepAlive, 2000);
            
            // Resume audio context on user interaction
            ['click', 'keydown', 'touchstart'].forEach(event => {
                document.addEventListener(event, () => {
                    if (audioContext.state === 'suspended') {
                        audioContext.resume().catch(() => {});
                    }
                }, { once: true });
            });
            
            // Force iframe to stay active
            const iframe = document.querySelector('#youtube-player iframe');
            if (iframe) {
                iframe.style.position = 'fixed';
                iframe.style.left = '-9999px';
                iframe.style.visibility = 'hidden';
                iframe.style.pointerEvents = 'none';
                iframe.setAttribute('allow', 'autoplay; fullscreen');
            }
            
            // Prevent page from being considered idle
            const preventIdle = () => {
                // Micro movement to prevent idle state
                if (document.hidden && player && player.getPlayerState() === YT.PlayerState.PLAYING) {
                    console.log('Keeping player active while tab is hidden');
                }
            };
            
            setInterval(preventIdle, 10000); // Every 10 seconds
            
        } catch (error) {
            console.log('Background playback enhancement failed:', error);
        }
    }
}

// Setup Media Session API for better background playback support
function setupMediaSession() {
    if ('mediaSession' in navigator) {
        console.log('Setting up Media Session API for background playback');

        navigator.mediaSession.metadata = new MediaMetadata({
            title: 'Background Music Player',
            artist: 'YouTube Playlist',
            album: 'Music Collection'
        });

        // Set up media session action handlers
        navigator.mediaSession.setActionHandler('play', () => {
            if (player) player.playVideo();
        });

        navigator.mediaSession.setActionHandler('pause', () => {
            if (player) player.pauseVideo();
        });

        navigator.mediaSession.setActionHandler('previoustrack', () => {
            if (player) player.previousVideo();
        });

        navigator.mediaSession.setActionHandler('nexttrack', () => {
            if (player) player.nextVideo();
        });

        // Update media session when track changes
        navigator.mediaSession.playbackState = 'playing';
    }
}

// Enhanced background playback prevention
function preventAutoPause() {
    console.log('Setting up enhanced background playback prevention...');

    let keepAliveInterval;

    // Create Web Audio context to keep audio active
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();

    // Keep audio context alive to prevent auto-pause
    const keepAlive = () => {
        if (audioContext.state === 'suspended') {
            audioContext.resume().catch(() => {});
        }

        // Micro activity to prevent idle state
        if (document.hidden && player && player.getPlayerState() === YT.PlayerState.PLAYING) {
            console.log('Keeping player active while tab is hidden');
        }
    };

    // Check every 30 seconds and on visibility change
    keepAliveInterval = setInterval(keepAlive, 30000);

    // Resume audio context on user interaction
    ['click', 'keydown', 'touchstart'].forEach(event => {
        document.addEventListener(event, () => {
            if (audioContext.state === 'suspended') {
                audioContext.resume().catch(() => {});
            }
        }, { once: true });
    });

    // Force iframe to stay active
    const iframe = document.querySelector('#youtube-player iframe');
    if (iframe) {
        iframe.style.position = 'fixed';
        iframe.style.left = '-9999px';
        iframe.style.visibility = 'hidden';
        iframe.style.pointerEvents = 'none';
        iframe.setAttribute('allow', 'autoplay; fullscreen');
    }

    // Store interval ID for cleanup
    return keepAliveInterval;
}

