# -*- coding: utf-8 -*-
"""Shared family loading utilities."""
import os
from pyrevit import revit, DB

def load_gpc_families(doc):
    """
    Loads all families from the centralized shared_parameters/families directory.
    This file is expected to be in shared_parameters/lib/
    """
    # this file: .../shared_parameters/lib/families.py
    lib_dir = os.path.dirname(os.path.abspath(__file__))
    sp_dir = os.path.dirname(lib_dir)
    families_dir = os.path.join(sp_dir, "families")
    
    if not os.path.isdir(families_dir):
        return 0

    family_files = [f for f in os.listdir(families_dir) if f.lower().endswith('.rfa')]
    
    loaded_count = 0
    # Collect existing families to avoid redundant loading
    existing_families = {f.Name for f in DB.FilteredElementCollector(doc).OfClass(DB.Family)}
    
    # Check if we are already in a transaction
    has_transaction = doc.IsModifiable
    
    if not has_transaction:
        t = DB.Transaction(doc, "Load GPC Families")
        t.Start()
        
    try:
        for f_file in family_files:
            f_name = f_file[:-4] # Remove .rfa
            if f_name in existing_families:
                continue
                
            f_path = os.path.join(families_dir, f_file)
            try:
                if doc.LoadFamily(f_path):
                    loaded_count += 1
            except Exception as e:
                print("Could not load family {}: {}".format(f_name, e))
        
        if not has_transaction:
            t.Commit()
    except Exception as e:
        if not has_transaction:
            t.RollBack()
        raise e
                    
    return loaded_count
