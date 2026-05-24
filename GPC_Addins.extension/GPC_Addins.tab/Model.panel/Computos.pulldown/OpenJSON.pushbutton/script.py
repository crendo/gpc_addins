"""Open the quantity data JSON database file in the default viewer."""

__title__ = 'Open\nJSON'
__author__ = 'Computos Revit Team'

from pyrevit import revit, DB, forms
import os
import sys

# Library paths are handled automatically by pyRevit

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

