# -*- coding: utf-8 -*-
"""Analyze and color-code all conduits in the active view based on fill capacity."""

__title__ = 'Conduit Capacity\nColor'
__author__ = 'Electrical Team'

import os
import json
import math
import clr  # type: ignore

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
    # Locate shared_parameters directory (5 levels up from this script)
    _root = os.path.abspath(__file__)
    for _ in range(5):
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

def get_inner_diameter(elem):
    """Safely extracts inner diameter of Conduit in decimal feet."""
    try:
        p_cond = elem.get_Parameter(DB.BuiltInParameter.RBS_CONDUIT_INNER_DIAM_PARAM)
        if p_cond and p_cond.HasValue:
            return p_cond.AsDouble()
    except Exception:
        pass
    
    for name in ["Inside Diameter", "Inner Diameter", "Diámetro interior", "Diámetro Interior", "InsideDiam"]:
        try:
            p = elem.LookupParameter(name)
            if p and p.HasValue:
                return p.AsDouble()
        except Exception:
            pass
            
    return None

def calculate_conduit_capacity(conduit, cable_areas):
    """Calculates fill ratio, NEC limit, and capacity percent for a conduit."""
    param = conduit.LookupParameter("GPC-Cables")
    param_json = param.AsString() or "" if param else ""
    
    inner_diam_feet = get_inner_diameter(conduit)
    if inner_diam_feet is None or inner_diam_feet <= 0.0:
        return None
        
    inner_diam_in = inner_diam_feet * 12.0
    inner_area = math.pi * (inner_diam_in / 2.0)**2
    
    total_cable_area = 0.0
    total_wires_count = 0
    
    if param_json:
        try:
            circuits = json.loads(param_json)
            if isinstance(circuits, list):
                for circuit in circuits:
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
        except Exception:
            pass
            
    if total_wires_count == 1:
        nec_limit = 53.0
    elif total_wires_count == 2:
        nec_limit = 31.0
    else:
        nec_limit = 40.0
        
    fill_ratio = (total_cable_area / inner_area) * 100.0 if inner_area > 0.0 else 0.0
    capacity_nec = (fill_ratio / nec_limit) * 100.0 if nec_limit > 0.0 else 0.0
    
    return {
        "fill_ratio": fill_ratio,
        "nec_limit": nec_limit,
        "capacity_nec": capacity_nec
    }

class ConduitCapacityWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Load cable database
        cable_db = load_cable_types(doc)
        self.cable_areas = {x["Name"]: x["CableArea"] for x in cable_db}
        
        # Scan conduits in active view
        self.scan_conduits()
        
        # Initialize UI and update counters
        self.update_ui_elements()
        
    def scan_conduits(self):
        collector = DB.FilteredElementCollector(doc, doc.ActiveView.Id) \
                      .OfCategory(DB.BuiltInCategory.OST_Conduit) \
                      .WhereElementIsNotElementType()
                      
        self.conduits_data = []
        for c in collector:
            cap_data = calculate_conduit_capacity(c, self.cable_areas)
            if cap_data:
                self.conduits_data.append({
                    "element": c,
                    "fill_ratio": cap_data["fill_ratio"],
                    "nec_limit": cap_data["nec_limit"],
                    "capacity_nec": cap_data["capacity_nec"]
                })
                
    def update_ui_elements(self):
        method_idx = self.cbSizingMethod.SelectedIndex
        if method_idx == 0:
            # NEC Capacity Limit
            self.lblScale1Range.Text = "0% - 40% of allowed NEC limit"
            self.lblScale2Range.Text = "40% - 80% of allowed NEC limit"
            self.lblScale3Range.Text = "80% - 100% of allowed NEC limit"
            self.lblScale4Range.Text = ">100% of allowed NEC limit"
        else:
            # Direct Fill Ratio
            self.lblScale1Range.Text = "0% - 10% raw fill ratio"
            self.lblScale2Range.Text = "10% - 25% raw fill ratio"
            self.lblScale3Range.Text = "25% - 40% raw fill ratio"
            self.lblScale4Range.Text = ">40% raw fill ratio"
            
        scale1_count = 0
        scale2_count = 0
        scale3_count = 0
        scale4_count = 0
        
        for item in self.conduits_data:
            scale = self.get_scale_for_conduit(item, method_idx)
            if scale == 1:
                scale1_count += 1
            elif scale == 2:
                scale2_count += 1
            elif scale == 3:
                scale3_count += 1
            elif scale == 4:
                scale4_count += 1
                
        self.lblScale1Count.Text = "{} Conduit{}".format(scale1_count, "" if scale1_count == 1 else "s")
        self.lblScale2Count.Text = "{} Conduit{}".format(scale2_count, "" if scale2_count == 1 else "s")
        self.lblScale3Count.Text = "{} Conduit{}".format(scale3_count, "" if scale3_count == 1 else "s")
        self.lblScale4Count.Text = "{} Conduit{}".format(scale4_count, "" if scale4_count == 1 else "s")
        
        total_count = len(self.conduits_data)
        self.lblTotalConduits.Text = "Total Conduits Found in View: {}".format(total_count)
        
    def get_scale_for_conduit(self, item, method_idx):
        if method_idx == 0:
            # NEC Capacity Used
            val = item["capacity_nec"]
            if val <= 40.0:
                return 1
            elif val <= 80.0:
                return 2
            elif val <= 100.0:
                return 3
            else:
                return 4
        else:
            # Direct Fill Ratio
            val = item["fill_ratio"]
            if val <= 10.0:
                return 1
            elif val <= 25.0:
                return 2
            elif val <= 40.0:
                return 3
            else:
                return 4
                
    def get_color_for_scale(self, scale):
        if scale == 1:
            return DB.Color(16, 185, 129)  # Emerald Green
        elif scale == 2:
            return DB.Color(132, 204, 22)  # Lime
        elif scale == 3:
            return DB.Color(245, 158, 11)  # Amber
        else:
            return DB.Color(239, 68, 68)   # Red
            
    def SizingMethod_Changed(self, sender, e):
        if hasattr(self, 'cbSizingMethod') and self.cbSizingMethod:
            self.update_ui_elements()
            
    def SliderWeight_Changed(self, sender, e):
        if hasattr(self, 'lblWeightVal') and self.lblWeightVal:
            self.lblWeightVal.Text = str(int(self.sliderWeight.Value))
            
    def Close_Click(self, sender, e):
        self.Close()
        
    def Clear_Click(self, sender, e):
        if not self.conduits_data:
            forms.alert("No conduits found in the active view to clear.", title="Clear Overrides")
            return
            
        with revit.Transaction("Clear Conduit Capacity Colors"):
            reset_override = DB.OverrideGraphicSettings()
            count = 0
            for item in self.conduits_data:
                doc.ActiveView.SetElementOverrides(item["element"].Id, reset_override)
                count += 1
                
        forms.alert(
            "Graphic overrides cleared successfully!\n\n"
            "Reset elements in active view: {}".format(count), 
            title="Overrides Cleared"
        )
        
    def Apply_Click(self, sender, e):
        if not self.conduits_data:
            forms.alert("No conduits found in the active view to color code.", title="Apply Overrides")
            return
            
        method_idx = self.cbSizingMethod.SelectedIndex
        line_weight = int(self.sliderWeight.Value)
        
        with revit.Transaction("Apply Conduit Capacity Colors"):
            count = 0
            for item in self.conduits_data:
                scale = self.get_scale_for_conduit(item, method_idx)
                color = self.get_color_for_scale(scale)
                
                override = DB.OverrideGraphicSettings()
                override.SetProjectionLineColor(color)
                override.SetProjectionLineWeight(line_weight)
                
                doc.ActiveView.SetElementOverrides(item["element"].Id, override)
                count += 1
                
        forms.alert(
            "Conduit capacity overrides applied successfully!\n\n"
            "Color-coded elements: {}".format(count),
            title="Overrides Applied"
        )

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xaml_file = os.path.join(script_dir, "ui.xaml")
    
    win = ConduitCapacityWindow(xaml_file)
    win.ShowDialog()

if __name__ == "__main__":
    main()
