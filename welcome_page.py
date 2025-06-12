from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog
from PySide6.QtCore import Signal

class WelcomePage(QWidget):
    """
    Welcome Page for the Aether Editor.
    Allows users to open files, folders, or join a collaborative session.
    """
    join_session_requested = Signal()
    open_file_requested = Signal(str)  # Signal to emit file path
    open_folder_requested = Signal(str) # Signal to emit folder path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome")
        layout = QVBoxLayout(self)

        title = QLabel("Welcome to Aether Editor")
        title.setStyleSheet("font-size: 18pt; font-weight: bold;") # Basic styling
        layout.addWidget(title)

        self.open_file_button = QPushButton("Open File...")
        self.open_file_button.clicked.connect(self._on_open_file)
        layout.addWidget(self.open_file_button)

        self.open_folder_button = QPushButton("Open Folder...")
        self.open_folder_button.clicked.connect(self._on_open_folder)
        layout.addWidget(self.open_folder_button)

        self.join_session_button = QPushButton("Join Session...")
        self.join_session_button.clicked.connect(self.join_session_requested.emit)
        layout.addWidget(self.join_session_button)

        self.setFixedSize(400, 300) # Give it a reasonable default size

    def _on_open_file(self):
        # Use QFileDialog to get a file path
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File")
        if file_path:
            self.open_file_requested.emit(file_path)

    def _on_open_folder(self):
        # Use QFileDialog to get a directory path
        folder_path = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder_path:
            self.open_folder_requested.emit(folder_path)
