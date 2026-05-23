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

# --- Default Cable Types ---
DEFAULT_CABLE_TYPES = [
    "#14 AWG",
    "#12 AWG",
    "#10 AWG",
    "#8 AWG",
    "#6 AWG",
    "#4 AWG",
    "#2 AWG",
    "#1/0 AWG",
    "#2/0 AWG",
    "#3/0 AWG",
    "#4/0 AWG",
    "250 kcmil",
    "350 kcmil",
    "500 kcmil"
]

def load_cable_types(doc_obj):
    # Locate shared_parameters directory (6 levels up from this script)
    _root = __file__
    for _ in range(6):
        _root = os.path.dirname(_root)
    
    shared_params_dir = os.path.join(_root, "shared_parameters")
    cable_types_path = os.path.join(shared_params_dir, "cable_types.json")
    
    string_types = (str, type(u''))
        
    # 1. Try to load from file
    if os.path.exists(cable_types_path):
        try:
            with open(cable_types_path, 'r') as f:
                loaded = json.load(f)
            if isinstance(loaded, list) and loaded:
                return [x for x in loaded if isinstance(x, string_types)]
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
        
    cable_list = sorted(list(extracted)) if extracted else DEFAULT_CABLE_TYPES
    
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

CABLE_TYPES = load_cable_types(doc)

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
                
            if new_cable in CABLE_TYPES:
                forms.alert("Cable type '{}' already exists!".format(new_cable), title="Duplicate Entry")
                return
                
            # Add and save
            CABLE_TYPES.append(new_cable)
            CABLE_TYPES.sort()
            save_cable_types(CABLE_TYPES)
            self.refresh_list()
            
            forms.alert("Cable type '{}' added successfully!".format(new_cable), title="Success")
        finally:
            self.Topmost = was_topmost

    def Rename_Click(self, sender, e):
        selected_cable = self.lstCableTypes.SelectedItem
        if not selected_cable:
            forms.alert("Please select a cable type from the list to rename.", title="No Selection")
            return

        was_topmost = self.Topmost
        self.Topmost = False
        try:
            new_name = forms.ask_for_string(
                title="Rename Cable Type",
                prompt="Enter the new name for '{}':".format(selected_cable),
                default=selected_cable
            )
            if not new_name:
                return
                
            new_name = new_name.strip()
            if not new_name or new_name == selected_cable:
                return
                
            if new_name in CABLE_TYPES:
                forms.alert("A cable type with the name '{}' already exists!".format(new_name), title="Duplicate Entry")
                return

            # Check model dependencies
            using_elements = get_elements_using_cable(doc, selected_cable)
            
            if using_elements:
                element_desc = ["ID: {} ({})".format(el.Id, el.Name) for el in using_elements]
                confirm = forms.alert(
                    "Cable type '{}' is currently assigned to {} conduit(s) and fitting(s):\n\n{}\n\n"
                    "Do you want to rename this cable in the database and automatically update all model instances?".format(
                        selected_cable, len(using_elements), "\n".join(element_desc)
                    ),
                    yes=True, no=True, title="Rename Active Cable"
                )
                if not confirm:
                    return

                # Perform Revit model update inside Transaction
                with revit.Transaction("Rename Cable Type in Model"):
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
                                        
                                        # Re-serialize and set parameter value
                                        param.Set(json.dumps(circuits))
                                except Exception:
                                    pass

            # Update database
            idx = CABLE_TYPES.index(selected_cable)
            CABLE_TYPES[idx] = new_name
            CABLE_TYPES.sort()
            save_cable_types(CABLE_TYPES)
            self.refresh_list()
            
            if using_elements:
                forms.alert(
                    "Cable successfully renamed to '{}' in database and replaced in all {} model element(s)!".format(
                        new_name, len(using_elements)
                    ),
                    title="Success"
                )
            else:
                forms.alert("Cable successfully renamed to '{}' in database!".format(new_name), title="Success")
        finally:
            self.Topmost = was_topmost

    def Delete_Click(self, sender, e):
        selected_cable = self.lstCableTypes.SelectedItem
        if not selected_cable:
            forms.alert("Please select a cable type from the list to delete.", title="No Selection")
            return

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
            CABLE_TYPES.remove(selected_cable)
            save_cable_types(CABLE_TYPES)
            self.refresh_list()
            
            forms.alert("Cable '{}' deleted successfully from the database!".format(selected_cable), title="Success")
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
