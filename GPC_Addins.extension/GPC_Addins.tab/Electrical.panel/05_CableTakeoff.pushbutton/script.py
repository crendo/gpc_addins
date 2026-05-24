# -*- coding: utf-8 -*-
"""Cable Takeoff tool: aggregate, sum, and export cable lengths in selected or all conduits."""

__title__ = 'Cable Takeoff'
__author__ = 'Electrical Team'

import os
import json
import csv
import codecs
import clr  # type: ignore

# Load .NET assemblies for WPF and standard components
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")
clr.AddReference("System")

import System.Windows as Windows  # type: ignore
import System.Windows.Data as Data  # type: ignore
import System.Windows.Controls as Controls  # type: ignore
import Microsoft.Win32 as Win32  # type: ignore
from pyrevit import revit, DB, UI, forms, script  # type: ignore

doc = revit.doc
uidoc = revit.uidoc

# --- WPF Grid Binding Models ---
# The IronPython runtime exposes properties decorated with @property
# as standard .NET descriptors, allowing the WPF DataGrid to bind to them.

class BothGroupRow(object):
    def __init__(self, circuit, cable_type, wires, length):
        self._circuit = str(circuit)
        self._cable_type = str(cable_type)
        self._wires = int(wires)
        self._length = float(length)

    @property
    def Circuit(self):
        return self._circuit

    @property
    def CableType(self):
        return self._cable_type

    @property
    def Wires(self):
        return self._wires

    @property
    def Length(self):
        return self._length


class CableGroupRow(object):
    def __init__(self, cable_type, wires, length):
        self._cable_type = str(cable_type)
        self._wires = int(wires)
        self._length = float(length)

    @property
    def CableType(self):
        return self._cable_type

    @property
    def Wires(self):
        return self._wires

    @property
    def Length(self):
        return self._length


class CircuitGroupRow(object):
    def __init__(self, circuit, wires, length):
        self._circuit = str(circuit)
        self._wires = int(wires)
        self._length = float(length)

    @property
    def Circuit(self):
        return self._circuit

    @property
    def Wires(self):
        return self._wires

    @property
    def Length(self):
        return self._length


# --- Helper Functions ---
def get_base_cable_type(c_type):
    """Strips trailing 'C' or 'c' suffix representing Ground cables to consolidate them."""
    c_type_str = str(c_type).strip()
    if c_type_str.endswith('C') or c_type_str.endswith('c'):
        return c_type_str[:-1].strip()
    return c_type_str


# --- WPF Main Window ---
class CableTakeoffWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        forms.WPFWindow.__init__(self, xaml_file_name)
        self.all_rows = []
        self.display_rows = []
        self._is_initializing = True

        # Check if active selection exists
        selected_ids = uidoc.Selection.GetElementIds()
        has_sel = False
        for eid in selected_ids:
            el = doc.GetElement(eid)
            if el and el.Category:
                cat_val = el.Category.Id.IntegerValue
                if cat_val in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]:
                    has_sel = True
                    break

        if not has_sel:
            # Fall back to Entire Model if selection is empty
            self.rbModel.IsChecked = True
            self.rbSelection.IsEnabled = False

        self._is_initializing = False
        self.update_data()

    def update_data(self):
        if getattr(self, "_is_initializing", True):
            return

        # 1. Gather conduits/fittings in scope
        scope_model = bool(self.rbModel.IsChecked)
        elements = []
        
        if scope_model:
            conduits = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Conduit).WhereElementIsNotElementType().ToElements()
            fittings = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ConduitFitting).WhereElementIsNotElementType().ToElements()
            elements = list(conduits) + list(fittings)
        else:
            selected_ids = uidoc.Selection.GetElementIds()
            for eid in selected_ids:
                el = doc.GetElement(eid)
                if el and el.Category:
                    cat_val = el.Category.Id.IntegerValue
                    if cat_val in [int(DB.BuiltInCategory.OST_Conduit), int(DB.BuiltInCategory.OST_ConduitFitting)]:
                        elements.append(el)

        # Update summary label
        conduit_count = sum(1 for e in elements if e.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_Conduit))
        self.lblStatusSummary.Text = "Scope Conduits: {}".format(conduit_count)

        # 2. Extract and consolidate cable quantities & lengths
        raw_cables = []
        unit_meters = bool(self.rbMeters.IsChecked)

        for el in elements:
            cat_id = el.Category.Id.IntegerValue
            
            # Fetch physical length in internal feet (only for Conduits, fittings are 0.0)
            if cat_id == int(DB.BuiltInCategory.OST_Conduit):
                p_len = el.get_Parameter(DB.BuiltInParameter.CURVE_ELEM_LENGTH)
                length_ft = p_len.AsDouble() if p_len and p_len.HasValue else 0.0
            else:
                length_ft = 0.0

            # Convert to target unit
            elem_length = length_ft * 0.3048 if unit_meters else length_ft

            # Parse GPC-Cables parameter JSON
            param = el.LookupParameter("GPC-Cables")
            if param:
                val = param.AsString() or ""
                if val:
                    try:
                        circuits = json.loads(val)
                        if isinstance(circuits, list):
                            for circuit in circuits:
                                c_name = circuit.get("Circuit", "Unknown").strip()
                                if not c_name:
                                    c_name = "Unknown"
                                    
                                for phase in ["Phase 1", "Phase 2", "Phase 3", "Neutral", "Ground"]:
                                    phase_data = circuit.get(phase)
                                    if isinstance(phase_data, dict):
                                        qty = phase_data.get("Quantity", 0)
                                        if qty > 0:
                                            c_type = phase_data.get("CableType")
                                            if c_type:
                                                c_type_clean = get_base_cable_type(c_type)
                                                raw_cables.append({
                                                    "circuit": c_name,
                                                    "cable_type": c_type_clean,
                                                    "qty": qty,
                                                    "length": elem_length * qty
                                                })
                    except Exception:
                        pass # Ignore malformed values

        # 3. Aggregate based on chosen Grouping
        agg = {}
        group_both = bool(self.rbGroupBoth.IsChecked)
        group_cable = bool(self.rbGroupCable.IsChecked)

        for item in raw_cables:
            if group_both:
                key = (item["circuit"], item["cable_type"])
            elif group_cable:
                key = item["cable_type"]
            else: # circuit only
                key = item["circuit"]

            if key not in agg:
                agg[key] = {"qty": 0, "length": 0.0}
            agg[key]["qty"] += item["qty"]
            agg[key]["length"] += item["length"]

        # 4. Generate visual row model instances for binding
        self.all_rows = []
        for key, data in agg.items():
            if group_both:
                row = BothGroupRow(key[0], key[1], data["qty"], data["length"])
            elif group_cable:
                row = CableGroupRow(key, data["qty"], data["length"])
            else:
                row = CircuitGroupRow(key, data["qty"], data["length"])
            self.all_rows.append(row)

        # 5. Sort rows cleanly
        if group_both:
            self.all_rows.sort(key=lambda r: (r.Circuit, r.CableType))
        elif group_cable:
            self.all_rows.sort(key=lambda r: r.CableType)
        else:
            self.all_rows.sort(key=lambda r: r.Circuit)

        # Re-build Columns dynamically to ensure dynamic Python properties bind properly
        self.dgTakeoff.Columns.Clear()
        unit = "m" if self.rbMeters.IsChecked else "ft"
        len_header = "Total Length ({})".format(unit)

        if group_both:
            c1 = Controls.DataGridTextColumn()
            c1.Header = "Circuit ID"
            c1.Binding = Data.Binding("Circuit")
            c1.Width = Controls.DataGridLength(1, Controls.DataGridLengthUnitType.Star)
            
            c2 = Controls.DataGridTextColumn()
            c2.Header = "Cable Type"
            c2.Binding = Data.Binding("CableType")
            c2.Width = Controls.DataGridLength(1, Controls.DataGridLengthUnitType.Star)
            
            c3 = Controls.DataGridTextColumn()
            c3.Header = len_header
            c3.Binding = Data.Binding("Length")
            c3.Binding.StringFormat = "{0:N2}"
            c3.Width = Controls.DataGridLength(1, Controls.DataGridLengthUnitType.Star)
            
            self.dgTakeoff.Columns.Add(c1)
            self.dgTakeoff.Columns.Add(c2)
            self.dgTakeoff.Columns.Add(c3)
            
        elif group_cable:
            c1 = Controls.DataGridTextColumn()
            c1.Header = "Cable Type"
            c1.Binding = Data.Binding("CableType")
            c1.Width = Controls.DataGridLength(1, Controls.DataGridLengthUnitType.Star)
            
            c2 = Controls.DataGridTextColumn()
            c2.Header = len_header
            c2.Binding = Data.Binding("Length")
            c2.Binding.StringFormat = "{0:N2}"
            c2.Width = Controls.DataGridLength(1, Controls.DataGridLengthUnitType.Star)
            
            self.dgTakeoff.Columns.Add(c1)
            self.dgTakeoff.Columns.Add(c2)
            
        else:
            c1 = Controls.DataGridTextColumn()
            c1.Header = "Circuit ID"
            c1.Binding = Data.Binding("Circuit")
            c1.Width = Controls.DataGridLength(1, Controls.DataGridLengthUnitType.Star)
            
            c2 = Controls.DataGridTextColumn()
            c2.Header = len_header
            c2.Binding = Data.Binding("Length")
            c2.Binding.StringFormat = "{0:N2}"
            c2.Width = Controls.DataGridLength(1, Controls.DataGridLengthUnitType.Star)
            
            self.dgTakeoff.Columns.Add(c1)
            self.dgTakeoff.Columns.Add(c2)

        self.apply_filter()

    def apply_filter(self):
        search_text = self.txtSearch.Text.strip().lower()
        group_both = bool(self.rbGroupBoth.IsChecked)
        group_cable = bool(self.rbGroupCable.IsChecked)

        if search_text:
            filtered = []
            for r in self.all_rows:
                if group_both:
                    matches = (search_text in r.Circuit.lower() or search_text in r.CableType.lower())
                elif group_cable:
                    matches = (search_text in r.CableType.lower())
                else:
                    matches = (search_text in r.Circuit.lower())
                if matches:
                    filtered.append(r)
            self.display_rows = filtered
        else:
            self.display_rows = list(self.all_rows)

        # Re-bind grid data
        self.dgTakeoff.ItemsSource = None
        self.dgTakeoff.ItemsSource = self.display_rows

        # Handle empty list state
        if not self.display_rows:
            self.lblNoData.Visibility = Windows.Visibility.Visible
        else:
            self.lblNoData.Visibility = Windows.Visibility.Collapsed



    # --- UI Event Handlers ---
    def Filter_Changed(self, sender, e):
        self.update_data()

    def Search_Changed(self, sender, e):
        self.apply_filter()

    def Export_Click(self, sender, e):
        if not self.display_rows:
            forms.alert("No takeoff data available to export.", title="Export Report")
            return

        sfd = Win32.SaveFileDialog()
        sfd.Filter = "CSV Files (*.csv)|*.csv|All Files (*.*)|*.*"
        sfd.FileName = "GPC_Cable_Takeoff_Report.csv"
        
        if sfd.ShowDialog() == True:
            filepath = sfd.FileName
            try:
                # Write with UTF-8 BOM encoding for seamless Excel import
                with codecs.open(filepath, 'w', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, lineterminator='\n')
                    
                    unit = "m" if self.rbMeters.IsChecked else "ft"
                    len_header = "Total Length ({})".format(unit)
                    
                    # Define headers and write based on active grouping
                    if self.rbGroupBoth.IsChecked:
                        writer.writerow(["Circuit ID", "Cable Type", len_header])
                        for r in self.display_rows:
                            writer.writerow([r.Circuit, r.CableType, "{:.2f}".format(r.Length)])
                    elif self.rbGroupCable.IsChecked:
                        writer.writerow(["Cable Type", len_header])
                        for r in self.display_rows:
                            writer.writerow([r.CableType, "{:.2f}".format(r.Length)])
                    else:
                        writer.writerow(["Circuit ID", len_header])
                        for r in self.display_rows:
                            writer.writerow([r.Circuit, "{:.2f}".format(r.Length)])

                forms.alert("Takeoff report exported successfully!", title="Export Complete")
            except Exception as ex:
                forms.alert("Failed to export CSV: {}".format(ex), title="Export Error")

    def Copy_Click(self, sender, e):
        if not self.display_rows:
            forms.alert("No takeoff data available to copy.", title="Copy Report")
            return

        try:
            lines = []
            unit = "m" if self.rbMeters.IsChecked else "ft"
            len_header = "Total Length ({})".format(unit)

            # Format data into tab-separated values (TSV) for direct Excel paste support (excluding cable counts)
            if self.rbGroupBoth.IsChecked:
                lines.append("\t".join(["Circuit ID", "Cable Type", len_header]))
                for r in self.display_rows:
                    lines.append("\t".join([r.Circuit, r.CableType, "{:.2f}".format(r.Length)]))
            elif self.rbGroupCable.IsChecked:
                lines.append("\t".join(["Cable Type", len_header]))
                for r in self.display_rows:
                    lines.append("\t".join([r.CableType, "{:.2f}".format(r.Length)]))
            else:
                lines.append("\t".join(["Circuit ID", len_header]))
                for r in self.display_rows:
                    lines.append("\t".join([r.Circuit, "{:.2f}".format(r.Length)]))

            tsv_text = "\n".join(lines)
            Windows.Clipboard.SetText(tsv_text)
            forms.toast("Takeoff copied to clipboard!")
        except Exception as ex:
            forms.alert("Failed to copy to clipboard: {}".format(ex), title="Copy Error")

    def Close_Click(self, sender, e):
        self.Close()


def main():
    xaml_file = os.path.join(os.path.dirname(__file__), "ui.xaml")
    win = CableTakeoffWindow(xaml_file)
    win.ShowDialog()


if __name__ == '__main__':
    main()
