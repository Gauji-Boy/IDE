# custom_python_highlighter.py

import sys
from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextDocument

class PythonHighlighter(QSyntaxHighlighter):
    """
    A syntax highlighter for Python code, using QRegularExpression.
    Highlights keywords, comments, strings, numbers, and definitions.
    """
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
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"\b0[xX][0-9a-fA-F_]+\b|\b0[bB][01_]+\b|\b0[oO][0-7_]+\b|(?:\b\d+[eE][-+]?\d+\b)|(?:\b\d+\.\d*(?:[eE][-+]?\d+)?\b)|(?:\b\.\d+(?:[eE][-+]?\d+)?\b)|(?:\b\d+\b)"),
            'format': number_format,
            'group': 0
        })

        # Strings (this format is also used for multi-line strings)
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor(Qt.magenta))
        
        # Single-quoted strings
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r"'(?:[^'\\]|\\.)*'"), # Handles basic escapes
            'format': self.string_format,
            'group': 0
        })
        # Double-quoted strings
        self.highlighting_rules.append({
            'pattern': QRegularExpression(r'"(?:[^"\\]|\\.)*"'), # Handles basic escapes
            'format': self.string_format,
            'group': 0
        })

        # Multi-line string delimiters
        self.tri_double_start_expression = QRegularExpression(r'"""')
        self.tri_double_end_expression = QRegularExpression(r'"""')
        self.tri_single_start_expression = QRegularExpression(r"'''")
        self.tri_single_end_expression = QRegularExpression(r"'''")

    def highlightBlock(self, text: str):
        # Apply all single-line highlighting rules first
        for rule_info in self.highlighting_rules:
            pattern = rule_info['pattern']
            fmt = rule_info['format']
            capture_group_index = rule_info['group']

            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start_index = match.capturedStart(capture_group_index)
                length = match.capturedLength(capture_group_index)
                if start_index >= 0 and length > 0:
                     self.setFormat(start_index, length, fmt)

        # --- Multi-line string handling ---
        self.setCurrentBlockState(self.NORMAL_STATE) # Default state for the next block

        # Handle Triple Double Quotes
        # This simplified logic assumes that if a block starts in a multi-line state,
        # we search for the end. If not, we search for a new start.
        # It doesn't handle multiple multi-line strings starting/ending in the same block perfectly yet.
        
        # Check for Triple Double Quotes
        in_multiline_double = (self.previousBlockState() == self.TRIPLE_DOUBLE_QUOTED_STRING_STATE)
        start_offset = 0
        
        if in_multiline_double:
            end_match = self.tri_double_end_expression.match(text, start_offset)
            if end_match.hasMatch():
                end_index = end_match.capturedEnd()
                self.setFormat(0, end_index, self.string_format)
                # setCurrentBlockState(self.NORMAL_STATE) is already default
                start_offset = end_index # Continue scanning for other patterns after this one
            else:
                self.setFormat(0, len(text), self.string_format)
                self.setCurrentBlockState(self.TRIPLE_DOUBLE_QUOTED_STRING_STATE)
                return # Whole block is part of the multi-line string
        else: # Not continuing, search for a new start
            start_match = self.tri_double_start_expression.match(text, start_offset)
            if start_match.hasMatch():
                start_index = start_match.capturedStart()
                end_match = self.tri_double_end_expression.match(text, start_index + start_match.capturedLength())
                if end_match.hasMatch(): # Starts and ends on the same line
                    end_index = end_match.capturedEnd()
                    self.setFormat(start_index, end_index - start_index, self.string_format)
                    # setCurrentBlockState(self.NORMAL_STATE) is already default
                    start_offset = end_index
                else: # Starts but does not end on this line
                    self.setFormat(start_index, len(text) - start_index, self.string_format)
                    self.setCurrentBlockState(self.TRIPLE_DOUBLE_QUOTED_STRING_STATE)
                    return
            else: # No new start found for triple-double
                start_offset = len(text) # Don't scan further for this type


        # Check for Triple Single Quotes - only if not currently in a triple-double state
        if self.currentBlockState() == self.NORMAL_STATE:
            in_multiline_single = (self.previousBlockState() == self.TRIPLE_SINGLE_QUOTED_STRING_STATE)
            start_offset_single = 0 # Reset scan offset for this type if starting new search

            if in_multiline_single:
                end_match = self.tri_single_end_expression.match(text, start_offset_single)
                if end_match.hasMatch():
                    end_index = end_match.capturedEnd()
                    self.setFormat(0, end_index, self.string_format)
                    # self.setCurrentBlockState(self.NORMAL_STATE) is already default
                else:
                    self.setFormat(0, len(text), self.string_format)
                    self.setCurrentBlockState(self.TRIPLE_SINGLE_QUOTED_STRING_STATE)
                    return
            else: # Not continuing, search for a new start
                start_match = self.tri_single_start_expression.match(text, start_offset_single)
                if start_match.hasMatch():
                    start_index = start_match.capturedStart()
                    # Important: Search for end *after* the start delimiter
                    end_match = self.tri_single_end_expression.match(text, start_index + start_match.capturedLength())
                    if end_match.hasMatch(): # Starts and ends on the same line
                        end_index = end_match.capturedEnd()
                        self.setFormat(start_index, end_index - start_index, self.string_format)
                        # self.setCurrentBlockState(self.NORMAL_STATE) is already default
                    else: # Starts but does not end on this line
                        self.setFormat(start_index, len(text) - start_index, self.string_format)
                        self.setCurrentBlockState(self.TRIPLE_SINGLE_QUOTED_STRING_STATE)
                        return
                        
# Note: A more robust multi-line handling would typically iterate through the block,
# finding matches for start/end delimiters and switching states. The logic above is a common
# structure but might need refinement for all edge cases (e.g., multiple multi-line strings
# of different types or the same type starting/ending within a single block).
# For the purpose of this restoration, it mirrors a functional baseline.
