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
    # Locate shared_parameters directory (5 levels up from this script)
    _root = os.path.abspath(__file__)
    for _ in range(5):
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

# Populated lazily inside main() so the file-read / model-scan only happen
# when the button is actually pressed, not at module import time.
CABLE_TYPES_DB = []
CABLE_TYPES = []
CABLE_AREAS = {}

# --- Brush cache ---
# A single BrushConverter instance is reused; results are memoised so each
# hex colour string is converted exactly once per session.
_BRUSH_CONVERTER = Media.BrushConverter()
_BRUSH_CACHE = {}

def _brush(hex_color):
    """Return a cached SolidColorBrush for the given hex string."""
    if hex_color not in _BRUSH_CACHE:
        _BRUSH_CACHE[hex_color] = _BRUSH_CONVERTER.ConvertFromString(hex_color)
    return _BRUSH_CACHE[hex_color]

def get_default_cable_type():
    preferred = "THW #12 AWG (Elec/Ilum)"
    if preferred in CABLE_TYPES:
        return preferred
    if CABLE_TYPES:
        return CABLE_TYPES[0]
    return "#12 AWG"

def load_last_used_cables():
    # Locate shared_parameters directory (5 levels up from this script)
    _root = os.path.abspath(__file__)
    for _ in range(5):
        _root = os.path.dirname(_root)
    
    shared_params_dir = os.path.join(_root, "shared_parameters")
    last_used_path = os.path.join(shared_params_dir, "last_used_cables.json")
    
    default_cable = get_default_cable_type()
    
    defaults = {}
    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
        defaults[phase] = {
            "Quantity": 1,
            "Shared": False,
            "CableType": default_cable
        }
        
    if os.path.exists(last_used_path):
        try:
            with open(last_used_path, 'r') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                res = {}
                for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                    p_data = loaded.get(phase)
                    if isinstance(p_data, dict):
                        c_type = p_data.get("CableType")
                        if c_type not in CABLE_TYPES:
                            c_type = default_cable
                        res[phase] = {
                            "Quantity": int(p_data.get("Quantity", 1)),
                            "Shared": bool(p_data.get("Shared", False)),
                            "CableType": c_type
                        }
                    else:
                        res[phase] = defaults[phase]
                return res
        except Exception:
            pass
            
    return defaults

def save_last_used_cables(data):
    # Locate shared_parameters directory (5 levels up from this script)
    _root = os.path.abspath(__file__)
    for _ in range(5):
        _root = os.path.dirname(_root)
    
    shared_params_dir = os.path.join(_root, "shared_parameters")
    last_used_path = os.path.join(shared_params_dir, "last_used_cables.json")
    
    try:
        if not os.path.exists(shared_params_dir):
            os.makedirs(shared_params_dir)
            
        save_data = {}
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
            phase_data = data.get(phase)
            if phase_data:
                save_data[phase] = {
                    "Quantity": phase_data.get("Quantity", 1),
                    "Shared": bool(phase_data.get("Shared", False)),
                    "CableType": phase_data.get("CableType")
                }
                
        with open(last_used_path, 'w') as f:
            json.dump(save_data, f, indent=4)
    except Exception:
        pass

def generate_cables_tag_text(circuits):
    if not circuits:
        return ""
        
    circuit_parts = []
    for circuit in circuits:
        c_name = circuit.get("Circuit", "")
        # Group cables by (CableType, IsShared) within this circuit
        cables_summary = {}
        # Keep track of which phases each (CableType, IsShared) is used in to determine sorting priority
        cable_roles = {}
        
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
                        
                        # Record role
                        if key not in cable_roles:
                            cable_roles[key] = set()
                        if phase in ["Phase 1", "Phase 2", "Phase 3"]:
                            cable_roles[key].add("phase")
                        elif phase == "Neutral":
                            cable_roles[key].add("neutral")
                        elif phase == "Ground":
                            cable_roles[key].add("ground")
                            
        # Define priority function for keys in cables_summary
        def get_sort_key(item_key):
            c_type_str, is_shared = item_key
            roles = cable_roles.get(item_key, set())
            if "phase" in roles:
                priority = 0
            elif "neutral" in roles:
                priority = 1
            elif "ground" in roles:
                priority = 2
            else:
                priority = 3
            return (priority, c_type_str, is_shared)
            
        # Format the items for this circuit
        parts = []
        for (c_type, is_shared) in sorted(cables_summary.keys(), key=get_sort_key):
            qty = cables_summary[(c_type, is_shared)]
            suffix = " C" if is_shared else ""
            parts.append("{}{}{}".format(qty, c_type, suffix))
            
        if parts:
            circuit_parts.append("{} ({})".format(c_name, ", ".join(parts)))
        else:
            circuit_parts.append(c_name)
            
    return "; ".join(circuit_parts)


# --- Database Helper Functions ---
def get_database_path(doc):
    if not doc.PathName:
        # Fallback if document is not saved
        _root = os.path.abspath(__file__)
        for _ in range(5):
            _root = os.path.dirname(_root)
        shared_params_dir = os.path.join(_root, "shared_parameters")
        if not os.path.exists(shared_params_dir):
            try:
                os.makedirs(shared_params_dir)
            except Exception:
                pass
        return os.path.join(shared_params_dir, "fallback_circuits.json")
    
    # Same folder as Revit document
    return os.path.splitext(doc.PathName)[0] + "_circuits.json"

def _cable_config_matches(entry_a, entry_b):
    """Return True if both circuit entries share the same CableType and Shared flag
    for every phase.  Quantity is intentionally excluded: shared cables are
    legitimately zeroed-out on subsequent conduits by the deduplication logic."""
    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
        pa = entry_a.get(phase, {})
        pb = entry_b.get(phase, {})
        if pa.get("CableType") != pb.get("CableType"):
            return False
        if bool(pa.get("Shared", False)) != bool(pb.get("Shared", False)):
            return False
    return True

def init_circuit_database(doc):
    json_path = get_database_path(doc)
    
    # If the JSON file already exists, load and return it
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                db = json.load(f)
                if isinstance(db, dict):
                    return db
        except Exception:
            pass

    # If it does not exist or failed to load, create and populate from model parameters
    db = {}
    # Maps circuit name -> list of conflicting entry dicts (only populated when configs differ)
    conflicting_circuits = {}
    
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
                                if isinstance(circuit, dict) and "Circuit" in circuit:
                                    c_name = str(circuit["Circuit"]).strip().upper()
                                    if not c_name:
                                        continue
                                    # Build normalised entry for this occurrence
                                    entry = {"Circuit": c_name}
                                    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                                        phase_data = circuit.get(phase)
                                        if isinstance(phase_data, dict):
                                            entry[phase] = {
                                                "Quantity": int(phase_data.get("Quantity", 1)),
                                                "Shared": bool(phase_data.get("Shared", False)),
                                                "CableType": str(phase_data.get("CableType", get_default_cable_type())).strip()
                                            }
                                        else:
                                            entry[phase] = {
                                                "Quantity": 1,
                                                "Shared": False,
                                                "CableType": get_default_cable_type()
                                            }
                                    if c_name not in db:
                                        # First time we see this circuit name
                                        db[c_name] = entry
                                    else:
                                        # Already seen — check for a cable-config conflict
                                        if not _cable_config_matches(db[c_name], entry):
                                            if c_name not in conflicting_circuits:
                                                conflicting_circuits[c_name] = [db[c_name]]
                                            conflicting_circuits[c_name].append(entry)
                                    # Duplicate name with matching config is intentional
                                    # (same circuit running through multiple conduits) — no action needed.
                    except Exception:
                        pass
    except Exception as e:
        print("Error populating database from model: {}".format(e))

    # Alert only when the same circuit name carries different cable configurations
    if conflicting_circuits:
        forms.alert(
            "The following circuit(s) have inconsistent cable configurations across conduits:\n\n{}\n\n"
            "Please review and fix them using Circuit Management.".format(
                ", ".join(sorted(conflicting_circuits.keys()))
            ),
            title="Cable Configuration Conflicts"
        )

    # Save initial database to JSON file
    try:
        with open(json_path, 'w') as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print("Error saving database: {}".format(e))
        
    return db

def save_circuit_database(doc, db):
    json_path = get_database_path(doc)
    try:
        with open(json_path, 'w') as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print("Error saving database: {}".format(e))


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
    def __init__(self, data, on_delete_callback, window=None):
        self.data = data
        self.on_delete_callback = on_delete_callback
        self.window = window
        self.current_circuit_name = data.get("Circuit", "")
        
        # Create Main Card Border
        self.border = Controls.Border()
        self.border.Background = Media.Brushes.White
        self.border.BorderBrush = _brush("#E2E8F0")
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
        btn_del.Background = _brush("#EF4444")
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
        lbl.Foreground = _brush("#1E293B")
        lbl.VerticalAlignment = Windows.VerticalAlignment.Center
        lbl.Margin = Windows.Thickness(0, 0, 8, 0)
        Controls.DockPanel.SetDock(lbl, Controls.Dock.Left)
        header_panel.Children.Add(lbl)
        
        # Plus Button to create a new circuit
        self.btn_add_circ = Controls.Button()
        self.btn_add_circ.Content = "+"
        self.btn_add_circ.Width = 24
        self.btn_add_circ.Height = 24
        self.btn_add_circ.Background = _brush("#10B981")
        self.btn_add_circ.Foreground = Media.Brushes.White
        self.btn_add_circ.BorderBrush = None
        self.btn_add_circ.FontWeight = Windows.FontWeights.Bold
        self.btn_add_circ.Margin = Windows.Thickness(5, 0, 5, 0)
        self.btn_add_circ.Click += self.create_new_circuit_clicked
        Controls.DockPanel.SetDock(self.btn_add_circ, Controls.Dock.Right)
        header_panel.Children.Add(self.btn_add_circ)
        
        # Circuit Name Dropdown (ComboBox)
        self.cb_circuit = Controls.ComboBox()
        self.cb_circuit.Height = 24
        self.cb_circuit.Padding = Windows.Thickness(4, 2, 4, 2)
        self.cb_circuit.VerticalAlignment = Windows.VerticalAlignment.Center
        
        # Gather all circuit names currently in database
        all_circuit_names = []
        if self.window and hasattr(self.window, "circuit_db"):
            db = self.window.circuit_db
            all_circuit_names = sorted(list(db.keys()))
            
        if self.current_circuit_name and self.current_circuit_name not in all_circuit_names:
            all_circuit_names.append(self.current_circuit_name)
            all_circuit_names = sorted(all_circuit_names)
            
        self.cb_circuit.ItemsSource = all_circuit_names
        self.cb_circuit.SelectedItem = self.current_circuit_name
        self.cb_circuit.SelectionChanged += self.on_circuit_selection_changed
        
        header_panel.Children.Add(self.cb_circuit)
        
        # Row 1: Multi-Column Phase Details Grid
        columns_grid = Controls.Grid()
        columns_grid.Margin = Windows.Thickness(0, 12, 0, 0)
        for _ in range(5):
            columns_grid.ColumnDefinitions.Add(Controls.ColumnDefinition())
            
        grid.SetRow(columns_grid, 1)
        grid.Children.Add(columns_grid)
        
        phases = ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]
        self.controls = {}
        
        default_cable = get_default_cable_type()
        
        for idx, phase in enumerate(phases):
            phase_data = data.get(phase, {"Quantity": 1, "Shared": False, "CableType": default_cable})
            
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
            phase_lbl.Foreground = _brush("#475569")
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
            cb_cable.SelectedItem = phase_data.get("CableType", default_cable)
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
        
    def on_circuit_selection_changed(self, sender, e):
        # Save current UI state for the old circuit before switching
        if self.current_circuit_name and self.window and hasattr(self.window, "circuit_db"):
            self.window.circuit_db[self.current_circuit_name] = self.get_data()
            
        selected_name = self.cb_circuit.SelectedItem
        if not selected_name:
            return
            
        self.current_circuit_name = selected_name
        self.data["Circuit"] = selected_name
        self.load_circuit_data(selected_name)
        
    def create_new_circuit_clicked(self, sender, e):
        if self.window:
            was_topmost = self.window.Topmost
            self.window.Topmost = False
        else:
            was_topmost = False
            
        try:
            new_name = forms.ask_for_string(
                prompt="Enter the name for the new Circuit ID:",
                title="Create New Circuit"
            )
        finally:
            if self.window:
                self.window.Topmost = was_topmost
                
        if not new_name:
            return
            
        new_name = new_name.strip().upper().replace(",", "-")
        if not new_name:
            return
            
        if self.window and hasattr(self.window, "circuit_db"):
            db = self.window.circuit_db
            
            if new_name not in db:
                default_cable = get_default_cable_type()
                db[new_name] = {
                    "Circuit": new_name,
                    "Phase 1": {"Quantity": 1, "Shared": False, "CableType": default_cable, "CableArea": CABLE_AREAS.get(default_cable, 0.0)},
                    "Phase 2": {"Quantity": 0, "Shared": False, "CableType": default_cable, "CableArea": CABLE_AREAS.get(default_cable, 0.0)},
                    "Phase 3": {"Quantity": 0, "Shared": False, "CableType": default_cable, "CableArea": CABLE_AREAS.get(default_cable, 0.0)},
                    "Neutral": {"Quantity": 1, "Shared": False, "CableType": default_cable, "CableArea": CABLE_AREAS.get(default_cable, 0.0)},
                    "Ground": {"Quantity": 1, "Shared": True, "CableType": default_cable, "CableArea": CABLE_AREAS.get(default_cable, 0.0)}
                }
            
            self.window.refresh_all_cards_circuit_dropdowns(self, new_name)
            
    def load_circuit_data(self, name):
        if self.window and hasattr(self.window, "circuit_db"):
            db = self.window.circuit_db
            if name in db:
                config = db[name]
                for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                    phase_data = config.get(phase)
                    if phase_data and phase in self.controls:
                        ctrl = self.controls[phase]
                        ctrl["qty"].Text = str(phase_data.get("Quantity", 1))
                        
                        c_type = phase_data.get("CableType")
                        cb_cable = ctrl["cable"]
                        if c_type in CABLE_TYPES:
                            cb_cable.SelectedItem = c_type
                        else:
                            cb_cable.SelectedItem = get_default_cable_type()
                            
                        ctrl["shared"].IsChecked = bool(phase_data.get("Shared", False))
        
    def get_data(self):
        res = {  # type: dict[str, any]
            "Circuit": self.cb_circuit.SelectedItem or self.current_circuit_name or ""
        }
        for phase, ctrl in self.controls.items():
            qty_str = ctrl["qty"].Text
            try:
                qty = int(qty_str)
            except ValueError:
                qty = 0
            
            c_type = ctrl["cable"].SelectedItem or get_default_cable_type()
            res[phase] = {
                "Quantity": qty,
                "Shared": bool(ctrl["shared"].IsChecked),
                "CableType": c_type,
                "CableArea": CABLE_AREAS.get(c_type, 0.0)
            }
        return res

# --- Main WPF Window ---
class ManageCablesWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name, conduits, initial_circuits, circuit_db):
        self.conduits = conduits
        self.cards = []
        self.loaded_circuit_names = {c["Circuit"] for c in initial_circuits} if initial_circuits else set()
        self.circuit_db = circuit_db
        
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Populate selected conduit label
        conduit_names = ["ID: {}".format(c.Id) for c in conduits]
        self.lblTargetConduits.Text = "Conduits (Total: {}): {}".format(len(conduits), ", ".join(conduit_names))
        
        # Load initial circuits
        if initial_circuits:
            for c_data in initial_circuits:
                self.add_circuit_card(c_data)
        self.update_empty_state()

    def add_circuit_card(self, data):
        card = CircuitCard(data, self.remove_circuit_card, window=self)
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

    def refresh_all_cards_circuit_dropdowns(self, target_card, select_name):
        all_names = set(self.circuit_db.keys())
        for card in self.cards:
            if card.current_circuit_name:
                all_names.add(card.current_circuit_name)
        if select_name:
            all_names.add(select_name)
            
        sorted_names = sorted(list(all_names))
        
        for card in self.cards:
            # Unsubscribe event to avoid triggering selection changed handling
            card.cb_circuit.SelectionChanged -= card.on_circuit_selection_changed
            
            curr_selected = card.cb_circuit.SelectedItem
            card.cb_circuit.ItemsSource = None
            card.cb_circuit.ItemsSource = sorted_names
            
            if card == target_card:
                card.cb_circuit.SelectedItem = select_name
                card.current_circuit_name = select_name
                card.data["Circuit"] = select_name
                card.load_circuit_data(select_name)
            else:
                if curr_selected in sorted_names:
                    card.cb_circuit.SelectedItem = curr_selected
                else:
                    card.cb_circuit.SelectedIndex = 0 if sorted_names else -1
                    
            # Re-subscribe event
            card.cb_circuit.SelectionChanged += card.on_circuit_selection_changed

    def AddCircuit_Click(self, sender, e):
        default_name = ""
        
        # Default starting values: copy from the last card if exists, otherwise load last used
        if self.cards:
            last_card_data = self.cards[-1].get_data()
            default_data = {
                "Circuit": default_name
            }
            for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                p_data = last_card_data.get(phase)
                if p_data:
                    default_data[phase] = {
                        "Quantity": p_data.get("Quantity", 1),
                        "Shared": p_data.get("Shared", False),
                        "CableType": p_data.get("CableType")
                    }
        else:
            default_data = load_last_used_cables()
            default_data["Circuit"] = default_name
            
        # Add the card
        self.add_circuit_card(default_data)
        
        # Refresh all other cards' dropdown lists
        self.refresh_all_cards_circuit_dropdowns(self.cards[-1], default_name)

    def AddCableType_Click(self, sender, e):
        # Temporarily disable Topmost so database window is drawn on top correctly
        was_topmost = self.Topmost
        self.Topmost = False
        try:
            # Locate 07_ManageCableDatabase.pushbutton directory relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            panel_dir = os.path.dirname(script_dir)
            db_dir = os.path.join(panel_dir, "07_ManageCableDatabase.pushbutton")
            db_script_path = os.path.join(db_dir, "script.py")
            db_xaml_path = os.path.join(db_dir, "ui.xaml")
            
            if os.path.exists(db_script_path) and os.path.exists(db_xaml_path):
                # Dynamically load the database management module.
                # Prefer importlib (CPython 3); fall back to imp for IronPython 2.7.
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location('cable_db_script', db_script_path)
                    db_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(db_module)
                except (ImportError, AttributeError):
                    import imp  # noqa: F401  (IronPython 2.7 fallback)
                    db_module = imp.load_source('cable_db_script', db_script_path)
                # Show the database management window modal dialog
                win_db = db_module.ManageCableDatabaseWindow(db_xaml_path)
                win_db.ShowDialog()
            else:
                forms.alert("Could not locate the Cable Database Management pushbutton script or UI file.", title="File Not Found")
                return

            # Reload updated cable database lists from file / model
            global CABLE_TYPES_DB, CABLE_TYPES, CABLE_AREAS
            CABLE_TYPES_DB = load_cable_types(doc)
            CABLE_TYPES = [x["Name"] for x in CABLE_TYPES_DB]
            CABLE_AREAS = {x["Name"]: x["CableArea"] for x in CABLE_TYPES_DB}
            
            # Dynamically refresh all active circuit card ComboBoxes with the updated list
            for card in self.cards:
                for phase, ctrl in card.controls.items():
                    cb = ctrl["cable"]
                    selected = cb.SelectedItem
                    
                    # Refresh ItemsSource and restore selected item if it still exists
                    cb.ItemsSource = None
                    cb.ItemsSource = CABLE_TYPES
                    
                    if selected in CABLE_TYPES:
                        cb.SelectedItem = selected
                    else:
                        cb.SelectedItem = get_default_cable_type()
        finally:
            self.Topmost = was_topmost

    def ClearCables_Click(self, sender, e):
        # Prompt user to confirm clearing
        was_topmost = self.Topmost
        self.Topmost = False
        try:
            if not forms.alert(
                "Are you sure you want to clear all cables and circuits from the selected {} conduit(s)/fitting(s)?\n\n"
                "This will set the 'GPC-Cables' parameter value to empty on all selected elements.".format(len(self.conduits)),
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
                    
                    # If it's a conduit fitting, clear the Comments parameter as well
                    is_fitting = c.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_ConduitFitting)
                    if is_fitting:
                        comments_param = c.LookupParameter("Comments")
                        if comments_param and not comments_param.IsReadOnly:
                            comments_param.Set("")

            forms.alert("Cables cleared successfully from {} conduit(s)/fitting(s)!".format(len(self.conduits)), title="Success")
            self.Close()
        finally:
            self.Topmost = was_topmost

    def Cancel_Click(self, sender, e):
        self.Close()

    def Save_Click(self, sender, e):
        # 1. Collect and validate data
        final_circuits = []
        for card in self.cards:
            data = card.get_data()
            circuit_name = str(data["Circuit"]).strip().upper()
            if not circuit_name:
                forms.alert("Please provide a valid Circuit ID for all circuits.", title="Validation Error")
                return
            
            # Check integer inputs
            for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                qty = data[phase]["Quantity"]
                if qty < 0:
                    forms.alert("Quantities cannot be negative (found on circuit {}).".format(circuit_name), title="Validation Error")
                    return
            
            data["Circuit"] = circuit_name
            final_circuits.append(data)

        # Update and save the circuit database
        for data in final_circuits:
            c_name = data["Circuit"]
            self.circuit_db[c_name] = data
        save_circuit_database(doc, self.circuit_db)

        # Persist the configuration of the last circuit for future runs
        if final_circuits:
            save_last_used_cables(final_circuits[-1])

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
                        "CableType": str(phase_data.get("CableType", get_default_cable_type())).strip()
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

                # Update Comments field of Conduit Fittings with unique circuit names
                is_fitting = c.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_ConduitFitting)
                if is_fitting:
                    comments_param = c.LookupParameter("Comments")
                    if comments_param and not comments_param.IsReadOnly:
                        seen_names = set()
                        unique_names = []
                        for circuit in conduit_circuits:
                            c_name = circuit.get("Circuit", "")
                            if c_name:
                                c_name_str = str(c_name).strip()
                                if c_name_str and c_name_str not in seen_names:
                                    seen_names.add(c_name_str)
                                    unique_names.append(c_name_str)
                        comments_param.Set(", ".join(unique_names))

            # 3. Scan the rest of the model for other conduits/fittings containing the saved circuits and synchronize them
            other_sync_count = 0
            selected_ids = {el.Id.IntegerValue for el in self.conduits}
            saved_names_map = {c["Circuit"]: c for c in processed_final_circuits}

            if saved_names_map:
                all_conduits = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
                all_fittings = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
                all_elems = list(all_conduits) + list(all_fittings)

                for el in all_elems:
                    if el.Id.IntegerValue in selected_ids:
                        continue

                    param = el.LookupParameter("GPC-Cables")
                    if not param:
                        continue

                    val = param.AsString()
                    if not val:
                        continue

                    try:
                        circuits = json.loads(val)
                        if isinstance(circuits, list) and circuits:
                            modified = False
                            for circuit in circuits:
                                if isinstance(circuit, dict) and "Circuit" in circuit:
                                    c_name = str(circuit["Circuit"]).strip().upper()
                                    if c_name in saved_names_map:
                                        matching_new_c = saved_names_map[c_name]
                                        for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                                            phase_data = matching_new_c.get(phase)
                                            if phase_data:
                                                circuit[phase] = {
                                                    "Quantity": phase_data.get("Quantity", 1),
                                                    "Shared": bool(phase_data.get("Shared", False)),
                                                    "CableType": str(phase_data.get("CableType", get_default_cable_type())).strip()
                                                }
                                                modified = True

                            if modified:
                                # Re-run duplicate shared cable deduplication within this conduit/fitting
                                seen_cables = set()
                                for circuit in circuits:
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

                                # Set updated parameters
                                param.Set(json.dumps(circuits))

                                param_tag = el.LookupParameter("GPC-Cables-Tag")
                                if param_tag:
                                    param_tag.Set(generate_cables_tag_text(circuits))

                                # Update Comments if fitting
                                is_fitting = el.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_ConduitFitting)
                                if is_fitting:
                                    comments_param = el.LookupParameter("Comments")
                                    if comments_param and not comments_param.IsReadOnly:
                                        seen_names = set()
                                        unique_names = []
                                        for c_elem in circuits:
                                            name = c_elem.get("Circuit", "")
                                            if name:
                                                name_str = str(name).strip()
                                                if name_str and name_str not in seen_names:
                                                    seen_names.add(name_str)
                                                    unique_names.append(name_str)
                                        comments_param.Set(", ".join(unique_names))

                                other_sync_count += 1
                    except Exception as ex:
                        print("Error updating other elements in sync: {}".format(ex))

        if other_sync_count > 0:
            forms.alert(
                "Cables saved successfully to {} selected conduit(s)/fitting(s)!\n\n"
                "Also synchronized {} other conduit(s)/fitting(s) carrying the updated circuits in the active model.".format(
                    len(self.conduits), other_sync_count
                ),
                title="Success"
            )
        else:
            forms.alert("Cables saved successfully to {} conduit(s)/fitting(s)!".format(len(self.conduits)), title="Success")
        self.Close()


def main():
    global CABLE_TYPES_DB, CABLE_TYPES, CABLE_AREAS
    
    # Load cable types now (lazy) -- this is the first moment we actually need them.
    # Kept out of module scope so the file-read/model-scan doesn't run on every
    # pyRevit script reload, only when the button is pressed.
    CABLE_TYPES_DB = load_cable_types(doc)
    CABLE_TYPES = [x["Name"] for x in CABLE_TYPES_DB]
    CABLE_AREAS  = {x["Name"]: x["CableArea"] for x in CABLE_TYPES_DB}
    
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
                el = doc.GetElement(ref.ElementId)
                if el and el.Category:
                    cat_id = el.Category.Id.IntegerValue
                    if cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]:
                        conduits.append(el)
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
    
    if len(conduits) == 1:
        existing_json_str = param.AsString() or ""
        if existing_json_str:
            try:
                initial_circuits = json.loads(existing_json_str)
                if not isinstance(initial_circuits, list):
                    initial_circuits = []
            except Exception:
                initial_circuits = []

    # Initialise the circuit database here (before the window) so the model scan
    # completes before the UI is constructed and doesn't block the WPF thread.
    circuit_db = init_circuit_database(doc)

    # Launch WPF UI
    xaml_file = os.path.join(os.path.dirname(__file__), "ui.xaml")
    win = ManageCablesWindow(xaml_file, conduits, initial_circuits, circuit_db)
    win.ShowDialog()

if __name__ == '__main__':
    main()
