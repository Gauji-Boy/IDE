# Ensure GEMINI_API_KEY is set as an environment variable.
# For example, in your shell:
# export GEMINI_API_KEY='your_actual_api_key'
# The application will not work without this key.
import os
import google.generativeai as genai
import ai_tools # To access tool functions

# Ensure GEMINI_API_KEY is set as an environment variable
# e.g., export GEMINI_API_KEY='your_api_key_here'
# The user of this application is responsible for setting this up.

class GeminiAgent:
    def __init__(self, main_window, apply_code_signal_emitter):
        self.main_window = main_window  # Reference to MainWindow for context-aware tools
        self.apply_code_signal_emitter = apply_code_signal_emitter # Signal emitter for apply_code_edit
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not found.")

        genai.configure(api_key=self.api_key)

        # Define the tools for Gemini, matching functions in ai_tools.py
        self.gemini_tools = [
            {
                "name": "get_current_code",
                "description": "Returns the full text content of the currently active code editor.",
                "parameters": {} # No parameters for this tool
            },
            {
                "name": "read_file",
                "description": "Reads and returns the content of a specified file from the file system.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "The path to the file to read."}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "write_file",
                "description": "Writes content to a specified file. Overwrites the file if it exists.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "The path to the file to write."},
                        "content": {"type": "string", "description": "The content to write to the file."}
                    },
                    "required": ["file_path", "content"]
                }
            },
            {
                "name": "list_directory",
                "description": "Lists the files and folders in a given directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The path of the directory to list."}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "apply_code_edit",
                "description": "Replaces the entire content of the current code editor with the provided new code. This tool is used to apply changes directly to the editor.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_code": {"type": "string", "description": "The new code to apply to the editor."}
                    },
                    "required": ["new_code"]
                }
            }
        ]

        # System prompt defining the AI's role and capabilities
        self.system_prompt = """
You are a helpful AI coding assistant integrated into a Python IDE.
Your goal is to assist the user with their coding tasks.
You have the following tools available to interact with the IDE and file system:
- get_current_code(): Gets the code from the current editor.
- read_file(file_path): Reads a specified file.
- write_file(file_path, content): Writes content to a file.
- list_directory(path): Lists files in a directory.
- apply_code_edit(new_code): Applies new code to the current editor.

When a user asks for a change that involves modifying the code in the editor,
first get the current code, then propose the changes, and if the user agrees or if you are confident,
use apply_code_edit to make the changes.
If you need to read a file, use read_file. If you need to write a file, use write_file.
If you need to see what files are in a directory, use list_directory.

Always think step by step. When a tool is called, I will get the result back.
If the tool execution is successful, I will see "Tool execution successful".
If the tool is `apply_code_edit`, it doesn't return data to you, but the user will see the change in their editor.
You can then inform the user that the code has been applied.

If you are asked to refactor or modify code, you should:
1. Use `get_current_code` to get the existing code.
2. Analyze the code and formulate the changes.
3. Respond to the user with the proposed changes (e.g., showing the diff or the new code block).
4. THEN, use the `apply_code_edit` tool with the complete new version of the code if you are to apply it.
   Do not try to apply partial edits or diffs. Provide the full, complete code content for the editor.
"""

        self.model = genai.GenerativeModel(
            model_name='gemini-1.0-pro', # Or your preferred model
            # tools=self.gemini_tools, # Tool declaration for Gemini
            system_instruction=self.system_prompt
        )
        self.conversation_history = []

    def send_message(self, user_message):
        self.conversation_history.append({'role': 'user', 'parts': [{'text': user_message}]})

        # Start a chat session with the existing history
        chat = self.model.start_chat(history=self.conversation_history)

        # Send the message to Gemini, including the tool definitions for this turn
        # We send tools every time as per current best practices for some Gemini versions/setups
        response = chat.send_message(user_message, tools=self.gemini_tools)

        ai_response_parts = []

        while True:
            latest_response_part = response.candidates[0].content.parts[0]
            if hasattr(latest_response_part, 'function_call'):
                function_call = latest_response_part.function_call
                tool_name = function_call.name
                tool_args = dict(function_call.args)

                ai_response_parts.append(f"AI wants to call tool: {tool_name} with args: {tool_args}\n")

                tool_result_text = "Tool execution result not available or tool does not return text."

                try:
                    if tool_name == "get_current_code":
                        tool_output = ai_tools.get_current_code(self.main_window)
                    elif tool_name == "read_file":
                        tool_output = ai_tools.read_file(tool_args['file_path'])
                    elif tool_name == "write_file":
                        tool_output = ai_tools.write_file(tool_args['file_path'], tool_args['content'])
                    elif tool_name == "list_directory":
                        tool_output = ai_tools.list_directory(tool_args['path'])
                    elif tool_name == "apply_code_edit":
                        # This tool emits a signal, doesn't return data to AI directly
                        tool_output = ai_tools.apply_code_edit(tool_args['new_code'], self.apply_code_signal_emitter)
                    else:
                        tool_output = f"Unknown tool: {tool_name}"

                    tool_result_text = str(tool_output) if tool_output is not None else "Tool executed successfully but returned no textual output."
                    ai_response_parts.append(f"Tool {tool_name} executed. Output: {tool_result_text}\n")

                    # Send the tool's response back to Gemini
                    response = chat.send_message(
                        [genai.types.Part(function_response={
                            'name': tool_name,
                            'response': {'content': tool_result_text} # Or adjust based on actual tool output structure
                        })]
                    )
                except Exception as e:
                    error_message = f"Error executing tool {tool_name}: {e}"
                    ai_response_parts.append(error_message + "\n")
                    response = chat.send_message(
                         [genai.types.Part(function_response={
                            'name': tool_name,
                            'response': {'content': error_message}
                        })]
                    )
            else: # It's a text response from the AI
                text_response = latest_response_part.text
                ai_response_parts.append(text_response)
                break # Exit loop if it's a final text response

        final_ai_message = "".join(ai_response_parts)
        self.conversation_history.append({'role': 'model', 'parts': [{'text': final_ai_message}]})
        return final_ai_message

```
