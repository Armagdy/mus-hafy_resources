"""
PDF to JPG Converter
Converts each page of a PDF file to individual JPG images.

Requirements:
    pip install pdf2image pillow
    
    You also need to install poppler:
    - Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/
      and add the bin folder to your PATH
    - Linux: sudo apt-get install poppler-utils
    - Mac: brew install poppler
"""

import os
import sys
from pathlib import Path
import urllib.request
import zipfile
from pdf2image import convert_from_path
from PIL import Image


def ensure_poppler():
    """Download and setup Poppler if not available."""
    poppler_dir = Path("poppler")
    poppler_bin = poppler_dir / "poppler-24.08.0" / "Library" / "bin"
    
    if poppler_bin.exists():
        return str(poppler_bin)
    
    print("Poppler not found. Downloading...")
    poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip"
    zip_path = "poppler.zip"
    
    try:
        urllib.request.urlretrieve(poppler_url, zip_path)
        print("Extracting Poppler...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(poppler_dir)
        os.remove(zip_path)
        print(f"Poppler installed to: {poppler_bin}")
        return str(poppler_bin)
    except Exception as e:
        print(f"Error downloading Poppler: {e}")
        print("Please download manually from: https://github.com/oschwartz10612/poppler-windows/releases/")
        return None


def pdf_to_jpg(pdf_path, output_folder=None, dpi=300, jpg_quality=95, poppler_path=None):
    """
    Convert PDF pages to JPG images.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_folder (str): Output folder for JPG images (default: same as PDF location)
        dpi (int): DPI for image quality (default: 300)
        jpg_quality (int): JPG quality 1-100 (default: 95)
    
    Returns:
        list: Paths to generated JPG files
    """
    # Validate PDF path
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Set output folder
    if output_folder is None:
        output_folder = pdf_path.parent / f"{pdf_path.stem}_images"
    else:
        output_folder = Path(output_folder)
    
    # Create output folder if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"Converting PDF: {pdf_path}")
    print(f"Output folder: {output_folder}")
    print(f"DPI: {dpi}, Quality: {jpg_quality}%")
    
    try:
        # Convert PDF to images
        print("Converting pages...")
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            fmt='jpeg',
            poppler_path=poppler_path
        )
        
        output_files = []
        total_pages = len(images)
        
        # Save each page as JPG
        for i, image in enumerate(images, start=1):
            output_path = output_folder / f"page_{i:04d}.jpg"
            
            # Save with specified quality
            image.save(output_path, 'JPEG', quality=jpg_quality, optimize=True)
            output_files.append(output_path)
            
            print(f"  Saved page {i}/{total_pages}: {output_path.name}")
        
        print(f"\n✓ Successfully converted {total_pages} pages to JPG")
        return output_files
    
    except Exception as e:
        print(f"✗ Error converting PDF: {e}")
        raise


def batch_convert(pdf_folder, output_folder=None, dpi=300, jpg_quality=95, poppler_path=None):
    """
    Convert all PDF files in a folder to JPG images.
    
    Args:
        pdf_folder (str): Folder containing PDF files
        output_folder (str): Output folder for all images
        dpi (int): DPI for image quality
        jpg_quality (int): JPG quality 1-100
        poppler_path (str): Path to Poppler binaries
    """
    pdf_folder = Path(pdf_folder)
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in: {pdf_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s)\n")
    
    # Use the same folder for output if specified
    if output_folder:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    
    for pdf_file in pdf_files:
        try:
            # Convert each PDF and save JPG with same name in output folder
            if output_folder:
                # Convert PDF to image
                images = convert_from_path(
                    pdf_file,
                    dpi=dpi,
                    fmt='jpeg',
                    poppler_path=poppler_path
                )
                
                # Save first page with PDF's name as JPG
                if images:
                    output_path = output_folder / f"{pdf_file.stem}.jpg"
                    images[0].save(output_path, 'JPEG', quality=jpg_quality, optimize=True)
                    print(f"✓ Converted {pdf_file.name} -> {output_path.name}")
            else:
                pdf_to_jpg(pdf_file, None, dpi, jpg_quality, poppler_path)
                print()
        except Exception as e:
            print(f"✗ Failed to convert {pdf_file.name}: {e}\n")


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single file: python pdf_to_jpg.py <pdf_file> [output_folder] [dpi] [quality]")
        print("  Batch:       python pdf_to_jpg.py --batch <pdf_folder> [output_folder] [dpi] [quality]")
        print("\nExamples:")
        print("  python pdf_to_jpg.py document.pdf")
        print("  python pdf_to_jpg.py document.pdf output_images 200 90")
        print("  python pdf_to_jpg.py --batch ./pdfs ./all_images")
        sys.exit(1)
    
    # Ensure Poppler is available
    poppler_path = ensure_poppler()
    
    # Parse arguments
    if sys.argv[1] == "--batch":
        if len(sys.argv) < 3:
            print("Error: Please specify folder containing PDF files")
            sys.exit(1)
        
        pdf_folder = sys.argv[2]
        output_folder = sys.argv[3] if len(sys.argv) > 3 else None
        dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 300
        quality = int(sys.argv[5]) if len(sys.argv) > 5 else 95
        
        batch_convert(pdf_folder, output_folder, dpi, quality, poppler_path)
    else:
        pdf_file = sys.argv[1]
        output_folder = sys.argv[2] if len(sys.argv) > 2 else None
        dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        quality = int(sys.argv[4]) if len(sys.argv) > 4 else 95
        
        pdf_to_jpg(pdf_file, output_folder, dpi, quality, poppler_path)
