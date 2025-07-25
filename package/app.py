"""
JKam Application Entry Point

Main entry point for the JKam GUI application for ultracold atomic imaging.
Initializes PyQt5 application, sets up window icon, and launches main window.
"""

import sys
import ctypes
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from jkam_window import JKamWindow


def run():
    """
    Main entry point for the JKam application.
    
    Initializes PyQt5 application, sets up window icon, and launches
    the main JKam window interface.
    """
    app = QApplication(sys.argv)

    # Setup windows icon for jkam
    app.setWindowIcon(QIcon('package/imagedata/favicon.ico'))
    myappid = u'jkam_app'  # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    ex = JKamWindow()
    app.exec_()
