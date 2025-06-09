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
from PySide6.QtGui import QAction, QKeySequence, QTextCursor, QIcon, QFont, QActionGroup
from PySide6.QtCore import (
    Slot, Qt, QObject, Signal, QProcess, QFileInfo, QDir, QStandardPaths
) # Added QProcess, QFileInfo, QDir, QStandardPaths
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
