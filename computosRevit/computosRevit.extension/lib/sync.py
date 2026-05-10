# -*- coding: utf-8 -*-
from pyrevit import revit, DB, forms
import json
import os
import codecs

def load_category_exclusions():
    """Load exclusion list from CategoryExclusion.json if it exists."""
    lib_dir = os.path.dirname(__file__)
    json_path = os.path.join(lib_dir, "CategoryExclusion.json")
    
    try:
        with codecs.open(json_path, 'r', 'utf-8-sig') as f:
            data = json.load(f)
            return data.get("ExcludedKeywords", [])
    except:
        # High-level defaults to avoid a blank set if loading fails
        return [u"Floor Plans", u"Grids", u"Cameras", u"Views", u"View", u"Sheets", u"Levels"]

CATEGORIES_TO_EXCLUDE = load_category_exclusions()

def load_unit_mappings():
    # Use a relative path from the current file's location to find extension root
    # lib/sync.py -> extension/lib -> extension
    lib_dir = os.path.dirname(__file__)
    extension_dir = os.path.dirname(lib_dir)
    
    json_path = os.path.join(extension_dir, "reference_docs", "CategoryUnits.json")
    try:
        with codecs.open(json_path, 'r', 'utf-8-sig') as f:
            return json.load(f)
    except:
        return {"Categories": {}, "Families": {}}

def get_initial_unit(sym, unit_mappings, el=None):
    if not sym: return "und"
    
    # 1. CHECK FAMILY NAME FIRST (Most specific)
    # Get the real Family Name safely across different Revit API access patterns
    fam_name = ""
    if hasattr(sym, "Family") and sym.Family:
        fam_name = sym.Family.Name
    else:
        # Fallback to parameter lookup for family name
        p_fam = sym.get_Parameter(DB.BuiltInParameter.SYMBOL_FAMILY_NAME_PARAM)
        fam_name = p_fam.AsString() if p_fam else ""
        
    family_overrides = unit_mappings.get("Families", {})
    if fam_name in family_overrides:
        return family_overrides[fam_name]
    
    # 2. CHECK CATEGORY NAME SECOND
    cat_name = sym.Category.Name if sym.Category else ""
    category_defaults = unit_mappings.get("Categories", {})
    if cat_name in category_defaults:
        return category_defaults[cat_name]
    
    # Fallback smart detection
    if el:
        for p_name in ["Length", "CURVE_ELEM_LENGTH", "STRUCTURAL_FRAME_OUT_OUT_LENGTH"]:
            p = el.get_Parameter(getattr(DB.BuiltInParameter, p_name)) if hasattr(DB.BuiltInParameter, p_name) else None
            if not p: p = el.LookupParameter(p_name)
            if p and p.HasValue: return "m"
        
        for p_name in ["HOST_AREA_COMPUTED", "SURFACE_AREA", "ROOM_AREA"]:
            p = el.get_Parameter(getattr(DB.BuiltInParameter, p_name)) if hasattr(DB.BuiltInParameter, p_name) else None
            if not p: p = el.LookupParameter(p_name)
            if p and p.HasValue: return "m2"
            
        for p_name in ["HOST_VOLUME_COMPUTED"]:
            p = el.get_Parameter(getattr(DB.BuiltInParameter, p_name)) if hasattr(DB.BuiltInParameter, p_name) else None
            if not p: p = el.LookupParameter(p_name)
            if p and p.HasValue: return "m3"

    return "und"

def get_element_geometry_stats(el):
    """Calculates perimeter and area from element geometry for non-standard categories."""
    perim = 0.0
    area = 0.0
    try:
        opt = DB.Options()
        geometry = el.get_Geometry(opt)
        for obj in geometry:
            if isinstance(obj, DB.Solid):
                # Area: Sum of faces pointing UP
                for face in obj.Faces:
                    if face.ComputeNormal(DB.UV(0.5, 0.5)).Z > 0.9:
                        area += face.Area
                # Perimeter: Sum of horizontal edges / 2 (assuming top/bottom loops)
                for edge in obj.Edges:
                    direction = edge.AsCurve().GetEndPoint(1) - edge.AsCurve().GetEndPoint(0)
                    if abs(direction.Normalize().Z) < 0.001:
                        perim += edge.ApproximateLength / 2.0
            elif isinstance(obj, DB.GeometryInstance):
                # Handle nested geometry if needed
                inst_geom = obj.GetInstanceGeometry()
                for i_obj in inst_geom:
                    if isinstance(i_obj, DB.Solid):
                        for face in i_obj.Faces:
                            if face.ComputeNormal(DB.UV(0.5, 0.5)).Z > 0.9: area += face.Area
                        for edge in i_obj.Edges:
                            direction = edge.AsCurve().GetEndPoint(1) - edge.AsCurve().GetEndPoint(0)
                            if abs(direction.Normalize().Z) < 0.001: perim += edge.ApproximateLength / 2.0
    except:
        pass
    return perim, area

def get_element_quantity(el, unidad):
    def get_param_value(param_names):
        el_type = el.Document.GetElement(el.GetTypeId())
        lower_names = [n.lower() for n in param_names]
        
        # 1. Built-in Parameter Check
        for name in param_names:
            if hasattr(DB.BuiltInParameter, name):
                bip = getattr(DB.BuiltInParameter, name)
                p = el.get_Parameter(bip)
                if p and p.HasValue: return p.AsDouble()
                if el_type:
                    p_type = el_type.get_Parameter(bip)
                    if p_type and p_type.HasValue: return p_type.AsDouble()
                    
        # 2. Iterate all Instance Parameters to avoid LookupParameter conflicts
        for p in el.Parameters:
            if p.Definition and p.Definition.Name.lower() in lower_names and p.HasValue:
                if p.StorageType == DB.StorageType.Double:
                    return p.AsDouble()
                    
        # 3. Iterate all Type Parameters
        if el_type:
            for p in el_type.Parameters:
                if p.Definition and p.Definition.Name.lower() in lower_names and p.HasValue:
                    if p.StorageType == DB.StorageType.Double:
                        return p.AsDouble()
        
        return None

    if unidad == "und": return 1.0
    
    # Normalize synonyms
    u = unidad.lower().strip()
    if u in ["m","M" "ml", "Ml", "ML", "mL", "Lineal", "linear"]: u = "m"
    if u in ["m2", "M2", "m2", "SqM", "sqm", "Area", "area"]: u = "m2"
    if u in ["m3", "M3", "m3", "Cum", "cum", "Volume", "volume"]: u = "m3"

    # 1. Try standard and custom parameters
    if u == "m":
        val = get_param_value(["Length", "Longitud", "Largo", "CURVE_ELEM_LENGTH", "STRUCTURAL_FRAME_OUT_OUT_LENGTH", "DOOR_WIDTH", "WINDOW_WIDTH"])
        if val is not None:
            return DB.UnitUtils.ConvertFromInternalUnits(val, DB.UnitTypeId.Meters)
            
    elif u == "m2":
        val = get_param_value(["Area", "Areas", "Superficie", "HOST_AREA_COMPUTED", "SURFACE_AREA", "ROOM_AREA"])
        if val is not None:
            return DB.UnitUtils.ConvertFromInternalUnits(val, DB.UnitTypeId.SquareMeters)
            
    elif u == "m3":
        val = get_param_value(["Volume", "Volumen", "HOST_VOLUME_COMPUTED"])
        if val is not None:
            return DB.UnitUtils.ConvertFromInternalUnits(val, DB.UnitTypeId.CubicMeters)

    # 2. Fallback to Geometry Analysis (Crucial for DirectShape Polygons)
    perim, area = get_element_geometry_stats(el)
    if u == "m" and perim > 0:
        return DB.UnitUtils.ConvertFromInternalUnits(perim, DB.UnitTypeId.Meters)
    if u == "m2" and area > 0:
        return DB.UnitUtils.ConvertFromInternalUnits(area, DB.UnitTypeId.SquareMeters)

    # 3. Last resort fallbacks
    if u == "m2":
        w = get_param_value(["DOOR_WIDTH", "WINDOW_WIDTH", "GENERIC_WIDTH"])
        h = get_param_value(["DOOR_HEIGHT", "WINDOW_HEIGHT", "GENERIC_HEIGHT"])
        if w is not None and h is not None:
            w_m = DB.UnitUtils.ConvertFromInternalUnits(w, DB.UnitTypeId.Meters)
            h_m = DB.UnitUtils.ConvertFromInternalUnits(h, DB.UnitTypeId.Meters)
            return w_m * h_m
            
    if u == "kg":
        val = get_param_value(["Weight", "Peso", "STRUCTURAL_WEIGHT", "ASSEMBLY_WEIGHT"])
        if val is not None:
            return DB.UnitUtils.ConvertFromInternalUnits(val, DB.UnitTypeId.Kilograms)
        vol = get_param_value(["Volume", "Volumen", "HOST_VOLUME_COMPUTED"])
        if vol is not None:
            v_m3 = DB.UnitUtils.ConvertFromInternalUnits(vol, DB.UnitTypeId.CubicMeters)
            return v_m3 * 7850.0  # Density factor
            
    return 1.0

def get_string_param_value(el, param_names):
    """Safely retrieves a string parameter value from an element or its type."""
    el_type = el.Document.GetElement(el.GetTypeId())
    lower_names = [n.lower() for n in param_names]
    
    # 1. Built-in Parameter Check
    for name in param_names:
        if hasattr(DB.BuiltInParameter, name):
            bip = getattr(DB.BuiltInParameter, name)
            p = el.get_Parameter(bip)
            if p and p.HasValue: return p.AsString()
            if el_type:
                p_type = el_type.get_Parameter(bip)
                if p_type and p_type.HasValue: return p_type.AsString()

    # 2. Iterate all Instance Parameters to avoid LookupParameter conflicts
    for p in el.Parameters:
        if p.Definition and p.Definition.Name.lower() in lower_names and p.HasValue:
            if p.StorageType == DB.StorageType.String:
                return p.AsString()

    # 3. Iterate all Type Parameters
    if el_type:
        for p in el_type.Parameters:
            if p.Definition and p.Definition.Name.lower() in lower_names and p.HasValue:
                if p.StorageType == DB.StorageType.String:
                    return p.AsString()

    return ""

def sync_elements(doc, elements, store, show_progress=False, auto_save=False):
    """Syncs a specific set of elements into the DataStore."""
    if not elements:
        return 0

    synced_count = 0
    unit_mappings = load_unit_mappings()
    
    # Pre-fetch groups to avoid repeat lookups
    groups_lookup = store.get_groups_lookup()
    
    # We need a function to get/create default group inside this context
    def get_or_create_default_group():
        return store.add_group(u"No asignado", u"Grupo por defecto para elementos sin clasificar")
    
    default_group_id = get_or_create_default_group()

    # Note: caller should handle transaction if needed for param updates
    # But for a background listener, we MUST use a transaction if we modify parameters
    
    total_elements = len(elements)
    
    def process_element(el):
        # 1. Basic Filters & Parameter Check
        # Robustly find GPC-Cantidad - crucial for sync
        p_qty = el.LookupParameter("GPC-Cantidad")
        if not p_qty:
            # Fallback for some element types where LookupParameter might be finicky
            for p in el.Parameters:
                if p.Definition and p.Definition.Name == "GPC-Cantidad":
                    p_qty = p
                    break
        
        if not p_qty: return False
        if isinstance(el, DB.ProjectInfo): return False
        
        # Category Check
        cat = el.Category
        if not cat: return False
        
        cat_name = cat.Name.lower()
        if any(excl.lower() in cat_name for excl in CATEGORIES_TO_EXCLUDE):
            return False
            
        # Ignore nested components (handled by their parents/independently usually)
        if hasattr(el, "SuperComponent") and el.SuperComponent is not None:
             return False
            
        # 2. Get Type (Optional for DirectShapes)
        # DirectShapes can be typeless or have a DirectShapeType
        el_type_id = el.GetTypeId()
        el_type = doc.GetElement(el_type_id) if el_type_id != DB.ElementId.InvalidElementId else None
        
        # 3. GPC-UnidadMedicion
        p_unidad = None
        if el_type:
            p_unidad = el_type.LookupParameter("GPC-UnidadMedicion")
        if not p_unidad:
            p_unidad = el.LookupParameter("GPC-UnidadMedicion")
            
        unidad = p_unidad.AsString() if (p_unidad and p_unidad.HasValue) else ""
        if not unidad:
            unidad = get_initial_unit(el_type, unit_mappings, el=el)
            if p_unidad and not p_unidad.IsReadOnly: p_unidad.Set(unidad)
            
        # 4. GPC-Cantidad
        cantidad = get_element_quantity(el, unidad)
        if p_qty and not p_qty.IsReadOnly: p_qty.Set(cantidad)
        
        # 5. GPC-GrupoCosto
        p_grupo = None
        if el_type:
            p_grupo = el_type.LookupParameter("GPC-GrupoCosto")
        if not p_grupo:
            p_grupo = el.LookupParameter("GPC-GrupoCosto")
            
        grupo_name = p_grupo.AsString() if (p_grupo and p_grupo.HasValue) else ""
        if not grupo_name:
            omni_val = ""
            if el_type:
                omni_param = el_type.LookupParameter("OmniClass Title")
                omni_val = omni_param.AsString() if omni_param and omni_param.HasValue else ""
            grupo_name = omni_val if omni_val else "No asignado"
            if p_grupo and not p_grupo.IsReadOnly: p_grupo.Set(grupo_name)
            
        if grupo_name not in groups_lookup:
            new_id = store.add_group(grupo_name)
            groups_lookup[grupo_name] = new_id
            
        id_grupo_costo = groups_lookup.get(grupo_name, default_group_id)
        
        # 6. Costing
        p_punit = el.LookupParameter("GPC-PrecioUnitario")
        if p_punit and p_punit.HasValue:
            unit_cost = p_punit.AsDouble()
        else:
            p_cost_type = None
            if el_type:
                p_cost_type = el_type.LookupParameter("Cost")
            unit_cost = p_cost_type.AsDouble() if (p_cost_type and p_cost_type.HasValue) else 0.0
            if p_punit and not p_punit.IsReadOnly: p_punit.Set(unit_cost)
        
        preciototal = cantidad * unit_cost
        p_punit_total = el.LookupParameter("GPC-CostoItem")
        if p_punit_total and not p_punit_total.IsReadOnly:
            p_punit_total.Set(preciototal)
        
        # 7. Metadata (Description and Comments)
        desc = get_string_param_value(el, ["ALL_MODEL_DESCRIPTION", "Description", u"Descripción", "GPC-Descripcion"])
        comm = get_string_param_value(el, ["ALL_MODEL_INSTANCE_COMMENTS", "Comments", "Comentarios", "GPC-Comentarios"])
        
        try:
            eid = el.Id
            eid_val = int(eid.Value) if hasattr(eid, "Value") else eid.IntegerValue
            store.upsert_partida(eid_val, id_grupo_costo, cantidad, unit_cost, unidad, preciototal, description=desc, comments=comm)
        except:
            pass
        return True

    if show_progress:
        with forms.ProgressBar(title="Syncing Elements...", step=100, total=total_elements) as pb:
            for i, el in enumerate(elements):
                if i % 100 == 0: pb.update_progress(i, total_elements)
                if process_element(el):
                    synced_count += 1
    else:
        for el in elements:
            if process_element(el):
                synced_count += 1
                
    if synced_count > 0 and auto_save:
        try:
            store.save()
        except:
            pass
        
    return synced_count

def sync_from_store(doc, store, show_progress=True):
    """Syncs data FROM the DataStore into model element parameters."""
    partidas = store.data.get("partidas", {})
    if not partidas:
        return 0
    
    # Pre-fetch groups for name lookups
    groups = store.get_groups()
    
    updated_count = 0
    total = len(partidas)
    
    def update_element_from_data(eid_int, data):
        try:
            eid = DB.ElementId(int(eid_int))
            el = doc.GetElement(eid)
            if not el: return False
            
            # 1. GPC-Cantidad
            p_qty = el.LookupParameter("GPC-Cantidad")
            if p_qty and not p_qty.IsReadOnly:
                p_qty.Set(float(data.get('cantidad', 0)))
                
            # 2. GPC-UnidadMedicion
            p_unit = None
            el_type_id = el.GetTypeId()
            el_type = doc.GetElement(el_type_id) if el_type_id != DB.ElementId.InvalidElementId else None
            
            if el_type:
                 p_unit = el_type.LookupParameter("GPC-UnidadMedicion")
            if not p_unit:
                 p_unit = el.LookupParameter("GPC-UnidadMedicion")
            
            if p_unit and not p_unit.IsReadOnly:
                p_unit.Set(str(data.get('unidad', "")))
            
            # 3. GPC-GrupoCosto
            p_group = None
            if el_type:
                 p_group = el_type.LookupParameter("GPC-GrupoCosto")
            if not p_group:
                 p_group = el.LookupParameter("GPC-GrupoCosto")
            
            if p_group and not p_group.IsReadOnly:
                group_id = data.get('idGrupoCosto')
                group_name = groups.get(group_id, "No asignado")
                p_group.Set(group_name)
                
            # 4. GPC-PrecioUnitario
            p_punit = el.LookupParameter("GPC-PrecioUnitario")
            if p_punit and not p_punit.IsReadOnly:
                p_punit.Set(float(data.get('punit', 0)))
                
            # 5. GPC-CostoItem
            p_cost_total = el.LookupParameter("GPC-CostoItem")
            if p_cost_total and not p_cost_total.IsReadOnly:
                p_cost_total.Set(float(data.get('preciototal', 0)))
                
            return True
        except:
            return False

    with revit.Transaction("Import Cost Data from JSON"):
        if show_progress:
            with forms.ProgressBar(title="Importing from JSON...", step=10, total=total) as pb:
                for i, (eid_int, data) in enumerate(partidas.items()):
                    if i % 10 == 0: pb.update_progress(i, total)
                    if update_element_from_data(eid_int, data):
                        updated_count += 1
        else:
            for eid_int, data in partidas.items():
                if update_element_from_data(eid_int, data):
                    updated_count += 1
    
    return updated_count

# --- Background Session Management ---
# Using module-level globals to persist state across script executions in the same Revit session
if 'GPC_PENDING_IDS' not in globals():
    GPC_PENDING_IDS = set()
if 'GPC_LISTENERS_ACTIVE' not in globals():
    GPC_LISTENERS_ACTIVE = False

def handle_doc_changed(sender, args):
    """Fires when the model changes. Populates the module-level pending queue."""
    from pyrevit import script
    if not script.get_envvar('GPC_AUTOSYNC_ENABLED'):
        return
    
    # 1. Avoid infinite loops: Ignore changes triggered by our own sync/UI transactions
    our_transactions = ["GPC Background Sync", "Sync Model Elements", "Grid Cell Edit", "Import Cost Data from JSON"]
    trans_names = args.GetTransactionNames()
    if any(name in our_transactions for name in trans_names):
        return
        
    added = args.GetAddedElementIds()
    modified = args.GetModifiedElementIds()
    
    for eid in added: GPC_PENDING_IDS.add(eid)
    for eid in modified: GPC_PENDING_IDS.add(eid)

def handle_idling(sender, args):
    """Processes the pending element queue when Revit is idle."""
    from pyrevit import script
    if not GPC_PENDING_IDS or not script.get_envvar('GPC_AUTOSYNC_ENABLED'):
        return

    doc = revit.doc
    if not doc:
        return

    # Process pending IDs
    ids_to_process = list(GPC_PENDING_IDS)
    GPC_PENDING_IDS.clear()
    
    # We need database access here
    import database
    db_path = database.get_db_path(doc)
    store = database.get_store(db_path)
    
    elements = []
    for eid in ids_to_process:
        try:
            el = doc.GetElement(eid)
            if el and el.Category:
                elements.append(el)
        except:
            pass
            
    if elements:
        try:
            with revit.Transaction("GPC Background Sync"):
                sync_elements(doc, elements, store)
        except Exception:
            pass

def ensure_listeners():
    """Registers session-level listeners if they are not already active."""
    global GPC_LISTENERS_ACTIVE
    if not GPC_LISTENERS_ACTIVE:
        try:
            ui_app = revit.uidoc.Application
            db_app = ui_app.Application
            
            db_app.DocumentChanged += handle_doc_changed
            ui_app.Idling += handle_idling
            GPC_LISTENERS_ACTIVE = True
        except:
            pass

def remove_listeners():
    """Removes session-level listeners to free up resources."""
    global GPC_LISTENERS_ACTIVE
    if GPC_LISTENERS_ACTIVE:
        try:
            ui_app = revit.uidoc.Application
            db_app = ui_app.Application
            
            db_app.DocumentChanged -= handle_doc_changed
            ui_app.Idling -= handle_idling
            GPC_LISTENERS_ACTIVE = False
            GPC_PENDING_IDS.clear()
        except:
            pass

