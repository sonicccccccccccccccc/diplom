from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit,
    QVBoxLayout, QMessageBox, QDialogButtonBox
)

class CustomEntryDialog(QDialog):
    def __init__(self, parent=None, entry_data=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить запись" if entry_data is None else "Изменить запись")
        self.resize(450, 300)

        self.title_edit = QLineEdit()
        self.content_edit = QTextEdit()

        form = QFormLayout()
        form.addRow("Название:", self.title_edit)
        form.addRow("Содержимое:", self.content_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)

        if entry_data:
            self.title_edit.setText(entry_data.get("title", ""))
            self.content_edit.setPlainText(entry_data.get("content", ""))

    def _validate_and_accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название не может быть пустым.")
            self.title_edit.setFocus()
            return
        self.accept()

    def get_data(self):
        return {
            "title": self.title_edit.text(),
            "content": self.content_edit.toPlainText()
        }