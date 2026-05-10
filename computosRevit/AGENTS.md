# Agent Instructions: Revit pyRevit Extension Development (Python)

This document provides context and guidelines for AI agents working on the **Computos Revit** project.

## 1. Project Overview
- **Project Name:** Computos Revit
- **Description:** A pyRevit extension designed to automate quantity takeoff (computos) by injecting and managing shared parameters across all Revit categories.
- **Language:** Python (IronPython 2.7 via pyRevit)
- **Primary Platform:** Autodesk Revit 2023
- **Framework:** pyRevit Extension

## 2. Directory Structure
All pyRevit extension code follows the standard bundle hierarchy:
- `computosRevit.extension/`: Root extension folder.
  - `computosRevit.tab/`: Custom Revit Tab.
    - `Quantities.panel/`: Custom Panel.
      - `[CommandName].pushbutton/`: Button folder containing `script.py` and `icon.png`.
  - `lib/`: Shared libraries.
    - `database.py`: DataStore API.
    - `sync.py`: Core synchronization logic, unit detection, and background listeners.
- `reference_docs/`: Contains official shared parameter files (e.g., `GPC-SharedParameters.txt`) and unit mappings.

## 3. Coding Guidelines
- **Imports:** Always use `from pyrevit import revit, DB, forms` for a consistent API interface.
- **Shared Logic:** Never duplicate synchronization logic. Use `import sync` and call `sync.sync_elements()` for any model-to-database operations.
- **Transactions:** Use `with revit.Transaction("Description"):` for all document modifications.
- **Active Sync:** The project uses background listeners (`Idling` and `DocumentChanged`) registered in `lib/sync.py`. Ensure any new background features check the `GPC_AUTOSYNC_ENABLED` environment variable.
- **Paths:** Use dynamic path resolution (via `os.path`) to find `reference_docs` relative to the script location.
- **UI:** Prefer `pyrevit.forms` for user interaction (alerts, progress bars, selectors).
- **Categories:** When binding parameters, check `category.AllowsBoundParameters` to avoid API exceptions.

## 4. Revit API Specifics
- **ForgeTypeIds:** For Revit 2022+, use `SpecTypeId` (e.g., `DB.SpecTypeId.Number`) instead of deprecated `ParameterType`.
- **Units:** Be mindful of internal units. Use `UnitUtils` to convert from displayed units if needed.
- **Performance:** For bulk category operations, pass the entire `CategorySet` to the binding map rather than iterating individual bindings if possible.

## 5. Shared Parameter Management
- **Source:** Refer to `reference_docs/GPC-SharedParameters.txt`.
- **Injection:** Ensure required parameters (`GPC-Cantidad`, `GPC-GrupoCosto`, `GPC-PrecioUnitario`, etc.) exist in the shared parameter file before attempting project binding. If the file doesn't exist, create it with the contents of `GPC-SharedParameters.txt` in Group `GPC`.

## Useful Tools & Docs
- [Revit API Docs (apidocs.co)](https://apidocs.co/)
- [pyRevit Documentation](https://www.notion.so/pyRevit-For-Teams-0ed932e6040c495393c52e4f08e5c8e4)
- [RevitLookup](https://github.com/jeremytammik/RevitLookup)

---
*Note: This file is for AI agents. Do not delete without consulting the team.*
