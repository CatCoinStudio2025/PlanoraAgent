"""
FastAPI REST API for image processing service
Endpoints: POST /process_image/, GET /health
"""

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core import ImageProcessor, ImageProcessingError
from .models import ProcessImageResponse, HealthResponse, Document
from .config import get_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Image Processing Service",
    description="Microservice để xử lý ảnh thành Document objects tương thích với Document Assembly",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize processor
config = get_config()
processor = ImageProcessor(config)


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting Image Processing Service...")
    
    # Ensure default directories exist
    try:
        config.ensure_directories()
        logger.info("Service directories initialized")
    except Exception as e:
        logger.error(f"Failed to initialize directories: {e}")
    
    logger.info("Image Processing Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Image Processing Service...")
    processor.cleanup()
    logger.info("Service shutdown complete")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns:
        HealthResponse: Service health status
    """
    try:
        # Check if service is operational
        supported_formats = processor.get_supported_formats()
        
        return HealthResponse(
            status="healthy",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            service="image_service",
            version="1.0.0",
            supported_formats=supported_formats
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {e}"
        )


@app.post("/process_image/", response_model=ProcessImageResponse)
async def process_image(
    file: UploadFile = File(..., description="Image file to process"),
    workspace: Optional[str] = Form(None, description="Workspace path (optional)"),
    output_format: Optional[str] = Form("webp", description="Output format (webp, jpeg)"),
    document_id: Optional[str] = Form(None, description="Custom document ID (optional)")
):
    """
    Process uploaded image file
    
    Args:
        file: Uploaded image file
        workspace: Optional workspace path
        output_format: Output format (webp, jpeg)
        document_id: Optional custom document ID
        
    Returns:
        ProcessImageResponse: Processed document with page data
        
    Raises:
        HTTPException: If processing fails
    """
    temp_file_path = None
    
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Check file size
        if file.size and file.size > config.max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {config.max_file_size} bytes"
            )
        
        # Validate output format
        if output_format not in ["webp", "jpeg"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid output format. Supported: webp, jpeg"
            )
        
        # Create temporary file
        file_extension = Path(file.filename).suffix.lower()
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=file_extension,
            prefix="upload_"
        ) as temp_file:
            temp_file_path = temp_file.name
            
            # Save uploaded file
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
        
        logger.info(f"Processing uploaded file: {file.filename} ({len(content)} bytes)")
        
        # Process image
        document = await processor.process(
            file_path=temp_file_path,
            workspace=workspace,
            output_format=output_format,
            document_id=document_id
        )
        
        # Create response
        response = ProcessImageResponse(
            success=True,
            message="Image processed successfully",
            document=document,
            processing_time=0.0  # Will be calculated by processor
        )
        
        logger.info(f"Successfully processed: {file.filename} -> {document.id}")
        return response
        
    except ImageProcessingError as e:
        logger.error(f"Image processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}"
        )
    finally:
        # Cleanup temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temp file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file_path}: {e}")


@app.get("/formats")
async def get_supported_formats():
    """
    Get list of supported image formats
    
    Returns:
        dict: Supported formats and extensions
    """
    try:
        formats = processor.get_supported_formats()
        return {
            "supported_formats": formats,
            "max_file_size": config.max_file_size,
            "default_output_format": config.default_output_format
        }
    except Exception as e:
        logger.error(f"Error getting formats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/config")
async def get_service_config():
    """
    Get service configuration (for debugging)
    
    Returns:
        dict: Service configuration
    """
    try:
        return {
            "max_image_size": config.pdf_max_image_size,
            "thumbnail_size": config.thumbnail_size,
            "supported_formats": config.supported_extensions,
            "default_output_format": config.default_output_format,
            "enable_thumbnails": config.enable_thumbnails,
            "image_quality": config.image_quality
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Error handlers
@app.exception_handler(ImageProcessingError)
async def image_processing_exception_handler(request, exc: ImageProcessingError):
    """Handle ImageProcessingError exceptions"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": str(exc),
            "file_path": exc.file_path,
            "error_type": "ImageProcessingError"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "error_type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run development server
    uvicorn.run(
        "image_service.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )