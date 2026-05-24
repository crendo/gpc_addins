"""Remove all GPC Shared Parameters from the project."""

__title__ = 'Remove\nGPC Params'
__author__ = 'Computos Revit Team'

from pyrevit import revit, DB, forms

def remove_gpc_parameters():
    doc = revit.doc
    
    # 1. Ask for Confirmation
    confirm = forms.alert(
        "This will REMOVE ALL shared parameters starting with 'GPC-' from the project.\n"
        "This includes data in Project Parameters and their bindings.\n\n"
        "Are you sure you want to proceed?",
        title="Warning: Destructive Action",
        yes=True, no=True
    )
    
    if not confirm:
        return

    # 2. Start Transaction
    with revit.Transaction("Remove GPC Parameters"):
        # We'll use FilteredElementCollector to find all ParameterElements
        # This covers Project Parameters (both shared and local)
        param_elements = DB.FilteredElementCollector(doc).OfClass(DB.ParameterElement).ToElements()
        
        count_removed = 0
        names_removed = []
        
        for pe in param_elements:
            # We want to catch anything starting with GPC-
            if pe.Name.startswith("GPC-"):
                try:
                    name = pe.Name
                    doc.Delete(pe.Id)
                    count_removed += 1
                    names_removed.append(name)
                except Exception as e:
                    print("Could not delete parameter {}: {}".format(pe.Name, str(e)))

        if count_removed > 0:
            forms.alert(
                "Successfully removed {} parameters:\n\n- {}".format(count_removed, "\n- ".join(names_removed)),
                title="Result"
            )
        else:
            forms.alert("No parameters starting with 'GPC-' were found.", title="Result")

if __name__ == "__main__":
    remove_gpc_parameters()
