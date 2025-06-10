from PySide6.QtWidgets import QPlainTextEdit, QCompleter, QApplication, QTextEdit
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QKeyEvent, QFont, QSyntaxHighlighter
from PySide6.QtCore import Qt, QTimer, QStringListModel, QRect, QRegularExpression, QFileInfo, Signal, Slot
import json
import os
import sys
from PySide6.QtCore import QThreadPool # Import QThreadPool

# Import worker threads
from worker_threads import JediCompletionWorker, PyflakesLinterWorker, WorkerSignals

from python_highlighter import PythonHighlighter # Import the dedicated highlighter

class CodeEditor(QPlainTextEdit):
    cursor_position_changed_signal = Signal(int, int) # Line, Column
    language_changed_signal = Signal(str)
    control_reclaim_requested = Signal() # New signal for host to reclaim control

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabStopDistance(4 * self.fontMetrics().averageCharWidth())
        self.file_path = None
        self.current_language = "Plain Text"

        self.theme_config = self._load_theme_config()
        self._apply_editor_theme()

        self.highlighter = PythonHighlighter(self.document(), self.theme_config) # Use PythonHighlighter
        self.thread_pool = QThreadPool.globalInstance() # Get global thread pool
        self.setup_linter()
        self.setup_completer()

        self.PAIRS = {
            '(': ')',
            '[': ']',
            '{': '}',
            '"': '"',
            "'": "'",
            '<': '>'
        }
        self.CLOSING_CHARS = set(self.PAIRS.values())

        self.textChanged.connect(self._update_language_and_highlighting)
        self.cursorPositionChanged.connect(self._emit_cursor_position)
        self._is_programmatic_change = False # Master control flag

    def _load_theme_config(self):
        print("LOG: CodeEditor._load_theme_config - Entry")
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'theme.json')
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            sys.stderr.write(f"Theme config file not found at {config_path}. Using default theme.\n")
            return {}
        except json.JSONDecodeError:
            sys.stderr.write(f"Error decoding theme config from {config_path}. Using default theme.\n")
            return {}
        except Exception as e:
            sys.stderr.write(f"An unexpected error occurred loading theme config from {config_path}: {e}\n")
            return {}
        finally:
            print("LOG: CodeEditor._load_theme_config - Exit")

    def _apply_editor_theme(self):
        print("LOG: CodeEditor._apply_editor_theme - Entry")
        editor_theme = self.theme_config.get("editor", {})
        bg_color = editor_theme.get("background", "#282c34")
        fg_color = editor_theme.get("foreground", "#abb2bf")
        selection_bg = editor_theme.get("selection_background", "#3e4451")
        line_num_fg = editor_theme.get("line_number_foreground", "#5c6370")

        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg_color};
                color: {fg_color};
                selection-background-color: {selection_bg};
            }}
            QPlainTextEdit QAbstractScrollArea::corner {{
                background-color: {bg_color};
            }}
        """)
        print("LOG: CodeEditor._apply_editor_theme - Exit")

    def _update_language_and_highlighting(self):
        print("LOG: CodeEditor._update_language_and_highlighting - Entry")
        if self._is_programmatic_change:
            print("LOG: CodeEditor._update_language_and_highlighting - Programmatic change, skipping.")
            return

        old_language = self.current_language
        
        if self.file_path:
            self._is_programmatic_change = True # Set flag before programmatic change
            self.highlighter.set_lexer_for_filename(self.file_path, self.toPlainText())
            self._is_programmatic_change = False # Reset flag after programmatic change
            if self.highlighter.lexer:
                self.current_language = self.highlighter.lexer.name
            else:
                self.current_language = "Plain Text"
        else:
            self._is_programmatic_change = True # Set flag before programmatic change
            self.highlighter.lexer = None
            self.current_language = "Plain Text"
            self.highlighter.rehighlight()
            self._is_programmatic_change = False # Reset flag after programmatic change

        if self.current_language != old_language:
            self.language_changed_signal.emit(self.current_language)
        
        self.linter_timer.start()
        print("LOG: CodeEditor._update_language_and_highlighting - Exit")

    def _emit_cursor_position(self):
        print("LOG: CodeEditor._emit_cursor_position - Entry")
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.cursor_position_changed_signal.emit(line, column)
        print("LOG: CodeEditor._emit_cursor_position - Exit")

    def setup_completer(self):
        print("LOG: CodeEditor.setup_completer - Entry")
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setModel(QStringListModel())
        self.completer.activated.connect(self.insert_completion)

        self.cursorPositionChanged.connect(self.show_completion_if_dot)
        print("LOG: CodeEditor.setup_completer - Exit")

    def show_completion_if_dot(self):
        print("LOG: CodeEditor.show_completion_if_dot - Entry")
        cursor = self.textCursor()
        text_before_cursor = self.toPlainText()[:cursor.position()]
        if text_before_cursor and text_before_cursor[-1] == '.':
            self.request_completions()
        elif self.completer.popup().isVisible():
            self.completer.popup().hide()
        print("LOG: CodeEditor.show_completion_if_dot - Exit")

    def request_completions(self):
        print("LOG: CodeEditor.request_completions - Entry")
        text = self.toPlainText()
        line = self.textCursor().blockNumber() + 1
        column = self.textCursor().columnNumber()
        file_path = self.file_path if self.file_path else "untitled.py"

        worker = JediCompletionWorker(text, line, column, file_path)
        worker.signals.result.connect(self._handle_completions_result)
        worker.signals.error.connect(lambda msg: sys.stderr.write(f"Jedi error: {msg}\n"))
        self.thread_pool.start(worker)
        print("LOG: CodeEditor.request_completions - Exit")

    @Slot(list)
    def _handle_completions_result(self, words):
        print("LOG: CodeEditor._handle_completions_result - Entry")
        self.completer.model().setStringList(words)

        if words:
            cursor_rect = self.cursorRect(self.textCursor())
            self.completer.popup().setGeometry(
                self.mapToGlobal(cursor_rect.bottomLeft()).x(),
                self.mapToGlobal(cursor_rect.bottomLeft()).y(),
                self.completer.popup().sizeHint().width(),
                self.completer.popup().sizeHint().height()
            )
            self.completer.complete()
        else:
            self.completer.popup().hide()
        print("LOG: CodeEditor._handle_completions_result - Exit")

    def insert_completion(self, completion):
        print("LOG: CodeEditor.insert_completion - Entry")
        if self.completer.widget() is not self:
            print("LOG: CodeEditor.insert_completion - Completer widget mismatch, returning.")
            return

        tc = self.textCursor()
        extra = len(self.completer.completionPrefix())
        
        self._is_programmatic_change = True # Set flag before programmatic change
        tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, extra)
        tc.insertText(completion)
        self.setTextCursor(tc)
        self._is_programmatic_change = False # Reset flag after programmatic change
        print("LOG: CodeEditor.insert_completion - Exit")

    def setup_linter(self):
        print("LOG: CodeEditor.setup_linter - Entry")
        self.linter_timer = QTimer(self)
        self.linter_timer.setInterval(700)
        self.linter_timer.setSingleShot(True)
        self.linter_timer.timeout.connect(self.lint_code)
        print("LOG: CodeEditor.setup_linter - Exit")

    def lint_code(self):
        print("LOG: CodeEditor.lint_code - Entry")
        code = self.toPlainText()
        file_path = self.file_path if self.file_path else "untitled.py"
        worker = PyflakesLinterWorker(code)
        worker.signals.result.connect(self.apply_linting_highlights)
        worker.signals.error.connect(lambda msg: sys.stderr.write(f"Pyflakes error: {msg}\n"))
        self.thread_pool.start(worker)
        print("LOG: CodeEditor.lint_code - Exit")

    def apply_linting_highlights(self, errors):
        print("LOG: CodeEditor.apply_linting_highlights - Entry")
        self._is_programmatic_change = True # Set flag before programmatic change
        extra_selections = []
        error_format = QTextCharFormat()
        error_format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        error_format.setUnderlineColor(QColor("red"))

        for line_num, col_num, message in errors:
            block = self.document().findBlockByNumber(line_num - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.StartOfBlock)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)

                selection = QTextEdit.ExtraSelection()
                selection.format = error_format
                selection.cursor = cursor
                extra_selections.append(selection)

        self.setExtraSelections(extra_selections)
        self._is_programmatic_change = False # Reset flag after programmatic change
        print("LOG: CodeEditor.apply_linting_highlights - Exit")

    def keyPressEvent(self, event: QKeyEvent):
        print(f"LOG: CodeEditor.keyPressEvent - Key: {event.key()}, Text: '{event.text()}' - Entry")
        
        # Host-side logic to reclaim control
        if self.isReadOnly(): # The host is currently a viewer
            # This means the host is trying to type while a client has control.
            # Instead of typing, emit the signal to reclaim control.
            self.control_reclaim_requested.emit()
            event.accept() # Consume the event so no character is typed yet.
            return
        
        cursor = self.textCursor()
        key = event.key()
        text = event.text()
        
        # Get character to the right of the cursor
        char_after_cursor = ''
        if cursor.position() < len(self.toPlainText()):
            char_after_cursor = self.toPlainText()[cursor.position()]

        # Get character to the left of the cursor
        char_before_cursor = ''
        if cursor.position() > 0:
            char_before_cursor = self.toPlainText()[cursor.position() - 1]

        # 1. Handle Tab for indentation
        if key == Qt.Key.Key_Tab:
            self._is_programmatic_change = True
            if cursor.hasSelection():
                # Indent selected lines
                start_block = cursor.blockNumber()
                end_block = self.document().findBlock(cursor.anchor()).blockNumber()
                if start_block > end_block:
                    start_block, end_block = end_block, start_block
                
                cursor.beginEditBlock()
                block = self.document().findBlockByNumber(start_block)
                while block.isValid() and block.blockNumber() <= end_block:
                    cursor_for_block = QTextCursor(block)
                    cursor_for_block.movePosition(QTextCursor.StartOfBlock)
                    cursor_for_block.insertText("    ") # 4 spaces for tab
                    block = block.next()
                cursor.endEditBlock()
            else:
                # Insert 4 spaces at cursor position
                cursor.insertText("    ")
            self._is_programmatic_change = False
            event.accept() # Consume the event
            print("LOG: CodeEditor.keyPressEvent - Tab handled, Exit")
            return

        # 2. Handle "Smart Over-Typing" for Closing Brackets
        if text in self.CLOSING_CHARS and not cursor.hasSelection():
            if char_after_cursor == text:
                self._is_programmatic_change = True
                cursor.movePosition(QTextCursor.NextCharacter)
                self.setTextCursor(cursor)
                self._is_programmatic_change = False
                event.accept() # Consume the event
                print("LOG: CodeEditor.keyPressEvent - Over-typing handled, Exit")
                return

        # 3. Handle Context-Aware Insertion for Opening Brackets (Auto-pairing)
        if text in self.PAIRS:
            if cursor.hasSelection():
                # Wrap selection
                selected_text = cursor.selectedText()
                self._is_programmatic_change = True
                cursor.insertText(text + selected_text + self.PAIRS[text])
                cursor.setPosition(cursor.position() - len(selected_text) - 1) # Move cursor back inside
                self.setTextCursor(cursor)
                self._is_programmatic_change = False
                event.accept() # Consume the event
                print("LOG: CodeEditor.keyPressEvent - Auto-pair wrap handled, Exit")
                return
            else:
                # Context-aware insertion
                should_auto_pair = False
                if not char_after_cursor or char_after_cursor.isspace() or char_after_cursor in self.CLOSING_CHARS:
                    should_auto_pair = True
                
                # Special case for quotes: don't auto-pair if char before is same quote
                if text in ['"', "'"] and char_before_cursor == text:
                    should_auto_pair = False

                if should_auto_pair:
                    self._is_programmatic_change = True
                    cursor.insertText(text + self.PAIRS[text])
                    cursor.movePosition(QTextCursor.PreviousCharacter) # Move cursor back inside
                    self.setTextCursor(cursor)
                    self._is_programmatic_change = False
                    event.accept() # Consume the event
                    print("LOG: CodeEditor.keyPressEvent - Context-aware auto-pair insert handled, Exit")
                    return
        
        # 4. Smart Backspace
        if key == Qt.Key.Key_Backspace and not cursor.hasSelection():
            if char_before_cursor in self.PAIRS and char_after_cursor == self.PAIRS[char_before_cursor]:
                self._is_programmatic_change = True
                cursor.beginEditBlock()
                cursor.deletePreviousChar() # Delete opening char
                cursor.deleteChar()         # Delete closing char
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self._is_programmatic_change = False
                event.accept() # Consume the event
                print("LOG: CodeEditor.keyPressEvent - Smart Backspace handled, Exit")
                return

        # If none of the special cases are handled, call the default handler
        super().keyPressEvent(event)
        print("LOG: CodeEditor.keyPressEvent - Default handler, Exit")