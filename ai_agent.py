import google.generativeai as genai
import google.generativeai.types as glm # Import the types module
import os
import json
from PySide6.QtCore import QObject, Signal, Slot, QThread
from ai_tools import AITools # Import the tools

# Ensure GEMINI_API_KEY is set as an environment variable
# For example: export GEMINI_API_KEY="YOUR_API_KEY"
# Or in a .env file loaded by a library like python-dotenv
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class GeminiAgent(QObject):
    """
    Manages interaction with the Google Gemini API, including conversation history
    and tool execution.
    """
    response_received = Signal(str)
    tool_code_edit_requested = Signal(str) # Signal to forward apply_code_edit requests

    def __init__(self, main_window_instance):
        super().__init__()
        self.tools = AITools(main_window_instance) # Initialize tools first
        
        # Define tools as FunctionDeclaration objects
        # Define tools as FunctionDeclaration objects
        tool_definitions = [
            glm.FunctionDeclaration(
                name='get_current_code',
                description='Returns the full text content of the currently active CodeEditor.',
                parameters=glm.Schema(type=glm.Type.OBJECT)
            ),
            glm.FunctionDeclaration(
                name='read_file',
                description='Reads and returns the content of a specified file from the file system.',
                parameters=glm.Schema(
                    type=glm.Type.OBJECT,
                    properties={
                        'file_path': glm.Schema(type=glm.Type.STRING)
                    },
                    required=['file_path']
                )
            ),
            glm.FunctionDeclaration(
                name='write_file',
                description='Writes content to a specified file. If the file exists, it will be overwritten.',
                parameters=glm.Schema(
                    type=glm.Type.OBJECT,
                    properties={
                        'file_path': glm.Schema(type=glm.Type.STRING),
                        'content': glm.Schema(type=glm.Type.STRING)
                    },
                    required=['file_path', 'content']
                )
            ),
            glm.FunctionDeclaration(
                name='list_directory',
                description='Lists the files and folders in a given directory.',
                parameters=glm.Schema(
                    type=glm.Type.OBJECT,
                    properties={
                        'path': glm.Schema(type=glm.Type.STRING)
                    }
                )
            ),
            glm.FunctionDeclaration(
                name='apply_code_edit',
                description='Applies the provided new_code to the currently active CodeEditor. This tool does not return data to the AI; it emits a signal to the MainWindow.',
                parameters=glm.Schema(
                    type=glm.Type.OBJECT,
                    properties={
                        'new_code': glm.Schema(type=glm.Type.STRING)
                    },
                    required=['new_code']
                )
            )
        ]

        self.model = genai.GenerativeModel(
            'gemini-pro',
            tools=tool_definitions # Pass the defined tools here
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)
        self.tools = AITools(main_window_instance)
        
        # Connect the tool's signal to this agent's signal
        self.tools.apply_code_edit_signal.connect(self.tool_code_edit_requested)
        
        # Connect AITools result signals to agent's slots
        self.tools.current_code_result.connect(self._handle_tool_result)
        self.tools.read_file_result.connect(self._handle_tool_result)
        self.tools.write_file_result.connect(self._handle_tool_result)
        self.tools.list_directory_result.connect(self._handle_tool_result)

        self.system_prompt = """
        You are an expert Python programmer and a helpful AI coding assistant integrated into an IDE.
        Your goal is to assist the user with coding tasks, refactoring, debugging, and file management.
        You have access to a set of tools to interact with the IDE's environment.

        Here's how you should operate:
        1.  **Understand the Request:** Carefully read the user's request.
        2.  **Plan:** Determine which tools are necessary to fulfill the request.
            - Use `get_current_code()` to see the code in the active editor.
            - Use `read_file(file_path)` to inspect other files.
            - Use `list_directory(path)` to explore the file system.
            - Use `write_file(file_path, content)` to create or modify files.
            - Use `apply_code_edit(new_code)` to directly update the active code editor.
        3.  **Execute Tools:** Call the appropriate tools. If a tool requires arguments, provide them.
        4.  **Analyze Results:** Interpret the output from the tools.
        5.  **Iterate:** If the task requires multiple steps (e.g., read file, analyze, then write file), continue using tools and analyzing results.
        6.  **Respond to User:** Once you have completed the task or gathered enough information, provide a clear and concise answer or confirmation to the user.
            - When applying code edits, explicitly state that you are doing so.
            - If you write to a file, confirm the action.
            - If you need more information, ask clarifying questions.

        **Important Considerations:**
        - Always prioritize using the provided tools to gather information or make changes.
        - When asked to modify code, use `get_current_code()` first to see the existing code, then provide the *complete* modified code to `apply_code_edit()`. Do not provide partial diffs.
        - Be precise with file paths when using `read_file`, `write_file`, and `list_directory`. Assume paths are relative to the project root unless specified otherwise by the user.
        - If a tool call fails, report the error to the user and suggest a next step.
        - Be concise in your responses.
        """
        # Initialize chat with the system prompt
        self.chat.send_message(self.system_prompt)

    @Slot(str)
    def send_message_to_gemini(self, user_message):
        """
        Sends a user message to Gemini and handles the response, including tool calls.
        """
        if not os.getenv("GEMINI_API_KEY"):
            self.response_received.emit("Error: GEMINI_API_KEY environment variable not set. Please set it to use the AI assistant.")
            return

        try:
            # Send the user message
            response = self.chat.send_message(user_message)

            # Process the response, which might include tool calls
            self._process_gemini_response(response)

        except Exception as e:
            self.response_received.emit(f"Error communicating with Gemini: {e}")

    def _process_gemini_response(self, response):
        """
        Processes Gemini's response, executing tool calls if requested.
        """
        try:
            # Check if the response contains tool function calls
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.function_call:
                                tool_call = part.function_call
                                tool_name = tool_call.name
                                tool_args = {k: v for k, v in tool_call.args.items()} # Convert to dict

                                print(f"AI Agent: Gemini requested tool: {tool_name} with args: {tool_args}")

                                # Execute the tool based on its name
                                if hasattr(self.tools, tool_name):
                                    tool_function = getattr(self.tools, tool_name)
                                    # For tools that return results asynchronously via signals,
                                    # we don't send the result back to Gemini immediately here.
                                    # Instead, the _handle_tool_result slot will do it.
                                    if tool_name in ['get_current_code', 'read_file', 'write_file', 'list_directory']:
                                        tool_function(**tool_args) # Just call the function, result comes via signal
                                    else:
                                        tool_result = tool_function(**tool_args)
                                        print(f"AI Agent: Tool '{tool_name}' executed, result: {tool_result}")
                                        # Send tool result back to Gemini for synchronous tools
                                        tool_response = self.chat.send_message(
                                            glm.ToolCode(
                                                name=tool_name,
                                                result=tool_result
                                            )
                                        )
                                        self._process_gemini_response(tool_response) # Process new response
                                else:
                                    error_msg = f"AI Agent: Gemini requested unknown tool: {tool_name}"
                                    print(error_msg)
                                    self.response_received.emit(error_msg)
                            elif part.text:
                                # If it's a text response, emit it to the UI
                                self.response_received.emit(part.text)
            else:
                # If no candidates or no content, it might be an empty response or an error
                self.response_received.emit("AI Agent: Received an empty or unhandled response from Gemini.")

        except Exception as e:
            self.response_received.emit(f"AI Agent: Error processing Gemini response: {e}")

    @Slot(str)
    @Slot(str, str)
    @Slot(str, bool, str)
    @Slot(str, str)
    def _handle_tool_result(self, *args):
        """
        Receives results from AITools signals and sends them back to Gemini.
        The arguments depend on the signal that emitted the result.
        """
        if len(args) == 1: # get_current_code_result
            tool_name = 'get_current_code'
            result = args[0]
        elif len(args) == 2: # read_file_result or list_directory_result
            # Differentiate based on expected content type or context
            # For simplicity, assuming the first arg is path, second is content/error
            if isinstance(args[1], str) and (args[1].startswith("Error:") or args[0].endswith(".json")): # Heuristic for list_directory vs read_file
                tool_name = 'list_directory'
                result = args[1] # The JSON string or error message
            else:
                tool_name = 'read_file'
                result = args[1] # The file content or error message
        elif len(args) == 3: # write_file_result
            tool_name = 'write_file'
            file_path, success, message = args
            result = f"File '{file_path}' write {'succeeded' if success else 'failed'}: {message}"
        else:
            print(f"AI Agent: Unhandled tool result format: {args}")
            return

        print(f"AI Agent: Received tool result for {tool_name}: {result[:100]}...")
        
        try:
            tool_response = self.chat.send_message(
                glm.ToolCode(
                    name=tool_name,
                    result=result
                )
            )
            self._process_gemini_response(tool_response)
        except Exception as e:
            self.response_received.emit(f"AI Agent: Error sending tool result to Gemini: {e}")

class GeminiAgentWorker(QThread):
    """
    A QThread worker to run GeminiAgent operations in a separate thread
    to keep the UI responsive.
    """
    response_received = Signal(str)
    tool_code_edit_requested = Signal(str)

    def __init__(self, agent, user_message):
        super().__init__()
        self.agent = agent
        self.user_message = user_message
        
        # Forward the agent's signals through the worker
        self.agent.response_received.connect(self.response_received)
        self.agent.tool_code_edit_requested.connect(self.tool_code_edit_requested)

    def run(self):
        self.agent.send_message_to_gemini(self.user_message)