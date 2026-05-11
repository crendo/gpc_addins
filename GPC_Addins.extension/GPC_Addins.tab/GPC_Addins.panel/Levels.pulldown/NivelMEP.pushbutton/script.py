# -*- coding: utf-8 -*-
"""
NivelMEP/script.py  –  Phase 1: Level Normalization
-----------------------------------------------------
Reads the levels_association.json file to determine which levels are in scope,
then normalizes all pipes and pipe fittings project-wide by:
  1. Computing each element's absolute elevation.
  2. Reassigning it to the correct level bracket (per AGENTS.md §6 rules).
  3. Recalculating the offset to maintain physical position.
  4. Writing the normalized level name into the GPC_NivelMEP parameter.

Must be run with an active Revit document that has been saved.
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
from System.Collections.Generic import List

from meplevels.shared_params import (
    ensure_parameter_bound,
    load_families,
)
from meplevels.element_query  import collect_piping_elements
from meplevels.level_utils    import (
    get_sorted_levels,
    load_level_association,
    get_association_file_path,
    is_level_writable,
    needs_normalization,
    apply_normalization,
)

doc    = revit.doc
output = script.get_output()

output.print_md("## GPC – Nivel MEP")

# ---------------------------------------------------------------------------
# Guard: model must be saved
# ---------------------------------------------------------------------------
if not doc.PathName:
    forms.alert(
        "The Revit model must be saved before running this script.\n"
        "Please save and try again.",
        title="GPC – Nivel MEP",
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
        title="GPC – Nivel MEP",
        exitscript=True
    )

association = load_level_association(doc)
if not association:
    forms.alert(
        "The level association file is empty.\n\n"
        "Please run 'Set Level Association' to define the level mapping.",
        title="GPC – Nivel MEP",
        exitscript=True
    )

output.print_md("**Association file:** `{}`".format(assoc_file))
output.print_md("**Mapped levels:** {}".format(len(association)))

# ---------------------------------------------------------------------------
# Step 0 – Ensure shared parameter and families are present
# ---------------------------------------------------------------------------
was_bound = ensure_parameter_bound(doc)
if was_bound:
    output.print_md(":white_check_mark: `GPC_NivelMEP` parameter bound to piping categories.")
else:
    output.print_md(":information_source: `GPC_NivelMEP` already bound – skipping.")

loaded_count = load_families(doc)
if loaded_count > 0:
    output.print_md(":white_check_mark: **{}** families loaded from library.".format(loaded_count))
else:
    output.print_md(":information_source: No new families to load.")

# ---------------------------------------------------------------------------
# Collect all piping elements project-wide
# ---------------------------------------------------------------------------
output.print_md("---")
output.print_md("**Collecting piping elements...**")

raw_elements  = collect_piping_elements(doc)
all_elements  = [e for e in raw_elements if is_level_writable(e)]
skipped_count = len(raw_elements) - len(all_elements)

output.print_md(
    "**Elements found:** {} total, {} writable  *(skipped {} read-only/hosted)*".format(
        len(raw_elements), len(all_elements), skipped_count
    )
)

if not all_elements:
    forms.alert(
        "No writable piping elements found in the project.",
        title="GPC – Nivel MEP"
    )
    sys.exit(0)

# ---------------------------------------------------------------------------
# Build sorted level list for normalization
# ---------------------------------------------------------------------------
sorted_levels = get_sorted_levels(doc)
if not sorted_levels:
    forms.alert("No levels found in the project.", title="GPC – Nivel MEP")
    sys.exit(0)

output.print_md("**Project levels (sorted):**")
for lvl in sorted_levels:
    output.print_md("- `{}` at {:.3f} ft".format(lvl.Name, lvl.Elevation))

# ---------------------------------------------------------------------------
# Detect elements that need normalization
# ---------------------------------------------------------------------------
output.print_md("---")
output.print_md("**Detecting elements that need level normalization...**")

to_normalize = [e for e in all_elements if needs_normalization(e, sorted_levels)]

output.print_md(
    "**Elements to normalize:** {} / {}".format(len(to_normalize), len(all_elements))
)

if not to_normalize:
    output.print_md(":white_check_mark: All elements are already on the correct level.")
    forms.alert(
        "All piping elements are already correctly assigned to their levels.\n"
        "GPC_NivelMEP will be refreshed for all elements.",
        title="GPC – Nivel MEP"
    )

# ---------------------------------------------------------------------------
# Confirm with user before modifying
# ---------------------------------------------------------------------------
if to_normalize:
    proceed = forms.alert(
        "{} piping elements need level reassignment.\n\n"
        "Do you want to normalize them now?\n"
        "(This operation cannot be undone automatically.)".format(len(to_normalize)),
        title="GPC – Normalize Levels",
        yes=True,
        no=True
    )
    if not proceed:
        output.print_md(":information_source: Normalization cancelled by user.")
        sys.exit(0)

# ---------------------------------------------------------------------------
# Apply normalization
# ---------------------------------------------------------------------------
normalized_count = 0
error_count      = 0

with revit.Transaction("GPC - Normalize MEP Levels"):
    for elem in all_elements:
        try:
            changed = apply_normalization(elem, sorted_levels)
            if changed:
                normalized_count += 1
        except Exception as e:
            error_count += 1
            output.print_md(":x: Error on element {}: `{}`".format(elem.Id, str(e)))

output.print_md("---")
output.print_md(
    ":white_check_mark: **Normalization complete.**\n"
    "- Elements updated: **{}**\n"
    "- Errors: **{}**".format(normalized_count, error_count)
)

forms.alert(
    "Level normalization complete!\n\n"
    "Elements updated: {}\n"
    "Errors: {}".format(normalized_count, error_count),
    title="GPC – Nivel MEP"
)
