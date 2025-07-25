#!/usr/bin/env python3
"""
Background Removal Script for Crown Automotive Image Processing
Uses rembg with optimized settings for automotive parts
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import shutil

import numpy as np
import cv2
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
from io import BytesIO
from rembg import remove, new_session
import structlog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/background_removal.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
INPUT_DIR = Path('/data/input')
PROCESSING_DIR = Path('/data/processing')
MODELS_DIR = Path('/config/models')


class BackgroundRemover:
    def __init__(self):
        # Ensure directories exist
        for directory in [PROCESSING_DIR / 'originals', PROCESSING_DIR / 'bg_removed', MODELS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

        # Initialize model session
        self.session = None
        self.model_name = "isnet-general-use"  # Best for automotive parts
        self._init_model()

    def _init_model(self):
        """Initialize the background removal model"""
        try:
            logger.info(f"Initializing background removal model: {self.model_name}")
            self.session = new_session(model_name=self.model_name)
            logger.info("Background removal model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            raise

    def enhance_image_for_processing(self, img: Image.Image,
                                     contrast_factor: float = 1.2,
                                     brightness_factor: float = 1.0,
                                     apply_sharpening: bool = True) -> bytes:
        """
        Enhance image before background removal for better results
        """
        try:
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Apply contrast enhancement
            if contrast_factor != 1.0:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(contrast_factor)

            # Apply brightness adjustment
            if brightness_factor != 1.0:
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(brightness_factor)

            # Apply unsharp mask for better edge detection
            if apply_sharpening:
                img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

            # Convert to bytes for rembg processing
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        except Exception as e:
            logger.error(f"Error enhancing image: {e}")
            # Fallback: return original image as bytes
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    def post_process_result(self, result_img: Image.Image,
                            alpha_threshold: int = 40,
                            apply_morphological: bool = True,
                            edge_feathering: int = 1) -> Image.Image:
        """
        Post-process the background removal result for cleaner edges
        """
        try:
            # Ensure we have an RGBA image
            if result_img.mode != 'RGBA':
                result_img = result_img.convert('RGBA')

            # Apply alpha threshold to clean up semi-transparent pixels
            if alpha_threshold > 0:
                alpha = result_img.split()[-1]
                alpha = alpha.point(lambda p: 255 if p > alpha_threshold else 0)
                result_img.putalpha(alpha)

            # Apply morphological operations to clean up the mask
            if apply_morphological:
                # Extract alpha channel as numpy array
                alpha_array = np.array(result_img.split()[-1])

                # Apply opening operation to remove small noise
                kernel = np.ones((3, 3), np.uint8)
                alpha_array = cv2.morphologyEx(alpha_array, cv2.MORPH_OPEN, kernel)

                # Apply closing operation to fill small holes
                alpha_array = cv2.morphologyEx(alpha_array, cv2.MORPH_CLOSE, kernel)

                # Convert back to PIL and apply to image
                alpha_img = Image.fromarray(alpha_array)
                result_img.putalpha(alpha_img)

            # Apply edge feathering for smoother edges
            if edge_feathering > 0:
                alpha = result_img.split()[-1]
                alpha = alpha.filter(ImageFilter.GaussianBlur(radius=edge_feathering))
                result_img.putalpha(alpha)

            return result_img

        except Exception as e:
            logger.error(f"Error post-processing result: {e}")
            return result_img

    def remove_background(self, input_path: Path,
                          output_path: Optional[Path] = None,
                          enhance_input: bool = True,
                          post_process: bool = True) -> Dict[str, Any]:
        """
        Remove background from a single image
        """
        try:
            start_time = datetime.now()

            # FIXED: Always save to processing directory, NOT back to input
            if output_path is None:
                bg_removed_dir = Path('/data/processing/bg_removed')
                bg_removed_dir.mkdir(parents=True, exist_ok=True)
                output_path = bg_removed_dir / f"{input_path.stem}_bg_removed.png"

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Processing background removal: {input_path.name}")
            logger.info(f"Input: {input_path}")
            logger.info(f"Output: {output_path}")

            # Load and prepare image
            original_img = Image.open(input_path)
            original_size = original_img.size

            # Copy original to processing directory for reference
            originals_dir = Path('/data/processing/originals')
            originals_dir.mkdir(parents=True, exist_ok=True)
            original_copy_path = originals_dir / input_path.name
            shutil.copy2(input_path, original_copy_path)

            # Enhance image for better background removal
            if enhance_input:
                input_bytes = self.enhance_image_for_processing(original_img)
            else:
                buf = BytesIO()
                original_img.save(buf, format="PNG")
                input_bytes = buf.getvalue()

            # Remove background using rembg
            logger.debug("Running background removal model...")
            output_bytes = remove(input_bytes, session=self.session)
            result_img = Image.open(BytesIO(output_bytes)).convert("RGBA")

            # Post-process for cleaner results
            if post_process:
                result_img = self.post_process_result(result_img)

            # Crop to content (remove excess transparent space)
            bbox = result_img.split()[-1].getbbox()
            if bbox:
                result_img = result_img.crop(bbox)
            else:
                logger.warning(f"No foreground object detected in {input_path.name}")

            # Save result
            result_img.save(output_path, "PNG")

            processing_time = (datetime.now() - start_time).total_seconds()

            # Generate processing report
            result_data = {
                "input_file": str(input_path),
                "output_file": str(output_path),
                "original_copy": str(original_copy_path),
                "original_size": {"width": original_size[0], "height": original_size[1]},
                "result_size": {"width": result_img.width, "height": result_img.height},
                "processing_time_seconds": processing_time,
                "model_used": self.model_name,
                "enhancement_applied": enhance_input,
                "post_processing_applied": post_process,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }

            # Save processing metadata
            metadata_dir = Path('/data/metadata')
            metadata_dir.mkdir(parents=True, exist_ok=True)
            metadata_file = metadata_dir / f"{input_path.stem}_bg_removal_log.json"

            with open(metadata_file, 'w') as f:
                json.dump(result_data, f, indent=2)

            logger.info(
                f"Background removal complete: {input_path.name} -> {output_path.name} ({processing_time:.1f}s)")

            return result_data

        except Exception as e:
            error_msg = f"Error removing background from {input_path}: {e}"
            logger.error(error_msg)

            return {
                "input_file": str(input_path),
                "error": str(e),
                "status": "failed",
                "timestamp": datetime.now().isoformat()
            }

    def process_batch(self, input_files: list) -> list:
        """Process multiple files for background removal"""
        results = []

        for input_file in input_files:
            input_path = Path(input_file)
            if not input_path.exists():
                logger.error(f"File not found: {input_path}")
                continue

            try:
                result = self.remove_background(input_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process {input_path}: {e}")
                results.append({
                    "input_file": str(input_path),
                    "error": str(e),
                    "status": "failed",
                    "timestamp": datetime.now().isoformat()
                })

        return results

    def retry_with_different_settings(self, input_path: Path) -> Dict[str, Any]:
        """Retry background removal with different settings if first attempt failed"""
        try:
            logger.info(f"Retrying background removal with alternative settings: {input_path.name}")

            # Try with less aggressive post-processing
            result = self.remove_background(
                input_path,
                enhance_input=True,
                post_process=False  # Skip post-processing for difficult images
            )

            if result.get("status") == "success":
                # If still successful, try with different enhancement
                alt_result = self.remove_background(
                    input_path,
                    enhance_input=False,  # Skip enhancement
                    post_process=True
                )

                # Compare results and return the better one (could be based on size, etc.)
                return alt_result if alt_result.get("status") == "success" else result

            return result

        except Exception as e:
            logger.error(f"Retry failed for {input_path}: {e}")
            return {
                "input_file": str(input_path),
                "error": f"Retry failed: {e}",
                "status": "failed",
                "timestamp": datetime.now().isoformat()
            }


def main():
    """Main entry point for command line usage"""
    import argparse

    parser = argparse.ArgumentParser(description='Remove backgrounds from images')
    parser.add_argument('files', nargs='*', help='Image files to process')
    parser.add_argument('--single-file', help='Process a single file')
    parser.add_argument('--output-dir', help='Output directory for processed images')
    parser.add_argument('--no-enhance', action='store_true', help='Skip input enhancement')
    parser.add_argument('--no-post-process', action='store_true', help='Skip post-processing')
    parser.add_argument('--retry', action='store_true', help='Retry with different settings')

    args = parser.parse_args()

    remover = BackgroundRemover()

    if args.single_file:
        input_path = Path(args.single_file)
        if not input_path.exists():
            logger.error(f"File not found: {input_path}")
            sys.exit(1)

        if args.retry:
            result = remover.retry_with_different_settings(input_path)
        else:
            result = remover.remove_background(
                input_path,
                enhance_input=not args.no_enhance,
                post_process=not args.no_post_process
            )

        print(json.dumps(result, indent=2))

    elif args.files:
        results = remover.process_batch(args.files)
        print(json.dumps(results, indent=2))

    else:
        # Process from stdin (JSON input from n8n)
        try:
            input_data = json.loads(sys.stdin.read())

            if 'file_path' in input_data:
                input_path = Path(input_data['file_path'])

                if input_data.get('retry', False):
                    result = remover.retry_with_different_settings(input_path)
                else:
                    result = remover.remove_background(
                        input_path,
                        enhance_input=input_data.get('enhance_input', True),
                        post_process=input_data.get('post_process', True)
                    )

                print(json.dumps(result, indent=2))

            elif 'files' in input_data:
                results = remover.process_batch(input_data['files'])
                print(json.dumps(results, indent=2))

            else:
                logger.error("Invalid input data format")
                sys.exit(1)

        except json.JSONDecodeError:
            logger.error("Invalid JSON input")
            sys.exit(1)


if __name__ == "__main__":
    main()