"""Manual Sync for all project elements with GPC Parameters."""

__title__ = 'Sync\nAll'
__author__ = 'Computos Revit Team'

from pyrevit import revit, DB, forms
import os
import sys

# Library paths are handled automatically by pyRevit

import database
import sync

def run():
    doc = revit.doc
    
    # 1. Initialize Database
    db_path = database.get_db_path(doc)
    # 2. Get Store
    store = database.get_store(db_path)
    
    # 3. Collect ALL Model Elements
    # Use a more robust collector to find all elements with GPC parameters
    # This ensures DirectShapes and other View-Independent instances are included
    all_elements = DB.FilteredElementCollector(doc).WhereElementIsNotElementType()
    
    elements_with_gpc = []
    # Using an explicit check to find anything with GPC parameters
    for el in all_elements:
        p_qty = el.LookupParameter("GPC-Cantidad")
        if not p_qty:
            # Robust fallback for atypical elements
            for p in el.Parameters:
                if p.Definition and p.Definition.Name == "GPC-Cantidad":
                    p_qty = p
                    break
        
        if p_qty:
            elements_with_gpc.append(el)
            
    if not elements_with_gpc:
        forms.alert("No elements with 'GPC-Cantidad' found. Try Running 'Setup Parameters' or creating elements first.", title="No Elements Found")
        return
        
    # 4. Synchronize
    with revit.Transaction("GPC Manual Sync All"):
        synced_count = sync.sync_elements(doc, elements_with_gpc, store, show_progress=True)
        
    forms.toast("Synchronized {} elements with the DataStore.".format(synced_count))

if __name__ == "__main__":
    run()

