from PySide6.QtWidgets import QTreeView, QFileSystemModel, QMenu, QInputDialog, QMessageBox
from PySide6.QtCore import QDir, Signal, Slot, QModelIndex, QPoint
from PySide6.QtGui import QAction
import os
import shutil

class FileExplorer(QTreeView):
    file_opened = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QFileSystemModel()
        self.setModel(self.model)

        # Hide unnecessary columns
        self.setHeaderHidden(True)
        self.hideColumn(1) # Size
        self.hideColumn(2) # Type
        self.hideColumn(3) # Date Modified

        self.setAnimated(True)
        self.setIndentation(20)
        self.setSortingEnabled(True)

        self.set_root_path(QDir.currentPath()) # Set initial path to current directory
        self.doubleClicked.connect(self.on_double_clicked)

    def set_root_path(self, path):
        self.model.setRootPath(path)
        self.setRootIndex(self.model.index(path))

    @Slot(QModelIndex)
    def on_double_clicked(self, index):
        if not self.model.isDir(index):
            file_path = self.model.filePath(index)
            self.file_opened.emit(file_path)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        add_file_action = QAction("Add New File", self)
        add_file_action.triggered.connect(lambda: self.add_new_file(event.pos()))
        menu.addAction(add_file_action)
        menu.exec(self.mapToGlobal(event.pos()))

    @Slot(QPoint)
    def add_new_file(self, pos):
        index = self.indexAt(pos)
        if index.isValid():
            if self.model.isDir(index):
                target_dir = self.model.filePath(index)
            else:
                target_dir = self.model.filePath(index.parent())
        else:
            # If no item is clicked, use the current root path
            target_dir = self.model.rootPath()

        file_name, ok = QInputDialog.getText(self, "New File", "Enter new file name:")
        if ok and file_name:
            new_file_path = os.path.join(target_dir, file_name)
            try:
                with open(new_file_path, 'w') as f:
                    f.write("") # Create an empty file
                # Get the index of the parent directory to refresh its view
                parent_dir_index = self.model.index(target_dir)
                # Collapse and then expand the parent directory to force a refresh of its contents
                self.collapse(parent_dir_index)
                self.expand(parent_dir_index)
                self.file_opened.emit(new_file_path) # Open the new file in editor
            except PermissionError:
                QMessageBox.critical(self, "Error", f"Permission denied to create file: '{new_file_path}'")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An unexpected error occurred while creating file: {e}")