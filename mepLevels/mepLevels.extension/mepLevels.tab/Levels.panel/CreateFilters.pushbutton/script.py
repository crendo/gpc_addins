# -*- coding: utf-8 -*-
"""
CreateFilters/script.py  –  Phase 2: System View Filters per Level
------------------------------------------------------------------
Reads levels_association.json to obtain the list of canonical (right-list) levels,
then creates or updates 3 view filters per level:
  - "Ver Agua Domestica en [LevelName]"    → Domestic Hot Water + Domestic Cold Water
  - "Ver Sanitario en [LevelName]"         → Sanitary
  - "Ver Vent en [LevelName]"              → Vent

The filters are created in the project (not bound to any view automatically,
unless a plan view is active – in which case they are also applied to it).
"""
import sys
import os

# ---------------------------------------------------------------------------
# Library path
# ---------------------------------------------------------------------------
_ext_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_lib_path  = os.path.join(_ext_root, "lib")
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

from pyrevit import revit, DB, forms, script

from meplevels.level_utils   import (
    load_level_association,
    get_association_file_path,
    get_target_levels,
)
from meplevels.filter_utils  import create_system_filters_for_levels

doc    = revit.doc
output = script.get_output()

output.print_md("## GPC – Create System Filters")

# ---------------------------------------------------------------------------
# Guard: model must be saved
# ---------------------------------------------------------------------------
if not doc.PathName:
    forms.alert(
        "The Revit model must be saved before running this script.\n"
        "Please save and try again.",
        title="GPC – Create Filters",
        exitscript=True
    )

# ---------------------------------------------------------------------------
# Guard: association file must exist
# ---------------------------------------------------------------------------
assoc_file = get_association_file_path(doc)
if not assoc_file or not os.path.isfile(assoc_file):
    forms.alert(
        "No level association file found.\n\n"
        "Please run 'Set Level Association' first to define the level mapping.",
        title="GPC – Create Filters",
        exitscript=True
    )

target_levels = get_target_levels(doc)
if not target_levels:
    forms.alert(
        "The level association file contains no target levels.\n\n"
        "Please run 'Set Level Association' to define the level mapping.",
        title="GPC – Create Filters",
        exitscript=True
    )

output.print_md("**Association file:** `{}`".format(assoc_file))
output.print_md("**Target levels (right-list):** {}".format(len(target_levels)))
for name in target_levels:
    output.print_md("- `{}`".format(name))

# ---------------------------------------------------------------------------
# Optional: apply to active view if it is a floor/ceiling plan
# ---------------------------------------------------------------------------
active_view = doc.ActiveView
apply_to_view = None
if active_view and active_view.ViewType in (DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan):
    apply_to_view = active_view
    output.print_md(
        "\n:information_source: Active view **`{}`** is a floor/ceiling plan – filters will also be applied to it.".format(
            active_view.Name
        )
    )
else:
    output.print_md(
        "\n:information_source: No active floor plan – filters will be created in the project only."
    )

# ---------------------------------------------------------------------------
# Create filters
# ---------------------------------------------------------------------------
output.print_md("---")
output.print_md("**Creating filters...**")

try:
    results = create_system_filters_for_levels(doc, target_levels, view=apply_to_view)

    for filter_name, pfe in results:
        output.print_md(":white_check_mark: `{}`".format(filter_name))

    output.print_md(
        "\n---\n:white_check_mark: **{} filter(s) created/updated.**".format(len(results))
    )
    forms.alert(
        "{} view filters created/updated successfully!\n\n"
        "Filters follow the format:\n"
        "  Ver [System] en [LevelName]".format(len(results)),
        title="GPC – Create Filters"
    )

except Exception as ex:
    output.print_md(":x: Error creating filters: `{}`".format(str(ex)))
    forms.alert(
        "An error occurred while creating filters:\n\n{}".format(str(ex)),
        title="GPC – Create Filters"
    )
