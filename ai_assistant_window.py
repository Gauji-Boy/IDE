from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel, QHBoxLayout,
    QFrame, QCheckBox, QToolButton, QApplication
)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QIcon, QFont, QPixmap
import os
from ai_agent import GeminiAgent, GeminiAgentWorker # Import the agent and worker

class AIAssistantWindow(QDialog):
    """
    A sophisticated dialog window for interacting with the Gemini-powered AI assistant,
    matching the provided UI design.
    """
    user_message_sent = Signal(str) # Signal to send user input to the agent

    def __init__(self, main_window_instance, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Assistant")
        self.setFixedSize(800, 600) # Fixed size as per design

        self.main_window = main_window_instance
        self.gemini_agent = GeminiAgent(self.main_window) # Pass main_window_instance to agent
        self.current_worker = None # To hold the QThread worker

        self.load_stylesheet("styling.qss")
        self.setup_ui()
        self.setup_connections()

    def load_stylesheet(self, filename):
        """Loads a QSS file and applies it to the application."""
        try:
            with open(filename, "r") as f:
                _style = f.read()
                self.setStyleSheet(_style)
        except FileNotFoundError:
            print(f"Error: Stylesheet file '{filename}' not found.")
        except Exception as e:
            print(f"Error loading stylesheet '{filename}': {e}")

    def setup_ui(self):
        """
        Sets up the user interface components for the AI assistant window,
        matching the provided design.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20) # Add some padding
        main_layout.setSpacing(15) # Spacing between sections

        # 1. Top Logo/Icon
        logo_label = QLabel()
        # Placeholder for a kangaroo icon. You might need to provide an actual image file.
        # For now, using a generic icon or text.
        # If you have a 'kangaroo.png' in an 'icons' folder:
        # pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'icons', 'kangaroo.png'))
        # logo_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setText("🦘") # Placeholder text icon
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFont(QFont("Segoe UI Emoji", 36)) # Larger font for emoji
        main_layout.addWidget(logo_label)

        # 2. Task Display Frame
        task_frame = QFrame()
        task_frame_layout = QVBoxLayout(task_frame)
        task_frame_layout.setContentsMargins(15, 15, 15, 15)
        task_frame_layout.setSpacing(8)

        self.task_title_label = QLabel("### **Prompt: Integrate a Gemini-Powered AI Assistant**")
        self.task_title_label.setObjectName("taskTitle") # For QSS styling
        self.task_title_label.setTextFormat(Qt.MarkdownText)
        task_frame_layout.addWidget(self.task_title_label)

        task_stats_layout = QHBoxLayout()
        self.tokens_up_label = QLabel("↑ 814.1k")
        self.tokens_up_label.setObjectName("taskStat")
        self.tokens_down_label = QLabel("↓ 10.9k")
        self.tokens_down_label.setObjectName("taskStat")
        self.cost_label = QLabel("$$ 0.08")
        self.cost_label.setObjectName("taskStat")
        task_stats_layout.addWidget(self.tokens_up_label)
        task_stats_layout.addWidget(self.tokens_down_label)
        task_stats_layout.addWidget(self.cost_label)
        task_stats_layout.addStretch() # Push stats to left
        task_frame_layout.addLayout(task_stats_layout)

        self.task_description_label = QLabel("Generate, refactor, and debug code with an AI assistant that can read and write files, list directories, and apply edits directly to your active editor.")
        self.task_description_label.setObjectName("taskDescription") # For QSS styling
        self.task_description_label.setWordWrap(True)
        task_frame_layout.addWidget(self.task_description_label)

        main_layout.addWidget(task_frame)

        # 3. Features Section
        features_layout = QHBoxLayout()
        features_layout.setSpacing(20)

        # Customizable Modes
        modes_layout = QHBoxLayout()
        modes_icon = QLabel("⚙️") # Gear icon
        modes_icon.setFont(QFont("Segoe UI Emoji", 18))
        modes_text_layout = QVBoxLayout()
        modes_title = QLabel("<b>Customizable Modes</b>")
        modes_description = QLabel("Tailor AI behavior for specific tasks.")
        modes_description.setWordWrap(True)
        modes_text_layout.addWidget(modes_title)
        modes_text_layout.addWidget(modes_description)
        modes_layout.addWidget(modes_icon)
        modes_layout.addLayout(modes_text_layout)
        modes_layout.addStretch() # Push content to left

        # Boomerang Tasks
        boomerang_layout = QHBoxLayout()
        boomerang_icon = QLabel("🔄") # Cycle icon
        boomerang_icon.setFont(QFont("Segoe UI Emoji", 18))
        boomerang_text_layout = QVBoxLayout()
        boomerang_title = QLabel("<b>Boomerang Tasks</b>")
        boomerang_description = QLabel("AI can ask for clarification or more info.")
        boomerang_description.setWordWrap(True)
        boomerang_text_layout.addWidget(boomerang_title)
        boomerang_text_layout.addWidget(boomerang_description)
        boomerang_layout.addWidget(boomerang_icon)
        boomerang_layout.addLayout(boomerang_text_layout)
        boomerang_layout.addStretch() # Push content to left

        features_layout.addLayout(modes_layout)
        features_layout.addLayout(boomerang_layout)
        features_layout.addStretch() # Distribute space
        main_layout.addLayout(features_layout)

        # 4. Main Input Area
        input_area_layout = QVBoxLayout()
        input_area_layout.setSpacing(10)

        self.auto_approve_checkbox = QCheckBox("Auto-approve: Read, Write, Execute, Install")
        input_area_layout.addWidget(self.auto_approve_checkbox)

        self.task_input_textedit = QTextEdit()
        self.task_input_textedit.setPlaceholderText("Type your task here...")
        self.task_input_textedit.setFixedHeight(100) # Multi-line input
        input_area_layout.addWidget(self.task_input_textedit)

        main_layout.addLayout(input_area_layout)

        # 5. Bottom Action Bar
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.setContentsMargins(0, 0, 0, 0) # No extra margins

        # Left side status info
        status_left_layout = QHBoxLayout()
        status_left_layout.setSpacing(10)
        status_left_layout.addWidget(QLabel("@ Code"))
        status_left_layout.addWidget(QLabel("^")) # Placeholder for up arrow
        status_left_layout.addWidget(QLabel("+")) # Placeholder for plus
        status_left_layout.addWidget(QLabel("☰")) # Placeholder for hamburger menu
        status_left_layout.addWidget(QLabel("Gemini 2.5 Flash"))
        bottom_bar_layout.addLayout(status_left_layout)

        bottom_bar_layout.addStretch() # Push right side buttons to the right

        # Right side action buttons
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.setSpacing(10)

        camera_button = QToolButton()
        camera_button.setIcon(QIcon.fromTheme("camera-photo")) # Placeholder icon
        camera_button.setText("Camera") # Text for accessibility/tooltip
        camera_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        action_buttons_layout.addWidget(camera_button)

        mic_button = QToolButton()
        mic_button.setIcon(QIcon.fromTheme("audio-input-microphone")) # Placeholder icon
        mic_button.setText("Mic")
        mic_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        action_buttons_layout.addWidget(mic_button)

        self.send_act_button = QPushButton("Send/Act")
        self.send_act_button.setIcon(QIcon.fromTheme("mail-send")) # Send icon
        self.send_act_button.setFixedSize(120, 35) # Prominent size
        action_buttons_layout.addWidget(self.send_act_button)

        bottom_bar_layout.addLayout(action_buttons_layout)
        main_layout.addLayout(bottom_bar_layout)

    def setup_connections(self):
        """
        Connects UI signals to slots and agent signals to UI updates.
        """
        self.send_act_button.clicked.connect(self.send_user_message)
        # Connect agent's response signal to update chat history (using task description for now)
        self.gemini_agent.response_received.connect(self.update_task_description)
        
        # Connect agent's tool_code_edit_requested signal to MainWindow's slot
        self.gemini_agent.tool_code_edit_requested.connect(self.main_window.apply_ai_code_edit)

    @Slot()
    def send_user_message(self):
        """
        Retrieves user input, displays it, and sends it to the GeminiAgent.
        """
        message = self.task_input_textedit.toPlainText().strip()
        if not message:
            return

        # For now, update the task description with user message as a placeholder for conversation
        self.task_description_label.setText(f"<b>User:</b> {message}")
        self.task_input_textedit.clear()
        self.send_act_button.setEnabled(False) # Disable button while AI is thinking

        # Create and start a worker thread for the GeminiAgent
        self.current_worker = GeminiAgentWorker(self.gemini_agent, message)
        self.current_worker.response_received.connect(self.update_task_description) # Update description with AI response
        self.current_worker.finished.connect(self.on_worker_finished)
        self.current_worker.start()

    @Slot(str)
    def update_task_description(self, text):
        """
        Updates the task description label with AI's response or status.
        """
        self.task_description_label.setText(f"<b>AI:</b> {text}")
        self.send_act_button.setEnabled(True) # Re-enable button after AI responds

    @Slot()
    def on_worker_finished(self):
        """
        Slot called when the GeminiAgentWorker thread finishes.
        """
        self.send_act_button.setEnabled(True) # Ensure button is re-enabled
        self.current_worker = None # Clear the worker reference