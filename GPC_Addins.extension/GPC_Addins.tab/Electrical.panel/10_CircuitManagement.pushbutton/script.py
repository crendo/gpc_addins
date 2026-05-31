# -*- coding: utf-8 -*-
"""Manage, search, add, edit, or delete Project Circuit definitions."""

__title__ = 'Circuit\nManagement'
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
from pyrevit import revit, DB, UI, forms, script  # type: ignore

doc = revit.doc

# --- Wrapper for ListBox binding ---
class CircuitListItem(object):
    def __init__(self, name):
        self.Name = name

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


def _build_circuit_entry_from_model(circuit, default_cable):
    """Build a normalised circuit dict from a raw model circuit dict."""
    c_name = str(circuit["Circuit"]).strip().upper()
    entry = {"Circuit": c_name}
    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
        phase_data = circuit.get(phase)
        if isinstance(phase_data, dict):
            entry[phase] = {
                "Quantity": int(phase_data.get("Quantity", 1)),
                "Shared": bool(phase_data.get("Shared", False)),
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
    """Scan all conduits and fittings and return (db_from_model, conflicting_circuits).

    db_from_model       – dict keyed by upper-cased circuit name (first-seen entry).
    conflicting_circuits – dict of circuit name -> list of entries whose CableType or
                           Shared flags differ from the first-seen entry.  An empty dict
                           means every repeated occurrence is consistent (which is the
                           normal case for a circuit running through many conduits).
    """
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
    """Load the JSON circuit database and merge any circuits found in the model
    that are not yet represented in the JSON.  This prevents a misconstruced or
    stale JSON from hiding circuits that already exist on conduits/fittings.

    Strategy
    --------
    1. Load the JSON file if it exists (the *authoritative* cable configuration).
    2. Scan the model for all circuits stored in GPC-Cables parameters.
    3. For every model circuit that is **not already in the JSON database**,
       add it using the cable type data from the model parameter.
    4. If the JSON did not exist at all, build the database entirely from the model.
    5. Save the (possibly augmented) database back to disk.
    """
    json_path = get_database_path(doc_obj)

    # Determine default cable type from the shared cable_types.json
    loaded_cables = load_cable_types(doc_obj)
    cable_type_names = [x["Name"] for x in loaded_cables]
    preferred = "THW #12 AWG (Elec/Ilum)"
    default_cable = preferred if preferred in cable_type_names else (cable_type_names[0] if cable_type_names else "#12 AWG")

    # --- Step 1: Try to load existing JSON database ---
    db = {}
    json_existed = False
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                loaded_db = json.load(f)
            if isinstance(loaded_db, dict):
                db = loaded_db
                json_existed = True
        except Exception:
            pass  # treat as missing and rebuild from model

    # --- Step 2: Scan the model ---
    db_from_model, conflicting_circuits = _scan_model_circuits(doc_obj, default_cable)

    # --- Step 3: Merge model circuits that are missing or update non-zero quantities ---
    added_from_model = []
    for c_name, entry in db_from_model.items():
        if c_name not in db:
            db[c_name] = entry
            added_from_model.append(c_name)
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

    # --- Step 4: Alert when the same circuit name has different cable configs across conduits ---
    if conflicting_circuits:
        forms.alert(
            "The following circuit(s) have inconsistent cable configurations across conduits:\n\n{}\n\n"
            "Please review and fix them using Circuit Management.".format(
                ", ".join(sorted(conflicting_circuits.keys()))
            ),
            title="Cable Configuration Conflicts"
        )

    # Inform the user if new circuits were merged in from the model
    if added_from_model and json_existed:
        forms.alert(
            "The following circuit(s) were found in the model but were missing from the "
            "saved database and have been added automatically:\n\n{}".format(
                "\n".join(sorted(added_from_model))
            ),
            title="Circuits Added from Model"
        )

    # --- Step 5: Save augmented database to disk ---
    try:
        with open(json_path, 'w') as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print("Error saving database: {}".format(e))
        
    return db


def save_circuit_database(doc_obj, db):
    json_path = get_database_path(doc_obj)
    try:
        with open(json_path, 'w') as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print("Error saving database: {}".format(e))

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

# --- Main WPF Window Class ---
class CircuitManagementWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name, circuit_db):
        self.circuit_db = circuit_db
        self.renamed_circuits = {}
        self.deleted_circuits = set()
        
        # Load cable types
        loaded_cables = load_cable_types(doc)
        self.cable_types = [x["Name"] for x in loaded_cables]
        
        # Load circuit list items
        self.circuit_list = [CircuitListItem(k) for k in sorted(self.circuit_db.keys())]
        self.current_circuit_name = None
        
        # Initialize forms window
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Populate Comboboxes
        for phase in ["Phase1", "Phase2", "Phase3", "Neutral", "Ground"]:
            cb = getattr(self, "cbCable_" + phase)
            cb.ItemsSource = self.cable_types
            
        self.refresh_list()

    def refresh_list(self):
        search_term = self.txtSearch.Text.strip().upper()
        if search_term:
            filtered = [x for x in self.circuit_list if search_term in x.Name.upper()]
        else:
            filtered = list(self.circuit_list)
            
        filtered.sort(key=lambda x: x.Name)
        self.lstCircuits.ItemsSource = None
        self.lstCircuits.ItemsSource = filtered

    def get_default_cable(self):
        preferred = "THW #12 AWG (Elec/Ilum)"
        if preferred in self.cable_types:
            return preferred
        if self.cable_types:
            return self.cable_types[0]
        return "#12 AWG"

    def parse_qty(self, text):
        try:
            val = int(text)
            return val if val >= 0 else 0
        except ValueError:
            return 0

    def Search_TextChanged(self, sender, e):
        if hasattr(self, "lblSearchPlaceholder") and self.lblSearchPlaceholder:
            if self.txtSearch.Text:
                self.lblSearchPlaceholder.Visibility = Windows.Visibility.Collapsed
            else:
                self.lblSearchPlaceholder.Visibility = Windows.Visibility.Visible
        self.refresh_list()

    def save_current_editor_state(self):
        if self.current_circuit_name is not None:
            # Re-read editor values and write back to database
            config = {
                "Circuit": self.current_circuit_name
            }
            for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                phase_suffix = phase.replace(" ", "")
                qty_txt = getattr(self, "txtQty_" + phase_suffix).Text
                qty = self.parse_qty(qty_txt)
                
                cb = getattr(self, "cbCable_" + phase_suffix)
                cable_type = cb.SelectedItem or self.get_default_cable()
                
                chk = getattr(self, "chkShared_" + phase_suffix)
                is_shared = bool(chk.IsChecked)
                
                config[phase] = {
                    "Quantity": qty,
                    "Shared": is_shared,
                    "CableType": cable_type
                }
            self.circuit_db[self.current_circuit_name] = config

    def Circuits_SelectionChanged(self, sender, e):
        # Save previous circuit state first
        self.save_current_editor_state()
        
        selected_item = self.lstCircuits.SelectedItem
        if selected_item:
            self.gridEmptyState.Visibility = Windows.Visibility.Collapsed
            self.gridEditor.Visibility = Windows.Visibility.Visible
            
            name = selected_item.Name
            self.current_circuit_name = name
            
            # Populate editing fields
            self.txtCircuitName.Text = name
            config = self.circuit_db[name]
            
            for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                phase_suffix = phase.replace(" ", "")
                phase_data = config.get(phase, {})
                
                txt_qty = getattr(self, "txtQty_" + phase_suffix)
                txt_qty.Text = str(phase_data.get("Quantity", 1))
                
                cb = getattr(self, "cbCable_" + phase_suffix)
                c_type = phase_data.get("CableType", self.get_default_cable())
                if c_type in self.cable_types:
                    cb.SelectedItem = c_type
                else:
                    cb.SelectedItem = self.get_default_cable()
                    
                chk = getattr(self, "chkShared_" + phase_suffix)
                chk.IsChecked = bool(phase_data.get("Shared", False))
        else:
            self.gridEmptyState.Visibility = Windows.Visibility.Visible
            self.gridEditor.Visibility = Windows.Visibility.Collapsed
            self.current_circuit_name = None

    def AddCircuit_Click(self, sender, e):
        # Save current state first
        self.save_current_editor_state()
        
        # Generate a unique circuit name
        idx = 1
        new_name = "CIRC-NEW-{}".format(idx)
        while new_name in self.circuit_db:
            idx += 1
            new_name = "CIRC-NEW-{}".format(idx)
            
        # Initialize in database
        default_cable = self.get_default_cable()
        config = {
            "Circuit": new_name
        }
        for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
            config[phase] = {
                "Quantity": 1,
                "Shared": False,
                "CableType": default_cable
            }
        
        self.circuit_db[new_name] = config
        
        # Add to list wrapper
        new_item = CircuitListItem(new_name)
        self.circuit_list.append(new_item)
        self.refresh_list()
        
        # Select the newly created circuit in the list box
        for item in self.lstCircuits.ItemsSource:
            if item.Name == new_name:
                self.lstCircuits.SelectedItem = item
                self.lstCircuits.ScrollIntoView(item)
                break

    def DeleteCircuit_Click(self, sender, e):
        selected_item = self.lstCircuits.SelectedItem
        if not selected_item:
            forms.alert("Please select a circuit from the list to delete.", title="No Selection")
            return
            
        name = selected_item.Name
        
        was_topmost = self.Topmost
        self.Topmost = False
        try:
            if not forms.alert("Are you sure you want to permanently delete circuit '{}'?".format(name), yes=True, no=True, title="Confirm Delete"):
                return
                
            # Track deletion
            name_upper = name.strip().upper()
            self.deleted_circuits.add(name_upper)
            for old_name, new_name in list(self.renamed_circuits.items()):
                if new_name.strip().upper() == name_upper:
                    self.deleted_circuits.add(old_name.strip().upper())

            # Remove from database and list
            if name in self.circuit_db:
                del self.circuit_db[name]
                
            for item in list(self.circuit_list):
                if item.Name == name:
                    self.circuit_list.remove(item)
                    
            self.current_circuit_name = None
            self.refresh_list()
            self.lstCircuits.SelectedItem = None
        finally:
            self.Topmost = was_topmost

    def CircuitName_LostFocus(self, sender, e):
        if self.current_circuit_name is None:
            return
            
        new_name = self.txtCircuitName.Text.strip().upper()
        if not new_name:
            self.txtCircuitName.Text = self.current_circuit_name
            return
            
        if new_name == self.current_circuit_name:
            return
            
        if new_name in self.circuit_db:
            forms.alert("A circuit named '{}' already exists!".format(new_name), title="Duplicate Circuit")
            self.txtCircuitName.Text = self.current_circuit_name
            return
            
        # Record rename history
        original_old_name = self.current_circuit_name
        for old, new in list(self.renamed_circuits.items()):
            if new == self.current_circuit_name:
                original_old_name = old
                break
        self.renamed_circuits[original_old_name] = new_name

        # Update database keys
        self.save_current_editor_state()
        config = self.circuit_db[self.current_circuit_name]
        config["Circuit"] = new_name
        
        # Delete old key, save new key
        del self.circuit_db[self.current_circuit_name]
        self.circuit_db[new_name] = config
        
        # Update list item Name
        for item in self.circuit_list:
            if item.Name == self.current_circuit_name:
                item.Name = new_name
                break
                
        self.current_circuit_name = new_name
        self.refresh_list()
        
        # Re-select the renamed item
        for item in self.lstCircuits.ItemsSource:
            if item.Name == new_name:
                self.lstCircuits.SelectedItem = item
                break

    def Cancel_Click(self, sender, e):
        self.Close()

    def Save_Click(self, sender, e):
        # Save current editor values first
        self.save_current_editor_state()
        
        # Save database to JSON
        save_circuit_database(doc, self.circuit_db)
        
        # Perform Revit model update: synchronize all conduits and fittings in the model
        updated_count = 0
        
        try:
            conduits = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
            fittings = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
            all_elems = list(conduits) + list(fittings)
            
            with revit.Transaction("Sync Conduits with Circuit Database"):
                for el in all_elems:
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
                            
                            # Filter out deleted circuits
                            new_circuits_list = []
                            for circuit in circuits:
                                if isinstance(circuit, dict) and "Circuit" in circuit:
                                    c_name = str(circuit["Circuit"]).strip().upper()
                                    if c_name in self.deleted_circuits:
                                        modified = True
                                        continue
                                    new_circuits_list.append(circuit)
                                else:
                                    new_circuits_list.append(circuit)
                            
                            circuits = new_circuits_list
                            
                            for circuit in circuits:
                                if isinstance(circuit, dict) and "Circuit" in circuit:
                                    c_name = str(circuit["Circuit"]).strip().upper()
                                    if not c_name:
                                        continue
                                        
                                    # 1. Handle Rename
                                    if c_name in self.renamed_circuits:
                                        new_name = self.renamed_circuits[c_name]
                                        circuit["Circuit"] = new_name
                                        c_name = new_name
                                        modified = True
                                        
                                    # 2. Handle Cable Configuration Update
                                    if c_name in self.circuit_db:
                                        db_config = self.circuit_db[c_name]
                                        for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                                            phase_data = db_config.get(phase)
                                            if phase_data:
                                                circuit[phase] = {
                                                    "Quantity": phase_data.get("Quantity", 1),
                                                    "Shared": bool(phase_data.get("Shared", False)),
                                                    "CableType": str(phase_data.get("CableType", "#12 AWG")).strip()
                                                }
                                                modified = True
                                                
                            if modified:
                                if not circuits:
                                    # All circuits removed
                                    param.Set("")
                                    param_tag = el.LookupParameter("GPC-Cables-Tag")
                                    if param_tag:
                                        param_tag.Set("")
                                    
                                    is_fitting = el.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_ConduitFitting)
                                    if is_fitting:
                                        comments_param = el.LookupParameter("Comments")
                                        if comments_param and not comments_param.IsReadOnly:
                                            comments_param.Set("")
                                else:
                                    # Process duplicate shared cables
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
                                                        
                                    # Set updated GPC-Cables parameter
                                    param.Set(json.dumps(circuits))
                                    
                                    # Update GPC-Cables-Tag parameter
                                    param_tag = el.LookupParameter("GPC-Cables-Tag")
                                    if param_tag:
                                        param_tag.Set(generate_cables_tag_text(circuits))
                                        
                                    # If fitting, update Comments field
                                    is_fitting = el.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_ConduitFitting)
                                    if is_fitting:
                                        comments_param = el.LookupParameter("Comments")
                                        if comments_param and not comments_param.IsReadOnly:
                                            seen_names = set()
                                            unique_names = []
                                            for c in circuits:
                                                name = c.get("Circuit", "")
                                                if name:
                                                    name_str = str(name).strip()
                                                    if name_str and name_str not in seen_names:
                                                        seen_names.add(name_str)
                                                        unique_names.append(name_str)
                                            comments_param.Set(", ".join(unique_names))
                                    
                                updated_count += 1
                    except Exception as ex:
                        print("Error updating elements in sync: {}".format(ex))
        except Exception as e:
            forms.alert("Error syncing active model: {}".format(e))
            
        if updated_count > 0:
            forms.alert(
                "Project circuit database saved successfully!\n\n"
                "Synchronized {} conduit(s)/fitting(s) in the active model with the updated configurations.".format(updated_count),
                title="Success"
            )
        else:
            forms.alert("Project circuit database saved successfully!", title="Success")
            
        self.Close()

def main():
    # Initialise the circuit database before the window opens:
    # loads the JSON file AND merges any circuits from the model that are missing.
    circuit_db = init_circuit_database(doc)

    xaml_file = os.path.join(os.path.dirname(__file__), "ui.xaml")
    win = CircuitManagementWindow(xaml_file, circuit_db)
    win.ShowDialog()

if __name__ == '__main__':
    main()
