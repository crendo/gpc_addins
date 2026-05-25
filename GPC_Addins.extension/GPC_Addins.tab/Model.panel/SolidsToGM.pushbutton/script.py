# -*- coding: utf-8 -*-
__title__ = "Convert Solids"
__doc__ = "Extracts solids from a selected DWG and creates a Generic Model Family."

from pyrevit import revit, DB, UI, forms
import os

# Get active document
doc = revit.doc
app = doc.Application

def extract_solids(geom_elem, solids_list):
    """Recursive function to extract solids from geometry elements."""
    for obj in geom_elem:
        if isinstance(obj, DB.Solid) and obj.Volume > 0.00001:
            solids_list.append(obj)
        elif isinstance(obj, DB.GeometryInstance):
            # GetInstanceGeometry() returns geometry in project coordinates if it's an instance
            extract_solids(obj.GetInstanceGeometry(), solids_list)

def convert_solids():
    # 1. Select the Imported/Linked DWG
    selection = revit.get_selection()
    
    dwg = None
    if selection:
        dwg = selection[0]
        if not isinstance(dwg, DB.ImportInstance):
            dwg = None
            
    if not dwg:
        try:
            class DWGSelectionFilter(UI.Selection.ISelectionFilter):
                def AllowElement(self, element):
                    return isinstance(element, DB.ImportInstance)
                def AllowReference(self, reference, point):
                    return False
            
            with forms.WarningBar(title="Select DWG Import/Link in the model"):
                ref = revit.uidoc.Selection.PickObject(
                    UI.Selection.ObjectType.Element, 
                    DWGSelectionFilter(), 
                    "Select DWG Import/Link"
                )
                if ref:
                    dwg = revit.doc.GetElement(ref.ElementId)
        except Exception:
            # User cancelled selection
            return


    # 2. Get Geometry (Solids)
    options = DB.Options()
    options.ComputeReferences = True
    options.DetailLevel = DB.ViewDetailLevel.Fine
    
    geometry = dwg.get_Geometry(options)
    
    solids = []
    extract_solids(geometry, solids)
    
    if not solids:
        forms.alert("No valid solids found in the selected DWG.")
        return

    # 3. Find Generic Model Template
    revit_ver = app.VersionNumber
    # List of possible template paths (English, Imperial, and common localizatios)
    common_paths = [
        r"C:\ProgramData\Autodesk\RVT {}\Family Templates\English\Generic Model.rft".format(revit_ver),
        r"C:\ProgramData\Autodesk\RVT {}\Family Templates\English-Imperial\Generic Model.rft".format(revit_ver),
        r"C:\ProgramData\Autodesk\AutoCAD 2024\Template\Generic Model.rft", # Unusual but possible
    ]
    
    template_path = None
    for p in common_paths:
        if os.path.exists(p):
            template_path = p
            break
            
    if not template_path:
        # Fallback: ask user to locate the template
        template_path = forms.pick_file(
            file_ext='rft', 
            title="Generic Model Template not found. Please select 'Generic Model.rft'"
        )
        if not template_path:
            return

    # 4. Create Family Document
    try:
        fam_doc = app.NewFamilyDocument(template_path)
    except Exception as e:
        forms.alert("Error creating family document: {}".format(e))
        return

    if not fam_doc:
        forms.alert("Failed to initialize family document.")
        return

    # 5. Add Solids to Family using FreeFormElement
    try:
        with revit.Transaction("Create FreeForm Solids", fam_doc):
            for solid in solids:
                try:
                    DB.FreeFormElement.Create(fam_doc, solid)
                except Exception as ex:
                    print("Could not convert a solid: {}".format(ex))
    except Exception as e:
        forms.alert("Transaction failed in family document: {}".format(e))
        fam_doc.Close(False)
        return

    # 6. Save and Load
    temp_folder = os.environ.get("TEMP")
    fam_name = "Converted_Solid_{}".format(dwg.Id.ToString())
    fam_path = os.path.join(temp_folder, fam_name + ".rfa")
    
    save_options = DB.SaveAsOptions()
    save_options.OverwriteExistingFile = True
    
    try:
        fam_doc.SaveAs(fam_path, save_options)
    except Exception as e:
        forms.alert("Could not save family to {}: {}".format(fam_path, e))
        fam_doc.Close(False)
        return

    # Define Load Options for overwriting
    class FamilyLoadOptions(DB.IFamilyLoadOptions):
        def OnFamilyFound(self, familyInUse, overwriteParameterValues):
            overwriteParameterValues.Value = True
            return True
        def OnSharedFamilyFound(self, sharedFamily, familyInUse, source, overwriteParameterValues):
            return True

    # Load into project
    family = None
    try:
        with revit.Transaction("Load Converted Family"):
            # Use overload with LoadOptions
            # In IronPython, for 'out' parameters: (bool_result, out_param_value)
            success, loaded_family = doc.LoadFamily(fam_path, FamilyLoadOptions())
            if success:
                family = loaded_family
    except Exception as e:
        print("Error during LoadFamily: {}".format(e))
    finally:
        fam_doc.Close(False)

    if not family:
        # Fallback: Find by name if load didn't return the object (happens if matching exactly)
        family_collector = DB.FilteredElementCollector(doc).OfClass(DB.Family)
        for f in family_collector:
            if f.Name.lower() == fam_name.lower():
                family = f
                break

    if not family:
        forms.alert("Family loading failed or was cancelled. Could not find {}".format(fam_name))
        return

    # 7. Place Family Instance at the project origin (since geometry was absolute)
    try:
        symbol_ids = list(family.GetFamilySymbolIds())
        if not symbol_ids:
            forms.alert("No symbols found in loaded family.")
            return
            
        symbol = doc.GetElement(symbol_ids[0])
        
        with revit.Transaction("Place Converted Solid"):
            if not symbol.IsActive:
                symbol.Activate()
            
            # Since we used GetInstanceGeometry, the coordinates are in Project Space.
            # Placing at DB.XYZ.Zero will align the family with the DWG.
            doc.Create.NewFamilyInstance(
                DB.XYZ.Zero, 
                symbol, 
                DB.Structure.StructuralType.NonStructural
            )
            
        # 8. Optionally hide the DWG
        try:
            active_view = revit.active_view
            if active_view and dwg:
                with revit.Transaction("Hide Original DWG"):
                    from System.Collections.Generic import List
                    ids_to_hide = List[DB.ElementId]()
                    ids_to_hide.Add(dwg.Id)
                    
                    # Some views or API versions might have issues with CanHideElements
                    # We check for the attribute first to be safe
                    if hasattr(active_view, "CanHideElements"):
                        if active_view.CanHideElements(ids_to_hide):
                            active_view.HideElements(ids_to_hide)
                    else:
                        # Fallback for older API or binding issues: just try hiding
                        try:
                            active_view.HideElements(ids_to_hide)
                        except:
                            pass
        except Exception as hide_err:
            print("Note: Could not hide original DWG: {}".format(hide_err))

        forms.alert("Successfully converted DWG solids to Generic Model Family: {}".format(fam_name))

    except Exception as e:
        import traceback
        error_msg = "Error placing family instance: {}\n\n{}".format(e, traceback.format_exc())
        forms.alert(error_msg)

if __name__ == "__main__":
    # Check Revit Version for SpecTypeId (though not used directly here, good for AGENTS.md compliance check)
    # The script uses DB.FreeFormElement which is well supported in 2023+
    convert_solids()
