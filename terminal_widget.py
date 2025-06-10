from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit
from PySide6.QtCore import QProcess, Signal, Slot
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
import sys
import os
import tempfile

class TerminalWidget(QWidget):
    output_received = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self) # Initialize QProcess here
        self.is_interactive_mode = False # Flag for interactive debugging
        self.setup_ui()
        self._start_shell() # Start the default shell

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.output_display = QTextEdit(self)
        self.output_display.setReadOnly(True)
        self.output_display.setStyleSheet("background-color: black; color: white; font-family: 'Consolas', 'Monospace';")
        self.layout.addWidget(self.output_display)

        self.input_line = QLineEdit(self)
        self.input_line.setStyleSheet("background-color: black; color: white;")
        self.input_line.returnPressed.connect(self.send_command)
        self.layout.addWidget(self.input_line)

        self.setLayout(self.layout)

        self.output_received.connect(self.append_output)

    def _start_shell(self):
        """Starts the default system shell."""
        if sys.platform.startswith('win'):
            shell_command = ["cmd.exe"]
        else:
            shell_command = ["bash"] # Or "zsh", "sh", etc.
        self._start_process(shell_command, os.getcwd(), interactive=True) # Start shell in interactive mode

    def _start_process(self, command, working_directory, interactive=False):
        """
        Starts a QProcess with the given command and working directory.
        If interactive is True, stdin is connected for user input.
        """
        if self.process.state() == QProcess.Running:
            self.process.kill()
            self.process.waitForFinished(1000) # Wait a bit for it to terminate

        self.is_interactive_mode = interactive
        self.process.setProcessChannelMode(QProcess.MergedChannels) # Merge stdout and stderr
        self.process.setWorkingDirectory(working_directory)

        # Disconnect old signals to prevent multiple connections
        try:
            self.process.readyReadStandardOutput.disconnect(self.read_output)
        except TypeError:
            pass # Signal not connected
        try:
            self.process.finished.disconnect(self.process_finished)
        except TypeError:
            pass # Signal not connected

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.process_finished)

        try:
            self.process.start(command[0], command[1:])
            if not self.process.waitForStarted(5000): # 5 second timeout
                self.append_output(f"Error: Could not start process: {self.process.errorString()}\n", color="red")
        except Exception as e:
            self.append_output(f"Exception starting process: {e}\n", color="red")

    @Slot()
    def read_output(self):
        # Read both stdout and stderr if merged
        data = self.process.readAllStandardOutput().data()
        text = data.decode(sys.getdefaultencoding(), errors='replace')
        self.output_received.emit(text)

    @Slot(str)
    def append_output(self, text, color=None):
        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if color:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.insertText(text, fmt)
        else:
            cursor.insertText(text)
        
        self.output_display.setTextCursor(cursor)
        self.output_display.ensureCursorVisible()

    @Slot()
    def send_command(self):
        command = self.input_line.text()
        self.input_line.clear()

        if self.process and self.process.state() == QProcess.Running:
            if self.is_interactive_mode:
                # For interactive processes (like pdb), just send the command + newline
                self.append_output(f"> {command}\n", color="cyan") # Echo command for interactive mode
                self.process.write((command + '\n').encode(sys.getdefaultencoding()))
            else:
                # For shell, echo prompt and command
                prompt = "C:\\Users\\You> " if sys.platform.startswith('win') else "$ "
                self.append_output(f"{prompt}{command}\n") # Echo command
                self.process.write((command + '\n').encode(sys.getdefaultencoding()))
        else:
            self.append_output("No process running. Starting shell...\n")
            self._start_shell()
            # After starting shell, the user will need to re-type the command if it was meant for the shell.
            # For interactive processes, the process needs to be started via debug_code.

    @Slot(int, QProcess.ExitStatus)
    def process_finished(self, exit_code, exit_status):
        if self.is_interactive_mode:
            self.append_output(f"\nInteractive session exited with code {exit_code} ({exit_status}).\n", color="green" if exit_code == 0 else "red")
            self.is_interactive_mode = False # Reset interactive mode
            self._start_shell() # Restart the default shell after interactive session ends
        else:
            self.append_output(f"\nShell exited with code {exit_code} ({exit_status}).\n", color="green" if exit_code == 0 else "red")
            self.append_output("Type a command to restart the shell.\n")

    def clear_output(self):
        """Clears the text in the output display."""
        self.output_display.clear()

    def start_interactive_process(self, command, working_directory):
        """
        Starts an interactive process (like a debugger) in the terminal.
        """
        self.clear_output()
        self._start_process(command, working_directory, interactive=True)
        self.append_output(f"Started interactive process: {' '.join(command)}\n", color="yellow")

    def run_command_sequence(self, commands_list, temp_file_path, selected_language):
        """
        Executes a sequence of commands (e.g., compile then run) in the terminal.
        This is non-interactive.
        """
        self.is_interactive_mode = False # Ensure non-interactive mode for sequences
        self.clear_output() # Clear output for new run

        if not commands_list:
            self.append_output("No commands to execute.\n", color="red")
            return

        # Use a helper to run commands sequentially
        self._execute_sequential_command(commands_list, temp_file_path, selected_language)

    def _execute_sequential_command(self, commands_list, temp_file_path, selected_language):
        """Helper to execute commands one by one."""
        if not commands_list:
            # All commands executed, clean up
            self._cleanup_temp_files(temp_file_path, selected_language)
            self.append_output("Code execution finished.\n", color="green")
            return

        current_command = commands_list.pop(0)
        
        command_str = ' '.join(current_command)
        prompt = "C:\\Users\\You> " if sys.platform.startswith('win') else "$ "
        self.append_output(f"\n{prompt}{command_str}\n", color="yellow")

        # Disconnect old signals from self.process if any
        try:
            self.process.readyReadStandardOutput.disconnect(self.read_output)
        except TypeError:
            pass
        try:
            self.process.finished.disconnect(self.process_finished)
        except TypeError:
            pass

        # Connect signals for this specific command sequence
        self.process.readyReadStandardOutput.connect(self._on_script_output)
        self.process.readyReadStandardError.connect(self._on_script_error)
        self.process.finished.connect(lambda exit_code, exit_status:
                                       self._on_script_finished_sequence(exit_code, exit_status, remaining_commands, temp_file_path, selected_language))

        try:
            self.process.start(current_command[0], current_command[1:])
            if not self.process.waitForStarted(5000):
                self.append_output(f"Error: Could not start process: {self.process.errorString()}\n", color="red")
                self._cleanup_temp_files(temp_file_path, selected_language)
        except Exception as e:
            self.append_output(f"Exception starting process: {e}\n", color="red")
            self._cleanup_temp_files(temp_file_path, selected_language)

    @Slot()
    def _on_script_output(self):
        data = self.process.readAllStandardOutput().data()
        text = data.decode(sys.getdefaultencoding(), errors='replace')
        self.append_output(text)

    @Slot()
    def _on_script_error(self):
        data = self.process.readAllStandardError().data()
        text = data.decode(sys.getdefaultencoding(), errors='replace')
        self.append_output(text, color="red")

    @Slot(int, QProcess.ExitStatus)
    def _on_script_finished_sequence(self, exit_code, exit_status, remaining_commands, temp_file_path, selected_language):
        self.append_output(f"\nProcess finished with exit code {exit_code} ({exit_status}).\n", color="green" if exit_code == 0 else "red")

        if exit_code == 0 and remaining_commands:
            self._execute_sequential_command(remaining_commands, temp_file_path, selected_language)
        else:
            # If current command failed or no more commands, clean up
            self._cleanup_temp_files(temp_file_path, selected_language)
            # Reconnect to shell output after sequence finishes
            self.process.readyReadStandardOutput.disconnect(self._on_script_output)
            self.process.readyReadStandardError.disconnect(self._on_script_error)
            self.process.finished.disconnect(lambda exit_code, exit_status:
                                              self._on_script_finished_sequence(exit_code, exit_status, remaining_commands, temp_file_path, selected_language))
            self.process.readyReadStandardOutput.connect(self.read_output)
            self.process.finished.connect(self.process_finished)
            self.append_output("Type a command to restart the shell.\n") # Prompt user to restart shell

    def _cleanup_temp_files(self, temp_file_path, selected_language):
        """Helper to clean up temporary files."""
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        if selected_language == "C++":
            output_file = os.path.splitext(temp_file_path)[0]
            if os.path.exists(output_file):
                os.unlink(output_file)