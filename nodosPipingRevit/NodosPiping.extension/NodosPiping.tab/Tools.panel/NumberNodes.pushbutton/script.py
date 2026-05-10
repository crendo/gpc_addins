# -*- coding: utf-8 -*-
"""Number Nodes in a Piping System using DFS traversal.
User manually selects a starting pipe, then the app uses the system classification type 
and name that the selected pipe belongs to, performing a Depth-First Search to number nodes.
"""

import sys
import re
import os
import os.path as op

# Add lib directory to sys.path
script_dir = op.dirname(__file__)
extension_dir = op.dirname(op.dirname(op.dirname(script_dir)))
lib_dir = op.join(extension_dir, 'lib')
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

import networkx as nx

from pyrevit import revit, DB, UI, forms, script

doc = revit.doc
uidoc = revit.uidoc
logger = script.get_logger()

def get_connectors(elem):
    """Safely get connectors from an element."""
    conn_mgr = None
    if hasattr(elem, 'ConnectorManager'):
        conn_mgr = elem.ConnectorManager
    elif hasattr(elem, 'MEPModel') and elem.MEPModel:
        conn_mgr = elem.MEPModel.ConnectorManager
    
    if conn_mgr:
        return [c for c in conn_mgr.Connectors if c.IsConnected and c.ConnectorType != DB.ConnectorType.Logical]
    return []

def build_graph(system_elements):
    """Builds a networkx Graph from a list of Revit elements."""
    G = nx.Graph()
    
    # Add nodes
    for elem in system_elements:
        G.add_node(elem.Id.IntegerValue)
        
    # Add edges
    for elem in system_elements:
        conns = get_connectors(elem)
        for conn in conns:
            for ref_conn in conn.AllRefs:
                if ref_conn.Owner.Id == elem.Id:
                    continue
                if ref_conn.Owner.Id.IntegerValue in G.nodes:
                    G.add_edge(elem.Id.IntegerValue, ref_conn.Owner.Id.IntegerValue)
                    
    return G

def is_node_element(elem):
    """Check if the element is a fitting, accessory, or equipment (should be numbered)."""
    if not isinstance(elem, DB.FamilyInstance):
        return False
    cat = elem.Category
    if not cat:
        return False
    cat_id = cat.Id.IntegerValue
    # BuiltInCategory.OST_PipeFitting, OST_PipeAccessory, OST_PlumbingFixtures, OST_PlumbingEquipment, OST_MechanicalEquipment, OST_Sprinklers
    valid_cats = [
        int(DB.BuiltInCategory.OST_PipeFitting),
        int(DB.BuiltInCategory.OST_PipeAccessory),
        int(DB.BuiltInCategory.OST_PlumbingFixtures),
        int(DB.BuiltInCategory.OST_PlumbingEquipment),
        int(DB.BuiltInCategory.OST_MechanicalEquipment)
    ]
    return cat_id in valid_cats

def get_next_available_number(doc, param_name, prefix):
    """Finds the highest number already assigned with the given prefix in the project."""
    cats = [
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
    
    highest = 0
    found = False
    for elem in collector:
        param = elem.LookupParameter(param_name)
        if param:
            val = param.AsString()
            if val and val.startswith(prefix):
                # Use regex to find the first sequence of digits after the prefix
                suffix = val[len(prefix):]
                match = re.search(r'(\d+)', suffix)
                if match:
                    try:
                        num = int(match.group(1))
                        if num > highest:
                            highest = num
                            found = True
                    except (ValueError, TypeError):
                        continue
    return highest + 1 if found else 1

def main():
    # 1. Prompt for User Inputs
    param_name = forms.ask_for_string(default="Node_Number", prompt="Enter parameter name to write to:", title="Parameter Name")
    if not param_name: sys.exit()

    prefix = forms.ask_for_string(default="N-", prompt="Enter numbering prefix:", title="Prefix")
    if prefix is None: sys.exit()

    # Calculate suggested start number
    with forms.ProgressBar(title="Finding next available number...", indeterminate=True) as pb:
        suggested_start = get_next_available_number(doc, param_name, prefix)

    start_num_str = forms.ask_for_string(default=str(suggested_start), prompt="Enter start number:", title="Start Number")
    if start_num_str is None: sys.exit()
    try:
        start_num = int(start_num_str)
    except ValueError:
        forms.alert("Start number must be an integer.")
        sys.exit()

    # 2. Select Starting Pipe
    with forms.WarningBar(title="Pick the starting Pipe to determine the system and root node"):
        try:
            ref = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, "Select the starting pipe")
            start_pipe = doc.GetElement(ref)
        except Exception:
            sys.exit() # User canceled
            
    if not isinstance(start_pipe, (DB.Plumbing.Pipe, DB.Plumbing.FlexPipe)):
        forms.alert("Please select a Pipe element.")
        sys.exit()
        
    system = start_pipe.MEPSystem
    if not system:
        forms.alert("The selected pipe does not belong to a system.")
        sys.exit()

    sys_name = getattr(system, "Name", "Unknown")
    sys_type_elem = system.Document.GetElement(system.GetTypeId()) if hasattr(system, "GetTypeId") else None
    sys_type_name = getattr(sys_type_elem, "Name", "Unknown") if sys_type_elem else "Unknown"


    # 3. Build Graph
    from System.Collections.Generic import List
    cats = [
        DB.BuiltInCategory.OST_PipeCurves,
        DB.BuiltInCategory.OST_FlexPipeCurves,
        DB.BuiltInCategory.OST_PipeFitting,
        DB.BuiltInCategory.OST_PipeAccessory,
        DB.BuiltInCategory.OST_PlumbingFixtures,
        DB.BuiltInCategory.OST_PlumbingEquipment,
        DB.BuiltInCategory.OST_MechanicalEquipment
    ]
    cat_list = List[DB.ElementId]()
    for c in cats:
        cat_list.Add(DB.ElementId(c))
    
    filter = DB.ElementMulticategoryFilter(cat_list)
    collector = DB.FilteredElementCollector(doc).WherePasses(filter).WhereElementIsNotElementType()
    
    system_elements = []
    for elem in collector:
        param = elem.get_Parameter(DB.BuiltInParameter.RBS_SYSTEM_NAME_PARAM)
        if param:
            val = param.AsString()
            if val:
                sys_names = [s.strip() for s in val.split(',')]
                if sys_name in sys_names:
                    system_elements.append(elem)
    
    if start_pipe.Id.IntegerValue not in [e.Id.IntegerValue for e in system_elements]:
        system_elements.append(start_pipe)

    G = build_graph(system_elements)
    
    if start_pipe.Id.IntegerValue not in G:
        forms.alert("Start pipe is not in the built graph.")
        sys.exit()

    # 4. Perform DFS
    # source is the selected pipe
    dfs_nodes = list(nx.dfs_preorder_nodes(G, source=start_pipe.Id.IntegerValue))

    # 5. Number the Nodes
    elements_to_number = []
    for node_id in dfs_nodes:
        elem = doc.GetElement(DB.ElementId(node_id))
        if is_node_element(elem):
            elements_to_number.append(elem)

    if not elements_to_number:
        forms.alert("No fittings, accessories, or equipment found in this system.")
        sys.exit()

    # 6. Write to Parameter
    t = DB.Transaction(doc, "Number Piping Nodes")
    t.Start()
    
    count = 0
    skipped = 0
    for i, elem in enumerate(elements_to_number):
        # Always update elevation if parameter exists
        elev_param = elem.LookupParameter("Elev_Node_Number")
        if elev_param and not elev_param.IsReadOnly:
            loc = elem.Location
            if isinstance(loc, DB.LocationPoint):
                z_val = loc.Point.Z
                elev_param.Set(z_val)

        # Update Node Number only if it doesn't have a value
        param = elem.LookupParameter(param_name)
        if param and not param.IsReadOnly:
            # Check if parameter already has a value to avoid overwriting
            existing_value = param.AsString()
            if existing_value and existing_value.strip():
                skipped += 1
                continue
                
            value = "{}{}".format(prefix, start_num + i)
            param.Set(value)
            count += 1
        else:
            logger.warning("Element {} does not have writable parameter '{}'".format(elem.Id, param_name))

    t.Commit()
    
    msg = "Successfully numbered {} nodes.".format(count)
    if skipped > 0:
        msg += "\n{} nodes already had values and were skipped.".format(skipped)
    
    forms.alert(msg, title="Complete")

if __name__ == '__main__':
    main()
