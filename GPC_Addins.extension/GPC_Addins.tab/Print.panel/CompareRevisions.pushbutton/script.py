# -*- coding: utf-8 -*-
"""Compare two revisions of a PDF visual changes"""

import os
import re
import sys
import subprocess
import datetime
from pyrevit import forms, script

def sanitize_filename(name):
    """Remove illegal OS characters from filename"""
    invalid_chars = r'[<>:"/\\|?*]'
    return re.sub(invalid_chars, '_', name)

def get_sort_key(rev):
    """Returns a key for sorting revisions naturally."""
    if rev.isdigit():
        return (1, int(rev))
    return (0, rev.upper())

def main():
    # 1. Ask the user to select the latest PDF file
    latest_pdf_path = forms.pick_file(
        files_filter="PDF files (*.pdf)|*.pdf",
        title="Select Latest PDF (from Export Folder)"
    )
    if not latest_pdf_path:
        return

    folder = os.path.dirname(latest_pdf_path)
    filename = os.path.basename(latest_pdf_path)

    # 2. Extract base name and revision (Format: BaseName_Revision.pdf)
    pattern = re.compile(r"^(.*)_([a-zA-Z0-9\-]+)\.pdf$", re.IGNORECASE)
    match = pattern.match(filename)
    if match:
        base_name, current_rev = match.groups()
    else:
        base_name = os.path.splitext(filename)[0]
        current_rev = None

    # 3. Look for matching archived revisions in the "superados" folder
    archive_dir = os.path.join(folder, "superados")
    candidates = []

    if os.path.exists(archive_dir):
        for f in os.listdir(archive_dir):
            if not f.lower().endswith(".pdf"):
                continue

            f_match = pattern.match(f)
            if f_match:
                archived_base, archived_rev = f_match.groups()
            else:
                archived_base, archived_rev = os.path.splitext(f)[0], ""

            if archived_base.lower() == base_name.lower():
                # Avoid comparing the exact same file/revision
                if archived_rev.lower() != (current_rev or "").lower():
                    candidates.append((os.path.join(archive_dir, f), archived_rev, f))

    archived_pdf_path = None
    archived_rev = "Old"

    selected_filename = None
    if candidates:
        # Sort candidates naturally by revision
        candidates.sort(key=lambda x: get_sort_key(x[1]))
        options = [c[2] for c in candidates]
        options.append("<Select another PDF file manually...>")
        
        selected_filename = forms.ask_for_one_item(
            options,
            title="Select Archived PDF Revision to Compare",
            default=options[-2] if len(options) > 1 else options[0]
        )
        if not selected_filename:
            return
            
        if selected_filename == "<Select another PDF file manually...>":
            selected_filename = None

    if not selected_filename:
        # Prompt user to pick manually
        archived_pdf_path = forms.pick_file(
            files_filter="PDF files (*.pdf)|*.pdf",
            title="Select Archived PDF to Compare",
            init_dir=archive_dir if os.path.exists(archive_dir) else folder
        )
        if not archived_pdf_path:
            return
        
        # Parse revision from manually picked filename
        archived_filename = os.path.basename(archived_pdf_path)
        f_match = pattern.match(archived_filename)
        archived_rev = f_match.group(2) if f_match else "Old"
    else:
        # Resolve the selected candidate
        for c in candidates:
            if c[2] == selected_filename:
                archived_pdf_path, archived_rev, _ = c
                break

    # 4. Resolve the path to compare_pdfs.py in the BatchExport bundle
    current_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(current_dir)
    compare_script = os.path.join(parent_dir, "BatchExport.pushbutton", "compare_pdfs.py")

    if not os.path.exists(compare_script):
        forms.alert(
            "Could not locate compare_pdfs.py at:\n{}".format(compare_script),
            title="Engine Error"
        )
        return

    # 5. Define output comparison path
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    comp_file_name = "Comparacion_{}_{}_{}_{}".format(
        base_name,
        current_rev or "New",
        archived_rev,
        timestamp
    )
    comp_file_name = sanitize_filename(comp_file_name)
    comp_pdf_path = os.path.join(folder, comp_file_name + ".pdf")

    # 6. Run comparison via standard python subprocess
    python_exe = "python"
    try:
        process = subprocess.Popen(
            [python_exe, compare_script, archived_pdf_path, latest_pdf_path, comp_pdf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        if process.returncode == 1:
            forms.alert(
                "Visual comparison PDF generated successfully:\n\nFile: {}.pdf\nFolder: {}".format(comp_file_name, folder),
                title="Comparison Complete"
            )
        elif process.returncode == 0:
            forms.alert(
                "The PDFs are visually identical.\n\nNo comparison PDF was saved.",
                title="Comparison Complete"
            )
        else:
            error_msg = stderr.decode('utf-8', errors='ignore') or stdout.decode('utf-8', errors='ignore')
            forms.alert(
                "Comparison engine returned error:\n\n{}".format(error_msg),
                title="Engine Error"
            )
    except Exception as e:
        forms.alert(
            "Failed to launch Python comparison subprocess:\n\n{}".format(e),
            title="Launch Error"
        )

if __name__ == '__main__':
    main()
