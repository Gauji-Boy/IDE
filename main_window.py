# main_window.py
# This file defines the MainWindow class, which is the main user interface
# for the Simple Collaborative Editor. It integrates the text editor,
# menu actions, status bar, and the NetworkManager for handling
# collaborative sessions (both hosting and joining).

import sys
import black # For code formatting
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QApplication, QStatusBar
)
from PySide6.QtGui import QAction, QKeySequence, QTextCursor # QTextCursor for formatting
from PySide6.QtCore import Slot, Qt, QObject, Signal # QObject, Signal for MockNetworkManager
from PySide6.QtNetwork import QTcpSocket # For type hinting in MockNetworkManager

# Import custom modules
from network_manager import NetworkManager
from connection_dialog import ConnectionDialog
from code_editor import CodeEditor # Use the new CodeEditor
from python_highlighter import PythonHighlighter # Use the new PythonHighlighter

class MainWindow(QMainWindow):
    """
    The main window for the collaborative editor application.
    This class is responsible for:
    - Setting up the main UI elements (CodeEditor, menus, status bar).
    - Creating and managing an instance of NetworkManager for network operations.
    - Handling user interactions through menu actions.
    - Responding to network events via signals from NetworkManager.
    - Managing the editor's state (e.g., read-only for clients, sending local changes).
    """
    DEFAULT_PORT = 54321 # Default port for hosting and connecting

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Code-Sync IDE (Simple Collab)")
        self.setGeometry(100, 100, 800, 600)

        # --- Central Code Editor ---
        self.editor = CodeEditor() # Use the new CodeEditor
        self.setCentralWidget(self.editor)

        # Syntax Highlighter (attached to the CodeEditor's document)
        self.highlighter = PythonHighlighter(self.editor.document())

        # --- Network Manager ---
        self.network_manager = NetworkManager(self)

        # --- Loop Prevention Flag ---
        self._is_updating_from_network = False

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Start or connect to a session.")

        # --- UI Setup ---
        self._setup_menus()
        self._connect_network_signals()
        
        # Connect the editor's textChanged signal to send updates when user types.
        # CodeEditor itself handles its internal textChanged for linting/completion.
        # This connection is purely for MainWindow's network sync logic.
        self.editor.textChanged.connect(self._on_editor_text_changed_for_network)

    def _setup_menus(self):
        self.menu_bar = self.menuBar()
        session_menu = self.menu_bar.addMenu("&Session")

        self.start_hosting_action = QAction("&Start Hosting Session", self)
        self.start_hosting_action.setShortcut(QKeySequence("Ctrl+H"))
        self.start_hosting_action.triggered.connect(self._start_hosting_session)
        session_menu.addAction(self.start_hosting_action)

        self.connect_to_host_action = QAction("&Connect to Host...", self)
        self.connect_to_host_action.setShortcut(QKeySequence("Ctrl+J"))
        self.connect_to_host_action.triggered.connect(self._connect_to_host_session)
        session_menu.addAction(self.connect_to_host_action)
        
        self.stop_session_action = QAction("S&top Current Session", self)
        self.stop_session_action.setShortcut(QKeySequence("Ctrl+T"))
        self.stop_session_action.triggered.connect(self._stop_current_session)
        self.stop_session_action.setEnabled(False)
        session_menu.addAction(self.stop_session_action)

        # --- Edit Menu ---
        edit_menu = self.menu_bar.addMenu("&Edit")

        # Format Code Action
        self.format_code_action = QAction("&Format Code", self)
        self.format_code_action.setShortcut(QKeySequence("Ctrl+Alt+L"))
        self.format_code_action.triggered.connect(self._format_code)
        edit_menu.addAction(self.format_code_action)

        # Note: "Show Completions" action might be removed if CodeEditor handles this automatically
        # or via its own keyPressEvent. If a manual trigger is still desired from MainWindow menu,
        # it would need to call a public method on self.editor (e.g., self.editor._request_completion()).
        # For now, assuming CodeEditor handles its completion triggers.

    def _connect_network_signals(self):
        self.network_manager.data_received.connect(self._handle_data_received)
        self.network_manager.peer_connected.connect(self._handle_peer_connected)
        self.network_manager.peer_disconnected.connect(self._handle_peer_disconnected)
        self.network_manager.hosting_started.connect(self._handle_hosting_started)
        self.network_manager.connection_failed.connect(self._handle_connection_failed)

    @Slot()
    def _format_code(self):
        current_text = self.editor.toPlainText()
        if not current_text.strip():
            self.status_bar.showMessage("Nothing to format.", 3000)
            return

        try:
            cursor = self.editor.textCursor()
            original_pos = cursor.position() # Simple position, not line/col for this basic restoration

            formatted_text = black.format_str(current_text, mode=black.FileMode())

            if formatted_text == current_text:
                self.status_bar.showMessage("Code is already well-formatted.", 3000)
                return

            self._is_updating_from_network = True # Prevent network send during format
            self.editor.setPlainText(formatted_text)
            self._is_updating_from_network = False

            # Attempt to restore cursor position (basic)
            new_cursor = self.editor.textCursor()
            # Ensure new position is within the bounds of the (potentially shorter) formatted text
            new_cursor.setPosition(min(original_pos, len(formatted_text)))
            self.editor.setTextCursor(new_cursor)

            self.status_bar.showMessage("Code formatted successfully.", 3000)

        except black.NothingChanged:
            self.status_bar.showMessage("Code is already well-formatted (Black: Nothing changed).", 3000)
        except black.InvalidInput as e:
            QMessageBox.warning(self, "Formatting Error", f"Could not format code due to invalid input: {e}")
            self.status_bar.showMessage("Formatting error: Invalid input.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Formatting Error", f"An unexpected error occurred during formatting: {e}")
            self.status_bar.showMessage(f"Formatting error: {e}", 3000)


    # --- Session Action Slots ---
    @Slot()
    def _start_hosting_session(self):
        self.status_bar.showMessage(f"Attempting to start hosting on port {self.DEFAULT_PORT}...")
        self.network_manager.start_hosting(self.DEFAULT_PORT)

    @Slot()
    def _connect_to_host_session(self):
        ip, port = ConnectionDialog.get_details(self) 
        if ip and port:
            self.status_bar.showMessage(f"Attempting to connect to {ip}:{port}...")
            self.network_manager.connect_to_host(ip, port)
        else:
            self.status_bar.showMessage("Connection cancelled or invalid details provided.")
            
    @Slot()
    def _stop_current_session(self):
        self.network_manager.stop_session()
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self.status_bar.showMessage("Session stopped. Ready to start or connect.")
        self.editor.setReadOnly(False)
        current_title = self.windowTitle()
        if " - Client (View-Only)" in current_title or " - Host" in current_title:
            self.setWindowTitle(current_title.split(" - ")[0])

    # --- NetworkManager Signal Handler Slots ---
    @Slot(str)
    def _handle_data_received(self, text: str):
        self._is_updating_from_network = True
        cursor = self.editor.textCursor()
        old_pos = cursor.position()
        old_anchor = cursor.anchor()
        self.editor.setPlainText(text)
        if old_anchor != old_pos:
            cursor.setPosition(old_anchor, QTextCursor.MoveAnchor)
            cursor.setPosition(old_pos, QTextCursor.KeepAnchor)
        else:
            cursor.setPosition(old_pos)
        self.editor.setTextCursor(cursor)
        self._is_updating_from_network = False

    @Slot(str, int)
    def _handle_hosting_started(self, host_ip: str, port_num: int):
        self.status_bar.showMessage(f"Hosting on {host_ip}:{port_num}. Waiting for connection...")
        self.start_hosting_action.setEnabled(False)
        self.connect_to_host_action.setEnabled(False)
        self.stop_session_action.setEnabled(True)
        self.editor.setReadOnly(False)
        self.setWindowTitle(f"{self.windowTitle().split(' - ')[0]} - Host")

    @Slot()
    def _handle_peer_connected(self):
        self.status_bar.showMessage("Peer connected. Collaboration active.")
        self.start_hosting_action.setEnabled(False)
        self.connect_to_host_action.setEnabled(False)
        self.stop_session_action.setEnabled(True)
        base_title = self.windowTitle().split(" - ")[0]
        if not self.network_manager._is_server:
            self.editor.setReadOnly(True) 
            self.setWindowTitle(f"{base_title} - Client (View-Only)")
        else:
            self.editor.setReadOnly(False)
            self.setWindowTitle(f"{base_title} - Host")

    @Slot()
    def _handle_peer_disconnected(self):
        self.status_bar.showMessage("Peer disconnected. Session ended.")
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self.editor.setReadOnly(False)
        current_title = self.windowTitle()
        if " - Client (View-Only)" in current_title or " - Host" in current_title:
            self.setWindowTitle(current_title.split(" - ")[0])

    @Slot(str)
    def _handle_connection_failed(self, error_message: str):
        QMessageBox.critical(self, "Network Error", error_message)
        self.status_bar.showMessage(f"Error: {error_message}")
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self.editor.setReadOnly(False)
        current_title = self.windowTitle()
        if " - Client (View-Only)" in current_title or " - Host" in current_title:
            self.setWindowTitle(current_title.split(" - ")[0])

    # --- Editor Change Handler for Network ---
    @Slot()
    def _on_editor_text_changed_for_network(self):
        if self._is_updating_from_network:
            return
        
        is_host_with_clients = self.network_manager._is_server and self.network_manager.server_client_sockets
        is_connected_client = (not self.network_manager._is_server and 
                               self.network_manager.client_socket and 
                               self.network_manager.client_socket.state() == QTcpSocket.ConnectedState)

        if is_host_with_clients or is_connected_client:
            current_text = self.editor.toPlainText()
            self.network_manager.send_data(current_text)

    def closeEvent(self, event):
        self.status_bar.showMessage("Closing session...")
        self.network_manager.stop_session()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # MockNetworkManager can be used for standalone UI testing if network_manager.py is complex/unavailable
    class MockNetworkManager(QObject): # QObject needed for signals
        data_received = Signal(str)
        peer_connected = Signal()
        peer_disconnected = Signal()
        hosting_started = Signal(str, int)
        connection_failed = Signal(str)
        _is_server = False 
        server_client_sockets = [] 
        client_socket = None

        def start_hosting(self, port): self.connection_failed.emit("Mock: Hosting not implemented.")
        def connect_to_host(self, ip, port): self.connection_failed.emit("Mock: Connection not implemented.")
        def send_data(self, text): pass
        def stop_session(self): self.peer_disconnected.emit()
    
    window = MainWindow()
    # To test with MockNetworkManager:
    # window.network_manager = MockNetworkManager(window)
    # window._connect_network_signals() # Reconnect signals if you overwrite network_manager

    window.show()
    sys.exit(app.exec())
