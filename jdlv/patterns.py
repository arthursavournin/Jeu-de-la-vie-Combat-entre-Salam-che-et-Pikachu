# -*- coding: utf-8 -*-
"""
Bibliothèque de motifs classiques, décrits au format RLE
(https://conwaylife.com/wiki/Run_Length_Encoded).
"""
import re

import numpy as np


def rle(texte):
    """Convertit une chaîne RLE en tableau booléen (lignes, colonnes)."""
    lignes, ligne = [], []
    for nombre, symbole in re.findall(r"(\d*)([bo$!])", texte):
        n = int(nombre) if nombre else 1
        if symbole == "b":
            ligne += [False] * n
        elif symbole == "o":
            ligne += [True] * n
        elif symbole == "$":
            lignes.append(ligne)
            lignes += [[]] * (n - 1)
            ligne = []
        else:
            break
    lignes.append(ligne)
    largeur = max(len(l) for l in lignes)
    return np.array([l + [False] * (largeur - len(l)) for l in lignes], bool)


MOTIFS = {
    "Cellule": "o!",
    "Planeur": "bo$2bo$3o!",
    "Vaisseau léger (LWSS)": "bo2bo$o4b$o3bo$4o!",
    "Vaisseau moyen (MWSS)": "3bo2b$bo3bo$o5b$o4bo$5o!",
    "Vaisseau lourd (HWSS)": "3b2o2b$bo4bo$o6b$o5bo$6o!",
    "Canon à planeurs (Gosper)":
        "24bo$22bobo$12b2o6b2o12b2o$11bo3bo4b2o12b2o$2o8bo5bo3b2o$"
        "2o8bo3bob2o4bobo$10bo5bo7bo$11bo3bo$12b2o!",
    "Clignotant": "3o!",
    "Crapaud": "b3o$3o!",
    "Balise": "2o$o$3bo$2b2o!",
    "Pulsar":
        "2b3o3b3o2b2$o4bobo4bo$o4bobo4bo$o4bobo4bo$2b3o3b3o2b2$"
        "2b3o3b3o2b$o4bobo4bo$o4bobo4bo$o4bobo4bo2$2b3o3b3o!",
    "Pentadécathlon": "2bo4bo2b$2ob4ob2o$2bo4bo!",
    "R-pentomino": "b2o$2o$bo!",
    "Gland (Acorn)": "bo5b$3bo3b$2o2b3o!",
    "Diehard": "6bob$2o6b$bo3b3o!",
    "Bloc": "2o$2o!",
    "Ruche": "b2o$o2bo$b2o!",
}

MOTIFS = {nom: rle(code) for nom, code in MOTIFS.items()}

# Vaisseaux utilisés par les attaques : tous orientés vers la droite.
# (le LWSS en RLE ci-dessus avance vers la gauche, on le retourne.)
LWSS_DROITE = np.fliplr(MOTIFS["Vaisseau léger (LWSS)"])
MWSS_DROITE = np.fliplr(MOTIFS["Vaisseau moyen (MWSS)"])
HWSS_DROITE = np.fliplr(MOTIFS["Vaisseau lourd (HWSS)"])
