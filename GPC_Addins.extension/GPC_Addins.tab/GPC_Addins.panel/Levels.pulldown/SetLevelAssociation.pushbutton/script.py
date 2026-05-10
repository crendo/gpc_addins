# -*- coding: utf-8 -*-
"""
SetLevelAssociation/script.py  –  Step 0: Level Association Setup
-----------------------------------------------------------------
Presents a two-column UI:
  Left  – All levels in the project (including linked models)
  Right – Canonical / "target" levels the user wants to normalize to

The user maps each left-side level to a right-side level.
The mapping is persisted as  levels_association.json  next to the Revit model.
"""
import sys
import os
import json

# ---------------------------------------------------------------------------
# Library path
# ---------------------------------------------------------------------------
_ext_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_lib_path  = os.path.join(_ext_root, "lib")
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

import clr
clr.AddReference('RevitAPI')
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')

import Autodesk.Revit.DB as aDB
import System
from System.Windows import (
    Window, WindowStartupLocation,
    HorizontalAlignment, VerticalAlignment, Thickness,
    GridLength, GridUnitType
)
from System.Windows.Controls import (
    Grid, ColumnDefinition, RowDefinition, StackPanel,
    Label, ComboBox, ComboBoxItem, Button, ScrollViewer,
    Separator, ScrollBarVisibility, Orientation
)
from System.Windows.Media import SolidColorBrush, Color

from pyrevit import revit, forms, script

doc    = revit.doc
output = script.get_output()

# ---------------------------------------------------------------------------
# Guard: model must be saved
# ---------------------------------------------------------------------------
model_path = doc.PathName
if not model_path:
    forms.alert(
        "The Revit model must be saved before running this script.\n"
        "Please save the model and try again.",
        title="GPC – Level Association",
        exitscript=True
    )

assoc_file = os.path.join(os.path.dirname(model_path), "levels_association.json")


# ---------------------------------------------------------------------------
# Collect levels from host document
# ---------------------------------------------------------------------------
def get_all_host_levels(document):
    """Return all levels from the host model, sorted by elevation."""
    levels = list(
        aDB.FilteredElementCollector(document)
        .OfClass(aDB.Level)
        .WhereElementIsNotElementType()
    )
    return sorted(levels, key=lambda l: l.Elevation)


def get_linked_levels(document):
    """Return levels from all loaded Revit links."""
    linked = []
    link_instances = list(
        aDB.FilteredElementCollector(document)
        .OfClass(aDB.RevitLinkInstance)
        .WhereElementIsNotElementType()
    )
    for link_inst in link_instances:
        try:
            link_doc = link_inst.GetLinkDocument()
            if link_doc is None:
                continue
            link_levels = list(
                aDB.FilteredElementCollector(link_doc)
                .OfClass(aDB.Level)
                .WhereElementIsNotElementType()
            )
            for lvl in link_levels:
                # Tag name with origin for disambiguation
                linked.append("{} [{}]".format(lvl.Name, link_doc.Title))
        except Exception:
            continue
    return linked


# Build the two level lists
host_levels   = get_all_host_levels(doc)
host_names    = [l.Name for l in host_levels]
linked_names  = get_linked_levels(doc)
all_left      = host_names + linked_names   # left list (all levels incl. linked)
right_options = host_names                  # right list (target levels = host only)


# ---------------------------------------------------------------------------
# Load existing association if present
# ---------------------------------------------------------------------------
existing_map = {}
if os.path.isfile(assoc_file):
    try:
        with open(assoc_file, "r") as f:
            existing_map = json.load(f)
    except Exception:
        existing_map = {}


# ---------------------------------------------------------------------------
# Build WPF window
# ---------------------------------------------------------------------------
class LevelAssociationWindow(Window):
    def __init__(self):
        self.Title = "GPC – Asociar Niveles / Level Association"
        self.Width  = 680
        self.Height = 520
        self.WindowStartupLocation = WindowStartupLocation.CenterScreen
        self.Background = SolidColorBrush(Color.FromRgb(30, 30, 30))

        self.mapping = dict(existing_map)  # { source_name: target_name }
        self._combos = {}   # { source_name: ComboBox }

        # Root grid
        root = Grid()
        root.Margin = Thickness(12)
        root.RowDefinitions.Add(RowDefinition())            # rows list
        root.RowDefinitions.Add(RowDefinition(Height=GridLength(50, GridUnitType.Pixel)))  # buttons

        # --- header row labels ---
        header = Grid()
        header.ColumnDefinitions.Add(ColumnDefinition())
        header.ColumnDefinitions.Add(ColumnDefinition())

        lbl_left = self._make_label("Nivel en modelo  (izquierda)", bold=True)
        lbl_right = self._make_label("Nivel canónico  (derecha)", bold=True)
        Grid.SetColumn(lbl_left,  0)
        Grid.SetColumn(lbl_right, 1)
        header.Children.Add(lbl_left)
        header.Children.Add(lbl_right)
        Grid.SetRow(header, 0)

        # wrap scrollable content
        scroll = ScrollViewer()
        scroll.VerticalScrollBarVisibility = ScrollBarVisibility.Auto
        scroll.Margin = Thickness(0, 28, 0, 0)

        content = StackPanel()
        content.Children.Add(header)

        # Add a separator line
        sep = Separator()
        sep.Margin = Thickness(0, 4, 0, 4)
        content.Children.Add(sep)

        # One row per source level
        for src_name in all_left:
            row = Grid()
            row.ColumnDefinitions.Add(ColumnDefinition())
            row.ColumnDefinitions.Add(ColumnDefinition())
            row.Margin = Thickness(0, 2, 0, 2)

            # Left label
            lbl = self._make_label(src_name)
            Grid.SetColumn(lbl, 0)
            row.Children.Add(lbl)

            # Right combo – keep default light background so text stays readable
            combo = ComboBox()
            combo.Margin = Thickness(8, 0, 0, 0)
            combo.Foreground = SolidColorBrush(Color.FromRgb(10, 10, 10))
            for opt in right_options:
                item = ComboBoxItem()
                item.Content    = opt
                item.Foreground = SolidColorBrush(Color.FromRgb(10, 10, 10))
                combo.Items.Add(item)

            # Pre-select
            preselect = self.mapping.get(src_name, src_name)
            for i, opt in enumerate(right_options):
                if opt == preselect:
                    combo.SelectedIndex = i
                    break
            if combo.SelectedIndex < 0 and right_options:
                combo.SelectedIndex = 0

            Grid.SetColumn(combo, 1)
            row.Children.Add(combo)

            content.Children.Add(row)
            self._combos[src_name] = combo

        scroll.Content = content
        Grid.SetRow(scroll, 0)

        # --- Buttons ---
        btn_panel = StackPanel()
        btn_panel.HorizontalAlignment = HorizontalAlignment.Right
        btn_panel.Orientation = Orientation.Horizontal
        btn_panel.Margin = Thickness(0, 8, 0, 0)

        btn_cancel = self._make_button("Cancelar", self._on_cancel)
        btn_ok     = self._make_button("Guardar / Save", self._on_ok)
        btn_panel.Children.Add(btn_cancel)
        btn_panel.Children.Add(btn_ok)

        Grid.SetRow(btn_panel, 1)

        root.Children.Add(scroll)
        root.Children.Add(btn_panel)
        self.Content = root

    # ---- helpers ----
    def _make_label(self, text, bold=False):
        lbl = Label()
        lbl.Content    = text
        lbl.Foreground = SolidColorBrush(Color.FromRgb(220, 220, 220))
        lbl.Padding    = Thickness(2)
        if bold:
            lbl.FontWeight = System.Windows.FontWeights.Bold
        return lbl

    def _make_button(self, text, handler):
        btn = Button()
        btn.Content    = text
        btn.Margin     = Thickness(6, 0, 0, 0)
        btn.Padding    = Thickness(12, 4, 12, 4)
        btn.Foreground = SolidColorBrush(Color.FromRgb(220, 220, 220))
        btn.Background  = SolidColorBrush(Color.FromRgb(60, 100, 180))
        btn.Click      += handler
        return btn

    def _on_ok(self, sender, args):
        self.mapping = {}
        for src_name, combo in self._combos.items():
            if combo.SelectedItem is not None:
                self.mapping[src_name] = combo.SelectedItem.Content
        self.DialogResult = True
        self.Close()

    def _on_cancel(self, sender, args):
        self.DialogResult = False
        self.Close()


# (System already imported at top)

win = LevelAssociationWindow()
result = win.ShowDialog()

if result:
    mapping = win.mapping
    # Save to JSON
    try:
        with open(assoc_file, "w") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        output.print_md(
            ":white_check_mark: **Level association saved** to:\n`{}`".format(assoc_file)
        )
        output.print_md("**Mapping ({} entries):**".format(len(mapping)))
        for src, tgt in sorted(mapping.items()):
            output.print_md("- `{}` → `{}`".format(src, tgt))
        forms.alert(
            "Level association saved successfully!\n{} levels mapped.".format(len(mapping)),
            title="GPC – Level Association"
        )
    except Exception as e:
        forms.alert(
            "Error saving association file:\n{}".format(str(e)),
            title="GPC – Level Association"
        )
else:
    output.print_md(":information_source: Level association cancelled – no changes made.")
