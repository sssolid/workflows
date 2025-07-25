# ===== Fix imports in services/background_removal_service.py =====
import io
import time
from pathlib import Path
from typing import Optional
from PIL import Image
import numpy as np

from ..config.settings import settings
from ..models.file_models import ProcessedFile
from ..models.processing_models import BackgroundRemovalRequest, ProcessingResult, ProcessingModel
from ..utils.error_handling import handle_processing_errors, ProcessingError
from ..utils.filesystem_utils import ensure_directory

logger = logging.getLogger(__name__)


class BackgroundRemovalService:
    """
    Service for AI-powered background removal.

    This service handles:
    - Multiple model support (isnet, u2net, etc.)
    - Image preprocessing and postprocessing
    - Quality validation
    - Error handling and retries
    """

    def __init__(self):
        self.models_cache = {}
        self.output_dir = settings.processing.processing_dir / "bg_removed"
        ensure_directory(self.output_dir)

    def _get_model_session(self, model: ProcessingModel):
        """Get or create a model session."""
        if model not in self.models_cache:
            try:
                from rembg import new_session
                logger.info(f"Loading background removal model: {model}")
                self.models_cache[model] = new_session(model.value)
                logger.info(f"Successfully loaded model: {model}")
            except Exception as e:
                raise ProcessingError(f"Failed to load model {model}: {e}")

        return self.models_cache[model]

    @handle_processing_errors("background_removal")
    def remove_background(
            self,
            file_obj: ProcessedFile,
            request: BackgroundRemovalRequest
    ) -> ProcessingResult:
        """
        Remove background from an image file.

        Args:
            file_obj: File to process
            request: Processing request parameters

        Returns:
            Processing result
        """
        start_time = time.time()

        if not file_obj.current_location or not file_obj.current_location.exists():
            raise ProcessingError(f"Input file not found: {file_obj.current_location}")

        # Generate output path
        output_filename = f"{file_obj.metadata.stem}_bg_removed.png"
        output_path = self.output_dir / output_filename

        try:
            # Load and preprocess image
            with Image.open(file_obj.current_location) as img:
                if request.enhance_input:
                    img = self._enhance_image_for_processing(img)

                # Convert to bytes for rembg
                img_bytes = self._image_to_bytes(img)

            # Get model session
            session = self._get_model_session(request.model)

            # Remove background
            from rembg import remove
            output_bytes = remove(img_bytes, session=session)

            # Load result and post-process
            result_img = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

            if request.post_process:
                result_img = self._post_process_result(
                    result_img,
                    alpha_threshold=request.alpha_threshold
                )

            # Crop to content
            result_img = self._crop_to_content(result_img)

            # Save result
            result_img.save(output_path, "PNG")

            processing_time = time.time() - start_time

            # Calculate quality score
            quality_score = self._calculate_quality_score(result_img)

            return ProcessingResult(
                file_id=file_obj.metadata.file_id,
                processing_type="background_removal",
                success=True,
                output_path=output_path,
                processing_time_seconds=processing_time,
                model_used=request.model.value,
                quality_score=quality_score,
                metadata={
                    "original_size": {"width": img.width, "height": img.height},
                    "result_size": {"width": result_img.width, "height": result_img.height},
                    "enhance_input": request.enhance_input,
                    "post_process": request.post_process,
                    "alpha_threshold": request.alpha_threshold
                }
            )

        except Exception as e:
            processing_time = time.time() - start_time
            raise ProcessingError(f"Background removal failed: {e}")

    def _enhance_image_for_processing(self, img: Image.Image) -> Image.Image:
        """Enhance image for better background removal results."""
        from PIL import ImageEnhance, ImageFilter

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Slight contrast enhancement
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.1)

        # Slight sharpening
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))

        return img

    def _image_to_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL Image to bytes."""
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _post_process_result(
            self,
            result_img: Image.Image,
            alpha_threshold: int = 40
    ) -> Image.Image:
        """Post-process background removal result."""
        import cv2

        # Apply alpha threshold
        if alpha_threshold > 0:
            alpha = result_img.split()[-1]
            alpha = alpha.point(lambda p: 255 if p > alpha_threshold else 0)
            result_img.putalpha(alpha)

        # Apply morphological operations
        alpha_array = np.array(result_img.split()[-1])
        kernel = np.ones((3, 3), np.uint8)
        alpha_array = cv2.morphologyEx(alpha_array, cv2.MORPH_OPEN, kernel)
        alpha_array = cv2.morphologyEx(alpha_array, cv2.MORPH_CLOSE, kernel)

        alpha_img = Image.fromarray(alpha_array)
        result_img.putalpha(alpha_img)

        return result_img

    def _crop_to_content(self, img: Image.Image) -> Image.Image:
        """Crop image to content, removing transparent borders."""
        if img.mode == 'RGBA':
            alpha = img.split()[-1]
            bbox = alpha.getbbox()
            if bbox:
                return img.crop(bbox)

        return img

    def _calculate_quality_score(self, result_img: Image.Image) -> float:
        """Calculate a quality score for the background removal result."""
        alpha = result_img.split()[-1]
        alpha_array = np.array(alpha)

        # Calculate metrics
        total_pixels = alpha_array.size
        transparent_pixels = np.sum(alpha_array == 0)
        opaque_pixels = np.sum(alpha_array == 255)
        semi_transparent = total_pixels - transparent_pixels - opaque_pixels

        # Quality is based on clean separation (fewer semi-transparent pixels)
        clean_ratio = (transparent_pixels + opaque_pixels) / total_pixels
        quality_score = min(100, clean_ratio * 100)

        return round(quality_score, 2)