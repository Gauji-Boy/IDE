# app_config.py

RUNNER_CONFIG = {
    "Python": {
        "cmd": ["python", "-u", "{file}"],
        "ext": ".py"
    },
    "JavaScript": {
        "cmd": ["node", "{file}"],
        "ext": ".js"
    },
    "Ruby": {
        "cmd": ["ruby", "{file}"],
        "ext": ".rb"
    },
    "Java": {
        "cmd": ["javac", "{file}", "&&", "java", "-cp", "{dir}", "{class_name}"], # Added -cp {dir} for class path
        "ext": ".java",
        "class_based": True # Indicates class_name placeholder is important
    },
    "C++": {
        # For C++, using shlex.split for the command string might be needed if passed to shell
        # This example assumes direct execution or simple shell wrapper if needed.
        # Output file placeholder is {output_file_no_ext} to avoid confusion with {file}
        "cmd": ["g++", "{file}", "-o", "{output_file_no_ext}", "&&", "./{output_file_no_ext}"],
        "ext": ".cpp",
        "output_based": True # Indicates output_file_no_ext placeholder is important
    }
}

# Notes on complex configurations:
# C++:
# - The command `"{output_file_no_ext}"` for execution might need `./` on Unix-like systems.
# - Windows might require just `"{output_file_no_ext}.exe"`.
# - Error handling for compilation vs. runtime is separate.
# Java:
# - `javac` compiles to `.class` files. `java` runs the class.
# - `"{class_name}"` should be the main class name, derived from the filename.
# - `"-cp", "{dir}"` tells java where to find the class file (directory of the temp file).
# These will require careful handling in the QProcess execution logic in main_window.py,
# potentially splitting commands or using shell execution for `&&`.
