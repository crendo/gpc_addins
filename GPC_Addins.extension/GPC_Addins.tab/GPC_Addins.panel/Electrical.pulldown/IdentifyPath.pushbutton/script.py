# -*- coding: utf-8 -*-
"""Identify and highlight the physical conduit path between two selected points."""

import sys
import os.path as op
from pyrevit import revit, DB, UI, forms, script

# Add lib directory to sys.path to find networkx
script_dir = op.dirname(__file__)
extension_dir = op.dirname(op.dirname(op.dirname(op.dirname(script_dir))))
lib_dir = op.join(extension_dir, 'lib')
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

try:
    import networkx as nx
except ImportError:
    forms.alert("networkx library not found in {}".format(lib_dir))
    sys.exit()

doc = revit.doc
uidoc = revit.uidoc
logger = script.get_logger()

class ConduitSelectionFilter(UI.Selection.ISelectionFilter):
    def AllowElement(self, element):
        if not element or not element.Category:
            return False
        cat_id = element.Category.Id.IntegerValue
        return cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]
        
    def AllowReference(self, reference, point):
        return False

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

def get_connected_conduit_elements(start_element):
    """Traverse physical connectors starting from start_element to find all connected conduits and fittings."""
    visited = set()
    to_visit = [start_element.Id]
    elements = {start_element.Id.IntegerValue: start_element}
    
    while to_visit:
        curr_id = to_visit.pop(0)
        curr_val = curr_id.IntegerValue
        if curr_val in visited:
            continue
        visited.add(curr_val)
        
        curr_elem = elements[curr_val]
        conns = get_connectors(curr_elem)
        for conn in conns:
            for ref_conn in conn.AllRefs:
                owner = ref_conn.Owner
                if owner.Id == curr_id:
                    continue
                # Ensure the connected element is a Conduit or Conduit Fitting
                if owner.Category:
                    cat_id = owner.Category.Id.IntegerValue
                    if cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]:
                        owner_val = owner.Id.IntegerValue
                        if owner_val not in elements:
                            elements[owner_val] = owner
                            to_visit.append(owner.Id)
                            
    return list(elements.values())

def build_graph(elements_list):
    """Builds an undirected networkx Graph representing physical connections."""
    G = nx.Graph()
    for elem in elements_list:
        G.add_node(elem.Id.IntegerValue)
        
    for elem in elements_list:
        conns = get_connectors(elem)
        for conn in conns:
            for ref_conn in conn.AllRefs:
                owner = ref_conn.Owner
                if owner.Id == elem.Id:
                    continue
                if owner.Id.IntegerValue in G.nodes:
                    G.add_edge(elem.Id.IntegerValue, owner.Id.IntegerValue)
    return G

def main():
    sel_filter = ConduitSelectionFilter()

    # 1. Select Start Conduit
    with forms.WarningBar(title="Select the START Conduit or Fitting"):
        try:
            ref_start = uidoc.Selection.PickObject(
                UI.Selection.ObjectType.Element, 
                sel_filter, 
                "Select starting conduit or fitting"
            )
            start_elem = doc.GetElement(ref_start)
        except Exception:
            # User cancelled selection
            return

    # 2. Select End Conduit
    with forms.WarningBar(title="Select the END Conduit or Fitting to define the path"):
        try:
            ref_end = uidoc.Selection.PickObject(
                UI.Selection.ObjectType.Element, 
                sel_filter, 
                "Select ending conduit or fitting"
            )
            end_elem = doc.GetElement(ref_end)
        except Exception:
            # User cancelled selection
            return

    if start_elem.Id.IntegerValue == end_elem.Id.IntegerValue:
        forms.alert("Start and End elements are the same conduit/fitting.", title="Same Element")
        return

    # 3. Build Connected Conduit Network Graph
    with forms.ProgressBar(title="Traversing conduit network...", indeterminate=True) as pb:
        # Traverse from the start element to find all physically connected components
        connected_elements = get_connected_conduit_elements(start_elem)
        G = build_graph(connected_elements)

    if end_elem.Id.IntegerValue not in G:
        forms.alert(
            "The selected END element is not connected to the START element's physical run.\n\n"
            "Please ensure they are physically connected by junctions or fittings.",
            title="Elements Disconnected"
        )
        return

    # 4. Find Shortest Path
    try:
        path_node_ids = nx.shortest_path(G, source=start_elem.Id.IntegerValue, target=end_elem.Id.IntegerValue)
    except nx.NetworkXNoPath:
        forms.alert("No connected path found between these two elements.", title="No Path Found")
        return

    # 5. Highlight Identified Path in Active View and select elements in Revit UI
    t = DB.Transaction(doc, "Highlight Conduit Path")
    t.Start()
    
    amber = DB.Color(255, 128, 0)
    override = DB.OverrideGraphicSettings()
    override.SetProjectionLineColor(amber)
    override.SetProjectionLineWeight(8)
    
    from System.Collections.Generic import List
    selection_ids = List[DB.ElementId]()
    
    count = 0
    for node_id in path_node_ids:
        eid = DB.ElementId(node_id)
        doc.ActiveView.SetElementOverrides(eid, override)
        selection_ids.Add(eid)
        count += 1
        
    t.Commit()
    
    # Programmatically select the elements along the identified path
    uidoc.Selection.SetElementIds(selection_ids)
    
    forms.alert(
        "Conduit path successfully identified, highlighted, and selected!\n\n"
        "Total elements: {}\n\n"
        "You can now immediately click 'Manage Cables' to configure their circuits.",
        title="Path Selected"
    )

if __name__ == "__main__":
    main()
