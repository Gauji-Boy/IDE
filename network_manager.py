# network_manager.py
# This file defines the NetworkManager class, which encapsulates all network
# communication logic for the collaborative editor. It handles both hosting
# (server-side) and connecting (client-side) functionalities using PySide6's
# QTcpServer and QTcpSocket. It uses signals to communicate network events
# (like connection, disconnection, data reception) to inescapablythe main UI (MainWindow).

import json # Add this import at the top of the file
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress

class NetworkManager(QObject):
    # --- Message Type Constants ---
    MSG_TYPE_TEXT_UPDATE = "TEXT_UPDATE"
    MSG_TYPE_REQ_CONTROL = "REQ_CONTROL"
    MSG_TYPE_GRANT_CONTROL = "GRANT_CONTROL"
    MSG_TYPE_REVOKE_CONTROL = "REVOKE_CONTROL"
    MSG_TYPE_DECLINE_CONTROL = "DECLINE_CONTROL"

    """
    Manages network communication (both server and client roles)
    for the collaborative editor.
    Emits signals to inform the UI (MainWindow) about network events,
    allowing the UI to react appropriately (e.g., update status messages,
    enable/disable actions, display data).
    """
    # --- Custom Signals ---
    # These signals are emitted by NetworkManager to notify other parts of the
    # application (typically MainWindow) about specific network events.

    # Emitted when text data is received from a peer (host or client).
    # The payload is the received string.
    data_received = Signal(str)      

    # Emitted when a connection is successfully established.
    # For a host, this means a client has connected.
    # For a client, this means it has connected to a host.
    peer_connected = Signal()        

    # Emitted when a peer disconnects or the connection is lost.
    peer_disconnected = Signal()     

    # Emitted when the server starts successfully.
    # Provides the host IP (usually 127.0.0.1) and port number.
    hosting_started = Signal(str, int) 

    # Emitted when a client fails to connect to a host, or the server fails to start.
    # Provides an error message string.
    connection_failed = Signal(str)

    # --- New Signals for Control Exchange ---
    control_request_received = Signal() # Emitted by host when client requests control
    control_granted_received = Signal() # Emitted by client when host grants control
    control_revoked_received = Signal() # Emitted by client when host revokes control
    control_declined_received = Signal() # Emitted by host when client declines control (or host if client declines)


    def __init__(self, parent=None):
        """
        Initializes the NetworkManager.

        Args:
            parent (QObject, optional): The parent QObject, typically for lifecycle management.
        """
        super().__init__(parent)
        self.tcp_server = None            # QTcpServer instance when acting as host.
        self.client_socket = None         # QTcpSocket instance when acting as client.
        self.server_client_sockets = []   # List of QTcpSocket for connected clients when hosting.
        self._is_server = False           # Flag indicating if this instance is currently a server/host.

    @Slot(int)
    def start_hosting(self, port=54321):
        """
        Starts hosting a collaborative session on the given port.
        Initializes a QTcpServer and makes it listen for incoming connections.

        Args:
            port (int, optional): The port number to host on. Defaults to 54321.
        """
        # Prevent starting if already hosting or connected as a client.
        if self.tcp_server is not None or self.client_socket is not None:
            print("NetworkManager: Attempt to start hosting while already active.")
            self.connection_failed.emit("Session is already active (hosting or connected).")
            return

        self.tcp_server = QTcpServer(self) # Create the server object.
        # Connect the server's newConnection signal to our handler.
        self.tcp_server.newConnection.connect(self._handle_new_connection)

        # Attempt to listen on localhost for the specified port.
        if self.tcp_server.listen(QHostAddress.LocalHost, port):
            self._is_server = True # Set server mode flag.
            # Emit signal that hosting has started, providing IP and port.
            # QHostAddress.LocalHost typically resolves to "127.0.0.1".
            self.hosting_started.emit(QHostAddress(QHostAddress.LocalHost).toString(), port)
            print(f"NetworkManager: Server started successfully on port {port}.")
        else:
            # If listening fails (e.g., port in use), emit failure signal.
            error_msg = f"Server could not start: {self.tcp_server.errorString()}"
            print(f"NetworkManager: {error_msg}")
            self.connection_failed.emit(error_msg)
            if self.tcp_server: self.tcp_server.deleteLater() # Ensure QTcpServer object is cleaned up.
            self.tcp_server = None 

    @Slot()
    def _handle_new_connection(self):
        """
        Handles a new client connection when this instance is acting as a server.
        This slot is connected to QTcpServer's newConnection signal.
        """
        if not self.tcp_server: # Should not happen if server is active.
            return

        # Loop as long as there are pending connections.
        while self.tcp_server.hasPendingConnections():
            new_socket = self.tcp_server.nextPendingConnection() # Accept the connection.
            if new_socket:
                # Simplified approach: If other clients were connected, disconnect them.
                # This makes the server effectively handle one "primary" client for simplicity,
                # especially for receiving data. Broadcasting will still go to all in the list.
                if self.server_client_sockets:
                    print("NetworkManager: Disconnecting existing client(s) to accept new one.")
                    for sock in list(self.server_client_sockets): # Iterate a copy for safe removal
                        try: # Disconnect signals to prevent them firing during abort
                            sock.disconnected.disconnect(self._handle_peer_socket_disconnected)
                            sock.readyRead.disconnect(self._handle_peer_socket_ready_read)
                        except RuntimeError: pass # If signals were not connected or already disconnected
                        sock.abort() # Force close the socket.
                        sock.deleteLater() # Schedule for deletion.
                    self.server_client_sockets.clear()
                    self.peer_disconnected.emit() # Signal that the old peer(s) are gone.

                self.server_client_sockets.append(new_socket) # Add the new client socket.
                # Connect signals for the newly connected client.
                new_socket.readyRead.connect(self._handle_peer_socket_ready_read)
                new_socket.disconnected.connect(self._handle_peer_socket_disconnected)
                
                self.peer_connected.emit() # Signal that a peer (client) has connected.
                print(f"NetworkManager: Client connected from {new_socket.peerAddress().toString()}:{new_socket.peerPort()}")
                # The main window will typically send the initial document upon this signal.

    @Slot(str, int)
    def connect_to_host(self, ip_address: str, port: int):
        """
        Connects to a hosting session at the given IP address and port.

        Args:
            ip_address (str): The IP address of the host.
            port (int): The port number of the host.
        """
        # Prevent connecting if already hosting or connected.
        if self.tcp_server is not None or \
           (self.client_socket is not None and self.client_socket.state() == QTcpSocket.ConnectedState):
            print("NetworkManager: Attempt to connect while already active.")
            self.connection_failed.emit("Session is already active (hosting or connected).")
            return
        
        # If there's an old client socket (e.g., from a failed attempt), clean it up.
        if self.client_socket: 
             self.client_socket.abort() # Ensure it's closed before deletion
             self.client_socket.deleteLater()
             self.client_socket = None

        self.client_socket = QTcpSocket(self) # Create the client socket.
        # Connect client socket signals to their handlers.
        self.client_socket.connected.connect(self._on_client_connected)
        self.client_socket.readyRead.connect(self._handle_peer_socket_ready_read)
        self.client_socket.disconnected.connect(self._on_client_disconnected)
        self.client_socket.errorOccurred.connect(self._on_client_connection_error)

        print(f"NetworkManager: Attempting to connect to {ip_address}:{port}")
        try:
            host_addr = QHostAddress(ip_address)
            if host_addr.isNull():
                 # More specific error for invalid IP format before attempting connection
                 error_msg = f"Invalid IP address format: {ip_address}. Please use a valid IPv4 (e.g., 127.0.0.1) or IPv6 address."
                 print(f"NetworkManager: Connection error - {error_msg}")
                 self.connection_failed.emit(error_msg)
                 # Ensure client_socket is cleaned up if it was already created
                 if self.client_socket:
                     self.client_socket.deleteLater()
                     self.client_socket = None
                 return # Stop further processing
            self.client_socket.connectToHost(host_addr, port) # Initiate connection.
        except ValueError as e: # Catch ValueError from QHostAddress or our own validation (though explicit check is better)
             error_msg = str(e) # This might now be less likely if QHostAddress itself doesn't raise ValueError for format
             print(f"NetworkManager: Connection error - {error_msg}")
             self.connection_failed.emit(error_msg)
             if self.client_socket: # Ensure socket is cleaned up if created.
                self.client_socket.deleteLater()
                self.client_socket = None
        except RuntimeError as e: # QHostAddress can raise RuntimeError for invalid addresses.
             error_msg = f"Host address error or other runtime issue: {ip_address}. Error: {e}"
             print(f"NetworkManager: Connection error - {error_msg}")
             self.connection_failed.emit(error_msg)
             if self.client_socket:
                self.client_socket.deleteLater()
                self.client_socket = None

    @Slot()
    def _on_client_connected(self):
        """Slot for when the client successfully connects to the host."""
        self._is_server = False # Now in client mode.
        self.peer_connected.emit() # Notify UI.
        print("NetworkManager: Successfully connected to host.")

    @Slot()
    def _on_client_disconnected(self):
        """Slot for when the client is disconnected from the host."""
        print("NetworkManager: Disconnected from host.")
        self.peer_disconnected.emit() # Notify UI.
        # Clean up the client socket if it hasn't been already (e.g. by errorOccurred).
        if self.client_socket:
            # self.client_socket.deleteLater() # deleteLater might be problematic if errorOccurred also calls it.
            # Nullifying is safer here as errorOccurred or stop_session should manage deletion.
            self.client_socket = None 

    @Slot(QTcpSocket.SocketError) 
    def _on_client_connection_error(self, socket_error: QTcpSocket.SocketError):
        """
        Slot for handling client connection errors.
        `socket_error` is an enum QTcpSocket.SocketError.
        """
        if self.client_socket: # Check if socket object still exists.
            error_msg = self.client_socket.errorString() # Get human-readable error.
            print(f"NetworkManager: Connection error: {error_msg} (Code: {socket_error})")
            self.connection_failed.emit(error_msg) # Notify UI of failure.
            
            self.client_socket.abort() # Ensure the socket is closed.
            self.client_socket.deleteLater() # Schedule for deletion.
            self.client_socket = None
            
            # Emit peer_disconnected as well, because from UI perspective, there's no active peer.
            # This helps reset UI state consistently.
            self.peer_disconnected.emit() 

    @Slot()
    def _handle_peer_socket_ready_read(self):
        """
        Handles incoming data from a peer (can be a client if this is server,
        or the server if this is a client). The `sender()` method determines
        which socket emitted the signal.
        """
        socket = self.sender() # Get the QTcpSocket that has data.
        if socket and socket.bytesAvailable() > 0: # Check if there's data to read.
            try:
                # QTcpSocket is stream-based. readAll() gets what's currently in the buffer.
                data_bytes = socket.readAll()
                try:
                    raw_message = bytes(data_bytes).decode('utf-8')
                    message = json.loads(raw_message) # Parse JSON
                    message_type = message.get("type")
                    content = message.get("content") # content can be None if not present

                    print(f"NetworkManager: Received message: type='{message_type}', content_preview='{str(content)[:50]}...'") # Debug print

                    if message_type == self.MSG_TYPE_TEXT_UPDATE:
                        if content is not None:
                            self.data_received.emit(content)
                        else:
                            print(f"NetworkManager: Warning - {self.MSG_TYPE_TEXT_UPDATE} received with None content.")
                    elif message_type == self.MSG_TYPE_REQ_CONTROL:
                        self.control_request_received.emit()
                    elif message_type == self.MSG_TYPE_GRANT_CONTROL:
                        self.control_granted_received.emit()
                    elif message_type == self.MSG_TYPE_REVOKE_CONTROL:
                        self.control_revoked_received.emit()
                    elif message_type == self.MSG_TYPE_DECLINE_CONTROL:
                        self.control_declined_received.emit()
                    else:
                        print(f"NetworkManager: Unknown message type received: '{message_type}'")

                except json.JSONDecodeError as jde:
                    print(f"NetworkManager: JSONDecodeError - {jde}. Raw data: {raw_message[:100]}...") # Show part of raw data
                except UnicodeDecodeError as ude:
                    print(f"NetworkManager: UnicodeDecodeError - {ude}. Cannot decode received data.")
                except KeyError as ke: # Should be less likely with .get() but good for robustness
                    print(f"NetworkManager: KeyError - {ke}. Message structure unexpected: {message}")
                except Exception as e: # General catch-all
                    print(f"NetworkManager: Unexpected error in _handle_peer_socket_ready_read: {e}")
        # else:
        #     print(f"NetworkManager: _handle_peer_socket_ready_read triggered by {socket} but no bytes available or invalid socket.")


    @Slot()
    def _handle_peer_socket_disconnected(self):
        """
        Handles disconnection of a specific client socket when acting as a server.
        This is connected to each client socket's disconnected() signal.
        """
        socket = self.sender() # Get the QTcpSocket that disconnected.
        if socket:
            peer_info = f"{socket.peerAddress().toString()}:{socket.peerPort()}"
            print(f"NetworkManager: Peer socket {peer_info} disconnected.")
            if socket in self.server_client_sockets:
                self.server_client_sockets.remove(socket)
            socket.deleteLater() # Schedule for deletion.
            self.peer_disconnected.emit() # Notify UI that a peer has disconnected.

    @Slot(str, str)
    def send_data(self, message_type: str, content: str = ""):
        """
        Sends the given message type and content (JSON serialized, UTF-8 encoded)
        to the connected peer(s).
        If acting as a server, broadcasts to all connected clients.
        If acting as a client, sends to the host.

        Args:
            message_type (str): The type of message (e.g., MSG_TYPE_TEXT_UPDATE).
            content (str, optional): The content of the message. Defaults to "".
        """
        final_data_to_send = None
        message_dict = {"type": message_type, "content": content} # Keep dict for logging on error
        try:
            final_data_to_send = json.dumps(message_dict).encode('utf-8')
        except TypeError as e:
            print(f"NetworkManager: Error serializing message to JSON: {e}. Message: {message_dict}")
            return
        except Exception as e: # Other potential json errors
            print(f"NetworkManager: Error during JSON preparation for sending: {e}. Message: {message_dict}")
            return

        if not final_data_to_send: # Should not happen if above try/except is thorough
            return

        print(f"NetworkManager: Sending message: type='{message_type}', content_preview='{str(content)[:50]}...'") # Debug print

        if self._is_server:
            if not self.server_client_sockets:
                return
            for client_sock in list(self.server_client_sockets): # Iterate copy
                if client_sock.isValid() and client_sock.state() == QTcpSocket.ConnectedState:
                    if client_sock.write(final_data_to_send) == -1:
                        print(f"NetworkManager (Host): Error writing to client {client_sock.peerAddress().toString()}. State: {client_sock.state()}")
                        # Consider further error handling like removing problematic client
                else:
                    print(f"NetworkManager (Host): Skipping dead/invalid socket {client_sock.peerAddress().toString()}. State: {client_sock.state()}")
                    # Optionally remove from list here if state implies it's permanently unusable
        elif self.client_socket and self.client_socket.isValid() and self.client_socket.state() == QTcpSocket.ConnectedState:
            if self.client_socket.write(final_data_to_send) == -1:
                print(f"NetworkManager (Client): Error writing to host. State: {self.client_socket.state()}")
        # else:
            # print("NetworkManager: Not connected or not hosting, cannot send data.")

    def stop_session(self):
        """
        Stops any active hosting session or client connection.
        Cleans up server and socket resources.
        """
        print("NetworkManager: Stopping current session...")
        session_was_active = self._is_server or (self.client_socket is not None)

        if self.tcp_server: # If hosting
            # Close all client connections managed by the server
            for sock in self.server_client_sockets:
                sock.abort() # Force close
                sock.deleteLater() # Schedule for deletion
            self.server_client_sockets.clear() # Clear the list
            
            self.tcp_server.close() # Stop listening
            self.tcp_server.deleteLater() # Schedule server for deletion
            self.tcp_server = None
            print("NetworkManager: Server stopped.")
        
        if self.client_socket: # If connected as a client
            self.client_socket.abort() # Force close the connection
            self.client_socket.deleteLater() # Schedule socket for deletion
            self.client_socket = None
            print("NetworkManager: Client connection closed.")
        
        self._is_server = False # Reset server status flag
        
        # Emit peer_disconnected if a session was genuinely active and is now stopped.
        # This helps the UI reset to a disconnected state.
        if session_was_active:
            self.peer_disconnected.emit() 
        print("NetworkManager: Session stopped.")


if __name__ == '__main__':
    # This class is primarily intended to be imported and used within a QApplication.
    # Direct execution doesn't demonstrate its functionality without a running event loop
    # and UI components to interact with its signals and slots.
    print("NetworkManager class defined. Not executable on its own. Import into a PySide6 application.")
