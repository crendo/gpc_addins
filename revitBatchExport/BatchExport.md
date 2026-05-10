# Description

pyRevit script that allows the user to select a set of drawings and export then to PDF and Autocad, populating the name inferred from the Revit sheets parameters. The exported files will have exactly the same name with the extension pdf or/and dwg.
Script assumes that sheets are named under this convention XX-YYYYYYYYYYYYYYYY, where XX is the first n characters of the Sheet Number and YY is the the Sheet Name

## Technical Constraints

- **Platform**: pyRevit Extension (Python/IronPython).
- **API**: Revit 2023+ (uses `SpecTypeId`).
- **Performance**: High-speed filtering using `FilteredElementCollector` and bulk operations for category binding.
- **Safety**: All modifications are wrapped in `DB.Transaction` blocks.

## Tasks

- When user push a button, a windows will open with some fields to be populated. This window will have an Ok and a Cancel button and the following elements:
  
  - There is an integer field  'n  to indicate the number of characters that define the grouping for the sheet numbers. Example 'AP-01 Drawing plan', is Sheet Number 'AP-01'. Sheet Name is 'Drawing Plan'. In this example if we specify n=2, the group name for the sheets is 'AP'. This field is called 'sheetGroupName'.
  - From the sheets lists, calculate the list of 'sheetGroupName' available in the document and present it as a dropdown list.
  - Pick from the file systema a folder where to place the exported sheets.
  - Present a selectable list of sheets grouped by the previous dropdown. Show only the sheets with the selected sheetGroupName in the dropdown list.
  - Present a checbox group for selecting wants to export PDF or DWG or both.
  - Present a Preffix string field to preffix this to the final name wich will have the following format:
    <preffixField>-<sheetNumber><space><Sheet Name>_<SheetRevision>
    If the Sheet does not have a parameter set, it will use 'a'

## Useful Tools & Docs

- [Revit API Docs (apidocs.co)](https://apidocs.co/)
- [pyRevit Documentation](https://www.notion.so/pyRevit-For-Teams-0ed932e6040c495393c52e4f08e5c8e4)
- [RevitLookup](https://github.com/jeremytammik/RevitLookup)