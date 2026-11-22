"""
PDF Splitter
Splits a PDF file into separate PDF files, one for each page.

Requirements:
    pip install pypdf
"""

import os
import sys
from pathlib import Path
from pypdf import PdfReader, PdfWriter


def split_pdf(pdf_path, output_folder=None):
    """
    Split a PDF into separate PDF files, one per page.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_folder (str): Output folder for split PDFs (default: same as PDF location)
    
    Returns:
        list: Paths to generated PDF files
    """
    # Validate PDF path
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Set output folder
    if output_folder is None:
        output_folder = pdf_path.parent / f"{pdf_path.stem}_pages"
    else:
        output_folder = Path(output_folder)
    
    # Create output folder if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"Splitting PDF: {pdf_path}")
    print(f"Output folder: {output_folder}")
    
    try:
        # Read the PDF
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        print(f"Total pages: {total_pages}")
        print("\nSplitting pages...")
        
        output_files = []
        
        # Split each page into a separate PDF
        for i, page in enumerate(reader.pages, start=1):
            # Create a new PDF writer for each page
            writer = PdfWriter()
            writer.add_page(page)
            
            # Generate output filename
            output_path = output_folder / f"page_{i:04d}.pdf"
            
            # Write the page to a new PDF file
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            output_files.append(output_path)
            
            # Progress indicator
            if i % 10 == 0 or i == total_pages:
                print(f"  Processed: {i}/{total_pages} pages")
        
        print(f"\n✓ Successfully split {total_pages} pages")
        print(f"  Output folder: {output_folder}")
        
        return output_files
    
    except Exception as e:
        print(f"✗ Error splitting PDF: {e}")
        raise


def batch_split(pdf_folder, output_folder=None):
    """
    Split all PDF files in a folder.
    
    Args:
        pdf_folder (str): Folder containing PDF files
        output_folder (str): Output folder for all split PDFs
    """
    pdf_folder = Path(pdf_folder)
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in: {pdf_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s)\n")
    
    for pdf_file in pdf_files:
        try:
            if output_folder:
                pdf_output = Path(output_folder) / pdf_file.stem
            else:
                pdf_output = None
            
            split_pdf(pdf_file, pdf_output)
            print()
        except Exception as e:
            print(f"Failed to split {pdf_file.name}: {e}\n")


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single file: python split_pdf.py <pdf_file> [output_folder]")
        print("  Batch:       python split_pdf.py --batch <pdf_folder> [output_folder]")
        print("\nExamples:")
        print("  python split_pdf.py document.pdf")
        print("  python split_pdf.py document.pdf output_pages")
        print("  python split_pdf.py --batch ./pdfs ./all_pages")
        sys.exit(1)
    
    # Parse arguments
    if sys.argv[1] == "--batch":
        if len(sys.argv) < 3:
            print("Error: Please specify folder containing PDF files")
            sys.exit(1)
        
        pdf_folder = sys.argv[2]
        output_folder = sys.argv[3] if len(sys.argv) > 3 else None
        
        batch_split(pdf_folder, output_folder)
    else:
        pdf_file = sys.argv[1]
        output_folder = sys.argv[2] if len(sys.argv) > 2 else None
        
        split_pdf(pdf_file, output_folder)
