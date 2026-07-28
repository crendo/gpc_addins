# -*- coding: utf-8 -*-
"""PDF Visual Comparison Engine"""

import sys
import os
import fitz # PyMuPDF
import cv2
import numpy as np

def compare_pdfs(pdf1_path, pdf2_path, out_pdf_path):
    if not os.path.exists(pdf1_path) or not os.path.exists(pdf2_path):
        print("ERROR: One or both PDF files do not exist.")
        return False
        
    doc1 = fitz.open(pdf1_path)
    doc2 = fitz.open(pdf2_path)
    
    out_doc = fitz.open()
    
    # Compare page count first
    num_pages1 = len(doc1)
    num_pages2 = len(doc2)
    num_pages = min(num_pages1, num_pages2)
    
    has_differences = num_pages1 != num_pages2
    
    for i in range(num_pages):
        page1 = doc1[i]
        page2 = doc2[i]
        
        # Render pages to high-res images (zoom factor 2.0 for sharp comparison)
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        
        pix1 = page1.get_pixmap(matrix=mat)
        pix2 = page2.get_pixmap(matrix=mat)
        
        # Convert pixmaps to numpy arrays
        img1 = np.frombuffer(pix1.samples, dtype=np.uint8).reshape(pix1.h, pix1.w, pix1.n)
        img2 = np.frombuffer(pix2.samples, dtype=np.uint8).reshape(pix2.h, pix2.w, pix2.n)
        
        # Ensure 3-channel RGB format
        if pix1.n == 4:
            img1 = cv2.cvtColor(img1, cv2.COLOR_RGBA2RGB)
        if pix2.n == 4:
            img2 = cv2.cvtColor(img2, cv2.COLOR_RGBA2RGB)
            
        h, w = img1.shape[:2]
        if img2.shape[:2] != (h, w):
            img2 = cv2.resize(img2, (w, h))
            
        # Convert to grayscale to mask drawing elements
        gray1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
        
        # Threshold: elements are dark (pixel value < 240)
        mask1 = gray1 < 240
        mask2 = gray2 < 240
        
        # Detect additions and deletions
        deleted = mask1 & ~mask2
        added = mask2 & ~mask1
        unchanged = mask1 & mask2
        
        # Filter minor rendering/aliasing noise (threshold of 20 pixels)
        diff_pixels = np.sum(deleted) + np.sum(added)
        if diff_pixels > 20:
            has_differences = True
            
        # Create visual diff image with white background
        diff_img = np.ones((h, w, 3), dtype=np.uint8) * 255
        
        # Unchanged elements: Gray
        diff_img[unchanged] = [128, 128, 128]
        
        # Deleted elements (previous version only): Red
        diff_img[deleted] = [255, 0, 0]
        
        # Added elements (new version only): Green
        diff_img[added] = [0, 180, 0]
        
        # Save diff image to temporary file
        temp_img_path = os.path.join(os.path.dirname(out_pdf_path), "temp_diff_{}.png".format(i))
        cv2.imwrite(temp_img_path, cv2.cvtColor(diff_img, cv2.COLOR_RGB2BGR))
        
        # Insert image as a new page in output document
        rect = page1.rect
        out_page = out_doc.new_page(width=rect.width, height=rect.height)
        out_page.insert_image(rect, filename=temp_img_path)
        
        # Clean up temp file
        if os.path.exists(temp_img_path):
            try:
                os.remove(temp_img_path)
            except:
                pass
                
    doc1.close()
    doc2.close()
    
    if has_differences:
        try:
            # Create output folder if it doesn't exist
            out_dir = os.path.dirname(out_pdf_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir)
            out_doc.save(out_pdf_path)
        except Exception as e:
            print("ERROR: Failed to save comparison PDF: {}".format(e))
        finally:
            out_doc.close()
        return True
    else:
        out_doc.close()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python compare_pdfs.py <pdf1_path> <pdf2_path> <out_pdf_path>")
        sys.exit(2)
        
    pdf1 = sys.argv[1]
    pdf2 = sys.argv[2]
    out_pdf = sys.argv[3]
    
    diff = compare_pdfs(pdf1, pdf2, out_pdf)
    if diff:
        print("DIFFERENT")
        sys.exit(1)
    else:
        print("IDENTICAL")
        sys.exit(0)
