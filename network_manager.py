# network_manager.py
# This file defines the NetworkManager class, which encapsulates all network
# communication logic for the collaborative editor. It handles both hosting
# (server-side) and connecting (client-side) functionalities using PySide6's
# QTcpServer and QTcpSocket. It uses signals to communicate network events
# (like connection, disconnection, data reception) to the main UI (MainWindow).

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress

class NetworkManager(QObject):
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
            host_addr = QHostAddress(ip_address) # Create QHostAddress from string.
            if host_addr.isNull(): # Basic validation for IP address format.
                 raise ValueError(f"Invalid IP address format: {ip_address}")
            self.client_socket.connectToHost(host_addr, port) # Initiate connection.
        except ValueError as e: # Catch ValueError from our own validation.
             error_msg = str(e)
             print(f"NetworkManager: Connection error - {error_msg}")
             self.connection_failed.emit(error_msg)
             if self.client_socket: # Ensure socket is cleaned up if created.
                self.client_socket.deleteLater()
                self.client_socket = None
        except RuntimeError as e: # QHostAddress can raise RuntimeError for invalid addresses.
             error_msg = f"Host address error: {ip_address}. Error: {e}"
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
                # For simple full-document sync, this is often okay if documents aren't huge.
                # More robust protocols would use QDataStream with message length prefixing
                # or a clear end-of-message delimiter.
                data_bytes = socket.readAll()
                # data = data_bytes.data().decode('utf-8') # .data() for QByteArray to bytes, then decode
                data = bytes(data_bytes).decode('utf-8') # Simpler way to convert QByteArray to bytes
                if data:
                    self.data_received.emit(data) # Emit signal with the received text.
                    # print(f"NetworkManager: Data received: {data[:70]}...") # For debugging
            except UnicodeDecodeError:
                print("NetworkManager: Error decoding received data (not UTF-8).")
            except Exception as e:
                print(f"NetworkManager: Error in _handle_peer_socket_ready_read: {e}")


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

    @Slot(str)
    def send_data(self, text: str):
        """
        Sends the given text (UTF-8 encoded) to the connected peer(s).
        If acting as a server, broadcasts to all connected clients.
        If acting as a client, sends to the host.

        Args:
            text (str): The text content to send.
        """
        data = text.encode('utf-8') # Ensure text is UTF-8 encoded bytes.
        if self._is_server: # If this instance is the host/server
            if not self.server_client_sockets:
                # print("NetworkManager (Host): No clients connected, cannot send data.")
                return
            # Iterate over a copy of the list for safe removal if a socket is dead.
            for client_sock in list(self.server_client_sockets):
                if client_sock.state() == QTcpSocket.ConnectedState:
                    bytes_written = client_sock.write(data)
                    if bytes_written == -1 : # Error during write
                        print(f"NetworkManager (Host): Error writing to client {client_sock.peerAddress().toString()}")
                        # Consider removing this client
                else: # Socket is not connected, remove it.
                    print(f"NetworkManager (Host): Removing dead socket {client_sock.peerAddress().toString()}")
                    if client_sock in self.server_client_sockets:
                         self.server_client_sockets.remove(client_sock)
                    client_sock.deleteLater()
        elif self.client_socket and self.client_socket.state() == QTcpSocket.ConnectedState:
            # If this instance is the client
            bytes_written = self.client_socket.write(data)
            if bytes_written == -1:
                 print(f"NetworkManager (Client): Error writing to host.")
                 # Connection might be dead, error/disconnect signals should handle cleanup.
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
