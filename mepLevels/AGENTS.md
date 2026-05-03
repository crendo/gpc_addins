# Agent Instructions: Revit pyRevit Extension Development (Python)

This document provides context and guidelines for AI agents working on the **Mep Levels** project.

## 1. Project Overview
- **Project Name:** Mep Levels
- **Description:** A pyRevit extension designed to assign levels to mep elements and create view filters for each level.
- **Language:** Python (IronPython 2.7 via pyRevit)
- **Primary Platform:** Autodesk Revit 2023+. Script should take in mind the differences between Revit 2023 and 2025 regarding python and revit api.
- **Framework:** pyRevit Extension

## 2. Directory Structure
All pyRevit extension code follows the standard bundle hierarchy:
- `mepLevels.extension/`: Root extension folder.
  - `mepLevels.tab/`: Custom Revit Tab.
    - `Levels.panel/`: Custom Panel.
      - `[CommandName].pushbutton/`: Button folder containing `script.py` and `icon.png`.

## 3. Coding Guidelines
- **Imports:** Always use `from pyrevit import revit, DB, forms` for a consistent API interface.
- **Shared Logic:** Never duplicate logic.
- **Transactions:** Use `with revit.Transaction("Description"):` for all document modifications.
- **Paths:** Use dynamic path resolution (via `os.path`) to find `reference_docs` relative to the script location.
- **UI:** Prefer `pyrevit.forms` for user interaction (alerts, progress bars, selectors).
- **Categories:** When binding parameters, check `category.AllowsBoundParameters` to avoid API exceptions.

## 4. Revit API Specifics
- **ForgeTypeIds:** For Revit 2023+, use `SpecTypeId` (e.g., `DB.SpecTypeId.Number`) instead of deprecated `ParameterType`.
- **Units:** Be mindful of internal units. Use `UnitUtils` to convert from displayed units if needed.
- **Performance:** For bulk category operations, pass the entire `CategorySet` to the binding map rather than iterating individual bindings if possible.

## 5. Shared Parameter Management
- For all the Mep families, we will use a shared parameter file to store the parameter called 'GPC_NivelMEP' which will be a text parameter.
- Depending of the revit family, GPC_NivelMEP will be an instance parameter that will take the value of 'Level' or 'Reference Level', depending on the Revit family type. If the family has a 'Level' parameter, it will be used, otherwise it will use 'Reference Level
- The parameters will be stored in the `GPC` group.

## 6. Preparation of Revit model for the pyRevit extension
### Level List Selection.
The script should present a window with two lists of levels. Each level of the left list will be associated to a level of the right list. The user should be able to select a level from the right list for each level of the left list. This selection will be persisted in a json file in the same folder of the Revit model and will be used to normalize the levels of the Revit model. The file will be named levels_association.json. The left list will contain all the levels in the project, including the linked models.

### Pipe and Pipe Fittings level normalization
The pipes and pipe fittings should be normalized using the levels selected in the previous step. If the pipe or pipe fitting is on a level different than the View Level selected, it means that the instance was not modeled with the correct level. An lemente is considered bad modelled if the offset value is bigger than the level height.
Example: With the levels:
Level 1 at +0.00
Level 2 at +2.70
Level 3 at +5.40

If a pipe or pipe fitting is on Level 1 with an offset of -0.60, it means that the instance was modeled with the correct level because there is no lower level than Level 1.
If a pipe or pipe fitting is on Level 1 with an offset of +2.10, it means that the instance was modeled with the correct level, because it is on Level 1 with value 0.00 and the offset is +2.10, which is still in level 1 , because Level 2 is at +2.70. We don't normalize to Level 2 -0.60, because we don't use negative offset if the original offset is positive. We use negative offsets only if the original offset is negative.
If a pipe or pipe fitting is on Level 1 with an offset of +3.00, it means that the instance was not modeled with the correct level, because it is on Level 1 with value 0.00 and the offset is +3.00, which is bigger than the value of Level 2, 2.70. The pipe should be moved to Level 2 with an offset of +0.30 (3.00 - 2.70 = 0.30).
If a pipe or pipe fitting is on Level 3 with an offset of -6.00, it means that the instance was not modeled with the correct level, because it is on Level 3 with level value of 5.40 minus 6.00 = -0.60 that falls below level 1. The pipe should be moved to level 1 with an offset of -0.60.
If a pipe or fitting is on a Level 1 with an offset value of 10 , it means the pipe is at 10ft from the floor level of Level 1. Then the pipe should be corrected to Level 3 with an offset of 10.00 - 5.40 = +4.60.
If a pipe or fitting is on a Level 2 with an offset value of -8 , it means the pipe is at -8ft from the floor level of Level 2. Then the pipe should be corrected to Level 1 with an offset of 2.70 - 8.00 = -5.30.
If a pipe or fitting is on a Level 2 with an offset value of -11 , it means the pipe is at -11ft from the floor level of Level 2. Then the pipe should be corrected to Level 1 with an offset of 2.70 - 11.00 = -8.30.
If a pipe or fitting is on a Level 1 with an offset of 2.70 , it means the pipe should be on level 2 with an offset of 0.00.
If a pipe or fitting is on a Level 2 with an offset of -2.70 , it means the pipe should be on level 1 with an offset of 0.00.
This logic should be used to correct the levels for pipes and reference label and offset for pipe fittings for all the project.

### Level NiveMEP button
The button will place the value of the pipe or pipe fitting's level or reference level, which are already normalized as described above into the GPC_NivelMEP parameter.
### Phase 2. Filter creation.
For all the levels in the right list, the script will create view filters for:
- Domestic Water System
- Sanitary System
- Vent System
The filter name will have the following format: Ver [System] en [LevelName]

## Useful Tools & Docs
- [Revit API Docs (apidocs.co)](https://apidocs.co/)
- [pyRevit Documentation](https://www.notion.so/pyRevit-For-Teams-0ed932e6040c495393c52e4f08e5c8e4)
- [RevitLookup](https://github.com/jeremytammik/RevitLookup)

---
*Note: This file is for AI agents. Do not delete without consulting the team.*
