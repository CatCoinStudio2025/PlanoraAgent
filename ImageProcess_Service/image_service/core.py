"""
Core image processing logic
Xử lý ảnh theo flow: validate -> load -> optimize -> save -> create objects
"""

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

from .models import Document, Page, DocumentStatus
from .config import ImageServiceConfig, get_config
from .storage import ImageStorage
from .metadata import MetadataExtractor

logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """Exception cho image processing errors"""
    
    def __init__(self, message: str, file_path: str = None):
        self.file_path = file_path
        super().__init__(message)


class ImageProcessor:
    """Core image processor - xử lý ảnh thành Document objects"""
    
    def __init__(self, config: ImageServiceConfig = None):
        self.config = config or get_config()
        self.storage = ImageStorage(self.config)
        self.metadata_extractor = MetadataExtractor(self.config)
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def validate_file(self, file_path: str) -> None:
        """
        Validate input file
        
        Args:
            file_path: Path to image file
            
        Raises:
            ImageProcessingError: If file is invalid
        """
        if not file_path:
            raise ImageProcessingError("File path is required")
        
        path = Path(file_path)
        
        # Check file exists
        if not path.exists():
            raise ImageProcessingError(f"File not found: {file_path}", file_path)
        
        # Check is file (not directory)
        if not path.is_file():
            raise ImageProcessingError(f"Path is not a file: {file_path}", file_path)
        
        # Check file size
        if path.stat().st_size == 0:
            raise ImageProcessingError(f"File is empty: {file_path}", file_path)
        
        # Check supported format
        if not self.config.is_supported_format(file_path):
            raise ImageProcessingError(
                f"Unsupported format: {path.suffix}. Supported: {self.config.supported_extensions}",
                file_path
            )
        
        logger.debug(f"File validation passed: {file_path}")
    
    def load_image(self, file_path: str) -> Image.Image:
        """
        Load image using PIL
        
        Args:
            file_path: Path to image file
            
        Returns:
            PIL Image object
            
        Raises:
            ImageProcessingError: If image cannot be loaded
        """
        try:
            with Image.open(file_path) as img:
                # Load image data into memory
                img.load()
                # Return copy to avoid file handle issues
                return img.copy()
                
        except Image.UnidentifiedImageError as e:
            raise ImageProcessingError(f"Unrecognized image format: {e}", file_path)
        except Exception as e:
            raise ImageProcessingError(f"Failed to load image: {e}", file_path)
    
    def optimize_image(self, image: Image.Image) -> Image.Image:
        """
        Optimize image: convert mode, resize if needed
        Based on docpixie's _optimize_image logic
        
        Args:
            image: PIL Image object
            
        Returns:
            Optimized PIL Image object
        """
        try:
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                rgb_img = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    rgb_img.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                elif image.mode == 'P' and 'transparency' in image.info:
                    # Handle palette mode with transparency
                    image = image.convert('RGBA')
                    rgb_img.paste(image, mask=image.split()[-1])
                else:
                    rgb_img.paste(image)
                image = rgb_img
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if image is too large
            max_width, max_height = self.config.pdf_max_image_size
            if image.width > max_width or image.height > max_height:
                # Calculate new size maintaining aspect ratio
                ratio = min(max_width / image.width, max_height / image.height)
                new_width = int(image.width * ratio)
                new_height = int(image.height * ratio)
                
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.debug(f"Resized image to {new_width}x{new_height}")
            
            return image
            
        except Exception as e:
            raise ImageProcessingError(f"Failed to optimize image: {e}")
    
    def process_image_sync(
        self, 
        file_path: str, 
        workspace: str = None,
        output_format: str = None
    ) -> Tuple[Page, str, str]:
        """
        Synchronous image processing
        
        Args:
            file_path: Path to input image
            workspace: Workspace path
            output_format: Output format (webp, jpeg)
            
        Returns:
            Tuple[Page, saved_path, thumbnail_path]
        """
        output_format = output_format or self.config.default_output_format
        
        try:
            # Load original image
            original_image = self.load_image(file_path)
            original_size = original_image.size
            
            # Optimize image
            optimized_image = self.optimize_image(original_image)
            final_size = optimized_image.size
            
            # Save optimized image
            saved_path, file_size = self.storage.save_image(
                optimized_image, file_path, workspace, output_format
            )
            
            # Create thumbnail (parallel task)
            thumbnail_path = None
            if self.config.enable_thumbnails:
                thumbnail_path = self.storage.create_thumbnail(
                    optimized_image, 
                    Path(saved_path).name,
                    workspace
                )
            
            # Extract metadata
            metadata = self.metadata_extractor.create_image_metadata(
                original_image, file_path, final_size
            )
            
            # Update metadata with file size from saved image
            metadata.file_size = file_size
            
            # Create Page object
            page = Page(
                page_number=1,
                text_content=None,  # Images don't have text content
                image_path=saved_path,
                thumbnail_path=thumbnail_path,
                metadata=metadata
            )
            
            logger.info(f"Successfully processed image: {file_path} -> {saved_path}")
            return page, saved_path, thumbnail_path
            
        except Exception as e:
            logger.error(f"Failed to process image {file_path}: {e}")
            raise ImageProcessingError(f"Image processing failed: {e}", file_path)
    
    async def process_image_async(
        self, 
        file_path: str, 
        workspace: str = None,
        output_format: str = None
    ) -> Tuple[Page, str, str]:
        """
        Asynchronous image processing wrapper
        
        Args:
            file_path: Path to input image
            workspace: Workspace path
            output_format: Output format
            
        Returns:
            Tuple[Page, saved_path, thumbnail_path]
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.process_image_sync,
            file_path,
            workspace,
            output_format
        )
    
    def create_document(
        self, 
        page: Page, 
        original_file_path: str,
        document_id: str = None
    ) -> Document:
        """
        Create Document object từ Page
        
        Args:
            page: Page object
            original_file_path: Path to original file
            document_id: Optional custom document ID
            
        Returns:
            Document object
        """
        try:
            # Generate document title from filename
            title = Path(original_file_path).name
            
            # Create document metadata
            metadata = {
                "original_file": original_file_path,
                "processor": "ImageProcessor",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "file_size": page.metadata.file_size,
                "image_format": page.metadata.format,
                "dimensions": f"{page.metadata.width}x{page.metadata.height}"
            }
            
            # Create Document object
            document = Document(
                id=document_id or f"doc_img_{int(time.time())}",
                title=title,
                file_path=page.image_path,  # Point to processed image
                num_pages=1,
                pages=[page],
                status=DocumentStatus.COMPLETED,
                metadata=metadata
            )
            
            # Update page references
            document.update_page_references()
            
            logger.info(f"Created document: {document.id} with 1 page")
            return document
            
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise ImageProcessingError(f"Document creation failed: {e}")
    
    async def process(
        self, 
        file_path: str, 
        workspace: str = None,
        output_format: str = None,
        document_id: str = None
    ) -> Document:
        """
        Main processing method - async interface
        
        Args:
            file_path: Path to input image
            workspace: Workspace path
            output_format: Output format
            document_id: Optional custom document ID
            
        Returns:
            Document object
        """
        start_time = time.time()
        
        try:
            # Validate input file
            self.validate_file(file_path)
            
            # Ensure workspace directories exist
            self.config.ensure_directories(workspace)
            
            # Process image
            page, saved_path, thumbnail_path = await self.process_image_async(
                file_path, workspace, output_format
            )
            
            # Create document
            document = self.create_document(page, file_path, document_id)
            
            processing_time = time.time() - start_time
            logger.info(f"Image processing completed in {processing_time:.2f}s")
            
            return document
            
        except ImageProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing {file_path}: {e}")
            raise ImageProcessingError(f"Processing failed: {e}", file_path)
    
    def process_sync(
        self, 
        file_path: str, 
        workspace: str = None,
        output_format: str = None,
        document_id: str = None
    ) -> Document:
        """
        Synchronous processing method
        
        Args:
            file_path: Path to input image
            workspace: Workspace path
            output_format: Output format
            document_id: Optional custom document ID
            
        Returns:
            Document object
        """
        start_time = time.time()
        
        try:
            # Validate input file
            self.validate_file(file_path)
            
            # Ensure workspace directories exist
            self.config.ensure_directories(workspace)
            
            # Process image
            page, saved_path, thumbnail_path = self.process_image_sync(
                file_path, workspace, output_format
            )
            
            # Create document
            document = self.create_document(page, file_path, document_id)
            
            processing_time = time.time() - start_time
            logger.info(f"Image processing completed in {processing_time:.2f}s")
            
            return document
            
        except ImageProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing {file_path}: {e}")
            raise ImageProcessingError(f"Processing failed: {e}", file_path)
    
    def get_supported_formats(self) -> list:
        """Get list of supported image formats"""
        return self.config.supported_extensions.copy()
    
    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)