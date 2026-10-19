# -*- coding: utf-8 -*-
"""
Zone de jeu : rendu des cellules, des Pokémon, des effets (particules,
éclairs, boules de feu), de l'interface façon jeux Pokémon, et édition à la
souris.
"""
import math
import random
from collections import deque

import numpy as np
from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import (QColor, QFont, QImage, QPainter, QPainterPath, QPen,
                         QPolygonF, QRadialGradient)
from PyQt5.QtWidgets import QWidget

from .arenes import dessiner_arene
from .battle import PV_MAX
from .engine import ELEC, FEU

# Couleur des cellules selon l'équipe et l'âge (nouveau-né -> vieille cellule).
PALETTE = np.array([
    [(255, 244, 190), (255, 200, 90), (255, 145, 45), (240, 85, 40), (196, 44, 44)],
    [(235, 252, 255), (255, 246, 140), (255, 222, 40), (245, 190, 0), (214, 150, 0)],
], np.uint8)
COULEUR_EQUIPE = {FEU: QColor(255, 120, 40), ELEC: QColor(255, 215, 30)}
LIGNE_SOL = 60  # ligne d'horizon du décor, en cases


class Particule:
    __slots__ = ("x", "y", "vx", "vy", "vie", "duree", "couleur", "taille", "gravite")

    def __init__(self, x, y, vx, vy, duree, couleur, taille=0.5, gravite=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.vie = self.duree = duree
        self.couleur = couleur
        self.taille = taille
        self.gravite = gravite


def _qimage(buf):
    h, w = buf.shape[:2]
    return QImage(buf.data, w, h, w * 4, QImage.Format_RGBA8888)


class Canvas(QWidget):
    def __init__(self, jeu):
        super().__init__()
        self.jeu = jeu
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(720, 420)
        self.t = 0.0
        self.particules = []
        self.eclairs = []
        self.textes = []
        self.secousse = 0.0
        self.flash = 0.0
        self.flash_couleur = QColor(255, 255, 255)
        self.banniere = None
        self.messages = deque()
        self.message = None
        self.aide = False
        self.anim = {}
        self.souris = None
        self.selection = None
        self._trace = None
        self._derniere_case = None
        self._cle_fond = None
        self._fond = None
        self._cle_cellules = None
        self._sprites = {}
        for f in jeu.combat.combattants:
            buf = np.ascontiguousarray(f.sprite)
            blanc = buf.copy()
            blanc[..., :3] = 255
            self._sprites[f.nom] = (buf, _qimage(buf), blanc, _qimage(blanc))
        self.reinitialiser_effets()

    # ------------------------------------------------------------- outils
    def reinitialiser_effets(self):
        self.particules.clear()
        self.eclairs.clear()
        self.textes.clear()
        self.messages.clear()
        self.message = None
        self.banniere = None
        self.secousse = self.flash = 0.0
        for f in self.jeu.combat.combattants:
            self.anim[f.nom] = {"touche": 0.0, "attaque": 0.0, "pv": float(f.pv)}
        self.sale()

    def sale(self):
        self._cle_cellules = None
        self.update()

    def geometrie(self):
        life = self.jeu.life
        c = max(2, int(min(self.width() / life.largeur, self.height() / life.hauteur)))
        ox = (self.width() - life.largeur * c) // 2
        oy = (self.height() - life.hauteur * c) // 2
        return c, ox, oy

    def dire(self, texte, prioritaire=False):
        if prioritaire:
            self.messages.append(texte)
        elif not self.messages and (self.message is None or self._message_fini()):
            self.messages.append(texte)

    def _message_fini(self):
        texte, t0 = self.message
        return self.t - t0 > len(texte) / 50 + 0.6

    def eclater(self, x, y, n, couleurs, vitesse=12.0, duree=0.8, gravite=6.0, taille=0.5):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            v = random.uniform(0.2, 1.0) * vitesse
            self.particules.append(Particule(
                x, y, math.cos(a) * v, math.sin(a) * v,
                random.uniform(0.5, 1.0) * duree, random.choice(couleurs),
                taille * random.uniform(0.6, 1.3), gravite))
        del self.particules[:-700]

    # ------------------------------------------------------------ événements
    def consommer(self, evenements):
        sons = self.jeu.sons
        combat = self.jeu.combat
        for type_, d in evenements:
            if type_ == "debut":
                self.reinitialiser_effets()
                self.dire("Un PIKACHU sauvage apparaît !", True)
                self.dire("SALAMÈCHE, je te choisis !", True)
            elif type_ == "tir":
                f = d
                self.anim[f.nom]["attaque"] = 0.18
                x = f.x + f.w + 1 if f.direction > 0 else f.x - 1
                y = f.centre[1]
                couleurs = _couleurs_equipe(f.equipe)
                for _ in range(16):
                    self.particules.append(Particule(
                        x, y + random.uniform(-3, 3), f.direction * random.uniform(4, 16),
                        random.uniform(-4, 4), random.uniform(0.2, 0.5),
                        random.choice(couleurs), 0.5))
                sons.jouer("tir_feu" if f.equipe == FEU else "tir_elec", 0.08)
                self.dire(f"{f.nom} utilise {f.nom_attaque.upper()} !")
            elif type_ == "touche":
                f, degats, cases = d
                self.anim[f.nom]["touche"] = 0.3
                adverse = combat.adversaire(f)
                for (x, y) in cases[:6]:
                    self.eclater(x + 0.5, y + 0.5, 6, _couleurs_equipe(adverse.equipe) + [QColor("white")],
                                 vitesse=10, duree=0.5)
                cx, cy = f.centre
                self.textes.append([cx + random.uniform(-4, 4), f.y - 1.0, f"-{degats}", 1.0])
                sons.jouer("touche", 0.09)
                if degats >= 8:
                    self.dire("C'est super efficace !")
            elif type_ == "lance_flammes":
                self.secousse = max(self.secousse, 0.25)
                sons.jouer("lance_flammes")
                self.dire(f"{d.nom} utilise {d.nom_speciale.upper()} !", True)
            elif type_ == "tonnerre":
                f, chemin = d
                self.eclairs.append([chemin, 0.0])
                self.flash, self.flash_couleur = 0.55, QColor(255, 250, 200)
                self.secousse = max(self.secousse, 0.5)
                x, y = chemin[-1]
                self.eclater(x, y, 60, _couleurs_equipe(ELEC) + [QColor("white")], vitesse=22, duree=0.7)
                sons.jouer("tonnerre")
                self.dire(f"{f.nom} utilise {f.nom_speciale.upper()} !", True)
            elif type_ == "impact":
                x, y, equipe = d
                self.eclater(x, y, 80, _couleurs_equipe(equipe) + [QColor(80, 70, 70)],
                             vitesse=22, duree=0.9, gravite=10)
                self.secousse = max(self.secousse, 0.45)
                self.flash, self.flash_couleur = 0.25, QColor(255, 200, 120)
                sons.jouer("impact")
            elif type_ == "ko":
                f = d
                buf = self._sprites[f.nom][0]
                ys, xs = np.nonzero(buf[..., 3])
                for k in np.random.choice(len(xs), min(260, len(xs) * 2)):
                    r, g, b = buf[ys[k], xs[k], :3]
                    a = random.uniform(0, 2 * math.pi)
                    v = random.uniform(6, 40)
                    self.particules.append(Particule(
                        f.x + xs[k] + 0.5, f.y + ys[k] + 0.5, math.cos(a) * v, math.sin(a) * v,
                        random.uniform(0.8, 1.8), QColor(int(r), int(g), int(b)), 0.8, 14))
                self.secousse = 1.2
                self.flash, self.flash_couleur = 1.0, QColor(255, 255, 255)
                self.banniere = ["K.O. !", 0.0, QColor(255, 70, 60)]
                sons.jouer("ko")
                vainqueur = combat.adversaire(f)
                self.messages.clear()
                self.message = None
                self.dire(f"{f.nom} est K.O. !", True)
                self.dire(f"{vainqueur.nom} remporte le combat !", True)
                self.dire("Sa dépouille donne naissance à une nouvelle vie...", True)
                QTimer.singleShot(1300, lambda: sons.jouer("victoire"))

    # -------------------------------------------------------------- animation
    def avancer(self, dt):
        self.t += dt
        for p in self.particules:
            p.vie -= dt
            p.vy += p.gravite * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vx *= 1 - 1.5 * dt
        self.particules = [p for p in self.particules if p.vie > 0]
        for e in self.eclairs:
            e[1] += dt
        self.eclairs = [e for e in self.eclairs if e[1] < 0.5]
        for tx in self.textes:
            tx[1] -= dt * 4
            tx[3] -= dt
        self.textes = [tx for tx in self.textes if tx[3] > 0]
        self.secousse = max(0.0, self.secousse - dt * 1.6)
        self.flash = max(0.0, self.flash - dt * 2.2)
        if self.banniere:
            self.banniere[1] += dt
            if self.banniere[1] > 1.8:
                self.banniere = None
        for f in self.jeu.combat.combattants:
            a = self.anim[f.nom]
            a["touche"] = max(0.0, a["touche"] - dt)
            a["attaque"] = max(0.0, a["attaque"] - dt)
            a["pv"] += (f.pv - a["pv"]) * min(1.0, dt * 5)
        # Traînée de la boule de feu
        for p in self.jeu.combat.projectiles:
            x, y = _position_projectile(p)
            for _ in range(3):
                self.particules.append(Particule(
                    x + random.uniform(-1, 1), y + random.uniform(-1, 1),
                    random.uniform(-3, 3), random.uniform(-6, 0), random.uniform(0.3, 0.6),
                    random.choice(_couleurs_equipe(FEU)), 0.7, -4))
        if self.message is None:
            if self.messages:
                self.message = (self.messages.popleft(), self.t)
        else:
            texte, t0 = self.message
            lecture = len(texte) / 50
            if (self.messages and self.t - t0 > lecture + 0.9) or self.t - t0 > lecture + 2.4:
                self.message = (self.messages.popleft(), self.t) if self.messages else None
        self.update()

    # ----------------------------------------------------------------- rendu
    def paintEvent(self, _):
        p = QPainter(self)
        c, ox, oy = self.geometrie()
        life = self.jeu.life
        W, H = life.largeur, life.hauteur
        fw, fh = W * c, H * c
        combat_actif = self.jeu.mode == "combat"

        if self.secousse > 0:
            amp = self.secousse ** 2 * c * 1.6
            p.translate(random.uniform(-amp, amp), random.uniform(-amp, amp))

        cle = (self.jeu.arene, self.width(), self.height(), c)
        if cle != self._cle_fond:
            self._cle_fond = cle
            self._fond = dessiner_arene(self.jeu.arene, self.width() + 40, self.height() + 40,
                                        oy + 20 + LIGNE_SOL * c, c)
        p.drawPixmap(-20, -20, self._fond)

        champ = QRectF(ox, oy, fw, fh)
        if c >= 6:
            p.setPen(QPen(QColor(255, 255, 255, 14), 1))
            for i in range(1, W):
                p.drawLine(ox + i * c, oy, ox + i * c, oy + fh)
            for j in range(1, H):
                p.drawLine(ox, oy + j * c, ox + fw, oy + j * c)

        if combat_actif:
            for f in self.jeu.combat.combattants:
                if not f.ko:
                    self._plateforme(p, f, c, ox, oy)

        self._preparer_cellules(c)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setOpacity(0.9)
        p.drawImage(champ, self._img_trainee)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        p.setOpacity(0.45)
        p.drawImage(champ, self._img_halo)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setOpacity(1.0)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QPointF(ox, oy), self._img_cellules)

        if combat_actif:
            for f in self.jeu.combat.combattants:
                if not f.ko:
                    self._pokemon(p, f, c, ox, oy)
            self._projectiles(p, c, ox, oy)
        self._eclairs(p, c, ox, oy)
        self._particules(p, c, ox, oy)
        self._textes(p, c, ox, oy)
        self._apercu_outil(p, c, ox, oy)

        p.resetTransform()
        if combat_actif:
            self._hud_combat(p, c, ox, oy, fw)
        else:
            self._hud_bac(p, c, ox, oy, fw)
        self._boite_dialogue(p, c, ox, oy, fw, fh)
        self._banniere(p, c, ox, oy, fw, fh)
        if self.flash > 0:
            col = QColor(self.flash_couleur)
            col.setAlpha(int(min(1.0, self.flash) * 200))
            p.fillRect(self.rect(), col)
        if self.aide:
            self._aide(p, c, ox, oy, fw, fh)
        p.end()

    def _preparer_cellules(self, c):
        life = self.jeu.life
        cle = (life.generation, c, id(life.vivant))
        if cle == self._cle_cellules:
            return
        self._cle_cellules = cle
        H, W = life.hauteur, life.largeur
        niveau = np.digitize(life.age, [1, 2, 6, 25])
        rgba = np.zeros((H, W, 4), np.uint8)
        rgba[..., :3] = PALETTE[life.equipe, niveau]
        rgba[..., 3] = life.vivant * 255

        grand = rgba.repeat(c, 0).repeat(c, 1)
        if c >= 4:
            grand[c - 1::c, :, 3] = 0
            grand[:, c - 1::c, 3] = 0
        if c >= 7:
            for dy in (0, c - 2):
                for dx in (0, c - 2):
                    grand[dy::c, dx::c, 3] = 0
        self._buf_cellules = np.ascontiguousarray(grand)
        self._img_cellules = _qimage(self._buf_cellules)

        halo = rgba.reshape(H // 2, 2, W // 2, 2, 4).max(axis=(1, 3))
        self._buf_halo = np.ascontiguousarray(halo)
        self._img_halo = _qimage(self._buf_halo)

        trainee = np.zeros((H, W, 4), np.uint8)
        trainee[..., :3] = PALETTE[life.equipe, 3]
        trainee[..., 3] = (np.clip(life.trainee, 0, 1) * 150).astype(np.uint8)
        self._buf_trainee = trainee
        self._img_trainee = _qimage(self._buf_trainee)

    def _plateforme(self, p, f, c, ox, oy):
        cx = ox + (f.x + f.w / 2) * c
        cy = oy + (f.y + f.h + 0.3) * c
        g = QRadialGradient(QPointF(cx, cy), f.w * c * 0.8)
        g.setColorAt(0, QColor(255, 255, 255, 70))
        g.setColorAt(0.7, QColor(255, 255, 255, 35))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), f.w * c * 0.8, c * 2.6)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawEllipse(QPointF(cx, cy), f.w * c * 0.45, c * 1.0)

    def _pokemon(self, p, f, c, ox, oy):
        a = self.anim[f.nom]
        combat = self.jeu.combat
        phase = 0 if f.equipe == FEU else 1.7
        if combat.vainqueur is f:
            dy = -abs(math.sin(self.t * 7)) * 2.2 * c
        else:
            dy = math.sin(self.t * 3 + phase) * 0.35 * c
        dx = f.direction * math.sin(a["attaque"] / 0.18 * math.pi) * 1.5 * c if a["attaque"] else 0
        if a["touche"] > 0:
            dx += random.uniform(-0.6, 0.6) * c
        cible = QRectF(ox + f.x * c + dx, oy + f.y * c + dy, f.w * c, f.h * c)
        _, img, _, blanc = self._sprites[f.nom]
        if a["touche"] > 0 and int(a["touche"] * 20) % 2:
            p.setOpacity(0.5)
        p.drawImage(cible, img)
        p.setOpacity(1.0)
        if a["touche"] > 0:
            p.setOpacity(min(1.0, a["touche"] * 3) * 0.75)
            p.drawImage(cible, blanc)
            p.setOpacity(1.0)
        if f.energie >= 100 and combat.en_cours():  # aura quand la spéciale est prête
            col = QColor(COULEUR_EQUIPE[f.equipe])
            col.setAlpha(int(60 + 40 * math.sin(self.t * 8)))
            g = QRadialGradient(cible.center(), f.w * c * 0.9)
            g.setColorAt(0.4, QColor(col.red(), col.green(), col.blue(), 0))
            g.setColorAt(0.75, col)
            g.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(cible.center(), f.w * c * 0.9, f.h * c * 0.8)

    def _projectiles(self, p, c, ox, oy):
        p.setPen(Qt.NoPen)
        for proj in self.jeu.combat.projectiles:
            x, y = _position_projectile(proj)
            centre = QPointF(ox + x * c, oy + y * c)
            g = QRadialGradient(centre, c * 3.2)
            g.setColorAt(0, QColor(255, 255, 220))
            g.setColorAt(0.35, QColor(255, 180, 40))
            g.setColorAt(0.7, QColor(255, 70, 20, 160))
            g.setColorAt(1, QColor(255, 40, 0, 0))
            p.setBrush(g)
            p.drawEllipse(centre, c * 3.2, c * 3.2)

    def _eclairs(self, p, c, ox, oy):
        for chemin, age in self.eclairs:
            if int(age * 30) % 3 == 2:
                continue
            alpha = 1 - age / 0.5
            path = QPainterPath(QPointF(ox + (chemin[0][0] + 0.5) * c, oy))
            for x, y in chemin[::2]:
                path.lineTo(ox + (x + 0.5) * c, oy + (y + 0.5) * c)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 230, 80, int(110 * alpha)), c * 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(QColor(255, 255, 255, int(255 * alpha)), max(1.5, c * 0.6), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)

    def _particules(self, p, c, ox, oy):
        p.setPen(Qt.NoPen)
        for q in self.particules:
            col = QColor(q.couleur)
            col.setAlpha(int(255 * max(0.0, min(1.0, q.vie / q.duree * 1.5))))
            p.setBrush(col)
            s = q.taille * c
            p.drawRect(QRectF(ox + q.x * c - s / 2, oy + q.y * c - s / 2, s, s))

    def _textes(self, p, c, ox, oy):
        f = _police(c * 2.6, True)
        p.setFont(f)
        for x, y, texte, vie in self.textes:
            alpha = int(255 * min(1.0, vie * 2))
            pos = QPointF(ox + x * c, oy + y * c)
            _texte_contour(p, pos, texte, QColor(255, 80, 70, alpha), QColor(40, 0, 0, alpha), c * 0.25)

    def _apercu_outil(self, p, c, ox, oy):
        jeu = self.jeu
        if self.selection:
            x0, y0, x1, y1 = _normaliser(self.selection)
            r = QRectF(ox + x0 * c, oy + y0 * c, (x1 - x0 + 1) * c, (y1 - y0 + 1) * c)
            p.setBrush(QColor(120, 200, 255, 40))
            p.setPen(QPen(QColor(200, 235, 255), 1.5, Qt.DashLine))
            p.drawRect(r)
        if self.souris is None:
            return
        x, y = self.souris
        if jeu.outil == "motif":
            motif = jeu.motif_courant()
            h, w = motif.shape
            x0, y0 = x - w // 2, y - h // 2
            col = QColor(COULEUR_EQUIPE[jeu.equipe_pinceau])
            col.setAlpha(150)
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            ys, xs = np.nonzero(motif)
            for yy, xx in zip(ys, xs):
                p.drawRect(QRectF(ox + (x0 + xx) * c, oy + (y0 + yy) * c, c - 1, c - 1))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.DotLine))
            p.drawRect(QRectF(ox + x0 * c, oy + y0 * c, w * c, h * c))
        elif jeu.outil in ("feu", "elec", "gomme"):
            col = QColor(255, 255, 255) if jeu.outil == "gomme" else COULEUR_EQUIPE[jeu.equipe_pinceau]
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(col, 1.5))
            p.drawRect(QRectF(ox + x * c, oy + y * c, c, c))

    # ------------------------------------------------------------ interface
    def _hud_combat(self, p, c, ox, oy, fw):
        combat = self.jeu.combat
        s, k = combat.salameche, combat.pikachu
        bw, bh = 38 * c, 12.5 * c
        self._boite_pv(p, s, QRectF(ox + 3 * c, oy + 2.5 * c, bw, bh), c, "A", "Z")
        self._boite_pv(p, k, QRectF(ox + fw - 3 * c - bw, oy + 2.5 * c, bw, bh), c, "P", "O")
        # Centre : génération + territoire
        feu, elec = self.jeu.life.population()
        total = max(1, feu + elec)
        lw = fw - 2 * (bw + 8 * c)
        if lw > 10 * c:
            x0 = ox + (fw - lw) / 2
            p.setFont(_police(c * 1.7, True))
            _texte_contour(p, QPointF(x0 + lw / 2, oy + 4.5 * c), f"GÉNÉRATION {self.jeu.life.generation}",
                           QColor("white"), QColor(0, 0, 0, 160), c * 0.2, centre=True)
            barre = QRectF(x0, oy + 6.2 * c, lw, 1.6 * c)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 120))
            p.drawRoundedRect(barre.adjusted(-2, -2, 2, 2), c, c)
            part = feu / total if feu + elec else 0.5
            p.setBrush(QColor(255, 110, 40))
            p.drawRoundedRect(QRectF(barre.x(), barre.y(), barre.width() * part, barre.height()), c * 0.8, c * 0.8)
            p.setBrush(QColor(255, 215, 30))
            p.drawRoundedRect(QRectF(barre.x() + barre.width() * part, barre.y(),
                                     barre.width() * (1 - part), barre.height()), c * 0.8, c * 0.8)
            p.setFont(_police(c * 1.3, True))
            _texte_contour(p, QPointF(x0 + lw / 2, oy + 10 * c),
                           f"TERRITOIRE   {round(100 * part)}% FEU · ÉLECTRIK {100 - round(100 * part)}%",
                           QColor(255, 255, 255, 220), QColor(0, 0, 0, 160), c * 0.15, centre=True)

    def _boite_pv(self, p, f, r, c, touche_atk, touche_spe):
        a = self.anim[f.nom]
        p.setPen(QPen(QColor(40, 44, 52), c * 0.45))
        p.setBrush(QColor(248, 248, 232, 238))
        p.drawRoundedRect(r, c * 1.4, c * 1.4)
        p.setPen(QPen(QColor(120, 130, 120), c * 0.15))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(c * 0.6, c * 0.6, -c * 0.6, -c * 0.6), c, c)

        m = 1.6 * c
        p.setFont(_police(c * 2.0, True))
        p.setPen(QColor(40, 40, 48))
        p.drawText(QPointF(r.x() + m, r.y() + 3.1 * c), f.nom)
        p.setFont(_police(c * 1.5, True))
        niveau = "N.5" if f.equipe == FEU else "N.6"
        p.drawText(QRectF(r.x(), r.y() + 1.1 * c, r.width() - m, 2.5 * c), Qt.AlignRight | Qt.AlignVCenter, niveau)
        # Badge de type
        type_txt = "FEU" if f.equipe == FEU else "ÉLECTRIK"
        p.setFont(_police(c * 1.05, True))
        largeur = p.fontMetrics().horizontalAdvance(type_txt) + c * 1.4
        badge = QRectF(r.x() + m, r.y() + 3.9 * c, largeur, 1.7 * c)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(238, 129, 48) if f.equipe == FEU else QColor(247, 208, 44))
        p.drawRoundedRect(badge, c * 0.8, c * 0.8)
        p.setPen(QColor("white") if f.equipe == FEU else QColor(60, 50, 0))
        p.drawText(badge, Qt.AlignCenter, type_txt)
        if f.ia:
            p.setPen(QColor(110, 110, 120))
            p.drawText(QRectF(badge.right() + c, badge.y(), 12 * c, badge.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, "IA")
        else:
            p.setPen(QColor(30, 140, 80))
            p.drawText(QRectF(badge.right() + c, badge.y(), 20 * c, badge.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, f"JOUEUR · {touche_atk} / {touche_spe}")

        # Barre de PV
        y = r.y() + 6.4 * c
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(60, 60, 60))
        etiquette = QRectF(r.x() + m, y, 3.2 * c, 1.7 * c)
        p.drawRoundedRect(etiquette, c * 0.5, c * 0.5)
        p.setPen(QColor(255, 210, 60))
        p.setFont(_police(c * 1.1, True))
        p.drawText(etiquette, Qt.AlignCenter, "PV")
        barre = QRectF(etiquette.right() - c * 0.3, y + 0.25 * c, r.right() - m - etiquette.right(), 1.2 * c)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(60, 60, 60))
        p.drawRoundedRect(barre.adjusted(-2, -2, 2, 2), c * 0.6, c * 0.6)
        ratio = max(0.0, a["pv"] / PV_MAX)
        couleur = QColor(88, 208, 96) if ratio > 0.5 else QColor(248, 200, 40) if ratio > 0.2 else QColor(240, 64, 48)
        if ratio <= 0.2 and int(self.t * 4) % 2:
            couleur = couleur.lighter(140)
        p.setBrush(couleur)
        p.drawRoundedRect(QRectF(barre.x(), barre.y(), barre.width() * ratio, barre.height()), c * 0.5, c * 0.5)
        p.setFont(_police(c * 1.4, True))
        p.setPen(QColor(40, 40, 48))
        p.drawText(QRectF(r.x(), y + 1.7 * c, r.width() - m, 2 * c), Qt.AlignRight | Qt.AlignVCenter,
                   f"{max(0, round(a['pv']))} / {PV_MAX}")

        # Jauge d'attaque spéciale
        y2 = y + 2.4 * c
        p.setFont(_police(c * 1.05, True))
        p.setPen(QColor(90, 90, 100))
        p.drawText(QPointF(r.x() + m, y2 + 1.2 * c), "SPÉ")
        jauge = QRectF(r.x() + m + 3.2 * c, y2 + 0.35 * c, barre.width() * 0.62, 0.9 * c)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(210, 210, 200))
        p.drawRoundedRect(jauge, c * 0.4, c * 0.4)
        p.setBrush(COULEUR_EQUIPE[f.equipe])
        p.drawRoundedRect(QRectF(jauge.x(), jauge.y(), jauge.width() * f.energie / 100, jauge.height()),
                          c * 0.4, c * 0.4)
        if f.energie >= 100 and int(self.t * 3) % 2 == 0:
            p.setPen(QColor(220, 60, 40) if f.equipe == FEU else QColor(170, 130, 0))
            p.drawText(QPointF(jauge.right() + c * 0.8, y2 + 1.2 * c), f"{f.nom_speciale.upper()} PRÊT !")

    def _hud_bac(self, p, c, ox, oy, fw):
        life = self.jeu.life
        feu, elec = life.population()
        r = QRectF(ox + 3 * c, oy + 2.5 * c, 52 * c, 6 * c)
        p.setPen(QPen(QColor(40, 44, 52), c * 0.4))
        p.setBrush(QColor(248, 248, 232, 230))
        p.drawRoundedRect(r, c, c)
        p.setFont(_police(c * 1.6, True))
        p.setPen(QColor(40, 40, 48))
        p.drawText(r.adjusted(c * 1.5, c * 0.6, 0, -c * 3), Qt.AlignLeft | Qt.AlignVCenter,
                   f"GÉNÉRATION {life.generation}")
        p.setFont(_police(c * 1.25, False))
        p.drawText(r.adjusted(c * 1.5, c * 3.0, 0, -c * 0.4), Qt.AlignLeft | Qt.AlignVCenter,
                   f"🔥 {feu}   ⚡ {elec}   ·   {life.regle}")

    def _boite_dialogue(self, p, c, ox, oy, fw, fh):
        jeu = self.jeu
        if self.message is not None:
            texte, t0 = self.message
            visible = texte[:int((self.t - t0) * 50)]
            fini = len(visible) >= len(texte)
        elif not jeu.en_marche:
            if jeu.mode == "combat" and jeu.combat.en_cours():
                visible = "Appuie sur ESPACE pour lancer le combat !"
            elif jeu.mode == "combat":
                visible = "Appuie sur R pour la revanche !"
            else:
                visible = "Dessine à la souris, puis ESPACE pour donner la vie."
            fini = True
        else:
            return
        r = QRectF(ox + 6 * c, oy + fh - 12.5 * c, fw - 12 * c, 9.5 * c)
        p.setPen(QPen(QColor(48, 56, 72), c * 0.6))
        p.setBrush(QColor(252, 252, 248, 240))
        p.drawRoundedRect(r, c * 1.2, c * 1.2)
        p.setPen(QPen(QColor(104, 160, 216), c * 0.35))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(c * 0.8, c * 0.8, -c * 0.8, -c * 0.8), c * 0.8, c * 0.8)
        p.setFont(_police(c * 2.5, True))
        p.setPen(QColor(48, 48, 56))
        p.drawText(r.adjusted(c * 3, c * 1.5, -c * 3, -c * 1.5), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
                   visible)
        if fini and int(self.t * 2.5) % 2 == 0:
            x, y = r.right() - c * 3.5, r.bottom() - c * 3
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(220, 60, 50))
            p.drawPolygon(QPolygonF([QPointF(x, y), QPointF(x + c * 1.6, y), QPointF(x + c * 0.8, y + c * 1.1)]))

    def _banniere(self, p, c, ox, oy, fw, fh):
        if not self.banniere:
            return
        texte, age, couleur = self.banniere
        echelle = min(1.0, age / 0.18) * (1 + 0.15 * max(0.0, 1 - age / 0.3))
        alpha = int(255 * min(1.0, (1.8 - age) / 0.4))
        p.save()
        p.translate(ox + fw / 2, oy + fh * 0.42)
        p.scale(echelle, echelle)
        p.setFont(_police(c * 9, True))
        col = QColor(couleur)
        col.setAlpha(alpha)
        _texte_contour(p, QPointF(0, c * 3), texte, col, QColor(20, 10, 10, alpha), c * 0.9, centre=True)
        p.restore()

    def _aide(self, p, c, ox, oy, fw, fh):
        p.fillRect(self.rect(), QColor(8, 10, 20, 200))
        lignes = [
            ("ESPACE", "Lancer / mettre en pause"),
            ("N  ou  →", "Avancer d'une génération"),
            ("←", "Remonter le temps d'une génération"),
            ("R", "Nouveau combat (revanche)"),
            ("A  /  Z", "Salamèche : Flammèche / Lance-Flammes"),
            ("P  /  O", "Pikachu : Éclair / Tonnerre"),
            ("T", "Changer d'arène"),
            ("Clic gauche", "Dessiner avec l'outil choisi"),
            ("Clic droit", "Gommer"),
            ("Molette  ou  E", "Tourner le motif"),
            ("⌘C / Suppr", "Copier / effacer la sélection"),
            ("M", "Couper / remettre le son"),
            ("H", "Afficher / cacher cette aide"),
        ]
        p.setFont(_police(c * 3.2, True))
        p.setPen(QColor(255, 215, 30))
        p.drawText(QRectF(ox, oy + 5 * c, fw, 5 * c), Qt.AlignCenter, "COMMANDES")
        y = oy + 14 * c
        for touche, desc in lignes:
            p.setFont(_police(c * 1.9, True))
            p.setPen(QColor(255, 140, 60))
            p.drawText(QRectF(ox, y, fw / 2 - 2 * c, 3 * c), Qt.AlignRight | Qt.AlignVCenter, touche)
            p.setFont(_police(c * 1.9, False))
            p.setPen(QColor(235, 235, 245))
            p.drawText(QRectF(ox + fw / 2 + 2 * c, y, fw / 2, 3 * c), Qt.AlignLeft | Qt.AlignVCenter, desc)
            y += 4.6 * c

    # --------------------------------------------------------------- souris
    def _case(self, pos):
        c, ox, oy = self.geometrie()
        x, y = int((pos.x() - ox) // c), int((pos.y() - oy) // c)
        return (x, y) if self.jeu.life.dans_grille(x, y) else None

    def mousePressEvent(self, e):
        case = self._case(e.pos())
        if case is None:
            return
        jeu = self.jeu
        self.setFocus()
        if jeu.outil == "selection" and e.button() == Qt.LeftButton:
            self.selection = [case[0], case[1], case[0], case[1]]
            self._trace = "selection"
            self.update()
            return
        jeu.debut_edition()
        if e.button() == Qt.RightButton or jeu.outil == "gomme":
            self._trace = "gomme"
        elif jeu.outil == "motif":
            motif = jeu.motif_courant()
            h, w = motif.shape
            jeu.life.tamponner(motif, case[0] - w // 2, case[1] - h // 2, jeu.equipe_pinceau)
            jeu.sons.jouer("clic")
            self._trace = None
            self.sale()
            return
        else:
            self._trace = "pinceau"
        self._derniere_case = case
        self._peindre(case)

    def mouseMoveEvent(self, e):
        case = self._case(e.pos())
        self.souris = case
        if case is not None and self._trace == "selection":
            self.selection[2], self.selection[3] = case
        elif case is not None and self._trace in ("pinceau", "gomme"):
            for intermediaire in _ligne(self._derniere_case, case):
                self._peindre(intermediaire)
            self._derniere_case = case
        self.update()

    def mouseReleaseEvent(self, e):
        self._trace = None

    def leaveEvent(self, e):
        self.souris = None
        self.update()

    def wheelEvent(self, e):
        if self.jeu.outil == "motif":
            self.jeu.tourner_motif(1 if e.angleDelta().y() > 0 else -1)
            self.update()

    def _peindre(self, case):
        life = self.jeu.life
        if self._trace == "gomme":
            life.effacer(*case)
        else:
            life.poser(case[0], case[1], self.jeu.equipe_pinceau)
        self.sale()


# ------------------------------------------------------------------ outils
def _couleurs_equipe(equipe):
    return [QColor(*map(int, rgb)) for rgb in PALETTE[equipe]]


def _position_projectile(p):
    frac = min(1.0, p["t"] / p["duree"])
    (x0, y0), (x1, y1) = p["depart"], p["arrivee"]
    return x0 + (x1 - x0) * frac, y0 + (y1 - y0) * frac - math.sin(math.pi * frac) * 28


_POLICES = {}


def _police(taille, gras):
    cle = (int(taille), gras)
    if cle not in _POLICES:
        f = QFont("Avenir Next")
        f.setPixelSize(max(6, int(taille)))
        f.setWeight(QFont.Black if gras else QFont.DemiBold)
        _POLICES[cle] = f
    return _POLICES[cle]


def _texte_contour(p, pos, texte, couleur, contour, epaisseur, centre=False):
    if centre:
        pos = QPointF(pos.x() - p.fontMetrics().horizontalAdvance(texte) / 2, pos.y())
    chemin = QPainterPath()
    chemin.addText(pos, p.font(), texte)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(contour, epaisseur * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(chemin)
    p.setPen(Qt.NoPen)
    p.setBrush(couleur)
    p.drawPath(chemin)


def _normaliser(sel):
    x0, y0, x1, y1 = sel
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _ligne(a, b):
    """Cases entre a et b (pour un trait continu même si la souris va vite)."""
    (x0, y0), (x1, y1) = a, b
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    return [(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)) for i in range(n + 1)]
