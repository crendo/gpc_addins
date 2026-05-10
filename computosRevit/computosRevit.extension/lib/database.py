# -*- coding: utf-8 -*-
import os
import json
import codecs
from pyrevit import forms

def get_db_path(doc):
    """Returns the path to the JSON storage file. Prefers Documents folder."""
    docs_folder = os.path.join(os.path.expanduser("~"), "Documents", "Computos Revit")
    if not os.path.exists(docs_folder):
        try:
            os.makedirs(docs_folder)
        except:
            pass 
            
    if not doc.IsModelInCloud:
        model_name = os.path.basename(doc.PathName).replace(".rvt", "_data.json")
        if model_name:
            return os.path.join(docs_folder, model_name)
    
    return os.path.join(docs_folder, "data_fallback.json")

def init_db(db_path):
    """Ensures the JSON file exists and has the correct structure."""
    def get_default_data():
        return {
            "partidas": {}, # Using dict for O(1) lookups during sync
            "GrupoCosto": [
                {"id": 1, "nombre": u"Estructura"},
                {"id": 2, "nombre": u"Alba\u00f1iler\u00eda"},
                {"id": 3, "nombre": u"Instalaciones"},
                {"id": 4, "nombre": u"Terminaciones"}
            ]
        }

    if not os.path.exists(db_path) or os.path.getsize(db_path) < 2:
        try:
            with codecs.open(db_path, 'w', encoding='utf-8') as f:
                json.dump(get_default_data(), f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            forms.alert("Error creating data file: {}".format(e))
            return False
    
    # Check for validity
    try:
        with codecs.open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data.get("partidas"), (dict, list)) or "GrupoCosto" not in data:
                raise ValueError("Invalid structure")
    except:
        # Self-repair: overwrite with default
        try:
            with codecs.open(db_path, 'w', encoding='utf-8') as f:
                json.dump(get_default_data(), f, indent=4, ensure_ascii=False)
        except:
             pass
    return True

class DataStore:
    """Clean JSON Data API for Revit Quantity Takeoff."""
    def __init__(self, path):
        self.path = path
        self.data = self._load()

    def _load(self):
        try:
            if not os.path.exists(self.path):
                return self._get_default_data()
            with codecs.open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Migration: convert list to dict if needed
            if isinstance(data.get("partidas"), list):
                new_p = {}
                for p in data["partidas"]:
                    if isinstance(p, dict) and "idRevit" in p:
                        new_p[str(p["idRevit"])] = p
                data["partidas"] = new_p
            return data
        except:
            return self._get_default_data()

    def _get_default_data(self):
        return {
            "partidas": {},
            "GrupoCosto": [
                {"id": 1, "nombre": u"Estructura"},
                {"id": 2, "nombre": u"Alba\u00f1iler\u00eda"},
                {"id": 3, "nombre": u"Instalaciones"},
                {"id": 4, "nombre": u"Terminaciones"}
            ]
        }

    def get_groups(self):
        """Returns {id: name} mapping for display."""
        return {g['id']: g['nombre'] for g in self.data["GrupoCosto"]}

    def get_groups_lookup(self):
        """Returns {name: id} mapping for sync lookups."""
        return {g['nombre']: g['id'] for g in self.data["GrupoCosto"]}

    def get_group_id_by_name(self, name):
        """Returns the ID of a group by its name, or None."""
        for g in self.data["GrupoCosto"]:
            if g['nombre'] == name:
                return g['id']
        return None

    def add_group(self, name, description=""):
        """Adds a new cost group and returns its ID."""
        existing_id = self.get_group_id_by_name(name)
        if existing_id:
            return existing_id

        new_id = len(self.data["GrupoCosto"]) + 1
        self.data["GrupoCosto"].append({"id": new_id, "nombre": name, "description": description})
        return new_id

    def get_partidas_list(self):
        """Returns a list of all partidas for UI display."""
        items = []
        for k in sorted(self.data["partidas"].keys()):
            p = self.data["partidas"][k]
            # (idRevit, idGrupoCosto, description, comments, cantidad, punit, unidad, preciototal)
            items.append((p.get('idRevit'), p.get('idGrupoCosto'), p.get('description', ""), p.get('comments', ""), p.get('cantidad', 0), 
                         p.get('punit', 0), p.get('unidad', ""), p.get('preciototal', 0)))
        return items

    def upsert_partida(self, id_revit, group_id, qty, punit, unit, total, description="", comments=""):
        """Saves or updates a takeoff item."""
        self.data["partidas"][str(id_revit)] = {
            "idRevit": id_revit,
            "idGrupoCosto": group_id,
            "description": description,
            "comments": comments,
            "cantidad": qty,
            "punit": punit,
            "unidad": unit,
            "preciototal": total
        }

    def save(self):
        """Atomic write to disk."""
        temp_path = self.path + ".tmp"
        try:
            with codecs.open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            if os.path.exists(self.path):
                os.remove(self.path)
            os.rename(temp_path, self.path)
            return True
        except:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

def get_store(db_path):
    """Returns a DataStore instance."""
    return DataStore(db_path)

