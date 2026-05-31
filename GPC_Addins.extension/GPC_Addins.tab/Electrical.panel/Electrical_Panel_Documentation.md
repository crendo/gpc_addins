# Electrical Panel Documentation

This document provides an overview of the PyRevit scripts available within the `Electrical.panel` of the GPC Addins.

## Parameter Setup

* **Setup Parameters** (`01_SetupParameters.pushbutton`)
  * **Description**: Setup Shared Parameters for Conduits and Conduit Fittings. It injects required parameters (e.g., `GPC-Cables`, `GPC-Cables-Tag`) and loads centralized families.

## Cable & Circuit Management

* **Manage Cables** (`06_ManageCables.pushbutton`)
  * **Description**: Manage circuits, wire counts, and cable sizes inside selected conduits.
* **Manage Database** (`07_ManageCableDatabase.pushbutton`)
  * **Description**: Maintain and update the cable sizes database with safety verification of model usage.
* **Circuit Management** (`10_CircuitManagement.pushbutton`)
  * **Description**: Manage, search, add, edit, or delete Project Circuit definitions.
* **Sync Cable Tags** (`08_SyncCableTags.pushbutton`)
  * **Description**: Synchronizes and generates cable tag text for circuits.

## Takeoff & Sizing Verification

* **Cable Takeoff** (`05_CableTakeoff.pushbutton`)
  * **Description**: Cable Takeoff tool: aggregate, sum, and export cable lengths in selected or all conduits.
* **Verify Conduit Size** (`02_VerifyConduitSize.pushbutton`)
  * **Description**: Verify the cable fill capacity of a single selected conduit or pipe element against NEC limits.
* **Conduit Capacity Color** (`09_ConduitCapacityColor.pushbutton`)
  * **Description**: Analyze and color-code all conduits in the active view based on fill capacity.

## Highlighting & Pathing

* **Identify Circuit** (`11_IdentifyCircuit.pushbutton`)
  * **Description**: Identify and highlight all conduits and conduit fittings belonging to a selected circuit in the active view.
* **Identify Path** (`PathButtons.stack/03_IdentifyPath.pushbutton`)
  * **Description**: Identify and highlight the physical conduit path between two selected points.
* **Clear Path** (`PathButtons.stack/04_ClearPath.pushbutton`)
  * **Description**: Clear all conduit path graphic overrides in the active view.
