# -*- coding: utf-8 -*-
"""
element_query.py
Element collection for the MepLevels extension.
Scope: Pipes and Pipe Fittings only (Domestic Water, Sanitary, Vent).
"""
import clr
clr.AddReference('RevitAPI')
import Autodesk.Revit.DB as aDB
from System.Collections.Generic import List

from pyrevit import DB

# ---------------------------------------------------------------------------
# Target categories: piping elements only
# ---------------------------------------------------------------------------
PIPING_BICS_NAMES = [
    "OST_PipeCurves",
    "OST_FlexPipeCurves",
    "OST_PipeFitting",
    "OST_PipeAccessory",
]

def _safe_bic(name):
    try:
        return getattr(aDB.BuiltInCategory, name)
    except AttributeError:
        return None

PIPING_BICS = [bic for bic in (_safe_bic(n) for n in PIPING_BICS_NAMES) if bic is not None]

# Integer values for quick category comparison
_PIPE_BIC_INT     = int(aDB.BuiltInCategory.OST_PipeCurves)
_FLEX_BIC_INT     = int(aDB.BuiltInCategory.OST_FlexPipeCurves)
_FITTING_BIC_INT  = int(aDB.BuiltInCategory.OST_PipeFitting)
_ACCESS_BIC_INT   = int(aDB.BuiltInCategory.OST_PipeAccessory)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
def collect_piping_elements(doc):
    """Return all piping elements (pipes + fittings + accessories) project-wide."""
    multi_filter = aDB.ElementMulticategoryFilter(
        List[aDB.BuiltInCategory](PIPING_BICS)
    )
    return list(
        aDB.FilteredElementCollector(doc)
        .WherePasses(multi_filter)
        .WhereElementIsNotElementType()
    )
