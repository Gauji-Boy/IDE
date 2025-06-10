# Aether Editor: Real-Time Collaborative Code Editor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🛠️ Technologies Used

*   **Programming Language:** Python
*   **GUI Framework:** PySide6
*   **Networking:** Python's `socket` module (wrapped by PySide6's `QTcpServer` and `QTcpSocket`)
*   **Code Intelligence:** Jedi (for completions), Pyflakes (for linting), Black (for formatting)

Welcome to Aether Editor, a lightweight and interactive code editor featuring real-time collaborative editing capabilities. This editor allows multiple users to work on the same codebase simultaneously, making it ideal for pair programming, code reviews, and educational purposes.

## ✨ Features

*   **Real-time Text Synchronization:** See your collaborators' changes instantly as they type.
*   **Turn-Based Control:** A clear control mechanism ensures only one user has editing permissions at a time, preventing conflicts.
*   **Integrated Terminal:** Run commands and scripts directly within the editor.
*   **File Explorer:** Easily navigate and manage your project files.
*   **Code Highlighting:** Syntax highlighting for various programming languages (currently focused on Python).
*   **Code Completion (Python):** Intelligent code suggestions powered by Jedi.
*   **Code Linting (Python):** Real-time error and warning detection using Pyflakes.
*   **Code Formatting (Python):** Format your Python code with Black.

## 🚀 Getting Started

Follow these instructions to set up and run Aether Editor on your local machine.

### Prerequisites

Before you begin, ensure you have the following installed:

*   **Python 3.8+**: You can download it from [python.org](https://www.python.org/downloads/).
*   **pip**: Python's package installer (usually comes with Python).

### Setup Instructions

1.  **Clone the Repository (if applicable):**
    If you received this project as a zip file, extract it. Otherwise, if it's in a Git repository, clone it:
    ```bash
    git clone [repository_url]
    cd aether_editor
    ```
    *(Replace `[repository_url]` with the actual URL if you're cloning from a Git repository.)*

2.  **Create a Virtual Environment (Recommended):**
    It's good practice to use a virtual environment to manage project dependencies.
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    *   **Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```

4.  **Install Dependencies:**
    With your virtual environment activated, install all necessary Python packages:
    ```bash
    pip install PySide6 jedi pyflakes black
    ```

### How to Run

Once the setup is complete, you can run the Aether Editor application.

1.  **Activate your virtual environment** (if you haven't already).

2.  **Run the main application file:**
    ```bash
    python main.py
    ```
    Alternatively, on Windows, you can use the provided batch file:
    ```bash
    Run.bat
    ```

    The Aether Editor window should now appear.

## 🤝 Using Collaboration Features

Aether Editor supports a host-client model for collaborative sessions.

### Starting a Hosting Session (Friend A - The Host)

1.  Go to `Session` -> `Start Hosting Session`.
2.  A dialog will appear asking for an IP address and Port. For local testing, you can use `127.0.0.1` (localhost) as the IP address. Choose any available port (e.g., `12345`).
3.  Click `OK`. The status bar will show "Hosting on port [your_port_number]...".
4.  The host automatically starts with editing control.

### Connecting to a Host (Friend B - The Viewer)

1.  Go to `Session` -> `Connect to Host...`.
2.  Enter the IP address and Port provided by the Host (Friend A).
3.  Click `OK`. The status bar will show "Connecting to [IP]:[Port]...".
4.  Once connected, the viewer will be in "viewing only" mode.

### Requesting and Granting Control

*   **Viewer (Friend B) requests control:**
    *   Click the "Request Control" button in the toolbar.
    *   The status bar will show "Requesting control...".

*   **Host (Friend A) grants/declines control:**
    *   When the viewer requests control, a pop-up message will appear on the Host's screen: "The client has requested editing control. Grant control?".
    *   Click `Yes` to grant control to the viewer. The Host will lose editing control and become a viewer.
    *   Click `No` to decline the request. The viewer will be notified that the request was declined.

### Reclaiming Control (Host - Friend A)

*   If the Host has granted control to the Viewer and wishes to reclaim it, simply start typing in the editor. The Host will automatically reclaim control, and the Viewer will lose editing permissions.

### Stopping a Session

*   Either the Host or the Client can stop the session by going to `Session` -> `Stop Current Session`. This will disconnect both parties.

## 🐛 Troubleshooting

*   **"Failed to start hosting: Address already in use"**: This means the port you chose is already being used by another application. Try a different port number.
*   **"Connection refused" / "Host not found"**: Double-check the IP address and port number. Ensure the host is running and accessible on the network.
*   **Text not synchronizing**:
    *   Ensure both parties are connected.
    *   Verify that the user with editing control (`You have editing control.` in the status bar) is the one typing.
    *   Check your firewall settings if you are having trouble connecting across different machines.

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).