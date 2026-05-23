# -*- coding: utf-8 -*-
"""Verify the cable fill capacity of a single selected conduit or pipe element against NEC limits."""

__title__ = 'Verify Conduit\nSize'
__author__ = 'Electrical Team'

import os
import json
import math
import clr  # type: ignore

# Load .NET assemblies for WPF
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")
clr.AddReference("System")

import System.Windows as Windows  # type: ignore
import System.Windows.Controls as Controls  # type: ignore
import System.Windows.Media as Media  # type: ignore
from pyrevit import revit, DB, UI, forms, script  # type: ignore

doc = revit.doc
uidoc = revit.uidoc

# --- Fallback Cable Areas ---
DEFAULT_CABLE_AREAS = {
    "#14 AWG": 0.0097,
    "#12 AWG": 0.0133,
    "#10 AWG": 0.0211,
    "#8 AWG": 0.0366,
    "#6 AWG": 0.0507,
    "#4 AWG": 0.0824,
    "#2 AWG": 0.1158,
    "#1/0 AWG": 0.1855,
    "#2/0 AWG": 0.2223,
    "#3/0 AWG": 0.2679,
    "#4/0 AWG": 0.3237,
    "250 kcmil": 0.3970,
    "350 kcmil": 0.5077,
    "500 kcmil": 0.6778
}

def load_cable_types(doc_obj):
    # Locate shared_parameters directory (6 levels up from this script)
    _root = __file__
    for _ in range(6):
        _root = os.path.dirname(_root)
    
    shared_params_dir = os.path.join(_root, "shared_parameters")
    cable_types_path = os.path.join(shared_params_dir, "cable_types.json")
    
    # 1. Try to load from file
    if os.path.exists(cable_types_path):
        try:
            with open(cable_types_path, 'r') as f:
                loaded = json.load(f)
            if isinstance(loaded, list) and loaded:
                res_list = []
                for item in loaded:
                    if isinstance(item, dict) and "Name" in item:
                        res_list.append({
                            "Name": str(item["Name"]).strip(),
                            "CableArea": float(item.get("CableArea", 0.0))
                        })
                if res_list:
                    return res_list
        except Exception:
            pass
            
    # Fallback to default list if file doesn't exist
    return [{"Name": k, "CableArea": DEFAULT_CABLE_AREAS[k]} for k in sorted(DEFAULT_CABLE_AREAS.keys())]

# --- Revit Selection Filter ---
class ConduitOrPipeSelectionFilter(UI.Selection.ISelectionFilter):
    def AllowElement(self, element):
        if not element or not element.Category:
            return False
        cat_id = element.Category.Id.IntegerValue
        return cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_PipeCurves)]
        
    def AllowReference(self, reference, point):
        return False

# --- Helper Functions ---
def get_inner_diameter(elem):
    """Safely extracts inner diameter of Conduit or Pipe in decimal feet."""
    # 1. Conduit Inner Diameter (Built-in)
    try:
        p_cond = elem.get_Parameter(DB.BuiltInParameter.RBS_CONDUIT_INNER_DIAM_PARAM)
        if p_cond and p_cond.HasValue:
            return p_cond.AsDouble()
    except Exception:
        pass
    
    # 2. Pipe Inner Diameter (Built-in)
    try:
        p_pipe = elem.get_Parameter(DB.BuiltInParameter.RBS_PIPE_INNER_DIAM_PARAM)
        if p_pipe and p_pipe.HasValue:
            return p_pipe.AsDouble()
    except Exception:
        pass
        
    # 3. Fallback Lookups
    for name in ["Inside Diameter", "Inner Diameter", "Diámetro interior", "Diámetro Interior", "InsideDiam"]:
        try:
            p = elem.LookupParameter(name)
            if p and p.HasValue:
                return p.AsDouble()
        except Exception:
            pass
            
    return None

def get_element_size_string(elem):
    """Retrieves size representation of Conduit or Pipe."""
    # 1. Try standard RBS_REFERENCE_SIZE built-in parameter
    try:
        p_size = elem.get_Parameter(DB.BuiltInParameter.RBS_REFERENCE_SIZE)
        if p_size and p_size.HasValue:
            return p_size.AsString()
    except Exception:
        pass
        
    # 2. Try common name lookups
    for name in ["Size", "Size Description", "Tamaño", "Tamaño de Conduit", "Size description"]:
        try:
            p = elem.LookupParameter(name)
            if p and p.HasValue:
                return p.AsString()
        except Exception:
            pass
            
    # 3. Fallback to computed diameter string
    diam = get_inner_diameter(elem)
    if diam:
        return '{:.3f}"'.format(diam * 12.0)
        
    return "N/A"

# --- Main WPF Window ---
class VerifyConduitSizeWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name, element, category_name, size_str, inner_diam, inner_area, total_cable_area, fill_ratio, total_wires_count, nec_limit, cables_details):
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Populate element info cards
        self.lblCategory.Text = category_name
        self.lblElementId.Text = str(element.Id.IntegerValue)
        self.lblSize.Text = size_str
        self.lblInnerDiam.Text = "{:.3f} in".format(inner_diam)
        self.lblInnerArea.Text = "{:.3f} sq in".format(inner_area)
        
        # Populate results
        self.lblPercentage.Text = "{:.1f}%".format(fill_ratio)
        self.lblCableCount.Text = "Total Wires: {}".format(total_wires_count)
        self.lblTotalCableArea.Text = "Total Cable Area: {:.4f} sq in".format(total_cable_area)
        self.lblNecLimit.Text = "NEC Limit: {}%".format(int(nec_limit))
        
        # Style ProgressBar and Status based on limits
        self.pbFill.Value = min(fill_ratio, 100.0)
        
        if fill_ratio > nec_limit:
            self.pbFill.Foreground = Media.BrushConverter().ConvertFromString("#EF4444")  # Red
            self.lblStatus.Text = "OVER CAPACITY"
            self.lblStatus.Foreground = Media.BrushConverter().ConvertFromString("#EF4444")
        elif fill_ratio > (nec_limit * 0.8):
            self.pbFill.Foreground = Media.BrushConverter().ConvertFromString("#F59E0B")  # Amber
            self.lblStatus.Text = "NEAR CAPACITY"
            self.lblStatus.Foreground = Media.BrushConverter().ConvertFromString("#F59E0B")
        else:
            self.pbFill.Foreground = Media.BrushConverter().ConvertFromString("#10B981")  # Emerald Green
            self.lblStatus.Text = "SAFE"
            self.lblStatus.Foreground = Media.BrushConverter().ConvertFromString("#10B981")
            
        # Populate cables list
        if not cables_details:
            self.lblNoCables.Visibility = Windows.Visibility.Visible
        else:
            self.lblNoCables.Visibility = Windows.Visibility.Collapsed
            
            for item in cables_details:
                row = Controls.DockPanel()
                row.Margin = Windows.Thickness(0, 4, 0, 4)
                
                # Left side text: Quantity, Type, Circuit & Phase
                txt_left = Controls.TextBlock()
                txt_left.Text = "{}x {} ({}, {})".format(item["Qty"], item["Type"], item["Circuit"], item["Phase"])
                txt_left.Foreground = Media.BrushConverter().ConvertFromString("#1E293B")
                txt_left.FontWeight = Windows.FontWeights.SemiBold
                txt_left.VerticalAlignment = Windows.VerticalAlignment.Center
                Controls.DockPanel.SetDock(txt_left, Controls.Dock.Left)
                row.Children.Add(txt_left)
                
                # Right side text: individual cable area
                txt_right = Controls.TextBlock()
                txt_right.Text = "{:.4f} sq in each".format(item["Area"])
                txt_right.Foreground = Media.BrushConverter().ConvertFromString("#64748B")
                txt_right.FontSize = 10
                txt_right.VerticalAlignment = Windows.VerticalAlignment.Center
                txt_right.HorizontalAlignment = Windows.HorizontalAlignment.Right
                Controls.DockPanel.SetDock(txt_right, Controls.Dock.Right)
                row.Children.Add(txt_right)
                
                # Card wrapper
                card = Controls.Border()
                card.Background = Media.BrushConverter().ConvertFromString("#F8FAFC")
                card.BorderBrush = Media.BrushConverter().ConvertFromString("#F1F5F9")
                card.BorderThickness = Windows.Thickness(0, 0, 0, 1)
                card.Padding = Windows.Thickness(5, 6, 5, 6)
                card.Child = row
                
                self.CablesPanel.Children.Add(card)

    def Close_Click(self, sender, e):
        self.Close()

# --- Main Entry Point ---
def main():
    # 1. Gather Selection
    selected_ids = uidoc.Selection.GetElementIds()
    selected_elem = None
    
    for eid in selected_ids:
        el = doc.GetElement(eid)
        if el and el.Category:
            cat_id = el.Category.Id.IntegerValue
            if cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_PipeCurves)]:
                selected_elem = el
                break
                
    # 2. Pick Object if nothing selected
    if not selected_elem:
        try:
            sel_filter = ConduitOrPipeSelectionFilter()
            with forms.WarningBar(title="Select a single Conduit or Pipe in the model"):
                ref = uidoc.Selection.PickObject(
                    UI.Selection.ObjectType.Element, 
                    sel_filter, 
                    "Select a Conduit or Pipe to verify its size"
                )
                selected_elem = doc.GetElement(ref.ElementId)
        except Exception:
            # User cancelled selection
            return
            
    if not selected_elem:
        return

    # 3. Parameter Validation (Check for GPC-Cables parameter)
    param = selected_elem.LookupParameter("GPC-Cables")
    if not param:
        forms.alert(
            "The 'GPC-Cables' parameter was not found on the selected element.\n\n"
            "If it is a Conduit, please run 'Setup Parameters' in the Electrical menu first to inject this parameter into your project.",
            title="Parameter Missing"
        )
        return

    # 4. Extract Category details
    cat_id = selected_elem.Category.Id.IntegerValue
    category_name = "Conduit" if cat_id == int(DB.BuiltInCategory.OST_Conduit) else "Pipe"
    size_str = get_element_size_string(selected_elem)

    # 5. Retrieve & Compute Inner Dimensions
    inner_diam_feet = get_inner_diameter(selected_elem)
    if inner_diam_feet is None or inner_diam_feet <= 0.0:
        forms.alert(
            "Could not retrieve the inner diameter parameter for this element.\n"
            "Please verify that the selected element has a valid inside/inner diameter size configuration.",
            title="Size Retrieval Error"
        )
        return
        
    inner_diam_in = inner_diam_feet * 12.0
    inner_area = math.pi * (inner_diam_in / 2.0)**2

    # 6. Load Cable Sizes database
    cable_db = load_cable_types(doc)
    cable_areas = {x["Name"]: x["CableArea"] for x in cable_db}

    # 7. Decode Circuits & Assigned Cables
    cables_details = []
    total_cable_area = 0.0
    total_wires_count = 0
    
    param_json = param.AsString() or ""
    if param_json:
        try:
            circuits = json.loads(param_json)
            if isinstance(circuits, list):
                for circuit in circuits:
                    c_name = circuit.get("Circuit", "Unknown")
                    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                        phase_data = circuit.get(phase)
                        if isinstance(phase_data, dict):
                            qty = phase_data.get("Quantity", 0)
                            if qty > 0:
                                c_type = phase_data.get("CableType")
                                if c_type:
                                    c_type_str = str(c_type).strip()
                                    area = cable_areas.get(c_type_str, DEFAULT_CABLE_AREAS.get(c_type_str, 0.0))
                                    total_cable_area += qty * area
                                    total_wires_count += qty
                                    cables_details.append({
                                        "Circuit": c_name,
                                        "Phase": phase,
                                        "Qty": qty,
                                        "Type": c_type_str,
                                        "Area": area
                                    })
        except Exception as ex:
            forms.alert("Error parsing GPC-Cables parameter JSON: {}".format(ex), title="JSON Parsing Error")
            return

    # 8. Calculate NEC Sizing and Sizing Limits
    # NEC Chapter 9, Table 1 limits:
    # 1 wire: 53% fill
    # 2 wires: 31% fill
    # 3 or more wires: 40% fill
    if total_wires_count == 1:
        nec_limit = 53.0
    elif total_wires_count == 2:
        nec_limit = 31.0
    else:
        nec_limit = 40.0  # standard for 3 or more, and default for 0

    fill_ratio = (total_cable_area / inner_area) * 100.0 if inner_area > 0.0 else 0.0

    # 9. Launch Window Dialog
    xaml_file = os.path.join(os.path.dirname(__file__), "ui.xaml")
    win = VerifyConduitSizeWindow(
        xaml_file,
        selected_elem,
        category_name,
        size_str,
        inner_diam_in,
        inner_area,
        total_cable_area,
        fill_ratio,
        total_wires_count,
        nec_limit,
        cables_details
    )
    win.ShowDialog()

if __name__ == '__main__':
    main()
