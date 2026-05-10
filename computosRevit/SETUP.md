# Setup Guide: Cómputos Revit Extension

Follow these steps to install and configure the `Cómputos Revit` pyRevit extension.

## 1. Prerequisites
- **Autodesk Revit**: Version 2022 or higher (tested on 2023).
- **pyRevit**: Ensure pyRevit is installed and working correctly. [Download pyRevit](https://github.com/eirannejad/pyRevit/releases).

## 2. Installation
To add the `Cómputos Revit` extension to your Revit Ribbon:

1.  Open **Revit**.
2.  Go to the **pyRevit** tab.
3.  Click on the **Settings** button (usually in the pyRevit panel).
4.  Navigate to the **Extensions** tab within the settings window.
5.  Click on **Add Folder** under "External Extensions".
6.  Select the folder: `c:\Users\crend\Documents\computosRevit\computosRevit.extension` (or the location where you cloned this repository).
7.  Click **Save Settings and Reload**.

The **Cómputos Revit** tab should now appear in your Revit Ribbon.

## 3. Configuration
The extension relies on a Shared Parameters file and a JSON DataStore.

### Shared Parameters
### Shared Parameters
The extension uses a central shared parameter file located at `shared_parameters/GPC-SharedParameters.txt` (at the root of the gpc_addins workspace). 
- When you first run **Setup Parameters**, it will automatically point Revit to this file.
- This central file is shared across all extensions in the repository.

### JSON DataStore
- The DataStore (`_data.json`) is automatically created in your **Documents/Cómputos Revit** folder the first time you run a sync.
- You can manually select or create new database files using the "Sync & Manage" dashboard.

## 4. First Run
1.  **Inject Parameters**: Click the "Setup Parameters" button. This will bind the GPC parameters (`Cantidad`, `CostoItem`, `GrupoCosto`, `PrecioUnitario`, `UnidadMedicion`) to all applicable categories in your project.
2.  **Verify Binding**: Select any element (e.g., a Wall) and check its Properties (Instance) or Type Properties under the "Data" group for the new GPC values.
3.  **Sync & Manage**: Click "Sync & Manage" to open the management dashboard. Use "Sync with Model" to populate the database with initial quantities.

## Troubleshooting
- **Missing Tab**: Ensure the path added in pyRevit settings points *directly* to the `.extension` folder.
- **Import Errors**: If the script fails with "ImportError", ensure the `lib` folder exists inside the `.extension` directory.
- **JSON Errors**: If the data file becomes corrupted, the extension will attempt to self-repair by creating a new empty database.

---
*Note: Folder names in paths (computosRevit.extension) are kept in lowercase for system compatibility.*
