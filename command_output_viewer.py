from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QPushButton
from PySide6.QtCore import QProcess, Signal, Slot, Qt
from PySide6.QtGui import QTextCharFormat, QColor
import sys
import os

class CommandOutputViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        self.output_display = QPlainTextEdit(self)
        self.output_display.setReadOnly(True)
        self.output_display.setStyleSheet("background-color: black; color: white; font-family: 'Consolas', 'Monospace';")
        self.layout.addWidget(self.output_display)

        self.clear_button = QPushButton("Clear Output", self)
        self.clear_button.clicked.connect(self.output_display.clear)
        self.layout.addWidget(self.clear_button)

        self.setLayout(self.layout)

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

    def execute_command(self, command_parts: list[str], working_dir: str):
        """
        Executes a command and displays its output.
        command_parts: A list of strings representing the command and its arguments.
        working_dir: The directory in which to execute the command.
        """
        if self.process is not None and self.process.state() == QProcess.Running:
            self.process.kill()
            self.process.waitForFinished()
            self.append_output("\n--- Previous process terminated ---\n", color="yellow")

        self.output_display.clear()
        self.append_output(f"Executing in: {working_dir}\n", color="yellow")

        self.process = QProcess(self)
        self.process.setWorkingDirectory(working_dir)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        self.process.readyReadStandardOutput.connect(self._on_output_ready)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)

        full_command_str = ' '.join(command_parts)
        self.append_output(f"> {full_command_str}\n", color="cyan")

        try:
            # QProcess.start takes program and arguments separately
            program = command_parts[0]
            args = command_parts[1:]
            self.process.start(program, args)
            if not self.process.waitForStarted(5000):
                self.append_output(f"Error: Could not start command: {self.process.errorString()}\n", color="red")
        except Exception as e:
            self.append_output(f"Exception starting command: {e}\n", color="red")

    @Slot()
    def _on_output_ready(self):
        data = self.process.readAllStandardOutput().data()
        text = data.decode(sys.getdefaultencoding(), errors='replace')
        self.append_output(text)

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code, exit_status):
        self.append_output(f"\n--- Process finished with exit code {exit_code} ---\n")
        self.process = None # Safely clear the process reference

    @Slot(QProcess.ProcessError)
    def _on_error(self, error):
        if self.process:
            self.append_output(f"\nProcess Error: {self.process.errorString()}\n", color="red")
        else:
            self.append_output(f"\nUnknown Process Error: {error}\n", color="red")
        self.process = None # Safely clear the process reference