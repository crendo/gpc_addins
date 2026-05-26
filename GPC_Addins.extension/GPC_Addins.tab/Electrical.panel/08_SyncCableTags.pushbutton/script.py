import json
from pyrevit import revit, DB

doc = revit.doc

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
    conduits = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
    fittings = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
    all_elements = list(conduits) + list(fittings)
    
    count = 0
    with revit.Transaction("Sync GPC Cable Tags"):
        for el in all_elements:
            param = el.LookupParameter("GPC-Cables")
            if param and param.AsString():
                try:
                    circuits = json.loads(param.AsString())
                    if isinstance(circuits, list) and circuits:
                        param_tag = el.LookupParameter("GPC-Cables-Tag")
                        if param_tag:
                            new_tag = generate_cables_tag_text(circuits)
                            param_tag.Set(new_tag)
                            count += 1
                        
                        # Add circuits list to Comments for Conduit Fittings
                        is_fitting = el.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_ConduitFitting)
                        if is_fitting:
                            comments_param = el.LookupParameter("Comments")
                            if comments_param and not comments_param.IsReadOnly:
                                seen_names = set()
                                unique_names = []
                                for circuit in circuits:
                                    c_name = circuit.get("Circuit", "")
                                    if c_name:
                                        c_name_str = str(c_name).strip()
                                        if c_name_str and c_name_str not in seen_names:
                                            seen_names.add(c_name_str)
                                            unique_names.append(c_name_str)
                                comments_param.Set(", ".join(unique_names))
                except Exception:
                    continue
                    
    print("Successfully updated {} GPC-Cables-Tag values in the active model to the new sorting standard!".format(count))

if __name__ == "__main__":
    main()
