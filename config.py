# config.py

RUNNER_CONFIG = {
    "Python": {
        "run": ["python", "-u", "{file}"],
        "debug": ["python", "-m", "pdb", "{file}"]
    },
    "JavaScript": {
        "run": ["node", "{file}"],
        "debug": ["node", "--inspect-brk", "{file}"] # Placeholder for future implementation
    },
    "Java": {
        "run": ["javac", "{file}", "&&", "java", "{class_name}"],
        "debug": ["java", "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,address=5005", "{class_name}"] # Placeholder
    },
    "C++": {
        "run": ["g++", "{file}", "-o", "{output_file}", "&&", "{output_file}"],
        "debug": ["gdb", "{output_file}"] # Placeholder
    },
    "C": {
        "run": ["gcc", "{file}", "-o", "{output_file}", "&&", "{output_file}"],
        "debug": ["gdb", "{output_file}"] # Placeholder
    },
    "Ruby": {
        "run": ["ruby", "{file}"],
        "debug": ["ruby", "-r", "debug", "{file}"] # Placeholder
    }
}