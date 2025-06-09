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
    QTreeView, QFileSystemModel, QFileDialog, QToolButton, QMenu, QStyle
)
from PySide6.QtGui import QAction, QKeySequence, QTextCursor, QIcon, QFont, QActionGroup
from PySide6.QtCore import (
    Slot, Qt, QObject, Signal, QProcess, QFileInfo, QDir, QStandardPaths, Signal as PySideSignal, QEvent
)
from PySide6.QtNetwork import QTcpSocket

# Import custom modules for AI Assistant
from ai_assistant_window import AIAssistantWindow
from ai_tools import ApplyCodeEditSignal

# Import other custom modules
from network_manager import NetworkManager
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

        # AI Assistant related initializations
        self.ai_apply_code_signal_emitter = ApplyCodeEditSignal()
        self.ai_apply_code_signal_emitter.apply_edit_signal.connect(self.handle_apply_code_edit)
        self.ai_assistant_window_instance = None # To keep track of the window

        # Initialize for new run/debug toolbar widget
        self.current_run_mode = "Run" 
        self.action_button = None
        self.dropdown_button = None
        self.run_debug_menu = None
        self.run_action_menu_item = None
        self.debug_action_menu_item = None
        self.run_debug_action_group = None
        self.run_action = None # This will be redefined or managed by the new setup
        self.execute_action = None

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

        self._setup_file_explorer_dock() 
        self._setup_toolbar()    
        self._setup_output_dock() 
        self._setup_menus()      
        self._connect_network_signals()
        
        self._add_new_editor_tab() # Start with one empty tab after all UI setup
        self._update_run_action_button_ui() # Initialize the run/debug button UI

        if self.terminal_panel_te: # Ensure it exists
            self.terminal_panel_te.installEventFilter(self)
        else:
            print("ERROR: self.terminal_panel_te not initialized before installing event filter.")

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
        
        if index != -1 : # A tab is selected
            current_editor = self.current_editor
            if current_editor:
                current_editor.textChanged.connect(self._on_editor_text_changed_for_network)
                current_editor.document().modificationChanged.connect(self._update_window_title_and_tab_text)
        
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

        # New Run/Debug combined button
        self.run_debug_widget = QWidget()
        run_debug_layout = QHBoxLayout(self.run_debug_widget)
        run_debug_layout.setContentsMargins(0, 0, 0, 0) # Compact layout
        run_debug_layout.setSpacing(0) # No space between buttons

        self.action_button = QToolButton()
        self.action_button.setAutoRaise(True)
        self.action_button.clicked.connect(self._on_main_action_button_clicked)
        # Icon and tooltip will be set by _update_run_action_button_ui later

        self.dropdown_button = QToolButton()
        self.dropdown_button.setAutoRaise(True)
        self.dropdown_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.dropdown_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup) # Show menu immediately

        self.run_debug_menu = QMenu(self)
        self.run_action_menu_item = QAction("Run", self, checkable=True)
        self.run_action_menu_item.setChecked(True) # Default to Run
        self.debug_action_menu_item = QAction("Debug", self, checkable=True)

        self.run_debug_action_group = QActionGroup(self)
        self.run_debug_action_group.setExclusive(True)
        self.run_debug_action_group.addAction(self.run_action_menu_item)
        self.run_debug_action_group.addAction(self.debug_action_menu_item)

        # Connect signals for menu items
        self.run_action_menu_item.triggered.connect(self._set_run_mode_run)
        self.debug_action_menu_item.triggered.connect(self._set_run_mode_debug)

        self.run_debug_menu.addAction(self.run_action_menu_item)
        self.run_debug_menu.addAction(self.debug_action_menu_item)
        self.dropdown_button.setMenu(self.run_debug_menu)

        run_debug_layout.addWidget(self.action_button)
        run_debug_layout.addWidget(self.dropdown_button)
        self.run_debug_widget.setLayout(run_debug_layout)
        toolbar.addWidget(self.run_debug_widget)
        # self.run_action is no longer the primary way to trigger execution from toolbar

    @Slot()
    def _on_main_action_button_clicked(self):
        if self.current_run_mode == "Run":
            self.status_bar.showMessage("Executing Run action...", 2000)
            self._trigger_run_code() # Existing method to run code
        elif self.current_run_mode == "Debug":
            self.status_bar.showMessage("Starting Debug session...", 2000)
            self._debug_code() # Call the new method
        else:
            QMessageBox.warning(self, "Unknown Mode", f"Unknown run mode: {self.current_run_mode}")

    @Slot()
    def _debug_code(self):
        editor = self.current_editor
        if not editor:
            self.status_bar.showMessage("No active editor to debug.", 3000)
            return

        if self.process and self.process.state() == QProcess.Running:
            reply = QMessageBox.question(self, "Process Running", 
                                         "A process (possibly another debug session or run) is already running. Stop it to start debugging?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.process.kill()
                self.process.waitForFinished(1000) # Give it a moment to die
            else:
                self.status_bar.showMessage("Debugging cancelled as another process is running.", 3000)
                return

        code = editor.toPlainText()
        if not code.strip():
            self.status_bar.showMessage("No code to debug.", 3000)
            return

        # Ensure Python is the selected language for debugging with PDB
        if self.language_selector.currentText() != "Python":
            QMessageBox.warning(self, "Language Mismatch", "Debugging with PDB currently only supports Python. Please select Python as the language.")
            py_idx = self.language_selector.findText("Python")
            if py_idx != -1:
                self.language_selector.setCurrentIndex(py_idx)
            else: # Python not in list, problem with RUNNER_CONFIG
                 self.status_bar.showMessage("Python language configuration not found for debugging.", 5000)
                 return

        self._cleanup_temp_files() # Clean up any previous temp files
        temp_dir = QStandardPaths.writableLocation(QStandardPaths.TempLocation) or tempfile.gettempdir()
        
        try:
            # For PDB, the extension must be .py
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding='utf-8', dir=temp_dir) as tf:
                self.current_temp_file_path = tf.name
                tf.write(code)
        except Exception as e:
            self.status_bar.showMessage(f"Error creating temp file for debugging: {e}", 5000)
            return

        # --- Crucial for debug mode: Switch to terminal view ---
        self._set_run_destination("Terminal") # Use existing method to switch state
        self.output_tabs.setCurrentWidget(self.terminal_panel_te)
        self.terminal_panel_te.clear() # Clear previous terminal content for new debug session

        # Prepare PDB command
        py_executable = sys.executable if sys.executable else "python"
        command = [py_executable, "-m", "pdb", self.current_temp_file_path]

        file_info = QFileInfo(self.current_temp_file_path)
        file_dir = file_info.absolutePath()

        self.terminal_panel_te.appendPlainText(f"Starting PDB: {' '.join(command)}\n---")

        self.process = QProcess(self)
        self.process.setWorkingDirectory(file_dir) 

        self.process.readyReadStandardOutput.connect(self._handle_process_output)
        self.process.readyReadStandardError.connect(self._handle_process_error)
        self.process.finished.connect(self._handle_process_finished)
        self.process.errorOccurred.connect(self._handle_process_qprocess_error) 

        if sys.platform != "win32":
            self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        self.process.start(command[0], command[1:])

        if not self.process.waitForStarted(3000): 
            err_msg = self.process.errorString()
            self._append_to_output_or_terminal(f"Error starting PDB process: {err_msg}\n", is_error=True)
            self._handle_process_finished(-1, QProcess.CrashExit) 
        else:
            self.status_bar.showMessage(f"PDB session started for {QFileInfo(self.current_temp_file_path).fileName()}", 5000)
            self.terminal_panel_te.setFocus() 

    @Slot()
    def _update_run_action_button_ui(self):
        if not self.action_button: # Should not happen if setup correctly
            return
        if self.current_run_mode == "Run":
            self.action_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.action_button.setToolTip("Run current script (F5)")
        else: # Debug mode
            # Using SP_BrowserReload as a placeholder for a 'bug' icon.
            # A proper bug icon might require adding a resource file.
            self.action_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)) 
            self.action_button.setToolTip("Debug current script (F5)")

    @Slot()
    def _set_run_mode_run(self):
        self.current_run_mode = "Run"
        # Ensure the correct menu item is checked (though QActionGroup should handle this)
        if self.run_action_menu_item and not self.run_action_menu_item.isChecked():
             self.run_action_menu_item.setChecked(True)
        self._update_run_action_button_ui()
        self.status_bar.showMessage("Switched to Run mode.", 2000)

    @Slot()
    def _set_run_mode_debug(self):
        self.current_run_mode = "Debug"
        # Ensure the correct menu item is checked
        if self.debug_action_menu_item and not self.debug_action_menu_item.isChecked():
            self.debug_action_menu_item.setChecked(True)
        self._update_run_action_button_ui()
        self.status_bar.showMessage("Switched to Debug mode.", 2000)

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
        # run_menu.addAction(self.run_action) # Old run_action removed from menu
        # self.run_action.setShortcut(QKeySequence("F5")) # Shortcut will be handled differently
        run_menu.addSeparator()

        # Add a general "Execute" action that respects the current Run/Debug mode
        self.execute_action = QAction("Execute (Run/Debug)", self)
        self.execute_action.setShortcut(QKeySequence("F5"))
        self.execute_action.triggered.connect(self._on_main_action_button_clicked)
        run_menu.addAction(self.execute_action) # Add it to the Run menu

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

        # Tools Menu
        tools_menu = self.menu_bar.addMenu("&Tools")
        ai_assistant_action = QAction("AI Assistant", self)
        ai_assistant_action.setShortcut(QKeySequence("Ctrl+Shift+A")) # Optional: add a shortcut
        ai_assistant_action.triggered.connect(self.show_ai_assistant)
        tools_menu.addAction(ai_assistant_action)

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

        if selected_language == "Python":
            # Ensure we use the same Python interpreter running the IDE
            # This makes the Python execution more robust.
            py_executable = sys.executable if sys.executable else "python" 
            lang_config = {"cmd": [py_executable, "{file}"], "ext": ".py"} # Override

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
        self.process.errorOccurred.connect(self._handle_process_qprocess_error)
        
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

    @Slot(QProcess.ProcessError)
    def _handle_process_qprocess_error(self, error):
        error_messages = {
            QProcess.ProcessError.FailedToStart: "Failed to start: The process failed to start. Check if the command or executable path is correct and if you have permissions.",
            QProcess.ProcessError.Crashed: "Crashed: The process crashed some time after starting successfully.",
            QProcess.ProcessError.Timedout: "Timed out: The last waitFor...() function timed out. The state of QProcess is unchanged.",
            QProcess.ProcessError.ReadError: "Read Error: An error occurred when attempting to read from the process.",
            QProcess.ProcessError.WriteError: "Write Error: An error occurred when attempting to write to the process.",
            QProcess.ProcessError.UnknownError: "Unknown Error: An unknown error occurred."
        }
        error_message = error_messages.get(error, f"An unspecified QProcess error occurred: {error}")
        self._append_to_output_or_terminal(f"QProcess Error: {error_message}\n", is_error=True)
        # Optionally, also call _handle_process_finished or update UI to reflect error state
        # For now, just logging. If the process finishes due to this, finished signal will also trigger.
        if self.process and self.process.state() == QProcess.NotRunning:
             self._handle_process_finished(self.process.exitCode(), QProcess.CrashExit) # Assuming crash if error leads to not running

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
        if not editor: return
        self._is_updating_from_network = True
        cursor = editor.textCursor()
        old_pos = cursor.position()
        old_anchor = cursor.anchor()
        editor.setPlainText(text) # Update the content of the current editor
        if old_anchor != old_pos:
            cursor.setPosition(old_anchor, QTextCursor.MoveAnchor)
            cursor.setPosition(old_pos, QTextCursor.KeepAnchor)
        else:
            cursor.setPosition(old_pos)
        editor.setTextCursor(cursor)
        self._is_updating_from_network = False

    @Slot(str, int)
    def _handle_hosting_started(self, host_ip: str, port_num: int):
        self.status_bar.showMessage(f"Hosting on {host_ip}:{port_num}. Waiting for connection...")
        self.start_hosting_action.setEnabled(False)
        self.connect_to_host_action.setEnabled(False)
        self.stop_session_action.setEnabled(True)
        # Host can always edit
        if self.current_editor: self.current_editor.setReadOnly(False) 
        self._update_window_title() 

    @Slot()
    def _handle_peer_connected(self):
        self.status_bar.showMessage("Peer connected. Collaboration active.")
        self.start_hosting_action.setEnabled(False)
        self.connect_to_host_action.setEnabled(False)
        self.stop_session_action.setEnabled(True)
        # If client, editor becomes read-only
        if not self.network_manager._is_server and self.current_editor:
            self.current_editor.setReadOnly(True)
        self._update_window_title() 

    @Slot()
    def _handle_peer_disconnected(self):
        self.status_bar.showMessage("Peer disconnected. Session ended.")
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        # Editor becomes writable again for everyone
        if self.current_editor: self.current_editor.setReadOnly(False)
        self._update_window_title()

    @Slot(str)
    def _handle_connection_failed(self, error_message: str):
        QMessageBox.critical(self, "Network Error", error_message)
        self.status_bar.showMessage(f"Error: {error_message}")
        self.start_hosting_action.setEnabled(True)
        self.connect_to_host_action.setEnabled(True)
        self.stop_session_action.setEnabled(False)
        self._update_window_title()

    @Slot()
    def _on_editor_text_changed_for_network(self):
        editor = self.current_editor
        if not editor or self._is_updating_from_network: # Ensure this flag is respected
            return
        
        is_host_with_clients = self.network_manager._is_server and self.network_manager.server_client_sockets
        is_connected_client = (not self.network_manager._is_server and 
                               self.network_manager.client_socket and 
                               self.network_manager.client_socket.state() == QTcpSocket.ConnectedState)

        # Client only sends data if editor is not read-only (which it would be in a session)
        # Host can always send.
        if is_host_with_clients or (is_connected_client and not editor.isReadOnly()):
            current_text = editor.toPlainText()
            self.network_manager.send_data(current_text)

    # --- AI Assistant Methods ---
    @Slot()
    def show_ai_assistant(self):
        if not self.ai_assistant_window_instance:
            # Pass 'self' (MainWindow instance) and the signal emitter
            self.ai_assistant_window_instance = AIAssistantWindow(
                main_window=self, 
                apply_code_signal_emitter=self.ai_apply_code_signal_emitter,
                parent=self # Ensure it's properly parented
            )
            # Ensure the window is cleaned up when closed
            self.ai_assistant_window_instance.finished.connect(self._ai_assistant_closed)
        self.ai_assistant_window_instance.show()
        self.ai_assistant_window_instance.activateWindow()
        self.ai_assistant_window_instance.raise_()

    @Slot()
    def _ai_assistant_closed(self):
        self.ai_assistant_window_instance = None # Allow garbage collection and recreation

    @Slot(str)
    def handle_apply_code_edit(self, new_code: str):
        editor = self.current_editor
        if editor:
            # Store cursor position
            cursor = editor.textCursor()
            original_pos = cursor.position()
            
            # Use a flag to prevent feedback loop if network sync is also active for text changes
            # This specific flag might need to be more general if text changes can come from other sources too
            # For now, reusing _is_updating_from_network, but consider a more specific one if needed.
            self._is_updating_from_network = True 
            editor.setPlainText(new_code)
            self._is_updating_from_network = False # Reset flag
            
            # Restore cursor position (or try to)
            new_cursor = editor.textCursor()
            # Ensure cursor position is within new text bounds
            new_cursor.setPosition(min(original_pos, len(new_code))) 
            editor.setTextCursor(new_cursor)
            
            self.status_bar.showMessage("AI Assistant applied code changes.", 3000)
            # Optionally, mark the document as modified, which also updates tab asterisk
            editor.document().setModified(True) 
        else:
            self.status_bar.showMessage("AI Assistant: No active editor to apply changes to.", 3000)
            # Optionally show a message box to the user
            QMessageBox.warning(self, "AI Assistant Error", "No active editor selected to apply code changes.")
    # --- End AI Assistant Methods ---

    def eventFilter(self, watched_object, event: QEvent):
        if watched_object is self.terminal_panel_te and event.type() == QEvent.Type.KeyPress:
            if self.process and self.process.state() == QProcess.ProcessState.Running and self.current_run_mode == "Debug":
                key_event = event # event is already a QKeyEvent

                if key_event.key() == Qt.Key_Return or key_event.key() == Qt.Key_Enter:
                    cursor = self.terminal_panel_te.textCursor()
                    
                    # Move cursor to the beginning of the current line (block)
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                    # Select text to the end of the current line (block)
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    current_line_text = cursor.selectedText()

                    prompts_to_check = ["(Pdb) ", "Pdb> ", "(Pdb)", "Pdb>", "... ", "...> "] 
                    command_text = current_line_text 
                    
                    found_prompt_in_line = False
                    for pdb_prompt in prompts_to_check:
                        prompt_idx = current_line_text.rfind(pdb_prompt)
                        if prompt_idx != -1:
                            command_text = current_line_text[prompt_idx + len(pdb_prompt):]
                            found_prompt_in_line = True
                            break
                    
                    if not found_prompt_in_line:
                        command_text = current_line_text

                    self.process.write(command_text.encode('utf-8') + b'\n')
                    
                    return False # Let event propagate

                elif key_event.key() == Qt.Key_C and key_event.modifiers() & Qt.ControlModifier:
                    if sys.platform == "win32":
                        self.process.generateConsoleCtrlEvent(0) # CTRL_C_EVENT
                    else:
                        self.process.terminate() 
                    self.terminal_panel_te.appendPlainText("^C\n")
                    return True # Event handled

        return super().eventFilter(watched_object, event)

    def _on_editor_text_changed_for_network(self):
        editor = self.current_editor
        if not editor or self._is_updating_from_network: # Check the flag here
            return
        
        is_host_with_clients = self.network_manager._is_server and self.network_manager.server_client_sockets
        is_connected_client = (not self.network_manager._is_server and 
                               self.network_manager.client_socket and 
                               self.network_manager.client_socket.state() == QTcpSocket.ConnectedState)

        # Client only sends data if editor is not read-only (which it would be in a session)
        # Host can always send.
        if is_host_with_clients or (is_connected_client and not editor.isReadOnly()):
            current_text = editor.toPlainText()
            self.network_manager.send_data(current_text)

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
