# connection_dialog.py
# This file defines a QDialog subclass for users to input connection details (IP and Port).
# It is used by the main application when a user chooses to connect to a host.

import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, # QPushButton not directly used, QDialogButtonBox is
    QApplication, QDialogButtonBox
)
from PySide6.QtCore import Qt # For Qt.WindowType (though not explicitly used here, good for reference)

class ConnectionDialog(QDialog):
    """
    A custom dialog window that prompts the user to enter the IP address
    and port number of the host they wish to connect to.
    Provides default values and basic validation for the port.
    """
    def __init__(self, parent=None):
        """
        Initializes the ConnectionDialog.
        Sets up the UI elements including labels, line edits for IP and port,
        and OK/Cancel buttons.

        Args:
            parent (QWidget, optional): The parent widget of this dialog. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Connect to Host")

        # Main vertical layout for the dialog
        layout = QVBoxLayout(self)
        
        # Layout for form elements (labels and line edits)
        form_layout = QVBoxLayout() 

        # IP Address Input Section
        ip_layout = QHBoxLayout() # Horizontal layout for label and line edit
        self.ip_label = QLabel("Host IP Address:")
        self.ip_edit = QLineEdit("127.0.0.1") # Default IP address (localhost)
        ip_layout.addWidget(self.ip_label)
        ip_layout.addWidget(self.ip_edit)
        form_layout.addLayout(ip_layout) # Add IP section to the form layout

        # Port Input Section
        port_layout = QHBoxLayout() # Horizontal layout for label and line edit
        self.port_label = QLabel("Host Port:")
        self.port_edit = QLineEdit("54321") # Default port number
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_edit)
        form_layout.addLayout(port_layout) # Add Port section to the form layout
        
        layout.addLayout(form_layout) # Add the form layout to the main dialog layout

        # Standard Dialog Buttons (OK, Cancel)
        # QDialogButtonBox provides standard buttons and connects their signals.
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept) # Connect OK button to QDialog.accept()
        self.button_box.rejected.connect(self.reject) # Connect Cancel button to QDialog.reject()
        layout.addWidget(self.button_box) # Add buttons to the main dialog layout

        self.setLayout(layout) # Set the main layout for the dialog

    def get_ip_address(self):
        """
        Retrieves the text entered in the IP address line edit.

        Returns:
            str: The entered IP address, stripped of leading/trailing whitespace.
        """
        return self.ip_edit.text().strip()

    def get_port(self):
        """
        Retrieves the text entered in the port line edit and attempts to convert it to an integer.

        Returns:
            int | None: The entered port as an integer if valid, otherwise None.
        """
        try:
            # Attempt to convert the port text to an integer.
            return int(self.port_edit.text().strip())
        except ValueError:
            # If conversion fails (e.g., non-numeric input), return None.
            return None

    @staticmethod
    def get_details(parent=None):
        """
        A static convenience method to create, display, and execute the dialog.
        This method encapsulates the dialog's creation and result retrieval.

        Args:
            parent (QWidget, optional): The parent widget for the dialog. Defaults to None.

        Returns:
            tuple: A tuple containing (ip_address, port) if the user clicked OK
                   and the port is valid (1-65535). Otherwise, returns (None, None).
        """
        dialog = ConnectionDialog(parent)
        # dialog.exec() shows the dialog modally and waits for user interaction.
        # It returns QDialog.Accepted if OK is clicked, QDialog.Rejected if Cancel is clicked.
        if dialog.exec() == QDialog.Accepted: 
            ip = dialog.get_ip_address()
            port = dialog.get_port()
            # Basic validation: ensure IP is not empty and port is a valid number.
            if ip and port is not None:
                # Port number validation (standard range for TCP/UDP ports).
                if 0 < port < 65536:
                    return ip, port
                # else: QMessageBox.warning(dialog, "Invalid Port", "Port number must be between 1 and 65535.") # Optional: more direct feedback
        return None, None # Return None if dialog was cancelled or input was invalid.

if __name__ == '__main__':
    # This block allows testing the ConnectionDialog independently.
    # It demonstrates how to use the static get_details method.
    app = QApplication(sys.argv) # A QApplication instance is required to show widgets.
    
    print("Showing ConnectionDialog via static get_details()...")
    ip_address, port_number = ConnectionDialog.get_details()
    
    if ip_address and port_number:
        print(f"Connection Details Entered: IP = {ip_address}, Port = {port_number}")
    else:
        print("Dialog was cancelled or the input was invalid.")

    # Example of showing an instance directly (less common for this type of dialog)
    # print("\nShowing ConnectionDialog as an instance (for UI check)...")
    # dialog_instance = ConnectionDialog()
    # result = dialog_instance.exec() # or .open() for non-modal, or .show()
    # if result == QDialog.Accepted:
    #     print(f"Instance Details: IP = {dialog_instance.get_ip_address()}, Port = {dialog_instance.get_port()}")
    # else:
    #     print("Instance dialog cancelled.")
    
    # sys.exit(app.exec()) # Not strictly necessary if only using modal dialog.exec() for testing.
    # For non-modal .show(), app.exec() would be needed to keep it alive.
    print("Exiting example script.")
