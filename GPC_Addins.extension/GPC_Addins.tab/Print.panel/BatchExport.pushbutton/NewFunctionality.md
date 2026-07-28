# Visual PDF Comparison & Archiving Feature

We have successfully implemented the visual comparison and archiving functionality for pyRevit Batch Export. Rather than using DWG comparison (which depends on heavy AutoCAD GUI automation and causes RPC blocks), we compare the higher-fidelity PDF exports using a modern, background-friendly CPython script.

## Features Implemented

1. **Comparison UI Checkbox:**
   - Added a new checkbox "Compare PDF exports before overwriting" in the Batch Export interface (`ui.xaml`), with settings persistence handled in `script.py`.

2. **Direct Export & Archive Flow:**
   - Standard PDF and DWG files are exported directly to the target folder.
   - If comparison is enabled, the script scans the `superados` folder (with fallback to the main folder) for the most recent previous revision of that sheet (using natural sort order to prioritize the latest, e.g. revision `3` over older revisions `a` or `C`).
   - If a previous revision exists, the script runs the comparison engine to compare the two PDFs.
   - At the end of the script execution, the standard pyRevit archiving logic moves superseded versions to the `superados` subfolder.

3. **High-Fidelity Visual Diff Engine (`compare_pdfs.py`):**
   - Created a standalone Python 3 worker script using `PyMuPDF` (fitz) and `OpenCV` / `NumPy`.
   - Renders PDF pages to high-resolution images, aligns them, and highlights differences:
     - **Gray:** Unchanged elements
     - **Red:** Deleted elements (old only)
     - **Green:** Added elements (new only)
   - Outputs the visual diff PDF directly next to the drawing using the format:
     `Comparacion_<sheet_number>_<new_rev>_<prev_rev>_<timestamp>.pdf`
     (e.g., `Comparacion_ICI-1_4_3_20260728_131655.pdf` or `Comparacion_ICI-1_4_4_20260728_134500.pdf` if comparing two versions of revision 4).

4. **Console Auto-Close:**
   - Added `output.self_destruct(3)` at the end of the main script. The pyRevit console output window automatically closes 3 seconds after the export completes.
