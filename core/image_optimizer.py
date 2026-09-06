import os
import io
import logging
from PIL import Image, ImageOps
from django.core.files.uploadedfile import UploadedFile, InMemoryUploadedFile

logger = logging.getLogger(__name__)


def compress_image(image_field, max_width=1200, quality=80):
    """
    Compresses and resizes an uploaded image before saving it to disk/cloud storage.
    - Preserves EXIF orientation (e.g., photos taken from mobile devices).
    - Proportionally resizes images exceeding max_width.
    - Preserves RGBA transparency for icons, badges, and transparent graphics.
    - Converts output to modern WebP format for optimal loading performance.
    - Only processes newly uploaded files (instances of UploadedFile).
    """
    if not image_field:
        return

    # Check whether image_field is an UploadedFile itself or a FieldFile wrapping an UploadedFile
    target_file = None
    if isinstance(image_field, UploadedFile):
        target_file = image_field
    elif hasattr(image_field, 'file') and isinstance(image_field.file, UploadedFile):
        target_file = image_field.file
    else:
        return

    try:
        # Open image via Pillow
        img = Image.open(target_file)

        # Transpose image according to EXIF orientation (handles no-EXIF natively)
        img = ImageOps.exif_transpose(img)

        # Proportional resize if width exceeds max_width
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Prepare memory buffer
        output = io.BytesIO()

        # Handle alpha channel / transparency conversion
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')

        # Convert filename extension to .webp
        original_name = os.path.basename(image_field.name)
        name_without_ext = os.path.splitext(original_name)[0]
        new_filename = f"{name_without_ext}.webp"

        # Save to memory buffer as WebP
        img.save(output, format='WEBP', quality=quality)
        output.seek(0)

        # Re-wrap in Django's InMemoryUploadedFile
        new_file = InMemoryUploadedFile(
            output,
            'ImageField',
            new_filename,
            'image/webp',
            output.getbuffer().nbytes,
            None
        )

        if hasattr(image_field, 'file'):
            image_field.file = new_file
            image_field.name = new_filename
        else:
            image_field.file = output
            image_field.name = new_filename
    except Exception:
        logger.exception("Failed to optimize uploaded image; preserving original file upload.")
