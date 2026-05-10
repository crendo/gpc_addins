from pyrevit import revit, DB

doc = revit.doc
categories = doc.Settings.Categories

search_terms = ["Duct", "Fabrication"]

for category in categories:
    if any(term in category.Name for term in search_terms):
        print("Name: {}, AllowsBoundParameters: {}, CategoryType: {}".format(
            category.Name, 
            category.AllowsBoundParameters, 
            category.CategoryType
        ))

# Specific check for BuiltInCategory
bics = [
    DB.BuiltInCategory.OST_DuctCurves,
    DB.BuiltInCategory.OST_FabricationDuctwork
]

for bic in bics:
    try:
        cat = categories.get_Item(bic)
        if cat:
            print("Found {}: {}, AllowsBoundParameters: {}".format(bic, cat.Name, cat.AllowsBoundParameters))
        else:
            print("{} NOT FOUND".format(bic))
    except Exception as e:
        print("{} Error: {}".format(bic, e))
