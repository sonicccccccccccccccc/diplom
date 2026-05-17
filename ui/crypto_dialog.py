from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox,
    QDialogButtonBox
)

class CryptoDialog(QDialog):
    def __init__(self, parent=None, entry_data=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить криптокошелёк" if entry_data is None else "Изменить криптокошелёк")
        self.resize(450, 350)

        self.title_edit = QLineEdit()
        self.currency_edit = QLineEdit()

        self.wallet_address_edit = QLineEdit()
        self.wallet_address_edit.setEchoMode(QLineEdit.Password)
        self.show_address_btn = QPushButton("Показать")
        self.show_address_btn.setCheckable(True)
        self.show_address_btn.toggled.connect(self._toggle_address_visibility)

        addr_layout = QHBoxLayout()
        addr_layout.addWidget(self.wallet_address_edit)
        addr_layout.addWidget(self.show_address_btn)

        self.seed_edit = QLineEdit()
        self.seed_edit.setEchoMode(QLineEdit.Password)
        self.show_seed_btn = QPushButton("Показать")
        self.show_seed_btn.setCheckable(True)
        self.show_seed_btn.toggled.connect(self._toggle_seed_visibility)

        seed_layout = QHBoxLayout()
        seed_layout.addWidget(self.seed_edit)
        seed_layout.addWidget(self.show_seed_btn)

        self.notes_edit = QTextEdit()

        form = QFormLayout()
        form.addRow("Название:", self.title_edit)
        form.addRow("Валюта:", self.currency_edit)
        form.addRow("Адрес кошелька:", addr_layout)
        form.addRow("Seed-фраза:", seed_layout)
        form.addRow("Заметки:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)

        if entry_data:
            self.title_edit.setText(entry_data.get("title", ""))
            self.currency_edit.setText(entry_data.get("currency", ""))
            self.wallet_address_edit.setText(entry_data.get("wallet_address", ""))
            self.seed_edit.setText(entry_data.get("seed_phrase", ""))
            self.notes_edit.setPlainText(entry_data.get("notes", ""))

    def _toggle_address_visibility(self, checked):
        if checked:
            self.wallet_address_edit.setEchoMode(QLineEdit.Normal)
            self.show_address_btn.setText("Скрыть")
        else:
            self.wallet_address_edit.setEchoMode(QLineEdit.Password)
            self.show_address_btn.setText("Показать")

    def _toggle_seed_visibility(self, checked):
        if checked:
            self.seed_edit.setEchoMode(QLineEdit.Normal)
            self.show_seed_btn.setText("Скрыть")
        else:
            self.seed_edit.setEchoMode(QLineEdit.Password)
            self.show_seed_btn.setText("Показать")

    def _validate_and_accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название не может быть пустым.")
            self.title_edit.setFocus()
            return
        self.accept()

    def get_data(self):
        return {
            "title": self.title_edit.text(),
            "currency": self.currency_edit.text(),
            "wallet_address": self.wallet_address_edit.text(),
            "seed_phrase": self.seed_edit.text(),
            "notes": self.notes_edit.toPlainText()
        }