#!/usr/bin/env python3
"""
Script to extract base64 SVG images from HTML files, convert them to images,
and decode QR codes from those images.

QR code images and decoded text are automatically saved to downloaded_tasks/qrcode/
with filenames matching the source HTML file.

Usage examples:
    # Process a single HTML file
    python extract_qr_from_html.py downloaded_tasks/html/task_bevo.html
    
    # Process multiple specific HTML files
    python extract_qr_from_html.py downloaded_tasks/html/task_bevo.html downloaded_tasks/html/task_dami.html

    # Process all HTML files in the directory
    python extract_qr_from_html.py downloaded_tasks/html/*.html

    # Process all HTML files and save intermediate PNG images
    python extract_qr_from_html.py downloaded_tasks/html/*.html -o output_images
    
    # Process with verbose output
    python extract_qr_from_html.py downloaded_tasks/html/*.html -v

Prerequisites:
    pip install opencv-python pyzbar cairosvg
"""

import argparse
import base64
import re
from pathlib import Path
from typing import List, Optional

try:
    import cv2
    import numpy as np
    from pyzbar import pyzbar
    from cairosvg import svg2png
except ImportError as e:
    print(f"Required package not installed: {e}")
    print("Please install with: pip install opencv-python pyzbar cairosvg")
    exit(1)


def extract_base64_svgs(html_content: str) -> List[str]:
    """Extract base64 encoded SVG images from HTML content."""
    # Pattern to match base64 encoded SVG images
    pattern = r'data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)'
    matches = re.findall(pattern, html_content)
    return matches


def decode_base64_svg(base64_data: str) -> str:
    """Decode base64 encoded SVG data."""
    try:
        svg_data = base64.b64decode(base64_data)
        return svg_data.decode('utf-8')
    except Exception as e:
        print(f"Error decoding base64 SVG: {e}")
        return ""


def svg_to_png(svg_data: str) -> Optional[np.ndarray]:
    """Convert SVG data to PNG image as numpy array."""
    try:
        # Convert SVG to PNG bytes
        png_bytes = svg2png(bytestring=svg_data.encode('utf-8'))
        if png_bytes is None:
            return None
            
        # Convert PNG bytes to numpy array
        png_array = np.frombuffer(memoryview(png_bytes), dtype=np.uint8)
        image = cv2.imdecode(png_array, cv2.IMREAD_COLOR)
        
        return image
    except Exception as e:
        print(f"Error converting SVG to PNG: {e}")
        return None


def decode_qr_code(image: np.ndarray) -> List[str]:
    """Decode QR codes from an image."""
    qr_codes = []
    
    # Convert to grayscale for better QR code detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Detect and decode QR codes
    decoded_objects = pyzbar.decode(gray)
    
    for obj in decoded_objects:
        qr_data = obj.data.decode('utf-8')
        qr_codes.append(qr_data)
    
    return qr_codes


def process_html_file(html_file: Path, output_dir: Optional[Path] = None) -> List[str]:
    """Process an HTML file and extract QR codes from base64 SVG images."""
    print(f"Processing: {html_file}")
    
    # Create QR code output directory
    qrcode_dir = Path("downloaded_tasks/qrcode")
    qrcode_dir.mkdir(parents=True, exist_ok=True)
    
    # Read HTML content
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"Error reading HTML file: {e}")
        return []
    
    # Extract base64 SVG images
    base64_svgs = extract_base64_svgs(html_content)
    print(f"Found {len(base64_svgs)} base64 SVG images")
    
    all_qr_codes = []
    
    for i, base64_svg in enumerate(base64_svgs):
        print(f"Processing SVG {i+1}/{len(base64_svgs)}")
        
        # Decode base64 SVG
        svg_data = decode_base64_svg(base64_svg)
        if not svg_data:
            continue
        
        # Convert SVG to PNG
        image = svg_to_png(svg_data)
        if image is None:
            continue
        
        # Save intermediate PNG if output directory is specified
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            png_file = output_dir / f"{html_file.stem}_svg_{i+1}.png"
            cv2.imwrite(str(png_file), image)
            print(f"Saved PNG: {png_file}")
        
        # Decode QR codes from image
        qr_codes = decode_qr_code(image)
        if qr_codes:
            print(f"Found QR code: {qr_codes[0]}")
            all_qr_codes.extend(qr_codes)
            
            # Save QR code image (without numbering)
            qr_image_file = qrcode_dir / f"{html_file.stem}.png"
            cv2.imwrite(str(qr_image_file), image)
            print(f"Saved QR code image: {qr_image_file}")
            
            # Save decoded QR code string (without numbering)
            qr_text_file = qrcode_dir / f"{html_file.stem}.txt"
            with open(qr_text_file, 'w', encoding='utf-8') as f:
                f.write(qr_codes[0])
            print(f"Saved QR code text: {qr_text_file}")
            
            # Since we expect only one QR code per HTML file, break after finding the first one
            break
        else:
            print("No QR codes found in this image")
    
    return all_qr_codes


def main():
    parser = argparse.ArgumentParser(description="Extract QR codes from base64 SVG images in HTML files")
    parser.add_argument("html_files", nargs="+", help="HTML files to process")
    parser.add_argument("-o", "--output-dir", type=Path, help="Directory to save intermediate PNG files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    all_qr_codes = []
    
    for html_file_path in args.html_files:
        html_file = Path(html_file_path)
        
        if not html_file.exists():
            print(f"File not found: {html_file}")
            continue
        
        if not html_file.is_file():
            print(f"Not a file: {html_file}")
            continue
        
        qr_codes = process_html_file(html_file, args.output_dir)
        all_qr_codes.extend(qr_codes)
    
    print("\n=== SUMMARY ===")
    print(f"Total QR codes found: {len(all_qr_codes)}")


if __name__ == "__main__":
    main()
