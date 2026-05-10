"""Insert an Area-m2 GPC instance."""
__title__ = 'Area/Perimetro'
__author__ = 'Computos Revit Team'

import os
import sys

# Setup Library Paths
TAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSION_DIR = os.path.join(os.path.dirname(TAB_DIR), "computosRevit.extension")
LIB_PATH = os.path.join(EXTENSION_DIR, "lib")
if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

import placement

if __name__ == "__main__":
    placement.place_gpc_instance("GPC-CM-Area")
