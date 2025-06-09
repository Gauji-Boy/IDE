# code_editor.py

import sys
from PySide6.QtWidgets import QPlainTextEdit, QApplication, QCompleter, QListView, QToolTip 
from PySide6.QtGui import QKeyEvent, QTextCursor, QTextCharFormat, QColor, QPainter, QFont # Added QFont
from PySide6.QtCore import Qt, QTimer, QRect, QSize, QStringListModel, QEvent, Signal
from pyflakes.api import check as pyflakes_check
from pyflakes.reporter import Reporter as PyflakesReporter
import jedi
import re # For smart deletion regex (though not explicitly used in current smart deletion logic)

class CustomPyflakesReporter(PyflakesReporter):
    def __init__(self):
        super().__init__(None, None) # error_stream, warning_stream (None, None means don't print to console)
        self.errors = []

    def unexpectedError(self, filename, msg):
        # Store basic info, actual line might be unknown or less relevant for unexpected
        self.errors.append({'lineno': 1, 'message': f"Unexpected error: {msg}", 'col': 0})

    def syntaxError(self, filename, msg, lineno, offset, text):
        self.errors.append({'lineno': lineno, 'message': msg, 'col': offset or 0})

    def flake(self, message): # message is a pyflakes.messages.Message object
        self.errors.append({
            'lineno': message.lineno,
            'message': message.message % message.message_args, # Format the message string
            'col': message.col
        })

class CodeEditor(QPlainTextEdit):
    """
    A QPlainTextEdit subclass with features like auto-pairing,
    real-time linting, and code completion.
    """
    host_wants_to_reclaim_control = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Auto Pairing Setup
        self.pairs = {'(': ')', '{': '}', '[': ']', '"': '"', "'": "'"}

        # Linting Setup
        self.linting_errors = [] 
        self.linting_timer = QTimer(self)
        self.linting_timer.setSingleShot(True)
        self.linting_timer.setInterval(1500) # 1.5 seconds delay
        self.linting_timer.timeout.connect(self._run_linter)
        self.textChanged.connect(self.linting_timer.start) # Trigger timer on text change

        # Code Completion Setup
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer_model = QStringListModel(self)
        self.completer.setModel(self.completer_model)
        # Ensure the signal for string argument is used
        # The isinstance check for Signal might fail here if Signal was not yet imported,
        # but it's a type hint / defensive check. The primary connection method is by name.
        self.completer.activated[str].connect(self._insert_completion_text)


        # Connect textChanged for completion triggering
        self.textChanged.connect(self._on_text_changed_for_completion)

    def keyPressEvent(self, event: QKeyEvent):
        # --- Control Reclaim Logic ---
        if self.isReadOnly(): # The host is currently a viewer
            # This event signals the host wants to type again.
            # Instead of processing the key, emit a custom signal.
            self.host_wants_to_reclaim_control.emit()
            event.accept() # Indicate the event has been handled
            return # Absorb the key press for now

        # --- Existing Logic ---
        key_text = event.text()
        cursor = self.textCursor()

        # Smart Deletion
        if event.key() == Qt.Key_Backspace:
            char_before_cursor = self.document().characterAt(cursor.position() - 1)
            char_after_cursor = self.document().characterAt(cursor.position())

            # Check if (char_before_cursor, char_after_cursor) form a pair from self.pairs
            is_pair = False
            if char_before_cursor in self.pairs and self.pairs[char_before_cursor] == char_after_cursor:
                is_pair = True
            
            if is_pair:
                # Need to ensure no race condition with other backspace handlers if any
                # For simplicity, we directly manipulate.
                cursor.beginEditBlock()
                cursor.deletePreviousChar() # Deletes char_before_cursor
                cursor.deleteChar()         # Deletes char_after_cursor
                cursor.endEditBlock()
                self.setTextCursor(cursor)  # Ensure cursor position is updated if needed
                event.accept()
                return

        # Selection Wrapping
        if key_text in self.pairs and cursor.hasSelection():
            selected_text = cursor.selectedText()
            cursor.insertText(key_text + selected_text + self.pairs[key_text])
            event.accept()
            return

        # Over-Typing Closing Character
        if key_text in self.pairs.values(): # key_text is a closing character
            # Check if the character we are about to type is the same as the one after the cursor
            char_after_cursor = self.document().characterAt(cursor.position())
            if key_text == char_after_cursor:
                cursor.movePosition(QTextCursor.NextCharacter) # Just move cursor forward
                self.setTextCursor(cursor)
                event.accept()
                return
        
        # Auto-Insertion of Opening Character (and its pair)
        if key_text in self.pairs: # key_text is an opening character
            cursor.insertText(key_text + self.pairs[key_text])
            cursor.movePosition(QTextCursor.PreviousCharacter) # Move cursor between the pair
            self.setTextCursor(cursor)
            event.accept()
            return

        super().keyPressEvent(event) # Default handling for other keys

    def _run_linter(self):
        code = self.toPlainText()
        if not code.strip(): # If code is empty or only whitespace
            self.linting_errors = []
            self._update_linting_highlights()
            return

        reporter = CustomPyflakesReporter()
        try:
            pyflakes_check(code, 'current_script.py', reporter=reporter)
            self.linting_errors = reporter.errors
        except Exception as e: # Catch potential errors during linting itself
            print(f"Linter crashed: {e}")
            self.linting_errors = [{'lineno': 1, 'message': f"Linter error: {e}", 'col': 0}]
        
        self._update_linting_highlights()

    def _update_linting_highlights(self):
        extra_selections = []
        SelectionClass = self.ExtraSelection # QPlainTextEdit.ExtraSelection

        for error in self.linting_errors:
            selection = SelectionClass()
            
            error_format = QTextCharFormat()
            error_format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            error_format.setUnderlineColor(QColor("red"))
            error_format.setToolTip(error['message'])
            
            selection.format = error_format
            
            line_no = error['lineno']
            # Ensure line_no is valid and 1-based for findBlockByNumber which is 0-based
            if line_no > 0:
                block = self.document().findBlockByNumber(line_no - 1)
                if block.isValid():
                    cursor = QTextCursor(block)
                    # Highlight the whole line for simplicity, or a specific part using 'col'
                    col_start = error.get('col', 0)
                    line_text = block.text()
                    # Attempt to highlight a sensible length, e.g., one word or fixed length
                    # This is a simplification; true error length is harder.
                    error_length = 1 
                    if col_start < len(line_text):
                        # Try to find a word or a small segment
                        match = re.search(r'\b\w+\b', line_text[col_start:])
                        if match:
                            error_length = len(match.group(0))
                        else: # Fallback: highlight a few chars or to end of line (simplified)
                            error_length = max(1, min(5, len(line_text) - col_start))
                    else: # col_start might be at or beyond end of line (e.g. for some EOL errors)
                        col_start = max(0, len(line_text) -1) # Highlight last char if possible
                        error_length = 1
                    
                    cursor.setPosition(block.position() + col_start)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, error_length)
                    selection.cursor = cursor
                    extra_selections.append(selection)
                else:
                     print(f"Linter: Invalid block for line number {line_no}")
            else: # Error with no specific line (e.g. unexpectedError)
                # Optionally, could add a general document-level warning or status bar message
                pass


        self.setExtraSelections(extra_selections)

    def _on_text_changed_for_completion(self):
        cursor = self.textCursor()
        current_char_pos_in_block = cursor.positionInBlock()
        if current_char_pos_in_block == 0: # No text before cursor on this line
            self.completer.popup().hide()
            return

        current_line_text_up_to_cursor = cursor.block().text()[:current_char_pos_in_block]
        
        # Trigger on '.' or if starting to type an identifier
        # More sophisticated triggers (e.g., after 'import ') could be added.
        if current_line_text_up_to_cursor.endswith('.') or \
           (len(current_line_text_up_to_cursor) > 0 and current_line_text_up_to_cursor[-1].isalnum() and \
            (len(current_line_text_up_to_cursor) == 1 or not current_line_text_up_to_cursor[-2].isalnum())):
            self._request_completion()
        else:
            self.completer.popup().hide() # Hide if no longer relevant

    def _request_completion(self):
        text = self.toPlainText()
        cursor = self.textCursor()
        
        line_num_jedi = cursor.blockNumber() + 1 # Jedi is 1-indexed for line
        col_num_jedi = cursor.positionInBlock()  # Jedi is 0-indexed for column

        # Determine completion prefix for QCompleter
        text_before_cursor = cursor.block().text()[:col_num_jedi]
        prefix_start_pos = col_num_jedi
        # Regex to find typical prefix characters (alphanumeric, underscore, dot)
        # This matches from the end of the string backwards.
        match = re.search(r"[\w.]*$", text_before_cursor)
        if match:
            prefix = match.group(0)
            self.completer.setCompletionPrefix(prefix)
        else:
            self.completer.setCompletionPrefix("")


        try:
            # Using a dummy path for Jedi. For more advanced setups,
            # a proper project path or sys.path manipulation might be needed.
            script = jedi.Script(code=text, path="dummy_path_for_jedi.py")
            completions = script.complete(line=line_num_jedi, column=col_num_jedi)
        except Exception as e:
            print(f"Jedi completion error: {e}")
            completions = []

        if completions:
            completion_list = [comp.name for comp in completions]
            self.completer_model.setStringList(completion_list)
            
            if self.completer.completionCount() > 0:
                cr = self.cursorRect()
                # Adjust width to be useful for the completer popup
                popup = self.completer.popup()
                # Basic width calculation, might need refinement for different fonts/styles
                width = popup.sizeHintForColumn(0) + \
                        popup.verticalScrollBar().sizeHint().width() + 20 # Padding
                cr.setWidth(width)
                self.completer.complete(cr)
            else:
                self.completer.popup().hide()
        else:
            self.completer.popup().hide()

    def _insert_completion_text(self, completion: str):
        cursor = self.textCursor()
        
        # Calculate how much of the prefix to remove
        # This relies on self.completer.completionPrefix() being set correctly
        # before _request_completion showed the popup.
        prefix = self.completer.completionPrefix()
        
        # Move cursor back by the length of the prefix to delete it
        cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.MoveAnchor, len(prefix))
        # Insert the full completion, effectively replacing the prefix
        cursor.insertText(completion)
        self.setTextCursor(cursor)
        self.completer.popup().hide() # Ensure popup is hidden

# Example usage (optional, for testing this file directly)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = CodeEditor()
    editor.setWindowTitle("Code Editor Test")
    editor.setPlainText("import os\n\ndef my_func(param1, param2):\n    # This is a comment\n    s = \"a string\"\n    s2 = 'another string'\n    num = 123 + 0xFA - 0b101\n    if param1 == os.path:\n        print(s)\n    return s\n\nclass MyClass:\n    def method(self):\n        # Test completion\n        # os.\n        # self.\n        pass\n\nmy_obj = MyClass()\nmy_obj.meth\n\n# Linting test\n# unused_var = 10 \n# print(undeclared_variable)\n")
    editor.show()
    sys.exit(app.exec())
