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
    QTreeView, QFileSystemModel, QFileDialog, QToolButton, QMenu, QStyle,
    QInputDialog, QLineEdit
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

        # Adapt Python configuration to the new nested run/debug structure
        # This simulates the change in config.py for development within main_window.py
        if "Python" in self.runner_config:
            python_config = self.runner_config["Python"]
            py_executable = sys.executable if sys.executable else "python"

            if isinstance(python_config, list): # Old format: ["python", "{file}"]
                # self.status_bar.showMessage("Adapting Python runner config to new structure.", 2000) # Status bar not ready yet
                print("Adapting Python runner config to new structure.")
                self.runner_config["Python"] = {
                    "run": [py_executable, "-u", "{file}"], # Using -u for unbuffered output
                    "debug": [py_executable, "-m", "pdb", "{file}"]
                }
            elif isinstance(python_config, dict): # Possibly new format already, or partially new
                if "run" not in python_config:
                    python_config["run"] = [py_executable, "-u", "{file}"]
                if "debug" not in python_config:
                    python_config["debug"] = [py_executable, "-m", "pdb", "{file}"]
                # Ensure sys.executable is used in existing run/debug commands if they exist
                if "run" in python_config and isinstance(python_config["run"], list) and python_config["run"]:
                    if "python" in python_config["run"][0].lower(): # if command is 'python' or 'python3' etc.
                        python_config["run"][0] = py_executable
                if "debug" in python_config and isinstance(python_config["debug"], list) and python_config["debug"]:
                     if "python" in python_config["debug"][0].lower():
                        python_config["debug"][0] = py_executable
            else: # Unknown format for Python
                # self.status_bar.showMessage("Warning: Python runner config has unexpected format. Defaulting.", 3000)
                print("Warning: Python runner config has unexpected format. Defaulting.")
                self.runner_config["Python"] = {
                    "run": [py_executable, "-u", "{file}"],
                    "debug": [py_executable, "-m", "pdb", "{file}"]
                }
        else: # Python not in config at all
            # self.status_bar.showMessage("Warning: Python not found in runner_config. Adding default.", 3000)
            print("Warning: Python not found in runner_config. Adding default.")
            py_executable = sys.executable if sys.executable else "python"
            self.runner_config["Python"] = {
                "run": [py_executable, "-u", "{file}"],
                "debug": [py_executable, "-m", "pdb", "{file}"]
            }

        self.process = None
        self.current_temp_file_path = None
        self.current_output_file_path = None

        self.network_manager = NetworkManager(self)
        self._is_updating_from_network = False

        # AI Assistant related initializations
        self.ai_apply_code_signal_emitter = ApplyCodeEditSignal()
        self.ai_apply_code_signal_emitter.apply_edit_signal.connect(self.handle_apply_code_edit)
        self.ai_assistant_window_instance = None

        # Attributes for the old run/debug UI (QToolButton with QMenu)
        # self.current_run_mode = "Run" # Obsolete with ComboBox
        # self.action_button = None # Obsolete QToolButton
        # self.dropdown_button = None # Obsolete QToolButton
        # self.run_debug_menu = None # Obsolete QMenu
        # self.run_action_menu_item = None # Obsolete QAction
        # self.debug_action_menu_item = None # Obsolete QAction
        # self.run_debug_action_group = None # Obsolete QActionGroup

        # New attributes for ComboBox Run/Debug UI
        self.run_debug_mode_selector = None
        self.play_action = None

        self.execute_action = None # For F5 shortcut in menu

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

        self._setup_file_explorer_dock() 
        self._setup_toolbar()    
        self._setup_output_dock() 
        self._setup_menus()      
        self._connect_network_signals()
        
        self._add_new_editor_tab()
        # self._update_run_action_button_ui() # Obsolete call

        if self.terminal_panel_te:
            self.terminal_panel_te.installEventFilter(self)

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
            editor.document().setModified(False)

        index = self.editor_tabs.addTab(editor, tab_title)
        self.editor_tabs.setCurrentIndex(index)
        editor.setFocus()
        self._update_window_title()

    def _close_editor_tab(self, index):
        editor_widget = self.editor_tabs.widget(index)
        if editor_widget:
            if editor_widget.document().isModified():
                self.editor_tabs.setCurrentIndex(index)
                reply = QMessageBox.question(self, "Unsaved Changes",
                                             f"'{self.editor_tabs.tabText(index).replace('*','')}*' has unsaved changes. Save before closing?",
                                             QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                             QMessageBox.Cancel)
                if reply == QMessageBox.Cancel:
                    return
                if reply == QMessageBox.Save:
                    if not self._save_current_file():
                        return 
            
            try: editor_widget.textChanged.disconnect(self._on_editor_text_changed_for_network)
            except RuntimeError: pass
            try: editor_widget.document().modificationChanged.disconnect(self._update_window_title_and_tab_text)
            except RuntimeError: pass

            self.editor_tabs.removeTab(index)
            editor_widget.deleteLater()
        
        if self.editor_tabs.count() == 0:
            self._add_new_editor_tab()
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
                editor.document().setModified(False)
                self._update_window_title_and_tab_text(False)
                return True
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save file: {file_path}\n{e}")
                self.status_bar.showMessage(f"Error saving file: {e}", 5000)
                return False
        else:
            return self._save_current_file_as()

    def _save_current_file_as(self):
        editor = self.current_editor
        if not editor: return False
        
        current_path = editor.property("file_path") or QDir.currentPath()
        suggested_name = self.editor_tabs.tabText(self.editor_tabs.currentIndex()).replace("*","") if not editor.property("file_path") else current_path

        file_path, _ = QFileDialog.getSaveFileName(self, "Save File As...", suggested_name, "All Files (*);;Text Files (*.txt);;Python Files (*.py)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                editor.setProperty("file_path", file_path)
                current_idx = self.editor_tabs.currentIndex()
                self.editor_tabs.setTabText(current_idx, QFileInfo(file_path).fileName())
                editor.document().setModified(False)
                self._update_window_title_and_tab_text(False)
                self.status_bar.showMessage(f"File saved as: {file_path}", 3000)
                return True
            except Exception as e:
                QMessageBox.critical(self, "Save As Error", f"Could not save file: {file_path}\n{e}")
                self.status_bar.showMessage(f"Error saving file as: {e}", 5000)
                return False
        return False


    def _on_current_tab_changed(self, index):
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if editor:
                try: editor.textChanged.disconnect(self._on_editor_text_changed_for_network)
                except RuntimeError: pass
                doc = editor.document()
                if doc:
                    try: doc.modificationChanged.disconnect(self._update_window_title_and_tab_text)
                    except RuntimeError: pass
        
        if index != -1 :
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
            tab_text = QFileInfo(file_path).fileName() if file_path else self.editor_tabs.tabText(tab_index).replace("*","")
            
            if editor.document().isModified():
                tab_text += "*"
            
            self.setWindowTitle(f"{tab_text} - {base_title}")
        elif self.editor_tabs.count() == 0:
             self.setWindowTitle(base_title)
    
    def _update_window_title_and_tab_text(self, modified):
        editor_doc = self.sender()
        if not editor_doc: return

        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if editor and editor.document() == editor_doc:
                file_path = editor.property("file_path")
                base_name = QFileInfo(file_path).fileName() if file_path else self.editor_tabs.tabText(i).replace("*", "")
                
                if not file_path:
                    if not base_name or base_name == "*": 
                         current_tab_text_no_star = self.editor_tabs.tabText(i).replace("*","")
                         base_name = current_tab_text_no_star

                new_tab_text = base_name + ("*" if modified else "")
                self.editor_tabs.setTabText(i, new_tab_text)
                
                if i == self.editor_tabs.currentIndex():
                    self._update_window_title()
                break


    def _setup_toolbar(self):
        toolbar = QToolBar("Execution Toolbar")
        self.addToolBar(toolbar)
        self.language_selector = QComboBox()
        self.language_selector.addItems(self.runner_config.keys())
        toolbar.addWidget(self.language_selector)

        # Mode Selector ComboBox
        self.run_debug_mode_selector = QComboBox()
        self.run_debug_mode_selector.addItems(["Run", "Debug"])
        self.run_debug_mode_selector.setFixedWidth(100)
        self.run_debug_mode_selector.setToolTip("Select execution mode (Run or Debug)")
        toolbar.addWidget(self.run_debug_mode_selector)

        # Play Action Button
        self.play_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Execute", self)
        self.play_action.setToolTip("Execute (Run/Debug based on selected mode) (F5)")
        toolbar.addAction(self.play_action)
        self.play_action.triggered.connect(self.handle_execution)

    @Slot()
    def handle_execution(self):
        if not self.run_debug_mode_selector:
            QMessageBox.critical(self, "Error", "Run/Debug mode selector not found.")
            return

        mode_text = self.run_debug_mode_selector.currentText().lower()
        self._execute_code_from_config(mode=mode_text)

    # @Slot() # Obsolete: Was connected to the old QToolButton UI
    # def _on_main_action_button_clicked(self):
    #     pass

    # @Slot() # Obsolete: Logic merged into _execute_code_from_config
    # def _debug_code(self):
    #     pass

    @Slot(str)
    def _execute_code_from_config(self, mode: str):
        editor = self.current_editor
        if not editor:
            self.status_bar.showMessage(f"No active editor to {mode}.", 3000)
            return

        if self.process and self.process.state() == QProcess.ProcessState.Running:
            reply = QMessageBox.question(self, "Process Running",
                                         f"A process is already running. Stop it to start {mode}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.process.kill()
                self.process.waitForFinished(1000)
            else:
                self.status_bar.showMessage(f"{mode.capitalize()} cancelled as another process is running.", 3000)
                return

        code = editor.toPlainText()
        if not code.strip():
            self.status_bar.showMessage(f"No code to {mode}.", 3000)
            return

        self.status_bar.showMessage(f"Preparing to {mode} code...", 2000)

        selected_language = self.language_selector.currentText()
        lang_configs_for_ide = self.runner_config

        if selected_language not in lang_configs_for_ide:
            self.status_bar.showMessage(f"Language '{selected_language}' not configured.", 5000)
            return

        current_lang_specific_config = lang_configs_for_ide[selected_language]

        if not isinstance(current_lang_specific_config, dict) or \
           mode not in current_lang_specific_config or \
           not isinstance(current_lang_specific_config[mode], list):
            self.status_bar.showMessage(f"'{mode}' command not configured for '{selected_language}'.", 5000)
            if mode != "run" and "run" in current_lang_specific_config and isinstance(current_lang_specific_config["run"], list):
                 self.status_bar.showMessage(f"Falling back to 'run' mode for '{selected_language}'.", 3000)
                 mode = "run"
                 command_template = current_lang_specific_config[mode]
            else:
                return
        else:
            command_template = current_lang_specific_config[mode]

        if mode == "debug":
            if selected_language != "Python":
                QMessageBox.warning(self, "Language Mismatch",
                                    "Debugging with PDB currently only supports Python. Please select Python as the language.")
                py_idx = self.language_selector.findText("Python")
                if py_idx != -1:
                    self.language_selector.setCurrentIndex(py_idx)
                else:
                    self.status_bar.showMessage("Python language configuration not found for debugging.", 5000)
                    return
                current_lang_specific_config = lang_configs_for_ide["Python"] # Re-fetch after potential lang change
                if mode not in current_lang_specific_config or not isinstance(current_lang_specific_config[mode], list):
                     self.status_bar.showMessage(f"'{mode}' command not configured for 'Python' after switch.", 5000)
                     return
                command_template = current_lang_specific_config[mode]

            self._set_run_destination("Terminal")
            self.output_tabs.setCurrentWidget(self.terminal_panel_te)
            self.terminal_panel_te.clear()
            self.terminal_panel_te.setFocus()
            self.status_bar.showMessage("Starting debug session in terminal...", 2000)
        else: # 'run' mode
            if self.run_destination == "Output Panel":
                self.output_tabs.setCurrentWidget(self.output_panel_te)
                self.output_panel_te.clear()
            else:
                self.output_tabs.setCurrentWidget(self.terminal_panel_te)
                self.terminal_panel_te.clear()

        self._cleanup_temp_files()
        temp_dir = QStandardPaths.writableLocation(QStandardPaths.TempLocation) or tempfile.gettempdir()

        lang_ext = ".py"
        if isinstance(lang_configs_for_ide.get(selected_language), dict) and \
           isinstance(lang_configs_for_ide[selected_language].get("ext"), str):
            lang_ext = lang_configs_for_ide[selected_language]["ext"]
        elif selected_language == "Python":
            lang_ext = ".py"
        else:
            lang_ext = ".tmp"

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=lang_ext, delete=False, encoding='utf-8', dir=temp_dir) as tf:
                self.current_temp_file_path = tf.name
                tf.write(code)
        except Exception as e:
            self.status_bar.showMessage(f"Error creating temp file for {mode}: {e}", 5000)
            return

        processed_command = []
        file_info = QFileInfo(self.current_temp_file_path)
        file_dir = file_info.absolutePath()
        file_name_no_ext = file_info.completeBaseName()
        self.current_output_file_path = os.path.join(temp_dir, file_name_no_ext) if current_lang_specific_config.get("output_based") else None

        for part in list(command_template):
            part = part.replace("{file}", self.current_temp_file_path)
            part = part.replace("{dir}", file_dir)
            part = part.replace("{class_name}", file_name_no_ext)
            if self.current_output_file_path:
                 part = part.replace("{output_file_no_ext}", self.current_output_file_path)
            processed_command.append(part)

        log_message = f"Executing ({mode}): {' '.join(processed_command)}\n---"
        if self.run_destination == "Output Panel" and mode == "run":
            self.output_panel_te.appendPlainText(log_message)
        else:
            self.terminal_panel_te.appendPlainText(log_message)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(file_dir)
        self.process.readyReadStandardOutput.connect(self._handle_process_output)
        self.process.readyReadStandardError.connect(self._handle_process_error)
        self.process.finished.connect(self._handle_process_finished)
        self.process.errorOccurred.connect(self._handle_process_qprocess_error)

        if sys.platform != "win32" and mode == "debug":
             self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        self.process.start(processed_command[0], processed_command[1:])

        if not self.process.waitForStarted(3000 if mode == "debug" else 2000):
            err_msg = self.process.errorString()
            self._append_to_output_or_terminal(f"Error starting process for {mode}: {err_msg}\n", is_error=True)
            self._handle_process_finished(-1, QProcess.ProcessError.FailedToStart)

    @Slot()
    def _update_run_action_button_ui(self):
        # This method is part of the old UI and will be removed or heavily refactored.
        # For now, it might try to access self.action_button which is None from __init__.
        # if hasattr(self, 'action_button') and self.action_button:
        #     if hasattr(self, 'current_run_mode') and self.current_run_mode == "Run":
        #          self.action_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        #          self.action_button.setToolTip("Run current script (F5)")
        #     else:
        #          self.action_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        #          self.action_button.setToolTip("Debug current script (F5)")
        pass # Body replaced with pass as it's obsolete

    @Slot()
    def _set_run_mode_run(self):
        # This method is part of the old UI and will be removed.
        # self.current_run_mode = "Run"
        # if self.run_action_menu_item and not self.run_action_menu_item.isChecked():
        #      self.run_action_menu_item.setChecked(True)
        # self._update_run_action_button_ui()
        # self.status_bar.showMessage("Switched to Run mode.", 2000)
        pass # Body replaced with pass as it's obsolete

    @Slot()
    def _set_run_mode_debug(self):
        # This method is part of the old UI and will be removed.
        # self.current_run_mode = "Debug"
        # if self.debug_action_menu_item and not self.debug_action_menu_item.isChecked():
        #     self.debug_action_menu_item.setChecked(True)
        # self._update_run_action_button_ui()
        # self.status_bar.showMessage("Switched to Debug mode.", 2000)
        pass # Body replaced with pass as it's obsolete

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
        new_file_action.triggered.connect(self._create_new_file_context_aware) # Changed connection
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
        try:
            self.execute_action.triggered.disconnect()
        except (RuntimeError, TypeError):
            pass # No connections or slot was C++
        self.execute_action.triggered.connect(self.handle_execution) # Connect to the new unified handler
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

    # def _trigger_run_code(self): # Obsolete
    #     pass

    # def _execute_current_code(self): # Obsolete
    #     pass

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

    @Slot()
    def _create_new_file_context_aware(self):
        target_dir = ""
        current_tree_index = self.file_tree_view.currentIndex()

        if current_tree_index.isValid():
            path_from_selection = self.file_system_model.filePath(current_tree_index)
            if os.path.isdir(path_from_selection):
                target_dir = path_from_selection
            elif os.path.isfile(path_from_selection):
                target_dir = os.path.dirname(path_from_selection)
            else:
                target_dir = self.file_system_model.rootPath()
        else:
            target_dir = self.file_system_model.rootPath()
            if not target_dir:
                target_dir = QDir.currentPath()

        file_name, ok = QInputDialog.getText(self, "New File", "Enter new file name:", QLineEdit.EchoMode.Normal, "")

        if ok and file_name:
            file_name = file_name.strip() # Ensure no leading/trailing whitespace in filename itself
            if not file_name:
                QMessageBox.warning(self, "Invalid Name", "File name cannot be empty.")
                self.status_bar.showMessage("File creation cancelled: empty name.", 3000)
                return

            if '/' in file_name or '\\' in file_name: # Check for path separators
                QMessageBox.warning(self, "Invalid Name", "File name cannot contain path separators (e.g., / or \\).")
                self.status_bar.showMessage("File creation cancelled: invalid characters in name.", 3000)
                return

            full_file_path = os.path.join(target_dir, file_name)

            # Check if file already exists
            if os.path.exists(full_file_path):
                QMessageBox.warning(self, "File Exists",
                                    f"A file or folder with the name '{file_name}' already exists in '{target_dir}'.")
                self.status_bar.showMessage(f"File creation aborted: '{file_name}' already exists.", 3000)
                return

            # Try to create the file
            try:
                with open(full_file_path, 'w', encoding='utf-8') as f:
                    # File is created empty, nothing to write for now
                    pass
                self.status_bar.showMessage(f"Successfully created file: {full_file_path}", 3000)

                # Open the newly created file in a new editor tab
                self._add_new_editor_tab(file_path=full_file_path)

                # Optional: Select the newly created file in the tree view.
                # This requires finding the model index for the new file path.
                # new_file_index = self.file_system_model.index(full_file_path)
                # if new_file_index.isValid():
                #    self.file_tree_view.setCurrentIndex(new_file_index)
                #    self.file_tree_view.scrollTo(new_file_index)

            except OSError as e:
                QMessageBox.critical(self, "Creation Error",
                                     f"Could not create file: {full_file_path}\n\nError: {e}")
                self.status_bar.showMessage(f"Error creating file: {e}", 5000)
                return
        else:
            self.status_bar.showMessage("New file creation cancelled by user.", 3000)
            return

    def eventFilter(self, watched_object, event: QEvent):
        if watched_object is self.terminal_panel_te and event.type() == QEvent.Type.KeyPress:
            if self.process and self.process.state() == QProcess.ProcessState.Running and \
               self.run_debug_mode_selector and self.run_debug_mode_selector.currentText() == "Debug":
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

[end of main_window.py]
