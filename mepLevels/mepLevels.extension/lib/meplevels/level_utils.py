# -*- coding: utf-8 -*-
"""
level_utils.py
Level helpers: reading level associations from JSON, element level detection,
normalization logic, and GPC_NivelMEP parameter writing.

Normalization rules (AGENTS.md §6):
  - Compute element's absolute elevation = level_elevation + offset
  - Find which level bracket it actually belongs to (positive offset stays
    positive, negative stays negative — never flip sign when crossing a boundary
    unless the offset sign was already negative)
  - Reassign element to the correct level and recalculate offset to maintain
    physical position
"""
import clr
import os
import json

clr.AddReference('RevitAPI')
import Autodesk.Revit.DB as aDB

from pyrevit import revit, DB

LEVEL_PARAM_NAMES = ["Level", "Reference Level"]
PARAM_NAME = "GPC_NivelMEP"


# ---------------------------------------------------------------------------
# Level parameter helpers
# ---------------------------------------------------------------------------
def get_level_param(element):
    """
    Return (parameter, param_name) for the element's level parameter.
    Uses BuiltInParameters for maximum reliability across languages.
    Returns (None, None) if no writable/readable level parameter is found.
    """
    # Priority 1: FAMILY_LEVEL_PARAM ("Level")
    p = element.get_Parameter(DB.BuiltInParameter.FAMILY_LEVEL_PARAM)
    if p: return p, "Level"

    # Priority 2: INSTANCE_REFERENCE_LEVEL_PARAM ("Reference Level")
    p = element.get_Parameter(DB.BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM)
    if p: return p, "Reference Level"

    # Priority 3: SCHEDULE_LEVEL_PARAM
    p = element.get_Parameter(DB.BuiltInParameter.SCHEDULE_LEVEL_PARAM)
    if p: return p, "Schedule Level"

    # Fallback to name search
    for name in LEVEL_PARAM_NAMES:
        p = element.LookupParameter(name)
        if p and p.StorageType == DB.StorageType.ElementId:
            return p, name

    return None, None


def is_level_writable(element):
    """True if the element has a Level/Reference Level parameter that is NOT read-only."""
    param, _ = get_level_param(element)
    return param is not None and not param.IsReadOnly


def get_element_level_id(element):
    """Return the ElementId of the element's level, or None."""
    if hasattr(element, "LevelId") and element.LevelId != DB.ElementId.InvalidElementId:
        return element.LevelId
    param, _ = get_level_param(element)
    if param:
        return param.AsElementId()
    return None


def get_element_level_name(element, doc):
    """Return the display name of the element's level, or None."""
    lvl_id = get_element_level_id(element)
    if lvl_id is None or lvl_id == DB.ElementId.InvalidElementId:
        return None
    lvl = doc.GetElement(lvl_id)
    return lvl.Name if lvl else None


def get_element_offset(element):
    """
    Return the element's elevation offset from its host level (in internal feet).
    Returns 0.0 if not found.
    """
    offset_bips = [
        DB.BuiltInParameter.RBS_OFFSET_PARAM,
        DB.BuiltInParameter.INSTANCE_FREE_HOST_OFFSET_PARAM,
        DB.BuiltInParameter.INSTANCE_ELEVATION_PARAM,
    ]
    for bip in offset_bips:
        p = element.get_Parameter(bip)
        if p and not p.IsReadOnly:
            return p.AsDouble()
    return 0.0


def set_element_offset(element, value_ft):
    """
    Set the element's elevation offset (in internal feet).
    Returns True if successful.
    """
    offset_bips = [
        DB.BuiltInParameter.RBS_OFFSET_PARAM,
        DB.BuiltInParameter.INSTANCE_FREE_HOST_OFFSET_PARAM,
        DB.BuiltInParameter.INSTANCE_ELEVATION_PARAM,
    ]
    for bip in offset_bips:
        p = element.get_Parameter(bip)
        if p and not p.IsReadOnly:
            try:
                p.Set(value_ft)
                return True
            except Exception:
                continue
    return False


# ---------------------------------------------------------------------------
# Level sorting helpers
# ---------------------------------------------------------------------------
def get_sorted_levels(doc):
    """Return all project levels sorted by elevation (ascending)."""
    levels = list(
        aDB.FilteredElementCollector(doc)
        .OfClass(aDB.Level)
        .WhereElementIsNotElementType()
    )
    return sorted(levels, key=lambda lvl: lvl.Elevation)


def get_adjacent_levels(doc, current_level):
    """
    Return (level_below, level_above) immediately adjacent to *current_level*.
    Either can be None if no adjacent level exists.
    """
    sorted_lvls = get_sorted_levels(doc)
    idx = next(
        (i for i, l in enumerate(sorted_lvls) if l.Id == current_level.Id),
        None
    )
    if idx is None:
        return None, None
    below = sorted_lvls[idx - 1] if idx > 0 else None
    above = sorted_lvls[idx + 1] if idx < len(sorted_lvls) - 1 else None
    return below, above


# ---------------------------------------------------------------------------
# Level Association JSON helpers
# ---------------------------------------------------------------------------
def get_association_file_path(doc):
    """
    Return the path to levels_association.json, placed next to the Revit model.
    Returns None if the document has not been saved.
    """
    model_path = doc.PathName
    if not model_path:
        return None
    folder = os.path.dirname(model_path)
    return os.path.join(folder, "levels_association.json")


def load_level_association(doc):
    """
    Load and return the levels association dict from JSON.
    Format: { "source_level_name": "target_level_name", ... }
    Returns empty dict if file not found or invalid.
    """
    path = get_association_file_path(doc)
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_level_association(doc, mapping):
    """
    Persist the association dict { source_name: target_name } to JSON.
    Returns True if successful.
    """
    path = get_association_file_path(doc)
    if not path:
        return False
    try:
        with open(path, "w") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_target_levels(doc):
    """
    Return a de-duplicated, sorted list of target level names from the association.
    These are the levels in the 'right list' used for filter creation.
    """
    mapping = load_level_association(doc)
    return sorted(set(mapping.values()))


# ---------------------------------------------------------------------------
# Normalization logic
# ---------------------------------------------------------------------------
def normalize_level(element, sorted_levels):
    """
    Determine the correct (level, new_offset_ft) for *element* based on its
    current absolute elevation.

    Rules (AGENTS.md §6):
      • absolute_elevation = current_level.Elevation + current_offset
      • If offset is positive (or zero), we look upward: the element belongs
        to the highest level whose elevation <= absolute_elevation.
      • If offset is negative, the element is anchored below its current level.
        We still compute the absolute elevation and find the bracket, but we
        preserve the sign: the element belongs to the lowest level whose
        elevation >= absolute_elevation (i.e., we round toward the level
        that gives a negative offset).
      • Boundary case: if absolute_elevation == a level's elevation, the
        element belongs exactly to that level with offset 0.
      • Never flip the sign of the resulting offset (positive stays positive,
        negative stays negative).

    Returns (target_level, new_offset_ft) or (None, None) if can't determine.
    """
    if not sorted_levels:
        return None, None

    current_level_id = get_element_level_id(element)
    if current_level_id is None:
        return None, None

    current_level = next(
        (l for l in sorted_levels if l.Id == current_level_id), None
    )
    if current_level is None:
        return None, None

    current_offset = get_element_offset(element)
    absolute_elev = current_level.Elevation + current_offset

    # Find target level
    target_level = None

    if current_offset >= 0:
        # Positive offset: find the highest level at or below absolute_elev
        for lvl in sorted_levels:
            if lvl.Elevation <= absolute_elev + 1e-9:
                target_level = lvl
            else:
                break
    else:
        # Negative offset: absolute_elev is below current level.
        # Find the lowest level whose elevation >= absolute_elev — that gives
        # a negative or zero offset.
        for lvl in sorted_levels:
            if lvl.Elevation >= absolute_elev - 1e-9:
                target_level = lvl
                break
        # If no level is above or at the absolute elevation, use the lowest level
        if target_level is None:
            target_level = sorted_levels[0]

    if target_level is None:
        return None, None

    new_offset = absolute_elev - target_level.Elevation
    return target_level, new_offset


def needs_normalization(element, sorted_levels):
    """
    Return True if the element's level assignment is incorrect according to
    the normalization rules (i.e., normalize_level would change its level).
    """
    current_level_id = get_element_level_id(element)
    if current_level_id is None:
        return False
    target_level, _ = normalize_level(element, sorted_levels)
    if target_level is None:
        return False
    return target_level.Id != current_level_id


def apply_normalization(element, sorted_levels):
    """
    Apply level normalization to *element* and write GPC_NivelMEP.
    Must be called inside an active Revit transaction.
    Returns True if any change was made.
    """
    if not element.IsValidObject:
        return False

    target_level, new_offset = normalize_level(element, sorted_levels)
    if target_level is None:
        return False

    current_level_id = get_element_level_id(element)
    current_offset = get_element_offset(element)
    changed = False

    param, _ = get_level_param(element)
    if param is not None and not param.IsReadOnly:
        if target_level.Id != current_level_id:
            try:
                param.Set(target_level.Id)
                changed = True
            except Exception:
                return False

    if abs(new_offset - current_offset) > 1e-9:
        set_element_offset(element, new_offset)
        changed = True

    # Write GPC_NivelMEP
    gpc = element.LookupParameter(PARAM_NAME)
    if gpc is not None and not gpc.IsReadOnly:
        try:
            gpc.Set(target_level.Name)
            changed = True
        except Exception:
            pass

    return changed


def set_gpc_nivel_mep(element, value):
    """
    Set GPC_NivelMEP to *value*.
    Returns True if successfully set.
    Must be called inside an active Revit transaction.
    """
    param = element.LookupParameter(PARAM_NAME)
    if param is not None and not param.IsReadOnly:
        try:
            return param.Set(value)
        except Exception:
            return False
    return False
