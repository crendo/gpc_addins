# -*- coding: utf-8 -*-
"""Identify a specific path/branch between two points using the system graph."""

import sys
import os.path as op
from pyrevit import revit, DB, UI, forms, script

# Add lib directory to sys.path to find networkx
script_dir = op.dirname(__file__)
extension_dir = op.dirname(op.dirname(op.dirname(script_dir)))
lib_dir = op.join(extension_dir, 'lib')
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

nx = None

def get_nx():
    global nx
    if nx is None:
        try:
            import networkx as nx
        except ImportError:
            forms.alert("networkx library not found in {}".format(lib_dir))
            sys.exit()
    return nx

doc = revit.doc
uidoc = revit.uidoc
logger = script.get_logger()

def get_connectors(elem):
    """Safely get connected connectors from an element."""
    conn_mgr = None
    if hasattr(elem, 'ConnectorManager'):
        conn_mgr = elem.ConnectorManager
    elif hasattr(elem, 'MEPModel') and elem.MEPModel:
        conn_mgr = elem.MEPModel.ConnectorManager
    
    if conn_mgr:
        valid_conns = []
        for c in conn_mgr.Connectors:
            try:
                if c.ConnectorType != DB.ConnectorType.Logical and c.IsConnected:
                    valid_conns.append(c)
            except Exception:
                continue
        return valid_conns
    return []

def build_graph(system_elements):
    """Builds a networkx Graph from a list of Revit elements."""
    nx = get_nx()
    G = nx.Graph()
    for elem in system_elements:
        G.add_node(elem.Id.IntegerValue)
        
    for elem in system_elements:
        conns = get_connectors(elem)
        for conn in conns:
            for ref_conn in conn.AllRefs:
                if ref_conn.Owner.Id == elem.Id:
                    continue
                if ref_conn.Owner.Id.IntegerValue in G.nodes:
                    G.add_edge(elem.Id.IntegerValue, ref_conn.Owner.Id.IntegerValue)
    return G

def get_element_system_names(elem):
    """Gets all MEP system names associated with the element."""
    system_names = set()
    
    # 1. Try MEPSystem property (for MEPCurves like Pipes)
    if hasattr(elem, 'MEPSystem') and elem.MEPSystem:
        sys_name = getattr(elem.MEPSystem, "Name", "")
        if sys_name:
            system_names.add(sys_name)
            
    # 2. Try RBS_SYSTEM_NAME_PARAM parameter (standard for MEP components)
    param = elem.get_Parameter(DB.BuiltInParameter.RBS_SYSTEM_NAME_PARAM)
    if param:
        val = param.AsString()
        if val:
            for s in val.split(','):
                s_clean = s.strip()
                if s_clean:
                    system_names.add(s_clean)
                    
    # 3. Try connectors
    conns = get_connectors(elem)
    for conn in conns:
        try:
            if conn.MEPSystem:
                sys_name = getattr(conn.MEPSystem, "Name", "")
                if sys_name:
                    system_names.add(sys_name)
        except Exception:
            continue
            
    return list(system_names)

def get_system_elements(start_pipe):
    """Collect all elements belonging to the same system as the start pipe."""
    sys_names = get_element_system_names(start_pipe)
    if not sys_names:
        return [start_pipe]
    
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
                elem_sys_names = [s.strip() for s in val.split(',')]
                if any(name in elem_sys_names for name in sys_names):
                    system_elements.append(elem)
                
    if start_pipe.Id.IntegerValue not in [e.Id.IntegerValue for e in system_elements]:
        system_elements.append(start_pipe)
        
    return system_elements

def main():
    # 1. Select Start Pipe
    with forms.WarningBar(title="Select the START pipe"):
        try:
            ref_start = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, "Select start pipe")
            start_pipe = doc.GetElement(ref_start)
        except Exception:
            return

    # 2. Select End Pipe
    with forms.WarningBar(title="Select the END pipe (or fixture) to define the path"):
        try:
            ref_end = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, "Select end pipe/fixture")
            end_elem = doc.GetElement(ref_end)
        except Exception:
            return

    # 3. Build System Graph
    with forms.ProgressBar(title="Building system graph...", indeterminate=True) as pb:
        system_elements = get_system_elements(start_pipe)
        G = build_graph(system_elements)

    if start_pipe.Id.IntegerValue not in G or end_elem.Id.IntegerValue not in G:
        forms.alert("One of the selected elements is not part of the same system or is not connected.")
        return

    # 4. Find Path
    try:
        nx = get_nx()
        path_node_ids = nx.shortest_path(G, source=start_pipe.Id.IntegerValue, target=end_elem.Id.IntegerValue)
    except nx.NetworkXNoPath:
        forms.alert("No connected path found between these two elements.")
        return

    # 5. Apply Overrides
    t = DB.Transaction(doc, "Highlight Identified Path")
    t.Start()
    
    magenta = DB.Color(255, 0, 255)
    override = DB.OverrideGraphicSettings()
    override.SetProjectionLineColor(magenta)
    override.SetProjectionLineWeight(8)
    
    count = 0
    for node_id in path_node_ids:
        eid = DB.ElementId(node_id)
        doc.ActiveView.SetElementOverrides(eid, override)
        count += 1
        
    t.Commit()
    
    forms.alert("Path identified and highlighted.\nElements in path: {}".format(count))

if __name__ == "__main__":
    main()
