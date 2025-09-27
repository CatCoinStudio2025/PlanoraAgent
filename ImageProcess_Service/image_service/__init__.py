"""
Image Service - Microservice xử lý ảnh đầu vào
Tạo Page object và Document object tương thích với Document Assembly
"""

__version__ = "1.0.0"
__author__ = "DocPixie Team"

from .models import Page, Document, ImageMetadata
from .core import ImageProcessor
from .api import app
from .cli import cli

__all__ = [
    "Page",
    "Document", 
    "ImageMetadata",
    "ImageProcessor",
    "app",
    "cli"
]