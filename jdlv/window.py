# -*- coding: utf-8 -*-
"""
Fenêtre principale : la zone de jeu à gauche, le panneau de contrôle à droite.
"""
import json
import random

import numpy as np
from PyQt5.QtCore import QElapsedTimer, Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                             QShortcut, QSlider, QVBoxLayout, QWidget)

from .arenes import ARENES
from .battle import HAUTEUR, LARGEUR, Combat
from .canvas import Canvas, _normaliser
from .engine import ELEC, FEU, REGLES, Life
from .patterns import MOTIFS
from .sound import Sons

COPIE = "(Sélection copiée)"


class Jeu:
    """État de la partie, partagé entre la fenêtre et la zone de jeu."""

    def __init__(self):
        self.life = Life(LARGEUR, HAUTEUR)
        self.combat = Combat(self.life)
        self.sons = Sons()
        self.mode = "combat"
        self.en_marche = False
        self.vitesse = 30
        self.outil = "crayon"
        self.equipe_pinceau = FEU
        self.nom_motif = "Planeur"
        self.rotation = 0
        self.presse_papier = None
        self.arene = random.choice(list(ARENES))

    def motif_courant(self):
        if self.nom_motif == COPIE and self.presse_papier is not None:
            motif = self.presse_papier
        else:
            motif = MOTIFS[self.nom_motif]
        return np.rot90(motif, self.rotation)

    def tourner_motif(self, sens=1):
        self.rotation = (self.rotation + sens) % 4

    def _extra(self):
        return self.combat.etat() if self.mode == "combat" else None

    def debut_edition(self):
        self.life.memoriser(self._extra())

    def generation(self):
        self.life.memoriser(self._extra())
        self.life.step()
        if self.mode == "combat":
            self.combat.apres_generation()

    def revenir(self):
        extra = self.life.revenir()
        if self.mode == "combat" and isinstance(extra, tuple):
            self.combat.restaurer(extra)
        return extra is not None

    def nouvelle_arene(self):
        autres = [a for a in ARENES if a != self.arene]
        self.arene = random.choice(autres)


STYLE = """
QMainWindow, QWidget#panneau { background: #11131b; }
QScrollArea { border: none; background: #11131b; }
QLabel { color: #d9dbe6; font-size: 12px; }
QLabel#titre { color: #ffffff; font-size: 19px; font-weight: 800; }
QLabel#sous_titre { color: #8a8fa8; font-size: 11px; }
QLabel#section { color: #ffcf33; font-size: 11px; font-weight: 800; letter-spacing: 1px; padding-top: 8px; }
QPushButton {
    background: #1f2230; color: #e9eaf2; border: 1px solid #2c3044; border-radius: 9px;
    padding: 7px 8px; font-size: 12px; font-weight: 600;
}
QPushButton:hover { background: #2a2e42; border-color: #3d4361; }
QPushButton:pressed { background: #161824; }
QPushButton:checked { background: #33395a; border: 1px solid #8ea2ff; color: #ffffff; }
QPushButton:disabled { color: #5a5e72; background: #171923; }
QPushButton#jouer { background: #e8452c; border: none; font-size: 15px; font-weight: 800; padding: 10px; }
QPushButton#jouer:hover { background: #ff5a3d; }
QPushButton#feu { background: #3a1d14; border-color: #7a3518; color: #ffb38a; }
QPushButton#feu:hover { background: #4f2618; }
QPushButton#elec { background: #3a3110; border-color: #7a6514; color: #ffe57a; }
QPushButton#elec:hover { background: #4d4116; }
QPushButton#feu:checked { background: #ff7a2f; color: #1b0d05; border-color: #ffd1b0; }
QPushButton#elec:checked { background: #ffd60a; color: #2b2300; border-color: #fff3b0; }
QComboBox {
    background: #1f2230; color: #e9eaf2; border: 1px solid #2c3044; border-radius: 8px;
    padding: 5px 8px; font-size: 12px;
}
QComboBox QAbstractItemView { background: #1f2230; color: #e9eaf2; selection-background-color: #33395a; }
QCheckBox { color: #d9dbe6; font-size: 12px; spacing: 8px; }
QSlider::groove:horizontal { height: 6px; background: #2c3044; border-radius: 3px; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff7a2f, stop:1 #ffd60a); border-radius: 3px; }
QSlider::handle:horizontal { background: #ffffff; width: 16px; margin: -6px 0; border-radius: 8px; }
"""


class Fenetre(QMainWindow):
    def __init__(self):
        super().__init__()
        self.jeu = Jeu()
        self.setWindowTitle("Jeu de la vie — Salamèche contre Pikachu")
        self.resize(1440, 860)
        self.setStyleSheet(STYLE)

        self.canvas = Canvas(self.jeu)
        panneau = self._panneau()
        defile = QScrollArea()
        defile.setWidget(panneau)
        defile.setWidgetResizable(True)
        defile.setFixedWidth(300)
        defile.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        centre = QWidget()
        disposition = QHBoxLayout(centre)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(0)
        disposition.addWidget(self.canvas, 1)
        disposition.addWidget(defile)
        self.setCentralWidget(centre)

        self._raccourcis()
        self._accumulateur = 0.0
        self._chrono = QElapsedTimer()
        self._chrono.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self._synchroniser()
        self.canvas.setFocus()

    # ------------------------------------------------------------- panneau
    def _panneau(self):
        w = QWidget()
        w.setObjectName("panneau")
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(6)

        titre = QLabel("Jeu de la vie")
        titre.setObjectName("titre")
        sous = QLabel("Combat entre Salamèche et Pikachu")
        sous.setObjectName("sous_titre")
        v.addWidget(titre)
        v.addWidget(sous)

        self.b_jouer = self._bouton("▶  Lancer", self.basculer, "jouer")
        v.addWidget(self.b_jouer)
        ligne = QHBoxLayout()
        ligne.addWidget(self._bouton("⏮ Retour", self.reculer))
        ligne.addWidget(self._bouton("Pas ⏭", self.pas))
        ligne.addWidget(self._bouton("⟲ Revanche", self.nouveau_combat))
        v.addLayout(ligne)

        self.l_vitesse = QLabel()
        v.addWidget(self.l_vitesse)
        self.s_vitesse = QSlider(Qt.Horizontal)
        self.s_vitesse.setRange(1, 120)
        self.s_vitesse.setValue(self.jeu.vitesse)
        self.s_vitesse.setFocusPolicy(Qt.NoFocus)
        self.s_vitesse.valueChanged.connect(self._vitesse)
        v.addWidget(self.s_vitesse)
        self._vitesse(self.jeu.vitesse)

        v.addWidget(self._section("MODE"))
        self.c_mode = QComboBox()
        self.c_mode.addItems(["⚔️  Combat Pokémon", "🧪  Bac à sable"])
        self.c_mode.currentIndexChanged.connect(self._changer_mode)
        v.addWidget(self.c_mode)

        # --- Dresseurs
        self.zone_combat = QWidget()
        zc = QVBoxLayout(self.zone_combat)
        zc.setContentsMargins(0, 0, 0, 0)
        zc.setSpacing(6)
        zc.addWidget(self._section("DRESSEURS"))
        combat = self.jeu.combat
        self.x_ia = {}
        grille = QGridLayout()
        grille.setSpacing(6)
        for col, (f, atk, spe, nom_obj) in enumerate([
                (combat.salameche, "A", "Z", "feu"), (combat.pikachu, "P", "O", "elec")]):
            x = QCheckBox(f"{f.nom.capitalize()} : IA")
            x.setChecked(True)
            x.setFocusPolicy(Qt.NoFocus)
            x.toggled.connect(lambda etat, f=f: setattr(f, "ia", etat))
            self.x_ia[f.nom] = x
            grille.addWidget(x, 0, col)
            grille.addWidget(self._bouton(f"{f.nom_attaque} ({atk})",
                                          lambda _=False, f=f: self.attaquer(f), nom_obj), 1, col)
            grille.addWidget(self._bouton(f"{f.nom_speciale} ({spe})",
                                          lambda _=False, f=f: self.speciale(f), nom_obj), 2, col)
        zc.addLayout(grille)
        astuce = QLabel("Appuie sur une attaque pour prendre le contrôle du Pokémon : "
                        "décoche « IA » des deux côtés pour jouer à deux !")
        astuce.setWordWrap(True)
        astuce.setObjectName("sous_titre")
        zc.addWidget(astuce)
        v.addWidget(self.zone_combat)

        v.addWidget(self._section("ARÈNE"))
        self.c_arene = QComboBox()
        self.c_arene.addItems(list(ARENES))
        self.c_arene.currentTextChanged.connect(self._changer_arene)
        v.addWidget(self.c_arene)

        # --- Outils
        v.addWidget(self._section("DESSINER"))
        equipes = QHBoxLayout()
        self.g_equipe = QButtonGroup(self)
        for i, (texte, nom_obj) in enumerate([("🔥 Feu", "feu"), ("⚡ Électrik", "elec")]):
            b = self._bouton(texte, None, nom_obj)
            b.setCheckable(True)
            self.g_equipe.addButton(b, i)
            equipes.addWidget(b)
        self.g_equipe.button(0).setChecked(True)
        self.g_equipe.idClicked.connect(lambda i: setattr(self.jeu, "equipe_pinceau", FEU if i == 0 else ELEC))
        v.addLayout(equipes)

        outils = QGridLayout()
        outils.setSpacing(6)
        self.g_outil = QButtonGroup(self)
        self._outils = ["crayon", "gomme", "motif", "selection"]
        for i, texte in enumerate(["✏️ Crayon", "🧽 Gomme", "✳️ Motif", "⬚ Sélection"]):
            b = self._bouton(texte, None)
            b.setCheckable(True)
            self.g_outil.addButton(b, i)
            outils.addWidget(b, i // 2, i % 2)
        self.g_outil.button(0).setChecked(True)
        self.g_outil.idClicked.connect(self._changer_outil)
        v.addLayout(outils)

        self.c_motif = QComboBox()
        self.c_motif.addItems(list(MOTIFS))
        self.c_motif.setCurrentText(self.jeu.nom_motif)
        self.c_motif.currentTextChanged.connect(self._changer_motif)
        v.addWidget(self.c_motif)

        ligne = QHBoxLayout()
        ligne.addWidget(self._bouton("🎲 Soupe", self.soupe))
        ligne.addWidget(self._bouton("🧹 Tout effacer", self.effacer_tout))
        v.addLayout(ligne)

        self.zone_regle = QWidget()
        zr = QVBoxLayout(self.zone_regle)
        zr.setContentsMargins(0, 0, 0, 0)
        zr.addWidget(self._section("RÈGLE"))
        self.c_regle = QComboBox()
        self.c_regle.addItems(list(REGLES))
        self.c_regle.currentTextChanged.connect(lambda nom: self.jeu.life.set_regle(REGLES[nom]))
        zr.addWidget(self.c_regle)
        v.addWidget(self.zone_regle)

        v.addWidget(self._section("FICHIERS"))
        ligne = QHBoxLayout()
        ligne.addWidget(self._bouton("📂 Ouvrir", self.ouvrir))
        ligne.addWidget(self._bouton("💾 Enregistrer", self.enregistrer))
        v.addLayout(ligne)
        ligne = QHBoxLayout()
        self.b_son = self._bouton("🔊 Son", self.basculer_son)
        ligne.addWidget(self.b_son)
        ligne.addWidget(self._bouton("❓ Aide (H)", self.basculer_aide))
        v.addLayout(ligne)
        v.addStretch(1)
        credits = QLabel("Projet de Eliott Michaux, Arthur Savournin et Martin Bravais.")
        credits.setWordWrap(True)
        credits.setObjectName("sous_titre")
        v.addWidget(credits)
        return w

    def _section(self, texte):
        l = QLabel(texte)
        l.setObjectName("section")
        return l

    def _bouton(self, texte, action, nom_obj=None):
        b = QPushButton(texte)
        b.setFocusPolicy(Qt.NoFocus)
        b.setCursor(Qt.PointingHandCursor)
        if nom_obj:
            b.setObjectName(nom_obj)
        if action:
            b.clicked.connect(action)
        return b

    def _raccourcis(self):
        combat = self.jeu.combat
        table = {
            "Space": self.basculer,
            "N": self.pas,
            "Right": self.pas,
            "Left": self.reculer,
            "R": self.nouveau_combat,
            "A": lambda: self.attaquer(combat.salameche),
            "Z": lambda: self.speciale(combat.salameche),
            "P": lambda: self.attaquer(combat.pikachu),
            "O": lambda: self.speciale(combat.pikachu),
            "T": lambda: self.c_arene.setCurrentText(
                random.choice([a for a in ARENES if a != self.jeu.arene])),
            "E": lambda: self.jeu.tourner_motif(),
            "H": self.basculer_aide,
            "M": self.basculer_son,
            "Escape": self._annuler,
            "Delete": self.effacer_selection,
            "Backspace": self.effacer_selection,
            "Ctrl+C": self.copier_selection,
            "Ctrl+S": self.enregistrer,
            "Ctrl+O": self.ouvrir,
            "Ctrl+Z": self.reculer,
        }
        for touche, action in table.items():
            QShortcut(QKeySequence(touche), self, activated=action)

    # ----------------------------------------------------------- boucle
    def _tick(self):
        dt = min(0.1, self._chrono.restart() / 1000)
        jeu = self.jeu
        if jeu.en_marche:
            self._accumulateur += dt * jeu.vitesse
            n = min(int(self._accumulateur), 12)
            self._accumulateur -= int(self._accumulateur)
            for _ in range(n):
                jeu.generation()
            if n:
                self.canvas.sale()
        evts = jeu.combat.evenements
        if evts:
            jeu.combat.evenements = []
            if jeu.mode == "combat":
                self.canvas.consommer(evts)
        self.canvas.avancer(dt)

    def _synchroniser(self):
        self.b_jouer.setText("⏸  Pause" if self.jeu.en_marche else "▶  Lancer")
        for f in self.jeu.combat.combattants:
            x = self.x_ia[f.nom]
            x.blockSignals(True)
            x.setChecked(f.ia)
            x.blockSignals(False)
        combat = self.jeu.mode == "combat"
        self.zone_combat.setVisible(combat)
        self.zone_regle.setVisible(not combat)
        self.c_arene.blockSignals(True)
        self.c_arene.setCurrentText(self.jeu.arene)
        self.c_arene.blockSignals(False)
        self.b_son.setText("🔊 Son" if self.jeu.sons.actif else "🔇 Muet")

    # ---------------------------------------------------------- actions
    def basculer(self):
        self.jeu.en_marche = not self.jeu.en_marche
        self._accumulateur = 0.0
        self._synchroniser()

    def pas(self):
        self.jeu.en_marche = False
        self.jeu.generation()
        self.canvas.sale()
        self._synchroniser()

    def reculer(self):
        self.jeu.en_marche = False
        if self.jeu.revenir():
            self.canvas.sale()
        self._synchroniser()

    def nouveau_combat(self):
        jeu = self.jeu
        if jeu.mode != "combat":
            self.c_mode.setCurrentIndex(0)
            return
        jeu.life.set_regle("B3/S23")
        jeu.combat.reinitialiser()
        jeu.en_marche = False
        jeu.nouvelle_arene()
        self.canvas.reinitialiser_effets()
        jeu.sons.jouer("debut")
        self._synchroniser()

    def attaquer(self, f):
        if self.jeu.mode != "combat":
            return
        self._prendre_controle(f)
        self.jeu.combat.attaque(f, manuel=True)

    def speciale(self, f):
        if self.jeu.mode != "combat":
            return
        self._prendre_controle(f)
        self.jeu.combat.speciale(f)

    def _prendre_controle(self, f):
        if f.ia:
            f.ia = False
            self.canvas.dire(f"Tu contrôles {f.nom} ! ({'A / Z' if f.equipe == FEU else 'P / O'})", True)
            self._synchroniser()

    def _changer_mode(self, index):
        jeu = self.jeu
        jeu.en_marche = False
        if index == 0:
            jeu.mode = "combat"
            self.nouveau_combat()
        else:
            jeu.mode = "bac"
            jeu.life.vider()
            jeu.life.set_regle(REGLES[self.c_regle.currentText()])
            self.canvas.reinitialiser_effets()
            self._installer_motif_demo()
        self._synchroniser()

    def _installer_motif_demo(self):
        life = self.jeu.life
        life.tamponner(MOTIFS["Canon à planeurs (Gosper)"], 10, 12, FEU)
        life.tamponner(np.fliplr(MOTIFS["Canon à planeurs (Gosper)"]), LARGEUR - 46, 12, ELEC)
        life.tamponner(MOTIFS["Pulsar"], LARGEUR // 2 - 6, 55, FEU)
        self.canvas.sale()

    def _changer_arene(self, nom):
        self.jeu.arene = nom
        self.canvas.update()

    def _changer_outil(self, i):
        self.jeu.outil = self._outils[i]
        self.canvas.selection = None if self.jeu.outil != "selection" else self.canvas.selection
        self.canvas.update()

    def _changer_motif(self, nom):
        self.jeu.nom_motif = nom
        self.jeu.rotation = 0
        self.g_outil.button(2).setChecked(True)
        self._changer_outil(2)

    def _annuler(self):
        self.canvas.selection = None
        self.canvas.aide = False
        self.canvas.update()

    def soupe(self):
        jeu = self.jeu
        jeu.debut_edition()
        if jeu.mode == "combat":
            for _ in range(6):
                jeu.life.soupe(random.randint(45, LARGEUR - 45), random.randint(20, HAUTEUR - 20),
                               random.randint(3, 7), 0.4, random.choice([FEU, ELEC]))
        else:
            jeu.life.aleatoire(0.22)
        self.canvas.sale()

    def effacer_tout(self):
        self.jeu.debut_edition()
        self.jeu.life.vivant[:] = False
        self.jeu.life.trainee[:] = 0
        self.canvas.sale()

    def copier_selection(self):
        if not self.canvas.selection:
            return
        x0, y0, x1, y1 = _normaliser(self.canvas.selection)
        zone = self.jeu.life.vivant[y0:y1 + 1, x0:x1 + 1].copy()
        if not zone.any():
            return
        ys, xs = np.nonzero(zone)
        self.jeu.presse_papier = zone[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        if self.c_motif.findText(COPIE) < 0:
            self.c_motif.addItem(COPIE)
        self.c_motif.setCurrentText(COPIE)
        self._changer_motif(COPIE)
        self.canvas.selection = None
        self.canvas.dire("Sélection copiée : clique pour la coller !", True)

    def effacer_selection(self):
        if not self.canvas.selection:
            return
        x0, y0, x1, y1 = _normaliser(self.canvas.selection)
        self.jeu.debut_edition()
        self.jeu.life.vivant[y0:y1 + 1, x0:x1 + 1] = False
        self.canvas.selection = None
        self.canvas.sale()

    def basculer_son(self):
        self.jeu.sons.actif = not self.jeu.sons.actif
        self._synchroniser()

    def basculer_aide(self):
        self.canvas.aide = not self.canvas.aide
        self.canvas.update()

    def _vitesse(self, valeur):
        self.jeu.vitesse = valeur
        self.l_vitesse.setText(f"Vitesse : {valeur} générations / seconde")

    # --------------------------------------------------------- fichiers
    def enregistrer(self):
        nom, _ = QFileDialog.getSaveFileName(self, "Enregistrer la grille", "grille.jdlv", "Grilles (*.jdlv)")
        if not nom:
            return
        life = self.jeu.life
        ys, xs = np.nonzero(life.vivant)
        donnees = {
            "format": "jdlv-2",
            "largeur": life.largeur,
            "hauteur": life.hauteur,
            "regle": life.regle,
            "generation": life.generation,
            "cellules": [[int(x), int(y), int(life.equipe[y, x])] for x, y in zip(xs, ys)],
        }
        with open(nom, "w", encoding="utf-8") as f:
            json.dump(donnees, f)
        self.canvas.dire("Grille enregistrée !", True)

    def ouvrir(self):
        nom, _ = QFileDialog.getOpenFileName(self, "Ouvrir une grille", "", "Grilles (*.jdlv)")
        if not nom:
            return
        try:
            with open(nom, encoding="utf-8") as f:
                donnees = json.load(f)
            cellules = _lire_cellules(donnees)
        except (OSError, ValueError, KeyError, TypeError) as erreur:
            QMessageBox.warning(self, "Ouverture impossible",
                                f"Le fichier n'a pas pu être chargé...\n\n{erreur}")
            return
        if self.jeu.mode != "bac":
            self.c_mode.setCurrentIndex(1)
        life = self.jeu.life
        life.vider()
        if isinstance(donnees, dict) and "regle" in donnees:
            nom_regle = next((k for k, v in REGLES.items() if v == donnees["regle"]), None)
            if nom_regle:
                self.c_regle.setCurrentText(nom_regle)
        for x, y, equipe in cellules:
            life.poser(x, y, equipe)
        self.canvas.sale()
        self.canvas.dire("Grille chargée !", True)


def _lire_cellules(donnees):
    """Lit le format actuel ou celui de la première version (liste de cases)."""
    if isinstance(donnees, dict):
        return [tuple(c) for c in donnees["cellules"]]
    jaunes = {"#FDD835", "yellow", "#F47F17"}
    cellules = []
    for y, ligne in enumerate(donnees):
        for x, case in enumerate(ligne):
            if case["s"] == 1:
                equipe = ELEC if case["c"] in jaunes else FEU
                cellules.append((x + (LARGEUR - len(ligne)) // 2, y - max(0, len(donnees) - HAUTEUR) // 2, equipe))
    return cellules
