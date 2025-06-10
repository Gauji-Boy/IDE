from PySide6.QtCore import QRunnable, QObject, Signal
import black
import traceback

class BlackFormatterSignals(QObject):
    """
    Defines the signals available from a running BlackFormatterWorker.
    """
    finished = Signal(str, str, int) # formatted_text, file_path, editor_index
    error = Signal(str, str, int)    # error_message, file_path, editor_index

class BlackFormatterWorker(QRunnable):
    """
    Worker for running Black code formatting in a separate thread.
    """
    def __init__(self, code_text: str, file_path: str, editor_index: int):
        super().__init__()
        self.code_text = code_text
        self.file_path = file_path
        self.editor_index = editor_index
        self.signals = BlackFormatterSignals()

    def run(self):
        """
        Formats the code using black and emits signals based on success or failure.
        """
        try:
            # Use black.format_str for formatting a string
            # mode=black.FileMode() uses default black settings
            formatted_code = black.format_str(self.code_text, mode=black.FileMode())
            self.signals.finished.emit(formatted_code, self.file_path, self.editor_index)
        except black.parsing.LibCSTError as e:
            # Specific error for syntax issues that black can't parse
            error_message = f"Black formatting failed due to syntax error: {e}"
            self.signals.error.emit(error_message, self.file_path, self.editor_index)
        except Exception as e:
            # Catch any other unexpected errors during formatting
            error_message = f"An unexpected error occurred during formatting: {e}\n{traceback.format_exc()}"
            self.signals.error.emit(error_message, self.file_path, self.editor_index)

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    """
    result = Signal(object)
    error = Signal(str)
    finished = Signal()

class JediCompletionWorker(QRunnable):
    """
    Worker for running Jedi completions in a separate thread.
    """
    def __init__(self, code_text, line, column, filename):
        super().__init__()
        self.code_text = code_text
        self.line = line
        self.column = column
        self.filename = filename
        self.signals = WorkerSignals()

    def run(self):
        try:
            import jedi
            environment = jedi.get_default_environment()
            script = jedi.Script(self.code_text, self.line, self.column, self.filename, environment=environment)
            completions = script.complete()
            self.signals.result.emit([c.name for c in completions])
        except Exception as e:
            self.signals.error.emit(f"Jedi completion error: {e}")
        finally:
            self.signals.finished.emit()

class PyflakesLinterWorker(QRunnable):
    """
    Worker for running Pyflakes linting in a separate thread.
    """
    def __init__(self, code_text):
        super().__init__()
        self.code_text = code_text
        self.signals = WorkerSignals()

    def run(self):
        try:
            from pyflakes import api
            from pyflakes import messages as m
            
            # Redirect stderr to capture pyflakes output
            original_stderr = sys.stderr
            sys.stderr = StringIO()
            
            # Run pyflakes check
            tree = api.parse(self.code_text)
            warnings = api.check(tree, os.path.basename("temp_file.py")) # Use a dummy filename
            
            # Get output from StringIO
            output = sys.stderr.getvalue()
            sys.stderr = original_stderr # Restore stderr
            
            # Parse warnings/errors
            problems = []
            for warning in warnings:
                if isinstance(warning, m.UnusedImport):
                    problems.append(f"Unused import: {warning.message} at line {warning.lineno}")
                elif isinstance(warning, m.UndefinedName):
                    problems.append(f"Undefined name: {warning.message} at line {warning.lineno}")
                else:
                    problems.append(f"Pyflakes: {warning.message} at line {warning.lineno}")
            
            self.signals.result.emit(problems)
        except Exception as e:
            self.signals.error.emit(f"Pyflakes linting error: {e}")
        finally:
            self.signals.finished.emit()

import sys
from io import StringIO