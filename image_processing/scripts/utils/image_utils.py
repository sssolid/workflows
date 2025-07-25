#!/usr/bin/env python3
"""
Image Utilities for Crown Automotive Image Processing
Shared image processing functions and utilities
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union
import hashlib
from datetime import datetime

from PIL import Image, ImageOps, ImageChops, ImageFilter, ImageEnhance
from PIL.ExifTags import TAGS
import piexif

logger = logging.getLogger(__name__)


class ImageInfo:
    """Class to hold comprehensive image information"""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        self.name = self.file_path.name
        self.stem = self.file_path.stem
        self.suffix = self.file_path.suffix.lower()
        self.size_bytes = 0
        self.size_mb = 0.0
        self.dimensions = (0, 0)
        self.mode = ""
        self.format = ""
        self.has_transparency = False
        self.dpi = (72, 72)
        self.color_profile = None
        self.created = None
        self.modified = None
        self.file_hash = ""
        self.exif_data = {}
        self.errors = []

        self._analyze_file()

    def _analyze_file(self):
        """Analyze the image file and populate all information"""
        try:
            if not self.file_path.exists():
                self.errors.append("File does not exist")
                return

            # Get file stats
            stat = self.file_path.stat()
            self.size_bytes = stat.st_size
            self.size_mb = round(stat.st_size / (1024 * 1024), 2)
            self.created = datetime.fromtimestamp(stat.st_ctime)
            self.modified = datetime.fromtimestamp(stat.st_mtime)

            # Calculate file hash
            self.file_hash = self._calculate_hash()

            # Analyze image with PIL
            try:
                with Image.open(self.file_path) as img:
                    self.dimensions = img.size
                    self.mode = img.mode
                    self.format = img.format or "Unknown"
                    self.has_transparency = img.mode in ('RGBA', 'LA', 'P') and 'transparency' in img.info

                    # Get DPI if available
                    if hasattr(img, 'info') and 'dpi' in img.info:
                        self.dpi = img.info['dpi']

                    # Get color profile
                    if hasattr(img, 'info') and 'icc_profile' in img.info:
                        self.color_profile = "ICC Profile Present"

                    # Extract EXIF data
                    self.exif_data = self._extract_exif(img)

            except Exception as e:
                self.errors.append(f"Error analyzing image: {e}")

        except Exception as e:
            self.errors.append(f"Error analyzing file: {e}")

    def _calculate_hash(self) -> str:
        """Calculate MD5 hash of the file"""
        try:
            hash_md5 = hashlib.md5()
            with open(self.file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {self.file_path}: {e}")
            return ""

    def _extract_exif(self, img: Image.Image) -> Dict[str, Any]:
        """Extract EXIF data from image"""
        exif_dict = {}

        try:
            if hasattr(img, '_getexif') and img._getexif() is not None:
                exif = img._getexif()
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_dict[tag] = value

            # Also try piexif for more complete EXIF extraction
            if self.suffix in ['.jpg', '.jpeg', '.tiff', '.tif']:
                try:
                    exif_data = piexif.load(str(self.file_path))

                    # Extract key EXIF fields
                    for ifd_name, ifd in exif_data.items():
                        if isinstance(ifd, dict):
                            for tag_id, value in ifd.items():
                                tag_name = piexif.TAGS.get(ifd_name, {}).get(tag_id, {}).get('name',
                                                                                             f'{ifd_name}_{tag_id}')
                                if tag_name and tag_name not in exif_dict:
                                    # Handle different value types
                                    if isinstance(value, bytes):
                                        try:
                                            value = value.decode('utf-8')
                                        except:
                                            value = str(value)
                                    exif_dict[tag_name] = value

                except Exception as e:
                    logger.debug(f"piexif extraction failed for {self.file_path}: {e}")

        except Exception as e:
            logger.debug(f"EXIF extraction failed for {self.file_path}: {e}")

        return exif_dict

    def to_dict(self) -> Dict[str, Any]:
        """Convert ImageInfo to dictionary"""
        return {
            "file_path": str(self.file_path),
            "name": self.name,
            "stem": self.stem,
            "suffix": self.suffix,
            "size_bytes": self.size_bytes,
            "size_mb": self.size_mb,
            "dimensions": {
                "width": self.dimensions[0],
                "height": self.dimensions[1]
            },
            "mode": self.mode,
            "format": self.format,
            "has_transparency": self.has_transparency,
            "dpi": self.dpi,
            "color_profile": self.color_profile,
            "created": self.created.isoformat() if self.created else None,
            "modified": self.modified.isoformat() if self.modified else None,
            "file_hash": self.file_hash,
            "exif_data": self.exif_data,
            "errors": self.errors
        }

    @property
    def is_valid(self) -> bool:
        """Check if the image is valid (no critical errors)"""
        return len(self.errors) == 0 and self.dimensions[0] > 0 and self.dimensions[1] > 0

    @property
    def is_high_resolution(self) -> bool:
        """Check if image is high resolution (>= 2500px on longest side)"""
        return max(self.dimensions) >= 2500

    @property
    def aspect_ratio(self) -> float:
        """Get aspect ratio (width/height)"""
        if self.dimensions[1] == 0:
            return 0.0
        return self.dimensions[0] / self.dimensions[1]

    @property
    def megapixels(self) -> float:
        """Get megapixel count"""
        return round((self.dimensions[0] * self.dimensions[1]) / 1_000_000, 2)


def validate_image_file(file_path: Union[str, Path],
                        min_size: int = 1024,
                        max_size: int = 100 * 1024 * 1024,
                        supported_formats: Optional[list] = None) -> Dict[str, Any]:
    """
    Validate an image file for processing

    Args:
        file_path: Path to image file
        min_size: Minimum file size in bytes
        max_size: Maximum file size in bytes
        supported_formats: List of supported file extensions

    Returns:
        Dictionary with validation results
    """
    if supported_formats is None:
        supported_formats = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.psd', '.bmp']

    file_path = Path(file_path)
    validation = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "file_info": None
    }

    try:
        # Check if file exists
        if not file_path.exists():
            validation["errors"].append("File does not exist")
            return validation

        # Check file extension
        if file_path.suffix.lower() not in supported_formats:
            validation["errors"].append(f"Unsupported format: {file_path.suffix}")
            return validation

        # Get detailed file info
        info = ImageInfo(file_path)
        validation["file_info"] = info.to_dict()

        # Check for analysis errors
        if info.errors:
            validation["errors"].extend(info.errors)
            return validation

        # File size validation
        if info.size_bytes < min_size:
            validation["errors"].append(f"File too small: {info.size_mb}MB (minimum: {min_size / 1024 / 1024}MB)")

        if info.size_bytes > max_size:
            validation["errors"].append(f"File too large: {info.size_mb}MB (maximum: {max_size / 1024 / 1024}MB)")

        # Resolution warnings
        if not info.is_high_resolution:
            validation["warnings"].append(
                f"Low resolution: {info.dimensions[0]}x{info.dimensions[1]} (recommended: 2500px+)")

        # Aspect ratio check
        if info.aspect_ratio < 0.5 or info.aspect_ratio > 2.0:
            validation["warnings"].append(f"Unusual aspect ratio: {info.aspect_ratio:.2f}")

        # Color mode warnings
        if info.mode not in ['RGB', 'RGBA', 'L']:
            validation["warnings"].append(f"Unusual color mode: {info.mode}")

        # Set valid if no errors
        validation["valid"] = len(validation["errors"]) == 0

    except Exception as e:
        validation["errors"].append(f"Validation error: {e}")

    return validation


def crop_to_content(img: Image.Image, padding: int = 0) -> Image.Image:
    """
    Crop image to content, removing transparent/empty areas

    Args:
        img: PIL Image
        padding: Padding to add around content

    Returns:
        Cropped image
    """
    try:
        if img.mode == 'RGBA':
            # For RGBA images, crop based on alpha channel
            alpha = img.split()[-1]
            bbox = alpha.getbbox()
        else:
            # For other modes, try to find non-white areas
            bg = Image.new(img.mode, img.size, (255,) * len(img.getbands()))
            diff = ImageChops.difference(img, bg)
            bbox = diff.getbbox()

        if bbox:
            # Add padding if specified
            if padding > 0:
                bbox = (
                    max(0, bbox[0] - padding),
                    max(0, bbox[1] - padding),
                    min(img.width, bbox[2] + padding),
                    min(img.height, bbox[3] + padding)
                )

            return img.crop(bbox)
        else:
            logger.warning("No content found to crop to")
            return img

    except Exception as e:
        logger.error(f"Error cropping to content: {e}")
        return img


def enhance_for_background_removal(img: Image.Image) -> Image.Image:
    """
    Enhance image for better background removal results

    Args:
        img: PIL Image

    Returns:
        Enhanced image
    """
    try:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Slight contrast enhancement
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.1)

        # Slight sharpening
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))

        return img

    except Exception as e:
        logger.error(f"Error enhancing image: {e}")
        return img


def create_thumbnail(img: Image.Image, size: Tuple[int, int] = (200, 200)) -> Image.Image:
    """
    Create a thumbnail of the image

    Args:
        img: PIL Image
        size: Thumbnail size as (width, height)

    Returns:
        Thumbnail image
    """
    try:
        # Create thumbnail maintaining aspect ratio
        thumbnail = img.copy()
        thumbnail.thumbnail(size, Image.LANCZOS)

        # Center on a square background if needed
        if thumbnail.size != size:
            background = Image.new('RGBA', size, (255, 255, 255, 0))
            offset = (
                (size[0] - thumbnail.width) // 2,
                (size[1] - thumbnail.height) // 2
            )
            background.paste(thumbnail, offset)
            thumbnail = background

        return thumbnail

    except Exception as e:
        logger.error(f"Error creating thumbnail: {e}")
        return img


def compare_images(img1: Image.Image, img2: Image.Image) -> Dict[str, Any]:
    """
    Compare two images and return similarity metrics

    Args:
        img1: First image
        img2: Second image

    Returns:
        Dictionary with comparison metrics
    """
    try:
        # Ensure same size for comparison
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.LANCZOS)

        # Ensure same mode
        if img1.mode != img2.mode:
            img2 = img2.convert(img1.mode)

        # Calculate difference
        diff = ImageChops.difference(img1, img2)

        # Get statistics
        stat = {
            "dimensions_match": img1.size == img2.size,
            "mode_match": img1.mode == img2.mode,
            "identical": diff.getbbox() is None
        }

        if not stat["identical"]:
            # Calculate difference metrics
            pixels = img1.width * img1.height
            diff_pixels = sum(1 for pixel in diff.getdata() if any(c > 0 for c in pixel))
            stat["difference_percentage"] = (diff_pixels / pixels) * 100
        else:
            stat["difference_percentage"] = 0.0

        return stat

    except Exception as e:
        logger.error(f"Error comparing images: {e}")
        return {"error": str(e)}


def extract_dominant_colors(img: Image.Image, num_colors: int = 5) -> list:
    """
    Extract dominant colors from an image

    Args:
        img: PIL Image
        num_colors: Number of dominant colors to extract

    Returns:
        List of RGB tuples representing dominant colors
    """
    try:
        # Convert to RGB and resize for faster processing
        img_rgb = img.convert('RGB')
        img_rgb = img_rgb.resize((150, 150), Image.LANCZOS)

        # Get colors using quantization
        quantized = img_rgb.quantize(colors=num_colors, method=Image.MEDIANCUT)
        palette = quantized.getpalette()

        # Extract RGB values
        colors = []
        for i in range(num_colors):
            rgb = tuple(palette[i * 3:(i + 1) * 3])
            colors.append(rgb)

        return colors

    except Exception as e:
        logger.error(f"Error extracting dominant colors: {e}")
        return []


def get_image_quality_score(img_info: ImageInfo) -> Dict[str, Any]:
    """
    Calculate a quality score for an image based on various factors

    Args:
        img_info: ImageInfo object

    Returns:
        Dictionary with quality assessment
    """
    score = 100  # Start with perfect score
    issues = []

    # Resolution check
    if not img_info.is_high_resolution:
        score -= 20
        issues.append("Low resolution")

    # File size check
    if img_info.size_mb < 1:
        score -= 10
        issues.append("Small file size")
    elif img_info.size_mb > 50:
        score -= 5
        issues.append("Very large file size")

    # Aspect ratio check
    if img_info.aspect_ratio < 0.7 or img_info.aspect_ratio > 1.4:
        score -= 5
        issues.append("Non-square aspect ratio")

    # Color mode check
    if img_info.mode not in ['RGB', 'RGBA']:
        score -= 10
        issues.append("Non-RGB color mode")

    # DPI check
    if img_info.dpi[0] < 150 or img_info.dpi[1] < 150:
        score -= 5
        issues.append("Low DPI")

    # Format check
    if img_info.suffix in ['.jpg', '.jpeg'] and img_info.has_transparency:
        score -= 5
        issues.append("JPEG with transparency")

    score = max(0, score)  # Don't go below 0

    quality_level = "Excellent" if score >= 90 else \
        "Good" if score >= 75 else \
            "Fair" if score >= 60 else \
                "Poor"

    return {
        "score": score,
        "level": quality_level,
        "issues": issues,
        "recommendations": _get_quality_recommendations(issues)
    }


def _get_quality_recommendations(issues: list) -> list:
    """Get recommendations based on quality issues"""
    recommendations = []

    if "Low resolution" in issues:
        recommendations.append("Use higher resolution source image (2500px+ recommended)")

    if "Small file size" in issues:
        recommendations.append("Source image may be too compressed")

    if "Non-square aspect ratio" in issues:
        recommendations.append("Consider cropping to square format for product images")

    if "Low DPI" in issues:
        recommendations.append("Set DPI to 300 for print quality")

    if "JPEG with transparency" in issues:
        recommendations.append("Use PNG format for images with transparency")

    return recommendations


def main():
    """Test image utilities"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Test image utilities')
    parser.add_argument('image_file', help='Image file to analyze')
    parser.add_argument('--validate', action='store_true', help='Run validation')
    parser.add_argument('--quality', action='store_true', help='Assess quality')

    args = parser.parse_args()

    if not Path(args.image_file).exists():
        print(f"❌ File not found: {args.image_file}")
        sys.exit(1)

    # Basic info
    info = ImageInfo(args.image_file)
    print(f"📁 File: {info.name}")
    print(f"📐 Dimensions: {info.dimensions[0]}x{info.dimensions[1]}")
    print(f"📊 Size: {info.size_mb} MB")
    print(f"🎨 Mode: {info.mode}")
    print(f"📸 Format: {info.format}")

    if args.validate:
        print("\n🔍 Validation:")
        validation = validate_image_file(args.image_file)
        print(f"Valid: {'✅' if validation['valid'] else '❌'}")

        if validation['errors']:
            print("Errors:")
            for error in validation['errors']:
                print(f"  ❌ {error}")

        if validation['warnings']:
            print("Warnings:")
            for warning in validation['warnings']:
                print(f"  ⚠️ {warning}")

    if args.quality:
        print("\n⭐ Quality Assessment:")
        quality = get_image_quality_score(info)
        print(f"Score: {quality['score']}/100 ({quality['level']})")

        if quality['issues']:
            print("Issues:")
            for issue in quality['issues']:
                print(f"  ⚠️ {issue}")

        if quality['recommendations']:
            print("Recommendations:")
            for rec in quality['recommendations']:
                print(f"  💡 {rec}")


if __name__ == "__main__":
    main()