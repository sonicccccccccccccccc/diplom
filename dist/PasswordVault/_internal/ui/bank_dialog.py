from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox,
    QDialogButtonBox
)

class BankDialog(QDialog):
    def __init__(self, parent=None, entry_data=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить банковский счёт" if entry_data is None else "Изменить банковский счёт")
        self.resize(450, 350)

        self.title_edit = QLineEdit()
        self.bank_name_edit = QLineEdit()
        self.account_holder_edit = QLineEdit()

        self.account_number_edit = QLineEdit()
        self.account_number_edit.setEchoMode(QLineEdit.Password)
        self.show_account_btn = QPushButton("Показать")
        self.show_account_btn.setCheckable(True)
        self.show_account_btn.toggled.connect(self._toggle_account_visibility)

        acc_layout = QHBoxLayout()
        acc_layout.addWidget(self.account_number_edit)
        acc_layout.addWidget(self.show_account_btn)

        self.bic_edit = QLineEdit()
        self.notes_edit = QTextEdit()

        form = QFormLayout()
        form.addRow("Название:", self.title_edit)
        form.addRow("Банк:", self.bank_name_edit)
        form.addRow("Владелец:", self.account_holder_edit)
        form.addRow("Номер счёта:", acc_layout)
        form.addRow("BIC/SWIFT:", self.bic_edit)
        form.addRow("Заметки:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)

        if entry_data:
            self.title_edit.setText(entry_data.get("title", ""))
            self.bank_name_edit.setText(entry_data.get("bank_name", ""))
            self.account_holder_edit.setText(entry_data.get("account_holder", ""))
            self.account_number_edit.setText(entry_data.get("account_number", ""))
            self.bic_edit.setText(entry_data.get("bic_swift", ""))
            self.notes_edit.setPlainText(entry_data.get("notes", ""))

    def _toggle_account_visibility(self, checked):
        if checked:
            self.account_number_edit.setEchoMode(QLineEdit.Normal)
            self.show_account_btn.setText("Скрыть")
        else:
            self.account_number_edit.setEchoMode(QLineEdit.Password)
            self.show_account_btn.setText("Показать")

    def _validate_and_accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название не может быть пустым.")
            self.title_edit.setFocus()
            return
        self.accept()

    def get_data(self):
        return {
            "title": self.title_edit.text(),
            "bank_name": self.bank_name_edit.text(),
            "account_holder": self.account_holder_edit.text(),
            "account_number": self.account_number_edit.text(),
            "bic_swift": self.bic_edit.text(),
            "notes": self.notes_edit.toPlainText()
        }