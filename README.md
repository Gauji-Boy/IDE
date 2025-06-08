# Code-Sync IDE (Simple Collab - Multi-file)

## Overview

Code-Sync IDE (Simple Collab) is a basic real-time collaborative text editor built using Python and the PySide6 GUI framework. It demonstrates fundamental concepts of network programming with `QTcpServer` and `QTcpSocket` to allow two users to edit a document simultaneously. One user acts as the "host" (server), and the other connects as a "client".

This multi-file version structures the application into logical components for better organization:
- UI management (`main_window.py`)
- Network communication (`network_manager.py`)
- Connection input (`connection_dialog.py`)
- Application entry (`main.py`)

## Prerequisites

To run this application, you need:

1.  **Python 3:** Version 3.7 or newer is recommended.
2.  **PySide6:** The Qt for Python library. Install it using pip:
    ```bash
    pip install PySide6
    ```

## Project Structure

The project consists of the following Python files:

*   `main.py`: The main entry point to launch the application.
*   `main_window.py`: Defines the `MainWindow` class, which sets up the main user interface (editor, menus, status bar) and handles user interactions and UI updates based on network events.
*   `network_manager.py`: Contains the `NetworkManager` class, responsible for all networking logic. This includes starting a TCP server (for hosting), connecting to a server (as a client), sending and receiving data, and managing connection states.
*   `connection_dialog.py`: Defines the `ConnectionDialog` class, a simple dialog window used by the client to input the host's IP address and port number.

## Running the Application & Testing Collaboration

Follow these steps to run two instances of the application on the same machine and test the collaborative functionality:

### 1. Instance 1 (Host)

   a.  **Open your terminal or command prompt.**
   b.  **Navigate to the directory** where you have saved the project files (`main.py`, `main_window.py`, etc.).
       ```bash
       cd path/to/your/project_directory
       ```
   c.  **Run the application:**
       ```bash
       python main.py
       ```
   d.  A window titled "Code-Sync IDE (Simple Collab)" will appear.
   e.  In this first window, go to the menu: **Session -> Start Hosting Session**.
   f.  Observe the status bar at the bottom of the window. It should update to indicate it's hosting, typically: *"Hosting on 127.0.0.1:54321. Waiting for connection..."*.
       The "Start Hosting Session" and "Connect to Host..." menu items should become disabled, and "Stop Current Session" should become enabled.

### 2. Instance 2 (Client)

   a.  **Open a *new* (second) terminal or command prompt.**
   b.  **Navigate to the *same* project directory** as before.
       ```bash
       cd path/to/your/project_directory
       ```
   c.  **Run the application again:**
       ```bash
       python main.py
       ```
   d.  A second "Code-Sync IDE (Simple Collab)" window will appear. This will be your client instance.

### 3. Connect Client to Host

   a.  In the **second application window (Client)**, go to the menu: **Session -> Connect to Host...**.
   b.  A "Connect to Host" dialog will pop up.
   c.  The default IP address (`127.0.0.1`) and port (`54321`) should be correct for local testing. Click **"OK"**.
   d.  Observe the status bars:
       *   **Client Window:** Should update to *"Peer connected. Collaboration active."*. The window title may also change to indicate "Client (View-Only)".
       *   **Host Window:** Should update to *"Peer connected. Collaboration active."* (or similar, indicating a client has connected). The window title may change to "Host".
   e.  On the client, the "Start Hosting Session" and "Connect to Host..." menu items should become disabled, and "Stop Current Session" should become enabled. The editor area will become read-only by default.

### 4. Test Collaboration

   a.  **Host to Client:** Type some text in the **Host** application's editor. The text should appear in real-time (or very close to it) in the **Client** application's editor.
   b.  **Client to Host (Bi-directional Editing):** The default implementation in `main_window.py` sets the client's editor to read-only upon connection (`self.editor.setReadOnly(True)` in `_handle_peer_connected`).
        *   To enable bi-directional editing where the client can also send changes, you would comment out or set to `False` the `self.editor.setReadOnly(True)` line for the client in `main_window.py`'s `_handle_peer_connected` method.
        *   If bi-directional editing is enabled, typing in the client's editor will send changes to the host, and they should appear in the host's editor.
   c.  **Loop Prevention:** Verify that typing in one editor doesn't cause an infinite feedback loop where text rapidly duplicates or causes errors. The `_is_updating_from_network` flag in `main_window.py` is designed to prevent this.

### 5. Test Disconnecting

   a.  **Using "Stop Current Session":**
       *   In either the Host or Client window, click **Session -> Stop Current Session**.
       *   The session should end. The status bar in both windows should update to reflect disconnection (e.g., "Session stopped..." or "Peer disconnected...").
       *   Menu items ("Start Hosting Session", "Connect to Host...") should become enabled again in both windows, and "Stop Current Session" disabled.
       *   The client's editor (if it was read-only) should become writable again.
   b.  **Closing a Window:**
       *   If you close the **Client** window, the **Host** window's status bar should update to indicate the client has disconnected. The host will remain in hosting mode, ready for a new client (in this simple version).
       *   If you close the **Host** window, the **Client** window should detect the disconnection, show a message (e.g., "Disconnected from host" or a connection error), and reset its UI to a non-connected state.

## How it Works (Briefly)

*   **Client-Server Architecture:** The application uses a simple client-server model. One instance acts as the host (server) using `QTcpServer` (managed by `NetworkManager`), listening for incoming connections. Other instances act as clients using `QTcpSocket` (managed by `NetworkManager`) to connect to the host.
*   **Network Communication:** Data (the full editor text) is sent between the host and client(s) over TCP/IP sockets. Text is UTF-8 encoded for transmission.
*   **Synchronization:** When text changes in one editor, the new full text is sent to the peer(s). The `NetworkManager` handles the sending and receiving, emitting signals to the `MainWindow` to update the UI or process data.
*   **Loop Prevention:** A flag (`_is_updating_from_network` in `main_window.py`) is used to prevent feedback loops. When an editor's text is updated due to an incoming network message, this flag is set. The `MainWindow`'s `_on_editor_text_changed` signal handler checks this flag; if set, it means the change was from the network, so it doesn't send the text back out again.

This application provides a basic framework for collaborative text editing. More advanced features like operational transformation (OT) or conflict-free replicated data types (CRDTs), along with a more robust protocol (e.g., using `QDataStream` for message framing), would be needed for more sophisticated multi-user collaboration, especially for handling concurrent edits without sending the full document on every change.
