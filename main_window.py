# main_window.py
# This file defines the MainWindow class, which is the main user interface
# for the Simple Collaborative Editor. It integrates the text editor,
# menu actions, status bar, and the NetworkManager for handling
# collaborative sessions (both hosting and joining).

import sys
import black # For code formatting
import jedi # For code completion
from pyflakes.api import check as pyflakes_check
from pyflakes.reporter import Reporter as PyflakesReporter
from PySide6.QtWidgets import (
    QMainWindow, QPlainTextEdit, QMessageBox, QApplication, QStatusBar, QCompleter
)
from PySide6.QtGui import QAction, QKeySequence, QTextCursor, QTextCharFormat, QColor, QKeyEvent # Added QTextCharFormat, QColor, QKeyEvent
from PySide6.QtCore import Slot, Qt, QObject, Signal, QStringListModel, QTimer, QEvent # Added QTimer, QEvent
from PySide6.QtNetwork import QTcpSocket # For type hinting in MockNetworkManager

# Import custom modules for networking and connection dialog
from network_manager import NetworkManager
from connection_dialog import ConnectionDialog
from custom_python_highlighter import PythonHighlighter # Import the highlighter


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
        self.editor.installEventFilter(self) # Install event filter for auto-pairing

        # Syntax Highlighter
        self.highlighter = PythonHighlighter(self.editor.document())

        # Code Completer
        self.completer = QCompleter(self)
        self.completer.setWidget(self.editor) # Attach to editor
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive) # Or CaseSensitive
        self.completer_model = QStringListModel(self)
        self.completer.setModel(self.completer_model)
        # Connect activated signal to insert completion
        self.completer.activated.connect(self._insert_completion) 
        
        # Note: Event filter for advanced trigger removed for simplicity in this version.
        # Completion is triggered by Ctrl+Space menu action or '.' in _on_editor_text_changed.

        # Live Linting
        self.linting_errors_extra_selections = []
        self.linting_timer = QTimer(self)
        self.linting_timer.setSingleShot(True) # Important: run only once after delay
        self.linting_timer.setInterval(1000)  # 1000 ms delay
        self.linting_timer.timeout.connect(self._run_linter)
        # Connect textChanged to restart the timer (use a dedicated slot for clarity)
        self.editor.textChanged.connect(self._on_text_changed_for_linting)

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
        self.menu_bar = self.menuBar() # QMainWindow creates a menu bar if one doesn't exist.
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

        # --- Edit Menu ---
        edit_menu = self.menu_bar.addMenu("&Edit")
        self.format_code_action = QAction("&Format Code", self)
        self.format_code_action.setShortcut(QKeySequence("Ctrl+Alt+L"))
        self.format_code_action.triggered.connect(self._format_code)
        edit_menu.addAction(self.format_code_action)

        self.completion_action = QAction("Show Co&mpletions", self)
        self.completion_action.setShortcut(QKeySequence("Ctrl+Space"))
        self.completion_action.triggered.connect(self._show_completion)
        edit_menu.addAction(self.completion_action)


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
        
        # --- Network Data Sending ---
        # Check if there's an active network session to send data to.
        is_host_with_clients = self.network_manager._is_server and self.network_manager.server_client_sockets
        is_connected_client = (not self.network_manager._is_server and 
                               self.network_manager.client_socket and 
                               self.network_manager.client_socket.state() == QTcpSocket.ConnectedState)

        if is_host_with_clients or is_connected_client:
            current_text = self.editor.toPlainText()
            self.network_manager.send_data(current_text)
            # self.status_bar.showMessage("Sent update.", 1000) # Optional: can be too frequent

        # --- Simplified Completion Trigger on dot (part of _on_editor_text_changed) ---
        # This is a basic way to trigger completions after a '.' is typed.
        # It checks if the completer popup is already visible to avoid redundant calls.
        # Also, ensure not to trigger during network updates or if editor is read-only for client.
        if not self._is_updating_from_network and not self.editor.isReadOnly():
            if not self.completer.popup().isVisible():
                cursor = self.editor.textCursor()
                if cursor.position() > 0:
                    # Move cursor back one character, keep anchor to select the char
                    cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor, 1)
                    char_before = cursor.selectedText() # Get the selected character
                    # Move cursor back to original position without selection
                    # We need to restore the cursor to its original position before checking char_before
                    original_cursor_pos = cursor.position() -1 # Position before PreviousCharacter
                    cursor.clearSelection()
                    cursor.setPosition(original_cursor_pos + 1) # Back to where it was after typing '.'
                    
                    if char_before == '.':
                        self._show_completion()
    
    @Slot()
    def _on_text_changed_for_linting(self):
        """Restarts the linting timer whenever text is changed by the user."""
        # Do not lint if the change came from network sync, or if client is view-only
        if self._is_updating_from_network or (not self.network_manager._is_server and self.editor.isReadOnly()):
            return
        self.linting_timer.start()

    def _insert_paired_character(self, opening_char: str, closing_char: str):
        """
        Inserts the opening and closing characters, wrapping selected text
        if any, or placing the cursor between them if no selection.
        """
        cursor = self.editor.textCursor()

        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            # Begin and end edit block for undo/redo atomicity (optional but good practice)
            # cursor.beginEditBlock()
            cursor.insertText(opening_char + selected_text + closing_char)
            # cursor.endEditBlock()
            # The cursor is automatically positioned after the inserted text.
        else:
            # cursor.beginEditBlock()
            cursor.insertText(opening_char + closing_char)
            cursor.movePosition(QTextCursor.PreviousCharacter) # Move between the pair
            # cursor.endEditBlock()

        self.editor.setTextCursor(cursor) # Apply cursor changes

    def _handle_key_press_for_auto_pair(self, event: QKeyEvent) -> bool:
        """
        Handles key presses for auto-pairing of characters.
        Inserts paired characters like (), [], {}, "", ''.
        Includes smart logic for quotes to skip over existing closing quote.

        Args:
            event (QKeyEvent): The key event.

        Returns:
            bool: True if the key press was handled, False otherwise.
        """
        key_text = event.text()
        pairs = { # Define pairs locally or as a class attribute if shared
            '(': ')',
            '[': ']',
            '{': '}',
            '"': '"',
            "'": "'"
        }

        cursor = self.editor.textCursor()
        original_cursor_pos = cursor.position() # For restoring cursor if needed

        # Smart Quotes Logic: If typing a quote and the next char is the same quote, just skip.
        if key_text in ('"', "'"):
            # Temporarily move cursor to check character after current position
            temp_cursor = QTextCursor(cursor) # Create a copy to avoid moving the main cursor yet
            temp_cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, 1)
            char_after = temp_cursor.selectedText()

            if char_after == key_text:
                # Just move the actual cursor forward one position
                cursor.movePosition(QTextCursor.NextCharacter)
                self.editor.setTextCursor(cursor)
                return True # Event handled by skipping

        # General Auto-Pairing for opening characters
        if key_text in pairs:
            # Smart Brackets/Parentheses (Optional - deferred for now as per instructions)
            # Example of how it could be:
            # if key_text in ('(', '[', '{'):
            #     temp_cursor = QTextCursor(cursor)
            #     temp_cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, 1)
            #     char_after = temp_cursor.selectedText()
            #     if char_after == pairs[key_text]: # If closing pair is already there
            #         cursor.movePosition(QTextCursor.NextCharacter)
            #         self.editor.setTextCursor(cursor)
            #         return True # Event handled by skipping

            # Proceed with inserting the pair
            self._insert_paired_character(key_text, pairs[key_text])
            return True # Event handled by inserting pair

        return False # Event not handled by auto-pair logic

    def eventFilter(self, obj, event: QEvent) -> bool:
        """
        Filters events for the editor, specifically to handle key presses
        for auto-pairing characters.
        """
        if obj is self.editor and event.type() == QEvent.KeyPress:
            # The event should be a QKeyEvent, as QEvent.KeyPress corresponds to it.
            # No explicit cast needed if methods of QKeyEvent are directly accessed on 'event',
            # but _handle_key_press_for_auto_pair expects QKeyEvent.
            # Python's dynamic typing handles this; if it's not a QKeyEvent with 'text()',
            # _handle_key_press_for_auto_pair would raise an AttributeError.
            if self._handle_key_press_for_auto_pair(event): # event is QKeyEvent
                return True # Event was handled, stop further processing

        # Pass the event to the base class implementation for default processing
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """
        Overrides QMainWindow.closeEvent.
        Ensures any active network session (hosting or client) is cleanly
        stopped before the application window closes.
        """
        self.status_bar.showMessage("Closing session...") # Brief message
        self.network_manager.stop_session() # Tell NetworkManager to clean up
        super().closeEvent(event) # Proceed with the normal close event

    @Slot()
    def _format_code(self):
        """Formats the code in the editor using the 'black' library."""
        current_text = self.editor.toPlainText()
        if not current_text.strip():
            self.status_bar.showMessage("Nothing to format.", 3000)
            return

        try:
            # Store old cursor position (line and column relative to line start)
            cursor = self.editor.textCursor()
            original_pos_in_block = cursor.positionInBlock()
            original_block_number = cursor.blockNumber() # Line number (0-indexed)

            # Use black to format the code
            # FileMode ensures Black treats the input as a complete file.
            formatted_text = black.format_str(current_text, mode=black.FileMode())
            
            if formatted_text == current_text: # Check if black made any changes
                self.status_bar.showMessage("Code is already well-formatted.", 3000)
                return

            # Update editor content
            # This will trigger textChanged, which is desired to propagate formatted code.
            self.editor.setPlainText(formatted_text) 

            # Attempt to restore cursor position
            # This is an approximation and might not be perfect due to text changes.
            new_cursor = self.editor.textCursor()
            if original_block_number < self.editor.document().blockCount():
                new_block = self.editor.document().findBlockByNumber(original_block_number)
                # Calculate new position within the potentially modified line
                new_pos_in_block = min(original_pos_in_block, new_block.length() -1)
                new_pos_in_block = max(0, new_pos_in_block) # Ensure it's not negative if line became empty

                new_pos = new_block.position() + new_pos_in_block
                new_cursor.setPosition(new_pos)
            else: # Fallback if original line number is now out of bounds (e.g. file shortened drastically)
                new_cursor.movePosition(QTextCursor.End)
            self.editor.setTextCursor(new_cursor)
            
            self.status_bar.showMessage("Code formatted successfully.", 3000)

        except black.NothingChanged:
            self.status_bar.showMessage("Code is already well-formatted (Black: Nothing changed).", 3000)
        except black.InvalidInput as e: # Catches errors like syntax errors Black can't handle
            QMessageBox.warning(self, "Formatting Error", f"Could not format code due to invalid input: {e}")
            self.status_bar.showMessage("Formatting error: Invalid input.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Formatting Error", f"An unexpected error occurred during formatting: {e}")
            self.status_bar.showMessage(f"Formatting error: {e}", 3000)

    # --- Code Completion Methods ---
    @Slot()
    def _show_completion(self):
        """Shows completion suggestions based on current code and cursor position."""
        # Do not show completions if in client view-only mode or if network update is happening
        if (self.network_manager.client_socket and not self.network_manager._is_server and self.editor.isReadOnly()) \
           or self._is_updating_from_network:
            self.completer.popup().hide()
            return

        text = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        
        # Determine prefix for completion for QCompleter
        cursor_pos_in_block = cursor.positionInBlock()
        current_line_text = cursor.block().text()
        
        prefix_start = cursor_pos_in_block
        while prefix_start > 0:
            char = current_line_text[prefix_start - 1]
            # Valid characters for a Python identifier part or a dot for attribute access
            if not (char.isalnum() or char == '_' or char == '.'):
                break
            prefix_start -= 1
        current_prefix = current_line_text[prefix_start:cursor_pos_in_block]
        self.completer.setCompletionPrefix(current_prefix)

        # Jedi uses 1-based indexing for line and 0-based for column
        line_num = cursor.blockNumber() + 1
        col_num = cursor.positionInBlock() # Jedi's column is where completion is requested (0-indexed)

        try:
            # Using a dummy path "temp_script.py" helps Jedi provide context-aware completions,
            # especially if project-level analysis or virtual environments are involved,
            # though for simple single-file context, it's less critical.
            script = jedi.Script(code=text, path="temp_script.py") 
            completions = script.complete(line=line_num, column=col_num)
        except Exception as e:
            print(f"Jedi completion error: {e}") # Log to console for debugging
            self.status_bar.showMessage(f"Code completion error: {e}", 2000)
            completions = []

        if not completions:
            self.completer.popup().hide() # Hide popup if no completions found
            return

        # Extract completion names for the QCompleter model
        completion_list = [comp.name for comp in completions] 
        self.completer_model.setStringList(completion_list)
        
        if self.completer.completionCount() > 0:
            # Position the completer popup below the cursor
            cr = self.editor.cursorRect() # Gets QRect for the cursor
            # Adjust width to be useful
            cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                        self.completer.popup().verticalScrollBar().sizeHint().width() + 20) # Add some padding
            self.completer.complete(cr) # Show completions at cursor rect
        else:
            self.completer.popup().hide()

    @Slot(str) 
    def _insert_completion(self, completion_text: str): 
        """
        Inserts the selected completion into the editor, replacing the current prefix.
        Args:
            completion_text (str): The string selected from the completer popup.
        """
        if self._is_updating_from_network: # Should not happen if editor is read-only or events are filtered
            return

        cursor = self.editor.textCursor()
        
        # Number of characters of the completion_text that are already typed (the prefix)
        prefix_len = len(self.completer.completionPrefix())
        # The part of the completion string that needs to be inserted
        text_to_insert = completion_text[prefix_len:]
        
        # Manually construct the edit operation for better control over textChanged signal
        # This avoids _on_editor_text_changed from potentially misinterpreting this.
        # However, for simplicity, direct insertion is often fine if _is_updating_from_network
        # is robustly handled or if this action should indeed trigger a network send.
        # For now, let's assume this local edit *should* be propagated if in a session.
        
        # Move cursor back by the length of the prefix to delete it
        # cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor, prefix_len)
        # cursor.removeSelectedText() # Remove the prefix
        # cursor.insertText(completion_text) # Insert the full completion

        # Simpler: QCompleter might handle prefix replacement if widget is fully compatible.
        # For QPlainTextEdit, manual insertion is more reliable.
        # The activated signal gives the full word. We need to replace the prefix.
        
        # Move cursor back to select the prefix.
        cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(self.completer.completionPrefix()))
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(self.completer.completionPrefix()))
        cursor.insertText(completion_text) # Replace selected prefix with full completion

        self.editor.setTextCursor(cursor)
        self.completer.popup().hide() # Ensure popup is hidden after insertion

    # --- Live Linting Methods ---
    def _clear_linting_highlights(self):
        """Clears all current linting error highlights."""
        self.linting_errors_extra_selections.clear()
        self.editor.setExtraSelections(self.linting_errors_extra_selections) # Pass empty list

    @Slot()
    def _run_linter(self):
        """Runs pyflakes linter on the current editor content and highlights errors."""
        # Do not run linter if client is in view-only mode
        if not self.network_manager._is_server and self.editor.isReadOnly():
            self._clear_linting_highlights()
            return

        current_text = self.editor.toPlainText()
        if not current_text.strip(): # Don't lint empty or whitespace-only text
            self._clear_linting_highlights()
            return

        reporter = CustomPyflakesReporter()
        try:
            # Pyflakes checks the code. "temp_script.py" is a dummy filename.
            pyflakes_check(current_text, "temp_script.py", reporter=reporter)
        except Exception as e:
            print(f"Pyflakes execution error: {e}") 
            self.status_bar.showMessage(f"Linter execution error: {e}", 3000)
            return

        self._clear_linting_highlights() # Clear previous highlights

        if not reporter.errors:
            # self.status_bar.showMessage("No linting issues found.", 2000) # Can be noisy
            return
        
        # self.status_bar.showMessage(f"{len(reporter.errors)} linting issue(s) found.", 2000) # Also noisy

        new_selections = []
        for error in reporter.errors:
            selection = QPlainTextEdit.ExtraSelection() 

            error_format = QTextCharFormat()
            error_format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            error_format.setUnderlineColor(QColor("red"))
            error_format.setToolTip(error['message']) # Show error message on hover
            
            selection.format = error_format
            
            line_number = error['lineno'] - 1 
            if line_number < 0: line_number = 0 

            block = self.editor.document().findBlockByNumber(line_number)
            if block.isValid():
                cursor = QTextCursor(block)
                # Highlight the whole line for simplicity.
                # For more precise highlighting, one would use error['col']
                # and potentially highlight only the specific token/word.
                cursor.movePosition(QTextCursor.StartOfLine)
                # Attempt to highlight a specific part if col info is useful, else whole line.
                # Pyflakes 'col' is 0-indexed offset into the line.
                col_start = error.get('col', 0)
                # Try to find a sensible length for the error, e.g., one word or fixed length.
                # This is a simplification. True error length is harder.
                error_length = 1 
                if 'text' in error and error['text']: # If pyflakes provides the offending text line
                    # Try to find the length of the token if possible, very simplified
                    # This part is non-trivial to get right for all error types.
                    # For now, let's highlight a small segment from the column or whole line.
                    line_text = block.text()
                    token_match = QRegularExpression(r"\b\w+\b").match(line_text, col_start)
                    if token_match.hasMatch():
                        error_length = token_match.capturedLength()
                    else: # Fallback to highlighting a few chars or the whole line
                        error_length = max(1, min(5, len(line_text) - col_start))


                if col_start < block.length(): # Ensure column is within line
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, col_start)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, error_length)
                else: # Fallback to whole line if column info is problematic
                    cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)

                selection.cursor = cursor
                new_selections.append(selection)
            else: 
                print(f"Linter: Invalid block for line number {error['lineno']}")

        self.linting_errors_extra_selections = new_selections
        self.editor.setExtraSelections(self.linting_errors_extra_selections)


# --- Custom Pyflakes Reporter ---
class CustomPyflakesReporter(PyflakesReporter):
    """
    A custom Pyflakes reporter to collect errors in a structured list
    instead of printing them to stdout/stderr.
    """
    def __init__(self):
        # Initialize with dummy streams as we don't use them.
        super().__init__(None, None) 
        self.errors = [] # List to store found errors

    def unexpectedError(self, filename, msg):
        """Handles unexpected errors during Pyflakes analysis."""
        self.errors.append({'message': msg, 'lineno': 0, 'col': 0, 'type': 'unexpected'})

    def syntaxError(self, filename, msg, lineno, offset, text):
        """Handles syntax errors found by Pyflakes."""
        self.errors.append({
            'message': msg, 
            'lineno': lineno, 
            'col': offset if offset is not None else 0, # offset can be None
            'text': text, 
            'type': 'syntax'
        })

    def flake(self, message_obj): # Pyflakes Message object
        """Handles Pyflakes messages (warnings/errors like undefined names, unused imports)."""
        # The message_obj has attributes like .lineno, .col, and .message (which is a format string).
        # .message_args contains the arguments for the format string.
        self.errors.append({
            'message': str(message_obj.message % message_obj.message_args), 
            'lineno': message_obj.lineno, 
            'col': message_obj.col, 
            'type': 'flake'
        })


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
