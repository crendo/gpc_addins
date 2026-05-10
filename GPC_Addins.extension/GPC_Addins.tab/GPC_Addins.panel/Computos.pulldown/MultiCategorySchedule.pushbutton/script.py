"""Automate the creation of a multi-category quantity takeoff schedule."""

__title__ = 'Multi-Category\nSchedule'
__author__ = 'Computos Revit Team'

import os
from pyrevit import revit, DB, forms

def create_multi_category_schedule():
    doc = revit.doc
    
    # 1. Schedule Name definition
    schedule_name = "Computos Revit - Multi-Category"
    
    # 2. Check if schedule already exists and exit if it does
    existing_schedules = DB.FilteredElementCollector(doc).OfClass(DB.ViewSchedule)
    for sched in list(existing_schedules):
        try:
            if sched.Name == schedule_name:
                forms.alert("The Multi-Category Schedule already exists in this project.", title="Schedule Exists")
                return
        except:
            continue

    # 3. Create Multi-Category Schedule
    with revit.Transaction("Create Computos Multi-Category Schedule"):
        try:
            # Create a Multi-Category Schedule
            new_sched = DB.ViewSchedule.CreateSchedule(doc, DB.ElementId.InvalidElementId)
            new_sched.Name = schedule_name
            
            # 4. Define target parameters
            target_params_names = [
                ("GPC-GrupoCosto", "GPC-GrupoCosto", None),
                ("Family and Type", "Family and Type", DB.BuiltInParameter.ALL_MODEL_TYPE_NAME),
                ("Description", "Description", DB.BuiltInParameter.ALL_MODEL_DESCRIPTION),
                ("GPC-UnidadMedicion", "GPC-UnidadMedicion", None),
                ("GPC-Cantidad", "GPC-Cantidad", None),
                ("GPC-PrecioUnitario", "GPC-PrecioUnitario", None),
                ("GPC-CostoItem", "GPC-CostoItem", None),
                ("Comments", "Comments", DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
            ]

            process_schedule_fields(new_sched, target_params_names)
            forms.toast("Created: {}".format(schedule_name))
            
        except Exception as e:
            forms.alert("Error creating Multi-Category schedule: {}".format(e), title="Error")

def create_material_takeoff_schedule():
    doc = revit.doc
    
    # 1. Schedule Name definition
    schedule_name = "Computos Revit - Materials (As Paint)"
    
    # 2. Check if schedule already exists
    existing_schedules = DB.FilteredElementCollector(doc).OfClass(DB.ViewSchedule)
    for sched in list(existing_schedules):
        try:
            if sched.Name == schedule_name:
                forms.alert("The Materials (As Paint) Schedule already exists.", title="Schedule Exists")
                return
        except:
            continue

    # 3. Create Multi-Category Material Takeoff
    with revit.Transaction("Create Computos Materials Schedule"):
        try:
            # Create a Multi-Category Material Takeoff
            new_sched = DB.ViewSchedule.CreateMaterialTakeoff(doc, DB.ElementId.InvalidElementId)
            new_sched.Name = schedule_name
            
            # 4. Define target parameters
            target_params_names = [
                ("GPC-GrupoCosto", "GPC-GrupoCosto", None),
                ("Material: Name", "Material: Name", DB.BuiltInParameter.MATERIAL_NAME),
                ("Material: As Paint", "Material: As Paint", None), # No BuiltInParameter for this
                ("GPC-UnidadMedicion", "GPC-UnidadMedicion", None),
                ("GPC-Cantidad", "GPC-Cantidad", None),
                ("GPC-PrecioUnitario", "GPC-PrecioUnitario", None),
                ("GPC-CostoItem", "GPC-CostoItem", None)
            ]

            # Special case for "As Paint" name search if standard fails
            added_fields = process_schedule_fields(new_sched, target_params_names, doc_lang_hint="paint")
            
            # 5. Apply Filter: Material: As Paint == Yes (1)
            definition = new_sched.Definition
            for p_name, field in added_fields:
                if "As Paint" in p_name:
                    filter = DB.ScheduleFilter(field.FieldId, DB.ScheduleFilterType.Equal, 1)
                    definition.AddFilter(filter)
                    break # Only one filter needed for this
            
            forms.toast("Created: {}".format(schedule_name))
            
        except Exception as e:
            forms.alert("Error creating Materials schedule: {}".format(e), title="Error")

def process_schedule_fields(new_sched, target_params_names, doc_lang_hint=None):
    doc = revit.doc
    definition = new_sched.Definition
    schedulable_fields = definition.GetSchedulableFields()
    
    # Map for BIP-based lookup
    id_map = {}
    for sf in schedulable_fields:
        # Compatibility fix for Revit 2024+: ElementId.Value vs ElementId.IntegerValue
        eid = sf.ParameterId
        bip_id = int(eid.Value) if hasattr(eid, "Value") else eid.IntegerValue
        if bip_id == -1: continue
        
        current_name = sf.GetName(doc)
        if bip_id not in id_map or (":" in id_map[bip_id].GetName(doc) and ":" not in current_name):
            id_map[bip_id] = sf

    # Map for name-based lookup
    name_map = {}
    for sf in schedulable_fields:
        try:
            name_map[sf.GetName(doc).lower()] = sf
        except:
            pass

    # Add fields in order
    added_fields = []
    for target_name, alt_name, bip_id in target_params_names:
        sf = None
        if bip_id is not None:
            sf = id_map.get(int(bip_id))
        
        if not sf:
            sf = name_map.get(target_name.lower()) or name_map.get(alt_name.lower())
        
        # Fallback for "As Paint" variations if standard lookup fails
        if not sf and doc_lang_hint == "paint" and "paint" in target_name.lower():
            for name, fsf in name_map.items():
                if "as paint" in name or "como pintura" in name:
                    sf = fsf
                    break

        if sf:
            field = definition.AddField(sf)
            field.ColumnHeading = target_name
            added_fields.append((target_name, field))
    
    # Basic Formatting (shared between both)
    for p_name, field in added_fields:
        # Alignment
        if "GrupoCosto" in p_name:
            field.HorizontalAlignment = DB.ScheduleHorizontalAlignment.Left
            definition.AddSortGroupField(DB.ScheduleSortGroupField(field.FieldId))
            
        elif any(x in p_name for x in ["Name", "Family", "Type", "Description"]):
            field.HorizontalAlignment = DB.ScheduleHorizontalAlignment.Left
            
        elif "UnidadMedicion" in p_name:
            field.HorizontalAlignment = DB.ScheduleHorizontalAlignment.Center
            
        elif any(x in p_name for x in ["Cantidad", "PrecioUnitario", "CostoItem"]):
            field.HorizontalAlignment = DB.ScheduleHorizontalAlignment.Right
            try:
                fo = field.GetFormatOptions()
                fo.UseDefault = False
                fo.Accuracy = 0.01
                field.SetFormatOptions(fo)
            except:
                pass
            if "CostoItem" in p_name:
                try: field.HasTotals = True
                except: pass

    definition.ShowGrandTotal = True
    definition.IsItemized = True
    
    return added_fields

if __name__ == "__main__":
    options = [
        "1. Standard Multi-Category Schedule",
        "2. Materials (As Paint) Multi-Category Schedule",
        "3. Both Schedules"
    ]
    
    choice = forms.SelectFromList.show(options, title="Select Schedule to Create", width=400)
    
    if choice:
        if "1." in choice or "3." in choice:
            create_multi_category_schedule()
        if "2." in choice or "3." in choice:
            create_material_takeoff_schedule()
