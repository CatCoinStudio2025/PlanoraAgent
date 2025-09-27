"""
Pydantic models cho Page và Document objects
Tương thích với Document Assembly microservice
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum
import uuid


class DocumentStatus(str, Enum):
    """Trạng thái xử lý document"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageMetadata(BaseModel):
    """Metadata của ảnh"""
    width: int = Field(..., description="Chiều rộng ảnh (pixels)")
    height: int = Field(..., description="Chiều cao ảnh (pixels)")
    mode: str = Field(..., description="Color mode (RGB, RGBA, L, etc.)")
    format: str = Field(..., description="Định dạng file (JPEG, PNG, WEBP, etc.)")
    file_size: int = Field(..., description="Kích thước file (bytes)")
    has_transparency: bool = Field(default=False, description="Có transparency không")
    exif: Optional[Dict[str, Any]] = Field(default=None, description="EXIF data nếu có")
    
    @validator('width', 'height', 'file_size')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('Giá trị phải lớn hơn 0')
        return v


class Page(BaseModel):
    """Page object - đại diện cho một trang document"""
    page_number: int = Field(..., description="Số thứ tự trang (bắt đầu từ 1)")
    text_content: Optional[str] = Field(default=None, description="Nội dung text (null cho ảnh)")
    image_path: str = Field(..., description="Đường dẫn tới file ảnh đã lưu")
    thumbnail_path: Optional[str] = Field(default=None, description="Đường dẫn thumbnail")
    metadata: ImageMetadata = Field(..., description="Metadata của ảnh")
    document_name: Optional[str] = Field(default=None, description="Tên document chứa page này")
    document_id: Optional[str] = Field(default=None, description="ID document chứa page này")
    
    @validator('page_number')
    def validate_page_number(cls, v):
        if v <= 0:
            raise ValueError('Page number phải lớn hơn 0')
        return v
    
    @validator('image_path')
    def validate_image_path(cls, v):
        if not v or not v.strip():
            raise ValueError('Image path không được rỗng')
        return v


class Document(BaseModel):
    """Document object - chứa một hoặc nhiều pages"""
    id: str = Field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:8]}", description="Document ID")
    title: str = Field(..., description="Tiêu đề document")
    file_path: str = Field(..., description="Đường dẫn file gốc")
    num_pages: int = Field(..., description="Số lượng pages")
    pages: List[Page] = Field(..., description="Danh sách pages")
    status: DocumentStatus = Field(default=DocumentStatus.PENDING, description="Trạng thái xử lý")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata của document")
    created_at: datetime = Field(default_factory=datetime.now, description="Thời gian tạo")
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title không được rỗng')
        return v
    
    @validator('num_pages')
    def validate_num_pages(cls, v):
        if v <= 0:
            raise ValueError('Số pages phải lớn hơn 0')
        return v
    
    @validator('pages')
    def validate_pages_count(cls, v, values):
        if 'num_pages' in values and len(v) != values['num_pages']:
            raise ValueError('Số lượng pages không khớp với num_pages')
        return v
    
    def get_page(self, page_number: int) -> Optional[Page]:
        """Lấy page theo số thứ tự"""
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None
    
    def update_page_references(self):
        """Cập nhật document_name và document_id cho tất cả pages"""
        for page in self.pages:
            page.document_name = self.title
            page.document_id = self.id


class ProcessImageRequest(BaseModel):
    """Request model cho API process_image"""
    workspace: Optional[str] = Field(default=None, description="Workspace path")
    max_width: Optional[int] = Field(default=None, description="Max width cho resize")
    max_height: Optional[int] = Field(default=None, description="Max height cho resize")
    output_format: str = Field(default="webp", description="Format output (jpeg, webp)")
    thumbnail_size: int = Field(default=200, description="Kích thước thumbnail")


class ProcessImageResponse(BaseModel):
    """Response model cho API process_image"""
    success: bool = Field(..., description="Thành công hay không")
    document: Optional[Document] = Field(default=None, description="Document object")
    error: Optional[str] = Field(default=None, description="Thông báo lỗi nếu có")
    processing_time: float = Field(default=0.0, description="Thời gian xử lý (seconds)")


class HealthResponse(BaseModel):
    """Response model cho health check"""
    status: str = Field(default="healthy", description="Trạng thái service")
    version: str = Field(default="1.0.0", description="Version")
    timestamp: datetime = Field(default_factory=datetime.now, description="Thời gian check")