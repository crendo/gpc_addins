"""Insert an Area-m2 GPC instance."""
__title__ = 'Area/Perimetro'
__author__ = 'Computos Revit Team'

import os
import sys

# Library paths are handled automatically by pyRevit

import placement

if __name__ == "__main__":
    placement.place_gpc_instance("GPC-CM-Area")

