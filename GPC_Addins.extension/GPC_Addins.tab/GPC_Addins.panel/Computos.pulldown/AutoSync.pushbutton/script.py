"""Toggle background synchronization for GPC parameters."""

__title__ = 'Auto-Sync'
__author__ = 'Computos Revit Team'

import os
import sys
from pyrevit import revit, forms, script

# 1. Setup Library Paths
# script.py (0) -> AutoSync.pushbutton (1) -> Quantities.panel (2) -> Quantities.tab (3) -> computosRevit.extension (4)
# Library paths are handled automatically by pyRevit

import sync

def toggle_autosync():
    # 2. Identify Current State (Get from environment or config)
    current_state = script.get_envvar('GPC_AUTOSYNC_ENABLED')
    new_state = not current_state
    
    # 3. Apply New State
    script.set_envvar('GPC_AUTOSYNC_ENABLED', new_state)
    
    # 4. Handle Persistence
    cfg = script.get_config()
    cfg.set_option('autosync_persistence', new_state)
    script.save_config()
    
    # 5. Handle Listeners
    if new_state:
        sync.ensure_listeners()
        forms.toast("Auto-Sync is now ENABLED", title="Sync Status")
    else:
        # Note: Listeners check GPC_AUTOSYNC_ENABLED internally, 
        # but we could also explicitly call sync.remove_listeners() if desired.
        forms.toast("Auto-Sync is now DISABLED", title="Sync Status")

    # 6. Visual Indication (Session Title Update)
    try:
        button = script.get_button()
        if button:
            state_text = 'ON' if new_state else 'OFF'
            button.set_title('Auto-Sync: ' + state_text)
    except Exception:
        pass

if __name__ == "__main__":
    toggle_autosync()

