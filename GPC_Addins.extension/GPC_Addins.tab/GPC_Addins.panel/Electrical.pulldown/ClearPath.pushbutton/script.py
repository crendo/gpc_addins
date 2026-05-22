# -*- coding: utf-8 -*-
"""Clear all conduit path graphic overrides in the active view."""

from pyrevit import revit, DB, UI, forms

doc = revit.doc
active_view = doc.ActiveView

def main():
    # 1. Collect all Conduits and Conduit Fittings in the active view
    from System.Collections.Generic import List
    cats = [
        DB.BuiltInCategory.OST_Conduit,
        DB.BuiltInCategory.OST_ConduitFitting
    ]
    cat_list = List[DB.ElementId]()
    for c in cats:
        cat_list.Add(DB.ElementId(c))
        
    filter = DB.ElementMulticategoryFilter(cat_list)
    collector = DB.FilteredElementCollector(doc, active_view.Id)\
                  .WherePasses(filter)\
                  .WhereElementIsNotElementType()

    # 2. Reset overrides in a Revit Transaction
    t = DB.Transaction(doc, "Clear Conduit Path Highlights")
    t.Start()
    
    # An empty OverrideGraphicSettings resets the overrides to default
    reset_override = DB.OverrideGraphicSettings()
    
    count = 0
    for elem in collector:
        active_view.SetElementOverrides(elem.Id, reset_override)
        count += 1
        
    t.Commit()
    
    forms.alert(
        "Conduit path highlights cleared successfully!\n\n"
        "Reset elements in active view: {}".format(count), 
        title="Highlights Cleared"
    )

if __name__ == '__main__':
    main()
