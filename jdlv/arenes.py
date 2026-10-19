# -*- coding: utf-8 -*-
"""
Décors des arènes, inspirés de lieux du monde Pokémon. Comme dans la
première version, le décor change à chaque nouvelle partie.
"""
import math
import random

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient


def _ciel(p, w, h, haut, bas):
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(haut))
    g.setColorAt(1, QColor(bas))
    p.fillRect(0, 0, w, h, g)


def _collines(p, w, sol, amplitude, couleur, graine, periode=1.0):
    rnd = random.Random(graine)
    phase = rnd.random() * 6
    chemin = QPainterPath(QPointF(0, sol))
    for i in range(0, w + 20, 20):
        y = sol - amplitude * (0.6 + 0.4 * math.sin(i / (90 * periode) + phase)
                               * math.sin(i / (37 * periode) + phase * 2))
        chemin.lineTo(i, y)
    chemin.lineTo(w, sol + 2)
    chemin.lineTo(0, sol + 2)
    p.fillPath(chemin, QColor(couleur))


def _sol(p, w, h, sol, haut, bas):
    g = QLinearGradient(0, sol, 0, h)
    g.setColorAt(0, QColor(haut))
    g.setColorAt(1, QColor(bas))
    p.fillRect(QRectF(0, sol, w, h - sol), g)


def route_1(p, w, h, sol, c):
    _ciel(p, w, h, "#5fb8f5", "#cdeeff")
    rnd = random.Random(1)
    p.setPen(Qt.NoPen)
    for _ in range(6):  # nuages
        x, y = rnd.uniform(0, w), rnd.uniform(0, sol * 0.45)
        p.setBrush(QColor(255, 255, 255, 200))
        for k in range(4):
            p.drawEllipse(QPointF(x + k * c * 2.2, y + (k % 2) * c * 0.8), c * 2.6, c * 1.6)
    _collines(p, w, sol, c * 9, "#7cc96a", 3)
    _collines(p, w, sol, c * 5, "#5aae4c", 5)
    _sol(p, w, h, sol, "#62b24f", "#3c7f33")
    for _ in range(90):  # herbes hautes et fleurs
        x, y = rnd.uniform(0, w), rnd.uniform(sol + c, h)
        p.setBrush(QColor(rnd.choice(["#ffffff", "#ffd84d", "#ff6f91", "#2f6d2a"])))
        p.drawRect(QRectF(x, y, c * 0.5, c * 0.5))


def foret_de_jade(p, w, h, sol, c):
    _ciel(p, w, h, "#0f2a1e", "#3f7a52")
    rnd = random.Random(2)
    p.setPen(Qt.NoPen)
    for couche, teinte in enumerate(["#1d4a32", "#163c28", "#0f2c1d"]):
        p.setBrush(QColor(teinte))
        x = -rnd.uniform(0, c * 6)
        while x < w:
            largeur = rnd.uniform(c * 5, c * 9)
            hauteur = rnd.uniform(c * 14, c * 26) * (1 - couche * 0.15)
            base = sol + couche * c * 2
            p.drawPolygon(QPolygonF([QPointF(x, base), QPointF(x + largeur / 2, base - hauteur),
                                     QPointF(x + largeur, base)]))
            x += largeur * 0.7
    _sol(p, w, h, sol, "#24502f", "#122a19")
    for _ in range(40):  # lucioles
        p.setBrush(QColor(200, 255, 140, rnd.randint(60, 160)))
        p.drawEllipse(QPointF(rnd.uniform(0, w), rnd.uniform(0, sol)), c * 0.25, c * 0.25)


def mont_selenite(p, w, h, sol, c):
    _ciel(p, w, h, "#120d24", "#2d2352")
    rnd = random.Random(3)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0b0818"))
    x = 0
    while x < w:  # stalactites
        largeur = rnd.uniform(c * 2, c * 5)
        p.drawPolygon(QPolygonF([QPointF(x, 0), QPointF(x + largeur / 2, rnd.uniform(c * 3, c * 12)),
                                 QPointF(x + largeur, 0)]))
        x += largeur
    _collines(p, w, sol, c * 7, "#241c40", 8, 0.6)
    _sol(p, w, h, sol, "#3a3058", "#1b1530")
    for _ in range(22):  # pierres lune scintillantes
        cx, cy = rnd.uniform(0, w), rnd.uniform(sol - c * 4, h)
        halo = QRadialGradient(QPointF(cx, cy), c * 2.5)
        halo.setColorAt(0, QColor(150, 200, 255, 120))
        halo.setColorAt(1, QColor(150, 200, 255, 0))
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), c * 2.5, c * 2.5)
        p.setBrush(QColor("#bfe3ff"))
        r = c * rnd.uniform(0.4, 0.9)
        p.drawPolygon(QPolygonF([QPointF(cx, cy - r * 2), QPointF(cx + r, cy),
                                 QPointF(cx, cy + r * 0.6), QPointF(cx - r, cy)]))


def centrale(p, w, h, sol, c):
    _ciel(p, w, h, "#121826", "#33405c")
    rnd = random.Random(4)
    p.setPen(QPen(QColor(255, 230, 90, 60), max(1, c * 0.25)))
    for _ in range(5):  # arcs électriques lointains
        x, y = rnd.uniform(0, w), 0
        chemin = QPainterPath(QPointF(x, y))
        while y < sol * 0.7:
            x += rnd.uniform(-c * 2, c * 2)
            y += rnd.uniform(c, c * 3)
            chemin.lineTo(x, y)
        p.drawPath(chemin)
    p.setPen(QPen(QColor("#0c111c"), max(2, c * 0.5)))
    for i in range(5):  # pylônes
        x = (i + 0.5) * w / 5
        p.drawLine(QPointF(x, sol), QPointF(x, sol - c * 22))
        p.drawLine(QPointF(x - c * 4, sol - c * 18), QPointF(x + c * 4, sol - c * 18))
        p.drawLine(QPointF(x - c * 3, sol - c * 13), QPointF(x + c * 3, sol - c * 13))
    p.setPen(QPen(QColor(20, 26, 40), max(1, c * 0.15)))
    for i in range(4):
        x0, x1 = (i + 0.5) * w / 5, (i + 1.5) * w / 5
        chemin = QPainterPath(QPointF(x0, sol - c * 18))
        chemin.quadTo(QPointF((x0 + x1) / 2, sol - c * 13), QPointF(x1, sol - c * 18))
        p.drawPath(chemin)
    p.setPen(Qt.NoPen)
    _sol(p, w, h, sol, "#454b58", "#23262e")
    bande = c * 1.5
    for i in range(int(w / bande) + 2):  # bande jaune et noire
        p.setBrush(QColor("#f2c200") if i % 2 else QColor("#15171c"))
        p.drawPolygon(QPolygonF([QPointF(i * bande, sol), QPointF((i + 1) * bande, sol),
                                 QPointF((i + 0.5) * bande, sol + bande),
                                 QPointF((i - 0.5) * bande, sol + bande)]))


def cramois_ile(p, w, h, sol, c):
    _ciel(p, w, h, "#1f0707", "#8a2c10")
    rnd = random.Random(5)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#2b0f0b"))
    p.drawPolygon(QPolygonF([QPointF(w * 0.25, sol), QPointF(w * 0.45, sol - c * 30),
                             QPointF(w * 0.55, sol - c * 30), QPointF(w * 0.78, sol)]))
    lave = QRadialGradient(QPointF(w * 0.5, sol - c * 30), c * 14)
    lave.setColorAt(0, QColor(255, 160, 40, 220))
    lave.setColorAt(1, QColor(255, 60, 0, 0))
    p.setBrush(lave)
    p.drawEllipse(QPointF(w * 0.5, sol - c * 30), c * 14, c * 14)
    _sol(p, w, h, sol, "#3b1a12", "#160806")
    p.setPen(QPen(QColor(255, 110, 20, 170), max(1, c * 0.35)))
    for _ in range(14):  # fissures de lave
        x, y = rnd.uniform(0, w), rnd.uniform(sol + c, h)
        chemin = QPainterPath(QPointF(x, y))
        for _ in range(4):
            x += rnd.uniform(c, c * 4)
            y += rnd.uniform(-c, c)
            chemin.lineTo(x, y)
        p.drawPath(chemin)
    p.setPen(Qt.NoPen)
    for _ in range(70):  # braises
        p.setBrush(QColor(255, rnd.randint(90, 200), 40, rnd.randint(80, 200)))
        p.drawEllipse(QPointF(rnd.uniform(0, w), rnd.uniform(0, sol)), c * 0.2, c * 0.2)


def plateau_indigo(p, w, h, sol, c):
    _ciel(p, w, h, "#070b24", "#2b3474")
    rnd = random.Random(6)
    p.setPen(Qt.NoPen)
    for _ in range(160):
        p.setBrush(QColor(255, 255, 255, rnd.randint(60, 230)))
        r = rnd.uniform(0.08, 0.22) * c
        p.drawEllipse(QPointF(rnd.uniform(0, w), rnd.uniform(0, sol)), r, r)
    lune = QRadialGradient(QPointF(w * 0.82, sol * 0.25), c * 7)
    lune.setColorAt(0, QColor(255, 250, 220, 255))
    lune.setColorAt(0.5, QColor(255, 250, 220, 255))
    lune.setColorAt(0.55, QColor(255, 250, 220, 60))
    lune.setColorAt(1, QColor(255, 250, 220, 0))
    p.setBrush(lune)
    p.drawEllipse(QPointF(w * 0.82, sol * 0.25), c * 7, c * 7)
    _collines(p, w, sol, c * 4, "#1a1f4a", 9, 1.6)
    _sol(p, w, h, sol, "#5a6194", "#2c3160")
    p.setPen(QPen(QColor(255, 255, 255, 90), max(1, c * 0.3)))
    p.setBrush(Qt.NoBrush)  # terrain de stade
    p.drawEllipse(QPointF(w / 2, sol + (h - sol) * 0.45), w * 0.42, (h - sol) * 0.32)
    p.drawLine(QPointF(w / 2, sol + (h - sol) * 0.13), QPointF(w / 2, sol + (h - sol) * 0.77))
    p.drawEllipse(QPointF(w / 2, sol + (h - sol) * 0.45), c * 4, c * 2)


ARENES = {
    "Route 1": route_1,
    "Forêt de Jade": foret_de_jade,
    "Mont Sélénite": mont_selenite,
    "Centrale": centrale,
    "Cramois'Île": cramois_ile,
    "Plateau Indigo": plateau_indigo,
}


def dessiner_arene(nom, w, h, sol, c):
    pix = QPixmap(max(1, w), max(1, h))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    ARENES[nom](p, w, h, sol, c)
    p.fillRect(0, 0, w, h, QColor(0, 0, 0, 70))  # voile pour faire ressortir les cellules
    p.end()
    return pix
