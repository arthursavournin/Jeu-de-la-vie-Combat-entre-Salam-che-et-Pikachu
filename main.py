# -*- coding: utf-8 -*-
"""Lance le jeu : python3 main.py"""
import sys

from PyQt5.QtWidgets import QApplication

from jdlv.window import Fenetre

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = Fenetre()
    fenetre.show()
    sys.exit(app.exec_())
