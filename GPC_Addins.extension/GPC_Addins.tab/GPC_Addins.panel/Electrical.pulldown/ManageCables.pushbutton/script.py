# -*- coding: utf-8 -*-
"""Manage circuits, wire counts, and cable sizes inside selected conduits."""

__title__ = 'Manage\nCables'
__author__ = 'Electrical Team'

import os
import json
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

# --- Cable Types List ---
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

DEFAULT_CABLE_TYPES = sorted(list(DEFAULT_CABLE_AREAS.keys()))
DEFAULT_CABLE_TYPES_DB = [{"Name": k, "CableArea": DEFAULT_CABLE_AREAS[k]} for k in DEFAULT_CABLE_TYPES]

def load_cable_types(doc):
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
            
    # 2. Extract from model conduits/fittings if file does not exist or failed to load
    extracted = set()
    try:
        conduits = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
        fittings = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
        for el in list(conduits) + list(fittings):
            param = el.LookupParameter("GPC-Cables")
            if param:
                val = param.AsString()
                if val:
                    try:
                        circuits = json.loads(val)
                        if isinstance(circuits, list):
                            for circuit in circuits:
                                if isinstance(circuit, dict):
                                    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                                        phase_data = circuit.get(phase)
                                        if isinstance(phase_data, dict):
                                            c_type = phase_data.get("CableType")
                                            if c_type:
                                                c_type_str = str(c_type).strip()
                                                if c_type_str:
                                                    extracted.add(c_type_str)
                    except Exception:
                        pass
    except Exception:
        pass
        
    if extracted:
        cable_list = []
        for name in sorted(list(extracted)):
            area = DEFAULT_CABLE_AREAS.get(name, 0.0)
            cable_list.append({"Name": name, "CableArea": area})
    else:
        cable_list = DEFAULT_CABLE_TYPES_DB
    
    # 3. Create directory if not exists and save the new cable_types.json
    try:
        if not os.path.exists(shared_params_dir):
            os.makedirs(shared_params_dir)
        with open(cable_types_path, 'w') as f:
            json.dump(cable_list, f, indent=4)
    except Exception:
        pass
        
    return cable_list

def save_cable_types(cable_list):
    # Locate shared_parameters directory (6 levels up from this script)
    _root = __file__
    for _ in range(6):
        _root = os.path.dirname(_root)
    
    shared_params_dir = os.path.join(_root, "shared_parameters")
    cable_types_path = os.path.join(shared_params_dir, "cable_types.json")
    
    try:
        if not os.path.exists(shared_params_dir):
            os.makedirs(shared_params_dir)
        with open(cable_types_path, 'w') as f:
            json.dump(cable_list, f, indent=4)
    except Exception:
        pass

CABLE_TYPES_DB = load_cable_types(doc)
CABLE_TYPES = [x["Name"] for x in CABLE_TYPES_DB]
CABLE_AREAS = {x["Name"]: x["CableArea"] for x in CABLE_TYPES_DB}

def generate_cables_tag_text(circuits):
    if not circuits:
        return ""
        
    circuit_parts = []
    for circuit in circuits:
        c_name = circuit.get("Circuit", "")
        # Group cables by (CableType, IsShared) within this circuit
        cables_summary = {}
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
            phase_data = circuit.get(phase)
            if phase_data:
                qty = phase_data.get("Quantity", 0)
                if qty > 0:
                    c_type = phase_data.get("CableType")
                    if c_type:
                        c_type_str = str(c_type).strip()
                        is_shared = bool(phase_data.get("Shared", False))
                        key = (c_type_str, is_shared)
                        cables_summary[key] = cables_summary.get(key, 0) + qty
                        
        # Format the items for this circuit
        parts = []
        # Sort so they display in a stable order (e.g. by CableType name)
        for (c_type, is_shared) in sorted(cables_summary.keys()):
            qty = cables_summary[(c_type, is_shared)]
            suffix = " C" if is_shared else ""
            parts.append("{}{}{}".format(qty, c_type, suffix))
            
        if parts:
            circuit_parts.append("{} ({})".format(c_name, ", ".join(parts)))
        else:
            circuit_parts.append(c_name)
            
    return "; ".join(circuit_parts)

# --- Revit Selection Filter ---
class ConduitSelectionFilter(UI.Selection.ISelectionFilter):
    def AllowElement(self, element):
        if not element or not element.Category:
            return False
        cat_id = element.Category.Id.IntegerValue
        return cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]
        
    def AllowReference(self, reference, point):
        return False

# --- UI Circuit Card ---
class CircuitCard(object):
    def __init__(self, data, on_delete_callback):
        self.data = data
        self.on_delete_callback = on_delete_callback
        
        # Create Main Card Border
        self.border = Controls.Border()
        self.border.Background = Media.Brushes.White
        self.border.BorderBrush = Media.BrushConverter().ConvertFromString("#E2E8F0")
        self.border.BorderThickness = Windows.Thickness(1)
        self.border.CornerRadius = Windows.CornerRadius(6)
        self.border.Padding = Windows.Thickness(15)
        self.border.Margin = Windows.Thickness(0, 0, 0, 12)
        
        # Grid layout inside card
        grid = Controls.Grid()
        grid.RowDefinitions.Add(Controls.RowDefinition())
        grid.RowDefinitions.Add(Controls.RowDefinition())
        self.border.Child = grid
        
        # Row 0: Circuit ID Header and Delete Button
        header_panel = Controls.DockPanel()
        header_panel.LastChildFill = True
        grid.SetRow(header_panel, 0)
        grid.Children.Add(header_panel)
        
        # Remove Button
        btn_del = Controls.Button()
        btn_del.Content = "Remove"
        btn_del.Width = 65
        btn_del.Height = 24
        btn_del.Background = Media.BrushConverter().ConvertFromString("#EF4444")
        btn_del.Foreground = Media.Brushes.White
        btn_del.BorderBrush = None
        btn_del.FontWeight = Windows.FontWeights.Bold
        btn_del.FontSize = 10
        btn_del.Click += self.delete_clicked
        Controls.DockPanel.SetDock(btn_del, Controls.Dock.Right)
        header_panel.Children.Add(btn_del)
        
        # Title Label
        lbl = Controls.TextBlock()
        lbl.Text = "Circuit ID:"
        lbl.FontWeight = Windows.FontWeights.Bold
        lbl.Foreground = Media.BrushConverter().ConvertFromString("#1E293B")
        lbl.VerticalAlignment = Windows.VerticalAlignment.Center
        lbl.Margin = Windows.Thickness(0, 0, 8, 0)
        Controls.DockPanel.SetDock(lbl, Controls.Dock.Left)
        header_panel.Children.Add(lbl)
        
        # Circuit Name Input
        self.txt_name = Controls.TextBox()
        self.txt_name.Text = data.get("Circuit", "")
        self.txt_name.Padding = Windows.Thickness(4)
        self.txt_name.VerticalAlignment = Windows.VerticalAlignment.Center
        header_panel.Children.Add(self.txt_name)
        
        # Row 1: Multi-Column Phase Details Grid
        columns_grid = Controls.Grid()
        columns_grid.Margin = Windows.Thickness(0, 12, 0, 0)
        for _ in range(5):
            columns_grid.ColumnDefinitions.Add(Controls.ColumnDefinition())
            
        grid.SetRow(columns_grid, 1)
        grid.Children.Add(columns_grid)
        
        phases = ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]
        self.controls = {}
        
        for idx, phase in enumerate(phases):
            phase_data = data.get(phase, {"Quantity": 1, "Shared": False, "CableType": "#12 AWG"})
            
            # StackPanel for this phase column
            col_panel = Controls.StackPanel()
            col_panel.Margin = Windows.Thickness(4, 0, 4, 0)
            columns_grid.SetColumn(col_panel, idx)
            columns_grid.Children.Add(col_panel)
            
            # Header
            phase_lbl = Controls.TextBlock()
            phase_lbl.Text = phase
            phase_lbl.FontWeight = Windows.FontWeights.Bold
            phase_lbl.FontSize = 10
            phase_lbl.Foreground = Media.BrushConverter().ConvertFromString("#475569")
            phase_lbl.Margin = Windows.Thickness(0, 0, 0, 6)
            col_panel.Children.Add(phase_lbl)
            
            # Quantity Section
            qty_panel = Controls.DockPanel()
            qty_panel.Margin = Windows.Thickness(0, 2, 0, 2)
            col_panel.Children.Add(qty_panel)
            
            qty_lbl = Controls.TextBlock()
            qty_lbl.Text = "Count:"
            qty_lbl.FontSize = 9
            qty_lbl.VerticalAlignment = Windows.VerticalAlignment.Center
            Controls.DockPanel.SetDock(qty_lbl, Controls.Dock.Left)
            qty_panel.Children.Add(qty_lbl)
            
            txt_qty = Controls.TextBox()
            txt_qty.Text = str(phase_data.get("Quantity", 1))
            txt_qty.Width = 35
            txt_qty.Padding = Windows.Thickness(3)
            txt_qty.HorizontalAlignment = Windows.HorizontalAlignment.Right
            Controls.DockPanel.SetDock(txt_qty, Controls.Dock.Right)
            qty_panel.Children.Add(txt_qty)
            
            # Cable Dropdown selection
            cb_cable = Controls.ComboBox()
            cb_cable.ItemsSource = CABLE_TYPES
            cb_cable.SelectedItem = phase_data.get("CableType", "#12 AWG")
            cb_cable.Margin = Windows.Thickness(0, 4, 0, 4)
            col_panel.Children.Add(cb_cable)
            
            # Shared checkbox
            chk_shared = Controls.CheckBox()
            chk_shared.Content = "Shared"
            chk_shared.FontSize = 9
            chk_shared.IsChecked = bool(phase_data.get("Shared", False))
            col_panel.Children.Add(chk_shared)
            
            self.controls[phase] = {
                "qty": txt_qty,
                "cable": cb_cable,
                "shared": chk_shared
            }
            
    def delete_clicked(self, sender, e):
        self.on_delete_callback(self)
        
    def get_data(self):
        res = {  # type: dict[str, any]
            "Circuit": self.txt_name.Text
        }
        for phase, ctrl in self.controls.items():
            qty_str = ctrl["qty"].Text
            try:
                qty = int(qty_str)
            except ValueError:
                qty = 0
            
            c_type = ctrl["cable"].SelectedItem or "#12 AWG"
            res[phase] = {
                "Quantity": qty,
                "Shared": bool(ctrl["shared"].IsChecked),
                "CableType": c_type,
                "CableArea": CABLE_AREAS.get(c_type, 0.0)
            }
        return res

# --- Main WPF Window ---
class ManageCablesWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name, conduits, initial_circuits, has_multiple_with_existing=False):
        self.conduits = conduits
        self.cards = []
        self.loaded_circuit_names = {c["Circuit"] for c in initial_circuits} if initial_circuits else set()
        
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Populate selected conduit label
        conduit_names = ["ID: {}".format(c.Id) for c in conduits]
        self.lblTargetConduits.Text = "Conduits (Total: {}): {}".format(len(conduits), ", ".join(conduit_names))
        
        if has_multiple_with_existing:
            # We are in "Clear/Cancel" mode for multiple conduits that already contain cables
            self.lblNoCircuits.Text = (
                "Multiple conduits are selected, and some already contain cables/circuits.\n\n"
                "To edit circuits and cables, please select a single conduit.\n"
                "You can clear all cables/circuits from the selected conduits, or click Cancel."
            )
            self.lblNoCircuits.Foreground = Media.BrushConverter().ConvertFromString("#EF4444")
            self.lblNoCircuits.FontSize = 13
            self.lblNoCircuits.Visibility = Windows.Visibility.Visible
            
            # Hide editing elements
            self.btnAddCircuit.Visibility = Windows.Visibility.Collapsed
            
            # Re-purpose Save button to "Clear Cables" in red
            self.btnSave.Content = "Clear Cables"
            self.btnSave.Background = Media.BrushConverter().ConvertFromString("#EF4444")
            self.is_clear_mode = True
        else:
            self.is_clear_mode = False
            # Load initial circuits
            if initial_circuits:
                for c_data in initial_circuits:
                    self.add_circuit_card(c_data)
            self.update_empty_state()

    def add_circuit_card(self, data):
        card = CircuitCard(data, self.remove_circuit_card)
        self.cards.append(card)
        self.CircuitsPanel.Children.Add(card.border)
        self.update_empty_state()

    def remove_circuit_card(self, card):
        self.cards.remove(card)
        self.CircuitsPanel.Children.Remove(card.border)
        self.update_empty_state()

    def update_empty_state(self):
        if len(self.cards) == 0:
            self.lblNoCircuits.Visibility = Windows.Visibility.Visible
        else:
            self.lblNoCircuits.Visibility = Windows.Visibility.Collapsed

    def AddCircuit_Click(self, sender, e):
        default_name = "Circ-{}".format(len(self.cards) + 1)
        
        # Default starting values
        default_data = {  # type: dict[str, any]
            "Circuit": default_name
        }
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
            default_data[phase] = {
                "Quantity": 1 if phase != "Ground" else 1,
                "Shared": False,
                "CableType": "#12 AWG"
            }
            
        self.add_circuit_card(default_data)

    def AddCableType_Click(self, sender, e):
        global CABLE_TYPES, CABLE_AREAS
        # Temporarily disable Topmost if set so dialogs/alerts are drawn on top
        was_topmost = self.Topmost
        self.Topmost = False
        try:
            new_cable = forms.ask_for_string(
                title="Add New Cable Type",
                prompt="Enter the name/size of the new cable type (e.g. 750 kcmil):"
            )
            if not new_cable:
                return
            
            new_cable = new_cable.strip()
            if not new_cable:
                return
                
            if new_cable in CABLE_TYPES:
                forms.alert("Cable type '{}' already exists!".format(new_cable), title="Duplicate Entry")
                return

            new_area_str = forms.ask_for_string(
                title="Add Cable Type Area",
                prompt="Enter the cross-sectional area (in sq in) for '{}':".format(new_cable),
                default="0.0"
            )
            if new_area_str is None:
                return
            try:
                new_area = float(new_area_str)
            except ValueError:
                new_area = 0.0
                
            # Add to global database list
            CABLE_TYPES_DB.append({"Name": new_cable, "CableArea": new_area})
            CABLE_TYPES_DB.sort(key=lambda x: x["Name"])
            
            # Save to database file
            save_cable_types(CABLE_TYPES_DB)

            # Update global lists
            CABLE_TYPES = [x["Name"] for x in CABLE_TYPES_DB]
            CABLE_AREAS = {x["Name"]: x["CableArea"] for x in CABLE_TYPES_DB}
            
            # Refresh all ComboBoxes on screen
            for card in self.cards:
                for phase, ctrl in card.controls.items():
                    cb = ctrl["cable"]
                    selected = cb.SelectedItem
                    # Temporarily reset ItemsSource to update dropdown list
                    cb.ItemsSource = None
                    cb.ItemsSource = CABLE_TYPES
                    # Restore selection
                    if selected in CABLE_TYPES:
                        cb.SelectedItem = selected
                    else:
                        cb.SelectedItem = new_cable
                        
            forms.alert("Cable type '{}' successfully added to database!".format(new_cable), title="Success")
        finally:
            self.Topmost = was_topmost

    def Cancel_Click(self, sender, e):
        self.Close()

    def Save_Click(self, sender, e):
        if getattr(self, "is_clear_mode", False):
            # Prompt user to confirm clearing
            if not forms.alert(
                "Are you sure you want to clear all cables and circuits from the selected {} conduit(s)?\n\n"
                "This will set the 'GPC-Cables' parameter value to empty on all selected conduits.".format(len(self.conduits)),
                yes=True, no=True, title="Clear Cables"
            ):
                return

            with revit.Transaction("Clear Conduit Cables"):
                for c in self.conduits:
                    param = c.LookupParameter("GPC-Cables")
                    if param:
                        param.Set("")
                    param_tag = c.LookupParameter("GPC-Cables-Tag")
                    if param_tag:
                        param_tag.Set("")

            forms.alert("Cables cleared successfully from {} conduit(s)/fitting(s)!".format(len(self.conduits)), title="Success")
            self.Close()
            return

        # 1. Collect and validate data
        final_circuits = []
        for card in self.cards:
            data = card.get_data()
            if not data["Circuit"].strip():
                forms.alert("Please provide a valid Circuit ID for all circuits.", title="Validation Error")
                return
            
            # Check integer inputs
            for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                qty = data[phase]["Quantity"]
                if qty < 0:
                    forms.alert("Quantities cannot be negative (found on circuit {}).".format(data["Circuit"]), title="Validation Error")
                    return
            final_circuits.append(data)

        # 1. Normalize and clean input circuits from dialog, preserving all phases
        processed_final_circuits = []
        for c in final_circuits:
            clean_c = {"Circuit": c["Circuit"]}
            for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                phase_data = c.get(phase)
                if phase_data:
                    clean_c[phase] = {
                        "Quantity": phase_data.get("Quantity", 1),
                        "Shared": bool(phase_data.get("Shared", False)),
                        "CableType": str(phase_data.get("CableType", "#12 AWG")).strip()
                    }
            processed_final_circuits.append(clean_c)

        # 2. Save / Merge to all selected conduits in a Revit Transaction
        with revit.Transaction("Update Conduit Cables"):
            for idx, c in enumerate(self.conduits):
                param = c.LookupParameter("GPC-Cables")
                if not param:
                    continue

                if len(self.conduits) == 1:
                    # Single selected conduit: save directly, supporting deletions and full updates
                    merged_circuits = processed_final_circuits
                else:
                    # Multiple selected conduits: do not overwrite. Merge the newly entered circuits
                    # from the dialog (since the dialog started empty) into each conduit's existing list of circuits.
                    existing_json_str = param.AsString() or ""
                    existing_circuits = []
                    if existing_json_str:
                        try:
                            existing_circuits = json.loads(existing_json_str)
                            if not isinstance(existing_circuits, list):
                                existing_circuits = []
                        except Exception:
                            existing_circuits = []

                    if not existing_circuits:
                        merged_circuits = processed_final_circuits
                    else:
                        merged_circuits = list(existing_circuits)
                        existing_names = {ext_c["Circuit"]: c_idx for c_idx, ext_c in enumerate(merged_circuits) if "Circuit" in ext_c}

                        # Merge each circuit from the dialog
                        for new_c in processed_final_circuits:
                            name = new_c["Circuit"]
                            if name in existing_names:
                                # Update existing circuit by name
                                merged_circuits[existing_names[name]] = new_c
                            else:
                                # Append new circuit
                                merged_circuits.append(new_c)

                # Process duplicate shared cables within this conduit specifically.
                # A cable is shared if Shared is True, and a cable of the same (Phase, CableType)
                # has already been seen in a previous circuit in this conduit's list.
                # In that case, we change its Quantity to 0 so it is not duplicated in count.
                conduit_circuits = json.loads(json.dumps(merged_circuits))
                seen_cables = set()
                for circuit in conduit_circuits:
                    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                        phase_data = circuit.get(phase)
                        if phase_data:
                            c_type = phase_data.get("CableType")
                            if c_type:
                                c_type_str = str(c_type).strip()
                                is_shared = phase_data.get("Shared", False)
                                cable_key = (phase, c_type_str)
                                
                                if is_shared and cable_key in seen_cables:
                                    phase_data["Quantity"] = 0
                                else:
                                    seen_cables.add(cable_key)

                # Serialize and set
                json_str = json.dumps(conduit_circuits)
                param.Set(json_str)
                
                param_tag = c.LookupParameter("GPC-Cables-Tag")
                if param_tag:
                    param_tag.Set(generate_cables_tag_text(conduit_circuits))

        forms.alert("Cables saved successfully to {} conduit(s)/fitting(s)!".format(len(self.conduits)), title="Success")
        self.Close()


def main():
    # Gather selected conduits and fittings
    selected_ids = uidoc.Selection.GetElementIds()
    conduits = []
    for eid in selected_ids:
        el = doc.GetElement(eid)
        if el and el.Category:
            cat_id = el.Category.Id.IntegerValue
            if cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]:
                conduits.append(el)

    if not conduits:
        try:
            sel_filter = ConduitSelectionFilter()
            refs = uidoc.Selection.PickObjects(
                UI.Selection.ObjectType.Element, 
                sel_filter, 
                "Select one or more Conduits or Fittings in the model"
            )
            for ref in refs:
                conduits.append(doc.GetElement(ref.ElementId))
        except:
            # User cancelled selection
            return

    if not conduits:
        return

    # Check for parameter existence
    first_conduit = conduits[0]
    param = first_conduit.LookupParameter("GPC-Cables")
    if not param:
        forms.alert(
            "The 'GPC-Cables' parameter was not found on the selected conduit(s).\n\n"
            "Please run 'Setup Parameters' in the Electrical menu first to inject this parameter into your project.",
            title="Parameter Missing"
        )
        return

    # Decode existing parameter value ONLY if exactly one conduit is selected.
    # If multiple conduits are selected, start with an empty dialog (initial_circuits = [])
    # to avoid loading one conduit's private circuits onto another.
    initial_circuits = []
    has_multiple_with_existing = False
    
    if len(conduits) == 1:
        existing_json_str = param.AsString() or ""
        if existing_json_str:
            try:
                initial_circuits = json.loads(existing_json_str)
                if not isinstance(initial_circuits, list):
                    initial_circuits = []
            except Exception:
                initial_circuits = []
    else:
        # Only trigger Clear Mode if ALL selected conduits already contain cables/circuits.
        # If at least one is empty, we allow regular edit/save.
        all_have_cables = True
        for c in conduits:
            p = c.LookupParameter("GPC-Cables")
            has_c = False
            if p:
                val = p.AsString()
                if val:
                    try:
                        circuits = json.loads(val)
                        if isinstance(circuits, list) and len(circuits) > 0:
                            has_c = True
                    except Exception:
                        pass
            if not has_c:
                all_have_cables = False
                break
        
        has_multiple_with_existing = all_have_cables

    # Launch WPF UI
    xaml_file = os.path.join(os.path.dirname(__file__), "ui.xaml")
    win = ManageCablesWindow(xaml_file, conduits, initial_circuits, has_multiple_with_existing)
    win.ShowDialog()

if __name__ == '__main__':
    main()
