# -*- coding: utf-8 -*-
"""
filter_utils.py
View filter creation for the MepLevels extension.

Phase 2: System filters per level (right-list levels from levels_association.json)
  Format:  "Ver [System] en [LevelName]"
  Systems: Domestic Water (Domestic Hot Water + Domestic Cold Water)
           Sanitary
           Vent
"""
import clr
clr.AddReference('RevitAPI')
import Autodesk.Revit.DB as aDB
from System.Collections.Generic import List
from Autodesk.Revit.DB import ParameterFilterUtilities

from pyrevit import revit, DB

# ---------------------------------------------------------------------------
# Target categories: pipes + fittings + accessories
# ---------------------------------------------------------------------------
PIPING_BICS_NAMES = [
    "OST_PipeCurves",
    "OST_FlexPipeCurves",
    "OST_PipeFitting",
    "OST_PipeAccessory",
]

def _safe_bic(name):
    try:
        return getattr(aDB.BuiltInCategory, name)
    except AttributeError:
        return None


def _safe_string_rule(provider, evaluator, value):
    """Safely create a FilterStringRule, handling Revit API version differences."""
    try:
        return aDB.FilterStringRule(provider, evaluator, value, False)
    except TypeError:
        return aDB.FilterStringRule(provider, evaluator, value)


def _piping_category_ids():
    ids = List[aDB.ElementId]()
    for name in PIPING_BICS_NAMES:
        bic = _safe_bic(name)
        if bic:
            ids.Add(aDB.ElementId(bic))
    return ids


def _get_filterable_piping_ids(doc, bip):
    """Return only the piping category IDs that support *bip* as a filterable parameter."""
    valid_ids = List[aDB.ElementId]()
    pid = aDB.ElementId(bip)
    for name in PIPING_BICS_NAMES:
        bic = _safe_bic(name)
        if not bic:
            continue
        cid = aDB.ElementId(bic)
        try:
            if ParameterFilterUtilities.IsFilterableParameter(doc, cid, pid):
                valid_ids.Add(cid)
        except Exception:
            valid_ids.Add(cid)  # include as fallback
    return valid_ids


# ---------------------------------------------------------------------------
# System classification string labels used by Revit in the parameter
# ---------------------------------------------------------------------------
_SYSTEM_LABELS = {
    "DomesticHotWater":  "Domestic Hot Water",
    "DomesticColdWater": "Domestic Cold Water",
    "Sanitary":          "Sanitary",
    "Vent":              "Vent",
}

# Filter definitions: (display_name_key, system_classification_keys_list)
# The filter name template:  "Ver {display_name} en {level_name}"
SYSTEM_FILTER_DEFS = [
    ("Agua Domestica", ["DomesticHotWater", "DomesticColdWater"]),
    ("Sanitario",      ["Sanitary"]),
    ("Vent",           ["Vent"]),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _make_string_equals_filter(param_id, value):
    """Return an ElementParameterFilter for param == value."""
    provider  = aDB.ParameterValueProvider(param_id)
    evaluator = aDB.FilterStringEquals()
    rule      = _safe_string_rule(provider, evaluator, value)
    return aDB.ElementParameterFilter(rule)


def _make_or_filter(filters):
    """Combine a list of ElementFilters with LogicalOrFilter."""
    if len(filters) == 1:
        return filters[0]
    return aDB.LogicalOrFilter(List[aDB.ElementFilter](filters))


def _get_existing_filter(doc, name):
    for f in (
        aDB.FilteredElementCollector(doc)
        .OfClass(aDB.ParameterFilterElement)
        .ToElements()
    ):
        if f.Name == name:
            return f
    return None


def _apply_filter_to_view(view, pfe):
    """Add *pfe* to *view* and enable visibility."""
    if not view.IsFilterApplied(pfe.Id):
        view.AddFilter(pfe.Id)
    view.SetFilterVisibility(pfe.Id, True)
    try:
        view.SetFilterEnabled(pfe.Id, True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def create_system_filters_for_levels(doc, target_level_names, view=None):
    """
    Create (or update) view filters for each combination of target level and
    system type.  Filter names follow the format:
        "Ver {system_display_name} en {level_name}"

    Parameters
    ----------
    doc               : Revit Document
    target_level_names: list[str]  – levels from the right-list association
    view              : optional View – if provided, filters are applied to it

    Returns a list of (filter_name, ParameterFilterElement) tuples created/updated.
    """
    bip = aDB.BuiltInParameter.RBS_PIPING_SYSTEM_TYPE_PARAM
    cat_ids = _get_filterable_piping_ids(doc, bip)

    if cat_ids.Count == 0:
        cat_ids = _piping_category_ids()

    results = []
    with revit.Transaction("GPC - Create System Filters"):
        for level_name in target_level_names:
            for display_name, sys_keys in SYSTEM_FILTER_DEFS:
                filter_name = u"Ver {} en {}".format(display_name, level_name)

                # Build OR filter for each system classification label
                sub_filters = []
                for key in sys_keys:
                    label = _SYSTEM_LABELS.get(key)
                    if label:
                        param_id = aDB.ElementId(bip)
                        sub_filters.append(_make_string_equals_filter(param_id, label))

                if not sub_filters:
                    continue

                elem_filter = _make_or_filter(sub_filters)

                existing = _get_existing_filter(doc, filter_name)
                if existing is not None:
                    existing.SetElementFilter(elem_filter)
                    existing.SetCategories(cat_ids)
                    pfe = existing
                else:
                    pfe = aDB.ParameterFilterElement.Create(
                        doc, filter_name, cat_ids, elem_filter
                    )

                if view is not None:
                    _apply_filter_to_view(view, pfe)

                results.append((filter_name, pfe))

    return results
