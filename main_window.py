# main_window.py
# This file defines the MainWindow class, which is the main user interface
# for the Simple Collaborative Editor. It integrates the text editor,
# menu actions, status bar, execution controls, output panels,
# and the NetworkManager for handling collaborative sessions.

import sys
import black # For code formatting
import tempfile
import os
import shlex # For robust command splitting if needed, though shell execution is simpler for &&

from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QApplication, QStatusBar,
    QToolBar, QComboBox, QDockWidget, QTabWidget, QPlainTextEdit,
    QSizePolicy, QVBoxLayout, QPushButton, QHBoxLayout, QWidget
)
from PySide6.QtGui import QAction, QKeySequence, QTextCursor, QIcon, QFont, QActionGroup, QKeyEvent
from PySide6.QtCore import QEvent
from PySide6.QtCore import (
    Slot, Qt, QObject, Signal, QProcess, QFileInfo, QDir, QStandardPaths, QEvent
) # Added QProcess, QFileInfo, QDir, QStandardPaths, QEvent
from PySide6.QtNetwork import QTcpSocket

# Import custom modules
from network_manager import NetworkManager
from connection_dialog import ConnectionDialog
from code_editor import CodeEditor
from python_highlighter import PythonHighlighter
from app_config import RUNNER_CONFIG

class MainWindow(QMainWindow):
    DEFAULT_PORT = 54321

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Code-Sync IDE (Simple Collab)")
        self.setGeometry(100, 100, 900, 700)

        self.editor = CodeEditor()
        self.setCentralWidget(self.editor)
        self.highlighter = PythonHighlighter(self.editor.document())

        self.run_destination = "Output Panel"
        self.runner_config = RUNNER_CONFIG
        self.process = None  # For QProcess
        self.current_temp_file_path = None # For temp file cleanup
        self.current_output_file_path = None # For C++/Java compiled output cleanup


        self.network_manager = NetworkManager(self)
        self._is_updating_from_network = False

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Start or connect to a session.")

        self._setup_toolbar()
        self._setup_output_dock()
        self._setup_menus()
        self._connect_network_signals()

        self.editor.textChanged.connect(self._on_editor_text_changed_for_network)

    def _setup_toolbar(self):
        toolbar = QToolBar("Execution Toolbar")
        self.addToolBar(toolbar)

        self.language_selector = QComboBox()
        self.language_selector.addItems(self.runner_config.keys())
        toolbar.addWidget(self.language_selector)

        self.run_action = QAction(QIcon.fromTheme("media-playback-start", QIcon(":/icons/run.png")), "&Run Code", self) # Placeholder icon path
        self.run_action.setToolTip("Run the current code (F5)")
        self.run_action.triggered.connect(self._trigger_run_code) # Connect run action
        toolbar.addAction(self.run_action)

    def _setup_output_dock(self):
        self.output_dock = QDockWidget("Output / Terminal", self)
        self.output_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self.output_dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)

        self.output_tabs = QTabWidget()
        self.output_tabs.setMinimumHeight(150)

        self.output_panel_te = QPlainTextEdit()
        self.output_panel_te.setReadOnly(True)
        self.output_tabs.addTab(self.output_panel_te, "Output")

        self.terminal_panel_te = QPlainTextEdit()
        term_font = QFont("Courier New", 10)
        if sys.platform == "darwin": term_font.setFamily("Monaco")
        elif sys.platform == "win32": term_font.setFamily("Consolas")
        else: term_font.setFamily("Monospace")
        self.terminal_panel_te.setFont(term_font)
        self.terminal_panel_te.setStyleSheet("background-color: #2E2E2E; color: #E0E0E0; padding: 5px;")
        self.output_tabs.addTab(self.terminal_panel_te, "Terminal")

        self.output_dock.setWidget(self.output_tabs)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.output_dock)

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

        edit_menu = self.menu_bar.addMenu("&Edit")
        self.format_code_action = QAction("&Format Code", self)
        self.format_code_action.setShortcut(QKeySequence("Ctrl+Alt+L"))
        self.format_code_action.triggered.connect(self._format_code)
        edit_menu.addAction(self.format_code_action)

        run_menu = self.menu_bar.addMenu("&Run")
        self.run_action.setShortcut(QKeySequence("F5")) # self.run_action is already created in _setup_toolbar
        run_menu.addAction(self.run_action)
        run_menu.addSeparator()
        run_destination_group = QActionGroup(self)
        run_destination_group.setExclusive(True)
        self.output_dest_action = QAction("Output Panel", self, checkable=True)
        self.output_dest_action.setChecked(self.run_destination == "Output Panel")
        self.output_dest_action.triggered.connect(lambda: self._set_run_destination("Output Panel"))
        run_menu.addAction(self.output_dest_action)
        run_destination_group.addAction(self.output_dest_action)
        self.terminal_dest_action = QAction("Integrated Terminal", self, checkable=True)
        self.terminal_dest_action.setChecked(self.run_destination == "Terminal")
        self.terminal_dest_action.triggered.connect(lambda: self._set_run_destination("Terminal"))
        run_menu.addAction(self.terminal_dest_action)
        run_destination_group.addAction(self.terminal_dest_action)

    def _set_run_destination(self, destination: str):
        self.run_destination = destination
        if destination == "Output Panel": self.output_dest_action.setChecked(True)
        elif destination == "Terminal": self.terminal_dest_action.setChecked(True)
        self.status_bar.showMessage(f"Run destination set to: {destination}", 2000)

    def _trigger_run_code(self):
        if self.process is not None and self.process.state() == QProcess.Running:
            reply = QMessageBox.question(self, "Process Running",
                                         "A process is already running. Stop it?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.process.kill()
                self.process.waitForFinished(1000) # Give it a moment to die
                # _handle_process_finished will set self.process to None
            else:
                return
        self._execute_current_code()

    def _execute_current_code(self):
        selected_language = self.language_selector.currentText()
        lang_config = self.runner_config.get(selected_language)

        if not lang_config:
            self.status_bar.showMessage(f"Language '{selected_language}' not configured for running.", 5000)
            return

        code = self.editor.toPlainText()
        if not code.strip():
            self.status_bar.showMessage("No code to run.", 3000)
            return

        # Cleanup previous temp files (if any)
        self._cleanup_temp_files()

        temp_dir = QStandardPaths.writableLocation(QStandardPaths.TempLocation)
        if not temp_dir: # Fallback if standard temp location is not available
            temp_dir = tempfile.gettempdir()

        try:
            temp_file_suffix = lang_config["ext"]
            # delete=False is crucial as the file is used by another process
            with tempfile.NamedTemporaryFile(mode="w", suffix=temp_file_suffix,
                                             delete=False, encoding='utf-8', dir=temp_dir) as temp_file:
                self.current_temp_file_path = temp_file.name
                temp_file.write(code)
                # temp_file.close() is handled by with statement exit
        except Exception as e:
            self.status_bar.showMessage(f"Error creating temp file: {e}", 5000)
            return

        command_template = list(lang_config["cmd"]) # Make a copy
        processed_command = []

        file_path = self.current_temp_file_path
        file_info = QFileInfo(file_path)
        file_dir = file_info.absolutePath()
        file_name_no_ext = file_info.completeBaseName()

        self.current_output_file_path = None # Reset
        if lang_config.get("output_based"):
             # Use temp_dir for output file as well to ensure writability
            self.current_output_file_path = os.path.join(temp_dir, file_name_no_ext)


        for part in command_template:
            part = part.replace("{file}", file_path)
            part = part.replace("{dir}", file_dir) # For Java -cp
            part = part.replace("{class_name}", file_name_no_ext) # For Java class name
            if self.current_output_file_path:
                 part = part.replace("{output_file_no_ext}", self.current_output_file_path)
            processed_command.append(part)

        # Prepare output area
        if self.run_destination == "Output Panel":
            self.output_tabs.setCurrentWidget(self.output_panel_te)
            self.output_panel_te.clear()
            self.output_panel_te.appendPlainText(f"Running: {' '.join(processed_command)}\n---")
        else: # Terminal
            self.output_tabs.setCurrentWidget(self.terminal_panel_te)
            # For terminal, we might not clear, just append
            self.terminal_panel_te.appendPlainText(f"\n[{file_dir}]$ {' '.join(processed_command)}")

        self.process = QProcess(self)
        self.process.setWorkingDirectory(file_dir) # Important for relative paths in code/commands
        self.process.readyReadStandardOutput.connect(self._handle_process_output)
        self.process.readyReadStandardError.connect(self._handle_process_error)
        self.process.finished.connect(self._handle_process_finished)

        # Execution strategy for "&&"
        command_str_for_shell = ""
        use_shell = False
        if "&&" in processed_command:
            use_shell = True
            # Join parts carefully, especially if some parts contain spaces
            # shlex.join might be good here if we weren't passing to shell directly
            command_str_for_shell = ' '.join(shlex.quote(part) for part in processed_command)

        if use_shell:
            if sys.platform == "win32":
                self.process.start("cmd", ["/C", command_str_for_shell])
            else: # Unix-like (Linux, macOS)
                self.process.start("sh", ["-c", command_str_for_shell])
        else:
            program = processed_command[0]
            arguments = processed_command[1:]
            self.process.start(program, arguments)

        if not self.process.waitForStarted(2000): # Timeout for process start
            error_message = self.process.errorString() if self.process.error() != QProcess.UnknownError else "Process failed to start (unknown error)."
            self._append_to_output_or_terminal(f"Error starting process: {error_message}\n")
            self._handle_process_finished(-1, QProcess.CrashExit) # Simulate finish with error


    def _handle_process_output(self):
        if not self.process: return
        data = self.process.readAllStandardOutput().data().decode(errors='replace')
        self._append_to_output_or_terminal(data)

    def _handle_process_error(self):
        if not self.process: return
        data = self.process.readAllStandardError().data().decode(errors='replace')
        self._append_to_output_or_terminal(data, is_error=True)

    def _append_to_output_or_terminal(self, text: str, is_error: bool = False):
        if self.run_destination == "Output Panel":
            # Could add color for errors here if desired, e.g. self.output_panel_te.setTextColor(QColor("red"))
            self.output_panel_te.insertPlainText(text)
            # self.output_panel_te.setTextColor(QColor("black")) # Reset color
        else: # Terminal
            self.terminal_panel_te.insertPlainText(text) # Terminal might handle colors via ANSI escapes if it were a full terminal


    def _handle_process_finished(self, exit_code, exit_status):
        status_message = f"\n--- Process finished with exit code {exit_code}."
        if exit_status == QProcess.CrashExit:
            status_message += " (Crashed)"
        elif exit_status == QProcess.NormalExit:
             status_message += " (Normal Exit)"

        self._append_to_output_or_terminal(status_message)

        # Cleanup is now handled by _cleanup_temp_files, called before next run or on close
        # self._cleanup_temp_files() # Or call it here

        if self.process: # Ensure self.process still exists
            self.process.deleteLater() # Schedule QProcess for deletion
        self.process = None


    def _cleanup_temp_files(self):
        # Remove code temp file
        if self.current_temp_file_path and os.path.exists(self.current_temp_file_path):
            try:
                os.remove(self.current_temp_file_path)
                # print(f"Cleaned up temp file: {self.current_temp_file_path}")
            except OSError as e:
                print(f"Error removing temp file {self.current_temp_file_path}: {e}")
        self.current_temp_file_path = None

        # Remove compiled output file (if any)
        if self.current_output_file_path and os.path.exists(self.current_output_file_path):
            try:
                os.remove(self.current_output_file_path)
                # print(f"Cleaned up output file: {self.current_output_file_path}")
            except OSError as e:
                print(f"Error removing output file {self.current_output_file_path}: {e}")

        # For Windows, .exe might be generated for C++
        if self.current_output_file_path and sys.platform == "win32" and os.path.exists(self.current_output_file_path + ".exe"):
            try:
                os.remove(self.current_output_file_path + ".exe")
            except OSError as e:
                 print(f"Error removing output file {self.current_output_file_path}.exe: {e}")
        self.current_output_file_path = None


    def _connect_network_signals(self):
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
        current_text = self.editor.toPlainText()
        if not current_text.strip():
            self.status_bar.showMessage("Nothing to format.", 3000)
            return
        try:
            cursor = self.editor.textCursor()
            original_pos = cursor.position()
            formatted_text = black.format_str(current_text, mode=black.FileMode())
            if formatted_text == current_text:
                self.status_bar.showMessage("Code is already well-formatted.", 3000)
                return
            self._is_updating_from_network = True
            self.editor.setPlainText(formatted_text)
            self._is_updating_from_network = False
            new_cursor = self.editor.textCursor()
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
        # Kill running process if any
        if self.process is not None and self.process.state() == QProcess.Running:
            self.status_bar.showMessage("Stopping running process...")
            self.process.kill()
            self.process.waitForFinished(1000) # Wait a bit

        # Cleanup temp files
        self._cleanup_temp_files()

        # Stop network session
        self.status_bar.showMessage("Closing session...")
        self.network_manager.stop_session()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    class MockNetworkManager(QObject):
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
        def send_data(self, text): print(f"Mock send: {text[:20]}")
        def stop_session(self): self.peer_disconnected.emit()
    
    window = MainWindow()
    # window.network_manager = MockNetworkManager(window)
    # window._connect_network_signals()
    window.show()
    sys.exit(app.exec())
