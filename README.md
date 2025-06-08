# Code-Sync IDE (Simple Collab - Multi-file)

## Overview

Code-Sync IDE (Simple Collab) is a basic real-time collaborative text editor built using Python and the PySide6 GUI framework. It demonstrates fundamental concepts of network programming with `QTcpServer` and `QTcpSocket` to allow two users to edit a document simultaneously. One user acts as the "host" (server), and the other connects as a "client".

This multi-file version structures the application into logical components for better organization:
- UI management (`main_window.py`)
- Network communication (`network_manager.py`)
- Connection input (`connection_dialog.py`)
- Application entry (`main.py`)
- Python syntax highlighting (`python_highlighter.py`)

## Prerequisites

To run this application, you need:

1.  **Python 3:** Version 3.7 or newer is recommended.
2.  **PySide6:** The Qt for Python library.
    ```bash
    pip install PySide6
    ```
3.  **Jedi:** For code completion.
    ```bash
    pip install jedi
    ```
4.  **Pyflakes:** For live linting (error detection).
    ```bash
    pip install pyflakes
    ```
5.  **Black:** For on-demand code formatting.
    ```bash
    pip install black
    ```
    
    You can also install all Python dependencies at once:
    ```bash
    pip install PySide6 jedi pyflakes black
    ```

## Project Structure

The project consists of the following Python files:

*   `main.py`: The main entry point to launch the application.
*   `main_window.py`: Defines the `MainWindow` class, which sets up the main user interface (editor, menus, status bar) and handles user interactions, advanced editor features, and UI updates based on network events.
*   `network_manager.py`: Contains the `NetworkManager` class, responsible for all networking logic. This includes starting a TCP server (for hosting), connecting to a server (as a client), sending and receiving data, and managing connection states.
*   `connection_dialog.py`: Defines the `ConnectionDialog` class, a simple dialog window used by the client to input the host's IP address and port number.
*   `python_highlighter.py`: Defines the `PythonHighlighter` class for syntax highlighting in the editor.

## Features

*   **Real-time Collaborative Text Editing:** Supports a host/client model for live text synchronization over a local network. The current simple version focuses on a single shared editor view for collaboration.
*   **Python Syntax Highlighting:** Real-time highlighting of Python code elements (keywords, comments, strings, numbers, definitions).
*   **Code Completion (IntelliSense):** Provides code completion suggestions via `Ctrl+Space` or automatically after typing a dot (`.`). Powered by the Jedi library.
*   **Real-time Error Detection (Live Linting):** Underlines potential errors and syntax issues in Python code as you type, with error messages available on hover. Powered by the Pyflakes library.
*   **On-Demand Code Formatting:** Allows formatting of the entire Python script in the editor using the Black code formatter. This is accessible via the "Edit" -> "Format Code" menu item or the `Ctrl+Alt+L` shortcut.
*   **Session Management:** Menu-driven actions for starting hosting sessions, connecting to hosts, and stopping the current session.
*   **Connection Dialog:** A user-friendly dialog for inputting host IP and port details.
*   **Status Bar Feedback:** Provides messages to the user about network status, application state, and outcomes of actions.
*   **Modular Design:** Code is organized into separate modules for UI, networking, dialogs, and syntax highlighting for better maintainability.

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

### 4. Test Collaboration & Editor Features

   a.  **Host to Client:** Type Python code in the **Host** application's editor. Observe syntax highlighting. The text should appear in real-time in the **Client** application's editor (also with highlighting).
   b.  **Client to Host (Bi-directional Editing):** The default implementation sets the client's editor to read-only. To enable bi-directional editing:
        *   Modify `main_window.py`: In the `_handle_peer_connected` method, comment out or set to `False` the line `self.editor.setReadOnly(True)` for the client.
        *   If enabled, typing in the client's editor will send changes to the host.
   c.  **Code Completion:** In an active editor (e.g., Host, or Client if not read-only), type Python code (e.g., `import sys; sys.`) and then type a dot `.` or press `Ctrl+Space` to trigger completion suggestions.
   d.  **Live Linting:** Type syntactically incorrect Python code (e.g., `foo = bar +`) or undefined variable names. After a short delay, errors should be underlined with a red wavy line. Hover over the underline to see the error message.
   e.  **Code Formatting:** Type some unformatted Python code. Select **Edit -> Format Code** (or press `Ctrl+Alt+L`). The code should be formatted according to Black's style. The formatted code will be sent to the other peer if in a session.
   f.  **Loop Prevention:** Verify that typing and receiving updates, or formatting code, doesn't cause infinite feedback loops.

### 5. Test Disconnecting

   a.  **Using "Stop Current Session":**
       *   In either the Host or Client window, click **Session -> Stop Current Session**.
       *   The session should end. Status bars should update. Menu items should reset. The client's editor (if read-only) should become writable.
   b.  **Closing a Window:**
       *   If the **Client** window is closed, the **Host** status bar should update. The host remains ready for new connections.
       *   If the **Host** window is closed, the **Client** should detect disconnection and reset its UI.

## How it Works (Briefly)

*   **Client-Server Architecture:** Uses `QTcpServer` and `QTcpSocket` (via `NetworkManager`) for a host-client model.
*   **Network Communication:** Full editor text is sent on changes, UTF-8 encoded.
*   **Synchronization & Loop Prevention:** The `_is_updating_from_network` flag in `main_window.py` prevents re-broadcasting received network updates.
*   **Editor Features:**
    *   `python_highlighter.py` uses `QSyntaxHighlighter` for syntax coloring.
    *   `jedi` library provides code intelligence for completions, displayed via `QCompleter`.
    *   `pyflakes` library checks code for errors, which are then displayed using `QPlainTextEdit.ExtraSelection`.
    *   `black` library is used for on-demand code formatting.

This application provides a basic framework for collaborative text editing with several advanced IDE features. More advanced synchronization (OT/CRDT) and protocol design would be needed for more robust multi-user collaboration.
