# main_window.py
# This file defines the MainWindow class, which is the main user interface
# for the Simple Collaborative Editor. It integrates the text editor,
# menu actions, status bar, execution controls, output panels,
# and the NetworkManager for handling collaborative sessions.

import sys
import black # For code formatting
import tempfile
import os
import shlex 

from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QApplication, QStatusBar,
    QToolBar, QComboBox, QDockWidget, QTabWidget, QPlainTextEdit, 
    QSizePolicy, QVBoxLayout, QPushButton, QHBoxLayout, QWidget,
    QTreeView, QFileSystemModel, QFileDialog
)
from PySide6.QtGui import QAction, QKeySequence, QTextCursor, QIcon, QFont, QActionGroup
from PySide6.QtCore import (
    Slot, Qt, QObject, Signal, QProcess, QFileInfo, QDir, QStandardPaths
)
from PySide6.QtNetwork import QTcpSocket

# Import custom modules
from network_manager import NetworkManager # Or specific constants
from connection_dialog import ConnectionDialog
from code_editor import CodeEditor 
from custom_python_highlighter import PythonHighlighter
from config import RUNNER_CONFIG

class MainWindow(QMainWindow):
    DEFAULT_PORT = 54321
    untitled_tab_counter = 0 

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Code-Sync IDE") 
        self.setGeometry(100, 100, 1200, 800)

        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self._close_editor_tab)
        self.editor_tabs.currentChanged.connect(self._on_current_tab_changed)
        self.setCentralWidget(self.editor_tabs)
        
        self.run_destination = "Output Panel" 
        self.runner_config = RUNNER_CONFIG
        self.process = None
        self.current_temp_file_path = None
        self.current_output_file_path = None

        self.network_manager = NetworkManager(self)
        self._is_updating_from_network = False

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

        self._setup_file_explorer_dock() 
        self._setup_toolbar()    
        self._setup_output_dock() 
        self._setup_menus()      
        self._connect_network_signals()

        self.is_host = False
        self.has_control = False # Host starts with control, client without. This will be set properly later.
        self.session_active = False

        self.request_control_button = QPushButton("Request Control")
        self.request_control_button.setObjectName("requestControlButton") # For easier identification if needed
        self.request_control_button.setToolTip("Request editing control from the host")
        # Add to toolbar (example, might need a specific toolbar or status bar)
        # If you have a main toolbar, you can add it there:
        # self.main_toolbar.addWidget(self.request_control_button)
        # For now, let's add it to the status bar as it's simpler to ensure visibility.
        self.status_bar.addPermanentWidget(self.request_control_button)
        self.request_control_button.hide() # Initially hidden, shown for clients.

        # Connect clicked signal
        self.request_control_button.clicked.connect(self._request_control_button_clicked)
        
        self._add_new_editor_tab() # Start with one empty tab after all UI setup
        self._update_ui_for_control_state() # Initial UI state update

    @property
    def current_editor(self) -> CodeEditor | None:
        return self.editor_tabs.currentWidget()

    def _setup_file_explorer_dock(self):
        self.file_explorer_dock = QDockWidget("File Explorer", self)
        self.file_tree_view = QTreeView()
        self.file_system_model = QFileSystemModel()
        default_path = QDir.homePath() if QDir.homePath() else QDir.currentPath()
        self.file_system_model.setRootPath(default_path) 
        self.file_system_model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self.file_tree_view.setModel(self.file_system_model)
        self.file_tree_view.setRootIndex(self.file_system_model.index(default_path))
        self.file_tree_view.doubleClicked.connect(self._open_file_from_explorer)
        self.file_tree_view.setAnimated(False)
        self.file_tree_view.setIndentation(20)
        self.file_tree_view.setSortingEnabled(True)
        self.file_tree_view.sortByColumn(0, Qt.AscendingOrder)
        for i in range(1, self.file_system_model.columnCount()): # Hide all but name
            self.file_tree_view.setColumnHidden(i, True)
        self.file_explorer_dock.setWidget(self.file_tree_view)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_explorer_dock)

    def _add_new_editor_tab(self, file_path=None, content=""):
        editor = CodeEditor()
        highlighter = PythonHighlighter(editor.document())
        
        # Connect signals for this new editor instance
        editor.textChanged.connect(self._on_editor_text_changed_for_network)
        editor.document().modificationChanged.connect(self._update_window_title_and_tab_text)
        editor.host_wants_to_reclaim_control.connect(self._handle_host_wants_to_reclaim_control)

        tab_title = "Untitled"
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                editor.setPlainText(content)
                tab_title = QFileInfo(file_path).fileName()
                editor.setProperty("file_path", file_path)
                editor.document().setModified(False) 
            except Exception as e:
                QMessageBox.warning(self, "Error Opening File", f"Could not open file: {file_path}\n{e}")
                content = f"# Error opening {file_path}\n{e}"
                editor.setPlainText(content)
                tab_title = "Error"
                editor.setProperty("file_path", None)
                editor.document().setModified(False)
        else:
            editor.setPlainText(content)
            MainWindow.untitled_tab_counter += 1
            tab_title = f"Untitled-{MainWindow.untitled_tab_counter}"
            editor.setProperty("file_path", None)
            editor.document().setModified(False) # New untitled files are initially not modified

        index = self.editor_tabs.addTab(editor, tab_title)
        self.editor_tabs.setCurrentIndex(index)
        editor.setFocus()
        self._update_window_title() # Update based on new tab

    def _close_editor_tab(self, index):
        editor_widget = self.editor_tabs.widget(index)
        if editor_widget:
            if editor_widget.document().isModified():
                self.editor_tabs.setCurrentIndex(index) # Ensure this is the active tab for context
                reply = QMessageBox.question(self, "Unsaved Changes",
                                             f"'{self.editor_tabs.tabText(index).replace('*','')}*' has unsaved changes. Save before closing?",
                                             QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                             QMessageBox.Cancel) # Default to Cancel
                if reply == QMessageBox.Cancel:
                    return
                if reply == QMessageBox.Save:
                    if not self._save_current_file(): # If save is cancelled
                        return 
            
            # Disconnect signals before deleting
            try: editor_widget.textChanged.disconnect(self._on_editor_text_changed_for_network)
            except RuntimeError: pass
            try: editor_widget.document().modificationChanged.disconnect(self._update_window_title_and_tab_text)
            except RuntimeError: pass
            try:
                editor_widget.host_wants_to_reclaim_control.disconnect(self._handle_host_wants_to_reclaim_control)
            except RuntimeError:
                pass # Signal might not have been connected or already disconnected

            self.editor_tabs.removeTab(index)
            editor_widget.deleteLater()
        
        if self.editor_tabs.count() == 0:
            self._add_new_editor_tab() # Ensure one tab is always open
        else:
            self._update_window_title()


    def _open_file_from_explorer(self, index):
        file_path = self.file_system_model.filePath(index)
        if QFileInfo(file_path).isFile():
            for i in range(self.editor_tabs.count()):
                editor = self.editor_tabs.widget(i)
                if editor and editor.property("file_path") == file_path:
                    self.editor_tabs.setCurrentIndex(i)
                    return
            self._add_new_editor_tab(file_path=file_path)

    def _open_file_dialog(self):
        start_dir = QDir.currentPath() 
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", start_dir, "All Files (*);;Text Files (*.txt);;Python Files (*.py)")
        if file_path:
            for i in range(self.editor_tabs.count()):
                editor = self.editor_tabs.widget(i)
                if editor and editor.property("file_path") == file_path:
                    self.editor_tabs.setCurrentIndex(i)
                    return
            self._add_new_editor_tab(file_path=file_path)

    def _save_current_file(self):
        editor = self.current_editor
        if not editor: return False
        file_path = editor.property("file_path")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                self.status_bar.showMessage(f"File saved: {file_path}", 3000)
                editor.document().setModified(False) # Mark as saved
                self._update_window_title_and_tab_text(False) # Update titles
                return True
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save file: {file_path}\n{e}")
                self.status_bar.showMessage(f"Error saving file: {e}", 5000)
                return False
        else:
            return self._save_current_file_as() # Delegate to Save As if no path

    def _save_current_file_as(self):
        editor = self.current_editor
        if not editor: return False
        
        current_path = editor.property("file_path") or QDir.currentPath()
        # Suggest filename for untitled tabs
        suggested_name = self.editor_tabs.tabText(self.editor_tabs.currentIndex()).replace("*","") if not editor.property("file_path") else current_path

        file_path, _ = QFileDialog.getSaveFileName(self, "Save File As...", suggested_name, "All Files (*);;Text Files (*.txt);;Python Files (*.py)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                editor.setProperty("file_path", file_path)
                # Update tab title using the actual editor instance for the current index
                current_idx = self.editor_tabs.currentIndex()
                self.editor_tabs.setTabText(current_idx, QFileInfo(file_path).fileName())
                editor.document().setModified(False) # Mark as saved
                self._update_window_title_and_tab_text(False) # Update titles
                self.status_bar.showMessage(f"File saved as: {file_path}", 3000)
                return True
            except Exception as e:
                QMessageBox.critical(self, "Save As Error", f"Could not save file: {file_path}\n{e}")
                self.status_bar.showMessage(f"Error saving file as: {e}", 5000)
                return False
        return False # User cancelled dialog


    def _on_current_tab_changed(self, index):
        # Disconnect from all tabs first to avoid multiple connections
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if editor:
                try: editor.textChanged.disconnect(self._on_editor_text_changed_for_network)
                except RuntimeError: pass
                # Document might be None if tab is being removed
                doc = editor.document()
                if doc:
                    try: doc.modificationChanged.disconnect(self._update_window_title_and_tab_text)
                    except RuntimeError: pass
                try:
                    editor.host_wants_to_reclaim_control.disconnect(self._handle_host_wants_to_reclaim_control)
                except RuntimeError: # Signal might not have been connected or already disconnected
                    pass
        
        if index != -1 : # A tab is selected
            current_editor = self.current_editor
            if current_editor:
                current_editor.textChanged.connect(self._on_editor_text_changed_for_network)
                current_editor.document().modificationChanged.connect(self._update_window_title_and_tab_text)
                try: # Adding a try-except for robustness, though direct connect should be fine
                    current_editor.host_wants_to_reclaim_control.connect(self._handle_host_wants_to_reclaim_control)
                except Exception as e:
                    print(f"Error connecting host_wants_to_reclaim_control: {e}")
        
        self._update_window_title()


    def _update_window_title(self):
        base_title = "Code-Sync IDE"
        editor = self.current_editor
        if editor:
            tab_index = self.editor_tabs.currentIndex()
            file_path = editor.property("file_path")
            tab_text = QFileInfo(file_path).fileName() if file_path else self.editor_tabs.tabText(tab_index).replace("*","") # Base name
            
            if editor.document().isModified():
                tab_text += "*"
            
            self.setWindowTitle(f"{tab_text} - {base_title}")
            # Also update the tab text itself if it's the current tab
            # This is now handled by _update_window_title_and_tab_text
        elif self.editor_tabs.count() == 0:
             self.setWindowTitle(base_title)
    
    def _update_window_title_and_tab_text(self, modified):
        # Find which editor's document emitted the signal
        editor_doc = self.sender() # This should be the QTextDocument
        if not editor_doc: return

        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if editor and editor.document() == editor_doc:
                file_path = editor.property("file_path")
                base_name = QFileInfo(file_path).fileName() if file_path else self.editor_tabs.tabText(i).replace("*", "") # Fallback to current tab text if no path
                
                # Special handling for untitled tabs to keep their "Untitled-N" name consistent
                if not file_path:
                    # Ensure base_name does not become empty or just "*"
                    if not base_name or base_name == "*": 
                         # Reconstruct "Untitled-N" if needed, requires knowing its number
                         # This part might need a more robust way to get the original "Untitled-N"
                         # For now, assume tabText without "*" is the base for untitled
                         current_tab_text_no_star = self.editor_tabs.tabText(i).replace("*","")
                         base_name = current_tab_text_no_star

                new_tab_text = base_name + ("*" if modified else "")
                self.editor_tabs.setTabText(i, new_tab_text)
                
                if i == self.editor_tabs.currentIndex(): # If it's the current tab, update window title
                    self._update_window_title()
                break


    def _setup_toolbar(self):
        toolbar = QToolBar("Execution Toolbar")
        self.addToolBar(toolbar)
        self.language_selector = QComboBox()
        self.language_selector.addItems(self.runner_config.keys())
        toolbar.addWidget(self.language_selector)
        self.run_action = QAction(QIcon.fromTheme("media-playback-start", QIcon()), "&Run Code", self)
        self.run_action.setToolTip("Run the current code (F5)")
        self.run_action.triggered.connect(self._trigger_run_code)
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
        file_menu = self.menu_bar.addMenu("&File")
        new_file_action = QAction(QIcon.fromTheme("document-new", QIcon()), "&New File", self)
        new_file_action.setShortcut(QKeySequence.New)
        new_file_action.triggered.connect(lambda: self._add_new_editor_tab())
        file_menu.addAction(new_file_action)
        open_file_action = QAction(QIcon.fromTheme("document-open", QIcon()), "&Open File...", self)
        open_file_action.setShortcut(QKeySequence.Open)
        open_file_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_file_action)
        self.save_file_action = QAction(QIcon.fromTheme("document-save", QIcon()), "&Save File", self)
        self.save_file_action.setShortcut(QKeySequence.Save)
        self.save_file_action.triggered.connect(self._save_current_file)
        file_menu.addAction(self.save_file_action)
        self.save_as_action = QAction(QIcon.fromTheme("document-save-as", QIcon()), "Save File &As...", self)
        self.save_as_action.setShortcut(QKeySequence.SaveAs)
        self.save_as_action.triggered.connect(self._save_current_file_as)
        file_menu.addAction(self.save_as_action)
        
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
        run_menu.addAction(self.run_action) 
        self.run_action.setShortcut(QKeySequence("F5")) 
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
        if not self.current_editor:
            self.status_bar.showMessage("No active editor tab to run code from.", 3000)
            return
        if self.process and self.process.state() == QProcess.Running:
            reply = QMessageBox.question(self, "Process Running", "A process is already running. Stop it?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.process.kill()
                self.process.waitForFinished(1000)
            else: return
        self._execute_current_code()

    def _execute_current_code(self):
        editor = self.current_editor
        if not editor: 
            self.status_bar.showMessage("No active editor to execute.", 3000)
            return

        selected_language = self.language_selector.currentText()
        lang_config = self.runner_config.get(selected_language)
        if not lang_config:
            self.status_bar.showMessage(f"Language '{selected_language}' not configured.", 5000)
            return

        code = editor.toPlainText()
        if not code.strip():
            self.status_bar.showMessage("No code to run.", 3000)
            return

        self._cleanup_temp_files()
        temp_dir = QStandardPaths.writableLocation(QStandardPaths.TempLocation) or tempfile.gettempdir()
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=lang_config["ext"], delete=False, encoding='utf-8', dir=temp_dir) as tf:
                self.current_temp_file_path = tf.name
                tf.write(code)
        except Exception as e:
            self.status_bar.showMessage(f"Error creating temp file: {e}", 5000)
            return

        command_template = list(lang_config["cmd"])
        processed_command = []
        file_info = QFileInfo(self.current_temp_file_path)
        file_dir = file_info.absolutePath()
        file_name_no_ext = file_info.completeBaseName()
        self.current_output_file_path = os.path.join(temp_dir, file_name_no_ext) if lang_config.get("output_based") else None

        for part in command_template:
            part = part.replace("{file}", self.current_temp_file_path)
            part = part.replace("{dir}", file_dir)
            part = part.replace("{class_name}", file_name_no_ext)
            if self.current_output_file_path:
                 part = part.replace("{output_file_no_ext}", self.current_output_file_path)
            processed_command.append(part)

        if self.run_destination == "Output Panel":
            self.output_tabs.setCurrentWidget(self.output_panel_te)
            self.output_panel_te.clear()
            self.output_panel_te.appendPlainText(f"Running: {' '.join(processed_command)}\n---")
        else:
            self.output_tabs.setCurrentWidget(self.terminal_panel_te)
            self.terminal_panel_te.appendPlainText(f"\n[{file_dir}]$ {' '.join(processed_command)}")

        self.process = QProcess(self)
        self.process.setWorkingDirectory(file_dir)
        self.process.readyReadStandardOutput.connect(self._handle_process_output)
        self.process.readyReadStandardError.connect(self._handle_process_error)
        self.process.finished.connect(self._handle_process_finished)
        
        command_str_for_shell = ' '.join(shlex.quote(part) for part in processed_command)
        if "&&" in processed_command: 
            if sys.platform == "win32": self.process.start("cmd", ["/C", command_str_for_shell])
            else: self.process.start("sh", ["-c", command_str_for_shell])
        else:
            self.process.start(processed_command[0], processed_command[1:])

        if not self.process.waitForStarted(2000):
            err_msg = self.process.errorString()
            self._append_to_output_or_terminal(f"Error starting process: {err_msg}\n")
            self._handle_process_finished(-1, QProcess.CrashExit)

    def _handle_process_output(self):
        if not self.process: return
        data = self.process.readAllStandardOutput().data().decode(errors='replace')
        self._append_to_output_or_terminal(data)

    def _handle_process_error(self):
        if not self.process: return
        data = self.process.readAllStandardError().data().decode(errors='replace')
        self._append_to_output_or_terminal(data, is_error=True)

    def _append_to_output_or_terminal(self, text: str, is_error: bool = False):
        target_panel = self.output_panel_te if self.run_destination == "Output Panel" else self.terminal_panel_te
        target_panel.insertPlainText(text)

    def _handle_process_finished(self, exit_code, exit_status):
        status_msg = f"\n--- Process finished with exit code {exit_code}."
        if exit_status == QProcess.CrashExit: status_msg += " (Crashed)"
        elif exit_status == QProcess.NormalExit: status_msg += " (Normal Exit)"
        self._append_to_output_or_terminal(status_msg)
        if self.process: self.process.deleteLater()
        self.process = None

    def _cleanup_temp_files(self):
        if self.current_temp_file_path and os.path.exists(self.current_temp_file_path):
            try: os.remove(self.current_temp_file_path)
            except OSError as e: print(f"Error removing temp file {self.current_temp_file_path}: {e}")
        self.current_temp_file_path = None
        if self.current_output_file_path and os.path.exists(self.current_output_file_path):
            try: os.remove(self.current_output_file_path)
            except OSError as e: print(f"Error removing output file {self.current_output_file_path}: {e}")
        if self.current_output_file_path and sys.platform == "win32" and os.path.exists(self.current_output_file_path + ".exe"):
            try: os.remove(self.current_output_file_path + ".exe")
            except OSError as e: print(f"Error removing output file {self.current_output_file_path}.exe: {e}")
        self.current_output_file_path = None

    def _connect_network_signals(self):
        self.network_manager.data_received.connect(self._handle_data_received)
        self.network_manager.peer_connected.connect(self._handle_peer_connected)
        self.network_manager.peer_disconnected.connect(self._handle_peer_disconnected)
        self.network_manager.hosting_started.connect(self._handle_hosting_started)
        self.network_manager.connection_failed.connect(self._handle_connection_failed)

        # New connections for control messages
        self.network_manager.control_request_received.connect(self._handle_control_request_received)
        self.network_manager.control_granted_received.connect(self._handle_control_granted_received)
        self.network_manager.control_revoked_received.connect(self._handle_control_revoked_received)
        self.network_manager.control_declined_received.connect(self._handle_control_declined_received)

    @Slot()
    def _format_code(self):
        editor = self.current_editor
        if not editor: 
            self.status_bar.showMessage("No active editor to format.", 3000)
            return
        current_text = editor.toPlainText()
        if not current_text.strip():
            self.status_bar.showMessage("Nothing to format.", 3000)
            return
        try:
            cursor = editor.textCursor()
            original_pos = cursor.position()
            formatted_text = black.format_str(current_text, mode=black.FileMode())
            if formatted_text == current_text:
                self.status_bar.showMessage("Code is already well-formatted.", 3000)
                return
            self._is_updating_from_network = True 
            editor.setPlainText(formatted_text)
            self._is_updating_from_network = False
            new_cursor = editor.textCursor()
            new_cursor.setPosition(min(original_pos, len(formatted_text)))
            editor.setTextCursor(new_cursor)
            self.status_bar.showMessage("Code formatted successfully.", 3000)
        except black.NothingChanged:
            self.status_bar.showMessage("Code is already well-formatted.", 3000)
        except black.InvalidInput as e:
            QMessageBox.warning(self, "Formatting Error", f"Could not format: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Formatting Error", f"Error: {e}")

    @Slot()
    def _start_hosting_session(self):
        self.network_manager.start_hosting(self.DEFAULT_PORT)
        self.status_bar.showMessage(f"Attempting to host on port {self.DEFAULT_PORT}...")

    @Slot()
    def _connect_to_host_session(self):
        ip, port = ConnectionDialog.get_details(self) 
        if ip and port:
            self.network_manager.connect_to_host(ip, port)
            self.status_bar.showMessage(f"Attempting to connect to {ip}:{port}...")
        else:
            self.status_bar.showMessage("Connection cancelled.")
            
    @Slot()
    def _stop_current_session(self):
        self.network_manager.stop_session()

    @Slot(str)
    def _handle_data_received(self, text: str):
        editor = self.current_editor
        if not editor:
            return

        # ==> New check: Only apply text if this instance does NOT have control (i.e., is a viewer) <==
        if self.has_control:
            # This instance is currently the active editor. It should not be receiving text updates
            # from others. If it does, it's likely an old message or a logic error.
            # Ignoring it to protect the active editor's changes.
            print(f"Warning: Text update received by an active editor. Ignoring. Text: {text[:50]}...")
            return

        # Proceed with applying text if this instance is a viewer
        self._is_updating_from_network = True

        # Store current cursor and selection to try and restore it
        cursor = editor.textCursor()
        original_pos = cursor.position()
        original_anchor = cursor.anchor()

        # Store current scrollbar positions
        # scroll_x = editor.horizontalScrollBar().value() # If you want to restore horizontal
        scroll_y = editor.verticalScrollBar().value()

        editor.setPlainText(text) # Update the content of the current editor

        # Attempt to restore cursor/selection
        # This part can be tricky with full text replacement.
        # A simple approach is to try to restore position if it's within new text length.
        new_length = len(editor.toPlainText())
        restored_pos = min(original_pos, new_length)

        new_cursor = editor.textCursor()
        if original_anchor != original_pos and min(original_anchor, new_length) != restored_pos :
            # If there was a selection, try to restore it meaningfully if possible
            # This is complex; for now, just set position like single cursor
            new_cursor.setPosition(min(original_anchor, new_length), QTextCursor.MoveMode.MoveAnchor)
            new_cursor.setPosition(restored_pos, QTextCursor.MoveMode.KeepAnchor)
        else:
            new_cursor.setPosition(restored_pos)
        editor.setTextCursor(new_cursor)

        # Restore scrollbar positions
        # editor.horizontalScrollBar().setValue(scroll_x) # If restoring horizontal
        editor.verticalScrollBar().setValue(scroll_y)

        self._is_updating_from_network = False
        # No explicit status bar message here, as text updates should be seamless for viewers.

    @Slot(str, int)
    def _handle_hosting_started(self, host_ip: str, port_num: int):
        self.is_host = True
        self.has_control = True
        self.session_active = True # Session is now active
        self._update_ui_for_control_state()

        self.status_bar.showMessage(f"Hosting on {host_ip}:{port_num}. Waiting for connection...")
        self.start_hosting_action.setEnabled(False)
        self.connect_to_host_action.setEnabled(False)
        self.stop_session_action.setEnabled(True)
        self._update_window_title() 

    @Slot()
    def _handle_peer_connected(self):
        if self.network_manager._is_server: # This instance is the HOST
            self.is_host = True
            self.has_control = True
        else: # This instance is the CLIENT
            self.is_host = False
            self.has_control = False
        self.session_active = True # Session is now active
        self._update_ui_for_control_state()

        self.status_bar.showMessage("Peer connected. Collaboration active.")
        self.start_hosting_action.setEnabled(False)
        self.connect_to_host_action.setEnabled(False)
        self.stop_session_action.setEnabled(True)
        self._update_window_title() 

    @Slot()
    def _handle_peer_disconnected(self):
        self.is_host = False
        self.has_control = False
        self.session_active = False # Session is no longer active
        self._update_ui_for_control_state() # Sets UI to "Ready.", makes editor writable

        self.status_bar.showMessage("Peer disconnected. Session ended.") # Specific message

        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self._update_window_title()

    @Slot(str)
    def _handle_connection_failed(self, error_message: str):
        self.is_host = False
        self.has_control = False
        self.session_active = False # Session is no longer active
        self._update_ui_for_control_state() # Sets UI to "Ready."

        QMessageBox.critical(self, "Network Error", error_message)
        self.status_bar.showMessage(f"Connection Error: {error_message}") # Specific error message

        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self._update_window_title()

    @Slot()
    def _on_editor_text_changed_for_network(self):
        editor = self.current_editor
        if not editor or self._is_updating_from_network:
            return

        # ==> New check: Only send if this instance has control <==
        if not self.has_control:
            return
        
        # Existing session activity checks (these are still useful to ensure a connection exists)
        is_host_with_clients = self.network_manager._is_server and self.network_manager.server_client_sockets
        is_connected_client = (not self.network_manager._is_server and 
                               self.network_manager.client_socket and 
                               self.network_manager.client_socket.state() == QTcpSocket.ConnectedState)

        if is_host_with_clients or is_connected_client:
            # If we have control AND a session is active, then send.
            current_text = editor.toPlainText()
            # Ensure NetworkManager and its constants are accessible
            self.network_manager.send_data(message_type=NetworkManager.MSG_TYPE_TEXT_UPDATE, content=current_text)
        # Removed the 'and not editor.isReadOnly()' from client check as
        # self.has_control now governs this. If client has_control, editor won't be read-only.

    @Slot()
    def _handle_host_wants_to_reclaim_control(self): # Renamed
        if self.is_host and not self.has_control and self.session_active:
            self.has_control = True
            self.network_manager.send_data(message_type=NetworkManager.MSG_TYPE_REVOKE_CONTROL, content='')
            self._update_ui_for_control_state()
            self.status_bar.showMessage("Control reclaimed. You can now edit.")

    @Slot()
    def _request_control_button_clicked(self):
        if not self.is_host and not self.has_control and self.session_active:
            self.network_manager.send_data(message_type=NetworkManager.MSG_TYPE_REQ_CONTROL, content='')
            self.status_bar.showMessage("Control request sent...")
            self.request_control_button.setEnabled(False)

    @Slot()
    def _handle_control_request_received(self):
        if self.is_host and self.session_active:
            # If host receives a request, but client is already believed to have control
            # (e.g. from a previous grant that client didn't acknowledge yet, or duplicate REQ)
            # For now, we will still show the dialog. Alternatively, could auto-approve/re-send GRANT.
            # Let's assume any REQ_CONTROL warrants a fresh approval decision from host.

            reply = QMessageBox.question(self, "Control Request",
                                         "A client has requested editing control. Do you approve?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No) # Default to No

            if reply == QMessageBox.StandardButton.Yes:
                # Host approves
                if not self.has_control and not self.network_manager.server_client_sockets:
                    # Edge case: Host had granted control, client disconnected, then somehow a REQ comes through.
                    # Host should reclaim control if no clients.
                    self.has_control = True
                    print("Warning: Host approved control grant, but no clients seem connected. Host retains control.")
                else:
                    self.has_control = False # Host gives up control

                self.network_manager.send_data(message_type=NetworkManager.MSG_TYPE_GRANT_CONTROL, content='')
                self._update_ui_for_control_state()
                self.status_bar.showMessage("Control granted to client.")
            else:
                # Host declines
                self.network_manager.send_data(message_type=NetworkManager.MSG_TYPE_DECLINE_CONTROL, content='')
                self.status_bar.showMessage("Control request declined.")
                # self.has_control remains True (or its previous state if it wasn't True)
                # _update_ui_for_control_state() might be useful if status bar message needs to be sticky via it
                self._update_ui_for_control_state() # Ensure UI reflects host still has control
        # If not host or not session_active, do nothing.

    @Slot()
    def _handle_control_granted_received(self):
        if not self.is_host and self.session_active: # Check session_active
            if not self.has_control: # Only update if not already having control
                self.has_control = True
                self._update_ui_for_control_state()
                self.status_bar.showMessage("You now have editing control.")
            # If client receives GRANT_CONTROL but already believes it has control,
            # UI should already be correct. _update_ui_for_control_state() will ensure it.
        elif self.is_host:
            # This case should ideally not happen (host granting control to itself via network message)
            # but if it does, ensure host state is correct.
            if not self.has_control: # If host somehow lost control and got it back this way
                self.has_control = True
                self._update_ui_for_control_state()

    @Slot()
    def _handle_control_revoked_received(self):
        if not self.is_host and self.session_active: # Check session_active
            if self.has_control: # Only update if client thought it had control
                self.has_control = False
                self._update_ui_for_control_state()
                self.status_bar.showMessage("Editing control revoked by host.")
            # If client receives REVOKE_CONTROL but already believes it's a viewer,
            # UI should be correct. _update_ui_for_control_state() ensures it.
        elif self.is_host:
             # Host should not receive this. If it does, it implies a logic error or crossed messages.
             # Ensure host state remains authoritative if it has control.
            if not self.has_control: # If host thought it didn't have control
                # This is an unusual state. Perhaps log it.
                # For safety, reclaim control visually if this message is received.
                self.has_control = True
                self._update_ui_for_control_state()
                print("Warning: Host received REVOKE_CONTROL. Correcting local state to has_control=True.")

    @Slot()
    def _handle_control_declined_received(self):
        if not self.is_host and self.session_active:
            # Client's request for control was declined by the host.
            self.status_bar.showMessage("Host declined the control request.", 5000) # Show for 5 seconds

            # Ensure client UI reflects viewer state (button enabled, editor read-only)
            # self.has_control should already be False if request was pending.
            # Calling _update_ui_for_control_state() will ensure everything is consistent.
            if self.has_control: # Should not happen if waiting for response, but as a safeguard
                self.has_control = False
            self._update_ui_for_control_state()

    def _update_ui_for_control_state(self):
        if not self.session_active:
            self.status_bar.showMessage("Ready.")
            if self.current_editor:
                self.current_editor.setReadOnly(False)
            self.request_control_button.hide()
            # Ensure button is disabled too when hidden and session inactive
            self.request_control_button.setEnabled(False)
            return # UI is set for inactive session

        editor = self.current_editor
        status_message = "Unknown state"
        can_edit = False
        show_request_button = False # Not directly used, but helps logic
        request_button_enabled = False

        if self.is_host:
            self.request_control_button.hide() # Host never shows this button for itself
            if self.has_control:
                status_message = "You have editing control."
                can_edit = True
            else: # Host is viewer, client has control
                status_message = "Viewer has control. Press any key to reclaim."
                can_edit = False # Host's editor is read-only
        else: # This is a client
            self.request_control_button.show() # Client always shows button (enabled/disabled based on control)
            if self.has_control:
                status_message = "You have editing control."
                can_edit = True
                request_button_enabled = False # Client has control, so disable request button
            else: # Client is viewer
                status_message = "Viewing only. Click 'Request Control' to edit."
                can_edit = False
                request_button_enabled = True # Client is viewer, so enable request button

        self.status_bar.showMessage(status_message)
        if editor:
            editor.setReadOnly(not can_edit)

        self.request_control_button.setEnabled(request_button_enabled)

        # Ensure the main window title reflects current state if needed,
        # e.g., by calling self._update_window_title() if it's not too disruptive.
        # For now, focus on status bar and editor read-only state.

    def closeEvent(self, event):
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        self._cleanup_temp_files()
        self.network_manager.stop_session()
        
        # Check for unsaved changes in any tab
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if editor and editor.document().isModified():
                self.editor_tabs.setCurrentIndex(i) # Focus the tab with unsaved changes
                reply = QMessageBox.question(self, "Unsaved Changes",
                                             f"'{self.editor_tabs.tabText(i).replace('*','')}*' has unsaved changes. Save before exiting?",
                                             QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                             QMessageBox.Cancel)
                if reply == QMessageBox.Cancel:
                    event.ignore()
                    return
                if reply == QMessageBox.Save:
                    if not self._save_current_file(): # If save is cancelled
                        event.ignore()
                        return
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
