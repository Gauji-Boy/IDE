# Ensure PyQt5 is installed: pip install PyQt5

import sys
import socket
import socketserver
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QTreeView, QFileSystemModel, QTabWidget, QPushButton,
    QDockWidget, QFileDialog, QAction, QMenu, QMessageBox, QInputDialog
)
from PyQt5.QtCore import QDir, Qt, QProcess, QRegExp, pyqtSignal, QObject, QMetaObject, Q_ARG
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QBrush

# Syntax Highlighter Class
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.highlighting_rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("blue"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "False", "None", "True", "and", "as", "assert", "async", "await",
            "break", "class", "continue", "def", "del", "elif", "else",
            "except", "finally", "for", "from", "global", "if", "import",
            "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
            "return", "try", "while", "with", "yield"
        ]
        for word in keywords:
            pattern = QRegExp(f"\\b{word}\\b")
            rule = (pattern, keyword_format)
            self.highlighting_rules.append(rule)

        # Built-ins (simplified list)
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("darkMagenta"))
        builtins = ["print", "len", "str", "int", "list", "dict", "set", "tuple", "range", "open"]
        for word in builtins:
            pattern = QRegExp(f"\\b{word}\\b")
            rule = (pattern, builtin_format)
            self.highlighting_rules.append(rule)

        # Decorators
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("darkGray"))
        decorator_format.setFontItalic(True)
        self.highlighting_rules.append((QRegExp("@[\w_]+"), decorator_format))


        # Single-quoted strings
        sq_string_format = QTextCharFormat()
        sq_string_format.setForeground(QColor("green"))
        self.highlighting_rules.append((QRegExp("'[^']*'"), sq_string_format))

        # Double-quoted strings
        dq_string_format = QTextCharFormat()
        dq_string_format.setForeground(QColor("green"))
        self.highlighting_rules.append((QRegExp("\"([^\"\\\\]|\\\\.)*\""), dq_string_format))


        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("darkRed"))
        self.highlighting_rules.append((QRegExp("\\b[0-9]+\\.?[0-9]*\\b"), number_format))
        self.highlighting_rules.append((QRegExp("\\b0x[0-9a-fA-F]+\\b"), number_format))

        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("red"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((QRegExp("#[^\n]*"), comment_format))

        self.tri_single_quote_start_expression = QRegExp("'''")
        self.tri_double_quote_start_expression = QRegExp("\"\"\"")
        self.tri_quote_format = QTextCharFormat()
        self.tri_quote_format.setForeground(QColor("darkGreen"))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, fmt)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        startIndex = 0
        if self.previousBlockState() != 1:
            startIndex = self.tri_single_quote_start_expression.indexIn(text)

        while startIndex >= 0:
            endIndex = self.tri_single_quote_start_expression.indexIn(text, startIndex + 3)
            if endIndex == -1:
                self.setCurrentBlockState(1)
                length = len(text) - startIndex
            else:
                length = endIndex - startIndex + 3
            self.setFormat(startIndex, length, self.tri_quote_format)
            startIndex = self.tri_single_quote_start_expression.indexIn(text, startIndex + length)

        if self.currentBlockState() != 1 :
            startIndex_dq = 0
            if self.previousBlockState() != 2:
                 startIndex_dq = self.tri_double_quote_start_expression.indexIn(text)

            while startIndex_dq >= 0:
                endIndex_dq = self.tri_double_quote_start_expression.indexIn(text, startIndex_dq + 3)
                if endIndex_dq == -1:
                    self.setCurrentBlockState(2)
                    length_dq = len(text) - startIndex_dq
                else:
                    length_dq = endIndex_dq - startIndex_dq + 3
                self.setFormat(startIndex_dq, length_dq, self.tri_quote_format)
                startIndex_dq = self.tri_double_quote_start_expression.indexIn(text, startIndex_dq + length_dq)


class IDEApplication(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simple IDE")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.open_files = {}

        self.current_editor = None
        self.process = None

        self.is_hosting = False
        self.collab_server = None
        self.collab_server_thread = None
        self.collab_clients = []

        self.is_client_connected = False
        self.collab_client_socket = None
        self.collab_client_thread = None
        self.collab_view_editor = None
        self.client_signals = ClientReceiverSignals()
        self.client_signals.text_received.connect(self._update_collab_editor_content)
        self.client_signals.connection_lost.connect(self._handle_unexpected_disconnect_ui)

        self._create_menus()
        self._create_file_explorer()
        self._create_editor_tabs()
        self._create_terminal_dock()

        self._disconnect_edit_menu_actions() # Call once to set initial states correctly


    def _create_menus(self):
        file_menu = self.menuBar().addMenu("&File")
        new_action = QAction("&New", self)
        new_action.triggered.connect(self._new_file)
        file_menu.addAction(new_action)
        open_action = QAction("&Open", self)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)
        self.save_action = QAction("&Save", self)
        self.save_action.triggered.connect(self._save_file)
        file_menu.addAction(self.save_action)
        self.save_as_action = QAction("Save &As...", self)
        self.save_as_action.triggered.connect(self._save_file_as)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        self.cut_action = QAction("Cu&t", self)
        edit_menu.addAction(self.cut_action)
        self.copy_action = QAction("&Copy", self)
        edit_menu.addAction(self.copy_action)
        self.paste_action = QAction("&Paste", self)
        edit_menu.addAction(self.paste_action)

        run_menu = self.menuBar().addMenu("&Run")
        self.run_script_action = QAction("Run Current &Script", self)
        self.run_script_action.setShortcut("F5")
        self.run_script_action.triggered.connect(self._run_current_script)
        run_menu.addAction(self.run_script_action)

        view_menu = self.menuBar().addMenu("&View")
        self.toggle_file_explorer_action = QAction("File E&xplorer", self, checkable=True)
        self.toggle_file_explorer_action.setChecked(True)
        self.toggle_file_explorer_action.triggered.connect(self._toggle_file_explorer_dock)
        view_menu.addAction(self.toggle_file_explorer_action)
        self.toggle_terminal_action = QAction("&Terminal", self, checkable=True)
        self.toggle_terminal_action.setChecked(True)
        self.toggle_terminal_action.triggered.connect(self._toggle_terminal_dock)
        view_menu.addAction(self.toggle_terminal_action)

        collab_menu = self.menuBar().addMenu("&Collaboration")
        self.host_session_action = QAction("Start &Hosting Session", self, checkable=True)
        self.host_session_action.toggled.connect(self._toggle_hosting_session)
        collab_menu.addAction(self.host_session_action)
        self.join_session_action = QAction("&Join Hosting Session", self, checkable=True)
        self.join_session_action.toggled.connect(self._toggle_join_session)
        collab_menu.addAction(self.join_session_action)


    def _create_file_explorer(self):
        self.file_explorer_dock = QDockWidget("File Explorer", self)
        self.file_explorer_dock.setObjectName("FileExplorerDock")
        self.file_explorer_dock.visibilityChanged.connect(lambda visible: self.toggle_file_explorer_action.setChecked(visible))
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(QDir.currentPath())
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(QDir.currentPath()))
        self.file_tree.setAnimated(False)
        self.file_tree.setIndentation(20)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.header().setSectionResizeMode(0, QTreeView.ResizeToContents)
        self.file_tree.doubleClicked.connect(self._handle_file_tree_double_click)
        self.file_explorer_dock.setWidget(self.file_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_explorer_dock)

    def _open_file_dialog(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*);;Python Files (*.py);;Text Files (*.txt)", options=options)
        if file_path:
            self._open_file(file_path)

    def _handle_file_tree_double_click(self, index):
        file_path = self.file_model.filePath(index)
        if not self.file_model.isDir(index):
            self._open_file(file_path)

    def _create_editor_tabs(self):
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self._close_tab)
        self.editor_tabs.currentChanged.connect(self._update_current_editor)
        self.main_layout.addWidget(self.editor_tabs)

    def _update_current_editor(self, index):
        if index != -1:
            widget = self.editor_tabs.widget(index)
            if isinstance(widget, QTextEdit):
                self.current_editor = widget
                self._connect_edit_menu_actions()
            else:
                self.current_editor = None
                self._disconnect_edit_menu_actions()
        else:
            self.current_editor = None
            self._disconnect_edit_menu_actions()

    def _connect_edit_menu_actions(self):
        is_editor_active = self.current_editor and isinstance(self.current_editor, QTextEdit)

        self.cut_action.setEnabled(is_editor_active)
        self.copy_action.setEnabled(is_editor_active)
        self.paste_action.setEnabled(is_editor_active)

        if is_editor_active:
            try:
                self.cut_action.triggered.disconnect()
                self.copy_action.triggered.disconnect()
                self.paste_action.triggered.disconnect()
            except TypeError:
                pass # Not connected is fine
            self.cut_action.triggered.connect(self.current_editor.cut)
            self.copy_action.triggered.connect(self.current_editor.copy)
            self.paste_action.triggered.connect(self.current_editor.paste)

            is_modified = self.current_editor.document().isModified()
            self.save_action.setEnabled(is_modified)
            self.save_as_action.setEnabled(True)

            current_file_path = self.editor_tabs.tabToolTip(self.editor_tabs.currentIndex())
            is_python_file = current_file_path and current_file_path.endswith(".py") and not current_file_path.startswith("Untitled-")
            is_process_not_running = self.process is None or self.process.state() == QProcess.NotRunning

            can_run_script = is_python_file and is_process_not_running and not self.is_client_connected
            self.run_script_action.setEnabled(can_run_script)

            if self.is_client_connected and self.current_editor == self.collab_view_editor:
                self.cut_action.setEnabled(False)
                self.paste_action.setEnabled(False)
                self.save_action.setEnabled(False)
                self.save_as_action.setEnabled(False)
                self.run_script_action.setEnabled(False) # Cannot run script in view-only collab mode
        else:
            self._disconnect_edit_menu_actions()

    def _disconnect_edit_menu_actions(self):
        self.cut_action.setEnabled(False)
        self.copy_action.setEnabled(False)
        self.paste_action.setEnabled(False)
        self.save_action.setEnabled(False)
        self.save_as_action.setEnabled(False)
        if hasattr(self, 'run_script_action'):
            self.run_script_action.setEnabled(False)
        try:
            self.cut_action.triggered.disconnect()
            self.copy_action.triggered.disconnect()
            self.paste_action.triggered.disconnect()
        except TypeError:
            pass

    def _open_file(self, file_path):
        if not file_path:
            return
        for i in range(self.editor_tabs.count()):
            if self.editor_tabs.tabToolTip(i) == file_path:
                self.editor_tabs.setCurrentIndex(i)
                return
        editor = QTextEdit()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            editor.setPlainText(content)
            editor.document().setModified(False)
            editor.textChanged.connect(self._mark_current_tab_as_modified)
            if file_path.endswith(".py"):
                # Store highlighter on the editor itself to manage its lifecycle if needed
                editor.highlighter = PythonHighlighter(editor.document())
        except Exception as e:
            QMessageBox.warning(self, "Error Reading File", f"Could not read file: {file_path}\n{e}")
            return
        file_name = file_path.split('/')[-1]
        index = self.editor_tabs.addTab(editor, file_name)
        self.editor_tabs.setTabToolTip(index, file_path)
        self.editor_tabs.setCurrentIndex(index)
        self.open_files[file_path] = editor

    def _mark_current_tab_as_modified(self):
        if not self.current_editor or not isinstance(self.current_editor, QTextEdit):
            return
        current_tab_index = self.editor_tabs.currentIndex()
        if current_tab_index == -1:
            return
        title = self.editor_tabs.tabText(current_tab_index)
        if not title.endswith('*'):
            self.editor_tabs.setTabText(current_tab_index, title + '*')
        self.save_action.setEnabled(True)
        self.current_editor.document().setModified(True)

    def _save_file(self):
        if not self.current_editor or not isinstance(self.current_editor, QTextEdit):
            # This case should ideally be prevented by disabling the save_action
            QMessageBox.warning(self, "Warning", "No active editor to save.")
            return
        current_tab_index = self.editor_tabs.currentIndex()
        if current_tab_index == -1: return
        file_path = self.editor_tabs.tabToolTip(current_tab_index)
        if not file_path or file_path.startswith("Untitled-"):
            self._save_file_as()
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.current_editor.toPlainText())
            title = self.editor_tabs.tabText(current_tab_index)
            if title.endswith('*'):
                self.editor_tabs.setTabText(current_tab_index, title[:-1])
            self.current_editor.document().setModified(False)
            self.save_action.setEnabled(False)
            QMessageBox.information(self, "Success", f"File '{file_path.split('/')[-1]}' saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", f"Could not save file: {file_path}\n{e}")

    def _close_tab(self, index):
        editor_widget = self.editor_tabs.widget(index)
        file_path = self.editor_tabs.tabToolTip(index)

        if editor_widget and isinstance(editor_widget, QTextEdit) and editor_widget.document().isModified():
            tab_title = self.editor_tabs.tabText(index)
            if not tab_title.endswith('*'): tab_title += '*'
            reply = QMessageBox.question(self, 'Save Changes?',
                                         f"Do you want to save changes to {tab_title.replace('*','')}?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                # If the tab to close is the current tab, _save_file works.
                # If not, we need to make it current to save, or implement saving non-current.
                # For simplicity, if it's not current, we'll just try to save it if we have path.
                original_current_index = self.editor_tabs.currentIndex()
                self.editor_tabs.setCurrentIndex(index) # Make it current to use self.current_editor logic

                if self._save_file() == False : # _save_file_as might return False on cancel
                    self.editor_tabs.setCurrentIndex(original_current_index) # Restore original tab
                    return # Don't close if save was cancelled

                if self.editor_tabs.widget(index).document().isModified(): # Check if save actually worked
                    self.editor_tabs.setCurrentIndex(original_current_index) # Restore original tab
                    return # Don't close tab if save failed or was cancelled by user
                # If save was successful, it will fall through to removeTab
                self.editor_tabs.setCurrentIndex(original_current_index) # Restore original tab before removing other

            elif reply == QMessageBox.Cancel:
                return
        self.editor_tabs.removeTab(index)
        if file_path and file_path in self.open_files :
            del self.open_files[file_path]
        elif file_path and file_path.startswith("Untitled-") and editor_widget in self.open_files.values():
            for k, v in list(self.open_files.items()):
                if v == editor_widget:
                    del self.open_files[k]
                    break
        if self.editor_tabs.count() == 0:
            self.current_editor = None
            self._disconnect_edit_menu_actions()

    def closeEvent(self, event):
        if self.is_hosting:
            self._stop_hosting_session()
        if self.is_client_connected:
            self._stop_client_session("Application closing.")

        for i in range(self.editor_tabs.count() -1, -1, -1): # Iterate backwards for safe removal
            self.editor_tabs.setCurrentIndex(i) # Set current tab to check its state
            editor_widget = self.editor_tabs.widget(i)
            if editor_widget and isinstance(editor_widget, QTextEdit) and editor_widget.document().isModified():
                reply = QMessageBox.question(self, 'Save Changes?',
                                             f"Do you want to save changes to {self.editor_tabs.tabText(i).replace('*','')} before exiting?",
                                             QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                if reply == QMessageBox.Save:
                    if self._save_file() == False : # if save_file_as was cancelled
                         event.ignore()
                         return
                    if self.current_editor.document().isModified(): # If save failed
                        event.ignore()
                        return
                elif reply == QMessageBox.Cancel:
                    event.ignore()
                    return
                elif reply == QMessageBox.Discard :
                    pass # Continue closing
        super().closeEvent(event)

    def _new_file(self):
        untitled_count = 1
        existing_titles = [self.editor_tabs.tabText(i) for i in range(self.editor_tabs.count())]
        while f"Untitled-{untitled_count}" in existing_titles or f"Untitled-{untitled_count}*" in existing_titles :
            untitled_count += 1
        new_editor = QTextEdit()
        new_editor.textChanged.connect(self._mark_current_tab_as_modified)
        tab_title = f"Untitled-{untitled_count}"
        index = self.editor_tabs.addTab(new_editor, tab_title)
        self.editor_tabs.setTabToolTip(index, tab_title)
        self.editor_tabs.setCurrentIndex(index)
        self.open_files[tab_title] = new_editor
        self.current_editor = new_editor
        self._connect_edit_menu_actions()
        self.save_as_action.setEnabled(True)

    def _save_file_as(self):
        if not self.current_editor or not isinstance(self.current_editor, QTextEdit):
            return False # Should be prevented by UI state
        current_tab_index = self.editor_tabs.currentIndex()
        if current_tab_index == -1: return False
        options = QFileDialog.Options()
        new_file_path, _ = QFileDialog.getSaveFileName(self, "Save File As...", "",
                                                       "All Files (*);;Python Files (*.py);;Text Files (*.txt)",
                                                       options=options)
        if not new_file_path:
            return False
        old_file_path_key = self.editor_tabs.tabToolTip(current_tab_index)
        try:
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write(self.current_editor.toPlainText())
            new_file_name = new_file_path.split('/')[-1]
            self.editor_tabs.setTabText(current_tab_index, new_file_name)
            self.editor_tabs.setTabToolTip(current_tab_index, new_file_path)
            self.current_editor.document().setModified(False)
            self.save_action.setEnabled(False)
            if new_file_path.endswith(".py") and isinstance(self.current_editor, QTextEdit):
                if not hasattr(self.current_editor, 'highlighter'): # Add highlighter if not present
                     self.current_editor.highlighter = PythonHighlighter(self.current_editor.document())
            # Update self.open_files
            if old_file_path_key and old_file_path_key in self.open_files:
                if old_file_path_key != new_file_path :
                    del self.open_files[old_file_path_key]
            self.open_files[new_file_path] = self.current_editor
            QMessageBox.information(self, "Success", f"File '{new_file_name}' saved successfully.")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", f"Could not save file: {new_file_path}\n{e}")
            return False

    # --- Collaboration Methods ---
    def _toggle_hosting_session(self, checked):
        if checked:
            if not self._start_hosting_session():
                self.host_session_action.setChecked(False)
            else:
                self.host_session_action.setText("Stop Hosting Session")
                self.join_session_action.setEnabled(False) # Added
        else:
            self._stop_hosting_session()
            self.host_session_action.setText("Start Hosting Session")
            self.join_session_action.setEnabled(True) # Added

    def _start_hosting_session(self):
        if self.is_hosting:
            self.terminal_output_view.append("Already hosting a session.")
            return True
        HOST, PORT = "localhost", 9999
        try:
            socketserver.TCPServer.allow_reuse_address = True
            self.collab_server = ThreadingCollaborationServer((HOST, PORT), CollaborationRequestHandler, ide_instance=self)
            self.collab_server_thread = threading.Thread(target=self.collab_server.serve_forever)
            self.collab_server_thread.daemon = True
            self.collab_server_thread.start()
            self.is_hosting = True
            self.terminal_output_view.append(f"Hosting session started on {HOST}:{PORT}")
            if self.current_editor:
                self.current_editor.textChanged.connect(self._broadcast_text_change)
            self.editor_tabs.currentChanged.connect(self._handle_host_tab_changed)
            return True
        except Exception as e:
            self.terminal_output_view.append(f"Error starting hosting session: {e}")
            QMessageBox.critical(self, "Hosting Error", f"Could not start hosting session: {e}")
            self.is_hosting = False
            return False

    def _stop_hosting_session(self):
        if not self.is_hosting or not self.collab_server:
            self.terminal_output_view.append("Not currently hosting a session.")
            return
        self.is_hosting = False
        if self.current_editor:
            try: self.current_editor.textChanged.disconnect(self._broadcast_text_change)
            except TypeError: pass
        try: self.editor_tabs.currentChanged.disconnect(self._handle_host_tab_changed)
        except TypeError: pass
        self.terminal_output_view.append("Stopping hosting session...")
        for client_handler in list(self.collab_clients):
            try:
                client_handler.request.sendall(b"Server is shutting down.\n--EOT--\n")
                client_handler.request.shutdown(socket.SHUT_RDWR)
                client_handler.request.close()
            except Exception as e:
                self.terminal_output_view.append(f"Error closing client connection: {e}")
        self.collab_clients.clear()
        self.collab_server.shutdown()
        self.collab_server.server_close()
        self.collab_server_thread.join(timeout=2)
        self.collab_server = None
        self.collab_server_thread = None
        self.terminal_output_view.append("Hosting session stopped.")

    def _broadcast_text_change(self):
        if not self.is_hosting or not self.current_editor or not self.collab_clients:
            return
        try:
            full_text = self.current_editor.toPlainText()
            message = full_text.encode('utf-8') + b'\n--EOT--\n'
            disconnected_clients = []
            for client_handler in self.collab_clients:
                try: client_handler.request.sendall(message)
                except (BrokenPipeError, ConnectionResetError, OSError) as e:
                    self.terminal_output_view.append(f"Client disconnected or error sending: {e}. Removing client.")
                    disconnected_clients.append(client_handler)
                except Exception as e:
                    self.terminal_output_view.append(f"Unexpected error broadcasting to client: {e}")
                    disconnected_clients.append(client_handler)
            for client in disconnected_clients:
                if client in self.collab_clients:
                    self.collab_clients.remove(client)
        except Exception as e:
            self.terminal_output_view.append(f"Error preparing broadcast: {e}")

    def _handle_host_tab_changed(self, index):
        if not self.is_hosting: return
        # Disconnect from all tabs first to be safe
        for i in range(self.editor_tabs.count()):
            editor_widget = self.editor_tabs.widget(i)
            if editor_widget and isinstance(editor_widget, QTextEdit):
                try: editor_widget.textChanged.disconnect(self._broadcast_text_change)
                except TypeError: pass

        new_editor = self.editor_tabs.widget(index)
        if new_editor and isinstance(new_editor, QTextEdit):
            self.current_editor = new_editor # Update current_editor reference BEFORE connecting
            try: new_editor.textChanged.connect(self._broadcast_text_change)
            except TypeError: pass # Should not happen if disconnected properly
            self._broadcast_text_change()
        else:
            self.current_editor = None
            empty_message = "\n--EOT--\n".encode('utf-8')
            for client_handler in self.collab_clients:
                try: client_handler.request.sendall(empty_message)
                except Exception as e:
                    self.terminal_output_view.append(f"Error sending empty content: {e}")

    # --- Client Methods ---
    def _toggle_join_session(self, checked):
        if checked:
            if not self._start_client_session():
                self.join_session_action.setChecked(False)
            else:
                self.join_session_action.setText("Leave Session")
                self.host_session_action.setEnabled(False)
        else:
            self._stop_client_session("User left the session.")
            # Text and enabling host_session_action is handled in _stop_client_session

    def _start_client_session(self):
        if self.is_client_connected:
            self.terminal_output_view.append("Already connected to a session.")
            return True
        if not self.current_editor:
            QMessageBox.warning(self, "No Active Tab", "Please open or select a tab to display the collaborative session.")
            return False
        host_address_text, ok = QInputDialog.getText(self, "Join Host Session",
                                                     "Enter host address (e.g., localhost:9999):",
                                                     text="localhost:9999")
        if not ok or not host_address_text:
            self.terminal_output_view.append("Join session cancelled by user.")
            return False
        try:
            host_parts = host_address_text.split(':')
            if len(host_parts) != 2: raise ValueError("Invalid address format. Use hostname:port")
            HOST = host_parts[0].strip()
            PORT = int(host_parts[1].strip())
            if not HOST or PORT <= 0 or PORT > 65535: raise ValueError("Invalid hostname or port number.")
        except ValueError as ve:
            QMessageBox.warning(self, "Invalid Address", str(ve))
            self.terminal_output_view.append(f"Invalid host address input: {host_address_text}. Error: {ve}")
            return False
        self.terminal_output_view.append(f"Attempting to connect to {HOST}:{PORT}...")
        try:
            self.collab_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.collab_client_socket.connect((HOST, PORT))
            self.is_client_connected = True
            self.collab_view_editor = self.current_editor
            self.collab_view_editor.setReadOnly(True)
            current_tab_idx = self.editor_tabs.currentIndex()
            self.editor_tabs.setTabText(current_tab_idx, f"[VIEW] {self.editor_tabs.tabText(current_tab_idx)}")
            self.collab_client_thread = threading.Thread(target=self._listen_for_host_messages, daemon=True)
            self.collab_client_thread.start()
            self.terminal_output_view.append(f"Successfully connected to host at {HOST}:{PORT}. Editor is view-only.")
            self._connect_edit_menu_actions()
            return True
        except ConnectionRefusedError:
            self.terminal_output_view.append(f"Connection refused by host at {HOST}:{PORT}. Ensure the host is running and accessible.")
            QMessageBox.critical(self, "Connection Failed", f"Connection refused by host at {HOST}:{PORT}.\nEnsure the host is running and accessible.")
        except socket.gaierror:
             self.terminal_output_view.append(f"Hostname {HOST} could not be resolved.")
             QMessageBox.critical(self, "Connection Failed", f"Hostname {HOST} could not be resolved.")
        except Exception as e:
            self.terminal_output_view.append(f"Error connecting to host {HOST}:{PORT}: {e}")
            QMessageBox.critical(self, "Connection Error", f"Could not connect to host {HOST}:{PORT}: {e}")
        self.is_client_connected = False
        return False

    def _listen_for_host_messages(self):
        buffer = ""
        try:
            while self.is_client_connected and self.collab_client_socket:
                data_chunk = self.collab_client_socket.recv(4096)
                if not data_chunk:
                    if self.is_client_connected: # Only emit if not intentionally stopped
                        self.client_signals.connection_lost.emit("Host closed the connection.")
                    break
                buffer += data_chunk.decode('utf-8', errors='replace')
                while '\n--EOT--\n' in buffer:
                    message, buffer = buffer.split('\n--EOT--\n', 1)
                    self.client_signals.text_received.emit(message)
        except ConnectionResetError:
            if self.is_client_connected: self.client_signals.connection_lost.emit("Connection to host reset.")
        except OSError:
            if self.is_client_connected: self.client_signals.connection_lost.emit("Socket error during connection.")
        except Exception as e:
            if self.is_client_connected: self.client_signals.connection_lost.emit(f"Error receiving data: {e}")

        if self.is_client_connected: # Unexpected exit from loop
             QMetaObject.invokeMethod(self, "_handle_unexpected_disconnect_ui", Qt.QueuedConnection, Q_ARG(str, "Listener thread terminated."))


    def _update_collab_editor_content(self, text_content):
        if self.is_client_connected and self.collab_view_editor:
            h_scroll = self.collab_view_editor.horizontalScrollBar().value()
            v_scroll = self.collab_view_editor.verticalScrollBar().value()
            cursor = self.collab_view_editor.textCursor()
            cursor_pos = cursor.position()
            self.collab_view_editor.setPlainText(text_content)
            cursor.setPosition(min(cursor_pos, len(text_content)))
            self.collab_view_editor.setTextCursor(cursor)
            self.collab_view_editor.horizontalScrollBar().setValue(h_scroll)
            self.collab_view_editor.verticalScrollBar().setValue(v_scroll)

    def _stop_client_session(self, reason_message="Disconnected from host."):
        if not self.is_client_connected and not self.collab_client_socket and not self.collab_view_editor :
            return
        self.is_client_connected = False
        if self.collab_client_socket:
            try:
                self.collab_client_socket.shutdown(socket.SHUT_RDWR)
                self.collab_client_socket.close()
            except OSError: pass
            self.collab_client_socket = None
        if self.collab_client_thread and self.collab_client_thread.is_alive():
            self.collab_client_thread.join(timeout=0.5) # Reduced timeout
        self.collab_client_thread = None
        if self.collab_view_editor:
            self.collab_view_editor.setReadOnly(False)
            current_tab_idx = self.editor_tabs.indexOf(self.collab_view_editor)
            if current_tab_idx != -1:
                original_text = self.editor_tabs.tabText(current_tab_idx).replace("[VIEW] ", "")
                self.editor_tabs.setTabText(current_tab_idx, original_text)
            self.collab_view_editor = None
        self.terminal_output_view.append(f"{reason_message} Editor is now writable.")
        self.join_session_action.setChecked(False)
        self.join_session_action.setText("Join Hosting Session")
        self.host_session_action.setEnabled(True)
        self._connect_edit_menu_actions()

    def _handle_unexpected_disconnect_ui(self, message):
        # This method is invoked via signal from the listener thread OR directly if already in main thread
        if self.is_client_connected : # Check if we are still in client mode logically
             self._stop_client_session(f"Lost connection to host: {message}")
        elif self.join_session_action.isChecked(): # UI might still be checked
            self.join_session_action.setChecked(False)
            self.join_session_action.setText("Join Hosting Session")
            self.host_session_action.setEnabled(True)
            if self.collab_view_editor: self.collab_view_editor.setReadOnly(False) # Ensure editor is usable
            self.terminal_output_view.append(f"Disconnected: {message}. Editor is now writable.")


    def _create_terminal_dock(self):
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_dock.setObjectName("TerminalDock")
        self.terminal_dock.visibilityChanged.connect(lambda visible: self.toggle_terminal_action.setChecked(visible))
        terminal_widget = QWidget()
        terminal_layout = QVBoxLayout(terminal_widget)
        terminal_layout.setContentsMargins(2, 2, 2, 2)
        self.terminal_output_view = QTextEdit()
        self.terminal_output_view.setReadOnly(True)
        self.terminal_output_view.setFont(QFont("Courier New", 10))
        terminal_layout.addWidget(self.terminal_output_view)
        input_layout = QHBoxLayout()
        self.terminal_input_line = QLineEdit()
        self.terminal_input_line.setFont(QFont("Courier New", 10))
        self.terminal_input_line.returnPressed.connect(self._execute_terminal_command_line)
        self.terminal_run_line_button = QPushButton("Execute Line")
        self.terminal_run_line_button.clicked.connect(self._execute_terminal_command_line)
        input_layout.addWidget(self.terminal_input_line)
        input_layout.addWidget(self.terminal_run_line_button)
        terminal_layout.addLayout(input_layout)
        self.terminal_dock.setWidget(terminal_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.terminal_dock)

    def _execute_terminal_command_line(self):
        command = self.terminal_input_line.text().strip()
        if not command: return
        self.terminal_output_view.append(f"> {command}")
        self.terminal_output_view.append(f"[Shell Command Echo]: {command}\n")
        self.terminal_input_line.clear()
        self.terminal_input_line.setFocus()

    def _run_current_script(self):
        if not self.current_editor or not isinstance(self.current_editor, QTextEdit):
            self.terminal_output_view.append("No active editor tab selected to run.")
            return
        current_tab_index = self.editor_tabs.currentIndex()
        file_path = self.editor_tabs.tabToolTip(current_tab_index)
        if not file_path or file_path.startswith("Untitled-"):
            self.terminal_output_view.append("Please save the file before running.")
            QMessageBox.warning(self, "Save File", "The file must be saved before it can be run.")
            return
        if not file_path.endswith(".py"):
            self.terminal_output_view.append(f"Cannot run '{file_path.split('/')[-1]}'. It is not a Python script.")
            QMessageBox.warning(self, "Not a Python Script", "The current file is not a Python (.py) script.")
            return
        if self.process and self.process.state() == QProcess.Running:
            self.terminal_output_view.append("A script is already running. Please wait or stop it.")
            QMessageBox.information(self, "Process Running", "A script is already running.")
            return
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.finished.connect(self._handle_process_finished)
        self.process.errorOccurred.connect(self._handle_process_error)
        self.terminal_output_view.append("\n" + "="*30 + "\n")
        self.terminal_output_view.append(f"Running {file_path.split('/')[-1]}...\n" + "-"*20)
        python_executable = "python3"
        self.process.start(python_executable, [file_path])
        if self.process.state() == QProcess.NotRunning:
            self.terminal_output_view.append(f"Failed to start process with '{python_executable}'. Check interpreter path.\n")
            self._handle_process_error(self.process.error())
        else:
            self.run_script_action.setEnabled(False)

    def _handle_stdout(self):
        if not self.process: return
        data = self.process.readAllStandardOutput().data().decode(errors='ignore')
        self.terminal_output_view.insertPlainText(data)
        self.terminal_output_view.ensureCursorVisible()

    def _handle_stderr(self):
        if not self.process: return
        data = self.process.readAllStandardError().data().decode(errors='ignore')
        self.terminal_output_view.insertPlainText(data)
        self.terminal_output_view.ensureCursorVisible()

    def _handle_process_finished(self, exit_code, exit_status):
        status_text = "normally" if exit_status == QProcess.NormalExit else "with a crash"
        self.terminal_output_view.append("-"*20 + f"\nProcess finished {status_text}. Exit code: {exit_code}\n" + "="*30 + "\n")
        self.process = None # Clear before calling _connect_edit_menu_actions
        self.terminal_output_view.ensureCursorVisible()
        if self.current_editor : self._connect_edit_menu_actions() # Refresh run action state


    def _handle_process_error(self, error_code):
        if not self.process: return
        error_string = self.process.errorString()
        if error_code == QProcess.FailedToStart:
            if "python3" in error_string or "No such file or directory" in error_string:
                 detailed_error = f"Failed to start script. Ensure 'python3' is installed and in your system's PATH. Details: {error_string}"
            else:
                 detailed_error = f"Failed to start script. Details: {error_string}"
        else:
            error_map = {
                QProcess.Crashed: "crashed during execution", QProcess.Timedout: "timed out",
                QProcess.WriteError: "encountered a write error", QProcess.ReadError: "encountered a read error",
                QProcess.UnknownError: "encountered an unknown error"
            }
            status_description = error_map.get(error_code, f"encountered an error (code: {error_code})")
            detailed_error = f"Script execution {status_description}. Details: {error_string}"
        self.terminal_output_view.append(f"[ERROR] {detailed_error}\n")
        self.process = None # Clear before calling _connect_edit_menu_actions
        self.terminal_output_view.ensureCursorVisible()
        if self.current_editor: self._connect_edit_menu_actions() # Refresh run action state

    # --- UI Toggling Methods for Docks ---
    def _toggle_file_explorer_dock(self, checked):
        self.file_explorer_dock.setVisible(checked)

    def _toggle_terminal_dock(self, checked):
        self.terminal_dock.setVisible(checked)

# --- Collaboration Helper Classes ---
class ClientReceiverSignals(QObject):
    text_received = pyqtSignal(str)
    connection_lost = pyqtSignal(str)

class ThreadingCollaborationServer(socketserver.ThreadingTCPServer):
    def __init__(self, server_address, RequestHandlerClass, ide_instance):
        super().__init__(server_address, RequestHandlerClass)
        self.ide_instance = ide_instance

class CollaborationRequestHandler(socketserver.BaseRequestHandler):
    def setup(self):
        super().setup()
        self.ide_instance = self.server.ide_instance
        self.ide_instance.terminal_output_view.append(f"Client connected: {self.client_address}")
        self.ide_instance.collab_clients.append(self)
        if self.ide_instance.current_editor:
            try:
                full_text = self.ide_instance.current_editor.toPlainText()
                message = full_text.encode('utf-8') + b'\n--EOT--\n'
                self.request.sendall(message)
            except Exception as e:
                self.ide_instance.terminal_output_view.append(f"Error sending initial document to {self.client_address}: {e}")
    def handle(self):
        try:
            while True:
                data = self.request.recv(1024)
                if not data:
                    # self.ide_instance.terminal_output_view.append(f"Client {self.client_address} gracefully disconnected (received empty).")
                    break
        except ConnectionResetError:
            self.ide_instance.terminal_output_view.append(f"Client {self.client_address} connection reset.")
        except socketserver.socket.timeout:
            self.ide_instance.terminal_output_view.append(f"Client {self.client_address} timed out (if timeout was set).")
        except Exception as e:
            self.ide_instance.terminal_output_view.append(f"Error receiving from {self.client_address}: {e}")
    def finish(self):
        super().finish()
        if self in self.ide_instance.collab_clients:
            self.ide_instance.collab_clients.remove(self)
        self.ide_instance.terminal_output_view.append(f"Client disconnected: {self.client_address}. Remaining clients: {len(self.ide_instance.collab_clients)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Test Script for Run Functionality
    try:
        with open("test_script.py", "w") as f:
            f.write("print('Hello from test_script.py!')\n")
            f.write("import sys\n")
            f.write("print(f'Python version: {sys.version_info.major}.{sys.version_info.minor}')\n")
    except Exception as e:
        print(f"Could not create test_script.py: {e}")

    ide = IDEApplication()
    ide.show()
    sys.exit(app.exec_())
