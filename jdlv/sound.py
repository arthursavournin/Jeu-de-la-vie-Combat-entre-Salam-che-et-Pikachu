# -*- coding: utf-8 -*-
"""
Bruitages 8 bits synthétisés à la volée avec numpy (aucun fichier à fournir).
Si QtMultimedia n'est pas disponible, le jeu reste simplement muet.
"""
import os
import tempfile
import time
import wave

import numpy as np

try:
    from PyQt5.QtCore import QUrl
    from PyQt5.QtMultimedia import QSoundEffect
except ImportError:  # pragma: no cover
    QSoundEffect = None

TAUX = 22050


def _t(duree):
    return np.linspace(0, duree, int(TAUX * duree), endpoint=False)


def _carre(freq, t):
    return np.sign(np.sin(2 * np.pi * np.cumsum(freq) / TAUX + 1e-9)) if np.ndim(freq) \
        else np.sign(np.sin(2 * np.pi * freq * t))


def _enveloppe(t, attaque=0.005, chute=4.0):
    env = np.exp(-chute * t / t[-1])
    n = max(1, int(attaque * TAUX))
    env[:n] *= np.linspace(0, 1, n)
    return env


def _bruit(t, rng):
    return rng.uniform(-1, 1, len(t))


def _passe_bas(x, k):
    noyau = np.ones(k) / k
    return np.convolve(x, noyau, mode="same")


def _synthes():
    rng = np.random.default_rng(7)
    sons = {}

    t = _t(0.28)  # Flammèche : souffle grave qui monte
    sons["tir_feu"] = _passe_bas(_bruit(t, rng), 6) * _enveloppe(t, 0.02, 3) \
        + 0.3 * _carre(np.linspace(180, 420, len(t)), t) * _enveloppe(t, 0.01, 6)

    t = _t(0.22)  # Éclair : arpège carré nerveux
    f = np.repeat([660, 880, 1320, 1760], len(t) // 4 + 1)[:len(t)]
    sons["tir_elec"] = 0.6 * _carre(f.astype(float), t) * _enveloppe(t, 0.002, 3)

    t = _t(0.12)  # Coup encaissé
    sons["touche"] = (_passe_bas(_bruit(t, rng), 3) * 0.7
                      + 0.5 * _carre(np.linspace(220, 80, len(t)), t)) * _enveloppe(t, 0.001, 5)

    t = _t(0.9)  # Tonnerre
    sons["tonnerre"] = (_bruit(t, rng) * _enveloppe(t, 0.001, 5)
                        + _passe_bas(_bruit(t, rng), 30) * 2.5 * _enveloppe(t, 0.05, 2))

    t = _t(0.7)  # Lance-Flammes : rugissement
    sons["lance_flammes"] = _passe_bas(_bruit(t, rng), 10) * 1.6 * _enveloppe(t, 0.08, 2.5) \
        + 0.25 * _carre(np.linspace(90, 260, len(t)), t) * _enveloppe(t, 0.05, 3)

    t = _t(0.5)  # Impact de boule de feu
    sons["impact"] = _passe_bas(_bruit(t, rng), 18) * 2.2 * _enveloppe(t, 0.001, 5)

    t = _t(1.4)  # K.O. : explosion + note qui tombe
    sons["ko"] = _passe_bas(_bruit(t, rng), 25) * 2.5 * _enveloppe(t, 0.001, 3) \
        + 0.35 * _carre(np.linspace(520, 60, len(t)), t) * _enveloppe(t, 0.01, 2)

    # Fanfare de victoire façon Pokémon
    notes = [(784, .12), (784, .12), (784, .12), (784, .36), (622, .36),
             (698, .36), (784, .2), (698, .1), (784, .6)]
    morceaux = []
    for freq, d in notes:
        t = _t(d)
        morceaux.append(0.45 * _carre(freq, t) * _enveloppe(t, 0.005, 1.5))
    sons["victoire"] = np.concatenate(morceaux)

    t = _t(0.05)
    sons["clic"] = 0.3 * _carre(1200, t) * _enveloppe(t, 0.001, 8)

    t = _t(0.6)  # Début du combat : petit jingle montant
    f = np.repeat([392, 523, 659, 784], len(t) // 4 + 1)[:len(t)]
    sons["debut"] = 0.4 * _carre(f.astype(float), t) * _enveloppe(t, 0.005, 1.2)
    return sons


class Sons:
    def __init__(self):
        self.actif = True
        self.effets = {}
        self._dernier = {}
        if QSoundEffect is None:
            return
        dossier = os.path.join(tempfile.gettempdir(), "jdlv_sons_v2")
        os.makedirs(dossier, exist_ok=True)
        for nom, signal in _synthes().items():
            chemin = os.path.join(dossier, nom + ".wav")
            if not os.path.exists(chemin):
                pcm = (np.clip(signal, -1, 1) * 0.5 * 32767).astype(np.int16)
                with wave.open(chemin, "wb") as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(TAUX)
                    f.writeframes(pcm.tobytes())
            effet = QSoundEffect()
            effet.setSource(QUrl.fromLocalFile(chemin))
            effet.setVolume(0.55)
            self.effets[nom] = effet

    def jouer(self, nom, intervalle=0.0):
        if not self.actif or nom not in self.effets:
            return
        maintenant = time.monotonic()
        if maintenant - self._dernier.get(nom, 0) < intervalle:
            return
        self._dernier[nom] = maintenant
        self.effets[nom].play()
