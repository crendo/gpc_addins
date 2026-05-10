"""Save quantity data from model to JSON database."""
__title__ = 'Save\nJSON'
from pyrevit import revit, DB, forms
import os
import sys

EXTENSION_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIB_PATH = os.path.join(EXTENSION_DIR, "lib")
if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

import database
import sync

doc = revit.doc
db_path = database.get_db_path(doc)

if not database.init_db(db_path):
    forms.alert("Error: Database initialization failed.")
    sys.exit()

store = database.get_store(db_path)

# Collect all valid elements
collector = DB.FilteredElementCollector(doc).WhereElementIsNotElementType()
all_elements = collector.ToElements()
elements_to_sync = []

for el in all_elements:
    if not el.Category: continue
    elements_to_sync.append(el)

with revit.Transaction("Sync and Save to JSON"):
    synced_count = sync.sync_elements(doc, elements_to_sync, store, show_progress=True, auto_save=True)

forms.alert("Successfully gathered {} elements and saved to {}.".format(synced_count, os.path.basename(db_path)), title="Save JSON Successful")
