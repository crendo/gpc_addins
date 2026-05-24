# -*- coding: utf-8 -*-
"""Hide all GPC Takeoff markers (Area and Lineal)."""
__title__ = 'Ocultar Marcadores'
__author__ = 'Computos Revit Team'

from pyrevit import revit, DB, forms
import clr
clr.AddReference("System")
from System.Collections.Generic import List

def set_markers_visibility(visible):
    doc = revit.doc
    view = doc.ActiveView
    
    # 1. Collect Family Instances (Generic Models)
    collector = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).WhereElementIsNotElementType()
    
    # 2. Collect DirectShapes (Room Polygons / Generic Models)
    ds_collector = DB.FilteredElementCollector(doc).OfClass(DB.DirectShape).WhereElementIsNotElementType()
    
    markers = []
    # Identify markers by name (flexible dash/underscore)
    for el in collector:
        fam_name = el.Symbol.Family.Name
        if "GPC-CM" in fam_name:
            markers.append(el)
            
    for ds in ds_collector:
        if "GPC-CM" in ds.Name or "Poligono" in ds.Name:
            markers.append(ds)
            
    if not markers:
        forms.toast("No GPC Takeoff markers found in the project.", title="Markers Not Found")
        return
 
    # Expanded parameter names for both 2D (Symbolic) and 3D (Model) visibility
    param_names = [
        "LineasVisible", "LineaVisible", 
        "ModeloVisible", "ModelVisible", "VisibleModelo", "VisibilidadModelo",
        "Lineas3D", "Lineas 3D", "CuerpoVisible", "Visible"
    ]
    
    count = 0
    with revit.Transaction("Toggle GPC Markers"):
        for marker in markers:
            success = False
            
            # Handle Family Instances via Parameters
            if isinstance(marker, DB.FamilyInstance):
                for p_name in param_names:
                    # Check Instance Parameter
                    p = marker.LookupParameter(p_name)
                    if not p:
                        # Check Type Parameter
                        p = marker.Symbol.LookupParameter(p_name)
                        
                    if p and not p.IsReadOnly:
                        p.Set(1 if visible else 0)
                        success = True
                if success:
                    count += 1
            
            # Handle DirectShapes (Generic Models without parameters) via View Visibility
            elif isinstance(marker, DB.DirectShape):
                if visible:
                    view.UnhideElements(List[DB.ElementId]([marker.Id]))
                else:
                    if view.CanElementBeHidden(marker.Id):
                        view.HideElements(List[DB.ElementId]([marker.Id]))
                count += 1
                
    status = "visible" if visible else "ocultos"
    forms.toast("Done! {} markers have been {}.".format(count, status), title="Visibilidad")

if __name__ == "__main__":
    set_markers_visibility(False)
