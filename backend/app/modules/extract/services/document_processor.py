"""
Document processing service.

Handles file validation, PDF conversion, and image encoding
for vision model input.
"""

import asyncio
import base64
import io
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List

from fastapi import UploadFile
from pdf2image import convert_from_bytes
from PIL import Image

from ..exceptions import FileTooLargeError, InvalidFileError

logger = logging.getLogger(__name__)

# Thread pool executor for CPU-intensive operations
_executor = ThreadPoolExecutor(max_workers=4)


class DocumentProcessor:
    """
    Processes uploaded documents for Extract.

    Responsibilities:
    - Validate file type and size
    - Convert PDFs to images
    - Resize images for optimal model input
    - Encode images as base64
    """

    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "application/pdf",
    }
    MAX_PDF_PAGES = 20  # Limit pages to prevent memory exhaustion

    async def process_file(
        self,
        file: UploadFile,
        max_size_mb: int = 10,
        max_dimension: int = 1024,
    ) -> List[str]:
        """
        Process uploaded file into base64-encoded images.

        Args:
            file: Uploaded file
            max_size_mb: Maximum file size in MB
            max_dimension: Maximum image dimension (width or height)

        Returns:
            List of base64-encoded PNG images

        Raises:
            InvalidFileError: If file type not allowed
            FileTooLargeError: If file exceeds size limit
        """
        # Validate file
        self._validate_file(file, max_size_mb)

        # Read content
        content = await file.read()
        await file.seek(0)

        logger.debug(
            "Processing file: %s (%d bytes, type: %s)",
            file.filename,
            len(content),
            file.content_type,
        )

        # Convert to images based on type
        # Check file extension instead of content_type (which may be None)
        filename = file.filename or ""
        ext = Path(filename).suffix.lower()

        # Run CPU-intensive operations in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()

        if ext == ".pdf" or file.content_type == "application/pdf":
            images = await loop.run_in_executor(
                _executor, self._convert_pdf_to_images, content
            )
            logger.debug("Converted PDF to %d images", len(images))
        else:
            images = await loop.run_in_executor(
                _executor, lambda: [Image.open(io.BytesIO(content))]
            )

        # Process images in executor (resize and encode)
        encoded_images = await loop.run_in_executor(
            _executor, self._process_images_sync, images, max_dimension
        )

        return encoded_images

    def _process_images_sync(
        self, images: List[Image.Image], max_dimension: int
    ) -> List[str]:
        """Synchronous image processing for executor."""
        encoded_images = []
        for i, img in enumerate(images):
            resized = self._resize_image(img, max_dimension)
            encoded = self._encode_image(resized)
            encoded_images.append(encoded)
            logger.debug(
                "Image %d: %dx%d -> %dx%d, encoded size: %d chars",
                i + 1,
                img.size[0],
                img.size[1],
                resized.size[0],
                resized.size[1],
                len(encoded),
            )
        return encoded_images

    def _validate_file(self, file: UploadFile, max_size_mb: int):
        """Validate file extension, MIME type, and size."""
        filename = file.filename or ""

        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise InvalidFileError(
                f"File type '{ext}' not allowed. "
                f"Allowed types: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )

        # Check MIME type (with fallback to extension if content_type is None)
        content_type = file.content_type

        # If content_type is None, infer from file extension
        if content_type is None:
            mime_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".pdf": "application/pdf",
            }
            content_type = mime_type_map.get(ext)
            logger.info(
                f"Content-Type was None, inferred {content_type} from extension {ext}"
            )

        if content_type not in self.ALLOWED_MIME_TYPES:
            raise InvalidFileError(f"MIME type '{content_type}' not allowed")

        # Check size
        file.file.seek(0, 2)
        size_bytes = file.file.tell()
        file.file.seek(0)

        size_mb = size_bytes / (1024 * 1024)
        if size_mb > max_size_mb:
            raise FileTooLargeError(
                f"File size {size_mb:.1f}MB exceeds limit of {max_size_mb}MB"
            )

    def _convert_pdf_to_images(
        self,
        pdf_bytes: bytes,
        dpi: int = 200,
    ) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images.

        Args:
            pdf_bytes: PDF file content
            dpi: Resolution for conversion (200 DPI is good for text)

        Returns:
            List of PIL Images, one per page (limited to MAX_PDF_PAGES)
        """
        try:
            # Limit pages to prevent memory exhaustion
            images = convert_from_bytes(
                pdf_bytes, dpi=dpi, first_page=1, last_page=self.MAX_PDF_PAGES
            )
            if len(images) == self.MAX_PDF_PAGES:
                logger.warning(
                    "PDF truncated to %d pages to prevent memory exhaustion",
                    self.MAX_PDF_PAGES,
                )
            return images
        except Exception as e:
            logger.error("PDF conversion failed: %s", e)
            raise InvalidFileError(f"Failed to process PDF: {e}") from e

    def _resize_image(
        self,
        image: Image.Image,
        max_dimension: int,
    ) -> Image.Image:
        """
        Resize image maintaining aspect ratio.

        Args:
            image: Source image
            max_dimension: Maximum width or height

        Returns:
            Resized image (or original if already smaller)
        """
        if max(image.size) <= max_dimension:
            return image

        # Calculate new size maintaining aspect ratio
        ratio = max_dimension / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)

        return image.resize(new_size, Image.Resampling.LANCZOS)

    def _encode_image(self, image: Image.Image) -> str:
        """
        Encode image as base64 PNG.

        Converts to RGB if needed (for RGBA/P mode images).
        """
        # Convert to RGB if necessary
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Encode as PNG
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)

        return base64.b64encode(buffer.getvalue()).decode("utf-8")
