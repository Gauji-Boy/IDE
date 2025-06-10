from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextBrowser, QTextEdit, QPushButton, QHBoxLayout, QMessageBox
)
from PySide6.QtCore import Qt
from ai_agent import GeminiAgent # Assuming ai_agent.py is in the same directory or accessible
# ApplyCodeEditSignal will be created in main_window and passed to GeminiAgent,
# which is then passed to AIAssistantWindow.

class AIAssistantWindow(QDialog):
    def __init__(self, main_window, apply_code_signal_emitter, parent=None):
        super().__init__(parent)
        self.main_window = main_window # Reference to the main window
        self.apply_code_signal_emitter = apply_code_signal_emitter

        self.setWindowTitle("AI Assistant")
        self.setGeometry(300, 300, 500, 400) # x, y, width, height

        layout = QVBoxLayout(self)

        self.conversation_browser = QTextBrowser(self)
        self.conversation_browser.setReadOnly(True)
        self.conversation_browser.setOpenExternalLinks(True) # For markdown links if any
        layout.addWidget(self.conversation_browser)

        input_layout = QHBoxLayout()
        self.user_input_edit = QTextEdit(self)
        self.user_input_edit.setFixedHeight(70) # Adjust height as needed
        # Handle Enter key to send, Shift+Enter for newline
        self.user_input_edit.installEventFilter(self) 
        input_layout.addWidget(self.user_input_edit)

        self.send_button = QPushButton("Send", self)
        self.send_button.setFixedHeight(70) # Match input height
        self.send_button.clicked.connect(self.handle_send_message)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        self.setLayout(layout)

        try:
            # Initialize the Gemini Agent
            self.agent = GeminiAgent(
                main_window=self.main_window,
                apply_code_signal_emitter=self.apply_code_signal_emitter
            )
            self.append_to_conversation("AI Assistant", "Hello! How can I help you today?")
        except ValueError as e: # Catch API key error
            QMessageBox.critical(self, "AI Agent Error", str(e))
            self.send_button.setEnabled(False) # Disable sending if agent fails to init
            self.append_to_conversation("Error", str(e))
            self.agent = None # Ensure agent is None if init failed
        except Exception as e: # Catch any other init errors (e.g., network issues with genai.configure)
            QMessageBox.critical(self, "AI Agent Initialization Error", f"Could not initialize Gemini Agent: {e}")
            self.send_button.setEnabled(False)
            self.append_to_conversation("Error", f"Could not initialize Gemini Agent: {e}")
            self.agent = None


    def eventFilter(self, obj, event):
        if obj is self.user_input_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if not (event.modifiers() & Qt.ShiftModifier):
                    self.handle_send_message()
                    return True # Event handled
        return super().eventFilter(obj, event)

    def handle_send_message(self):
        user_message = self.user_input_edit.toPlainText().strip()
        if not user_message:
            return

        if not self.agent:
            self.append_to_conversation("Error", "AI Agent is not initialized. Cannot send message.")
            return

        self.append_to_conversation("You", user_message)
        self.user_input_edit.clear()
        
        # Disable input while AI is processing
        self.user_input_edit.setEnabled(False)
        self.send_button.setEnabled(False)

        try:
            # In a real app, you might run this in a QThread to avoid UI freeze
            ai_response = self.agent.send_message(user_message)
            self.append_to_conversation("AI", ai_response)
        except Exception as e:
            self.append_to_conversation("Error", f"Error communicating with AI: {e}")
            QMessageBox.warning(self, "AI Communication Error", f"Could not get response from AI: {e}")
        finally:
            # Re-enable input
            self.user_input_edit.setEnabled(True)
            self.send_button.setEnabled(True)
            self.user_input_edit.setFocus()


    def append_to_conversation(self, speaker, message):
        # Using simple HTML for bolding speaker names. Markdown can be more complex.
        self.conversation_browser.append(f"<b>{speaker}:</b><br>{message.replace('\n', '<br>')}<br>")
        self.conversation_browser.ensureCursorVisible() # Scroll to the bottom

    def closeEvent(self, event):
        # Clean up resources or save conversation if needed
        super().closeEvent(event)
