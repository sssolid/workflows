#!/usr/bin/env python3
"""Create sample test images for development."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image(filename, size=(800, 600), color='white', text=None):
    """Create a test image with optional text."""
    img = Image.new('RGB', size, color)

    if text:
        draw = ImageDraw.Draw(img)
        # Try to use a default font, fall back to basic if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/arial.ttf", 40)
        except:
            font = ImageFont.load_default()

        # Center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2

        draw.text((x, y), text, fill='black', font=font)

    return img

# Sample images with various part number patterns
sample_images = [
    # Direct part number matches
    ("J1234567_detail.jpg", (1000, 800), 'lightblue', "J1234567\nFuel Tank\nSkid Plate"),
    ("A5551234_main.jpg", (1200, 900), 'lightgreen', "A5551234\nAir Filter\nElement"),
    ("12345_front.jpg", (800, 600), 'lightyellow', "12345\nEngine\nOil Pan"),
    ("67890_side.jpg", (900, 700), 'lightcoral', "67890\nWater Pump\nAssembly"),

    # Numbered variations (common pattern)
    ("J1234567_2.jpg", (1000, 800), 'lightcyan', "J1234567 #2\nAlternate View"),
    ("12345 (2).jpg", (800, 600), 'lavender', "12345 (2)\nSecond Photo"),
    ("A5551234_v3.jpg", (1200, 900), 'mistyrose', "A5551234 v3\nVersion 3"),

    # Interchange mapping tests (old part numbers)
    ("OLD12345_1.jpg", (800, 600), 'lightsteelblue', "OLD12345\n(maps to 12345)"),
    ("LEGACY67890.jpg", (900, 700), 'lightgoldenrodyellow', "LEGACY67890\n(maps to 67890)"),
    ("J1234567A_old.jpg", (1000, 800), 'lightpink', "J1234567A\n(revision A)"),

    # Manual review required (unclear part numbers)
    ("unknown_part_123.jpg", (800, 600), 'lightgray', "Unknown Part\nNeeds Review"),
    ("crown_part_xyz.jpg", (900, 700), 'wheat', "Crown Part XYZ\nManual Review"),
    ("IMG_001_product.jpg", (1000, 800), 'palegreen', "Generic Image\nNo Clear Part #"),

    # Different file formats
    ("B2222222_shock.png", (800, 600), 'aliceblue', "B2222222\nShock Absorber"),
    ("C3333333_joint.tiff", (1200, 900), 'honeydew', "C3333333\nCV Joint"),
]

# Create sample images directory
os.makedirs('dev/sample_images', exist_ok=True)

print("Creating sample test images...")
for filename, size, color, text in sample_images:
    img = create_test_image(filename, size, color, text)
    img.save(f'dev/sample_images/{filename}')
    print(f"  Created: {filename}")

print(f"Created {len(sample_images)} sample test images")

# Create a few PSD-like files (just renamed images for testing)
psd_files = [
    "J9876543_transmission_mount.psd",
    "A1111111_brake_pads.psd"
]

for psd_name in psd_files:
    # Create a larger, higher quality image for PSD simulation
    img = create_test_image("temp", (2500, 2000), 'white',
                          f"PSD FILE\n{psd_name.split('_')[0]}\nHigh Resolution")

    img.save(f'dev/sample_images/{psd_name}.png')  # Save as PNG
    os.rename(f'dev/sample_images/{psd_name}.png', f'dev/sample_images/{psd_name}')  # Rename to .psd

    print(f"  Created PSD simulation: {psd_name}")

print("Sample images created successfully!")
