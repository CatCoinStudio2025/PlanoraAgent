"""
CLI interface for image processing service using Typer
Usage: python -m image_service process <image_path> --workspace <workspace>
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from .core import ImageProcessor, ImageProcessingError
from .config import get_config

# Initialize CLI app
app = typer.Typer(
    name="image_service",
    help="Image Processing Service CLI - Xử lý ảnh thành Document objects",
    add_completion=False
)

# Initialize console for rich output
console = Console()

# Setup logging for CLI
logging.basicConfig(
    level=logging.WARNING,  # Less verbose for CLI
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Setup logging level based on verbose flag"""
    if verbose:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger('image_service').setLevel(logging.INFO)


@app.command()
def process(
    image_path: str = typer.Argument(..., help="Path to image file to process"),
    workspace: Optional[str] = typer.Option(
        None, 
        "--workspace", "-w", 
        help="Workspace directory path"
    ),
    output_format: str = typer.Option(
        "webp", 
        "--format", "-f", 
        help="Output format (webp, jpeg)"
    ),
    document_id: Optional[str] = typer.Option(
        None,
        "--id",
        help="Custom document ID"
    ),
    output_file: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="Save JSON output to file"
    ),
    pretty: bool = typer.Option(
        True,
        "--pretty/--no-pretty",
        help="Pretty print JSON output"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose logging"
    )
):
    """
    Process an image file and output Document JSON
    
    Examples:
        image_service process ./sample.jpg
        image_service process ./sample.jpg --workspace ./workspace_X
        image_service process ./sample.jpg --format jpeg --output result.json
    """
    setup_logging(verbose)
    
    try:
        # Validate input file
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            rprint(f"[red]Error: File not found: {image_path}[/red]")
            raise typer.Exit(1)
        
        # Validate output format
        if output_format not in ["webp", "jpeg"]:
            rprint(f"[red]Error: Invalid format '{output_format}'. Supported: webp, jpeg[/red]")
            raise typer.Exit(1)
        
        # Initialize processor
        config = get_config()
        processor = ImageProcessor(config)
        
        # Show processing info
        rprint(f"[blue]Processing image:[/blue] {image_path}")
        if workspace:
            rprint(f"[blue]Workspace:[/blue] {workspace}")
        rprint(f"[blue]Output format:[/blue] {output_format}")
        
        # Process with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Processing image...", total=None)
            
            start_time = time.time()
            document = processor.process_sync(
                file_path=str(image_path_obj.absolute()),
                workspace=workspace,
                output_format=output_format,
                document_id=document_id
            )
            processing_time = time.time() - start_time
            
            progress.update(task, description="Processing complete!")
        
        # Show results summary
        rprint(f"[green]✓ Processing completed in {processing_time:.2f}s[/green]")
        
        # Create results table
        table = Table(title="Processing Results")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Document ID", document.id)
        table.add_row("Title", document.title)
        table.add_row("Pages", str(document.num_pages))
        table.add_row("Status", document.status.value)
        table.add_row("Output Path", document.file_path)
        
        if document.pages:
            page = document.pages[0]
            table.add_row("Image Size", f"{page.metadata.width}x{page.metadata.height}")
            table.add_row("Format", page.metadata.format)
            table.add_row("File Size", f"{page.metadata.file_size:,} bytes")
            if page.thumbnail_path:
                table.add_row("Thumbnail", page.thumbnail_path)
        
        console.print(table)
        
        # Output JSON
        json_output = document.model_dump(exclude_none=True)
        
        if output_file:
            # Save to file
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=2 if pretty else None, ensure_ascii=False)
            rprint(f"[green]✓ JSON saved to: {output_path}[/green]")
        else:
            # Print to console
            rprint("\n[yellow]Document JSON:[/yellow]")
            if pretty:
                rprint(json.dumps(json_output, indent=2, ensure_ascii=False))
            else:
                rprint(json.dumps(json_output, ensure_ascii=False))
        
    except ImageProcessingError as e:
        rprint(f"[red]Processing Error: {e}[/red]")
        if verbose and e.file_path:
            rprint(f"[red]File: {e.file_path}[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        rprint("\n[yellow]Processing cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Unexpected error: {e}[/red]")
        if verbose:
            import traceback
            rprint(f"[red]{traceback.format_exc()}[/red]")
        raise typer.Exit(1)


@app.command()
def formats():
    """Show supported image formats"""
    try:
        config = get_config()
        processor = ImageProcessor(config)
        supported = processor.get_supported_formats()
        
        table = Table(title="Supported Image Formats")
        table.add_column("Extension", style="cyan")
        table.add_column("Description", style="white")
        
        format_descriptions = {
            ".jpg": "JPEG - Joint Photographic Experts Group",
            ".jpeg": "JPEG - Joint Photographic Experts Group", 
            ".png": "PNG - Portable Network Graphics",
            ".webp": "WebP - Google's image format",
            ".bmp": "BMP - Bitmap image file",
            ".tiff": "TIFF - Tagged Image File Format"
        }
        
        for ext in supported:
            desc = format_descriptions.get(ext, "Supported image format")
            table.add_row(ext, desc)
        
        console.print(table)
        
        # Show additional info
        rprint(f"\n[blue]Max file size:[/blue] {config.max_file_size:,} bytes")
        rprint(f"[blue]Max image dimensions:[/blue] {config.pdf_max_image_size[0]}x{config.pdf_max_image_size[1]}")
        rprint(f"[blue]Default output format:[/blue] {config.default_output_format}")
        
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config():
    """Show current service configuration"""
    try:
        config = get_config()
        
        table = Table(title="Service Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Max Image Size", f"{config.pdf_max_image_size[0]}x{config.pdf_max_image_size[1]}")
        table.add_row("Thumbnail Size", f"{config.thumbnail_size[0]}x{config.thumbnail_size[1]}")
        table.add_row("Image Quality", str(config.image_quality))
        table.add_row("Default Format", config.default_output_format)
        table.add_row("Enable Thumbnails", str(config.enable_thumbnails))
        table.add_row("Max File Size", f"{config.max_file_size:,} bytes")
        
        # Paths
        table.add_row("Default Workspace", config.default_workspace)
        table.add_row("Image Store", config.image_store_name)
        table.add_row("Thumbnails", config.thumbnails_name)
        
        console.print(table)
        
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    image_path: str = typer.Argument(..., help="Path to image file to validate"),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed validation info"
    )
):
    """Validate an image file without processing"""
    setup_logging(verbose)
    
    try:
        config = get_config()
        processor = ImageProcessor(config)
        
        rprint(f"[blue]Validating:[/blue] {image_path}")
        
        # Validate file
        processor.validate_file(image_path)
        
        # Load and show basic info
        image = processor.load_image(image_path)
        file_size = Path(image_path).stat().st_size
        
        table = Table(title="Image Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("File Path", image_path)
        table.add_row("File Size", f"{file_size:,} bytes")
        table.add_row("Dimensions", f"{image.width}x{image.height}")
        table.add_row("Mode", image.mode)
        table.add_row("Format", image.format or "Unknown")
        
        # Check if resize needed
        max_w, max_h = config.pdf_max_image_size
        needs_resize = image.width > max_w or image.height > max_h
        table.add_row("Needs Resize", "Yes" if needs_resize else "No")
        
        if needs_resize:
            ratio = min(max_w / image.width, max_h / image.height)
            new_w, new_h = int(image.width * ratio), int(image.height * ratio)
            table.add_row("New Size", f"{new_w}x{new_h}")
        
        console.print(table)
        rprint("[green]✓ Image is valid and can be processed[/green]")
        
    except ImageProcessingError as e:
        rprint(f"[red]Validation Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
        if verbose:
            import traceback
            rprint(f"[red]{traceback.format_exc()}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information"""
    rprint("[blue]Image Processing Service CLI[/blue]")
    rprint("Version: 1.0.0")
    rprint("Python backend microservice for image processing")


if __name__ == "__main__":
    app()