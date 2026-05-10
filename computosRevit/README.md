# Cómputos Revit: Quantity Takeoff Automation

A professional **pyRevit extension** designed to automate quantity takeoff (computos) and project costing directly within Autodesk Revit 2023+. 

This tool synchronizes model geometry with a high-performance **JSON DataStore**, allowing for real-time cost estimation and metadata management across all model categories.

## 🚀 Key Features

- **Dynamic Parameter Injection**: Automatically binds custom GPC shared parameters (`Cantidad`, `GrupoCosto`, `PrecioUnitario`, `UnidadMedicion`, `CostoItem`) to all applicable Revit model categories.
- **Real-time Active Sync**: Monitors your model changes in the background and automatically recalculates quantities and costs, reflecting them immediately in your Revit Schedules.
- **Management Dashboard**: A centralized WPF interface to review, filter, isolate, and color-highlight all takeoff items. Supports instance-level and type-level price editing.
- **Smart Unit Detection**: Intelligent mapping of units (`m`, `m2`, `m3`, `kg`, `und`) based on element geometry and predefined family/category associations.
- **Flexible JSON DataStore**: Uses a lightweight, portable JSON database per project, making it easy to share takeoff data or export it to downstream estimating software.

## 🛠 Workflow

1.  **Inject Parameters**: Run the "Setup Parameters" tool to prepare your Revit model.
2.  **Configure Units**: The tool uses `CategoryUnits.json` to assign initial units automatically.
3.  **Sync & Manage**: Open the dashboard to start the model synchronization.
4.  **Costing**: Assign unit prices directly in the grid or using the `GPC-PrecioUnitario` parameter.
5.  **Live Updates**: Enable "Auto-Sync" to keep your takeoff 100% accurate as you modify the model.

## 📂 Project Structure

- `computosRevit.extension/`: Core pyRevit extension files.
  - `lib/`: Shared Python libraries for database (`database.py`) and sync logic (`sync.py`).
- `reference_docs/`: Configuration files, unit mappings, and shared parameter definitions.

## 📜 Prerequisites

- **Autodesk Revit 2023** (Tested on Revit 2023 with ForgeTypes API).
- **pyRevit** environment.

---
*Developed for efficient Revit metadata management and quantity extraction workflows.*
