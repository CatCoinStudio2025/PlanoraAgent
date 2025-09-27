"""
Metadata extraction cho images
Extract thông tin từ ảnh: dimensions, format, EXIF, etc.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from PIL import Image
from PIL.ExifTags import TAGS
import os

from .models import ImageMetadata
from .config import ImageServiceConfig

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extract metadata từ images"""
    
    def __init__(self, config: ImageServiceConfig):
        self.config = config
    
    def extract_basic_metadata(self, image: Image.Image, file_path: str) -> Dict[str, Any]:
        """
        Extract basic metadata từ PIL Image
        
        Args:
            image: PIL Image object
            file_path: Path to original file
            
        Returns:
            Dict với basic metadata
        """
        try:
            # Basic image info
            width, height = image.size
            mode = image.mode
            format_name = image.format or "Unknown"
            
            # File size
            file_size = 0
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
            
            # Check transparency
            has_transparency = self._check_transparency(image)
            
            metadata = {
                "width": width,
                "height": height,
                "mode": mode,
                "format": format_name,
                "file_size": file_size,
                "has_transparency": has_transparency,
                "aspect_ratio": round(width / height, 3) if height > 0 else 0,
                "total_pixels": width * height
            }
            
            logger.debug(f"Extracted basic metadata: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract basic metadata: {e}")
            return {
                "width": 0,
                "height": 0,
                "mode": "Unknown",
                "format": "Unknown",
                "file_size": 0,
                "has_transparency": False
            }
    
    def extract_exif_data(self, image: Image.Image) -> Optional[Dict[str, Any]]:
        """
        Extract EXIF data từ image
        
        Args:
            image: PIL Image object
            
        Returns:
            Dict với EXIF data hoặc None
        """
        if not self.config.enable_exif_extraction:
            return None
        
        try:
            # Get EXIF data
            exif_dict = image.getexif()
            if not exif_dict:
                return None
            
            # Convert EXIF tags to readable names
            exif_data = {}
            for tag_id, value in exif_dict.items():
                tag_name = TAGS.get(tag_id, tag_id)
                
                # Convert bytes to string if needed
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8')
                    except UnicodeDecodeError:
                        value = str(value)
                
                # Skip very long values (binary data)
                if isinstance(value, str) and len(value) > 200:
                    continue
                
                exif_data[tag_name] = value
            
            # Extract useful EXIF fields
            useful_exif = {}
            useful_fields = [
                'Make', 'Model', 'DateTime', 'DateTimeOriginal',
                'ExifImageWidth', 'ExifImageHeight', 'Orientation',
                'XResolution', 'YResolution', 'ResolutionUnit',
                'Software', 'ColorSpace', 'WhiteBalance'
            ]
            
            for field in useful_fields:
                if field in exif_data:
                    useful_exif[field] = exif_data[field]
            
            logger.debug(f"Extracted EXIF data: {len(useful_exif)} fields")
            return useful_exif if useful_exif else None
            
        except Exception as e:
            logger.warning(f"Failed to extract EXIF data: {e}")
            return None
    
    def _check_transparency(self, image: Image.Image) -> bool:
        """Check if image has transparency"""
        try:
            # Check mode
            if image.mode in ('RGBA', 'LA'):
                return True
            
            # Check for transparency in palette mode
            if image.mode == 'P':
                transparency = image.info.get('transparency')
                return transparency is not None
            
            # Check for transparency info
            if 'transparency' in image.info:
                return True
            
            return False
            
        except Exception:
            return False
    
    def extract_color_info(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract color information từ image
        
        Args:
            image: PIL Image object
            
        Returns:
            Dict với color info
        """
        try:
            color_info = {
                "mode": image.mode,
                "bands": len(image.getbands()) if hasattr(image, 'getbands') else 0,
                "has_transparency": self._check_transparency(image)
            }
            
            # Get dominant colors (simplified)
            if image.mode in ('RGB', 'RGBA'):
                try:
                    # Convert to RGB and get colors
                    rgb_image = image.convert('RGB')
                    colors = rgb_image.getcolors(maxcolors=256*256*256)
                    if colors:
                        # Get most common color
                        most_common = max(colors, key=lambda x: x[0])
                        color_info["dominant_color"] = most_common[1]
                        color_info["color_count"] = len(colors)
                except Exception:
                    pass
            
            return color_info
            
        except Exception as e:
            logger.warning(f"Failed to extract color info: {e}")
            return {"mode": image.mode}
    
    def create_image_metadata(
        self, 
        image: Image.Image, 
        file_path: str,
        processed_size: Optional[Tuple[int, int]] = None
    ) -> ImageMetadata:
        """
        Tạo ImageMetadata object hoàn chỉnh
        
        Args:
            image: PIL Image object (original)
            file_path: Path to original file
            processed_size: Size after processing (if different)
            
        Returns:
            ImageMetadata object
        """
        try:
            # Extract basic metadata
            basic_meta = self.extract_basic_metadata(image, file_path)
            
            # Extract EXIF data
            exif_data = self.extract_exif_data(image)
            
            # Use processed size if provided
            if processed_size:
                width, height = processed_size
            else:
                width, height = basic_meta["width"], basic_meta["height"]
            
            # Create ImageMetadata object
            metadata = ImageMetadata(
                width=width,
                height=height,
                mode=basic_meta["mode"],
                format=basic_meta["format"],
                file_size=basic_meta["file_size"],
                has_transparency=basic_meta["has_transparency"],
                exif=exif_data
            )
            
            logger.info(f"Created ImageMetadata: {width}x{height}, {basic_meta['format']}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to create ImageMetadata: {e}")
            # Return minimal metadata
            return ImageMetadata(
                width=image.width if hasattr(image, 'width') else 0,
                height=image.height if hasattr(image, 'height') else 0,
                mode=image.mode if hasattr(image, 'mode') else "Unknown",
                format=image.format if hasattr(image, 'format') else "Unknown",
                file_size=0,
                has_transparency=False
            )
    
    def get_processing_recommendations(self, image: Image.Image) -> Dict[str, Any]:
        """
        Đưa ra recommendations cho image processing
        
        Args:
            image: PIL Image object
            
        Returns:
            Dict với recommendations
        """
        try:
            width, height = image.size
            recommendations = {
                "needs_resize": False,
                "needs_mode_conversion": False,
                "recommended_format": self.config.default_output_format,
                "estimated_output_size": 0
            }
            
            # Check if resize needed
            if width > self.config.max_width or height > self.config.max_height:
                recommendations["needs_resize"] = True
                ratio = min(self.config.max_width / width, self.config.max_height / height)
                recommendations["new_width"] = int(width * ratio)
                recommendations["new_height"] = int(height * ratio)
            
            # Check mode conversion
            if image.mode in ('RGBA', 'LA', 'P'):
                recommendations["needs_mode_conversion"] = True
                recommendations["target_mode"] = "RGB"
            
            # Recommend format based on content
            if self._check_transparency(image):
                recommendations["recommended_format"] = "webp"  # Better transparency support
            elif image.mode == 'L':
                recommendations["recommended_format"] = "jpeg"  # Good for grayscale
            
            return recommendations
            
        except Exception as e:
            logger.warning(f"Failed to get processing recommendations: {e}")
            return {"needs_resize": False, "needs_mode_conversion": False}