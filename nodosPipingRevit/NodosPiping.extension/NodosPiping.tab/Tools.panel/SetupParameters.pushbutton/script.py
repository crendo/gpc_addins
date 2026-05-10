# -*- coding: utf-8 -*-
"""Setup Shared Parameters for Nodos Piping."""

__title__ = 'Setup\nParameters'
__author__ = 'Antigravity'

import os
from pyrevit import revit, DB, forms

# --- Configuration ---
SHARED_PARAMS_FILENAME = "GPC-SharedParameters.txt"

# Calculate root path (6 levels up from this file)
# script.py (0) -> SetupParameters.pushbutton (1) -> Tools.panel (2) -> NodosPiping.tab (3) -> NodosPiping.extension (4) -> nodosPipingRevit (5) -> gpc_addins (6)
_root = __file__
for _ in range(6):
    _root = os.path.dirname(_root)

SHARED_PARAMS_PATH = os.path.join(_root, "shared_parameters", SHARED_PARAMS_FILENAME)
GROUP_NAME = "SistemaGPC"

# Parameters used by Nodos Piping and MEP Levels
TARGET_PARAMS = [
    "Node_Number",
    "Nodo_Inicio",
    "Nodo_Final",
    "DeltaZ",
    "Elev_Node_Number",
    "GPC_NivelMEP",
    "GPC-CWFU",
    "GPC-HWFU"
]

# Categories to bind to
MEP_CATEGORIES = [
    DB.BuiltInCategory.OST_PipeCurves,
    DB.BuiltInCategory.OST_PipeFitting,
    DB.BuiltInCategory.OST_PipeAccessory,
    DB.BuiltInCategory.OST_PlumbingFixtures,
    DB.BuiltInCategory.OST_PlumbingEquipment,
    DB.BuiltInCategory.OST_MechanicalEquipment,
    DB.BuiltInCategory.OST_FlexPipeCurves
]

def get_shared_parameter_file(doc):
    if not os.path.exists(SHARED_PARAMS_PATH):
        forms.alert("Shared Parameter file not found at: {}".format(SHARED_PARAMS_PATH))
        return None
    doc.Application.SharedParametersFilename = SHARED_PARAMS_PATH
    return doc.Application.OpenSharedParameterFile()

def setup_parameters():
    doc = revit.doc
    app = doc.Application
    
    # 1. Open Shared Parameter File
    sp_file = get_shared_parameter_file(doc)
    if not sp_file:
        return

    # 2. Get the Group
    group = sp_file.Groups.get_Item(GROUP_NAME)
    if not group:
        forms.alert("Group '{}' not found in shared parameter file.".format(GROUP_NAME))
        return

    # 3. Collect Categories
    cat_set = app.Create.NewCategorySet()
    for bic in MEP_CATEGORIES:
        cat = doc.Settings.Categories.get_Item(bic)
        if cat and cat.AllowsBoundParameters:
            cat_set.Insert(cat)

    # 4. Inject Parameters
    with revit.Transaction("Setup Nodos Piping Parameters"):
        binding_map = doc.ParameterBindings
        count = 0
        
        # Group compatibility
        revit_version = int(app.VersionNumber)
        if revit_version >= 2024:
            param_group = DB.GroupTypeId.Data
        else:
            param_group = DB.BuiltInParameterGroup.PG_DATA

        for param_name in TARGET_PARAMS:
            definition = group.Definitions.get_Item(param_name)
            if not definition:
                print("Definition not found for: {}".format(param_name))
                continue
            
            new_binding = app.Create.NewInstanceBinding(cat_set)
            
            if binding_map.Contains(definition):
                binding_map.ReInsert(definition, new_binding, param_group)
            else:
                binding_map.Insert(definition, new_binding, param_group)
            count += 1

    forms.alert("Setup Complete\n\nParameters Injected/Updated: {}".format(count), title="Result")

if __name__ == "__main__":
    setup_parameters()
