# -*- coding: utf-8 -*-
"""Populate Pipe Parameters Nodo_Inicio and Nodo_final based on connected nodes."""

import sys
from pyrevit import revit, DB, UI, forms, script

doc = revit.doc
uidoc = revit.uidoc
logger = script.get_logger()

def is_node_element(elem):
    """Check if the element is a fitting, accessory, fixture, or equipment."""
    if not isinstance(elem, DB.FamilyInstance):
        return False
    cat = elem.Category
    if not cat:
        return False
    cat_id = cat.Id.IntegerValue
    # BuiltInCategory ids for relevant MEP categories
    valid_cats = [
        int(DB.BuiltInCategory.OST_PipeFitting),
        int(DB.BuiltInCategory.OST_PipeAccessory),
        int(DB.BuiltInCategory.OST_PlumbingFixtures),
        int(DB.BuiltInCategory.OST_PlumbingEquipment),
        int(DB.BuiltInCategory.OST_MechanicalEquipment)
    ]
    return cat_id in valid_cats

def get_node_number(elem, param_name):
    """Retrieve the node number value from the element."""
    param = elem.LookupParameter(param_name)
    if param:
        val = param.AsString()
        return val if val else ""
    return ""

def main():
    # 1. Configuration
    source_param = forms.ask_for_string(
        default="Node_Number", 
        prompt="Enter the source parameter name (on Fittings/Fixtures):", 
        title="Source Parameter"
    )
    if not source_param: return

    start_param_name = "Nodo_Inicio"
    end_param_name = "Nodo_Final"
    delta_z_param_name = "DeltaZ"
    cwfu_param_name = "GPC-CWFU"
    hwfu_param_name = "GPC-HWFU"

    # 2. Collect Pipes
    selection = uidoc.Selection.GetElementIds()
    if selection:
        pipes = [doc.GetElement(id) for id in selection 
                 if isinstance(doc.GetElement(id), (DB.Plumbing.Pipe, DB.Plumbing.FlexPipe))]
        if not pipes:
            forms.alert("No pipes found in selection.")
            return
    else:
        # Get all pipes and flex pipes in the active view
        from System.Collections.Generic import List
        cat_list = List[DB.ElementId]()
        cat_list.Add(DB.ElementId(DB.BuiltInCategory.OST_PipeCurves))
        cat_list.Add(DB.ElementId(DB.BuiltInCategory.OST_FlexPipeCurves))
        
        filter = DB.ElementMulticategoryFilter(cat_list)
        pipes = DB.FilteredElementCollector(doc, doc.ActiveView.Id) \
                  .WherePasses(filter) \
                  .WhereElementIsNotElementType() \
                  .ToElements()
        
        if not pipes:
            # Fallback to all pipes in project if active view collector is empty
            pipes = DB.FilteredElementCollector(doc) \
                      .WherePasses(filter) \
                      .WhereElementIsNotElementType() \
                      .ToElements()

    if not pipes:
        forms.alert("No pipes found in the project.")
        return

    # 3. Process Pipes
    t = DB.Transaction(doc, "Populate Pipe Nodes")
    t.Start()

    count = 0
    missing_params = set()

    for pipe in pipes:
        # Get connectors
        try:
            connectors = pipe.ConnectorManager.Connectors
        except Exception:
            continue

        # Sort connectors by location to maintain consistency (e.g., start/end)
        conns_list = []
        for c in connectors:
            conns_list.append(c)
        
        # Sort by X, then Y, then Z
        conns_list.sort(key=lambda c: (round(c.Origin.X, 4), round(c.Origin.Y, 4), round(c.Origin.Z, 4)))

        node_values = []
        total_cwfu = 0.0
        total_hwfu = 0.0

        for conn in conns_list:
            found_val = ""
            for ref in conn.AllRefs:
                if ref.Owner.Id == pipe.Id:
                    continue
                
                owner = ref.Owner
                if is_node_element(owner):
                    # Node Number
                    val = get_node_number(owner, source_param)
                    if val:
                        found_val = val
                    
                    # Fixture Units
                    p_cw = owner.LookupParameter(cwfu_param_name)
                    if p_cw: total_cwfu += p_cw.AsDouble()
                    
                    p_hw = owner.LookupParameter(hwfu_param_name)
                    if p_hw: total_hwfu += p_hw.AsDouble()
            
            node_values.append(found_val)

        # Fill up to 2 values
        while len(node_values) < 2:
            node_values.append("")

        # Assign to parameters
        p_start = pipe.LookupParameter(start_param_name)
        p_end = pipe.LookupParameter(end_param_name)
        p_delta_z = pipe.LookupParameter(delta_z_param_name)

        if not p_start: missing_params.add(start_param_name)
        if not p_end: missing_params.add(end_param_name)
        if not p_delta_z: missing_params.add(delta_z_param_name)

        updated = False
        if p_start and not p_start.IsReadOnly:
            p_start.Set(node_values[0])
            updated = True
        
        if p_end and not p_end.IsReadOnly:
            # If we have more than 2 connectors (unlikely for pipe curves), 
            # we take the last one as the 'end'.
            p_end.Set(node_values[-1])
            updated = True

        if p_delta_z and not p_delta_z.IsReadOnly:
            # DeltaZ = Z of Nodo_Inicio - Z of Nodo_Final
            # conns_list is sorted the same way node_values were populated
            z_start = conns_list[0].Origin.Z
            z_end = conns_list[-1].Origin.Z
            delta_z = z_start - z_end
            p_delta_z.Set(delta_z)
            updated = True

        # Assign Fixture Units
        p_cwfu = pipe.LookupParameter(cwfu_param_name)
        if p_cwfu and not p_cwfu.IsReadOnly:
            p_cwfu.Set(total_cwfu)
            updated = True
            
        p_hwfu = pipe.LookupParameter(hwfu_param_name)
        if p_hwfu and not p_hwfu.IsReadOnly:
            p_hwfu.Set(total_hwfu)
            updated = True

        if updated:
            count += 1

    t.Commit()

    # 4. Final Report
    if missing_params:
        forms.alert("Warning: The following parameters were missing on some pipes:\n" + 
                    "\n".join(missing_params), title="Missing Parameters")

    forms.alert("Successfully processed {} pipes.".format(count), title="Complete")

if __name__ == "__main__":
    main()
