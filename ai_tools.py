import os
from PySide6.QtCore import QObject, Signal

# Placeholder for main_window reference, will be set by the agent
# This is a common pattern if tools are in a separate module and need app context.
# However, for this implementation, we'll pass main_window directly to functions that need it.

class ApplyCodeEditSignal(QObject):
    # Signal to indicate that code in the editor should be changed.
    # It will carry the new code as a string argument.
    apply_edit_signal = Signal(str)

def get_current_code(main_window):
    """Returns the full text content of the currently active CodeEditor."""
    if main_window and hasattr(main_window, 'code_editor'):
        return main_window.code_editor.toPlainText()
    return None # Or raise an error, or return a specific message

def read_file(file_path):
    """Reads and returns the content of a specified file from the file system."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

def write_file(file_path, content):
    """Writes content to a specified file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"File {file_path} written successfully."
    except Exception as e:
        return f"Error writing file {file_path}: {e}"

def list_directory(path):
    """Lists the files and folders in a given directory."""
    try:
        return os.listdir(path)
    except Exception as e:
        return f"Error listing directory {path}: {e}"

def apply_code_edit(new_code, signal_emitter: ApplyCodeEditSignal):
    """
    Emits a signal to instruct the MainWindow to replace the content
    of its CodeEditor with the new_code.
    """
    if signal_emitter:
        signal_emitter.apply_edit_signal.emit(new_code)
        return "Code edit signal emitted."
    return "Error: Signal emitter not provided for apply_code_edit."

# Example of how these tools might be registered or accessed by the agent
# For now, the agent will import them directly.
