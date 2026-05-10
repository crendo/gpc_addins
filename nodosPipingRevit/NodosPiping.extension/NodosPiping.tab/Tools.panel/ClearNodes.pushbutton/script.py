# -*- coding: utf-8 -*-
"""Clear Node Number parameter from all elements in the project.
"""

from pyrevit import revit, DB, forms, script

doc = revit.doc
logger = script.get_logger()

def main():
    # 1. Ask for Parameter Name
    param_name = forms.ask_for_string(
        default="Node_Number", 
        prompt="Enter the parameter name to clear from all nodes:", 
        title="Clear Node Numbers"
    )
    if not param_name:
        return

    # 2. Confirm Action
    if not forms.alert("This will clear node numbers, elevations, and fixture units from ALL pipes, fittings, accessories, equipment, and fixtures in the project.\n\nAre you sure you want to continue?", 
                       ok=True, 
                       cancel=True, 
                       title="Confirm Clear"):
        return

    # 3. Collect elements
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
    collector = DB.FilteredElementCollector(doc).WherePasses(filter).WhereElementIsNotElementType()

    # 4. Clear values in a transaction
    t = DB.Transaction(doc, "Clear Node Parameters")
    t.Start()
    
    params_to_clear = [
        param_name, 
        "Nodo_Inicio", 
        "Nodo_Final", 
        "DeltaZ", 
        "Elev_Node_Number",
        "GPC-CWFU",
        "GPC-HWFU"
    ]
    
    count = 0
    # Collect elements first to get count for progress bar
    elements = list(collector)
    total = len(elements)
    
    with forms.ProgressBar(title="Clearing node and equipment parameters...", total=total) as pb:
        for i, elem in enumerate(elements):
            element_updated = False
            for p_name in params_to_clear:
                param = elem.LookupParameter(p_name)
                if param and not param.IsReadOnly:
                    # Check storage type and clear accordingly
                    if param.StorageType == DB.StorageType.String:
                        val = param.AsString()
                        if val and val.strip():
                            param.Set("")
                            element_updated = True
                    elif param.StorageType == DB.StorageType.Double:
                        val = param.AsDouble()
                        if abs(val) > 0.0001: # Check if it's effectively non-zero
                            param.Set(0.0)
                            element_updated = True
                    elif param.StorageType == DB.StorageType.Integer:
                        val = param.AsInteger()
                        if val != 0:
                            param.Set(0)
                            element_updated = True
            
            if element_updated:
                count += 1
            pb.update_progress(i + 1, total)
                
    t.Commit()
    
    forms.alert("Successfully cleared {} elements.".format(count), title="Complete")

if __name__ == '__main__':
    main()
