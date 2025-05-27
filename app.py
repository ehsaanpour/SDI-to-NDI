"""Entry point for the SDI to NDI converter application"""
import sys
import os
import comtypes.client

# Ensure we can find our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication
from src.main import MainWindow
from src.ndi_input import ndi_lib # Assuming ndi_lib is loaded here
from src.config import DECKLINK_SDK_PATH # Import DECKLINK_SDK_PATH

# Generate COM interfaces for DeckLink
try:
    comtypes.client.GetModule(os.path.join(DECKLINK_SDK_PATH, "Win", "DeckLinkAPI.tlb"))
    print("DeckLinkAPI type library loaded/generated successfully.")
except Exception as e:
    print(f"Error loading DeckLinkAPI type library: {e}")
    # Do not sys.exit(1) here, let the application continue

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
