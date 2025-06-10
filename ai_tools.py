import os
import shutil
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox # Import QMessageBox for error dialogs

class AITools(QObject):
    """
    A collection of tools that the AI agent can use to interact with the IDE.
    These tools are exposed to the Gemini model.
    """
    # Signals for actions that need to be handled by MainWindow
    apply_code_edit_signal = Signal(str)
    get_current_code_signal = Signal()
    read_file_signal = Signal(str)
    write_file_signal = Signal(str, str)
    list_directory_signal = Signal(str)
    
    # Signals to return results from MainWindow back to AITools
    current_code_result = Signal(str)
    read_file_result = Signal(str)
    write_file_result = Signal(str)
    list_directory_result = Signal(str)

    def __init__(self, main_window_instance):
        super().__init__()
        self.main_window = main_window_instance
        
        # Connect signals from MainWindow to AITools slots for results
        self.main_window.ai_get_current_code_result.connect(self.current_code_result)
        self.main_window.ai_read_file_result.connect(self.read_file_result)
        self.main_window.ai_write_file_result.connect(self.write_file_result)
        self.main_window.ai_list_directory_result.connect(self.list_directory_result)

    def get_current_code(self):
        """
        Returns the full text content of the currently active CodeEditor.
        """
        current_editor = self.main_window._get_current_code_editor()
        if current_editor:
            return current_editor.toPlainText()
        return "Error: No active code editor found."

    def read_file(self, file_path: str):
        """
        Reads and returns the content of a specified file from the file system.
        Args:
            file_path (str): The path to the file to read.
        """
        try:
            # Ensure the path is absolute and within the project directory for security
            abs_path = os.path.abspath(file_path)
            if not abs_path.startswith(os.path.abspath('.')): # Assuming current directory is project root
                return f"Error: Access denied. File path '{file_path}' is outside the allowed project directory."

            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            return f"Error: File not found at '{file_path}'."
        except Exception as e:
            return f"Error reading file '{file_path}': {e}"

    def write_file(self, file_path: str, content: str):
        """
        Writes content to a specified file. If the file exists, it will be overwritten.
        Args:
            file_path (str): The path to the file to write to.
            content (str): The content to write to the file.
        """
        try:
            # Ensure the path is absolute and within the project directory for security
            abs_path = os.path.abspath(file_path)
            if not abs_path.startswith(os.path.abspath('.')): # Assuming current directory is project root
                return f"Error: Access denied. File path '{file_path}' is outside the allowed project directory."

            # Create directories if they don't exist
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)

            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to file: '{file_path}'."
        except Exception as e:
            return f"Error writing to file '{file_path}': {e}"

    def list_directory(self, path: str = "."):
        """
        Lists the files and folders in a given directory.
        Args:
            path (str): The directory path to list. Defaults to current directory.
        """
        try:
            # Ensure the path is absolute and within the project directory for security
            abs_path = os.path.abspath(path)
            if not abs_path.startswith(os.path.abspath('.')): # Assuming current directory is project root
                return f"Error: Access denied. Directory path '{path}' is outside the allowed project directory."

            contents = os.listdir(abs_path)
            files = [f for f in contents if os.path.isfile(os.path.join(abs_path, f))]
            dirs = [d for d in contents if os.path.isdir(os.path.join(abs_path, d))]
            return {
                "files": files,
                "directories": dirs
            }
        except FileNotFoundError:
            return f"Error: Directory not found at '{path}'."
        except Exception as e:
            return f"Error listing directory '{path}': {e}"

    @Slot(str) # Keep PySide slot decorator for internal connections
    def apply_code_edit(self, new_code: str):
        """
        Applies the provided new_code to the currently active CodeEditor.
        This tool does not return data to the AI; it emits a signal to the MainWindow.
        Args:
            new_code (str): The complete new content to set in the code editor.
        """
        print("AITools: apply_code_edit called, emitting signal.")
        self.apply_code_edit_signal.emit(new_code)
        # The AI doesn't need a return value for this, as it's an action.
        # We'll rely on the UI update for user feedback.
        return "Code edit applied successfully (signal emitted)." # Return a confirmation for the AI