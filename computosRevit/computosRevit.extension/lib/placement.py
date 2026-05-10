"""Helper to place family instances."""
from pyrevit import revit, DB, forms

def place_gpc_instance(family_name):
    """
    Finds a family by name and initiates the interactive placement process.
    Returns True if placement started, False otherwise.
    """
    doc = revit.doc
    uidoc = revit.uidoc
    
    # 1. Optimized Family Lookup
    # Using a generator expression is much faster in large projects
    collector = DB.FilteredElementCollector(doc).OfClass(DB.Family)
    family = next((f for f in collector if f.Name == family_name), None)
            
    if not family:
        forms.alert(
            "Family '{}' not found in project.\n"
            "Ensure the family is loaded and the name matches exactly.".format(family_name), 
            title="Family Missing"
        )
        return False
        
    # 2. Get Family Symbols (Types)
    symbol_ids = family.GetFamilySymbolIds()
    if not symbol_ids:
        forms.alert("Family '{}' contains no loaded types (symbols).".format(family_name))
        return False
        
    # We'll pick the first available symbol
    symbol_id = list(symbol_ids)[0]
    symbol = doc.GetElement(symbol_id)
    
    # 3. Ensure Symbol is Active
    if not symbol.IsActive:
        try:
            # Using get_Parameter for more robust name access in IronPython
            symbol_name = symbol.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()
            with revit.Transaction("Activate Symbol: {}".format(symbol_name)):
                symbol.Activate()
        except Exception as e:
            try:
                symbol_name = symbol.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()
            except:
                symbol_name = "Unknown"
            forms.alert("Failed to activate type '{}': {}".format(symbol_name, str(e)))
            return False
            
    # 4. Execute Placement
    try:
        # This triggers the Revit UI for placement
        uidoc.PromptForFamilyInstancePlacement(symbol)
        return True
    except Exception:
        # If the user hits 'Esc' or 'Cancel', Revit throws an error.
        # We catch it here so the script finishes cleanly.
        return False
