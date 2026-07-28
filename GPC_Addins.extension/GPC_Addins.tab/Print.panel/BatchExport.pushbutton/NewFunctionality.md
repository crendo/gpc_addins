# NEW FUNCTIONALITY FOR BATCH EXPORT

In this folder we have a perfectly working script that exports sheets to PDF and DWG. I want to add new functionality to it.

1. Add a check box to compare the newly generated DWG export with the one present in the archive folder before overwriting it. If they are different, we need to move the previous version to the 'superados' subfolder with a suffix with the date of the previous export.
2. Save the DWG file as implemented in the actual script.
3. Use the Revit API or another python script compatible with the current pyRevit environment to compare the DWG files (I found this non working script: 'C:\\Users\\crend\\Documents\\gpc_addins\\GPC_Addins.extension\\GPC_Addins.tab\\Print.panel\\BatchExport.pushbutton\\GPC_DWG_Comparison.py').
4. Modify the script to include the new functionality, and save the DWG file with a name like 'Comparacion_R1_R2_YYYYMMDD_HHMMSS.dwg' where YYYYMMDD_HHMMSS is the date and time of the export.
IMPORTANT: Do not break existing functionality. Keep the script as simple as possible to avoid adding unnecessary complexity. 
