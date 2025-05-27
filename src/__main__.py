"""Entry point for the SDI to NDI converter application"""
import sys
from PyQt6.QtWidgets import QApplication
try:
    from .main import MainWindow
except ImportError:
    from main import MainWindow

def main():
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
