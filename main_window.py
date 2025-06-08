# main_window.py
# This file defines the MainWindow class, which is the main user interface
# for the Simple Collaborative Editor. It integrates the text editor,
# menu actions, status bar, and the NetworkManager for handling
# collaborative sessions (both hosting and joining).

import sys
from PySide6.QtWidgets import (
    QMainWindow, QPlainTextEdit, QMessageBox, QApplication, QStatusBar
)
from PySide6.QtGui import QAction, QKeySequence, QTextCursor # QTextCursor for cursor/selection preservation
from PySide6.QtCore import Slot, Qt, QObject, Signal # QObject, Signal for MockNetworkManager
from PySide6.QtNetwork import QTcpSocket # For type hinting in MockNetworkManager

# Import custom modules for networking and connection dialog
from network_manager import NetworkManager
from connection_dialog import ConnectionDialog


class MainWindow(QMainWindow):
    """
    The main window for the collaborative editor application.
    This class is responsible for:
    - Setting up the main UI elements (text editor, menus, status bar).
    - Creating and managing an instance of NetworkManager for network operations.
    - Handling user interactions through menu actions (start hosting, connect to host, stop session).
    - Responding to network events via signals from NetworkManager (e.g., data received, peer connected/disconnected).
    - Managing the editor's state (e.g., read-only for clients, sending local changes).
    - Implementing the loop prevention mechanism for text synchronization.
    """
    DEFAULT_PORT = 54321 # Default port for hosting and connecting

    def __init__(self, parent=None):
        """
        Initializes the MainWindow.
        Sets up the window properties, central editor, NetworkManager,
        status bar, menus, and connects necessary signals.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)

        # --- Main Window Properties ---
        self.setWindowTitle("Code-Sync IDE (Simple Collab)") # Initial window title
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        # --- Central Text Editor ---
        self.editor = QPlainTextEdit() # Using QPlainTextEdit for potentially better performance
        self.setCentralWidget(self.editor)

        # --- Network Manager ---
        # Instantiate NetworkManager and parent it to the main window for lifecycle management.
        # This ensures NetworkManager is properly cleaned up when the MainWindow is destroyed.
        self.network_manager = NetworkManager(self)

        # --- Loop Prevention Flag ---
        # This flag is set to True when the editor's text is being updated due to
        # incoming network data. This prevents the _on_editor_text_changed slot
        # from re-broadcasting the same change back to the network, avoiding an infinite loop.
        self._is_updating_from_network = False

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Start or connect to a session.")

        # --- UI Setup ---
        self._setup_menus() # Initialize menus and actions
        self._connect_network_signals() # Connect signals from NetworkManager to MainWindow's slots
        
        # Connect the editor's textChanged signal to send updates when user types.
        self.editor.textChanged.connect(self._on_editor_text_changed)

    def _setup_menus(self):
        """
        Sets up the main menu bar and defines actions for session management.
        """
        self.menu_bar = self.menuBar()
        session_menu = self.menu_bar.addMenu("&Session")

        # Action to start hosting a new collaborative session
        self.start_hosting_action = QAction("&Start Hosting Session", self)
        self.start_hosting_action.setShortcut(QKeySequence("Ctrl+H")) # Keyboard shortcut
        self.start_hosting_action.triggered.connect(self._start_hosting_session)
        session_menu.addAction(self.start_hosting_action)

        # Action to connect to an existing session hosted by another user
        self.connect_to_host_action = QAction("&Connect to Host...", self)
        self.connect_to_host_action.setShortcut(QKeySequence("Ctrl+J")) # "J" for Join
        self.connect_to_host_action.triggered.connect(self._connect_to_host_session)
        session_menu.addAction(self.connect_to_host_action)
        
        # Action to stop the current session (either hosting or client connection)
        self.stop_session_action = QAction("S&top Current Session", self)
        self.stop_session_action.setShortcut(QKeySequence("Ctrl+T")) # "T" for Terminate
        self.stop_session_action.triggered.connect(self._stop_current_session)
        self.stop_session_action.setEnabled(False) # Initially disabled, enabled when a session is active
        session_menu.addAction(self.stop_session_action)

    def _connect_network_signals(self):
        """
        Connects signals emitted by the NetworkManager instance to the
        appropriate slots (handler methods) in this MainWindow class.
        This is how the UI layer reacts to network events.
        """
        self.network_manager.data_received.connect(self._handle_data_received)
        self.network_manager.peer_connected.connect(self._handle_peer_connected)
        self.network_manager.peer_disconnected.connect(self._handle_peer_disconnected)
        self.network_manager.hosting_started.connect(self._handle_hosting_started)
        self.network_manager.connection_failed.connect(self._handle_connection_failed)

    # --- Session Action Slots ---
    @Slot()
    def _start_hosting_session(self):
        """
        Slot for the 'Start Hosting Session' menu action.
        Delegates the hosting request to the NetworkManager.
        """
        self.status_bar.showMessage(f"Attempting to start hosting on port {self.DEFAULT_PORT}...")
        self.network_manager.start_hosting(self.DEFAULT_PORT)
        # Further UI updates (e.g., enabling/disabling actions, status messages)
        # are handled by the slots connected to NetworkManager's signals
        # like _handle_hosting_started or _handle_connection_failed.

    @Slot()
    def _connect_to_host_session(self):
        """
        Slot for the 'Connect to Host' menu action.
        Uses ConnectionDialog to get host IP and port from the user,
        then delegates the connection request to NetworkManager.
        """
        # Use the static method from ConnectionDialog to get connection details.
        ip, port = ConnectionDialog.get_details(self) 
        if ip and port: # If user provided valid details and clicked OK
            self.status_bar.showMessage(f"Attempting to connect to {ip}:{port}...")
            self.network_manager.connect_to_host(ip, port)
        else:
            # User cancelled or provided invalid details.
            self.status_bar.showMessage("Connection cancelled or invalid details provided.")
            
    @Slot()
    def _stop_current_session(self):
        """
        Slot for the 'Stop Current Session' menu action.
        Tells NetworkManager to stop any active session (hosting or client).
        Resets UI elements to their default non-session state.
        """
        self.network_manager.stop_session()
        # Most UI changes related to disconnection are handled by _handle_peer_disconnected.
        # However, we ensure a consistent state here as well.
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self.status_bar.showMessage("Session stopped. Ready to start or connect.")
        self.editor.setReadOnly(False) # Ensure editor is writable after stopping.
        
        # Reset window title if it was modified for host/client status
        current_title = self.windowTitle()
        if " - Client (View-Only)" in current_title or " - Host" in current_title:
            self.setWindowTitle(current_title.split(" - ")[0]) # Restore base title

    # --- NetworkManager Signal Handler Slots ---
    @Slot(str)
    def _handle_data_received(self, text: str):
        """
        Slot for NetworkManager's data_received signal.
        Updates the editor's content with the received text.
        Uses the `_is_updating_from_network` flag to prevent echoing this change.

        Args:
            text (str): The text content received from the peer.
        """
        self._is_updating_from_network = True # Set flag before changing editor content
        
        # Preserve cursor position and selection to provide a better user experience.
        # When setPlainText is called, the cursor usually goes to the beginning.
        cursor = self.editor.textCursor()
        old_pos = cursor.position()      # Current cursor position
        old_anchor = cursor.anchor()     # Start of selection (or same as position if no selection)
        
        self.editor.setPlainText(text) # Update the editor content
        
        # Try to restore cursor/selection state.
        if old_anchor != old_pos: # If there was a selection
            cursor.setPosition(old_anchor, QTextCursor.MoveAnchor) # Restore anchor
            cursor.setPosition(old_pos, QTextCursor.KeepAnchor)    # Restore position, keeping anchor
        else: # Just a cursor position
            cursor.setPosition(old_pos)
        self.editor.setTextCursor(cursor) # Apply the restored cursor
        
        self._is_updating_from_network = False # Reset flag after update
        # self.status_bar.showMessage("Received update.", 2000) # Optional: can be noisy

    @Slot(str, int)
    def _handle_hosting_started(self, host_ip: str, port_num: int):
        """
        Slot for NetworkManager's hosting_started signal.
        Updates UI to reflect that the application is now hosting a session.

        Args:
            host_ip (str): The IP address the server is hosting on.
            port_num (int): The port number the server is listening on.
        """
        self.status_bar.showMessage(f"Hosting on {host_ip}:{port_num}. Waiting for connection...")
        self.start_hosting_action.setEnabled(False) # Disable start hosting (already hosting)
        self.connect_to_host_action.setEnabled(False) # Disable connect to host (can't be client)
        self.stop_session_action.setEnabled(True) # Enable stopping the session
        self.editor.setReadOnly(False) # Host editor is always writable by the host
        self.setWindowTitle(f"{self.windowTitle().split(' - ')[0]} - Host") # Update window title

    @Slot()
    def _handle_peer_connected(self):
        """
        Slot for NetworkManager's peer_connected signal.
        Called when this instance (as client) connects to a host,
        OR when this instance (as host) has a client connect to it.
        Updates UI to reflect an active collaborative session.
        """
        self.status_bar.showMessage("Peer connected. Collaboration active.")
        self.start_hosting_action.setEnabled(False) # Session active, so can't start another
        self.connect_to_host_action.setEnabled(False) # Or connect to another
        self.stop_session_action.setEnabled(True) # Can stop the current session
        
        base_title = self.windowTitle().split(" - ")[0] # Get base title without status
        if not self.network_manager._is_server: # If this instance is the CLIENT
            # For this simple version, client is view-only.
            # For bi-directional editing, this setReadOnly(True) would be removed/False.
            self.editor.setReadOnly(True) 
            self.setWindowTitle(f"{base_title} - Client (View-Only)")
        else: # If this instance is the HOST and a client just connected
            self.editor.setReadOnly(False) # Host editor remains writable
            self.setWindowTitle(f"{base_title} - Host")

    @Slot()
    def _handle_peer_disconnected(self):
        """
        Slot for NetworkManager's peer_disconnected signal.
        Resets UI to a non-session state, allowing user to host or connect again.
        """
        self.status_bar.showMessage("Peer disconnected. Session ended.")
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self.editor.setReadOnly(False) # Ensure editor is writable again
        
        # Reset window title to its base state
        current_title = self.windowTitle()
        if " - Client (View-Only)" in current_title or " - Host" in current_title:
            self.setWindowTitle(current_title.split(" - ")[0])

    @Slot(str)
    def _handle_connection_failed(self, error_message: str):
        """
        Slot for NetworkManager's connection_failed signal.
        Displays an error message and resets UI to a non-session state.

        Args:
            error_message (str): The error message describing the failure.
        """
        QMessageBox.critical(self, "Network Error", error_message)
        self.status_bar.showMessage(f"Error: {error_message}")
        # Reset UI elements to allow new session attempts
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self.editor.setReadOnly(False)
        
        # Reset window title if it was changed during connection attempt
        current_title = self.windowTitle()
        if " - Client (View-Only)" in current_title or " - Host" in current_title:
            self.setWindowTitle(current_title.split(" - ")[0])

    # --- Editor Change Handler ---
    @Slot()
    def _on_editor_text_changed(self):
        """
        Slot for the editor's textChanged signal.
        If the change was made locally by the user (not from a network update)
        and a network session is active, it sends the current editor content
        to the NetworkManager for broadcasting/sending.
        """
        # Prevents sending updates that were themselves caused by network data.
        if self._is_updating_from_network:
            return
        
        # Check if there's an active network session to send data to.
        is_host_with_clients = self.network_manager._is_server and self.network_manager.server_client_sockets
        is_connected_client = (not self.network_manager._is_server and 
                               self.network_manager.client_socket and 
                               self.network_manager.client_socket.state() == QTcpSocket.ConnectedState)

        if is_host_with_clients or is_connected_client:
            current_text = self.editor.toPlainText()
            self.network_manager.send_data(current_text)
            # self.status_bar.showMessage("Sent update.", 1000) # Optional: can be too frequent

    def closeEvent(self, event):
        """
        Overrides QMainWindow.closeEvent.
        Ensures any active network session (hosting or client) is cleanly
        stopped before the application window closes.
        """
        self.status_bar.showMessage("Closing session...") # Brief message
        self.network_manager.stop_session() # Tell NetworkManager to clean up
        super().closeEvent(event) # Proceed with the normal close event

if __name__ == '__main__':
    # This block allows testing MainWindow independently, potentially with a mock NetworkManager.
    app = QApplication(sys.argv)
    
    # --- Mock NetworkManager for standalone UI testing ---
    # This class can be used to simulate NetworkManager behavior if network_manager.py
    # is not available or if you want to test UI logic in isolation.
    class MockNetworkManager(QObject):
        data_received = Signal(str)
        peer_connected = Signal()
        peer_disconnected = Signal()
        hosting_started = Signal(str, int)
        connection_failed = Signal(str)
        _is_server = False 
        server_client_sockets = [] 
        client_socket = None # Type: QTcpSocket or None

        def start_hosting(self, port): 
            print(f"MockNetworkManager: Attempting to start hosting on port {port}")
            # Simulate success:
            # self._is_server = True
            # self.hosting_started.emit("127.0.0.1", port) 
            # Simulate failure:
            self.connection_failed.emit("Mock: Failed to start hosting (simulated).")

        def connect_to_host(self, ip, port): 
            print(f"MockNetworkManager: Attempting to connect to host {ip}:{port}")
            # Simulate success:
            # self._is_server = False
            # self.peer_connected.emit()
            # Simulate failure:
            self.connection_failed.emit("Mock: Failed to connect (simulated).")

        def send_data(self, text): 
            print(f"MockNetworkManager: Send data requested: {text[:30]}...")

        def stop_session(self): 
            print("MockNetworkManager: Stop session requested.")
            # Simulate that stopping a session means peers are disconnected.
            # Actual state changes for _is_server, client_socket etc. would happen here in real NM.
            self.peer_disconnected.emit() 
    # --- End of MockNetworkManager ---

    # To run main_window.py standalone for UI checks:
    # 1. Ensure `network_manager.py` and `connection_dialog.py` are available for import.
    #    OR, for pure UI testing without the actual network logic:
    #    a. Comment out the line: `from network_manager import NetworkManager`
    #    b. Uncomment the `MockNetworkManager` class definition above.
    #    c. In `MainWindow.__init__`, change the line:
    #       `self.network_manager = NetworkManager(self)`
    #       to:
    #       `self.network_manager = MockNetworkManager(self)`
    #    d. Note: `ConnectionDialog` is still imported. If it's also unavailable,
    #       the "Connect to Host..." action would error unless `ConnectionDialog.get_details` is also mocked.
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
