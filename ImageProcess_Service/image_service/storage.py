"""
Storage management cho Image Service
Quản lý việc lưu ảnh, thumbnail và file paths
"""

import os
import hashlib
import shutil
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
import logging

from .config import ImageServiceConfig

logger = logging.getLogger(__name__)


class ImageStorage:
    """Quản lý storage cho images và thumbnails"""
    
    def __init__(self, config: ImageServiceConfig):
        self.config = config
    
    def generate_filename(self, original_path: str, format: str = "webp") -> str:
        """
        Tạo filename unique dựa trên MD5 hash của file path và timestamp
        """
        # Tạo hash từ original path
        hash_input = f"{original_path}_{os.path.getmtime(original_path) if os.path.exists(original_path) else ''}"
        file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        
        # Tạo filename với format
        extension = "jpg" if format.lower() == "jpeg" else format.lower()
        return f"img_{file_hash}.{extension}"
    
    def generate_thumbnail_filename(self, image_filename: str) -> str:
        """Tạo thumbnail filename từ image filename"""
        stem = Path(image_filename).stem
        return f"thumb_{stem}.jpg"
    
    def save_image(
        self, 
        image: Image.Image, 
        original_path: str,
        workspace: str = None,
        format: str = "webp"
    ) -> Tuple[str, int]:
        """
        Lưu ảnh vào image store
        
        Returns:
            Tuple[str, int]: (saved_path, file_size)
        """
        # Ensure directories exist
        self.config.ensure_directories(workspace)
        
        # Generate filename và path
        filename = self.generate_filename(original_path, format)
        image_store_path = self.config.get_image_store_path(workspace)
        save_path = image_store_path / filename
        
        # Save image với quality settings
        save_kwargs = {"optimize": True}
        if format.lower() in ["jpeg", "jpg"]:
            save_kwargs["quality"] = self.config.jpeg_quality
            save_format = "JPEG"
        elif format.lower() == "webp":
            save_kwargs["quality"] = self.config.webp_quality
            save_format = "WEBP"
        else:
            save_format = format.upper()
        
        try:
            image.save(str(save_path), save_format, **save_kwargs)
            file_size = save_path.stat().st_size
            
            logger.info(f"Saved image: {save_path} ({file_size} bytes)")
            return str(save_path), file_size
            
        except Exception as e:
            logger.error(f"Failed to save image {save_path}: {e}")
            raise
    
    def create_thumbnail(
        self, 
        image: Image.Image, 
        original_filename: str,
        workspace: str = None
    ) -> Optional[str]:
        """
        Tạo và lưu thumbnail
        
        Returns:
            str: thumbnail path hoặc None nếu fail
        """
        if not self.config.enable_thumbnails:
            return None
        
        try:
            # Ensure thumbnail directory exists
            thumbnail_path = self.config.get_thumbnail_path(workspace)
            thumbnail_path.mkdir(parents=True, exist_ok=True)
            
            # Create thumbnail
            thumbnail = image.copy()
            thumbnail.thumbnail(
                (self.config.thumbnail_size, self.config.thumbnail_size), 
                Image.Resampling.LANCZOS
            )
            
            # Convert to RGB if needed (for JPEG)
            if thumbnail.mode in ('RGBA', 'LA', 'P'):
                rgb_thumbnail = Image.new('RGB', thumbnail.size, (255, 255, 255))
                if thumbnail.mode == 'RGBA':
                    rgb_thumbnail.paste(thumbnail, mask=thumbnail.split()[-1])
                else:
                    rgb_thumbnail.paste(thumbnail)
                thumbnail = rgb_thumbnail
            
            # Generate thumbnail filename và save
            thumb_filename = self.generate_thumbnail_filename(original_filename)
            thumb_save_path = thumbnail_path / thumb_filename
            
            thumbnail.save(
                str(thumb_save_path), 
                "JPEG", 
                quality=85, 
                optimize=True
            )
            
            logger.info(f"Created thumbnail: {thumb_save_path}")
            return str(thumb_save_path)
            
        except Exception as e:
            logger.error(f"Failed to create thumbnail: {e}")
            return None
    
    def copy_original_file(
        self, 
        source_path: str, 
        workspace: str = None
    ) -> Optional[str]:
        """
        Copy original file vào workspace (optional backup)
        
        Returns:
            str: copied file path hoặc None nếu fail
        """
        try:
            # Ensure directories exist
            self.config.ensure_directories(workspace)
            
            source = Path(source_path)
            if not source.exists():
                logger.warning(f"Source file not found: {source_path}")
                return None
            
            # Generate destination path
            image_store_path = self.config.get_image_store_path(workspace)
            dest_filename = f"original_{source.name}"
            dest_path = image_store_path / dest_filename
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied original file: {source_path} -> {dest_path}")
            
            return str(dest_path)
            
        except Exception as e:
            logger.error(f"Failed to copy original file {source_path}: {e}")
            return None
    
    def cleanup_temp_files(self, temp_paths: list):
        """Clean up temporary files"""
        for temp_path in temp_paths:
            try:
                if os.path.exists(temp_path):
                    if os.path.isfile(temp_path):
                        os.remove(temp_path)
                    elif os.path.isdir(temp_path):
                        shutil.rmtree(temp_path)
                    logger.debug(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")
    
    def get_storage_info(self, workspace: str = None) -> dict:
        """Lấy thông tin storage"""
        image_store_path = self.config.get_image_store_path(workspace)
        thumbnail_path = self.config.get_thumbnail_path(workspace)
        
        info = {
            "image_store_path": str(image_store_path),
            "thumbnail_path": str(thumbnail_path),
            "image_store_exists": image_store_path.exists(),
            "thumbnail_path_exists": thumbnail_path.exists(),
        }
        
        # Count files if directories exist
        if image_store_path.exists():
            info["image_count"] = len(list(image_store_path.glob("img_*.{webp,jpg,jpeg,png}")))
        
        if thumbnail_path.exists():
            info["thumbnail_count"] = len(list(thumbnail_path.glob("thumb_*.jpg")))
        
        return info