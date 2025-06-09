# Code-Sync IDE: Real-time Collaborative Code Editor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- Add other badges if applicable, e.g., build status, version -->

Code-Sync IDE is a lightweight, cross-platform code editor built with Python and PySide6. It offers essential IDE features and specializes in a unique, turn-based real-time collaborative editing experience. This allows two users, a Host and a Client, to work together on the same code, with the Host having explicit control over editing permissions.

## ✨ Key Features

### 📝 Core IDE Functionality
*   **Multi-Tab Editing:** Work on multiple files simultaneously in a tabbed interface.
*   **Syntax Highlighting:** Python syntax highlighting for improved code readability. (Extensible for other languages via custom highlighters).
*   **File Explorer:** Integrated tree-view file explorer to easily navigate and open project files.
*   **Code Formatting:** On-demand code formatting for Python files using the `black` formatter.
*   **Basic Linting:** Real-time Python code linting using `pyflakes` to catch common errors.
*   **Auto-Pairing:** Automatic insertion of closing brackets, parentheses, and quotes.
*   **Smart Deletion:** Deletes paired characters (e.g., `()`, `""`) together.
*   **Code Completion:** Basic code completion suggestions using `jedi`.

### 🚀 Code Execution
*   **Multi-Language Support:** Run code in various languages (e.g., Python, JavaScript) directly within the IDE.
*   **Configurable Runners:** Easily configure new language runners or modify existing ones via `config.py`.
*   **Integrated Output/Terminal:** View program output and error messages in a dedicated panel.

### 🤝 Real-time Collaboration (Host-Approved, Turn-Based)
*   **Host-Centric Control:** The Host initiates the session and starts with editing control.
*   **Client as Viewer:** The Client connects as a read-only viewer by default.
*   **Request Control:** Clients can request editing permission from the Host using a dedicated button.
*   **Explicit Host Approval:** The Host receives a dialog prompt to "Accept" or "Decline" client control requests, ensuring deliberate control transfer.
*   **Turn-Based Editing:** Only one user (the "Active Editor") can type at a time. The other user becomes a "Viewer."
*   **Instant Host Reclaim:** The Host can instantly reclaim editing control at any moment by simply starting to type in their editor.
*   **Clear Role Indication:** The status bar clearly indicates the user's current role (Host/Client) and editing status (Active Editor/Viewer).
*   **Real-time Text Sync:** Code changes from the Active Editor are reflected in real-time for the Viewer.

## 📸 Screenshots (Illustrative)

*Placeholder: Add screenshots of the application here to showcase its interface and features.*

*   `![Main IDE Interface](path/to/your/screenshot_main.png "Main IDE Interface")`
*   `![Collaboration in Action](path/to/your/screenshot_collaboration.png "Collaboration Session")`
*   `![Code Execution Output](path/to/your/screenshot_execution.png "Code Execution Output")`

## 📋 Requirements

*   **Python:** Python 3.9 or newer recommended.
*   **Operating System:** Cross-platform (tested on Windows 10/11, macOS, and common Linux distributions).
*   **Key Libraries:**
    *   `PySide6`: For the graphical user interface.
    *   `black`: For Python code formatting.
    *   `pyflakes`: For Python linting.
    *   `jedi`: For Python code completion.
    *   (These will be installed via `requirements.txt`)

## ⚙️ Setup Instructions

Follow these steps to get Code-Sync IDE up and running on your system:

1.  **Clone the Repository:**
    Open your terminal or command prompt and clone this repository to your local machine:
    ```bash
    git clone https://your-repository-url-here/code-sync-ide.git
    cd code-sync-ide
    ```
    *(Replace `https://your-repository-url-here/code-sync-ide.git` with the actual URL of your repository if it's hosted, otherwise indicate it's from a local source/zip.)*

2.  **Create and Activate a Virtual Environment (Recommended):**
    It's highly recommended to use a virtual environment to manage project dependencies and avoid conflicts with global Python packages.

    *   **On macOS and Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   **On Windows:**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```
    You should see `(venv)` at the beginning of your terminal prompt, indicating the virtual environment is active.

3.  **Install Dependencies:**
    With your virtual environment activated, install the required libraries using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```
    This will install PySide6, black, pyflakes, jedi, and any other necessary packages.

## ▶️ Running the Application

Once the setup is complete, you can run the Code-Sync IDE from the root directory of the project (where `main.py` or `simple_collab_editor.py` is located):

```bash
python main.py
```
*(If your main script is named differently, e.g., `simple_collab_editor.py`, please adjust the command above accordingly.)*

The application window should now open.

## 📖 How to Use

### 📝 Basic Editing & File Management

*   **Creating a New File:**
    *   Click on **File > New File** in the menu bar.
    *   Or use the shortcut: `Ctrl+N` (Windows/Linux) or `Cmd+N` (macOS).
    *   A new "Untitled" tab will open for you to start coding.
*   **Opening an Existing File:**
    *   Click on **File > Open File...** in the menu bar.
    *   Or use the shortcut: `Ctrl+O` (Windows/Linux) or `Cmd+O` (macOS).
    *   A dialog will appear, allowing you to browse and select a file.
    *   Alternatively, you can double-click files in the **File Explorer** panel.
*   **Saving a File:**
    *   To save the currently active file, click on **File > Save File**.
    *   Or use the shortcut: `Ctrl+S` (Windows/Linux) or `Cmd+S` (macOS).
    *   If the file is new ("Untitled"), a "Save As" dialog will appear, prompting you to choose a location and filename.
*   **Save As...:**
    *   To save the current file under a new name or in a different location, click on **File > Save File As...**.
    *   Or use the shortcut: `Ctrl+Shift+S` (Windows/Linux) or `Cmd+Shift+S` (macOS).
*   **Multi-Tab Interface:**
    *   Open multiple files, each in its own tab.
    *   Click on a tab to switch between files.
    *   Close a tab by clicking the 'x' icon on the tab or by middle-clicking the tab. You'll be prompted to save if there are unsaved changes.
*   **Code Formatting (Python):**
    *   Ensure a Python file is open and active.
    *   Click on **Edit > Format Code** in the menu bar.
    *   Or use the shortcut: `Ctrl+Alt+L`.
    *   The code will be formatted using the `black` formatter.
*   **Auto-Pairing & Smart Deletion:**
    *   The editor automatically inserts closing characters for `(`, `{`, `[`, `"`, and `'`.
    *   When you press `Backspace` and the cursor is between a pair like `()`, both characters will be deleted.
    *   If you select text and type an opening character (e.g., `(`), the selected text will be wrapped with the pair (e.g., `(selected_text)`).

### 📂 File Explorer

*   The File Explorer panel is typically located on the left side of the window.
*   **Navigation:** Click on directories to expand or collapse them.
*   **Opening Files:** Double-click on a file in the explorer to open it in a new editor tab. If the file is already open, the IDE will switch to its tab.
*   **Initial Directory:** The explorer defaults to your home directory or the current working directory.

### 🚀 Running Code

Code-Sync IDE allows you to execute code written in various languages directly within the editor.

1.  **Select the Language:**
    *   In the toolbar at the top, find the dropdown menu (it might initially show "Python").
    *   Select the language corresponding to the code in your active editor tab.
    *   *(The available languages are configured in `config.py`.)*

2.  **Write Your Code:**
    *   Ensure the code you want to run is in the currently active editor tab.

3.  **Run the Code:**
    *   Click the **▶️ Run Code** button in the toolbar.
    *   Or press `F5`.

4.  **View Output:**
    *   The output of your program (and any error messages) will be displayed in the **Output Panel** at the bottom of the window.
    *   You can switch between the "Output" tab (for program stdout/stderr) and the "Terminal" tab (which shows the command executed and can be used for more interactive programs if the runner configuration supports it, though current runners primarily use the "Output" tab).
    *   You can choose the default output destination (**Run > Output Panel** or **Run > Integrated Terminal**) from the menu bar.

### 🤝 Collaboration Feature (Host-Approved, Turn-Based)

Code-Sync IDE enables two users to collaborate on the same codebase in real-time. The collaboration is turn-based, meaning only one user can edit at a time, with the Host managing permissions.

**Key Roles:**
*   **Host:** The user who initiates the session and has initial editing control. The Host approves or declines control requests from the Client.
*   **Client:** The user who connects to the Host's session. Starts as a viewer and must request permission to edit.

**Steps to Collaborate:**

1.  **Starting a Hosting Session (Host):**
    *   Go to the menu: **Session > Start Hosting Session**.
    *   The application will attempt to start hosting on a default port (e.g., 54321).
    *   The status bar will display a message like: *"Hosting on [Your IP Address]:[Port]. Waiting for connection..."*
    *   **Note your IP address and the port number displayed.** You will need to share this with the Client.
    *   Initially, the Host has full editing control. Their editor is writable.

2.  **Connecting to a Host (Client):**
    *   Go to the menu: **Session > Connect to Host...**.
    *   A dialog box will appear asking for the Host's IP Address and Port Number.
    *   Enter the IP address and port number provided by the Host.
    *   Click "Connect".
    *   Upon successful connection, the status bar will indicate: *"Peer connected. Collaboration active."* followed by *"Viewing only. Click 'Request Control' to edit."*
    *   The Client's editor will be **read-only**. A "**Request Control**" button will appear and be enabled in the status bar area.

3.  **Requesting Editing Control (Client):**
    *   When the Client wants to make changes, they click the "**Request Control**" button.
    *   The button will become disabled, and the status bar may show: *"Control request sent..."*

4.  **Host Approval/Decline (Host):**
    *   When the Client requests control, a dialog box will appear on the Host's screen: *"A client has requested editing control. Do you approve?"*
    *   **To Approve:** Click "**Yes**" (or "Accept").
        *   The Host's editor will become **read-only**.
        *   The Host's status bar will update to: *"Viewer has control. Press any key to reclaim."*
        *   A `GRANT_CONTROL` message is sent to the Client.
    *   **To Decline:** Click "**No**" (or "Decline").
        *   The Host retains editing control. Their editor remains writable.
        *   The Host's status bar may briefly show *"Control request declined."* before reverting to *"You have editing control."*
        *   A `DECLINE_CONTROL` message is sent to the Client.

5.  **Editing as the Active Editor (Client or Host):**
    *   **Client (after approval):**
        *   The Client's status bar will update to: *"You have editing control."*
        *   The Client's editor will become **writable**.
        *   The "Request Control" button will be disabled.
        *   Any text changes made by the Client are synced in real-time to the Host's view.
    *   **Host (initially, or after reclaiming/declining):**
        *   The Host's status bar shows: *"You have editing control."*
        *   The Host's editor is **writable**.
        *   Any text changes made by the Host are synced in real-time to the Client's view.

6.  **Reclaiming Control (Host):**
    *   If the Client has editing control (Host's editor is read-only), the Host can **instantly reclaim control** by simply **pressing any key to type** in their editor.
    *   The Host's editor will immediately become **writable** again.
    *   The Host's status bar will update to: *"Control reclaimed. You can now edit."*
    *   A `REVOKE_CONTROL` message is sent to the Client, and the Client's editor becomes read-only again (their "Request Control" button will be re-enabled).

7.  **Stopping the Session:**
    *   Either the Host or the Client can end the session.
    *   Go to the menu: **Session > Stop Current Session**.
    *   The connection will be terminated. Both users' editors will become writable, and the status bar will indicate the session has ended. Collaboration-specific UI elements (like the "Request Control" button) will be hidden.

**Important Notes for Collaboration:**
*   Ensure both users are on the same network if connecting via local IP addresses. Firewalls might sometimes block connections; ensure the application is allowed through.
*   The collaboration session focuses on a shared document view. When a user gains control, their current document's content is typically synchronized as the baseline. Text changes are then synced for that document.

## 🛠️ Troubleshooting

Here are some common issues and how to resolve them:

*   **Port Already in Use (Host):**
    *   **Symptom:** When trying to "Start Hosting Session," you get an error like "Server could not start: Address already in use."
    *   **Solution:** The default port (e.g., 54321) is being used by another application. You can either:
        1.  Close the other application using the port.
        2.  (If the application were to support it - currently not implemented) Modify the application to use a different default port. For now, ensure the default port is free.
*   **Connection Failed (Client):**
    *   **Symptom:** Client sees "Connection failed" or "Connection timed out."
    *   **Solutions:**
        *   Verify the Host's IP address and port number are entered correctly.
        *   Ensure the Host is actively hosting a session.
        *   Check network connectivity: Can the Client machine ping the Host machine?
        *   Firewall: Ensure that Code-Sync IDE (or Python) is allowed through firewalls on both the Host and Client machines for private/public networks as applicable.
*   **Python Not Found / `python` vs `python3`:**
    *   **Symptom:** Commands like `python -m venv venv` or `python main.py` fail.
    *   **Solution:** Ensure Python is installed correctly and its location (and `Scripts` subdirectory on Windows) is added to your system's PATH environment variable. On some systems (especially macOS/Linux), you might need to use `python3` instead of `python`.
*   **Module Not Found Errors (e.g., `No module named 'PySide6'`):**
    *   **Symptom:** Application fails to start with errors indicating missing modules.
    *   **Solution:** Make sure you have activated your virtual environment (if you created one) and successfully run `pip install -r requirements.txt`.
*   **Code Execution Issues:**
    *   **Symptom:** Code doesn't run as expected, or errors appear in the output panel related to the runner.
    *   **Solution:**
        *   Verify the correct language is selected in the toolbar.
        *   Check the `config.py` file for the runner configuration of that language. Ensure the command (`cmd`) and extension (`ext`) are correct for your system and the language interpreter/compiler is installed and in your PATH.
        *   Consult the detailed logs printed in the terminal where you launched `main.py` for more specific error messages from the application or the code execution process.
*   **Collaboration State Seems Stuck:**
    *   **Symptom:** Roles don't switch as expected, or UI doesn't update.
    *   **Solution:**
        *   Try stopping the session (**Session > Stop Current Session**) on both ends and restarting it.
        *   Check the console output where you launched `main.py` on both the Host and Client machines. The detailed logging for state changes and messages can help identify where the process got interrupted or if an error occurred.

## ⚙️ Configuration

For advanced users, some aspects of the IDE can be configured:

*   **Code Runners:**
    *   The languages available for execution and how their code is run are defined in the `RUNNER_CONFIG` dictionary within the `config.py` file.
    *   You can modify existing runner configurations or add new ones. Please refer to the extensive comments in `config.py` for details on the structure and available placeholders like `{file}`, `{dir}`, etc.
    *   Ensure any compilers or interpreters specified in `config.py` are installed on your system and accessible via your system's PATH.

## 🤝 Contributing

Contributions are welcome! If you'd like to contribute to Code-Sync IDE, please follow these general steps:

1.  **Fork the Repository.**
2.  **Create a New Branch** for your feature or bug fix (e.g., `git checkout -b feature/awesome-new-feature` or `git checkout -b fix/bug-name`).
3.  **Make Your Changes.**
4.  **Test Your Changes Thoroughly.**
5.  **Commit Your Changes** with clear and descriptive commit messages.
6.  **Push to Your Fork** (e.g., `git push origin feature/awesome-new-feature`).
7.  **Submit a Pull Request** to the main repository for review.

Please ensure your code adheres to any existing style guidelines and includes relevant documentation or comments.

## 📜 License

This project is licensed under the **MIT License**.

See the `LICENSE` file (you may need to create one if it doesn't exist - typically just the standard MIT License text) for full details.

---
*(Feel free to add a "Contact" or "Acknowledgements" section if desired.)*
