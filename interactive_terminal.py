from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QLineEdit
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QTextCursor

class InteractiveTerminal(QWidget):
    line_entered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        # Output Area
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFocusPolicy(Qt.NoFocus) # Prevent output view from taking focus
        self.output_view.setStyleSheet("background-color: #282c34; color: #abb2bf;")
        font = QFont("Cascadia Code", 10)
        self.output_view.setFont(font)
        self.output_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.layout().addWidget(self.output_view)

        # Input Line
        self.input_line = QLineEdit()
        self.input_line.setStyleSheet("background-color: #282c34; color: #abb2bf; border: 1px solid #3e4452;")
        self.input_line.setFont(font)
        self.layout().addWidget(self.input_line)
        self.input_line.setFocus() # Set initial focus to the input line

        # Connect input line signal
        self.input_line.returnPressed.connect(self._on_input_submitted)

    def _on_input_submitted(self):
        text = self.input_line.text()
        self.input_line.clear()
        self.line_entered.emit(text)
        self.input_line.setFocus() # Return focus to the input line after submission

    @Slot(str)
    def append_output(self, text: str):
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_view.setTextCursor(cursor)
        self.output_view.insertPlainText(text)
        self.output_view.verticalScrollBar().setValue(self.output_view.verticalScrollBar().maximum())

    @Slot()
    def clear_all(self):
        self.output_view.clear()