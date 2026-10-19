# -*- coding: utf-8 -*-
"""
Moteur du jeu de la vie, vectorisé avec numpy.

Chaque cellule vivante appartient à une équipe (FEU ou ELEC). Une cellule
qui naît prend la couleur majoritaire parmi ses voisines vivantes : c'est la
variante « Immigration » du jeu de la vie, qui permet à deux camps de se
disputer le terrain sans changer les règles de Conway.
"""
from collections import deque

import numpy as np

FEU, ELEC = 0, 1

# Quelques règles célèbres, au format B(naissance)/S(survie).
REGLES = {
    "Conway (B3/S23)": "B3/S23",
    "HighLife (B36/S23)": "B36/S23",
    "Day & Night (B3678/S34678)": "B3678/S34678",
    "Seeds (B2/S)": "B2/S",
    "Labyrinthe (B3/S12345)": "B3/S12345",
}


def parse_regle(texte):
    """'B36/S23' -> ({3, 6}, {2, 3})"""
    naissance, survie = set(), set()
    for partie in texte.upper().split("/"):
        if partie.startswith("B"):
            naissance = {int(c) for c in partie[1:]}
        elif partie.startswith("S"):
            survie = {int(c) for c in partie[1:]}
    return naissance, survie


def voisins(a):
    """Nombre de voisins vivants de chaque case (bords non toriques)."""
    p = np.pad(a.astype(np.uint8), 1)
    return (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:]
            + p[1:-1, :-2] + p[1:-1, 2:]
            + p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:])


class Life:
    def __init__(self, largeur, hauteur, regle="B3/S23"):
        self.largeur = largeur
        self.hauteur = hauteur
        self.set_regle(regle)
        self.rng = np.random.default_rng()
        self.historique = deque(maxlen=600)
        self.vider()

    # ------------------------------------------------------------------ état
    def vider(self):
        forme = (self.hauteur, self.largeur)
        self.vivant = np.zeros(forme, bool)
        self.equipe = np.zeros(forme, np.int8)
        self.age = np.zeros(forme, np.uint16)
        # Traînée lumineuse laissée par les cellules mortes (1 -> 0).
        self.trainee = np.zeros(forme, np.float32)
        self.generation = 0
        self.historique.clear()

    def set_regle(self, regle):
        self.regle = regle
        naissance, survie = parse_regle(regle)
        self._naissance = np.array(sorted(naissance), np.uint8)
        self._survie = np.array(sorted(survie), np.uint8)

    def snapshot(self):
        return (self.vivant.copy(), self.equipe.copy(), self.age.copy(),
                self.trainee.copy(), self.generation)

    def restore(self, etat):
        (self.vivant, self.equipe, self.age,
         self.trainee, self.generation) = (
            etat[0].copy(), etat[1].copy(), etat[2].copy(),
            etat[3].copy(), etat[4])

    def population(self):
        feu = int(np.count_nonzero(self.vivant & (self.equipe == FEU)))
        elec = int(np.count_nonzero(self.vivant & (self.equipe == ELEC)))
        return feu, elec

    # ------------------------------------------------------------ évolution
    def step(self):
        n = voisins(self.vivant)
        n_elec = voisins(self.vivant & (self.equipe == ELEC))
        nait = ~self.vivant & np.isin(n, self._naissance)
        survit = self.vivant & np.isin(n, self._survie)

        # Couleur des nouveau-nés : majorité des voisins, égalité au hasard.
        double = n_elec.astype(np.int16) * 2
        pile = self.rng.random(n.shape) < 0.5
        nouvelle_equipe = np.where(double > n, ELEC,
                                   np.where(double < n, FEU, pile))

        meurt = self.vivant & ~survit
        self.trainee *= 0.82
        self.trainee[meurt] = 1.0

        self.equipe = np.where(nait, nouvelle_equipe, self.equipe).astype(np.int8)
        self.age = np.where(survit, np.minimum(self.age + 1, 60000), 0).astype(np.uint16)
        self.vivant = nait | survit
        self.trainee[self.vivant] = 0.0
        self.generation += 1

    # -------------------------------------------------------------- édition
    def dans_grille(self, x, y):
        return 0 <= x < self.largeur and 0 <= y < self.hauteur

    def poser(self, x, y, equipe):
        if self.dans_grille(x, y):
            self.vivant[y, x] = True
            self.equipe[y, x] = equipe
            self.age[y, x] = 0

    def effacer(self, x, y):
        if self.dans_grille(x, y):
            self.vivant[y, x] = False

    def tamponner(self, motif, x, y, equipe):
        """Pose un motif (tableau booléen) avec son coin haut-gauche en (x, y)."""
        h, w = motif.shape
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, self.largeur), min(y + h, self.hauteur)
        if x0 >= x1 or y0 >= y1:
            return
        zone = motif[y0 - y:y1 - y, x0 - x:x1 - x]
        self.vivant[y0:y1, x0:x1] |= zone
        self.equipe[y0:y1, x0:x1][zone] = equipe
        self.age[y0:y1, x0:x1][zone] = 0

    def soupe(self, cx, cy, rayon, densite, equipe):
        """Nuage aléatoire de cellules dans un disque."""
        yy, xx = np.ogrid[:self.hauteur, :self.largeur]
        disque = (xx - cx) ** 2 + (yy - cy) ** 2 <= rayon ** 2
        zone = disque & (self.rng.random(disque.shape) < densite)
        self.vivant |= zone
        self.equipe[zone] = equipe
        self.age[zone] = 0

    def aleatoire(self, densite=0.25):
        self.vider()
        self.vivant = self.rng.random((self.hauteur, self.largeur)) < densite
        self.equipe[:, self.largeur // 2:] = ELEC

    # ------------------------------------------------------------ historique
    def memoriser(self, extra=None):
        self.historique.append((self.snapshot(), extra))

    def revenir(self):
        """Revient d'une génération en arrière. Renvoie l'extra mémorisé."""
        if not self.historique:
            return None
        etat, extra = self.historique.pop()
        self.restore(etat)
        return extra if extra is not None else True
