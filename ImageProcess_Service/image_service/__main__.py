"""
Entry point for running image_service as a module
Usage: python -m image_service <command>
"""

from .cli import app

if __name__ == "__main__":
    app()