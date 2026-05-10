# Agent Instructions: Revit pyRevit Extension Development (Python)

This document provides context and guidelines for AI agents working on the **solidsToGM*** project.

## 1. Project Overview

- **Project Name:** solidsToGM
- **Description:** A pyRevit extension designed to convert imported DWG file with solids into a Generic Model family with the same geometry.
- **Language:** Python (IronPython 2.7 via pyRevit)
- **Primary Platform:** Autodesk Revit 2023 to 2026
- **Framework:** pyRevit Extension

## 2. Directory Structure

All pyRevit extension code follows the standard bundle hierarchy:

- `solidsToGM.extension/`: Root extension folder.
  - `solidsToGM.tab/`: Custom Revit Tab.
    - `convertSolids.panel/`: Custom Panel.
      - `[CommandName].pushbutton/`: Button folder containing `script.py` and `icon.png`.

## 3. Coding Guidelines

- **Imports:** Always use `from pyrevit import revit, DB, forms` for a consistent API interface.
- **Transactions:** Use `with revit.Transaction("Description"):` for all document modifications.
- **UI:** Prefer `pyrevit.forms` for user interaction (alerts, progress bars, selectors).
- **Categories:** When binding parameters, check `category.AllowsBoundParameters` to avoid API exceptions.

## 4. Revit API Specifics

- **ForgeTypeIds:** For Revit 2022+, use `SpecTypeId` (e.g., `DB.SpecTypeId.Number`) instead of deprecated `ParameterType`.
- **Units:** Be mindful of internal units. Use `UnitUtils` to convert from displayed units if needed.
- **Performance:** For bulk category operations, pass the entire `CategorySet` to the binding map rather than iterating individual bindings if possible.

## Useful Tools & Docs

- [Revit API Docs (apidocs.co)](https://apidocs.co/)
- [pyRevit Documentation](https://www.notion.so/pyRevit-For-Teams-0ed932e6040c495393c52e4f08e5c8e4)
- [RevitLookup](https://github.com/jeremytammik/RevitLookup)

---

*Note: This file is for AI agents. Do not delete without consulting the team.*
