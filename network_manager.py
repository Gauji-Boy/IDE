from PySide6.QtCore import QObject, Signal, Slot, QByteArray
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
import json # Import json for structured messages

class NetworkManager(QObject):
    data_received = Signal(str) # For raw text content
    status_changed = Signal(str)
    peer_connected = Signal()
    peer_disconnected = Signal()
    
    # New signals for control messages
    control_request_received = Signal()
    control_granted = Signal()
    control_declined = Signal() # New signal for declined control
    control_revoked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tcp_server = QTcpServer(self)
        self.tcp_socket = QTcpSocket(self)
        self.peer_socket = None # Holds the socket for the connected peer (server side)
        self.buffer = {} # Buffer for incomplete messages, keyed by socket

        self.tcp_server.newConnection.connect(self._on_new_connection)
        self.tcp_socket.connected.connect(self._on_connected)
        self.tcp_socket.disconnected.connect(self._on_disconnected)
        self.tcp_socket.readyRead.connect(self._read_data)

    def start_hosting(self, port):
        if self.tcp_server.isListening():
            self.status_changed.emit("Server already listening.")
            return False
        
        # Try to listen on any available IP address
        if self.tcp_server.listen(QHostAddress.Any, port):
            self.status_changed.emit(f"Hosting on port {port}...")
            return True
        else:
            self.status_changed.emit(f"Failed to start hosting: {self.tcp_server.errorString()}")
            return False

    def connect_to_host(self, ip, port):
        if self.tcp_socket.state() == QTcpSocket.ConnectedState:
            self.status_changed.emit("Already connected to a host.")
            return
        
        self.status_changed.emit(f"Connecting to {ip}:{port}...")
        self.tcp_socket.connectToHost(ip, port)

    def stop_session(self):
        if self.tcp_server.isListening():
            self.tcp_server.close()
            if self.peer_socket:
                self.peer_socket.disconnectFromHost()
                self.peer_socket.waitForDisconnected(1000)
                self.peer_socket = None
            self.status_changed.emit("Hosting session stopped.")
        elif self.tcp_socket.state() == QTcpSocket.ConnectedState:
            self.tcp_socket.disconnectFromHost()
            self.tcp_socket.waitForDisconnected(1000)
            self.status_changed.emit("Connected session stopped.")
        else:
            self.status_changed.emit("No active session to stop.")

    @Slot()
    def _on_new_connection(self):
        if self.peer_socket: # Only allow one peer for simplicity
            new_socket = self.tcp_server.nextPendingConnection()
            new_socket.disconnectFromHost()
            new_socket.waitForDisconnected(1000)
            self.status_changed.emit("Rejected new connection: already have a peer.")
            return

        self.peer_socket = self.tcp_server.nextPendingConnection()
        self.peer_socket.readyRead.connect(self._read_data)
        self.peer_socket.disconnected.connect(self._on_peer_disconnected)
        self.status_changed.emit(f"Peer connected from {self.peer_socket.peerAddress().toString()}:{self.peer_socket.peerPort()}")
        self.peer_connected.emit()
        self.buffer[self.peer_socket] = "" # Initialize buffer for new peer

    @Slot()
    def _on_connected(self):
        self.status_changed.emit(f"Connected to host {self.tcp_socket.peerAddress().toString()}:{self.tcp_socket.peerPort()}")
        self.peer_connected.emit()
        self.buffer[self.tcp_socket] = "" # Initialize buffer for client socket

    @Slot()
    def _on_disconnected(self):
        self.status_changed.emit("Disconnected from host.")
        self.peer_disconnected.emit()
        if self.tcp_socket in self.buffer:
            del self.buffer[self.tcp_socket]

    @Slot()
    def _on_peer_disconnected(self):
        if self.peer_socket:
            self.peer_socket.deleteLater()
            if self.peer_socket in self.buffer:
                del self.buffer[self.peer_socket]
            self.peer_socket = None
        self.status_changed.emit("Peer disconnected.")
        self.peer_disconnected.emit()

    @Slot()
    def _read_data(self):
        sender_socket = self.sender() # Get the socket that emitted the signal
        if isinstance(sender_socket, QTcpSocket):
            raw_data = sender_socket.readAll().data()
            # Decode raw data and append to buffer for the specific socket
            decoded_data = raw_data.decode('utf-8', errors='ignore')
            print(f"5. readyRead triggered. Received raw data: {decoded_data}")
            
            self.buffer[sender_socket] += decoded_data
            
            # Process messages from the buffer
            while '\n' in self.buffer[sender_socket]:
                message_str, self.buffer[sender_socket] = self.buffer[sender_socket].split('\n', 1)
                if not message_str.strip(): # Handle empty lines
                    continue
 
                try:
                    message = json.loads(message_str)
                    print(f"6. Parsed message in NetworkManager: {message}")
                    msg_type = message.get('type')
                    if msg_type == 'TEXT_UPDATE':
                        content = message.get('content', '')
                        print(f"7. Emitting data_received with content: {content[:50]}...")
                        self.data_received.emit(content)
                    elif msg_type == 'REQ_CONTROL':
                        self.control_request_received.emit()
                    elif msg_type == 'GRANT_CONTROL':
                        self.control_granted.emit()
                    elif msg_type == 'DECLINE_CONTROL':
                        self.control_declined.emit()
                    elif msg_type == 'REVOKE_CONTROL':
                        self.control_revoked.emit()
                    else:
                        print(f"NetworkManager: Unknown message type received: {msg_type}")
                except json.JSONDecodeError:
                    print(f"NetworkManager: Received non-JSON data or incomplete JSON in buffer: {message_str}")
                except Exception as e:
                    print(f"NetworkManager: Error processing received data from buffer: {e}")

    def send_data(self, message_type, content=None):
        print(f"LOG: NetworkManager.send_data - Entry, Type: {message_type}")
        message = {'type': message_type}
        if content is not None:
            message['content'] = content
        
        # Add a newline delimiter to ensure messages are properly separated for buffering
        json_message = json.dumps(message) + '\n'
        data = QByteArray(json_message.encode('utf-8'))
        print(f"3. Formatting message: {json_message.strip()}") # Strip newline for cleaner log
 
        # Determine which socket to use based on whether we are a client or a server
        target_socket = None
        if self.tcp_socket and self.tcp_socket.state() == QTcpSocket.ConnectedState:
            target_socket = self.tcp_socket # We are the client, sending to host
        elif self.peer_socket and self.peer_socket.state() == QTcpSocket.ConnectedState:
            target_socket = self.peer_socket # We are the host, sending to peer
 
        if target_socket:
            try:
                target_socket.write(data)
                print(f"4. Data written to socket.")
                print(f"LOG: NetworkManager.send_data - Data sent via {target_socket.objectName()}: {message_type}")
            except Exception as e:
                print(f"LOG: NetworkManager.send_data - Error writing to socket: {e}")
                self.status_changed.emit(f"Network error: {e}")
        else:
            print("LOG: NetworkManager.send_data - No active connection to send data.")
        print("LOG: NetworkManager.send_data - Exit")

    def is_connected(self):
        return self.tcp_socket.state() == QTcpSocket.ConnectedState or \
               (self.peer_socket and self.peer_socket.state() == QTcpSocket.ConnectedState)