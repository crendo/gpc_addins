# -*- coding: utf-8 -*-
"""Batch Export Sheets to PDF and DWG"""

import os
import re
import clr
import json
import shutil

from pyrevit import revit, DB, forms, script

doc = revit.doc

# Load .NET classes required for Collections
clr.AddReference("System")
clr.AddReference("PresentationCore")
from System.Collections.Generic import List
from System.Collections.ObjectModel import ObservableCollection
from System import Object
import System.Windows as FrameworkWindows


def get_settings_path():
    """Generate path for settings file next to Revit document"""
    if not doc.PathName:
        return None
    return doc.PathName + ".batch_export.json"

def save_settings(settings):
    """Save settings to JSON file"""
    path = get_settings_path()
    if path:
        try:
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print("Failed to save settings: {}".format(e))

def load_settings():
    """Load settings from JSON file"""
    path = get_settings_path()
    if path and os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            # Silently fail if file is corrupt or unreadable
            pass
    return {}

class SheetWrapper(object):
    """Wrapper class for sheets to bind to WPF UI"""
    def __init__(self, sheet):
        self.sheet = sheet
        self.sheet_number = sheet.SheetNumber
        self.sheet_name = sheet.Name
        self._is_selected = True

    @property
    def Name(self):
        return "{} - {}".format(self.sheet_number, self.sheet_name)

    @property
    def IsSelected(self):
        return self._is_selected

    @IsSelected.setter
    def IsSelected(self, value):
        self._is_selected = value


class BatchExportWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        self.all_sheets = self.get_all_sheets()
        self.selected_folder = ""
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        # Load and apply persisted settings
        self.apply_settings()
        self.update_groups()

    def apply_settings(self):
        """Load settings from JSON and populate UI fields"""
        settings = load_settings()
        if not settings:
            return
            
        if "group_length" in settings:
            self.GroupLengthInput.Text = str(settings["group_length"])
            
        if "selected_folder" in settings:
            self.selected_folder = settings["selected_folder"]
            self.FolderPathText.Text = self.selected_folder
            # Try to set FontStyle to Normal if it was Italic by default
            try:
                self.FolderPathText.FontStyle = FrameworkWindows.FontStyles.Normal
            except:
                pass
            
        if "prefix" in settings:
            self.PrefixInput.Text = settings["prefix"]
            
        if "export_pdf" in settings:
            self.ExportPdfCheckbox.IsChecked = settings["export_pdf"]
            
        if "export_dwg" in settings:
            self.ExportDwgCheckbox.IsChecked = settings["export_dwg"]
            
        # Store selected group to re-select it after update_groups populates the items
        self._saved_group = settings.get("selected_group")

        if "archive_enabled" in settings:
            self.ArchiveCheckbox.IsChecked = settings["archive_enabled"]
            
        if "archive_folder" in settings:
            self.ArchiveFolderInput.Text = settings["archive_folder"]
        elif self.selected_folder:
            self.ArchiveFolderInput.Text = os.path.join(self.selected_folder, "superados")

        if "print_all" in settings:
            self.PrintAllCheckbox.IsChecked = settings["print_all"]
            self.OnPrintAllChanged(None, None)

    def get_all_sheets(self):
        """Fetch all non-placeholder sheets from the active document."""
        sheets = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Sheets).ToElements()
        # Filter IsPlaceholder on the raw ViewSheet element (s), not on the wrapper
        return [SheetWrapper(s) for s in sheets if not s.IsPlaceholder]

    def update_groups(self):
        """Update the dropdown based on the prefix length 'n'."""
        try:
            if hasattr(self, 'GroupLengthInput'):
                n = int(self.GroupLengthInput.Text)
            else:
                n = 2
            if n < 0: n = 0
        except ValueError:
            n = 2 # default if parsing fails
            
        groups = set()
        for wrapper in self.all_sheets:
            num = wrapper.sheet_number
            if len(num) >= n:
                groups.add(num[:n])
            else:
                groups.add(num)

        # Update ComboBox ItemsSource
        sorted_groups = sorted(list(groups))
        self.GroupDropdown.ItemsSource = sorted_groups
        
        # Try to re-select the saved group
        if hasattr(self, '_saved_group') and self._saved_group in sorted_groups:
            self.GroupDropdown.SelectedItem = self._saved_group
        elif self.GroupDropdown.Items.Count > 0:
            self.GroupDropdown.SelectedIndex = 0

    def OnGroupLengthChanged(self, sender, args):
        self.update_groups()

    def OnGroupSelectionChanged(self, sender, args):
        if not hasattr(self, 'GroupDropdown') or not hasattr(self, 'GroupLengthInput'):
            return
            
        selected_group = self.GroupDropdown.SelectedItem
        if selected_group is None:
            if hasattr(self, 'SheetListBox'):
                self.SheetListBox.ItemsSource = None
            return

        try:
            n = int(self.GroupLengthInput.Text)
        except ValueError:
            n = 2

        # Use ObservableCollection for WPF Data Binding
        obs_collection = ObservableCollection[Object]()
        
        for wrapper in self.all_sheets:
            num = wrapper.sheet_number
            if len(num) >= n and num[:n] == selected_group:
                obs_collection.Add(wrapper)
            elif len(num) < n and num == selected_group:
                obs_collection.Add(wrapper)
        
        self.SheetListBox.ItemsSource = obs_collection
        
        # Reset Select All checkbox state without triggering events if possible
        if hasattr(self, 'SelectAllCheckbox'):
            self.SelectAllCheckbox.IsChecked = True

    def OnSelectAllChecked(self, sender, args):
        if not hasattr(self, 'SheetListBox') or self.SheetListBox.ItemsSource is None:
            return
        items = self.SheetListBox.ItemsSource
        for item in items:
            item.IsSelected = True
        # Force UI update
        self.SheetListBox.ItemsSource = None
        self.SheetListBox.ItemsSource = items

    def OnSelectAllUnchecked(self, sender, args):
        if not hasattr(self, 'SheetListBox') or self.SheetListBox.ItemsSource is None:
            return
        items = self.SheetListBox.ItemsSource
        for item in items:
            item.IsSelected = False
        # Force UI update
        self.SheetListBox.ItemsSource = None
        self.SheetListBox.ItemsSource = items

    def OnPrintAllChanged(self, sender, args):
        if not hasattr(self, 'PrintAllCheckbox'):
            return
        is_print_all = bool(self.PrintAllCheckbox.IsChecked)
        
        if hasattr(self, 'GroupDropdown'):
            self.GroupDropdown.IsEnabled = not is_print_all
        if hasattr(self, 'GroupLengthInput'):
            self.GroupLengthInput.IsEnabled = not is_print_all
        if hasattr(self, 'SheetListBox'):
            self.SheetListBox.IsEnabled = not is_print_all
        if hasattr(self, 'SelectAllCheckbox'):
            self.SelectAllCheckbox.IsEnabled = not is_print_all

    def OnBrowseFolderClick(self, sender, args):
        folder = forms.pick_folder(title="Select Output Folder")
        if folder:
            self.selected_folder = folder
            self.FolderPathText.Text = folder
            
            # Using dynamic access to System.Windows.FontStyles is sometimes tricky in ironpython
            # If standard, text gets italic in xaml, we remove it.
            # A safe way is to just set it to Normal if we want to, or just skip it.
            # self.FolderPathText.FontStyle = System.Windows.FontStyles.Normal
            
            # Initialize archive folder
            self.ArchiveFolderInput.Text = os.path.join(folder, "superados")

    def OnExportClick(self, sender, args):
        if not self.selected_folder:
            forms.alert("Please select an output folder.")
            return
            
        export_pdf = self.ExportPdfCheckbox.IsChecked
        export_dwg = self.ExportDwgCheckbox.IsChecked
        
        if not export_pdf and not export_dwg:
            forms.alert("Please select at least one export format (PDF/DWG).")
            return

        is_print_all = bool(self.PrintAllCheckbox.IsChecked) if hasattr(self, 'PrintAllCheckbox') else False
        
        if is_print_all:
            sheets_to_export = self.all_sheets
        else:
            items = self.SheetListBox.ItemsSource
            sheets_to_export = [item for item in items if item.IsSelected] if items is not None else []
            
        if not sheets_to_export:
            forms.alert("Please select at least one sheet from the list.")
            return

        # Store values to execute outside UI
        self.prefix = self.PrefixInput.Text
        self.export_sheets = sheets_to_export
        self.export_pdf = export_pdf
        self.export_dwg = export_dwg

        # Save settings for next time
        settings = {
            "group_length": self.GroupLengthInput.Text,
            "selected_group": self.GroupDropdown.SelectedItem,
            "selected_folder": self.selected_folder,
            "prefix": self.prefix,
            "export_pdf": self.export_pdf,
            "export_dwg": self.export_dwg,
            "archive_enabled": self.ArchiveCheckbox.IsChecked,
            "archive_folder": self.ArchiveFolderInput.Text,
            "print_all": is_print_all
        }
        
        self.archive_enabled = self.ArchiveCheckbox.IsChecked
        self.archive_folder = self.ArchiveFolderInput.Text
        save_settings(settings)
        
        self.Close()

    def OnCancelClick(self, sender, args):
        self.export_sheets = None
        self.Close()


def get_sheet_revision(sheet):
    """Retrieve Current Revision, fallback to 'a'"""
    # Attempt BuiltInParameter first
    rev_param = sheet.get_Parameter(DB.BuiltInParameter.SHEET_CURRENT_REVISION)
    if rev_param and rev_param.AsString():
        return rev_param.AsString()
        
    # Attempt Lookup if BuiltIn fails
    rev = sheet.LookupParameter("Current Revision")
    if rev and rev.AsString():
        return rev.AsString()
        
    return "a"

def sanitize_filename(name):
    """Remove illegal OS characters from filename"""
    invalid_chars = r'[<>:"/\\|?*]'
    return re.sub(invalid_chars, '_', name)

def get_sort_key(rev):
    """Returns a key for sorting revisions."""
    if rev.isdigit():
        return (1, int(rev))
    return (0, rev.upper())

def run_archive_logic(target_dir, archive_dir):
    """Move older revisions of files to the archive directory."""
    if not os.path.exists(target_dir):
        return
        
    if not os.path.exists(archive_dir):
        try:
            os.makedirs(archive_dir)
        except:
            return

    # Regex: (BaseName)_(Revision).(Extension)
    pattern = re.compile(r"^(.*)_([a-zA-Z0-9]+)\.([^.]+)$")
    file_groups = {}

    files_in_dir = os.listdir(target_dir)
    for filename in files_in_dir:
        path = os.path.join(target_dir, filename)
        if os.path.isdir(path):
            continue

        match = pattern.match(filename)
        if match:
            base, rev, ext = match.groups()
            key = (base.lower(), ext.lower())
            
            if key not in file_groups:
                file_groups[key] = []
            
            file_groups[key].append({
                'name': filename,
                'rev': rev
            })

    moved_count = 0
    for key, revisions in file_groups.items():
        if len(revisions) <= 1:
            continue

        # Sort by revision naturally
        revisions.sort(key=lambda x: get_sort_key(x['rev']))
        
        # The last one in the sorted list is considered the latest
        latest = revisions[-1]
        older = revisions[:-1]
        
        for old_file in older:
            src = os.path.join(target_dir, old_file['name'])
            dst = os.path.join(archive_dir, old_file['name'])
            
            try:
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
                moved_count += 1
            except Exception as e:
                print("Failed to archive {}: {}".format(old_file['name'], e))
    
    return moved_count

def main():
    # Show warning if no sheets
    sheets = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Sheets).ToElements()
    if not sheets:
        forms.alert("No sheets found in the current project.", exitscript=True)

    # Initialize Window
    xaml_file = script.get_bundle_file('ui.xaml')
    window = BatchExportWindow(xaml_file)
    window.ShowDialog()

    # Check if user cancelled
    if getattr(window, 'export_sheets', None) is None:
        return

    folder = window.selected_folder
    prefix = window.prefix
    pdf_opt = window.export_pdf
    dwg_opt = window.export_dwg
    
    # Initialize base DWG Options from active settings if available
    base_dwg_options = None
    if dwg_opt:
        active_settings = DB.ExportDWGSettings.GetActivePredefinedSettings(doc)
        if active_settings:
            base_dwg_options = active_settings.GetDWGExportOptions()
        else:
            base_dwg_options = DB.DWGExportOptions()
        
        # User requirement: prevent exporting views/links as external references
        base_dwg_options.MergedViews = True
        base_dwg_options.TargetUnit = DB.ExportUnit.Meter
    
    exported_count = 0

    with forms.ProgressBar(title="Exporting Sheets...") as pb:
        total = len(window.export_sheets)
        
        # NOTE: doc.Export() is NOT allowed inside a DB.Transaction or TransactionGroup.
        # Revit will raise an InvalidOperationException if you try.
        # DWG export also requires no active transaction; it manages its own journal internally.
        for i, wrapper in enumerate(window.export_sheets):
            sheet = wrapper.sheet
            
            # Format: <prefixField>-<sheetNumber> <Sheet Name>_<SheetRevision>
            rev = get_sheet_revision(sheet)
            
            if prefix:
                file_name = "{}-{} {}_{}".format(prefix, wrapper.sheet_number, wrapper.sheet_name, rev)
            else:
                file_name = "{} {}_{}".format(wrapper.sheet_number, wrapper.sheet_name, rev)
            
            file_name = sanitize_filename(file_name)
            
            # DWG EXPORT
            if dwg_opt:
                view_ids = List[DB.ElementId]()
                view_ids.Add(sheet.Id)
                try:
                    # doc.Export() must be called outside any transaction
                    success = doc.Export(folder, file_name, view_ids, base_dwg_options)
                    if not success:
                        print("Warning: Revit returned False when exporting DWG for sheet {}".format(wrapper.sheet_number))
                    
                    # Revit may append the sheet name to DWGs. Rename to enforce exact name.
                    expected_dwg = os.path.join(folder, file_name + ".dwg")
                    if not os.path.exists(expected_dwg):
                        for f in os.listdir(folder):
                            if f.startswith(file_name) and f.endswith(".dwg"):
                                os.rename(os.path.join(folder, f), expected_dwg)
                                break
                except Exception as e:
                    print("Failed to export DWG for {}: {}".format(wrapper.sheet_number, e))

            # PDF EXPORT
            if pdf_opt:
                if int(revit.HOST_APP.version) >= 2022:
                    pdf_options = DB.PDFExportOptions()
                    # Combine = True: Because we export one sheet at a time, setting Combine = True
                    # forces Revit to respect our custom FileName property instead of ignoring it.
                    pdf_options.Combine = True
                    pdf_options.FileName = file_name
                    
                    view_ids = List[DB.ElementId]()
                    view_ids.Add(sheet.Id)
                    try:
                        # doc.Export() must be called outside any transaction
                        doc.Export(folder, view_ids, pdf_options)
                    except Exception as e:
                        print("Failed to export PDF for {}: {}".format(wrapper.sheet_number, e))
                else:
                    print("PDF Export natively supported only in Revit 2022+")

            exported_count += 1
            pb.update_progress(i + 1, total)

    forms.alert("Successfully exported {} sheets!".format(exported_count), title="Export Complete")

    # ARCHIVE OLD REVISIONS
    if window.archive_enabled and window.archive_folder:
        moved = run_archive_logic(folder, window.archive_folder)
        if moved:
            print("Archived {} old revision files to {}".format(moved, window.archive_folder))


if __name__ == '__main__':
    main()
