# -*- coding: utf-8 -*-
"""Maintain and update the cable sizes database with safety verification of model usage."""

__title__ = 'Manage Database'
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

# --- CableTypeItem Wrapper ---
class CableTypeItem(object):
    def __init__(self, name, area):
        self._name = name
        self._area = area
        
    @property
    def Name(self):
        return self._name
        
    @property
    def CableArea(self):
        return self._area
        
    @property
    def DisplayText(self):
        return "{}  (Area: {} sq in)".format(self._name, self._area)

# --- Default Cable Types ---
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
                    res_list.sort(key=lambda x: x["Name"])
                    return res_list
        except Exception:
            pass
            
    # 2. Extract from model conduits/fittings if file does not exist or failed to load
    extracted = set()
    try:
        conduits = DB.FilteredElementCollector(doc_obj).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
        fittings = DB.FilteredElementCollector(doc_obj).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
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
    
    data_to_save = []
    for item in cable_list:
        if isinstance(item, dict):
            data_to_save.append(item)
        else:
            data_to_save.append({"Name": item.Name, "CableArea": item.CableArea})
            
    try:
        if not os.path.exists(shared_params_dir):
            os.makedirs(shared_params_dir)
        with open(cable_types_path, 'w') as f:
            json.dump(data_to_save, f, indent=4)
    except Exception:
        pass

CABLE_TYPES_DB = load_cable_types(doc)
CABLE_TYPES = [CableTypeItem(x["Name"], x["CableArea"]) for x in CABLE_TYPES_DB]
CABLE_TYPES.sort(key=lambda x: x.Name)

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

def get_elements_using_cable(doc_obj, cable_name):
    """Finds all conduits and fittings using a specific cable size in their circuits."""
    used_elements = []
    try:
        conduits = DB.FilteredElementCollector(doc_obj).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
        fittings = DB.FilteredElementCollector(doc_obj).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
        
        for el in list(conduits) + list(fittings):
            param = el.LookupParameter("GPC-Cables")
            if param:
                val = param.AsString()
                if val:
                    try:
                        circuits = json.loads(val)
                        if isinstance(circuits, list):
                            is_used = False
                            for circuit in circuits:
                                if isinstance(circuit, dict):
                                    for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                                        phase_data = circuit.get(phase)
                                        if isinstance(phase_data, dict):
                                            c_type = phase_data.get("CableType")
                                            if c_type and str(c_type).strip() == cable_name:
                                                is_used = True
                                                break
                                if is_used:
                                    break
                            if is_used:
                                used_elements.append(el)
                    except Exception:
                        pass
    except Exception:
        pass
    return used_elements

# --- Main WPF Window ---
class ManageCableDatabaseWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        forms.WPFWindow.__init__(self, xaml_file_name)
        self.refresh_list()

    def refresh_list(self):
        self.lstCableTypes.ItemsSource = None
        self.lstCableTypes.ItemsSource = CABLE_TYPES

    def Add_Click(self, sender, e):
        was_topmost = self.Topmost
        self.Topmost = False
        try:
            new_cable = forms.ask_for_string(
                title="Add Cable Type",
                prompt="Enter the name/size of the new cable type (e.g. 750 kcmil):"
            )
            if not new_cable:
                return
            
            new_cable = new_cable.strip()
            if not new_cable:
                return
                
            if new_cable in [x.Name for x in CABLE_TYPES]:
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
                
            # Add and save
            CABLE_TYPES.append(CableTypeItem(new_cable, new_area))
            CABLE_TYPES.sort(key=lambda x: x.Name)
            save_cable_types(CABLE_TYPES)
            self.refresh_list()
            
            forms.alert("Cable type '{}' added successfully!".format(new_cable), title="Success")
        finally:
            self.Topmost = was_topmost

    def AddColor_Click(self, sender, e):
        selected_item = self.lstCableTypes.SelectedItem
        if not selected_item:
            forms.alert("Please select a cable type from the list to add a color variation.", title="No Selection")
            return

        selected_cable = selected_item.Name
        selected_area = selected_item.CableArea

        was_topmost = self.Topmost
        self.Topmost = False
        try:
            color_code = forms.ask_for_string(
                title="Add Color Variation",
                prompt="Enter the color code to append to '{}' (e.g. W, B, Y, R, W-B):".format(selected_cable)
            )
            if not color_code:
                return

            color_code = color_code.strip()
            if not color_code:
                return

            # Construct the new cable name by appending the color code directly
            new_cable = "{}{}".format(selected_cable, color_code)

            if new_cable in [x.Name for x in CABLE_TYPES]:
                forms.alert("Cable type '{}' already exists!".format(new_cable), title="Duplicate Entry")
                return

            # Duplicate the record with the same area
            new_item = CableTypeItem(new_cable, selected_area)
            CABLE_TYPES.append(new_item)
            CABLE_TYPES.sort(key=lambda x: x.Name)
            save_cable_types(CABLE_TYPES)
            self.refresh_list()

            # Highlight the new item in the list and scroll to it
            for item in self.lstCableTypes.ItemsSource:
                if item.Name == new_cable:
                    self.lstCableTypes.SelectedItem = item
                    self.lstCableTypes.ScrollIntoView(item)
                    break

            forms.alert("Cable variation '{}' added successfully!".format(new_cable), title="Success")
        finally:
            self.Topmost = was_topmost

    def Rename_Click(self, sender, e):
        selected_item = self.lstCableTypes.SelectedItem
        if not selected_item:
            forms.alert("Please select a cable type from the list to edit.", title="No Selection")
            return

        selected_cable = selected_item.Name

        was_topmost = self.Topmost
        self.Topmost = False
        try:
            new_name = forms.ask_for_string(
                title="Edit Cable Name",
                prompt="Enter the new name for '{}':".format(selected_cable),
                default=selected_cable
            )
            if not new_name:
                return
                
            new_name = new_name.strip()
            if not new_name:
                return
                
            new_area_str = forms.ask_for_string(
                title="Edit Cable Area",
                prompt="Enter the cross-sectional area (in sq in) for '{}':".format(new_name),
                default=str(selected_item.CableArea)
            )
            if new_area_str is None:
                return
            try:
                new_area = float(new_area_str)
            except ValueError:
                new_area = 0.0

            name_changed = (new_name != selected_cable)
            area_changed = (new_area != selected_item.CableArea)

            if not name_changed and not area_changed:
                return

            if name_changed and new_name in [x.Name for x in CABLE_TYPES if x.Name != selected_cable]:
                forms.alert("A cable type with the name '{}' already exists!".format(new_name), title="Duplicate Entry")
                return

            # Check model dependencies
            using_elements = get_elements_using_cable(doc, selected_cable)
            
            if using_elements:
                element_desc = ["ID: {} ({})".format(el.Id, el.Name) for el in using_elements]
                confirm = forms.alert(
                    "Cable type '{}' is currently assigned to {} conduit(s) and fitting(s):\n\n{}\n\n"
                    "Do you want to update this cable in the database and automatically update all model instances?".format(
                        selected_cable, len(using_elements), "\n".join(element_desc)
                    ),
                    yes=True, no=True, title="Update Active Cable"
                )
                if not confirm:
                    return

                # Perform Revit model update inside Transaction
                with revit.Transaction("Update Cable in Model"):
                    for el in using_elements:
                        param = el.LookupParameter("GPC-Cables")
                        if param:
                            val = param.AsString() or ""
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
                                                        if c_type and str(c_type).strip() == selected_cable:
                                                            phase_data["CableType"] = new_name
                                                            phase_data["CableArea"] = new_area
                                        
                                        # Re-serialize and set parameter value
                                        param.Set(json.dumps(circuits))

                                        # Update GPC-Cables-Tag
                                        param_tag = el.LookupParameter("GPC-Cables-Tag")
                                        if param_tag:
                                            param_tag.Set(generate_cables_tag_text(circuits))
                                except Exception:
                                    pass

            # Update database
            selected_item._name = new_name
            selected_item._area = new_area
            CABLE_TYPES.sort(key=lambda x: x.Name)
            save_cable_types(CABLE_TYPES)
            self.refresh_list()
            
            if using_elements:
                forms.alert(
                    "Cable successfully updated to '{}' in database and replaced in all {} model element(s)!".format(
                        new_name, len(using_elements)
                    ),
                    title="Success"
                )
            else:
                forms.alert("Cable successfully updated to '{}' in database!".format(new_name), title="Success")
        finally:
            self.Topmost = was_topmost

    def Delete_Click(self, sender, e):
        selected_item = self.lstCableTypes.SelectedItem
        if not selected_item:
            forms.alert("Please select a cable type from the list to delete.", title="No Selection")
            return

        selected_cable = selected_item.Name

        was_topmost = self.Topmost
        self.Topmost = False
        try:
            # Check model dependencies
            using_elements = get_elements_using_cable(doc, selected_cable)
            
            if using_elements:
                element_desc = ["ID: {} ({})".format(el.Id, el.Name) for el in using_elements]
                forms.alert(
                    "Cannot delete cable '{}' because it is currently in use in the active model!\n\n"
                    "Please replace or remove this cable from the following {} element(s) before deleting:\n\n{}".format(
                        selected_cable, len(using_elements), "\n".join(element_desc)
                    ),
                    title="Database Integrity Violation"
                )
                return

            # Confirm deletion
            confirm = forms.alert(
                "Are you sure you want to permanently delete '{}' from the cable database?".format(selected_cable),
                yes=True, no=True, title="Confirm Deletion"
            )
            if not confirm:
                return

            # Update database
            CABLE_TYPES.remove(selected_item)
            save_cable_types(CABLE_TYPES)
            self.refresh_list()
            
            forms.alert("Cable '{}' deleted successfully from the database!".format(selected_cable), title="Success")
        finally:
            self.Topmost = was_topmost

    def ClearModel_Click(self, sender, e):
        was_topmost = self.Topmost
        self.Topmost = False
        try:
            # 1. Ask for confirmation
            confirm = forms.alert(
                "Are you sure you want to permanently clear all GPC-Cables parameter data from ALL conduits and fittings in the active model?\n\n"
                "This action cannot be undone.",
                yes=True, no=True, title="Confirm Reset Model Cables"
            )
            if not confirm:
                return

            # 2. Collect conduits and fittings
            conduits = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
            fittings = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
            all_elements = list(conduits) + list(fittings)

            # 3. Reset GPC-Cables and GPC-Cables-Tag
            count = 0
            with revit.Transaction("Reset Model Cables"):
                for el in all_elements:
                    cleared = False
                    param = el.LookupParameter("GPC-Cables")
                    if param and param.AsString():
                        param.Set("")
                        cleared = True
                    param_tag = el.LookupParameter("GPC-Cables-Tag")
                    if param_tag and param_tag.AsString():
                        param_tag.Set("")
                        cleared = True
                    if cleared:
                        count += 1

            forms.alert(
                "Successfully cleared GPC-Cables parameter from {} conduit(s) and fitting(s) in the active model!".format(count),
                title="Reset Complete"
            )
        finally:
            self.Topmost = was_topmost

    def Close_Click(self, sender, e):
        self.Close()

def main():
    xaml_file = os.path.join(os.path.dirname(__file__), "ui.xaml")
    win = ManageCableDatabaseWindow(xaml_file)
    win.ShowDialog()

if __name__ == '__main__':
    main()
