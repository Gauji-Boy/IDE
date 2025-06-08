# python_highlighter.py

import sys
from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextDocument

class PythonHighlighter(QSyntaxHighlighter):
    """
    A syntax highlighter for Python code, using QRegularExpression.
    Highlights keywords, comments, strings, numbers, and definitions.
    """
    # Constants for block states (used for multi-line strings)
    NORMAL_STATE = 0
    TRIPLE_DOUBLE_QUOTED_STRING_STATE = 1
    TRIPLE_SINGLE_QUOTED_STRING_STATE = 2

    def __init__(self, parent=None): # parent is usually a QTextDocument
        super().__init__(parent)

        self.highlighting_rules = []

        # Keyword format
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(Qt.blue))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
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

        # Class Definition format
        class_name_format = QTextCharFormat()
        class_name_format.setForeground(QColor(Qt.darkMagenta))
        class_name_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"),
            'format': class_name_format,
            'group': 1  # Highlight only the class name
        })

        # Function Definition format
        func_name_format = QTextCharFormat()
        func_name_format.setForeground(QColor(Qt.darkCyan))
        func_name_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)"),
            'format': func_name_format,
            'group': 1  # Highlight only the function name
        })

        # Decorators
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor(Qt.gray))
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_\.]*"),
            'format': decorator_format,
            'group': 0
        })

        # Comments (single-line)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(Qt.darkGreen))
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"#[^\n]*"),
            'format': comment_format,
            'group': 0
        })

        # Numbers (integers, floats, hex, octal, binary)
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(Qt.darkRed))
        # Pattern covers: integers (123), floats (3.14, .5, 10.), scientific (1.2e3),
        # hex (0x...), binary (0b...), octal (0o...)
        # Using raw string for regex to avoid issues with backslashes
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"\b0[xX][0-9a-fA-F_]+\b|\b0[bB][01_]+\b|\b0[oO][0-7_]+\b|(?:\b\d+[eE][-+]?\d+\b)|(?:\b\d+\.\d*(?:[eE][-+]?\d+)?\b)|(?:\b\.\d+(?:[eE][-+]?\d+)?\b)|(?:\b\d+\b)"),
            'format': number_format,
            'group': 0
        })

        # Strings (single and double quoted, not multi-line here)
        self.string_format = QTextCharFormat() # Store for multi-line use too
        self.string_format.setForeground(QColor(Qt.magenta))
        # Single-quoted strings (handles basic escapes like \')
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"'(?:[^'\\]|\\.)*'"),
            'format': self.string_format,
            'group': 0
        })
        # Double-quoted strings (handles basic escapes like \")
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r'"(?:[^"\\]|\\.)*"'),
            'format': self.string_format,
            'group': 0
        })

        # Multi-line string delimiters
        self.tri_double_start_expression = QRegularExpression(r'"""')
        self.tri_double_end_expression = QRegularExpression(r'"""')
        self.tri_single_start_expression = QRegularExpression(r"'''")
        self.tri_single_end_expression = QRegularExpression(r"'''")


    def highlightBlock(self, text: str):
        """
        Highlights a single block of text.
        This method is called by QSyntaxHighlighter for each block.
        """
        # Apply single-line rules first
        for rule in self.highlighting_rules:
            iterator = rule['pattern'].globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start_index = match.capturedStart(rule['group'])
                length = match.capturedLength(rule['group'])
                if start_index >= 0 and length > 0:
                    self.setFormat(start_index, length, rule['format'])

        self.setCurrentBlockState(self.NORMAL_STATE) # Default state for next block

        # Multi-line string handling (Triple Double Quotes)
        start_offset = 0
        if self.previousBlockState() == self.TRIPLE_DOUBLE_QUOTED_STRING_STATE:
            start_offset = 0 # Start searching for end from beginning of block
        else:
            # Not continuing, so search for start of a new triple-double string
            match = self.tri_double_start_expression.match(text)
            if match.hasMatch():
                start_offset = match.capturedStart()
            else:
                start_offset = -1 # No start found

        while start_offset >= 0:
            if self.previousBlockState() != self.TRIPLE_DOUBLE_QUOTED_STRING_STATE and \
               self.tri_double_start_expression.match(text, start_offset).hasMatch():
                # This is a new start
                match_start = self.tri_double_start_expression.match(text, start_offset)
                start_index = match_start.capturedStart()

                # Search for the end from after the start delimiter
                match_end = self.tri_double_end_expression.match(text, start_index + match_start.capturedLength())
                if match_end.hasMatch():
                    # Ends on the same line
                    end_index = match_end.capturedEnd()
                    self.setFormat(start_index, end_index - start_index, self.string_format)
                    self.setCurrentBlockState(self.NORMAL_STATE)
                    start_offset = self.tri_double_start_expression.match(text, end_index).capturedStart() # Look for next
                else:
                    # Extends to next line
                    self.setFormat(start_index, len(text) - start_index, self.string_format)
                    self.setCurrentBlockState(self.TRIPLE_DOUBLE_QUOTED_STRING_STATE)
                    return # Block consumed
            elif self.previousBlockState() == self.TRIPLE_DOUBLE_QUOTED_STRING_STATE:
                # Block is continuation of a triple-double string
                match_end = self.tri_double_end_expression.match(text, start_offset) # Search for end from start_offset
                if match_end.hasMatch():
                    # Ends in this block
                    end_index = match_end.capturedEnd()
                    self.setFormat(0, end_index, self.string_format) # Format from start of block to end delimiter
                    self.setCurrentBlockState(self.NORMAL_STATE)
                    start_offset = self.tri_double_start_expression.match(text, end_index).capturedStart() # Look for next
                else:
                    # Continues further
                    self.setFormat(0, len(text), self.string_format) # Format whole block
                    self.setCurrentBlockState(self.TRIPLE_DOUBLE_QUOTED_STRING_STATE)
                    return # Block consumed
            else: # No match or already handled
                break


        # Multi-line string handling (Triple Single Quotes)
        # Only process if not currently in a triple-double state
        if self.currentBlockState() != self.TRIPLE_DOUBLE_QUOTED_STRING_STATE:
            start_offset_single = 0
            if self.previousBlockState() == self.TRIPLE_SINGLE_QUOTED_STRING_STATE:
                start_offset_single = 0
            else:
                match = self.tri_single_start_expression.match(text)
                if match.hasMatch():
                    start_offset_single = match.capturedStart()
                else:
                    start_offset_single = -1

            while start_offset_single >= 0:
                if self.previousBlockState() != self.TRIPLE_SINGLE_QUOTED_STRING_STATE and \
                   self.tri_single_start_expression.match(text, start_offset_single).hasMatch():
                    match_start = self.tri_single_start_expression.match(text, start_offset_single)
                    start_index = match_start.capturedStart()
                    match_end = self.tri_single_end_expression.match(text, start_index + match_start.capturedLength())
                    if match_end.hasMatch():
                        end_index = match_end.capturedEnd()
                        self.setFormat(start_index, end_index - start_index, self.string_format)
                        self.setCurrentBlockState(self.NORMAL_STATE) # Should be normal if it ends
                        start_offset_single = self.tri_single_start_expression.match(text, end_index).capturedStart()
                    else:
                        self.setFormat(start_index, len(text) - start_index, self.string_format)
                        self.setCurrentBlockState(self.TRIPLE_SINGLE_QUOTED_STRING_STATE)
                        return
                elif self.previousBlockState() == self.TRIPLE_SINGLE_QUOTED_STRING_STATE:
                    match_end = self.tri_single_end_expression.match(text, start_offset_single)
                    if match_end.hasMatch():
                        end_index = match_end.capturedEnd()
                        self.setFormat(0, end_index, self.string_format)
                        self.setCurrentBlockState(self.NORMAL_STATE)
                        start_offset_single = self.tri_single_start_expression.match(text, end_index).capturedStart()
                    else:
                        self.setFormat(0, len(text), self.string_format)
                        self.setCurrentBlockState(self.TRIPLE_SINGLE_QUOTED_STRING_STATE)
                        return
                else:
                    break
# Note: The process_multiline_string method is not included here; its logic is integrated
# (in a simplified form) into highlightBlock for this specific implementation.
# A more robust highlighter might use a helper like in previous full versions.
# For a production-quality highlighter, the multi-line logic would need more rigorous testing
# and refinement, especially for edge cases and interactions between different multi-line types.
# This version provides a foundational implementation as per the prompt.
