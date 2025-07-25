#!/usr/bin/env python3
"""
Dark Mode Demo for JKam GUI

This script demonstrates the dark mode functionality added to the JKam GUI.
Run this script to see the dark mode in action.
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
import ctypes
import pyqtgraph as pg

# Import the main window
from jkam_window import JKamWindow

def main():
    """
    Main entry point for the JKam application with dark mode demo.
    """
    app = QApplication(sys.argv)

    # Code to setup windows icon for jkam
    app.setWindowIcon(QIcon('jkamicon.ico'))
    myappid = u'jkam_app' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Create the main window
    ex = JKamWindow()
    ex.show()
    
    # Set dark mode by default hehe
    ex.set_theme(True)
    
    app.exec_()

if __name__ == '__main__':
    main()
    sys.exit() 