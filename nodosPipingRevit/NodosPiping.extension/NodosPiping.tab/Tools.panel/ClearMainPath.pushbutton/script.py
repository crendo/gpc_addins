# -*- coding: utf-8 -*-
"""Reset graphic overrides in the current view."""

from pyrevit import revit, DB, forms

doc = revit.doc

def reset_overrides():
    """Clear all graphic overrides for MEP categories in the active view."""
    cats = [
        DB.BuiltInCategory.OST_PipeCurves,
        DB.BuiltInCategory.OST_FlexPipeCurves,
        DB.BuiltInCategory.OST_PipeFitting,
        DB.BuiltInCategory.OST_PipeAccessory,
        DB.BuiltInCategory.OST_PlumbingFixtures,
        DB.BuiltInCategory.OST_PlumbingEquipment,
        DB.BuiltInCategory.OST_MechanicalEquipment
    ]
    
    from System.Collections.Generic import List
    cat_list = List[DB.ElementId]()
    for c in cats:
        cat_list.Add(DB.ElementId(c))
    
    filter = DB.ElementMulticategoryFilter(cat_list)
    # Only collect elements in the active view to keep it fast
    elements = DB.FilteredElementCollector(doc, doc.ActiveView.Id) \
                  .WherePasses(filter) \
                  .WhereElementIsNotElementType() \
                  .ToElements()
    
    if not elements:
        forms.alert("No elements found to reset in the active view.")
        return

    t = DB.Transaction(doc, "Reset Main Path Highlighting")
    t.Start()
    
    empty_override = DB.OverrideGraphicSettings()
    for elem in elements:
        # Resetting the override to default
        doc.ActiveView.SetElementOverrides(elem.Id, empty_override)
        
    t.Commit()
    forms.alert("Main Path highlighting has been cleared.")

if __name__ == "__main__":
    reset_overrides()
