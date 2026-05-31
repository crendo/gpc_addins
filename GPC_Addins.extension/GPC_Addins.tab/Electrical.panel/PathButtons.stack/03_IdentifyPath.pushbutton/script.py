# -*- coding: utf-8 -*-
"""Identify and highlight the physical conduit path between two selected points."""

import sys
import os.path as op
import json
from pyrevit import revit, DB, UI, forms, script

import clr
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")
clr.AddReference("System")

import System.Windows as Windows
import System.Windows.Controls as Controls
import System.Windows.Media as Media
import System.Windows.Shapes as Shapes

COLORS_LIST = [
    {"Name": "Amber / Orange", "Color": DB.Color(255, 128, 0), "Hex": "#FF8000"},
    {"Name": "Red", "Color": DB.Color(255, 0, 0), "Hex": "#FF0000"},
    {"Name": "Green", "Color": DB.Color(0, 180, 0), "Hex": "#00B400"},
    {"Name": "Blue", "Color": DB.Color(0, 120, 255), "Hex": "#0078FF"},
    {"Name": "Magenta", "Color": DB.Color(255, 0, 255), "Hex": "#FF00FF"},
    {"Name": "Purple", "Color": DB.Color(128, 0, 128), "Hex": "#800080"},
    {"Name": "Cyan", "Color": DB.Color(0, 255, 255), "Hex": "#00FFFF"},
    {"Name": "Lime", "Color": DB.Color(50, 205, 50), "Hex": "#32CD32"},
    {"Name": "Hot Pink", "Color": DB.Color(255, 105, 180), "Hex": "#FF69B4"}
]

class PathSettingsWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        self.selected_color = DB.Color(255, 128, 0)
        self.selected_weight = 8
        self.dialog_result = False
        
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Populate Color dropdown with visual colors
        self.populate_colors()
        
        # Load last used settings
        self.load_settings()
        
        # Attach event handlers
        self.sliderWeight.ValueChanged += self.slider_changed
        self.lblWeightVal.Text = str(int(self.sliderWeight.Value))

    def populate_colors(self):
        for c in COLORS_LIST:
            panel = Controls.StackPanel()
            panel.Orientation = Controls.Orientation.Horizontal
            panel.Height = 24
            
            # Rect
            rect = Shapes.Rectangle()
            rect.Width = 18
            rect.Height = 14
            rect.Margin = Windows.Thickness(2, 5, 10, 5)
            rect.Fill = Media.BrushConverter().ConvertFromString(c["Hex"])
            rect.RadiusX = 2
            rect.RadiusY = 2
            
            # Text
            lbl = Controls.TextBlock()
            lbl.Text = c["Name"]
            lbl.VerticalAlignment = Windows.VerticalAlignment.Center
            lbl.Foreground = Media.BrushConverter().ConvertFromString("#1E293B")
            
            panel.Children.Add(rect)
            panel.Children.Add(lbl)
            
            self.cbColor.Items.Add(panel)

    def load_settings(self):
        # Locate shared_parameters directory (5 levels up from this script directory inside a .stack bundle)
        _root = script_dir
        for _ in range(5):
            _root = op.dirname(_root)
        
        shared_params_dir = op.join(_root, "shared_parameters")
        settings_path = op.join(shared_params_dir, "last_used_path_settings.json")
        
        default_color_idx = 0
        default_weight = 8
        
        if op.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                if isinstance(settings, dict):
                    color_name = settings.get("color_name")
                    for idx, c in enumerate(COLORS_LIST):
                        if c["Name"] == color_name:
                            default_color_idx = idx
                            break
                    default_weight = int(settings.get("line_weight", 8))
            except Exception:
                pass
                
        self.cbColor.SelectedIndex = default_color_idx
        self.sliderWeight.Value = default_weight

    def save_settings(self, color_name, weight):
        # Locate shared_parameters directory (5 levels up from this script directory inside a .stack bundle)
        _root = script_dir
        for _ in range(5):
            _root = op.dirname(_root)
        
        shared_params_dir = op.join(_root, "shared_parameters")
        settings_path = op.join(shared_params_dir, "last_used_path_settings.json")
        
        try:
            if not op.exists(shared_params_dir):
                os.makedirs(shared_params_dir)
            
            settings = {
                "color_name": color_name,
                "line_weight": weight
            }
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception:
            pass

    def slider_changed(self, sender, e):
        if hasattr(self, 'lblWeightVal') and self.lblWeightVal:
            self.lblWeightVal.Text = str(int(self.sliderWeight.Value))

    def Cancel_Click(self, sender, e):
        self.dialog_result = False
        self.Close()

    def Highlight_Click(self, sender, e):
        idx = self.cbColor.SelectedIndex
        if idx >= 0 and idx < len(COLORS_LIST):
            self.selected_color = COLORS_LIST[idx]["Color"]
            color_name = COLORS_LIST[idx]["Name"]
        else:
            self.selected_color = DB.Color(255, 128, 0)
            color_name = "Amber / Orange"
            
        self.selected_weight = int(self.sliderWeight.Value)
        
        # Save to history
        self.save_settings(color_name, self.selected_weight)
        
        self.dialog_result = True
        self.Close()

script_dir = op.dirname(op.abspath(__file__))

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

def find_shortest_path_bfs(start_elem, end_elem):
    """Finds the shortest conduit path from start to end using direct connector BFS.
    Runs instantaneously in pure Python.
    """
    start_id = start_elem.Id.IntegerValue
    end_id = end_elem.Id.IntegerValue
    
    # Queue stores tuples of (current_element, path_of_ids_taken)
    queue = [(start_elem, [start_id])]
    visited = {start_id}
    
    while queue:
        curr_elem, path = queue.pop(0)
        curr_id = curr_elem.Id.IntegerValue
        
        if curr_id == end_id:
            return path
            
        conns = get_connectors(curr_elem)
        for conn in conns:
            for ref_conn in conn.AllRefs:
                owner = ref_conn.Owner
                if owner.Id.IntegerValue == curr_id:
                    continue
                # Ensure the connected element is a Conduit or Conduit Fitting
                if owner.Category:
                    cat_id = owner.Category.Id.IntegerValue
                    if cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]:
                        owner_id = owner.Id.IntegerValue
                        if owner_id not in visited:
                            visited.add(owner_id)
                            queue.append((owner, path + [owner_id]))
    return None

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

    # 3. Find Shortest Path using BFS
    with forms.ProgressBar(title="Searching conduit path...", indeterminate=True) as pb:
        path_node_ids = find_shortest_path_bfs(start_elem, end_elem)

    if not path_node_ids:
        forms.alert(
            "The selected END element is not connected to the START element's physical run.\n\n"
            "Please ensure they are physically connected by junctions or fittings.",
            title="Elements Disconnected"
        )
        return

    # 4.5 Launch Settings Dialog to select color and line weight
    xaml_file = op.join(script_dir, "ui.xaml")
    win = PathSettingsWindow(xaml_file)
    win.ShowDialog()
    
    if not win.dialog_result:
        # User closed or clicked cancel
        return
        
    path_color = win.selected_color
    path_weight = win.selected_weight

    # 5. Highlight Identified Path in Active View and select elements in Revit UI
    t = DB.Transaction(doc, "Highlight Conduit Path")
    t.Start()
    
    override = DB.OverrideGraphicSettings()
    override.SetProjectionLineColor(path_color)
    override.SetProjectionLineWeight(path_weight)
    
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
        "You can now immediately click 'Manage Cables' to configure their circuits.".format(count),
        title="Path Selected"
    )

if __name__ == "__main__":
    main()
