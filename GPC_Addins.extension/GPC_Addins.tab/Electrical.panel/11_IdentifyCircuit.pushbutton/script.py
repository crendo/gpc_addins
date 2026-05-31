# -*- coding: utf-8 -*-
"""Identify and highlight all conduits and conduit fittings belonging to a selected circuit in the active view."""

__title__ = 'Identify\nCircuit'
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
import System.Windows.Shapes as Shapes  # type: ignore
from pyrevit import revit, DB, UI, forms, script  # type: ignore

doc = revit.doc
uidoc = revit.uidoc

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

# --- Wrapper for ListBox binding ---
class CircuitListItem(object):
    def __init__(self, name, element_count, config_info):
        self.Name = name
        self.ElementCount = element_count
        self.DisplayName = "{} ({} element{})".format(
            name, 
            element_count, 
            "" if element_count == 1 else "s"
        )
        self.ConfigInfo = config_info

# --- Cable type helpers ---
def load_cable_types(doc_obj):
    _root = os.path.abspath(__file__)
    for _ in range(5):
        _root = os.path.dirname(_root)
    
    shared_params_dir = os.path.join(_root, "shared_parameters")
    cable_types_path = os.path.join(shared_params_dir, "cable_types.json")
        
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
            
    # Default fallback
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
    return [{"Name": k, "CableArea": DEFAULT_CABLE_AREAS[k]} for k in sorted(DEFAULT_CABLE_AREAS.keys())]

# --- Database Helper Functions ---
def get_database_path(doc_obj):
    if not doc_obj.PathName:
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
    
    return os.path.splitext(doc_obj.PathName)[0] + "_circuits.json"

def _cable_config_matches(entry_a, entry_b):
    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
        pa = entry_a.get(phase, {})
        pb = entry_b.get(phase, {})
        if pa.get("CableType") != pb.get("CableType"):
            return False
        if bool(pa.get("Shared", False)) != bool(pb.get("Shared", False)):
            return False
    return True

def _build_circuit_entry_from_model(circuit, default_cable):
    c_name = str(circuit["Circuit"]).strip().upper()
    entry = {"Circuit": c_name}
    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
        phase_data = circuit.get(phase)
        if phase_data and hasattr(phase_data, 'get'):
            qty = int(phase_data.get("Quantity", 1))
            is_shared = bool(phase_data.get("Shared", False))
            
            # If a cable is shared and has 0 quantity on this segment,
            # its logical quantity for the circuit configuration is 1.
            if is_shared and qty == 0 and phase_data.get("CableType"):
                qty = 1
                
            entry[phase] = {
                "Quantity": qty,
                "Shared": is_shared,
                "CableType": str(phase_data.get("CableType", default_cable)).strip()
            }
        else:
            entry[phase] = {
                "Quantity": 1,
                "Shared": False,
                "CableType": default_cable
            }
    return c_name, entry

def _scan_model_circuits(doc_obj, default_cable):
    db_from_model = {}
    conflicting_circuits = {}

    try:
        conduits = (DB.FilteredElementCollector(doc_obj)
                    .OfCategory(DB.BuiltInCategory.OST_Conduit)
                    .WhereElementIsNotElementType()
                    .ToElements())
        fittings = (DB.FilteredElementCollector(doc_obj)
                    .OfCategory(DB.BuiltInCategory.OST_ConduitFitting)
                    .WhereElementIsNotElementType()
                    .ToElements())

        for el in list(conduits) + list(fittings):
            param = el.LookupParameter("GPC-Cables")
            if not param:
                continue
            val = param.AsString()
            if not val:
                continue
            try:
                circuits = json.loads(val)
                if not isinstance(circuits, list):
                    continue
                for circuit in circuits:
                    if not (isinstance(circuit, dict) and "Circuit" in circuit):
                        continue
                    c_name = str(circuit["Circuit"]).strip().upper()
                    if not c_name:
                        continue
                    _, entry = _build_circuit_entry_from_model(circuit, default_cable)
                    if c_name not in db_from_model:
                        db_from_model[c_name] = entry
                    else:
                        existing_entry = db_from_model[c_name]
                        for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                            new_phase_data = entry.get(phase, {})
                            existing_phase_data = existing_entry.get(phase, {})
                            
                            new_qty = new_phase_data.get("Quantity", 0)
                            existing_qty = existing_phase_data.get("Quantity", 0)
                            
                            if new_qty > existing_qty or (existing_qty == 0 and new_qty > 0):
                                # Update to higher quantity and use its cable configurations
                                existing_entry[phase] = {
                                    "Quantity": new_qty,
                                    "Shared": new_phase_data.get("Shared", False),
                                    "CableType": new_phase_data.get("CableType", default_cable)
                                }
                                
                            # Check for genuine cable configuration conflicts (both > 0 but different CableTypes)
                            if new_qty > 0 and existing_qty > 0:
                                if new_phase_data.get("CableType") != existing_phase_data.get("CableType"):
                                    if c_name not in conflicting_circuits:
                                        conflicting_circuits[c_name] = [existing_entry]
                                    conflicting_circuits[c_name].append(entry)
            except Exception:
                pass
    except Exception as e:
        print("Error scanning model circuits: {}".format(e))

    return db_from_model, conflicting_circuits

def init_circuit_database(doc_obj):
    json_path = get_database_path(doc_obj)
    loaded_cables = load_cable_types(doc_obj)
    cable_type_names = [x["Name"] for x in loaded_cables]
    preferred = "THW #12 AWG (Elec/Ilum)"
    default_cable = preferred if preferred in cable_type_names else (cable_type_names[0] if cable_type_names else "#12 AWG")

    db = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                loaded_db = json.load(f)
            if isinstance(loaded_db, dict):
                db = loaded_db
        except Exception:
            pass

    db_from_model, conflicting_circuits = _scan_model_circuits(doc_obj, default_cable)

    # Merge and update existing entries in the database with non-zero model quantities
    for c_name, entry in db_from_model.items():
        if c_name not in db:
            db[c_name] = entry
        else:
            db_entry = db[c_name]
            for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                model_phase = entry.get(phase, {})
                db_phase = db_entry.get(phase, {})
                
                model_qty = model_phase.get("Quantity", 0)
                db_qty = db_phase.get("Quantity", 0)
                
                if model_qty > db_qty:
                    db_entry[phase] = {
                        "Quantity": model_qty,
                        "Shared": model_phase.get("Shared", db_phase.get("Shared", False)),
                        "CableType": model_phase.get("CableType", db_phase.get("CableType", default_cable))
                    }

    try:
        with open(json_path, 'w') as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print("Error saving database: {}".format(e))
        
    return db

# --- Scanning circuits and elements mapping ---
def scan_circuits_to_elements(doc_obj):
    """Scan the model and build an exact mapping of circuit_name (upper) -> list of elements."""
    mapping = {}
    try:
        conduits = (DB.FilteredElementCollector(doc_obj)
                    .OfCategory(DB.BuiltInCategory.OST_Conduit)
                    .WhereElementIsNotElementType()
                    .ToElements())
        fittings = (DB.FilteredElementCollector(doc_obj)
                    .OfCategory(DB.BuiltInCategory.OST_ConduitFitting)
                    .WhereElementIsNotElementType()
                    .ToElements())

        for el in list(conduits) + list(fittings):
            param = el.LookupParameter("GPC-Cables")
            if not param:
                continue
            val = param.AsString()
            if not val:
                continue
            try:
                circuits = json.loads(val)
                if isinstance(circuits, list):
                    for circuit in circuits:
                        if isinstance(circuit, dict) and "Circuit" in circuit:
                            c_name = str(circuit["Circuit"]).strip().upper()
                            if c_name:
                                if c_name not in mapping:
                                    mapping[c_name] = []
                                mapping[c_name].append(el)
            except Exception:
                pass
    except Exception as e:
        print("Error scanning circuits to elements mapping: {}".format(e))
    return mapping

# --- Format Summary Helper ---
def format_circuit_summary(config):
    if not config:
        return "No active cables found on the conduits of this circuit."
    lines = []
    
    # Map technical keys to standard user-facing electrical terms
    role_mapping = {
        "Phase 1": "Hot (Phase 1)",
        "Phase 2": "Hot (Phase 2)",
        "Phase 3": "Hot (Phase 3)",
        "Neutral": "Neutral",
        "Ground": "Ground"
    }
    
    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
        phase_data = config.get(phase)
        role_label = role_mapping.get(phase, phase)
        if phase_data:
            qty = phase_data.get("Quantity", 0)
            if qty > 0:
                is_shared = " (Shared)" if phase_data.get("Shared", False) else ""
                lines.append("{}: {}x {}{}".format(role_label, qty, phase_data.get("CableType", ""), is_shared))
    if not lines:
        return "No active cables configured for this circuit."
    return "\n".join(lines)

# --- WPF Window Class ---
class CircuitHighlightWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name, circuit_db, circuits_to_elements):
        self.circuit_db = circuit_db
        self.circuits_to_elements = circuits_to_elements
        
        # Build unified list items
        self.circuit_list = []
        all_circuit_names = set(circuit_db.keys()) | set(circuits_to_elements.keys())
        
        for name in sorted(all_circuit_names):
            el_count = len(circuits_to_elements.get(name, []))
            config = circuit_db.get(name, {})
            self.circuit_list.append(CircuitListItem(name, el_count, config))
            
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Populate color combobox with visual stackpanels
        self.populate_colors()
        
        # Load last used settings
        self.load_settings()
        
        # Attach slider value change event
        self.sliderWeight.ValueChanged += self.slider_changed
        self.lblWeightVal.Text = str(int(self.sliderWeight.Value))
        
        self.refresh_list()

    def populate_colors(self):
        for c in COLORS_LIST:
            panel = Controls.StackPanel()
            panel.Orientation = Controls.Orientation.Horizontal
            panel.Height = 24
            
            # Colored rectangle representation
            rect = Shapes.Rectangle()
            rect.Width = 18
            rect.Height = 14
            rect.Margin = Windows.Thickness(2, 5, 10, 5)
            rect.Fill = Media.BrushConverter().ConvertFromString(c["Hex"])
            rect.RadiusX = 2
            rect.RadiusY = 2
            
            # Label
            lbl = Controls.TextBlock()
            lbl.Text = c["Name"]
            lbl.VerticalAlignment = Windows.VerticalAlignment.Center
            lbl.Foreground = Media.BrushConverter().ConvertFromString("#1E293B")
            
            panel.Children.Add(rect)
            panel.Children.Add(lbl)
            
            self.cbColor.Items.Add(panel)

    def load_settings(self):
        _root = os.path.abspath(__file__)
        for _ in range(5):
            _root = os.path.dirname(_root)
        
        shared_params_dir = os.path.join(_root, "shared_parameters")
        settings_path = os.path.join(shared_params_dir, "last_used_circuit_highlight_settings.json")
        
        default_color_idx = 0
        default_weight = 8
        
        if os.path.exists(settings_path):
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
        _root = os.path.abspath(__file__)
        for _ in range(5):
            _root = os.path.dirname(_root)
        
        shared_params_dir = os.path.join(_root, "shared_parameters")
        settings_path = os.path.join(shared_params_dir, "last_used_circuit_highlight_settings.json")
        
        try:
            if not os.path.exists(shared_params_dir):
                os.makedirs(shared_params_dir)
            
            settings = {
                "color_name": color_name,
                "line_weight": weight
            }
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception:
            pass

    def refresh_list(self):
        search_term = self.txtSearch.Text.strip().upper()
        if search_term:
            filtered = [x for x in self.circuit_list if search_term in x.Name.upper()]
        else:
            filtered = list(self.circuit_list)
            
        filtered.sort(key=lambda x: x.Name)
        self.lstCircuits.ItemsSource = None
        self.lstCircuits.ItemsSource = filtered

    def Search_TextChanged(self, sender, e):
        if hasattr(self, "lblSearchPlaceholder") and self.lblSearchPlaceholder:
            if self.txtSearch.Text:
                self.lblSearchPlaceholder.Visibility = Windows.Visibility.Collapsed
            else:
                self.lblSearchPlaceholder.Visibility = Windows.Visibility.Visible
        self.refresh_list()

    def slider_changed(self, sender, e):
        if hasattr(self, 'lblWeightVal') and self.lblWeightVal:
            self.lblWeightVal.Text = str(int(self.sliderWeight.Value))

    def Circuits_SelectionChanged(self, sender, e):
        selected_item = self.lstCircuits.SelectedItem
        if selected_item:
            self.gridEmptyState.Visibility = Windows.Visibility.Collapsed
            self.gridSettings.Visibility = Windows.Visibility.Visible
            
            self.txtSelectedName.Text = selected_item.Name
            
            elements = self.circuits_to_elements.get(selected_item.Name.upper(), [])
            count = len(elements)
            self.txtSummaryInfo.Text = "Contains {} conduit/fitting element{} in this model.".format(
                count, 
                "" if count == 1 else "s"
            )
            
            # Read the cable summary directly from GPC-Cables-Tag.
            # The tag already stores the correctly aggregated string per element,
            # e.g. "C20 (2THHN #10, 1THHN #10 C)". We extract the cable list
            # from the first element whose tag contains the selected circuit name.
            cable_summary = None
            circuit_name_upper = selected_item.Name.strip().upper()
            for el in elements:
                param_tag = el.LookupParameter("GPC-Cables-Tag")
                if not param_tag:
                    continue
                tag_value = param_tag.AsString()
                if not tag_value:
                    continue
                # The tag lists multiple circuits separated by "; "
                # e.g. "C20 (1THHN #10, 1THHN #10 C); C21 (2THHN #12, 1THHN #12 C)"
                # Find the segment that starts with our circuit name
                for segment in tag_value.split("; "):
                    segment = segment.strip()
                    seg_upper = segment.upper()
                    if seg_upper.startswith(circuit_name_upper):
                        # Extract the cable list inside the parentheses
                        paren_start = segment.find("(")
                        paren_end = segment.rfind(")")
                        if paren_start != -1 and paren_end > paren_start:
                            cable_summary = segment[paren_start + 1:paren_end].strip()
                        else:
                            cable_summary = segment
                        break
                if cable_summary is not None:
                    break
            
            if cable_summary:
                # Format each comma-separated entry on its own line.
                # The tag uses a trailing " C" to mark shared cables (Compartido);
                # translate that to a readable "(Shared)" label.
                lines = []
                for part in cable_summary.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    if part.endswith(" C"):
                        part = part[:-2].rstrip() + " (Shared)"
                    lines.append(part)
                self.lblDetailsText.Text = "\n".join(lines)
            else:
                # Fall back to the database ConfigInfo summary if no tag found
                self.lblDetailsText.Text = format_circuit_summary(selected_item.ConfigInfo)
        else:
            self.gridEmptyState.Visibility = Windows.Visibility.Visible
            self.gridSettings.Visibility = Windows.Visibility.Collapsed


    def Close_Click(self, sender, e):
        self.Close()

    def Clear_Click(self, sender, e):
        # 1. Collect all Conduits and Conduit Fittings in the active view
        from System.Collections.Generic import List
        cats = [
            DB.BuiltInCategory.OST_Conduit,
            DB.BuiltInCategory.OST_ConduitFitting
        ]
        cat_list = List[DB.ElementId]()
        for c in cats:
            cat_list.Add(DB.ElementId(c))
            
        filter_multi = DB.ElementMulticategoryFilter(cat_list)
        collector = DB.FilteredElementCollector(doc, doc.ActiveView.Id)\
                      .WherePasses(filter_multi)\
                      .WhereElementIsNotElementType()

        # 2. Reset overrides in a Revit Transaction
        t = DB.Transaction(doc, "Clear Conduit Circuit Highlights")
        t.Start()
        
        reset_override = DB.OverrideGraphicSettings()
        count = 0
        for elem in collector:
            doc.ActiveView.SetElementOverrides(elem.Id, reset_override)
            count += 1
            
        t.Commit()
        
        forms.alert(
            "Conduit circuit highlights cleared successfully!\n\n"
            "Reset elements in active view: {}".format(count), 
            title="Highlights Cleared"
        )

    def Highlight_Click(self, sender, e):
        selected_item = self.lstCircuits.SelectedItem
        if not selected_item:
            forms.alert("Please select a circuit from the left list to highlight.", title="No Selection")
            return
            
        elements = self.circuits_to_elements.get(selected_item.Name.upper(), [])
        if not elements:
            forms.alert(
                "Circuit '{}' is not assigned to any conduits or fittings in this model.\n\n"
                "To assign circuits to conduits, please use the Cable Management or Circuit Management tools first.".format(selected_item.Name),
                title="No Placed Elements"
            )
            return
            
        idx = self.cbColor.SelectedIndex
        if idx >= 0 and idx < len(COLORS_LIST):
            path_color = COLORS_LIST[idx]["Color"]
            color_name = COLORS_LIST[idx]["Name"]
        else:
            path_color = DB.Color(255, 128, 0)
            color_name = "Amber / Orange"
            
        line_weight = int(self.sliderWeight.Value)
        
        # Save to settings history
        self.save_settings(color_name, line_weight)
        
        # Perform graphic override changes in Revit Transaction
        t = DB.Transaction(doc, "Highlight Circuit " + selected_item.Name)
        t.Start()
        
        override = DB.OverrideGraphicSettings()
        override.SetProjectionLineColor(path_color)
        override.SetProjectionLineWeight(line_weight)
        
        from System.Collections.Generic import List
        selection_ids = List[DB.ElementId]()
        
        count = 0
        for el in elements:
            doc.ActiveView.SetElementOverrides(el.Id, override)
            selection_ids.Add(el.Id)
            count += 1
            
        t.Commit()
        
        # Select the elements programmatically in Revit
        uidoc.Selection.SetElementIds(selection_ids)
        
        forms.alert(
            "Circuit '{}' successfully identified and highlighted!\n\n"
            "Color override: {} (weight {})\n"
            "Total elements overridden and selected in active view: {}".format(
                selected_item.Name, 
                color_name, 
                line_weight, 
                count
            ),
            title="Circuit Highlighted"
        )
        
        # Optionally close window or keep it open?
        # Standard is to keep it open so the user can easily select and highlight other circuits,
        # or clear them, without having to re-launch the dialog constantly! This is extremely helpful!

def main():
    # Load and sync the circuit database
    circuit_db = init_circuit_database(doc)
    
    # Scan the model for conduits and fittings associated with each circuit
    circuits_to_elements = scan_circuits_to_elements(doc)
    
    xaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.xaml")
    win = CircuitHighlightWindow(xaml_file, circuit_db, circuits_to_elements)
    win.ShowDialog()

if __name__ == '__main__':
    main()
