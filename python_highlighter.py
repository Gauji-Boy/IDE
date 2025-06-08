# python_highlighter.py

import sys
from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextDocument

class PythonHighlighter(QSyntaxHighlighter):
    """
    A syntax highlighter for Python code, using QRegularExpression.
    Highlights keywords, comments, strings, numbers, and definitions.
    """
    def __init__(self, parent=None): # parent is usually a QTextDocument or derived
        super().__init__(parent)

        self.highlighting_rules = []

        # Keyword format
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(Qt.blue)) # Standard blue for keywords
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [ # Using \b for word boundaries
            r"\bFalse\b", r"\bNone\b", r"\bTrue\b", r"\band\b", r"\bas\b", r"\bassert\b",
            r"\basync\b", r"\bawait\b", r"\bbreak\b", r"\bclass\b", r"\bcontinue\b",
            r"\bdef\b", r"\bdel\b", r"\belif\b", r"\belse\b", r"\bexcept\b", r"\bfinally\b",
            r"\bfor\b", r"\bfrom\b", r"\bglobal\b", r"\bif\b", r"\bimport\b", r"\bin\b",
            r"\bis\b", r"\blambda\b", r"\bnonlocal\b", r"\bnot\b", r"\bor\b", r"\bpass\b",
            r"\braise\b", r"\breturn\b", r"\btry\b", r"\bwhile\b", r"\bwith\b", r"\byield\b"
        ]
        for word_pattern in keywords:
            pattern = QRegularExpression(word_pattern)
            self.highlighting_rules.append({'pattern': pattern, 'format': keyword_format, 'group': 0})

        # Class and function definition names
        class_name_format = QTextCharFormat()
        class_name_format.setForeground(QColor(Qt.darkMagenta)) # Distinct color for class names
        class_name_format.setFontWeight(QFont.Bold)
        # Pattern: "class" followed by one or more spaces, then the class name (captured)
        self.highlighting_rules.append({'pattern': QRegularExpression(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"), 'format': class_name_format, 'group': 1})

        func_name_format = QTextCharFormat()
        func_name_format.setForeground(QColor(Qt.darkCyan)) # Distinct color for function names
        func_name_format.setFontWeight(QFont.Bold)
        # Pattern: "def" followed by one or more spaces, then the function name (captured)
        self.highlighting_rules.append({'pattern': QRegularExpression(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)"), 'format': func_name_format, 'group': 1})
        
        # Decorators (e.g., @my_decorator)
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor(Qt.gray)) # Often a more muted color
        # Pattern: "@" followed by valid Python identifier characters (including dots for chained decorators)
        self.highlighting_rules.append({'pattern': QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_\.]*"), 'format': decorator_format, 'group': 0})

        # Single-line comments (#...)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(Qt.darkGreen)) # Common color for comments
        # Pattern: "#" followed by any characters except newline
        self.highlighting_rules.append({'pattern': QRegularExpression(r"#[^\n]*"), 'format': comment_format, 'group': 0})

        # Numbers (integers, floats, hex, binary)
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(Qt.darkRed)) # Common color for numbers
        # Pattern: Matches integers (with underscores), floats (with underscores, optional exponent), hex, and binary
        self.highlighting_rules.append({'pattern': QRegularExpression(r"\b[0-9_]+(?:\.[0-9_]*)?(?:[eE][-+]?[0-9_]+)?\b|\b0[xX][0-9a-fA-F_]+\b|\b0[bB][01_]+\b"), 'format': number_format, 'group': 0})

        # Strings (single and double quoted, handles basic escapes like \", \')
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(Qt.magenta)) # Common color for strings
        # Pattern for double-quoted strings: matches anything between " and " that isn't an unescaped "
        self.highlighting_rules.append({'pattern': QRegularExpression(r'"(?:[^"\\]|\\.)*"'), 'format': string_format, 'group': 0}) 
        # Pattern for single-quoted strings: matches anything between ' and ' that isn't an unescaped '
        self.highlighting_rules.append({'pattern': QRegularExpression(r"'(?:[^'\\]|\\.)*'"), 'format': string_format, 'group': 0})
        
        # Multi-line strings (triple quotes)
        self.tri_quote_format = QTextCharFormat()
        self.tri_quote_format.setForeground(QColor(Qt.magenta)) # Same as single-line strings
        # States for multi-line strings:
        # 0 = normal text
        # 1 = inside a triple double-quoted string (""")
        # 2 = inside a triple single-quoted string (''')
        self.tri_double_start_expression = QRegularExpression(r'"""')
        self.tri_double_end_expression = QRegularExpression(r'"""') # End is same as start
        self.tri_single_start_expression = QRegularExpression(r"'''")
        self.tri_single_end_expression = QRegularExpression(r"'''") # End is same as start

    def highlightBlock(self, text: str):
        """
        Highlights a single block of text (typically one line).
        This method is called by QSyntaxHighlighter for each block in the document.
        It applies single-line highlighting rules and manages state for multi-line strings.

        Args:
            text (str): The text content of the current block.
        """
        # Apply all single-line highlighting rules first
        for rule_info in self.highlighting_rules:
            pattern = rule_info['pattern']
            fmt = rule_info['format']
            capture_group_index = rule_info['group'] # Which captured group to format (0 for whole match)

            iterator = pattern.globalMatch(text) # Find all non-overlapping matches
            while iterator.hasNext():
                match = iterator.next()
                start_index = match.capturedStart(capture_group_index)
                length = match.capturedLength(capture_group_index)
                # Apply format only if the captured group is valid
                if start_index >= 0 and length > 0:
                     self.setFormat(start_index, length, fmt)

        # --- Multi-line string handling ---
        # Default state for the *next* block is 0 (normal text), unless a multi-line string continues.
        # The currentBlockState() is set by this method for the *current* block's processing of multi-lines.
        # The previousBlockState() is what the *previous* block set its state to.

        # Assume the block does not continue a multi-line string unless determined otherwise
        current_block_continues_multiline = False

        # Check for triple double-quoted strings
        # process_multiline_string returns True if this block is part of such a string
        if self.process_multiline_string(text, self.tri_double_start_expression, self.tri_double_end_expression, 1, self.tri_quote_format):
            current_block_continues_multiline = True
        
        # Check for triple single-quoted strings
        # Only process if not already handled by triple-double quotes OR if the double-quote string ended within this block.
        # currentBlockState() reflects the state *after* processing the previous multi-line type for *this* block.
        if not current_block_continues_multiline or self.currentBlockState() == 0:
             if self.process_multiline_string(text, self.tri_single_start_expression, self.tri_single_end_expression, 2, self.tri_quote_format):
                 current_block_continues_multiline = True # Not strictly needed to set this again here

        # If, after all checks, no multi-line string is active at the end of this block,
        # set the state for the next block to 0 (normal).
        # This is important if a multi-line string ended in this block.
        if not current_block_continues_multiline and self.currentBlockState() != 0 :
            # This case implies a multi-line string ended. If process_multiline_string correctly
            # set state to 0 on end, this might not be strictly necessary, but acts as a fallback.
            # However, process_multiline_string should handle setting state to 0 when a string ends.
            # If a string *continues*, process_multiline_string sets the target_state.
            # If no multiline string is active or started/ended, state remains as it was or becomes 0.
            pass # State should be correctly set by process_multiline_string


    def process_multiline_string(self, text: str, start_expression: QRegularExpression, 
                                 end_expression: QRegularExpression, target_state: int, 
                                 fmt: QTextCharFormat) -> bool:
        """
        Helper function to process a specific type of multi-line string (e.g., """...""" or '''...''').
        Manages the block state for multi-line comments that span across multiple blocks.

        Args:
            text (str): The current block's text.
            start_expression (QRegularExpression): Regex for the start delimiter (e.g., triple-double-quotes)
            end_expression (QRegularExpression): Regex for the end delimiter (e.g., triple-double-quotes).
            target_state (int): The block state to set if this multi-line string continues to the next block.
            fmt (QTextCharFormat): The format to apply to the multi-line string.

        Returns:
            bool: True if this block is determined to be part of this type of multi-line string
                  (either starting, continuing, or ending). False otherwise.
        """
        block_is_part_of_this_multiline_type = False
        current_scan_offset = 0 # Current position in the text block for scanning

        # Check if the previous block was already in this specific multi-line string state
        if self.previousBlockState() == target_state:
            # Previous block ended in this multi-line state, so this block starts in it.
            end_match = end_expression.match(text, 0) # Try to match end delimiter at start of block
            if end_match.hasMatch():
                # Multi-line string ends at the beginning of this block.
                end_offset = end_match.capturedLength()
                self.setFormat(0, end_offset, fmt)
                self.setCurrentBlockState(0) # String ended, next block is normal.
                current_scan_offset = end_offset # Continue scanning from after this string.
                block_is_part_of_this_multiline_type = True
            else:
                # Multi-line string continues through this entire block.
                self.setCurrentBlockState(target_state) # Mark this block as continuing the state.
                self.setFormat(0, len(text), fmt) # Format the whole block.
                return True # Entire block consumed by this multi-line string.
        
        # If not continuing from previous, or if a multi-line string ended and we need to check for new ones.
        # Loop to find all occurrences of this multi-line string type within the current block.
        while current_scan_offset < len(text):
            start_match = start_expression.match(text, current_scan_offset)
            if not start_match.hasMatch():
                break # No more start delimiters found in the remainder of the block.

            start_index = start_match.capturedStart()
            
            # Try to find the end delimiter *after* the start delimiter.
            # Add start_match.capturedLength() to search after the starting delimiter itself.
            end_match = end_expression.match(text, start_index + start_match.capturedLength())
            
            if end_match.hasMatch():
                # String starts and ends within the current block.
                length = end_match.capturedEnd() - start_index
                self.setFormat(start_index, length, fmt)
                self.setCurrentBlockState(0) # String ended, next block is normal (if no other rule applies).
                current_scan_offset = end_match.capturedEnd() # Continue scanning after this string.
                block_is_part_of_this_multiline_type = True
            else:
                # String starts in this block but does not end here (continues to next block).
                self.setCurrentBlockState(target_state) # Mark this block as starting/continuing the state.
                self.setFormat(start_index, len(text) - start_index, fmt) # Format from start to end of block.
                block_is_part_of_this_multiline_type = True
                break # Rest of the block is consumed by this multi-line string.
        
        return block_is_part_of_this_multiline_type


if __name__ == '__main__':
    # Example usage for testing the highlighter independently.
    # This creates a simple application with a QPlainTextEdit to showcase highlighting.
    from PySide6.QtWidgets import QApplication, QPlainTextEdit, QMainWindow

    app = QApplication(sys.argv)
    
    window = QMainWindow()
    editor = QPlainTextEdit()
    window.setCentralWidget(editor)
    
    # The QSyntaxHighlighter must be associated with a QTextDocument.
    highlighter = PythonHighlighter(editor.document()) 
    
    # Example Python code to test highlighting.
    editor.setPlainText("""# This is a comment
@my_decorator
class MyClass(object):
    """This is a class docstring.
    It can span multiple lines.""" # Ends here. Docstring is """..."""
    ''' And now a single quoted one.
    Still going... ''' # Also ends. This is '''...'''
    
    def __init__(self, value: int = 123_456_789_000): # constructor
        self.my_value = value # self is not a keyword by default
        s1 = "String with \\"esc\\"ape." # Double quoted string
        s2 = 'String with \\'esc\\'ape.' # Single quoted string
        hex_num = 0xDeadBeef
        bin_num = 0b0101_1010
        float_num = 3.14e-10
        
        # Test for multi-line strings starting after other code
        code_before = True; full_multi = """
        Line 1 of full multi
        Line 2 of full multi
        """ ; more_code = False # Multi-line string on same line as other code

        if None is False and True or not False: # Keywords
            pass
        return self.my_value

mc = MyClass() # Using the class
result = mc.my_value
print(f"Result: {result}")
""")
    window.setWindowTitle("Python Highlighter Test")
    window.setGeometry(100, 100, 600, 700) # x, y, width, height
    window.show()
    sys.exit(app.exec())
