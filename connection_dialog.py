from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QDialogButtonBox
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIntValidator

class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Host / Start Hosting")
        self.setModal(True)

        self.ip_address = "127.0.0.1"
        self.port = 12345

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # IP Address
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("IP Address:"))
        self.ip_input = QLineEdit(self)
        self.ip_input.setText(self.ip_address)
        ip_layout.addWidget(self.ip_input)
        main_layout.addLayout(ip_layout)

        # Port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_input = QLineEdit(self)
        self.port_input.setText(str(self.port))
        self.port_input.setValidator(QIntValidator(1024, 65535, self)) # Valid ports
        port_layout.addWidget(self.port_input)
        main_layout.addLayout(port_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def get_details(self):
        # Static method to show dialog and return results
        dialog = ConnectionDialog(self.parent()) # Pass parent for proper centering
        if dialog.exec() == QDialog.Accepted:
            ip = dialog.ip_input.text()
            port = int(dialog.port_input.text())
            return ip, port
        return None, None