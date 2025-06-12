import sys
from PySide6.QtWidgets import QApplication
from welcome_page import WelcomePage
from main_window import MainWindow
# AppController and __main__ block follow

class AppController:
    def __init__(self, app):
        self.app = app
        self.main_window = None  # Initialize as None, create when needed
        self.welcome_screen = WelcomePage()

        # Connect signals from WelcomePage
        self.welcome_screen.join_session_requested.connect(self.launch_for_join_session)
        self.welcome_screen.open_file_requested.connect(self.launch_main_window_with_path) # Connect to a generic path handler
        self.welcome_screen.open_folder_requested.connect(self.launch_main_window_with_path) # Connect to a generic path handler


    def start(self):
        self.welcome_screen.show()

    def _ensure_main_window(self):
        if self.main_window is None:
            self.main_window = MainWindow() # Create MainWindow instance

    def launch_for_join_session(self):
        print("AppController: launch_for_join_session triggered")
        self._ensure_main_window()
        self.main_window.join_session_from_welcome_page() # Method created in MainWindow (Step 3)
        self.main_window.show()
        self.welcome_screen.close()
        print("AppController: Join Session - MainWindow configured and shown, WelcomeScreen closed.")


    def launch_main_window_with_path(self, path):
        print(f"AppController: launch_main_window_with_path triggered with path: {path}")
        self._ensure_main_window()
        self.main_window.initialize_project(path) # Method created in MainWindow (Step 3)
        self.main_window.show()
        self.welcome_screen.close()
        print(f"AppController: Path '{path}' - MainWindow initialized and shown, WelcomeScreen closed.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = AppController(app)
    controller.start()
    sys.exit(app.exec())