"""Inject GPC Shared Parameters into the project and bind them to all categories."""

__title__ = 'Setup\nParameters'
__author__ = 'Computos Revit Team'

from pyrevit import revit, DB, forms
import os
import sys
import codecs
import json

# Add lib folder to sys.path
# script.py (0) -> .pushbutton (1) -> .panel (2) -> .tab (3) -> .extension (4)
EXTENSION_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LIB_PATH = os.path.join(EXTENSION_DIR, "lib")
if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

import database
import sync

# --- Constants & Configuration ---
SHARED_PARAMS_FILENAME = "GPC-SharedParameters.txt"
# Point to the central shared parameters folder at the workspace root
_root = os.path.dirname(os.path.dirname(EXTENSION_DIR))
SHARED_PARAMS_PATH = os.path.join(_root, "shared_parameters", SHARED_PARAMS_FILENAME)

GROUP_NAME = "SistemaGPC"

# USER FILTER: Categories to SKIP for GPC parameter injection
CATEGORIES_TO_EXCLUDE = sync.CATEGORIES_TO_EXCLUDE

# Define parameters to inject (Name, Type, IsInstance)
def get_text_spec():
    try: return DB.SpecTypeId.String.Text
    except: return DB.SpecTypeId.Text

PARAMS_SPECS = [
    ("GPC-Cantidad", DB.SpecTypeId.Number, True),
    ("GPC-GrupoCosto", get_text_spec(), True), 
    ("GPC-CostoItem", DB.SpecTypeId.Currency, True),
    ("GPC-PrecioUnitario", DB.SpecTypeId.Currency, True),
    ("GPC-UnidadMedicion", get_text_spec(), True)
]

def get_shared_parameter_file(doc):
    """Retrieve the shared parameter file, creating it in UTF-16LE with BOM if it doesn't exist."""
    app = doc.Application
    if not os.path.exists(SHARED_PARAMS_PATH):
        forms.alert("Shared Parameter file not found at: {}\nCreating a new one...".format(SHARED_PARAMS_PATH))
        if not os.path.exists(os.path.dirname(SHARED_PARAMS_PATH)):
            os.makedirs(os.path.dirname(SHARED_PARAMS_PATH))
        
        # Revit shared parameter files MUST be UTF-16 LE with BOM
        header = (
            "# This is a Revit shared parameter file.\r\n"
            "*META\tVERSION\tMINVERSION\r\n"
            "META\t2\t1\r\n"
            "*GROUP\tID\tNAME\r\n"
            "GROUP\t1\t{}\r\n"
            "*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\tUSERMODIFIABLE\r\n"
        ).format(GROUP_NAME)
        
        with codecs.open(SHARED_PARAMS_PATH, 'w', 'utf-16') as f:
            f.write(header)
            
    app.SharedParametersFilename = SHARED_PARAMS_PATH
    return app.OpenSharedParameterFile()

def load_gpc_families(doc):
    """Loads all families from the centralized shared_parameters/families directory."""
    families_dir = os.path.join(_root, "shared_parameters", "families")
    
    if not os.path.isdir(families_dir):
        return 0

    family_files = [f for f in os.listdir(families_dir) if f.lower().endswith('.rfa')]
    
    loaded_count = 0
    # Collect existing families to avoid redundant loading
    existing_families = {f.Name for f in DB.FilteredElementCollector(doc).OfClass(DB.Family)}
    
    with revit.Transaction("Load Families"):
        for f_file in family_files:
            f_name = f_file[:-4] # Remove .rfa
            if f_name in existing_families:
                continue
                
            f_path = os.path.join(families_dir, f_file)
            try:
                if doc.LoadFamily(f_path):
                    loaded_count += 1
            except Exception as e:
                print("Could not load family {}: {}".format(f_name, e))
                    
    return loaded_count

def inject_parameters():
    doc = revit.doc
    app = doc.Application
    
    # 0. Load Required Families
    loaded_count = load_gpc_families(doc)
    
    # 1. Open Shared Parameter File
    sp_file = get_shared_parameter_file(doc)
    if not sp_file:
        forms.alert("Could not open shared parameter file.", title="Error")
        return

    # 2. Get or Create the Group
    group = sp_file.Groups.get_Item(GROUP_NAME)
    if not group:
        group = sp_file.Groups.Create(GROUP_NAME)

    # 3. Collect MODEL Categories for binding
    cat_set = app.Create.NewCategorySet()
    
    # Track skipped categories to help debug
    skipped_model_cats = []
    
    for category in doc.Settings.Categories:
        # Check if it's a model category
        if category.CategoryType == DB.CategoryType.Model:
            name = category.Name
            
            # Primary filter: AllowsBoundParameters
            # (In some Revit versions, Fabrication Parts might return False here if not enabled)
            if not category.AllowsBoundParameters:
                # skipped_model_cats.append("{} (Not Bindable)".format(name))
                continue
                
            # Filter by exclusion list
            exclusion_match = next((excl for excl in CATEGORIES_TO_EXCLUDE if excl.lower() in name.lower()), None)
            if exclusion_match:
                # skipped_model_cats.append("{} (Excluded by '{}')".format(name, exclusion_match))
                continue
            
            # If we reached here, it's a valid category
            cat_set.Insert(category)
            
    # Explicitly print summary of what's happening (helpful for user)
    # print("Categories collection: Found {} bindable model categories.".format(cat_set.Size))


    # 4. Start Transaction
    with revit.Transaction("Inject and Initialize Parameters"):
        binding_map = doc.ParameterBindings
        count_injected = 0
        count_already_present = 0
        revit_version = int(app.VersionNumber)
        
        # Group compatibility
        if revit_version >= 2024:
            param_group = DB.GroupTypeId.Data
        else:
            param_group = DB.BuiltInParameterGroup.PG_DATA

        with forms.ProgressBar(title="Injecting Parameters...", step=1, total=len(PARAMS_SPECS)) as pb:
            for i, (param_name, spec_type_id, is_instance) in enumerate(PARAMS_SPECS):
                pb.update_progress(i, len(PARAMS_SPECS))
                
                if not param_name.startswith("GPC-"): continue
                
                definition = group.Definitions.get_Item(param_name)
                if not definition:
                    opt = DB.ExternalDefinitionCreationOptions(param_name, spec_type_id)
                    definition = group.Definitions.Create(opt)
                
                if not definition:
                    print("Could not find or create definition for {}".format(param_name))
                    continue

                # Prepare Binding
                if is_instance:
                    new_binding = app.Create.NewInstanceBinding(cat_set)
                else:
                    new_binding = app.Create.NewTypeBinding(cat_set)

                success = False
                if binding_map.Contains(definition):
                    # Check if matching binding type
                    existing_binding = binding_map.get_Item(definition)
                    is_currently_instance = isinstance(existing_binding, DB.InstanceBinding)
                    
                    if is_currently_instance == is_instance:
                        # Update existing binding categories
                        success = binding_map.ReInsert(definition, new_binding, param_group)
                    else:
                        # Re-create binding if type changed
                        binding_map.Remove(definition)
                        success = binding_map.Insert(definition, new_binding, param_group)
                else:
                    # New binding
                    success = binding_map.Insert(definition, new_binding, param_group)

                if success:
                    count_injected += 1
                    # Apply specific properties (e.g. Vary by group)
                    if is_instance and (param_name == "GPC-PrecioUnitario" or param_name == "GPC-CostoItem"):
                        param_elements = DB.FilteredElementCollector(doc).OfClass(DB.ParameterElement).ToElements()
                        for pe in param_elements:
                            if pe.Name == param_name:
                                internal_def = pe.GetDefinition()
                                if isinstance(internal_def, DB.InternalDefinition):
                                    try: internal_def.SetAllowVaryBetweenGroups(doc, True)
                                    except: pass
                                break
                else:
                    print("Failed to bind parameter: {}".format(param_name))

    forms.alert("Setup Complete\n\nFamilies Loaded: {}\nParameters Injected/Updated: {}".format(loaded_count, count_injected), title="Result")

if __name__ == "__main__":
    inject_parameters()
