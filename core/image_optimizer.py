import os
import io
from PIL import Image, ImageOps
from django.core.files.uploadedfile import UploadedFile, InMemoryUploadedFile


def compress_image(image_field, max_width=1200, quality=80):
    """
    Compresses and resizes an uploaded image before saving it to disk/cloud storage.
    - Preserves EXIF orientation (e.g., photos from mobile devices).
    - Proportionally resizes images exceeding max_width.
    - Preserves RGBA transparency for icons and graphics.
    - Converts output to modern WebP format for optimal loading performance.
    - Only processes newly uploaded files (instances of UploadedFile).
    """
    if not image_field:
        return

    # Only compress if it is a new upload (not loaded from DB)
    if not hasattr(image_field, 'file') or not isinstance(image_field.file, UploadedFile):
        return

    try:
        # Open image via Pillow
        img = Image.open(image_field.file)

        # Transpose image according to EXIF orientation
        if hasattr(img, '_getexif') and img._getexif() is not None:
            img = ImageOps.exif_transpose(img)

        # Proportional resize if width exceeds max_width
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Prepare memory buffer
        output = io.BytesIO()

        # Handle alpha channel / transparency
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            save_mode = 'RGBA'
        else:
            save_mode = 'RGB'
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
        image_field.file = InMemoryUploadedFile(
            output,
            'ImageField',
            new_filename,
            'image/webp',
            output.getbuffer().nbytes,
            None
        )
        image_field.name = new_filename
    except Exception:
        # If image processing fails, preserve original upload gracefully
        pass
