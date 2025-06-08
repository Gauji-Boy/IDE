# simple_collab_editor.py
# A basic real-time collaborative text editor using PySide6 and QTcpSocket.
# This application allows one user to host a session (acting as a server)
# and another user to connect as a client. Text changes are synchronized
# between the host and the client in real-time. It demonstrates basic
# PySide6 UI creation, QTcpServer/QTcpSocket usage for networking,
# and a simple loop prevention mechanism for text synchronization.

# Ensure PySide6 is installed: pip install PySide6

import sys
import socket # For QTcpSocket.SHUT_RDWR (though not explicitly used in this version's shutdown logic)
# socketserver and threading are not used in this PySide6 version, as QTcpServer handles client connections.

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QMessageBox, QInputDialog
)
from PySide6.QtGui import QAction, QTextCursor # QTextCursor for cursor position preservation
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PySide6.QtCore import Slot, Qt, QIODevice # QIODevice for socket read/write modes

# Main application window for the Collaborative Editor
class CollaborativeEditor(QMainWindow):
    """
    The main window class for the collaborative editor.
    It handles UI setup, text editing, and network communication
    for both host and client modes of operation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Main Window Properties ---
        self.setWindowTitle("Simple Collaborative Editor")
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        # --- Central Text Editor ---
        # QPlainTextEdit is used for its performance with large documents.
        self.editor = QPlainTextEdit()
        self.setCentralWidget(self.editor) # Make the editor the main widget

        # --- Networking Attributes ---
        # These attributes are initialized to None and will be set up
        # when a hosting session starts or a client connection is made.

        # For Host mode:
        self.tcp_server = None  # Will hold the QTcpServer instance when hosting.
        self.server_client_sockets = []  # List of QTcpSocket instances for connected clients.
        self.is_host = False  # Flag to indicate if this instance is currently acting as a host.

        # For Client mode:
        self.client_socket = None  # Will hold the QTcpSocket for this client's connection to a host.

        # --- Loop Prevention Flag ---
        # This flag is crucial for preventing infinite loops during text synchronization.
        # When True, it means the current text change in the editor was triggered by a
        # network update, so the _on_text_changed slot should not rebroadcast it.
        self._is_updating_from_network = False

        # --- Menu Bar and Actions ---
        self.menu_bar = self.menuBar()
        self.session_menu = self.menu_bar.addMenu("&Session") # Top-level menu for session management

        # Action to start hosting a new collaborative session
        self.start_hosting_action = QAction("&Start Hosting Session", self)
        self.start_hosting_action.triggered.connect(self._start_hosting_session)
        self.session_menu.addAction(self.start_hosting_action)

        # Action to connect to an existing session hosted by another user
        self.connect_to_host_action = QAction("&Connect to Host...", self)
        self.connect_to_host_action.triggered.connect(self._connect_to_host_session)
        self.session_menu.addAction(self.connect_to_host_action)

        # --- Status Bar ---
        # Used to display messages about connection status, errors, etc.
        self.statusBar().showMessage("Ready")

        # --- Connect Editor Signal ---
        # Connect the editor's textChanged signal to the _on_text_changed method.
        # This method is the primary trigger for sending text updates over the network.
        self.editor.textChanged.connect(self._on_text_changed)

    # --- Text Synchronization Logic ---
    @Slot()
    def _on_text_changed(self):
        """
        Handles local text changes in the editor. This is the core of the synchronization.
        If the change was not initiated by a network update (i.e., the user typed something),
        this method sends the current editor content to the connected peer(s).
        The `_is_updating_from_network` flag prevents re-sending data that was just received.
        """
        # If True, this text change was due to a network update, so ignore it to prevent a loop.
        if self._is_updating_from_network:
            return

        # Get the current text from the editor and encode it to UTF-8 for network transmission.
        current_text = self.editor.toPlainText().encode('utf-8')

        if self.is_host and self.tcp_server and self.server_client_sockets:
            # Host mode: Broadcast the text to all currently connected clients.
            # Iterate over a copy of the list (list(...)) because a client might disconnect
            # during this loop (e.g., due to a write error), which would modify
            # self.server_client_sockets and could cause issues with the iteration.
            for client_socket in list(self.server_client_sockets):
                if client_socket.state() == QTcpSocket.ConnectedState:
                    try:
                        client_socket.write(current_text)
                    except Exception as e:
                        # This might happen if the socket closes abruptly during write.
                        self.statusBar().showMessage(f"Error writing to client {client_socket.peerAddress()}: {e}")
                        # Attempt to clean up this problematic client.
                        if client_socket in self.server_client_sockets:
                            self.server_client_sockets.remove(client_socket)
                        client_socket.deleteLater() # Schedule for safe deletion.
                else:
                    # This socket is no longer connected. This should ideally be caught by its
                    # disconnected signal, but this serves as a safeguard during broadcast.
                    if client_socket in self.server_client_sockets:
                        self.server_client_sockets.remove(client_socket)
                    client_socket.deleteLater()
            # self.statusBar().showMessage("Sent update to client(s).") # Optional: can be noisy

        elif not self.is_host and self.client_socket and self.client_socket.state() == QTcpSocket.ConnectedState:
            # Client mode: Send the text update to the host.
            try:
                self.client_socket.write(current_text)
            except Exception as e:
                self.statusBar().showMessage(f"Error writing to host: {e}")
                # If writing to the host fails, the connection might be dead.
                # The disconnected() or errorOccurred() signals for client_socket should handle the full cleanup.
            # self.statusBar().showMessage("Sent update to host.") # Optional: can be noisy

    # --- Host Functionality Methods ---
    @Slot()
    def _start_hosting_session(self):
        """
        Initializes and starts the TCP server to host a collaborative session.
        Sets up the server to listen for incoming client connections.
        """
        self.is_host = True  # Set the application instance to host mode.
        self.tcp_server = QTcpServer(self) # Create the QTcpServer instance.
        # Connect the server's newConnection signal. This signal is emitted whenever
        # a new client attempts to connect to the server.
        self.tcp_server.newConnection.connect(self._handle_new_connection)

        # Attempt to make the server listen on localhost (127.0.0.1) and port 54321.
        # The port number is arbitrary but must be the same for host and client.
        if not self.tcp_server.listen(QHostAddress.LocalHost, 54321):
            # If listening fails (e.g., port is already in use), show an error message.
            QMessageBox.critical(self, "Server Error",
                                 f"Unable to start server: {self.tcp_server.errorString()}")
            self.is_host = False # Reset host status.
            self.tcp_server = None # Clean up the server object.
            return

        # Update UI to reflect that hosting has started.
        self.start_hosting_action.setEnabled(False) # Disable "Start Hosting" as it's active.
        self.connect_to_host_action.setEnabled(False) # Cannot be a client while hosting.
        self.statusBar().showMessage("Hosting on 127.0.0.1:54321. Waiting for client...")
        self.editor.setReadOnly(False) # Host can always edit their document.

    @Slot()
    def _handle_new_connection(self):
        """
        Handles a new client connection when the server is hosting.
        It accepts the connection, sets up communication signals for the client socket,
        and sends the current document state to the new client.
        """
        if not self.is_host or not self.tcp_server:
            # This check ensures that new connections are only handled if hosting is active.
            return

        # Get the QTcpSocket for the pending connection.
        client_connection = self.tcp_server.nextPendingConnection()
        if client_connection:
            # This simple version effectively handles one primary client for receiving updates.
            # If a new client connects while another is already connected, the older one is
            # disconnected to simplify the host's logic for receiving changes.
            # For broadcasting, the host sends to all sockets in server_client_sockets.
            if self.server_client_sockets:
                old_client = self.server_client_sockets.pop(0) # Remove the first (oldest) client.
                # Disconnect signals from the old client to prevent further processing.
                try: old_client.disconnected.disconnect(self._handle_client_disconnected)
                except RuntimeError: pass # Already disconnected
                try: old_client.readyRead.disconnect(self._handle_server_ready_read)
                except RuntimeError: pass # Already disconnected
                old_client.abort() # Forcibly close the old connection.
                old_client.deleteLater() # Schedule for safe deletion.
                self.statusBar().showMessage("Replaced old client with new connection.")

            self.server_client_sockets.append(client_connection) # Add new client to list.
            # Connect signals for the new client socket:
            # readyRead: Emitted when new data is available from the client.
            client_connection.readyRead.connect(self._handle_server_ready_read)
            # disconnected: Emitted when the client disconnects.
            client_connection.disconnected.connect(self._handle_client_disconnected)

            self.statusBar().showMessage(f"Client connected from {client_connection.peerAddress().toString()}:{client_connection.peerPort()}. Ready to collaborate.")

            # Send the current full editor content to the newly connected client.
            # This ensures the client starts with the host's current document state.
            try:
                current_text = self.editor.toPlainText().encode('utf-8')
                client_connection.write(current_text)
            except Exception as e:
                self.statusBar().showMessage(f"Error sending initial data to client: {e}")
                # Optionally, one might disconnect this client if the initial send fails.

    @Slot()
    def _handle_server_ready_read(self):
        """
        Handles data received from a connected client when this instance is hosting.
        The `sender()` method correctly identifies which QTcpSocket emitted the signal.
        """
        client_socket = self.sender() # Get the client socket that sent the data.
        if not client_socket or not isinstance(client_socket, QTcpSocket):
            return # Should not happen if signals are connected correctly.

        try:
            # Read all available data from the client socket and decode from UTF-8.
            received_data = client_socket.readAll().data().decode('utf-8')

            # Set the loop prevention flag before updating the editor's text.
            self._is_updating_from_network = True

            # Preserve cursor position and selection before programmatically changing text.
            cursor = self.editor.textCursor()
            original_pos = cursor.position()
            anchor_pos = cursor.anchor() # For maintaining selection if any.

            self.editor.setPlainText(received_data) # Update the host's editor content.

            # Restore cursor position and selection.
            cursor.setPosition(anchor_pos) # Set anchor first to define selection range.
            # Ensure new position is within the bounds of the (potentially shorter) new text.
            cursor.setPosition(min(original_pos, len(received_data)), QTextCursor.KeepAnchor if anchor_pos != original_pos else QTextCursor.MoveAnchor)
            self.editor.setTextCursor(cursor)

        except Exception as e:
            self.statusBar().showMessage(f"Error reading from client: {e}")
        finally:
            # Crucially, reset the loop prevention flag after processing the update.
            self._is_updating_from_network = False

    @Slot()
    def _handle_client_disconnected(self):
        """
        Handles a client disconnection when this instance is hosting.
        Cleans up the disconnected client's socket.
        """
        client_socket = self.sender() # Get the client socket that disconnected.
        if not client_socket or not isinstance(client_socket, QTcpSocket):
            return

        # Remove the disconnected client from the list of active client sockets.
        if client_socket in self.server_client_sockets:
            self.server_client_sockets.remove(client_socket)

        client_socket.deleteLater() # Schedule the QTcpSocket object for safe deletion.

        if not self.server_client_sockets: # If no clients are left.
            self.statusBar().showMessage("Client disconnected. Waiting for new client...")
        else:
            self.statusBar().showMessage(f"A client disconnected. {len(self.server_client_sockets)} client(s) remain.")

        # The server remains listening, allowing new clients to connect.

    # --- Client Functionality Methods ---
    @Slot()
    def _connect_to_host_session(self):
        """
        Initiates a connection to a host server for collaboration.
        It prompts the user for the host's address and port.
        """
        # Check if already connected or hosting.
        if self.client_socket and self.client_socket.state() == QTcpSocket.ConnectedState:
            QMessageBox.information(self, "Already Connected", "You are already connected to a host.")
            return
        if self.is_host:
            QMessageBox.warning(self, "Already Hosting", "Cannot connect to a host while also hosting a session.")
            return

        # Use QInputDialog to get the host address string from the user.
        host_address_str, ok = QInputDialog.getText(self, "Connect to Host",
                                                    "Enter host address (e.g., 127.0.0.1:54321):",
                                                    text="127.0.0.1:54321") # Default value
        if not ok or not host_address_str:
            return # User cancelled the dialog.

        # Parse the input address string (IP:Port).
        try:
            parts = host_address_str.split(':')
            if len(parts) != 2:
                raise ValueError("Address must be in format IP:PORT")
            host_ip = parts[0]
            host_port = int(parts[1])
            # Basic validation for port number range.
            if not (0 < host_port < 65536):
                raise ValueError("Port number must be between 1 and 65535")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Address", f"Invalid address format: {e}")
            return

        # If a client socket object already exists (e.g., from a previous failed attempt),
        # schedule it for deletion before creating a new one.
        if self.client_socket:
            self.client_socket.deleteLater()

        # Create a new QTcpSocket for the client.
        self.client_socket = QTcpSocket(self)
        # Connect signals for the client socket:
        self.client_socket.connected.connect(self._handle_client_connected_to_host) # Success
        self.client_socket.readyRead.connect(self._handle_client_ready_read)         # Data received
        self.client_socket.disconnected.connect(self._handle_client_disconnected_from_host) # Disconnected by host/self
        self.client_socket.errorOccurred.connect(self._handle_client_connection_error) # Connection errors

        self.statusBar().showMessage(f"Attempting to connect to {host_ip}:{host_port}...")
        # Attempt to connect to the specified host and port.
        self.client_socket.connectToHost(QHostAddress(host_ip), host_port)

    @Slot()
    def _handle_client_connected_to_host(self):
        """
        Handles the event of successfully connecting to the host server.
        Updates UI elements to reflect the client-connected state.
        """
        self.is_host = False # A client cannot simultaneously be a host.
        self.start_hosting_action.setEnabled(False) # Disable hosting option.
        self.connect_to_host_action.setEnabled(False) # Disable further connect attempts.
        self.statusBar().showMessage("Connected to host. Collaboration active.")
        # The client's editor will now reflect content sent by the host.
        # In this simple model, the client's local changes will be sent to the host via _on_text_changed.
        # For a view-only client, one might set self.editor.setReadOnly(True) here.

    @Slot()
    def _handle_client_ready_read(self):
        """
        Handles data received from the host server when this instance is a client.
        """
        if not self.client_socket or self.client_socket.state() != QTcpSocket.ConnectedState:
            return # Socket not valid or not connected.

        try:
            # Read all available data from the host and decode from UTF-8.
            received_data = self.client_socket.readAll().data().decode('utf-8')

            # Set the loop prevention flag before updating the editor's text.
            self._is_updating_from_network = True

            # Preserve cursor position and selection.
            cursor = self.editor.textCursor()
            original_pos = cursor.position()
            anchor_pos = cursor.anchor()

            self.editor.setPlainText(received_data) # Update the client's editor content.

            # Restore cursor position and selection.
            cursor.setPosition(anchor_pos)
            cursor.setPosition(min(original_pos, len(received_data)), QTextCursor.KeepAnchor if anchor_pos != original_pos else QTextCursor.MoveAnchor)
            self.editor.setTextCursor(cursor)

        except Exception as e:
            self.statusBar().showMessage(f"Error processing data from host: {e}")
        finally:
            # Crucially, reset the loop prevention flag.
            self._is_updating_from_network = False

    @Slot()
    def _handle_client_disconnected_from_host(self):
        """
        Handles disconnection from the host server (can be initiated by host, client, or network issue).
        Resets the client's UI and networking state.
        """
        if not self.client_socket: # If already cleaned up (e.g., by error handler).
            return

        self.client_socket.deleteLater() # Schedule the QTcpSocket for deletion.
        self.client_socket = None

        # Reset UI to allow starting/joining a new session.
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.statusBar().showMessage("Disconnected from host.")

        # Inform the user, but avoid duplicate messages if an error dialog was just shown.
        # `_last_client_error_handled` is a simple flag for this.
        if not hasattr(self, '_last_client_error_handled') or not self._last_client_error_handled:
             QMessageBox.information(self, "Disconnected", "Disconnected from the host.")
        self._last_client_error_handled = False # Reset the flag.

    @Slot(QTcpSocket.SocketError) # Type hint for the socket_error argument
    def _handle_client_connection_error(self, socket_error: QTcpSocket.SocketError):
        """
        Handles errors that occur on the client socket, such as connection failures.
        The `socket_error` argument provides details about the error.
        """
        if not self.client_socket: # Socket might have been cleaned up by another handler.
            return

        error_message = self.client_socket.errorString() # Get a human-readable error message.

        self.client_socket.deleteLater() # Schedule for deletion.
        self.client_socket = None

        # Reset UI elements.
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.statusBar().showMessage(f"Connection error: {error_message}")
        QMessageBox.warning(self, "Connection Error", f"Could not connect or lost connection to host: {error_message}")
        # Set a flag to indicate an error message was shown, so the subsequent
        # disconnected signal (if it also fires) doesn't show a redundant "Disconnected" message.
        self._last_client_error_handled = True

# Main function to run the application
def main():
    """
    Initializes and runs the PySide6 QApplication for the collaborative editor.
    """
    app = QApplication(sys.argv)
    editor_window = CollaborativeEditor()
    editor_window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()

# HOW TO RUN AND TEST:
#
# 1. Prerequisites:
#    - Ensure you have Python 3 installed.
#    - Install PySide6: pip install PySide6
#
# 2. Launch Host Instance:
#    - Open a terminal or command prompt.
#    - Navigate to the directory where this script (`simple_collab_editor.py`) is saved.
#    - Run the script: python simple_collab_editor.py
#    - In the application window that appears, go to "Session" -> "Start Hosting Session".
#    - The status bar should indicate it's hosting (e.g., "Hosting on 127.0.0.1:54321...").
#
# 3. Launch Client Instance:
#    - Open a *new* (second) terminal or command prompt.
#    - Navigate to the same directory where the script is saved.
#    - Run the script again: python simple_collab_editor.py
#    - A second application window will appear.
#
# 4. Connect Client to Host:
#    - In the second (client) application window, go to "Session" -> "Connect to Host...".
#    - A dialog will appear asking for the host address. The default "127.0.0.1:54321" should be correct. Click "OK".
#    - The status bar in the client window should indicate "Connected to host...".
#    - The status bar in the host window should indicate "Client connected...".
#
# 5. Test Collaboration:
#    - Type text in the host application's editor. The text should appear in real-time in the client's editor.
#    - Type text in the client application's editor. The text should appear in real-time in the host's editor.
#    - Test that there are no infinite feedback loops (text doesn't rapidly duplicate or cause errors).
#      The `_is_updating_from_network` flag is designed to prevent this.
#
# 6. Disconnecting:
#    - Closing either window will end its participation in the session (host server stops, client disconnects).
#    - If the client application window is closed, the host status bar should update to "Client disconnected...".
#    - If the host application window is closed, the client should show a "Disconnected from host" message or a connection error.
#    - (Note: Explicit "Disconnect" menu options are not implemented in this basic version but would be a good addition.)
#
# 7. Multiple Clients (Behavior Note):
#    - Host: If multiple clients connect, the host will broadcast its changes to ALL connected clients.
#            However, when receiving changes, the host's editor will be updated by whichever client sent data most recently
#            if multiple clients are typing simultaneously and sending data. This version doesn't merge changes from multiple clients
#            in a sophisticated way but rather overwrites with the latest received update.
#    - Client: Each client connects only to the host and synchronizes with the host's document state.
#
# 8. Error Conditions:
#    - Try connecting a client when no host is running (should give a connection error).
#    - Try starting a host on a port that might be in use (less likely with localhost and a high port, but server start errors are handled).
#
