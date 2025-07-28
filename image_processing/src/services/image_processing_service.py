# ===== src/services/image_processing_service.py =====
import logging
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

from ..config.settings import settings
from ..models.file_models import ProcessedFile
from ..models.processing_models import FormatGenerationRequest, ProcessingResult
from ..models.metadata_models import ExifMetadata
from ..utils.error_handling import handle_processing_errors, ProcessingError
from ..utils.filesystem_utils import ensure_directory

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """
    Service for generating multiple image formats.

    Handles:
    - Multiple output format generation
    - Watermarking and branding
    - EXIF metadata application
    - Quality optimization
    """

    def __init__(self):
        self.output_specs = self._load_output_specs()
        self.production_dir = settings.processing.production_dir
        ensure_directory(self.production_dir)

    def _load_output_specs(self) -> List[Dict]:
        """Load output format specifications."""
        try:
            spec_file = Path("/config/output_specs.yaml")
            with open(spec_file, 'r') as f:
                specs = yaml.safe_load(f)
            logger.info(f"Loaded {len(specs)} output specifications")
            return specs
        except Exception as e:
            logger.error(f"Error loading output specifications: {e}")
            return []

    @handle_processing_errors("format_generation")
    def generate_formats(
            self,
            file_obj: ProcessedFile,
            request: FormatGenerationRequest,
            exif_metadata: Optional[ExifMetadata] = None
    ) -> ProcessingResult:
        """
        Generate multiple output formats for an image.

        Args:
            file_obj: File to process
            request: Format generation request
            exif_metadata: EXIF metadata to apply

        Returns:
            Processing result
        """
        start_time = time.time()

        if not file_obj.current_location or not file_obj.current_location.exists():
            raise ProcessingError(f"Input file not found: {file_obj.current_location}")

        try:
            # Load and prepare image
            with Image.open(file_obj.current_location) as img:
                img = img.convert("RGBA")
                img = self._trim_transparent(img)

            successful_formats = []
            failed_formats = []

            # Process each requested format
            for format_name in request.output_formats:
                spec = self._find_format_spec(format_name)
                if not spec:
                    failed_formats.append(format_name)
                    continue

                try:
                    output_path = self._process_format(
                        img,
                        file_obj.metadata.stem,
                        spec,
                        exif_metadata,
                        request.include_watermark,
                        request.include_brand_icon
                    )

                    if output_path:
                        successful_formats.append({
                            "format": format_name,
                            "path": str(output_path),
                            "spec": spec
                        })
                    else:
                        failed_formats.append(format_name)

                except Exception as e:
                    logger.error(f"Failed to process format {format_name}: {e}")
                    failed_formats.append(format_name)

            processing_time = time.time() - start_time

            return ProcessingResult(
                file_id=file_obj.metadata.file_id,
                processing_type="format_generation",
                success=len(failed_formats) == 0,
                processing_time_seconds=processing_time,
                metadata={
                    "successful_formats": len(successful_formats),
                    "failed_formats": len(failed_formats),
                    "formats": successful_formats,
                    "failures": failed_formats,
                    "include_watermark": request.include_watermark,
                    "include_brand_icon": request.include_brand_icon
                }
            )

        except Exception as e:
            processing_time = time.time() - start_time
            raise ProcessingError(f"Format generation failed: {e}")

    def _find_format_spec(self, format_name: str) -> Optional[Dict]:
        """Find format specification by name."""
        for spec in self.output_specs:
            if spec.get("name") == format_name:
                return spec
        return None

    def _trim_transparent(self, img: Image.Image) -> Image.Image:
        """Remove transparent borders from image."""
        if img.mode == "RGBA":
            alpha = img.split()[-1]
            bbox = alpha.getbbox()
            if bbox:
                return img.crop(bbox)
        return img

    def _process_format(
            self,
            img: Image.Image,
            base_name: str,
            spec: Dict,
            exif_metadata: Optional[ExifMetadata],
            include_watermark: bool,
            include_brand_icon: bool
    ) -> Optional[Path]:
        """Process a single format specification."""
        try:
            # Create output directory
            format_dir = self.production_dir / spec["name"]
            ensure_directory(format_dir)

            ext = spec["format"].lower()
            output_path = format_dir / f"{base_name}.{ext}"

            # Process image according to spec
            processed_img = self._apply_format_spec(img, spec)

            # Apply watermark if requested and spec allows
            if include_watermark and spec.get("watermark"):
                processed_img = self._apply_watermark(processed_img, spec["watermark"])

            # Apply brand icon if requested and spec allows
            if include_brand_icon and spec.get("brand_icon"):
                processed_img = self._apply_brand_icon(
                    processed_img,
                    spec["brand_icon"],
                    spec.get("icon_offset", [15, 15])
                )

            # Save image
            save_kwargs = {"dpi": (spec["dpi"], spec["dpi"])}

            if spec["format"].upper() == "JPEG":
                save_kwargs.update({"quality": 85, "optimize": True})
                if processed_img.mode != "RGB":
                    processed_img = processed_img.convert("RGB")
            elif spec["format"].upper() == "TIFF":
                save_kwargs.update({"compression": "tiff_lzw"})

            processed_img.save(output_path, format=spec["format"], **save_kwargs)

            # Apply EXIF metadata if provided
            if exif_metadata:
                self._apply_exif_metadata(output_path, exif_metadata, spec.get("dpi"))

            logger.debug(f"Created format: {spec['name']}/{base_name}.{ext}")
            return output_path

        except Exception as e:
            logger.error(f"Error processing format {spec['name']}: {e}")
            return None

    def _apply_format_spec(self, img: Image.Image, spec: Dict) -> Image.Image:
        """Apply format specification transformations."""
        result_img = img.copy()

        # Handle resize operations
        if spec.get("resize_longest"):
            result_img = self._resize_longest(result_img, spec["resize_longest"])
        elif spec.get("resize"):
            result_img = ImageOps.contain(result_img, spec["resize"])

        # Apply background if specified
        if spec.get("background") and result_img.mode == "RGBA":
            bg_color = self._parse_background_color(spec["background"])
            background = Image.new("RGB", result_img.size, bg_color)
            background.paste(result_img, mask=result_img.split()[3])
            result_img = background

        # Apply extent (centering)
        if spec.get("extent"):
            bg_color = self._parse_background_color(spec.get("background", "white"))
            result_img = ImageOps.pad(result_img, spec["extent"], color=bg_color, centering=(0.5, 0.5))

        # Apply border
        if spec.get("border") and spec["border"] != [0, 0]:
            border_color = self._parse_background_color(spec.get("background", "white"))
            result_img = ImageOps.expand(result_img, border=tuple(spec["border"]), fill=border_color)

        return result_img

    def _resize_longest(self, img: Image.Image, target_size: int) -> Image.Image:
        """Resize image maintaining aspect ratio to fit longest side."""
        w, h = img.size
        scale = target_size / max(w, h)
        new_size = (int(w * scale), int(h * scale))
        return img.resize(new_size, Image.LANCZOS)

    def _parse_background_color(self, color_spec):
        """Parse background color specification."""
        if color_spec == "white":
            return (255, 255, 255)
        elif color_spec == "black":
            return (0, 0, 0)
        elif isinstance(color_spec, (list, tuple)) and len(color_spec) >= 3:
            return tuple(color_spec[:3])
        else:
            return (255, 255, 255)  # Default to white

    def _apply_watermark(self, img: Image.Image, watermark_path: str) -> Image.Image:
        """Apply watermark to image."""
        try:
            watermark_file = Path("/assets") / watermark_path.lstrip("/")
            if not watermark_file.exists():
                logger.warning(f"Watermark not found: {watermark_file}")
                return img.convert("RGB")

            base = img.convert("RGBA")
            watermark = Image.open(watermark_file).convert("RGBA")

            # Scale watermark to 80% of base width
            max_w = int(base.width * 0.8)
            max_h = int(base.height * 0.8)

            wm_ratio = min(max_w / watermark.width, max_h / watermark.height)
            new_size = (int(watermark.width * wm_ratio), int(watermark.height * wm_ratio))
            watermark = watermark.resize(new_size, Image.LANCZOS)

            # Center watermark
            x = (base.width - watermark.width) // 2
            y = (base.height - watermark.height) // 2

            base.alpha_composite(watermark, dest=(x, y))
            return base.convert("RGB")

        except Exception as e:
            logger.error(f"Error applying watermark: {e}")
            return img.convert("RGB")

    def _apply_brand_icon(self, img: Image.Image, icon_path: str, offset: List[int]) -> Image.Image:
        """Apply brand icon to image."""
        try:
            icon_file = Path("/assets") / icon_path.lstrip("/")
            if not icon_file.exists():
                logger.warning(f"Brand icon not found: {icon_file}")
                return img

            icon = Image.open(icon_file).convert("RGBA")
            base = img.convert("RGBA")

            # Position icon
            x = base.width - icon.width - offset[0]
            y = offset[1]

            base.alpha_composite(icon, dest=(x, y))
            return base

        except Exception as e:
            logger.error(f"Error applying brand icon: {e}")
            return img

    def _apply_exif_metadata(self, image_path: Path, metadata: ExifMetadata, dpi: Optional[int]) -> None:
        """Apply EXIF metadata using exiftool."""
        try:
            import subprocess

            cmd = ["exiftool", "-overwrite_original", "-All="]

            if dpi:
                cmd.extend([
                    f"-XResolution={dpi}",
                    f"-YResolution={dpi}",
                    "-ResolutionUnit=inches"
                ])

            # Add metadata fields
            if metadata.title:
                cmd.extend([f"-IPTC:Caption-Abstract={metadata.title}", f"-XMP:Description={metadata.title}"])
            if metadata.description:
                cmd.append(f"-XMP:Description={metadata.description}")
            if metadata.keywords:
                cmd.append(f"-IPTC:Keywords={metadata.keywords}")
            if metadata.author:
                cmd.append(f"-IPTC:By-line={metadata.author}")
            if metadata.copyright:
                cmd.extend([f"-EXIF:Copyright={metadata.copyright}", f"-XMP:Rights={metadata.copyright}"])

            cmd.append(str(image_path))

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"exiftool warning for {image_path.name}: {result.stderr}")

        except Exception as e:
            logger.error(f"Error applying EXIF metadata to {image_path}: {e}")