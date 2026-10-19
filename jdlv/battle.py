# -*- coding: utf-8 -*-
"""
Le combat Salamèche contre Pikachu, joué *dans* le jeu de la vie.

Chaque Pokémon tire des vaisseaux (LWSS, MWSS, HWSS) de sa couleur. Toute
cellule ennemie qui touche un Pokémon lui retire un point de vie. Les attaques
spéciales (Lance-Flammes, Tonnerre) font naître un nuage chaotique de cellules
juste devant l'adversaire. Au K.O., le Pokémon vaincu explose... et sa
dépouille devient de la vie.
"""
import copy

import numpy as np

from .engine import ELEC, FEU
from .patterns import HWSS_DROITE, LWSS_DROITE, MWSS_DROITE
from .sprites import PIKACHU, SALAMECHE, vers_rgba

LARGEUR, HAUTEUR = 160, 90
PV_MAX = 100
ENERGIE_PAR_GEN = 0.45
ENERGIE_PAR_DEGAT = 1.2
MARGE_BORD = 2
AGE_EROSION = 90
TAUX_EROSION = 0.03


class Combattant:
    def __init__(self, nom, equipe, dessin, direction, attaque, speciale):
        self.nom = nom
        self.equipe = equipe
        self.sprite = vers_rgba(dessin)
        self.masque = self.sprite[..., 3] > 0
        self.direction = direction          # +1 : tire vers la droite
        self.nom_attaque = attaque
        self.nom_speciale = speciale
        self.x = self.y = 0
        self.ia = True
        self.reinitialiser()

    def reinitialiser(self):
        self.pv = PV_MAX
        self.energie = 0.0
        self.recharge = 25
        self.ko = False

    @property
    def h(self):
        return self.masque.shape[0]

    @property
    def w(self):
        return self.masque.shape[1]

    @property
    def centre(self):
        return self.x + self.w / 2, self.y + self.h / 2

    def zone_touche(self, forme):
        """Masque du sprite élargi d'une case, à sa place dans la grille."""
        m = np.pad(self.masque, 1)
        d = m.copy()
        d[1:, :] |= m[:-1, :]
        d[:-1, :] |= m[1:, :]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        zone = np.zeros(forme, bool)
        y0, x0 = self.y - 1, self.x - 1
        h, w = d.shape
        zone[max(y0, 0):y0 + h, max(x0, 0):x0 + w] = d[max(-y0, 0):, max(-x0, 0):]
        return zone

    def etat(self):
        return (self.pv, self.energie, self.recharge, self.ko, self.ia)

    def restaurer(self, etat):
        self.pv, self.energie, self.recharge, self.ko, self.ia = etat


class Combat:
    def __init__(self, life):
        self.life = life
        self.rng = np.random.default_rng()
        self.salameche = Combattant("SALAMÈCHE", FEU, SALAMECHE, +1,
                                    "Flammèche", "Lance-Flammes")
        self.pikachu = Combattant("PIKACHU", ELEC, PIKACHU, -1,
                                  "Éclair", "Tonnerre")
        self.combattants = [self.salameche, self.pikachu]
        self.evenements = []
        self.reinitialiser()

    # ------------------------------------------------------------------ état
    def reinitialiser(self):
        self.life.vider()
        sol = HAUTEUR // 2 + 4
        s, p = self.salameche, self.pikachu
        s.x, s.y = 8, sol - s.h // 2
        p.x, p.y = LARGEUR - 8 - p.w, sol - p.h // 2
        for c in self.combattants:
            c.reinitialiser()
        forme = (HAUTEUR, LARGEUR)
        self.zones = {id(c): c.zone_touche(forme) for c in self.combattants}
        self.projectiles = []
        self.vainqueur = None
        self.evenements = [("debut", None)]

    def adversaire(self, c):
        return self.pikachu if c is self.salameche else self.salameche

    def etat(self):
        return ([c.etat() for c in self.combattants],
                copy.deepcopy(self.projectiles), self.vainqueur)

    def restaurer(self, etat):
        for c, e in zip(self.combattants, etat[0]):
            c.restaurer(e)
        self.projectiles = copy.deepcopy(etat[1])
        self.vainqueur = etat[2]

    def en_cours(self):
        return self.vainqueur is None

    # ------------------------------------------------------------- attaques
    def attaque(self, c, manuel=False):
        """Tir de base : un vaisseau de sa couleur vers l'adversaire."""
        if c.ko or c.recharge > 0 or not self.en_cours():
            return False
        vaisseau = [LWSS_DROITE, LWSS_DROITE, MWSS_DROITE][self.rng.integers(3)]
        self._tirer(c, vaisseau)
        c.recharge = 22 if manuel else int(self.rng.integers(35, 75))
        self.evenements.append(("tir", c))
        return True

    def _tirer(self, c, vaisseau, y=None):
        if c.direction < 0:
            vaisseau = np.fliplr(vaisseau)
        vh, vw = vaisseau.shape
        if y is None:
            y = c.y + int(self.rng.integers(1, max(c.h - vh, 2)))
        x = c.x + c.w + 3 if c.direction > 0 else c.x - 3 - vw
        self.life.tamponner(vaisseau, x, y, c.equipe)

    def speciale(self, c):
        if c.ko or c.energie < 100 or not self.en_cours():
            return False
        c.energie = 0.0
        cible = self.adversaire(c)
        cx = (cible.x - 7) if c.direction > 0 else (cible.x + cible.w + 7)
        cx += int(self.rng.integers(-2, 3))
        cy = int(cible.centre[1] + self.rng.integers(-5, 6))
        if c.equipe == FEU:
            # Boule de feu en cloche : elle explose à l'arrivée.
            bx, by = c.x + c.w, c.y + 4
            self.projectiles.append({"depart": (bx, by), "arrivee": (cx, cy),
                                     "t": 0, "duree": 26, "equipe": FEU})
            self.evenements.append(("lance_flammes", c))
        else:
            chemin = self._eclair(cx, cy)
            for (x, y) in chemin:
                for dx in (-1, 0, 1):
                    if self.rng.random() < 0.55:
                        self.life.poser(x + dx, y, ELEC)
            self.life.soupe(cx, cy, 6, 0.5, ELEC)
            self.evenements.append(("tonnerre", (c, chemin)))
        # Une salve de vaisseaux lourds accompagne l'attaque spéciale.
        for dy in (-7, 7):
            self._tirer(c, HWSS_DROITE, int(c.centre[1] + dy - 3))
        return True

    def _eclair(self, cx, cy):
        """Chemin en zigzag du haut de l'écran jusqu'à (cx, cy)."""
        chemin = []
        x = cx + int(self.rng.integers(-12, 13))
        for y in range(0, cy + 1):
            restant = cy - y
            if restant:
                x += int(self.rng.integers(-2, 3)) + int(np.sign(cx - x)) * (abs(cx - x) > restant)
            chemin.append((int(np.clip(x, 0, LARGEUR - 1)), y))
        return chemin

    # ------------------------------------------------------------ évolution
    def apres_generation(self):
        life = self.life
        m = MARGE_BORD
        life.vivant[:m, :] = life.vivant[-m:, :] = False
        life.vivant[:, :m] = life.vivant[:, -m:] = False

        # L'arène s'use : les débris figés finissent par s'effriter, sinon
        # ils formeraient des murs infranchissables entre les deux Pokémon.
        use = life.vivant & (life.age > AGE_EROSION) \
            & (self.rng.random(life.vivant.shape) < TAUX_EROSION)
        life.vivant[use] = False
        life.trainee[use] = 1.0

        for c in self.combattants:
            if c.ko:
                continue
            zone = self.zones[id(c)]
            touche = life.vivant & zone
            ennemi = touche & (life.equipe != c.equipe)
            degats = int(np.count_nonzero(ennemi))
            if degats and self.en_cours():
                c.pv = max(0, c.pv - degats)
                self.adversaire(c).energie = min(
                    100.0, self.adversaire(c).energie + degats * ENERGIE_PAR_DEGAT)
                ys, xs = np.nonzero(ennemi)
                self.evenements.append(("touche", (c, degats, list(zip(xs, ys)))))
            life.vivant[zone] = False

        for p in list(self.projectiles):
            p["t"] += 1
            if p["t"] >= p["duree"]:
                self.projectiles.remove(p)
                x, y = p["arrivee"]
                life.soupe(x, y, 6, 0.5, p["equipe"])
                self.evenements.append(("impact", (x, y, p["equipe"])))

        if not self.en_cours():
            return
        for c in self.combattants:
            c.energie = min(100.0, c.energie + ENERGIE_PAR_GEN)
            c.recharge -= 1
            if c.ia:
                if c.energie >= 100 and self.rng.random() < 0.04:
                    self.speciale(c)
                elif c.recharge <= 0 and self.rng.random() < 0.08:
                    self.attaque(c)
        for c in self.combattants:
            if c.pv <= 0 and not c.ko:
                self._ko(c)

    def _ko(self, c):
        """Le vaincu explose : son pixel art devient de la vie."""
        c.ko = True
        self.vainqueur = self.adversaire(c)
        ys, xs = np.nonzero(c.masque)
        for x, y in zip(xs, ys):
            self.life.poser(c.x + x, c.y + y, c.equipe)
        cx, cy = c.centre
        self.life.soupe(int(cx), int(cy), 14, 0.22, c.equipe)
        self.evenements.append(("ko", c))
