# config.py

# RUNNER_CONFIG defines configurations for running code in different languages.
# Each key is a language name (string) that will appear in the UI.
# The value is a dictionary with the following keys:
#   "cmd": A list of strings representing the command and its arguments.
#          Placeholders can be used:
#            "{file}" - Will be replaced with the path to the temporary source file.
#            "{dir}" - Will be replaced with the directory of the source file.
#            "{class_name}" - Will be replaced with the base name of the source file (without extension).
#            "{output_file_no_ext}" - Will be replaced with a path for output files (e.g., for compiled languages, without extension).
#          If "&&" is used in the command list, it will be executed via shell (sh -c or cmd /C).
#   "ext": A string for the temporary file's extension (e.g., ".py", ".cpp").
#   "output_based": (Optional) Boolean. If True, indicates that the runner produces an executable/output file
#                   that should then be run (e.g. C++, Java). The command should handle compilation, and
#                   the system might then try to run {output_file_no_ext} or {output_file_no_ext}.exe.
#                   If False or absent, the command in "cmd" is expected to directly execute the code.
#   "class_based": (Optional) Boolean. If True, it's a hint that the {class_name} placeholder is particularly
#                  important for this language's execution model (e.g., Java).

RUNNER_CONFIG = {
    "Python": {
        "cmd": ["python", "-u", "{file}"], # -u for unbuffered output
        "ext": ".py"
    },
    "JavaScript (Node.js)": { # Renamed for clarity
        "cmd": ["node", "{file}"],
        "ext": ".js"
    },
    "Ruby": {
        "cmd": ["ruby", "{file}"],
        "ext": ".rb"
    },
    "Java": {
        "cmd": ["javac", "{file}", "&&", "java", "-cp", "{dir}", "{class_name}"],
        "ext": ".java",
        "output_based": True, # Indicates compilation step producing an output to be run
        "class_based": True   # Indicates {class_name} is used for execution
    },
    "C++": {
        "cmd": ["g++", "{file}", "-o", "{output_file_no_ext}", "&&", "./{output_file_no_ext}"],
        "ext": ".cpp",
        "output_based": True  # Indicates compilation produces an executable
    }
}

# General Notes on Placeholders and Execution:
# - The main_window.py's _execute_current_code method is responsible for:
#   1. Replacing placeholders in the "cmd" list.
#   2. Handling commands with "&&" by executing them through a shell.
#   3. Managing temporary files for source code and potential executables.
# - For "output_based" languages, the "{output_file_no_ext}" placeholder is critical.
#   The command in "cmd" should compile the source to this output path.
#   The execution logic in main_window.py might then attempt to run this output
#   (e.g., by appending ".exe" on Windows if not already specified).
# - The "{class_name}" placeholder is typically the filename without its extension. This is
#   often used as the main class name in languages like Java.
# - Ensure that the commands specified are available in the system's PATH environment variable
#   where the application is run.
# - The "-u" flag for Python is recommended for unbuffered stdout/stderr, which helps in
#   getting real-time output in the application's output panels.
# - The "./" prefix for running the compiled C++ output is common on Unix-like systems to
#   execute a file in the current directory. Windows typically does not require this.
#   The main_window.py execution logic might need platform-specific adjustments for this if
#   the "./" is problematic on Windows or vice-versa.
#   Alternatively, the command itself could be made platform-dependent if necessary,
#   or the execution wrapper in main_window.py could adapt it.
#   For this version, "./{output_file_no_ext}" is used as a common practice for g++.
