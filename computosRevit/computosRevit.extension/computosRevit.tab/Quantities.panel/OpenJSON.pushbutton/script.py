"""Open the quantity data JSON database file in the default viewer."""

__title__ = 'Open\nJSON'
__author__ = 'Computos Revit Team'

from pyrevit import revit, DB, forms
import os
import sys

# Setup Library Paths
# OpenJSON.pushbutton -> Quantities.panel -> tab -> extension
TAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSION_DIR = os.path.join(os.path.dirname(TAB_DIR), "computosRevit.extension")
LIB_PATH = os.path.join(EXTENSION_DIR, "lib")
if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

import database
import sync

def run():
    doc = revit.doc
    # 1. Prompt user to select a JSON database file from any directory
    selected_file = forms.pick_file(file_ext='json', title="Select Computos Database JSON To Load")
    
    # 2. If a file is selected, process it
    if selected_file:
        # Load the DataStore from the selected file
        store = database.get_store(selected_file)
        
        # 3. Import data into Revit Elements
        updated_count = sync.sync_from_store(doc, store, show_progress=True)
        
        if updated_count > 0:
            forms.alert(
                "Successfully imported data for {} elements from:\n{}".format(updated_count, os.path.basename(selected_file)),
                title="Import Successful"
            )
        else:
            forms.alert("No matching elements found in the current model for the selected JSON.", title="Import Failed")
    else:
        # If user cancels
        forms.toast("Operation cancelled.")

if __name__ == "__main__":
    run()
