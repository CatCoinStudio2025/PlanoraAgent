"""
Configuration cho Image Service
Quản lý các settings và paths
"""

import os
from pathlib import Path
from typing import Tuple, List
from pydantic import BaseSettings, Field


class ImageServiceConfig(BaseSettings):
    """Configuration settings cho Image Service"""
    
    # Image processing settings
    max_width: int = Field(default=2048, description="Max width cho resize")
    max_height: int = Field(default=2048, description="Max height cho resize")
    jpeg_quality: int = Field(default=85, description="JPEG quality (1-100)")
    webp_quality: int = Field(default=80, description="WebP quality (1-100)")
    thumbnail_size: int = Field(default=200, description="Thumbnail size (pixels)")
    
    # Supported formats
    supported_extensions: List[str] = Field(
        default=['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'],
        description="Supported image extensions"
    )
    
    # Storage paths
    workspace_base: str = Field(default="workspace_X", description="Base workspace folder")
    image_store_folder: str = Field(default="PlanoraAgent/image_store", description="Image store subfolder")
    thumbnail_folder: str = Field(default="thumbnails", description="Thumbnail subfolder")
    
    # API settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_title: str = Field(default="Image Service API", description="API title")
    api_version: str = Field(default="1.0.0", description="API version")
    
    # Processing settings
    enable_thumbnails: bool = Field(default=True, description="Tạo thumbnails")
    enable_exif_extraction: bool = Field(default=True, description="Extract EXIF data")
    default_output_format: str = Field(default="webp", description="Default output format")
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    
    class Config:
        env_prefix = "IMAGE_SERVICE_"
        case_sensitive = False
    
    @property
    def pdf_max_image_size(self) -> Tuple[int, int]:
        """Compatibility với docpixie config"""
        return (self.max_width, self.max_height)
    
    def get_workspace_path(self, workspace: str = None) -> Path:
        """Lấy đường dẫn workspace"""
        if workspace:
            return Path(workspace)
        return Path(self.workspace_base)
    
    def get_image_store_path(self, workspace: str = None) -> Path:
        """Lấy đường dẫn image store"""
        workspace_path = self.get_workspace_path(workspace)
        return workspace_path / self.image_store_folder
    
    def get_thumbnail_path(self, workspace: str = None) -> Path:
        """Lấy đường dẫn thumbnail store"""
        image_store_path = self.get_image_store_path(workspace)
        return image_store_path / self.thumbnail_folder
    
    def ensure_directories(self, workspace: str = None):
        """Tạo các thư mục cần thiết"""
        image_store_path = self.get_image_store_path(workspace)
        thumbnail_path = self.get_thumbnail_path(workspace)
        
        image_store_path.mkdir(parents=True, exist_ok=True)
        thumbnail_path.mkdir(parents=True, exist_ok=True)
    
    def is_supported_format(self, file_path: str) -> bool:
        """Kiểm tra format có được hỗ trợ không"""
        return Path(file_path).suffix.lower() in self.supported_extensions


# Global config instance
config = ImageServiceConfig()


def get_config() -> ImageServiceConfig:
    """Get global config instance"""
    return config


def update_config(**kwargs) -> ImageServiceConfig:
    """Update config với new values"""
    global config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config