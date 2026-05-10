# Project Specifications: solidsToGM

## 1. Overview

**solidsToGM** is a pyRevit extension designed to convert imported DWG file with solids into a Generic Model family with the same geometry.

---

## 2.Tasks

- Read DWG file with solids
- Convert solids to Generic Model family
- Place the family in the model

---

## 3. Technical Constraints

- **Platform**: pyRevit Extension (Python/IronPython).
- **API**: Revit 2023+ (uses `SpecTypeId`).
- **Performance**: High-speed filtering using `FilteredElementCollector` and bulk operations for category binding.
- **Safety**: All modifications are wrapped in `DB.Transaction` blocks.
