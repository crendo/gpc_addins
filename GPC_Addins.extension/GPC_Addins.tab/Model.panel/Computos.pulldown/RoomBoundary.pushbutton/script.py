# -*- coding: utf-8 -*-
from pyrevit import revit, DB, forms
import clr

# Import System Collections for strict typing if needed
clr.AddReference("System")
from System.Collections.Generic import List

def create_room_boundary_polygons():
    """
    Creates Generic Model (DirectShape) elements matching the room boundary.
    Configured for GPC Takeoff with Area or Perimeter.
    """
    doc = revit.doc
    view = revit.active_view
    
    # Try to get selection first
    selection = revit.get_selection()
    rooms = [el for el in selection if isinstance(el, DB.Architecture.Room)]
    
    if not rooms:
        # If no rooms selected, show a picker
        collector = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()
        placed_rooms = [r for r in collector if r.Area > 0]
        
        if not placed_rooms:
            forms.alert(u"No placed rooms found in the project.", title=u"No Rooms")
            return
            
        rooms = forms.SelectFromList.show(
            placed_rooms,
            title=u"Select Rooms to Create Polygons",
            button_name=u"Process",
            width=500,
            multiselect=True
        )
    
    if not rooms:
        return

    # 1. Choose GPC Measurement Unit
    gpc_unit = forms.CommandSwitchWindow.show(
        [u"m", u"m2"],
        message=u"Select GPC Measurement Unit for the Polygons:"
    )
    if not gpc_unit:
        return

    # 2. Get Generic Model Category ID
    cat_id = doc.Settings.Categories.get_Item(DB.BuiltInCategory.OST_GenericModel).Id

    # 3. Process Rooms
    with revit.Transaction("Create Room Polygons (Generic Model)"):
        # Use Wall Finish face for the room shape
        options = DB.SpatialElementBoundaryOptions()
        options.SpatialElementBoundaryLocation = DB.SpatialElementBoundaryLocation.Finish
        
        total_created = 0
        for room in rooms:
            try:
                # Get boundary segments
                loops = room.GetBoundarySegments(options)
                if not loops:
                    continue
                
                # Prepare geometry loops
                curve_loops = List[DB.CurveLoop]()
                for loop in loops:
                    c_loop = DB.CurveLoop()
                    for segment in loop:
                        c_loop.Append(segment.GetCurve())
                    curve_loops.Add(c_loop)
                
                if curve_loops.Count > 0:
                    try:
                        # Create a flat extrusion (1cm height) at the room's level
                        # Note: room.GetBoundarySegments() returns curves at the room base
                        solid = DB.GeometryCreationUtilities.CreateExtrusionGeometry(
                            curve_loops, 
                            DB.XYZ.BasisZ, 
                            0.01 / 0.3048 # ~1cm feet
                        )
                        
                        ds = DB.DirectShape.CreateElement(doc, cat_id)
                        ds.SetShape([solid])
                        
                        # Naming: Poligono-Roomxx
                        room_number = room.get_Parameter(DB.BuiltInParameter.ROOM_NUMBER).AsString()
                        ds.Name = u"Poligono-Room{}".format(room_number)
                        
                        # GPC System Parameters
                        p_gpc_unit = ds.LookupParameter("GPC-UnidadMedicion")
                        if p_gpc_unit and not p_gpc_unit.IsReadOnly:
                            p_gpc_unit.Set(gpc_unit)
                            
                        p_gpc_qty = ds.LookupParameter("GPC-Cantidad")
                        if p_gpc_qty and not p_gpc_qty.IsReadOnly:
                            if gpc_unit == "m":
                                val = DB.UnitUtils.ConvertFromInternalUnits(room.Perimeter, DB.UnitTypeId.Meters)
                                p_gpc_qty.Set(val)
                            elif gpc_unit == "m2":
                                val = DB.UnitUtils.ConvertFromInternalUnits(room.Area, DB.UnitTypeId.SquareMeters)
                                p_gpc_qty.Set(val)

                        # NEW: Add Cost and Identity Parameters
                        # Comments (Use Room Name)
                        room_name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()
                        p_ds_comments = ds.get_Parameter(DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
                        if room_name and p_ds_comments and not p_ds_comments.IsReadOnly:
                            p_ds_comments.Set(room_name)

                        # GPC Cost Parameters (Initialize to 0.0)
                        p_punit = ds.LookupParameter("GPC-PrecioUnitario")
                        if p_punit and not p_punit.IsReadOnly:
                            p_punit.Set(0.0)

                        p_costitem = ds.LookupParameter("GPC-CostoItem")
                        if p_costitem and not p_costitem.IsReadOnly:
                            p_costitem.Set(0.0)
                            
                        total_created += 1
                    except Exception as inner_e:
                        print("DirectShape Error: {}".format(inner_e))
                        
            except Exception as e:
                print("Room Error {}: {}".format(room.Id, e))
        
        forms.toast(u"Created {} Polygons (Generic Models) for {} rooms.".format(total_created, len(rooms)))

if __name__ == "__main__":
    create_room_boundary_polygons()
