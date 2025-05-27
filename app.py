"""Entry point for the SDI to NDI converter application"""
import sys
import os

# Ensure we can find our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication
from src.main import MainWindow
from src.ndi_input import ndi_lib # Assuming ndi_lib is loaded here

def main():
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        exit_code = app.exec()
        
        # Ensure NDI library is destroyed on application exit
        if ndi_lib:
            ndi_lib.NDIlib_destroy()
        
        return exit_code
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    sys.exit(main())
