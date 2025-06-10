from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.util import ClassNotFound

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document, theme_config=None):
        super().__init__(document)
        self.formats = {}
        self.theme_config = theme_config if theme_config else {}
        self.lexer = None

        self._setup_formats()

    def _setup_formats(self):
        # Default formats if not provided by theme
        default_colors = {
            "keyword": "#c678dd",
            "string": "#98c379",
            "number": "#d19a66",
            "comment": "#5c6370",
            "function": "#61afef",
            "class": "#e5c07b",
            "operator": "#56b6c2",
            "default": "#abb2bf"
        }

        for token_type, default_color in default_colors.items():
            fmt = QTextCharFormat()
            color = self.theme_config.get("syntax", {}).get(token_type, default_color)
            fmt.setForeground(QColor(color))
            if token_type in ["keyword", "function", "class"]:
                fmt.setFontWeight(QFont.Bold)
            self.formats[token_type] = fmt

    def highlightBlock(self, text):
        if not self.lexer:
            return

        try:
            offset = 0
            for token, content in self.lexer.get_tokens_unprocessed(text):
                token_type = str(token).split('.')[-1].lower() # e.g., 'Token.Keyword' -> 'keyword'
                
                # Map Pygments token types to our defined formats
                fmt = self.formats.get(token_type, self.formats.get("default"))
                
                # Apply format
                self.setFormat(offset, len(content), fmt)
                offset += len(content)
        except Exception as e:
            # Fallback to default if Pygments fails for some reason
            print(f"Pygments highlighting error: {e}")
            self.setFormat(0, len(text), self.formats.get("default"))

    def set_lexer_for_filename(self, filename, text_content):
        try:
            self.lexer = guess_lexer_for_filename(filename, text_content)
        except ClassNotFound:
            self.lexer = None # Fallback to no highlighting
        self.rehighlight()