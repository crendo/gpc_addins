# Project Specifications: Cómputos Revit

## 1. Overview
**Cómputos Revit** is a pyRevit extension designed to automate quantity takeoff (computos) by injecting and managing shared parameters across all Revit categories. It ensures consistent metadata across model elements and provides tools for real-time synchronization with an external JSON database.

---

## 2. Shared Parameter Management

### 2.1 Schema Definition
The following shared parameters are injected into all model categories:
- **GPC-Cantidad** (Number, Instance): Stores the calculated quantity.
- **GPC-GrupoCosto** (Text, Type): Categorizes the element into a cost group.
- **GPC-PrecioUnitario** (Currency, Instance): Stores the unit price (defaults to Type `Cost` if available).
- **GPC-CostoItem** (Currency, Instance): Calculated as `GPC-Cantidad * GPC-PrecioUnitario`.
- **GPC-UnidadMedicion** (Text, Type): Stores the unit of measurement (e.g., m, m2, m3, kg, und).

### 2.2 Injection Behavior
- **Source**: `shared_parameters/GPC-SharedParameters.txt` (located at the root of the gpc_addins workspace).
- **Scope**: All model categories where `AllowsBoundParameters` is true, excluding non-geometric categories (Views, Sheets, etc.).
- **Initialization**: 
    - `GPC-GrupoCosto` maps from `OmniClass Title` or defaults to "No asignado".
    - `GPC-UnidadMedicion` is determined via `CategoryUnits.json` (Family -> Category -> fallback).

---

## 3. Quantity Calculation & Unit Mapping

### 3.1 Unit Detection Logic
The system determines the measurement unit using the following priority:
1.  **Family Override**: Matches in `CategoryUnits.json` under `Families`.
2.  **Category Default**: Matches in `CategoryUnits.json` under `Categories`.
3.  **Smart Detection**: Scans element parameters for Length, Area, or Volume properties.
4.  **Fallback**: Defaults to `und` (Quantity = 1.0).

### 3.2 Quantity Formulas
- **m (Linear)**: Uses `CURVE_ELEM_LENGTH` or similar length parameters.
- **m2 (Area)**: Uses `HOST_AREA_COMPUTED` or face-based geometry analysis.
- **m3 (Volume)**: Uses `HOST_VOLUME_COMPUTED`.
- **kg (Weight)**: Uses `STRUCTURAL_WEIGHT` or calculates `Volume * 7850` (Steel) / `2400` (Concrete).
- **und (Unit)**: Fixed quantity of `1.0` per instance.

---

## 4. Data Persistence (JSON DataStore)

### 4.1 Storage Strategy
Data is stored in a local JSON file per project, located in `%USERPROFILE%/Documents/Computos Revit/`.
- **Format**:
    - `partidas`: Dictionary keyed by Revit Element ID.
    - `GrupoCosto`: List of identifiers and names for categorization.
- **Safety**: Atomic writes using `.tmp` files to prevent data corruption during synchronization.

### 4.2 Manual Operations
- **Save JSON**: Manually triggers a full write of current model data to the database.
- **Open JSON**: Allows users to import external costing data and apply it back to Revit parameters.

---

## 5. User Interface & Toolsets

### 5.1 Quantities Panel (General Management)
- **Setup Parameters**: Injects the GPC schema and loads auxiliary takeoff families.
- **Sync All**: Scans the entire model and updates JSON data and GPC parameters.
- **Multi-Category Schedule**: Automates the creation of a formatted Revit schedule with filters to only show items with a `GPC-Cantidad > 0`.
- **Auto-Sync**: A toggle button that enables/disables real-time background listeners.
- **Remove GPC Params**: Utility to clean the project of all GPC-related shared parameters.

### 5.2 Takeoff Panel (Modeling Utilities)
- **Area/Perímetro**: Tool to place `GPC-CM-Area` markers for custom area takeoff.
- **Lineal Measure**: Tool to place `GPC-CM-Lineal` markers for custom length takeoff.
- **Room Polygons**: Automatically generates `DirectShape` (Generic Model) solids matching Room boundaries, used for finishing or floor takeoff.
- **Marker Visibility**: Pair of buttons (**Mostrar/Ocultar Marcadores**) to toggle the visibility checkbox (`LineasVisible`) of all placeholder markers.

---

## 6. Active Sync (Real-time Functionality)
The Active Sync system monitors the model in the background:
- **Listeners**: Registered on `DocumentChanged` and `Idling` events.
- **Trigger**: Controlled by the `GPC_AUTOSYNC_ENABLED` environment variable.
- **Behavior**: When an element is added or modified, the system automatically recalculates its `GPC-Cantidad` and `GPC-CostoItem` and updates the JSON store without user intervention.

---

## 7. Technical Constraints
- **Platform**: pyRevit Extension (Python/IronPython).
- **API**: Revit 2023+ (uses `SpecTypeId`).
- **Performance**: High-speed filtering using `FilteredElementCollector` and bulk operations for category binding.
- **Safety**: All modifications are wrapped in `DB.Transaction` blocks.
