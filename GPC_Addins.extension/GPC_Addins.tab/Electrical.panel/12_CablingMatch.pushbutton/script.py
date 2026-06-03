# -*- coding: utf-8 -*-
"""Copy GPC-Cables and GPC-Cables-Tag parameters from a source conduit or fitting to destination conduits or fittings."""

__title__ = 'Cabling\nMatch'
__author__ = 'Electrical Team'

import json
from pyrevit import revit, DB, UI, forms

doc = revit.doc
uidoc = revit.uidoc

class ConduitSelectionFilter(UI.Selection.ISelectionFilter):
    def AllowElement(self, element):
        if not element or not element.Category:
            return False
        cat_id = element.Category.Id.IntegerValue
        return cat_id in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]
        
    def AllowReference(self, reference, point):
        return False

def generate_cables_tag_text(circuits):
    if not circuits:
        return ""
        
    circuit_parts = []
    for circuit in circuits:
        c_name = circuit.get("Circuit", "")
        # Group cables by (CableType, IsShared) within this circuit
        cables_summary = {}
        # Keep track of which phases each CableType is used in to determine sorting priority
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
                        if c_type_str not in cable_roles:
                            cable_roles[c_type_str] = set()
                        if phase in ["Phase 1", "Phase 2", "Phase 3"]:
                            cable_roles[c_type_str].add("phase")
                        elif phase == "Neutral":
                            cable_roles[c_type_str].add("neutral")
                        elif phase == "Ground":
                            cable_roles[c_type_str].add("ground")
                            
        # Define priority function for keys in cables_summary
        def get_sort_key(item_key):
            c_type_str, is_shared = item_key
            roles = cable_roles.get(c_type_str, set())
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

def main():
    # 1. Select Source Element
    source_el = None
    try:
        with forms.WarningBar(title="Select the SOURCE Conduit or Fitting"):
            ref = uidoc.Selection.PickObject(
                UI.Selection.ObjectType.Element, 
                ConduitSelectionFilter(), 
                "Select the SOURCE Conduit or Fitting"
            )
            source_el = doc.GetElement(ref.ElementId)
    except Exception:
        # User cancelled / pressed ESC
        return

    if not source_el:
        return

    # Verify GPC-Cables parameter exists on source
    param_cables = source_el.LookupParameter("GPC-Cables")
    if not param_cables:
        forms.alert(
            "The 'GPC-Cables' parameter was not found on the selected source element.\n\n"
            "Please run 'Setup Parameters' in the Electrical menu first.",
            title="Parameter Missing"
        )
        return

    cables_val = param_cables.AsString() or ""
    param_tag = source_el.LookupParameter("GPC-Cables-Tag")
    tag_val = param_tag.AsString() or "" if param_tag else ""

    # 2. Select Destination Elements in a loop
    copied_count = 0
    while True:
        dest_el = None
        try:
            # Inform user how to finish the process (press ESC)
            prompt_msg = "Select a DESTINATION Conduit or Fitting (Press ESC when finished)"
            with forms.WarningBar(title=prompt_msg):
                ref = uidoc.Selection.PickObject(
                    UI.Selection.ObjectType.Element, 
                    ConduitSelectionFilter(), 
                    prompt_msg
                )
                dest_el = doc.GetElement(ref.ElementId)
        except Exception:
            # User pressed ESC or cancelled, which is the expected way to exit
            break

        if not dest_el:
            break

        if source_el.Id.IntegerValue == dest_el.Id.IntegerValue:
            forms.alert("The destination element cannot be the same as the source element.", title="Selection Error")
            continue

        dest_param_cables = dest_el.LookupParameter("GPC-Cables")
        if not dest_param_cables:
            forms.alert(
                "The 'GPC-Cables' parameter was not found on the selected destination element.\n\n"
                "Please run 'Setup Parameters' first.",
                title="Parameter Missing"
            )
            continue

        # Perform copying inside a Transaction
        try:
            with revit.Transaction("Copy Cabling Data"):
                dest_param_cables.Set(cables_val)
                
                dest_param_tag = dest_el.LookupParameter("GPC-Cables-Tag")
                if dest_param_tag:
                    # If GPC-Cables is not empty but GPC-Cables-Tag is empty on source, re-generate it to be safe
                    if cables_val and not tag_val:
                        try:
                            circuits = json.loads(cables_val)
                            new_tag = generate_cables_tag_text(circuits)
                            dest_param_tag.Set(new_tag)
                        except Exception:
                            dest_param_tag.Set(tag_val)
                    else:
                        dest_param_tag.Set(tag_val)
                
                # If it's a fitting, set Comments parameter as well
                is_fitting = dest_el.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_ConduitFitting)
                if is_fitting:
                    dest_comments_param = dest_el.LookupParameter("Comments")
                    if dest_comments_param and not dest_comments_param.IsReadOnly:
                        if cables_val:
                            try:
                                circuits = json.loads(cables_val)
                                if isinstance(circuits, list):
                                    seen_names = set()
                                    unique_names = []
                                    for circuit in circuits:
                                        c_name = circuit.get("Circuit", "")
                                        if c_name:
                                            c_name_str = str(c_name).strip()
                                            if c_name_str and c_name_str not in seen_names:
                                                seen_names.add(c_name_str)
                                                unique_names.append(c_name_str)
                                    dest_comments_param.Set(", ".join(unique_names))
                            except Exception:
                                pass
                        else:
                            dest_comments_param.Set("")
            
            copied_count += 1
        except Exception as e:
            forms.alert("Error copying cabling data: {}".format(e), title="Transaction Error")

    if copied_count > 0:
        print("Successfully copied cabling to {} destination element(s).".format(copied_count))

if __name__ == '__main__':
    main()
