# -*- coding: utf-8 -*-
"""
shared_params.py
Handles creation and binding of the GPC_NivelMEP shared instance parameter
to the 5 target piping categories.

Revit 2023/2025 compatible:
  - Uses GroupTypeId.Data instead of deprecated BuiltInParameterGroup.PG_DATA
  - Uses SpecTypeId.String.Text instead of deprecated ParameterType.Text
"""
import os
import clr
clr.AddReference('RevitAPI')
import Autodesk.Revit.DB as aDB   # direct CLR namespace – always works in IronPython

from pyrevit import revit, DB     # pyRevit proxy kept for Transaction helper

PARAM_NAME       = "GPC_NivelMEP"
PARAM_GROUP_NAME = "SistemaGPC"

# Path to the shared parameters file in the central 'shared_parameters' directory
# (4 levels up from this file to the gpc_addins root)
_root = __file__
for _ in range(4):
    _root = os.path.dirname(_root)
SHARED_PARAM_FILE = os.path.join(_root, "shared_parameters", "GPC-SharedParameters.txt")
FAMILIES_DIR      = os.path.join(_root, "shared_parameters", "families")

# Helper to safely get BuiltInCategory members
def _safe_bic(name):
    try:
        return getattr(aDB.BuiltInCategory, name)
    except AttributeError:
        return None

MEP_BICS_NAMES = [
    # Piping
    "OST_PipeCurves", "OST_FlexPipeCurves", "OST_PipeFitting",
    "OST_PipeAccessory", "OST_PlumbingFixtures", "OST_Sprinklers",
    # HVAC
    "OST_DuctCurves", "OST_FlexDuctCurves", "OST_DuctFitting",
    "OST_DuctAccessory", "OST_DuctTerminal", "OST_MechanicalEquipment",
    # Electrical
    "OST_Conduit", "OST_ConduitFitting", "OST_CableTray", "OST_CableTrayFitting",
    "OST_LightingFixtures", "OST_ElectricalEquipment", "OST_ElectricalFixtures",
    "OST_DataDevices", "OST_CommunicationDevices", "OST_FireAlarmDevices", "OST_SecurityDevices",
]

MEP_CATEGORIES = [bic for bic in (_safe_bic(n) for n in MEP_BICS_NAMES) if bic is not None]


def _get_or_create_definition(app):
    """Load the shared parameter file and return the GPC_NivelMEP definition."""
    original = app.SharedParametersFilename
    try:
        app.SharedParametersFilename = SHARED_PARAM_FILE
        spf = app.OpenSharedParameterFile()
        if spf is None:
            raise Exception(
                "Cannot open shared parameter file: {}".format(SHARED_PARAM_FILE)
            )
        group = spf.Groups.get_Item(PARAM_GROUP_NAME)
        if group is None:
            group = spf.Groups.Create(PARAM_GROUP_NAME)

        defn = group.Definitions.get_Item(PARAM_NAME)
        if defn is None:
            opts = aDB.ExternalDefinitionCreationOptions(
                PARAM_NAME, aDB.SpecTypeId.String.Text
            )
            opts.UserModifiable = True
            defn = group.Definitions.Create(opts)
        return defn
    finally:
        app.SharedParametersFilename = original


def _get_missing_categories(doc):
    """Return a list of categories from MEP_CATEGORIES that are NOT yet bound to GPC_NivelMEP."""
    it = doc.ParameterBindings.ForwardIterator()
    bound_cat_ids = []
    while it.MoveNext():
        if it.Key.Name == PARAM_NAME:
            binding = it.Current
            if hasattr(binding, 'Categories'):
                for cat in binding.Categories:
                    bound_cat_ids.append(cat.Id.IntegerValue)
            break
    
    missing = []
    for bic in MEP_CATEGORIES:
        if int(bic) not in bound_cat_ids:
            missing.append(bic)
    return missing


def _build_category_set(doc):
    cat_set = doc.Application.Create.NewCategorySet()
    for bic in MEP_CATEGORIES:
        try:
            cat = doc.Settings.Categories.get_Item(bic)
            if cat and cat.AllowsBoundParameters:
                cat_set.Insert(cat)
        except Exception:
            pass
    return cat_set


def ensure_parameter_bound(doc):
    """
    Bind GPC_NivelMEP to the target categories if missing.
    Returns True if the binding was updated/applied, False if already fully bound.
    """
    missing = _get_missing_categories(doc)
    if not missing:
        return False

    defn    = _get_or_create_definition(doc.Application)
    cat_set = _build_category_set(doc)
    binding = doc.Application.Create.NewInstanceBinding(cat_set)

    # Preferred group for general instance parameters
    group_type = aDB.GroupTypeId.Data
    try:
        # Check for General group availability (Revit 2023+)
        _ = aDB.GroupTypeId.General
        group_type = aDB.GroupTypeId.General
    except Exception:
        try:
            group_type = aDB.BuiltInParameterGroup.PG_DATA
        except Exception:
            pass

    success = False
    with revit.Transaction("GPC - Bind NivelMEP Parameter"):
        # Check if already bound to use ReInsert vs Insert
        if doc.ParameterBindings.Contains(defn):
            success = doc.ParameterBindings.ReInsert(defn, binding, group_type)
        else:
            success = doc.ParameterBindings.Insert(defn, binding, group_type)

    return success


def load_families(doc):
    """
    Load all families from the centralized shared_parameters/families directory.
    Returns the number of families successfully loaded.
    """
    if not os.path.isdir(FAMILIES_DIR):
        return 0

    family_files = [f for f in os.listdir(FAMILIES_DIR) if f.lower().endswith('.rfa')]
    if not family_files:
        return 0

    # Collect existing families to avoid redundant loading
    existing_families = {f.Name for f in aDB.FilteredElementCollector(doc).OfClass(aDB.Family)}
    
    loaded_count = 0
    with revit.Transaction("GPC - Load Families"):
        for f_file in family_files:
            f_name = f_file[:-4] # Remove .rfa
            if f_name in existing_families:
                continue
                
            f_path = os.path.join(FAMILIES_DIR, f_file)
            try:
                # LoadFamily returns True if it was loaded or already present but reloaded
                if doc.LoadFamily(f_path):
                    loaded_count += 1
            except Exception:
                pass
                    
    return loaded_count
