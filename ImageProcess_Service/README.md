# Image Processing Service

Microservice Python để xử lý ảnh thành Document objects tương thích với Document Assembly microservice, dựa trên kiến trúc docpixie-main.

## Tính năng

- **REST API** với FastAPI cho xử lý ảnh qua HTTP
- **CLI interface** với Typer cho xử lý local
- **Xử lý ảnh** với PIL/Pillow: resize, optimize, thumbnail generation
- **Metadata extraction** từ EXIF và image properties
- **Output format** tương thích với Document Assembly
- **Async processing** với ThreadPoolExecutor
- **Error handling** và logging đầy đủ

## Yêu cầu

- Python 3.10+
- PIL/Pillow cho image processing
- FastAPI cho REST API
- Typer cho CLI interface

## Cài đặt

```bash
# Clone repository
git clone <repository-url>
cd imageProcess-main

# Install dependencies
pip install -r requirements.txt

# Hoặc install package
pip install -e .
```

## Sử dụng

### REST API

Khởi động server:

```bash
# Development server
python -m uvicorn image_service.api:app --reload --host 0.0.0.0 --port 8000

# Hoặc sử dụng script
python -m image_service.api
```

API endpoints:

- `POST /process_image/` - Xử lý ảnh upload
- `GET /health` - Health check
- `GET /formats` - Danh sách format hỗ trợ
- `GET /config` - Cấu hình service

Ví dụ sử dụng với curl:

```bash
# Process image
curl -X POST "http://localhost:8000/process_image/" \
  -F "file=@sample.jpg" \
  -F "workspace=./workspace_X" \
  -F "output_format=webp"

# Health check
curl http://localhost:8000/health
```

### CLI Interface

```bash
# Process image
python -m image_service process ./sample.jpg

# Với workspace custom
python -m image_service process ./sample.jpg --workspace ./workspace_X

# Với output format và file
python -m image_service process ./sample.jpg --format jpeg --output result.json

# Xem supported formats
python -m image_service formats

# Validate image
python -m image_service validate ./sample.jpg

# Xem config
python -m image_service config
```

## Cấu trúc thư mục

```
image_service/
├── __init__.py          # Package initialization
├── __main__.py          # Module entry point
├── api.py              # FastAPI REST API
├── cli.py              # Typer CLI interface
├── core.py             # Core image processing logic
├── models.py           # Pydantic models (Page, Document)
├── storage.py          # File storage management
├── metadata.py         # Metadata extraction
└── config.py           # Configuration management
```

## Cấu hình

Service sử dụng environment variables hoặc config file:

```python
# Environment variables
IMAGE_SERVICE_MAX_WIDTH=2048
IMAGE_SERVICE_MAX_HEIGHT=2048
IMAGE_SERVICE_QUALITY=85
IMAGE_SERVICE_WORKSPACE=/path/to/workspace
```

## Output Format

### Page Object

```json
{
  "page_number": 1,
  "text_content": null,
  "image_path": "workspace_X/PlanoraAgent/image_store/img_001.webp",
  "thumbnail_path": "workspace_X/PlanoraAgent/thumbnails/thumb_001.webp",
  "metadata": {
    "width": 1024,
    "height": 1448,
    "mode": "RGB",
    "format": "WEBP",
    "file_size": 234567,
    "has_transparency": false,
    "exif": {}
  }
}
```

### Document Object

```json
{
  "id": "doc_img_1234567890",
  "title": "sample.jpg",
  "file_path": "workspace_X/PlanoraAgent/image_store/img_001.webp",
  "num_pages": 1,
  "pages": [/* Page object */],
  "status": "completed",
  "metadata": {
    "original_file": "sample.jpg",
    "processor": "ImageProcessor",
    "created_at": "2025-01-09T12:00:00",
    "file_size": 234567,
    "image_format": "WEBP",
    "dimensions": "1024x1448"
  }
}
```

## Supported Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- BMP (.bmp)
- TIFF (.tiff)

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black image_service/
isort image_service/

# Lint
flake8 image_service/
```

## Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY image_service/ ./image_service/
COPY setup.py .

RUN pip install -e .

EXPOSE 8000
CMD ["uvicorn", "image_service.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Tích hợp với Document Assembly

Service này tạo ra Document objects tương thích với Document Assembly microservice:

1. **Page objects** chứa image_path và metadata
2. **Document objects** chứa danh sách pages
3. **Metadata format** chuẩn cho downstream processing
4. **File paths** tương đối với workspace

## Logging

Service sử dụng Python logging với các levels:

- `INFO`: Processing status, successful operations
- `WARNING`: Non-critical issues
- `ERROR`: Processing failures, exceptions
- `DEBUG`: Detailed processing information

## Error Handling

- **ImageProcessingError**: Lỗi xử lý ảnh cụ thể
- **HTTP 422**: Invalid input data
- **HTTP 413**: File quá lớn
- **HTTP 500**: Internal server errors

## Performance

- **Async processing** cho REST API
- **ThreadPoolExecutor** cho CPU-intensive tasks
- **Thumbnail generation** song song
- **Memory optimization** với PIL
- **Temporary file cleanup**

## License

MIT License - xem file LICENSE để biết thêm chi tiết.