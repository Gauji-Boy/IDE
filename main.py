# main.py
# This is the main entry point for the Simple Collaborative Editor application.
# Its primary responsibilities are to:
# 1. Initialize the QApplication, which manages GUI application-wide resources.
# 2. Instantiate the MainWindow, which is the main UI of the application.
# 3. Show the MainWindow.
# 4. Start the Qt event loop, which processes events (like user input, signals, etc.).

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt # For Qt attributes, e.g., for High DPI scaling

# Import the MainWindow class from main_window.py.
# It's assumed that main_window.py is in the same directory or accessible
# via Python's import system (e.g., in PYTHONPATH).
from main_window import MainWindow

def main():
    """
    Main function to initialize and run the Code-Sync IDE (Simple Collab) application.
    - Creates the QApplication instance.
    - Optionally sets attributes for High DPI scaling.
    - Creates and displays the main application window (MainWindow).
    - Enters the Qt event loop.
    """
    # Every PySide6 application must create a QApplication instance.
    # sys.argv allows passing command-line arguments to the application.
    app = QApplication(sys.argv)

    # --- Optional: High DPI Scaling Attributes ---
    # These attributes can help improve how the application looks on High DPI displays.
    # Their effectiveness can vary depending on the OS, Qt version, and environment.
    # Uncomment and experiment if you encounter scaling issues.
    #
    # Enables automatic scaling based on the monitor's DPI.
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    #
    # Enables the use of high-resolution pixmaps (images/icons).
    # QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    #
    # Specifies how scale factors should be rounded. PassThrough avoids rounding.
    # QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Create an instance of our main application window.
    main_win = MainWindow()
    main_win.show() # Display the main window.

    # Start the Qt event loop.
    # sys.exit() ensures that the application exits cleanly and returns an appropriate exit code.
    # app.exec() enters the main event loop and waits until exit() is called.
    sys.exit(app.exec())

if __name__ == '__main__':
    # This standard Python construct ensures that main() is called only when
    # the script is executed directly (not when it's imported as a module).
    main()
