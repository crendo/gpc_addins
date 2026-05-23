# -*- coding: utf-8 -*-
"""Pin the GPC Tab to prevent Revit switching to contextual tab display during selection."""

__title__ = 'Pin Tab'
__author__ = 'Electrical Team'

import clr  # type: ignore
clr.AddReference("AdWindows")
clr.AddReference("WindowsBase")
clr.AddReference("PresentationFramework")
import Autodesk.Windows as adWin  # type: ignore
import System  # type: ignore
from System.Windows.Threading import DispatcherPriority  # type: ignore
from pyrevit import script, forms  # type: ignore

def switch_back():
    try:
        for tab in adWin.ComponentManager.Ribbon.Tabs:
            title = (getattr(tab, "Title", "") or "").replace("_", "-").replace(" ", "-").lower()
            name = (getattr(tab, "Name", "") or "").replace("_", "-").replace(" ", "-").lower()
            tab_id = (getattr(tab, "Id", "") or "").replace("_", "-").replace(" ", "-").lower()
            if "gpc-addins" in title or "gpc-addins" in name or "gpc-addins" in tab_id:
                tab.IsActive = True
                break
    except Exception:
        pass

def ribbon_ActiveTabChanged(sender, e):
    try:
        # Read from .NET process environment variable for complete thread & engine safety in Revit 2025 (.NET 8)
        if System.Environment.GetEnvironmentVariable("GPC_PIN_TAB_ACTIVE") == "True":
            active_tab = adWin.ComponentManager.Ribbon.ActiveTab
            if active_tab:
                title = getattr(active_tab, "Title", "") or getattr(active_tab, "Name", "") or ""
                tab_id = getattr(active_tab, "Id", "") or ""
                # Contextual tabs in Revit always start with "Modify"
                if title.startswith("Modify") or tab_id.startswith("Modify") or "contextual" in tab_id.lower():
                    # Defer the active tab switch to allow Revit's built-in contextual switch to complete first
                    adWin.ComponentManager.Ribbon.Dispatcher.BeginInvoke(
                        System.Action(switch_back),
                        DispatcherPriority.Background
                    )
    except Exception:
        pass

def __selfinit__(script_cmp, ui_button_cmp, __rvt__):
    # Apply initial icon state from process environment
    state = System.Environment.GetEnvironmentVariable("GPC_PIN_TAB_ACTIVE") == "True"
    icon_path = script_cmp.get_bundle_file('on.png' if state else 'off.png')
    if icon_path:
        ui_button_cmp.set_icon(icon_path)
    
    # Safely register active tab changed event handler
    def try_register_handler():
        try:
            ribbon = adWin.ComponentManager.Ribbon
            if ribbon:
                try:
                    ribbon.ActiveTabChanged -= ribbon_ActiveTabChanged
                except Exception:
                    pass
                ribbon.ActiveTabChanged += ribbon_ActiveTabChanged
                return True
        except Exception:
            pass
        return False

    # Attempt to register immediately
    if not try_register_handler():
        # If it failed (e.g. Ribbon not ready yet), defer it to Revit's Idling event
        def register_on_idling(sender, e):
            if try_register_handler():
                try:
                    sender.Idling -= register_on_idling
                except Exception:
                    pass
        try:
            __rvt__.Idling += register_on_idling
        except Exception:
            pass
    
    return True

if __name__ == '__main__':
    # Toggle state
    current_state = System.Environment.GetEnvironmentVariable("GPC_PIN_TAB_ACTIVE") == "True"
    new_state = not current_state
    
    # Save the toggled state to process environment
    val_str = "True" if new_state else "False"
    System.Environment.SetEnvironmentVariable("GPC_PIN_TAB_ACTIVE", val_str)
    
    # Update active button icon
    new_icon = script.get_bundle_file('on.png' if new_state else 'off.png')
    
    button = script.get_button()
    if button and new_icon:
        button.set_icon(new_icon)
        
    status_str = "ON" if new_state else "OFF"
    
    # Print status in pyRevit low-profile toast message
    forms.toast("GPC Tab Pinning is now: {}".format(status_str), title="Pin Tab")
