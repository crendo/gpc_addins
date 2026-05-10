"""Initialize Auto-Sync listeners on Revit startup based on persisted configuration."""
from pyrevit import script, revit
import sys
import os

# Add lib folder
EXTENSION_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.join(EXTENSION_DIR, "lib")
if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

import sync

def init_autosync():
    # 1. Recover persisted state
    cfg = script.get_config()
    is_enabled = cfg.get_option('autosync_persistence', False)
    
    # 2. Set environment variable for the current session
    script.set_envvar('GPC_AUTOSYNC_ENABLED', is_enabled)
    
    # 3. Start background listeners if enabled
    if is_enabled:
        try:
            sync.ensure_listeners()
        except:
            pass

if __name__ == "__main__":
    init_autosync()
