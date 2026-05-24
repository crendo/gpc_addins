# -*- coding: utf-8 -*-
from pyrevit import revit, DB, forms
# import clr # Not needed for WPF in pyRevit forms


# Path to UI
xaml_file = __file__.replace('script.py', 'ui.xaml')

class LineByCoordsWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        forms.WPFWindow.__init__(self, xaml_file_name)

    def Plot_Click(self, sender, e):
        try:
            # Parse inputs
            e1 = float(self.txtEast1.Text)
            n1 = float(self.txtNorth1.Text)
            e2 = float(self.txtEast2.Text)
            n2 = float(self.txtNorth2.Text)

            # Convert meters to feet (Revit Internal Units)
            to_feet = 3.2808399
            
            p1 = DB.XYZ(e1 * to_feet, n1 * to_feet, 0)
            p2 = DB.XYZ(e2 * to_feet, n2 * to_feet, 0)

            doc = revit.doc
            view = doc.ActiveView

            if not view.ViewType in [DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.EngineeringPlan, DB.ViewType.Detail]:
                forms.alert("Please run this command in a Plan or Detail view.")
                return

            if p1.IsAlmostEqualTo(p2):
                forms.alert("Start and End points cannot be the same.")
                return

            # Use explicit transaction for better stability
            t = DB.Transaction(doc, "Draw Line by Coordinates")
            t.Start()
            try:
                # Create a Detail Line
                line = DB.Line.CreateBound(p1, p2)
                doc.Create.NewDetailCurve(view, line)
                t.Commit()
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
    win = LineByCoordsWindow(xaml_file)
    win.ShowDialog()
