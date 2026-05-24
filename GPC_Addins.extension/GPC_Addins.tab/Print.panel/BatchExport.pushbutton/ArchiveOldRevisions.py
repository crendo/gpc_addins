import os
import shutil
import re

# ==========================================
# CONFIGURATION
# ==========================================
TARGET_DIR = r"z:\Proyectos\00-PROYECTOS 2024\2024 - TORRE BNC - SOCADO\07- INGENIERIAS SOCADO BNC\COORDINACION"
ARCHIVE_DIR = os.path.join(TARGET_DIR, "superados")
DRY_RUN = False # Set to True to only see what would happen

def get_sort_key(rev):
    """
    Returns a key for sorting revisions.
    Handles numeric (1, 2, 10) and alphabetic (A, B, C) revisions.
    """
    if rev.isdigit():
        return (1, int(rev))
    return (0, rev.upper())

def archive_old_revisions():
    print(">>> Starting Revision Archiver")
    print(">>> Source: {}".format(TARGET_DIR))
    print(">>> Archive: {}".format(ARCHIVE_DIR))
    print(">>> Dry Run: {}\n".format(DRY_RUN))

    if not os.path.exists(ARCHIVE_DIR):
        if not DRY_RUN:
            os.makedirs(ARCHIVE_DIR)
        print("Created archive directory: {}".format(ARCHIVE_DIR))

    # Regex: (BaseName)_(Revision).(Extension)
    # This captures everything before the last underscore, then the revision, then the extension.
    pattern = re.compile(r"^(.*)_([a-zA-Z0-9]+)\.([^.]+)$")

    file_groups = {}

    files_in_dir = os.listdir(TARGET_DIR)
    for filename in files_in_dir:
        path = os.path.join(TARGET_DIR, filename)
        
        # Skip directories and the script itself
        if os.path.isdir(path):
            continue
        if filename.lower() == os.path.basename(__file__).lower():
            continue

        match = pattern.match(filename)
        if match:
            base, rev, ext = match.groups()
            # Key is (BaseName, Extension) to handle different file types separately
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
        
        print("Group [{} . {}]:".format(key[0], key[1]))
        print("  [KEEP] {}".format(latest['name']))
        
        for old_file in older:
            src = os.path.join(TARGET_DIR, old_file['name'])
            dst = os.path.join(ARCHIVE_DIR, old_file['name'])
            
            print("  [MOVE] {} -> superados/".format(old_file['name']))
            
            if not DRY_RUN:
                try:
                    if os.path.exists(dst):
                        os.remove(dst)
                    shutil.move(src, dst)
                    moved_count += 1
                except Exception as e:
                    print("  [ERROR] Failed to move {}: {}".format(old_file['name'], e))
            else:
                moved_count += 1

    print("\n>>> Process Complete.")
    if DRY_RUN:
        print(">>> [DRY RUN] Would have moved {} files.".format(moved_count))
    else:
        print(">>> Successfully moved {} files to superados.".format(moved_count))

if __name__ == "__main__":
    archive_old_revisions()
