from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import base64
import io
from PIL import Image
import openai
from typing import Optional, List
import uuid
import aiofiles
import logging
import traceback
import datetime
import random
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load OpenRouter API key from environment
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables")

# Initialize OpenRouter client (using OpenAI SDK with custom base URL)
client = openai.OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# Available image generation models
IMAGE_MODELS = {
    "gemini-3-pro": "google/gemini-3-pro-image-preview",
    "gemini-2.5-flash": "google/gemini-2.5-flash-image",
    "gemini-2.5-flash-preview": "google/gemini-2.5-flash-image-preview",
    "gpt-5-mini": "openai/gpt-5-image-mini",
    "gpt-5": "openai/gpt-5-image"
}

# Test OpenRouter API key at startup
def validate_openrouter_key():
    """Validate OpenRouter API key at startup"""
    try:
        # Try a simple API call to validate the key
        client.models.list()
        logger.info("OpenRouter API key validated successfully")
        return True
    except Exception as e:
        logger.error(f"Invalid OpenRouter API key or connection error: {str(e)}")
        return False

# OpenAI Image Constraints
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB limit
SUPPORTED_SIZES = [(1024, 1024), (1024, 1536), (1536, 1024)]  # For gpt-image-1
MAX_DIMENSION = 1536  # Maximum dimension allowed

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the images directory exists
os.makedirs("images", exist_ok=True)

# Validate OpenRouter key at startup
if not validate_openrouter_key():
    logger.warning("OpenRouter API key validation failed. Image enhancement features may not work.")

# Mount static files
app.mount("/assets", StaticFiles(directory="../frontend/assets"), name="assets")

def resize_image_to_fit(image: Image.Image, max_size: int = MAX_DIMENSION) -> Image.Image:
    """
    Resize image to fit within the maximum dimensions while maintaining aspect ratio.
    """
    width, height = image.size
    
    # If image is already within bounds, return as is
    if width <= max_size and height <= max_size:
        return image
    
    # Calculate the scaling factor
    scale = min(max_size / width, max_size / height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    # Find the closest supported size
    best_size = None
    min_diff = float('inf')
    
    for supported_width, supported_height in SUPPORTED_SIZES:
        # Check if the aspect ratio is compatible
        if (new_width <= supported_width and new_height <= supported_height) or \
           (new_height <= supported_width and new_width <= supported_height):
            diff = abs(new_width * new_height - supported_width * supported_height)
            if diff < min_diff:
                min_diff = diff
                if new_width > new_height:
                    best_size = (supported_width, supported_height)
                else:
                    best_size = (supported_height, supported_width)
    
    # If no perfect fit, use square format
    if best_size is None:
        best_size = (1024, 1024)
    
    # Resize the image
    resized = image.resize(best_size, Image.Resampling.LANCZOS)
    logger.info(f"Resized image from {image.size} to {resized.size}")
    
    return resized

def compress_image(image: Image.Image, max_size_bytes: int = MAX_FILE_SIZE) -> io.BytesIO:
    """
    Compress image to ensure it's under the file size limit.
    """
    output = io.BytesIO()
    quality = 95
    
    # First try with high quality
    image.save(output, format='PNG', optimize=True)
    
    # If still too large, try progressively lower quality with JPEG
    while output.tell() > max_size_bytes and quality > 10:
        output = io.BytesIO()
        # Convert to RGB for JPEG if needed
        if image.mode == 'RGBA':
            # Create a white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            jpeg_image = background
        else:
            jpeg_image = image.convert('RGB')
        
        jpeg_image.save(output, format='JPEG', quality=quality, optimize=True)
        quality -= 10
        
        if output.tell() <= max_size_bytes:
            # Convert back to PNG for OpenAI API
            output.seek(0)
            jpeg_image = Image.open(output)
            output = io.BytesIO()
            # Convert back to RGBA
            if jpeg_image.mode != 'RGBA':
                jpeg_image = jpeg_image.convert('RGBA')
            jpeg_image.save(output, format='PNG', optimize=True)
    
    output.seek(0)
    logger.info(f"Compressed image to {output.tell()} bytes")
    return output

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image to meet OpenAI API requirements.
    """
    # Log original image info
    logger.info(f"Original image: format={image.format}, size={image.size}, mode={image.mode}")
    
    # Note: verify() modifies the image object, so we skip it here
    # The image has already been opened successfully from bytes, so it's valid
    
    # Ensure RGBA mode
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
        logger.info(f"Converted image mode to RGBA")
    
    # Check if resizing is needed
    width, height = image.size
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        image = resize_image_to_fit(image)
    
    return image

@app.post("/api/enhance-image")
async def enhance_image(
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(""),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    model: str = Form("gpt-5-mini")
):
    temp_filename = None  # Initialize to track temp file for cleanup

    # Validate model
    if model not in IMAGE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {model}. Supported models: {', '.join(IMAGE_MODELS.keys())}"
        )

    # Get the full model ID for OpenRouter
    model_id = IMAGE_MODELS[model]

    # Валидные значения для size и quality
    VALID_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}
    VALID_QUALITIES = {"low", "medium", "high", "auto"}

    # Валидация size
    if size not in VALID_SIZES:
        raise HTTPException(status_code=400, detail=f"Invalid size: {size}. Supported: {', '.join(VALID_SIZES)}")
    # Валидация quality
    if quality not in VALID_QUALITIES:
        raise HTTPException(status_code=400, detail=f"Invalid quality: {quality}. Supported: {', '.join(VALID_QUALITIES)}")
    
    try:
        # Log file details
        logger.info(f"Received file: {file.filename}, content_type: {file.content_type}")
        
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read the uploaded file
        contents = await file.read()
        logger.info(f"Original file size: {len(contents)} bytes")
        
        # Check initial file size
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )

        # Convert the uploaded image to PNG (required by the OpenAI edit endpoint)
        try:
            pil_image = Image.open(io.BytesIO(contents))
            logger.info(f"Image format: {pil_image.format}, size: {pil_image.size}, mode: {pil_image.mode}")
            
            # Preprocess the image (resize, convert to RGBA, etc.)
            pil_image = preprocess_image(pil_image)
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Unable to read the uploaded image: {str(e)}")

        # Save the preprocessed image as PNG with compression if needed
        temp_filename = f"images/temp_{uuid.uuid4()}.png"
        
        # First try to save normally
        pil_image.save(temp_filename, format="PNG", optimize=True)
        
        # Check if file is too large and compress if needed
        file_size = os.path.getsize(temp_filename)
        logger.info(f"Saved file size: {file_size} bytes")
        
        if file_size > MAX_FILE_SIZE:
            logger.info("File too large, compressing...")
            compressed_buffer = compress_image(pil_image)
            with open(temp_filename, 'wb') as f:
                f.write(compressed_buffer.getvalue())
            file_size = os.path.getsize(temp_filename)
            logger.info(f"Compressed file size: {file_size} bytes")
        
        logger.info(f"Saved temporary file: {temp_filename}")
        
        # Prepare the enhancement prompt
        enhancement_prompt = "Make a copy of an image. Do not change the image in any way if no Additional instructions are provided."
        if prompt:
            enhancement_prompt += f" Additional instructions: {prompt}"

        # Encode image as base64 for OpenRouter
        with open(temp_filename, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        # Use OpenRouter chat/completions API for image generation
        try:
            logger.info(f"Sending request to OpenRouter API with model: {model_id}, size={size}, quality={quality}")

            # Build the request payload
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": enhancement_prompt
                        }
                    ]
                }
            ]

            # Call OpenRouter API
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                modalities=["image", "text"],
                max_tokens=1000
            )
            logger.info("Received response from OpenRouter API")
        except openai.BadRequestError as e:
            logger.error(f"OpenRouter BadRequestError: {str(e)}")

            # Provide user-friendly error message
            error_msg = str(e)
            if "Invalid image format" in error_msg:
                raise HTTPException(status_code=400, detail="Invalid image format. Please upload a valid PNG, JPEG, or similar image.")
            elif "Image size" in error_msg or "too large" in error_msg:
                raise HTTPException(status_code=400, detail="Image dimensions or file size too large. Please upload a smaller image.")
            elif "Invalid input image" in error_msg:
                raise HTTPException(status_code=400, detail="The image couldn't be processed. Please try a different image or check the format.")
            else:
                raise HTTPException(status_code=400, detail=f"OpenRouter API error: {error_msg}")
        except openai.APIConnectionError as e:
            logger.error(f"OpenRouter connection error: {str(e)}")
            raise HTTPException(status_code=503, detail="Unable to connect to OpenRouter API. Please try again.")
        except openai.RateLimitError as e:
            logger.error(f"OpenRouter rate limit error: {str(e)}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment and try again.")
        except openai.APIError as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"OpenRouter API error: {str(e)}")
        except Exception as e:
            logger.error(f"[{datetime.datetime.now().isoformat()}] Unexpected error in enhance_image: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

        # Parse the response from OpenRouter
        try:
            if not response.choices or len(response.choices) == 0:
                raise HTTPException(status_code=500, detail="OpenRouter did not return any response.")

            choice = response.choices[0]
            message = choice.message

            # OpenRouter returns images in message.images array
            if (not hasattr(message, 'images') or not message.images) and not message.refusal:
                logger.error(f"No images found in response. Message: {message}")
                raise HTTPException(status_code=500, detail="OpenRouter did not return an image.")

            if message.refusal:
                logger.error(f"Model refused to generate image. Refusal: {message.refusal}")
                raise HTTPException(status_code=400, detail=f"The model refused to generate an image. Reason: {message.refusal}")


            # Extract the first image
            image_data = message.images[0]

            # Get the image URL (base64 data URL)
            if hasattr(image_data, 'image_url') and hasattr(image_data.image_url, 'url'):
                image_url = image_data.image_url.url
            elif isinstance(image_data, dict) and 'image_url' in image_data:
                image_url = image_data['image_url']['url']
            else:
                logger.error(f"Unexpected image data structure: {image_data}")
                raise HTTPException(status_code=500, detail="Unexpected image format in response.")

            # Extract base64 data
            if image_url.startswith('data:image'):
                # Remove the "data:image/png;base64," prefix
                base64_data = image_url.split(',', 1)[1]
                image_bytes = base64.b64decode(base64_data)
            else:
                # If it's a regular URL, download it
                import requests
                download_resp = requests.get(image_url)
                download_resp.raise_for_status()
                image_bytes = download_resp.content

            logger.info(f"Successfully extracted image, size: {len(image_bytes)} bytes")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error parsing OpenRouter response: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error parsing response: {str(e)}")
        
        # Return the enhanced image
        return StreamingResponse(
            io.BytesIO(image_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=enhanced_{file.filename}"
            }
        )
            
    except HTTPException:
        # Re-raise HTTP exceptions as they already have proper error messages
        raise
    except Exception as e:
        # Log unexpected errors with traceback
        logger.error(f"[{datetime.datetime.now().isoformat()}] Unexpected error in enhance_image: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    finally:
        # Always clean up temporary file
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                logger.info(f"Cleaned up temporary file: {temp_filename}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary file {temp_filename}: {str(e)}")

@app.post("/api/enhance-image-multi")
async def enhance_image_multi(
    files: List[UploadFile] = File(...),
    prompt: Optional[str] = Form(""),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    model: str = Form("gpt-5-mini"),
    seed: Optional[int] = Form(None)
):
    """Process multiple input images together and return one enhanced result"""

    temp_filenames = []

    try:
        # Validate model
        if model not in IMAGE_MODELS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model: {model}. Supported models: {', '.join(IMAGE_MODELS.keys())}"
            )

        model_id = IMAGE_MODELS[model]

        # Validate parameters
        VALID_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}
        VALID_QUALITIES = {"low", "medium", "high", "auto"}

        if size not in VALID_SIZES:
            raise HTTPException(status_code=400, detail=f"Invalid size: {size}")
        if quality not in VALID_QUALITIES:
            raise HTTPException(status_code=400, detail=f"Invalid quality: {quality}")

        # Check file count
        if len(files) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 images allowed per request")

        logger.info(f"Processing {len(files)} images with model: {model_id}, seed: {seed}")

        # Process all files
        image_base64_list = []

        for idx, file in enumerate(files):
            # Validate file type
            if not file.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail=f"File {idx+1} must be an image")

            # Read file
            contents = await file.read()

            if len(contents) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {idx+1} exceeds maximum size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
                )

            # Process image
            try:
                pil_image = Image.open(io.BytesIO(contents))
                pil_image = preprocess_image(pil_image)

                # Save to temp file
                temp_filename = f"images/temp_{uuid.uuid4()}.png"
                pil_image.save(temp_filename, format="PNG", optimize=True)
                temp_filenames.append(temp_filename)

                # Encode as base64
                with open(temp_filename, "rb") as image_file:
                    image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                    image_base64_list.append(image_base64)

            except Exception as e:
                logger.error(f"Error processing image {idx+1}: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Unable to process image {idx+1}: {str(e)}")

        # Prepare the enhancement prompt
        enhancement_prompt = prompt if prompt else "Process these images."

        # Build message with all images
        content_parts = []
        for image_base64 in image_base64_list:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}"
                }
            })

        # Add text prompt
        content_parts.append({
            "type": "text",
            "text": enhancement_prompt
        })

        messages = [{
            "role": "user",
            "content": content_parts
        }]

        # Call OpenRouter API
        try:
            logger.info(f"Sending {len(files)} images to OpenRouter API")

            api_params = {
                "model": model_id,
                "messages": messages,
                "modalities": ["image", "text"],
                "max_tokens": 1000
            }

            # Add seed if provided (for variation control)
            if seed is not None:
                api_params["seed"] = random.randint(0, 2**31 - 1)
            else:
                api_params["seed"] = random.randint(0, 2**31 - 1)

            response = client.chat.completions.create(**api_params)

            logger.info("Received response from OpenRouter API")

        except openai.BadRequestError as e:
            logger.error(f"OpenRouter BadRequestError: {str(e)}")
            raise HTTPException(status_code=400, detail=f"OpenRouter API error: {str(e)}")
        except openai.APIConnectionError as e:
            logger.error(f"OpenRouter connection error: {str(e)}")
            raise HTTPException(status_code=503, detail="Unable to connect to OpenRouter API. Please try again.")
        except openai.RateLimitError as e:
            logger.error(f"OpenRouter rate limit error: {str(e)}")
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment and try again.")
        except openai.APIError as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"OpenRouter API error: {str(e)}")

        # Parse response
        try:
            if not response.choices or len(response.choices) == 0:
                raise HTTPException(status_code=500, detail="OpenRouter did not return any response.")

            choice = response.choices[0]
            message = choice.message

            if (not hasattr(message, 'images') or not message.images) and not message.refusal:
                logger.error(f"No images found in response. Message: {message}")
                raise HTTPException(status_code=500, detail="OpenRouter did not return an image.")

            if message.refusal:
                logger.error(f"Model refused to generate image. Refusal: {message.refusal}")
                raise HTTPException(status_code=400, detail=f"The model refused to generate an image. Reason: {message.refusal}")

            # Extract the first image
            image_data = message.images[0]

            if hasattr(image_data, 'image_url') and hasattr(image_data.image_url, 'url'):
                image_url = image_data.image_url.url
            elif isinstance(image_data, dict) and 'image_url' in image_data:
                image_url = image_data['image_url']['url']
            else:
                logger.error(f"Unexpected image data structure: {image_data}")
                raise HTTPException(status_code=500, detail="Unexpected image format in response.")

            # Extract base64 data
            if image_url.startswith('data:image'):
                base64_data = image_url.split(',', 1)[1]
                image_bytes = base64.b64decode(base64_data)
            else:
                import requests
                download_resp = requests.get(image_url)
                download_resp.raise_for_status()
                image_bytes = download_resp.content

            logger.info(f"Successfully extracted image, size: {len(image_bytes)} bytes")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error parsing OpenRouter response: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error parsing response: {str(e)}")

        # Return the enhanced image
        return StreamingResponse(
            io.BytesIO(image_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=enhanced_multi.png"
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions as they already have proper error messages
        raise
    except Exception as e:
        # Log unexpected errors with traceback
        logger.error(f"[{datetime.datetime.now().isoformat()}] Unexpected error in enhance_image: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
    finally:
        # Always clean up temporary file
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                logger.info(f"Cleaned up temporary file: {temp_filename}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary file {temp_filename}: {str(e)}")

@app.get("/")
async def serve_index():
    """Serve the main index.html file"""
    return FileResponse("../frontend/index.html")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Image Enhancer API"} 