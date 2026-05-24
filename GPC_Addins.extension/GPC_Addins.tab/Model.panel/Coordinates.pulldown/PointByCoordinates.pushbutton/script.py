# -*- coding: utf-8 -*-
from pyrevit import revit, DB, forms
# import clr # Not needed for WPF in pyRevit forms


# Path to UI
xaml_file = __file__.replace('script.py', 'ui.xaml')

class PointByCoordsWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        forms.WPFWindow.__init__(self, xaml_file_name)
        self.point_plotted = False

    def Plot_Click(self, sender, e):
        try:
            east = float(self.txtEast.Text)
            north = float(self.txtNorth.Text)
            radius_m = float(self.txtRadius.Text)

            # Convert meters to feet (Revit Internal Units)
            # 1 meter = 3.2808399 feet
            to_feet = 3.2808399
            east_ft = east * to_feet
            north_ft = north * to_feet
            radius_ft = radius_m * to_feet

            center = DB.XYZ(east_ft, north_ft, 0)
            
            doc = revit.doc
            view = doc.ActiveView

            if not view.ViewType in [DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.EngineeringPlan, DB.ViewType.Detail]:
                forms.alert("Please run this command in a Plan or Detail view.")
                return

            # Use explicit transaction for better stability
            t = DB.Transaction(doc, "Plot Point by Coordinates")
            t.Start()
            try:
                # Create a circle (Detail Arc)
                arc = DB.Arc.Create(center, radius_ft, 0, 2 * 3.14159, view.RightDirection, view.UpDirection)
                doc.Create.NewDetailCurve(view, arc)
                t.Commit()
                self.point_plotted = True
                self.Close()
            except Exception as e:
                t.RollBack()
                forms.alert("Transaction failed: {}".format(str(e)))

            
        except ValueError:
            forms.alert("Please enter valid numeric values.")
        except Exception as ex:
            forms.alert("Error: {}".format(str(ex)))

    def Cancel_Click(self, sender, e):
        self.Close()

if __name__ == "__main__":
    win = PointByCoordsWindow(xaml_file)
    win.ShowDialog()
