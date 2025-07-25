#!/usr/bin/env python3
"""
Main Image Processor for Crown Automotive
Processes PSD files and approved images into multiple production formats
"""

import os
import sys
import json
import yaml
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import shutil

import pyodbc
from PIL import Image, ImageOps, ImageChops, ImageFilter, ImageEnhance
from psd_tools import PSDImage
import warnings

# Import local utilities
sys.path.append('/scripts/utils')
from filemaker_conn import Filemaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/image_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", module="psd_tools.psd.tagged_blocks")

# Configuration
CONFIG_DIR = Path('/config')
ASSETS_DIR = Path('/assets')
INPUT_DIR = Path('/data/input')
PROCESSING_DIR = Path('/data/processing')
PRODUCTION_DIR = Path('/data/production')
METADATA_DIR = Path('/data/metadata')

SUPPORTED_IMAGE_EXTENSIONS = ['.psd', '.png', '.jpg', '.jpeg', '.tif', '.tiff']
EXIFTOOL_PATH = 'exiftool'
MIN_REQUIRED_SIZE = 2500


class ImageProcessor:
    def __init__(self):
        self.specs = self.load_output_specs()
        self.part_metadata = self.fetch_part_metadata()

        # Ensure directories exist
        for directory in [PROCESSING_DIR, PRODUCTION_DIR, METADATA_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    def load_output_specs(self) -> List[Dict[str, Any]]:
        """Load image output specifications from YAML"""
        try:
            spec_file = CONFIG_DIR / 'output_specs.yaml'
            with open(spec_file, 'r', encoding='utf-8') as f:
                specs = yaml.safe_load(f)
            logger.info(f"Loaded {len(specs)} output specifications")
            return specs
        except Exception as e:
            logger.error(f"Error loading output specifications: {e}")
            return []

    def fetch_part_metadata(self) -> Dict[str, Dict[str, str]]:
        """Fetch part metadata from FileMaker database"""
        try:
            with Filemaker() as fm:
                return fm.get_part_metadata_bulk()
        except Exception as e:
            logger.error(f"Error fetching part metadata: {e}")
            return {}

    # Image utility functions
    def load_psd_image(self, path: Path) -> Image.Image:
        """Load PSD file and convert to PIL Image"""
        try:
            psd = PSDImage.open(path)
            return psd.topil().convert("RGBA")
        except Exception as e:
            logger.error(f"Error loading PSD {path}: {e}")
            raise

    def trim_transparent(self, img: Image.Image) -> Image.Image:
        """Remove transparent borders from image"""
        try:
            bg = Image.new("RGBA", img.size, (255, 255, 255, 0))
            diff = ImageChops.difference(img, bg)
            bbox = diff.getbbox()
            return img.crop(bbox) if bbox else img
        except Exception as e:
            logger.error(f"Error trimming transparent areas: {e}")
            return img

    def resize_to_fit_inside(self, img: Image.Image, target_size: tuple, border: tuple) -> Image.Image:
        """Resize image to fit inside target dimensions with border"""
        usable_width = target_size[0] - (border[0] * 2)
        usable_height = target_size[1] - (border[1] * 2)
        return ImageOps.contain(img, (usable_width, usable_height))

    def apply_extent_centered(self, img: Image.Image, extent: tuple, background) -> Image.Image:
        """Center image within specified extent"""
        return ImageOps.pad(img, extent, method=Image.LANCZOS, color=background, centering=(0.5, 0.5))

    def overlay_brand_icon(self, base_img: Image.Image, icon_path: str, offset: tuple = (15, 15)) -> Image.Image:
        """Overlay brand icon on image"""
        try:
            icon_full_path = Path(icon_path) if Path(icon_path).is_absolute() else ASSETS_DIR / icon_path
            if not icon_full_path.exists():
                logger.warning(f"Brand icon not found: {icon_full_path}")
                return base_img

            icon = Image.open(icon_full_path).convert("RGBA")
            base = base_img.convert("RGBA")
            x = base.width - icon.width - offset[0]
            y = offset[1]
            base.alpha_composite(icon, dest=(x, y))
            return base
        except Exception as e:
            logger.error(f"Error overlaying brand icon: {e}")
            return base_img

    def apply_watermark(self, base_img: Image.Image, watermark_path: str) -> Image.Image:
        """Apply watermark to image"""
        try:
            watermark_full_path = Path(watermark_path) if Path(
                watermark_path).is_absolute() else ASSETS_DIR / watermark_path
            if not watermark_full_path.exists():
                logger.warning(f"Watermark not found: {watermark_full_path}")
                return base_img.convert("RGB")

            base = base_img.convert("RGBA")
            watermark = Image.open(watermark_full_path).convert("RGBA")

            # Scale watermark to 80% of the base image width, preserving aspect ratio
            max_w = int(base.width * 0.8)
            max_h = int(base.height * 0.8)

            wm_ratio = min(max_w / watermark.width, max_h / watermark.height)
            new_size = (int(watermark.width * wm_ratio), int(watermark.height * wm_ratio))

            watermark = watermark.resize(new_size, Image.LANCZOS)

            # Position at center
            x = (base.width - watermark.width) // 2
            y = (base.height - watermark.height) // 2

            base.alpha_composite(watermark, dest=(x, y))
            return base.convert("RGB")  # Flatten after composition

        except Exception as e:
            logger.error(f"Error applying watermark: {e}")
            return base_img.convert("RGB")

    def apply_metadata_exiftool(self, image_path: Path, meta: Dict[str, str], dpi: Optional[int] = None) -> None:
        """Apply metadata to image using exiftool"""
        try:
            cmd = [EXIFTOOL_PATH, "-overwrite_original", "-All="]

            if dpi:
                cmd += [
                    f"-XResolution={dpi}",
                    f"-YResolution={dpi}",
                    "-ResolutionUnit=inches"
                ]

            # Add metadata fields
            metadata_fields = [
                ("Author", "IPTC:By-line"),
                ("Credit", "IPTC:Credit"),
                ("Title", "IPTC:Caption-Abstract"),
                ("Title", "XMP:Description"),
                ("Description", "XMP:Description"),
                ("Keywords", "IPTC:Keywords"),
                ("Copyright", "EXIF:Copyright"),
                ("Copyright", "XMP:Rights")
            ]

            for meta_key, exif_field in metadata_fields:
                if meta.get(meta_key):
                    cmd.append(f'-{exif_field}={meta[meta_key]}')

            cmd.append(str(image_path))

            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

            if result.returncode != 0:
                logger.warning(f"exiftool warning for {image_path.name}: {result.stderr}")

        except Exception as e:
            logger.error(f"Error applying metadata to {image_path}: {e}")

    def process_variant(self, img: Image.Image, base_name: str, spec: Dict[str, Any], meta: Dict[str, str]) -> Optional[
        Path]:
        """Process a single image variant according to specification"""
        try:
            # Create output directory
            out_dir = PRODUCTION_DIR / spec["name"]
            out_dir.mkdir(parents=True, exist_ok=True)

            ext = spec["format"].lower()
            out_path = out_dir / f"{base_name}.{ext}"

            img_variant = img.copy()

            # Skip flattening + borders for transparent cropped images
            is_transparent = spec["name"] in ["original_300dpi_png", "original_300dpi_tiff"] or spec.get(
                "mode") == "RGBA"
            needs_border = not is_transparent or spec.get("border", [0, 0]) != [0, 0]

            # Handle image mode conversion
            if is_transparent and spec.get("background") is None:
                img_variant = img_variant.convert("RGBA")
            elif spec.get("background") and img_variant.mode == "RGBA":
                # Flatten RGBA to RGB using background
                bg_color = spec["background"]
                if bg_color == "white":
                    bg_color = (255, 255, 255)
                elif isinstance(bg_color, str):
                    # Handle hex colors or named colors
                    bg_color = (255, 255, 255)  # Default to white

                bg = Image.new("RGB", img_variant.size, bg_color)
                bg.paste(img_variant, mask=img_variant.split()[3] if img_variant.mode == "RGBA" else None)
                img_variant = bg
            else:
                img_variant = img_variant.convert(spec.get("mode", "RGB"))

            # Resize using resize_longest
            if spec.get("resize_longest") and needs_border:
                longest = spec["resize_longest"]
                border_x, border_y = spec.get("border", [0, 0])
                target_max = longest - max(border_x, border_y) * 2

                w, h = img_variant.size
                scale = target_max / max(w, h)
                new_size = (round(w * scale), round(h * scale))
                img_variant = img_variant.resize(new_size, Image.LANCZOS)

            # Resize using fixed size
            elif spec.get("resize"):
                img_variant = ImageOps.contain(img_variant, spec["resize"])

            # Add border if needed
            if spec.get("border") and needs_border and spec["border"] != [0, 0]:
                border_color = spec.get("background")
                if border_color == "white":
                    border_color = (255, 255, 255)
                elif border_color is None and spec.get("mode") == "RGBA":
                    border_color = (255, 255, 255, 0)
                else:
                    border_color = (255, 255, 255)

                img_variant = ImageOps.expand(img_variant, border=tuple(spec["border"]), fill=border_color)

            # Center the image in final extent if provided
            if spec.get("extent"):
                background_color = spec.get("background") or (255, 255, 255, 0) if spec.get("mode") == "RGBA" else (255,
                                                                                                                    255,
                                                                                                                    255)
                if background_color == "white":
                    background_color = (255, 255, 255)

                img_variant = self.apply_extent_centered(img_variant, spec["extent"], background_color)

            # Overlay brand icon if present
            if spec.get("brand_icon"):
                offset = tuple(spec.get("icon_offset", [15, 15]))
                img_variant = self.overlay_brand_icon(img_variant, spec["brand_icon"], offset)

            # Apply watermark if specified
            if spec.get("watermark"):
                img_variant = self.apply_watermark(img_variant, spec["watermark"])

            # Ensure correct mode for saving
            if img_variant.mode != "RGB" and spec["format"].upper() in ["JPEG", "TIFF"] and not is_transparent:
                img_variant = img_variant.convert("RGB")

            # Save parameters
            save_args = {"dpi": (spec["dpi"], spec["dpi"])}
            if spec["format"].upper() == "JPEG":
                save_args.update({"quality": 85, "optimize": True})
            elif spec["format"].upper() == "TIFF":
                save_args.update({"compression": "tiff_lzw"})

            # Save file
            img_variant.save(out_path, format=spec["format"], **save_args)

            # Apply metadata
            if meta:
                self.apply_metadata_exiftool(out_path, meta, spec.get("dpi"))

            logger.info(f"Created variant: {spec['name']}/{base_name}.{ext}")
            return out_path

        except Exception as e:
            logger.error(f"Error processing variant {spec['name']}: {e}")
            return None

    def get_part_metadata(self, filename: str) -> Dict[str, str]:
        """Extract part metadata based on filename"""
        base_name = Path(filename).stem.upper()
        cleaned_number = base_name.split("_")[0]

        meta = self.part_metadata.get(cleaned_number, {})

        # Set defaults
        meta.setdefault("Title", "Crown Automotive Sales Co., Inc.")
        meta.setdefault("Author", "Crown Automotive Sales Co., Inc.")
        meta.setdefault("Credit", "Crown Automotive Sales Co., Inc.")
        meta.setdefault("Copyright", "(c) Crown Automotive Sales Co., Inc.")

        return meta

    def process_single_file(self, file_path: Path, source_type: str = "auto") -> Dict[str, Any]:
        """Process a single image file through all variants"""
        try:
            logger.info(f"Processing file: {file_path.name}")

            start_time = datetime.now()
            base_name = file_path.stem.upper()

            # Load image
            if file_path.suffix.lower() == ".psd":
                img = self.load_psd_image(file_path)
                source_type = "psd"
            else:
                img = Image.open(file_path).convert("RGBA")
                if source_type == "auto":
                    source_type = "background_removed"

            # Trim transparent areas
            img = self.trim_transparent(img)

            # Check minimum size
            size_warning = None
            if max(img.width, img.height) < MIN_REQUIRED_SIZE:
                size_warning = f"Low resolution: {img.width}x{img.height} (minimum recommended: {MIN_REQUIRED_SIZE}px)"
                logger.warning(f"{base_name} - {size_warning}")

            # Get part metadata
            meta = self.get_part_metadata(file_path.name)

            # Process all variants
            successful_variants = []
            failed_variants = []

            for spec in self.specs:
                try:
                    result_path = self.process_variant(img, base_name, spec, meta)
                    if result_path:
                        successful_variants.append({
                            "name": spec["name"],
                            "path": str(result_path),
                            "format": spec["format"],
                            "dpi": spec["dpi"]
                        })
                    else:
                        failed_variants.append(spec["name"])
                except Exception as e:
                    logger.error(f"Failed to process variant {spec['name']}: {e}")
                    failed_variants.append(spec["name"])

            processing_time = (datetime.now() - start_time).total_seconds()

            # Save processing log
            log_data = {
                "file": str(file_path),
                "base_name": base_name,
                "source_type": source_type,
                "original_size": {"width": img.width, "height": img.height},
                "processing_time_seconds": processing_time,
                "successful_variants": len(successful_variants),
                "failed_variants": len(failed_variants),
                "size_warning": size_warning,
                "part_metadata": meta,
                "timestamp": datetime.now().isoformat(),
                "variants": successful_variants
            }

            log_file = METADATA_DIR / f"{base_name}_processing_log.json"
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)

            logger.info(
                f"Processing complete: {base_name} - {len(successful_variants)} variants created in {processing_time:.1f}s")

            return log_data

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise

    def process_batch(self, file_paths: List[Path]) -> List[Dict[str, Any]]:
        """Process multiple files"""
        results = []

        for file_path in file_paths:
            try:
                result = self.process_single_file(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                results.append({
                    "file": str(file_path),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

        return results


def main():
    """Main entry point for command line usage"""
    import argparse

    parser = argparse.ArgumentParser(description='Process images into multiple production formats')
    parser.add_argument('files', nargs='*', help='Image files to process')
    parser.add_argument('--source-type', choices=['psd', 'background_removed', 'auto'],
                        default='auto', help='Source file type')
    parser.add_argument('--single-file', help='Process a single file')

    args = parser.parse_args()

    processor = ImageProcessor()

    if args.single_file:
        file_path = Path(args.single_file)
        if file_path.exists():
            result = processor.process_single_file(file_path, args.source_type)
            print(json.dumps(result, indent=2))
        else:
            logger.error(f"File not found: {file_path}")
            sys.exit(1)

    elif args.files:
        file_paths = [Path(f) for f in args.files if Path(f).exists()]
        if not file_paths:
            logger.error("No valid files provided")
            sys.exit(1)

        results = processor.process_batch(file_paths)
        print(json.dumps(results, indent=2))

    else:
        # Process from stdin (JSON input from n8n)
        try:
            input_data = json.loads(sys.stdin.read())

            if 'file_path' in input_data:
                file_path = Path(input_data['file_path'])
                source_type = input_data.get('source_type', 'auto')
                result = processor.process_single_file(file_path, source_type)
                print(json.dumps(result, indent=2))

            elif 'files' in input_data:
                file_paths = [Path(f) for f in input_data['files']]
                results = processor.process_batch(file_paths)
                print(json.dumps(results, indent=2))

            else:
                logger.error("Invalid input data format")
                sys.exit(1)

        except json.JSONDecodeError:
            logger.error("Invalid JSON input")
            sys.exit(1)


if __name__ == "__main__":
    main()