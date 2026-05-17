import secrets
import string
import os
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox,
    QDialogButtonBox, QLabel
)
from utils import resource_path   # используем универсальный путь

# ---------- Загрузка списка популярных паролей (один раз при импорте) ----------
_COMMON_PASSWORDS = set()
def _load_common_passwords():
    global _COMMON_PASSWORDS
    filepath = resource_path("ui/common_passwords.txt")
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            _COMMON_PASSWORDS = set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        # Если файл не найден – множество останется пустым, проверка не сработает
        pass

_load_common_passwords()  # выполняем сразу

class EntryDialog(QDialog):
    def __init__(self, parent=None, entry_data=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить запись" if entry_data is None else "Изменить запись")
        self.resize(450, 400)

        self.title_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.username_edit = QLineEdit()

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.show_password_btn = QPushButton("Показать")
        self.show_password_btn.setCheckable(True)
        self.show_password_btn.toggled.connect(self._toggle_password_visibility)

        self.generate_btn = QPushButton("Сгенерировать")
        self.generate_btn.clicked.connect(self._generate_password)

        password_line = QHBoxLayout()
        password_line.addWidget(self.password_edit)
        password_line.addWidget(self.show_password_btn)
        password_line.addWidget(self.generate_btn)

        self.strength_label = QLabel("")
        self.strength_label.setVisible(False)
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("font-size: 11px; color: gray;")
        self.hint_label.setWordWrap(True)

        self.notes_edit = QTextEdit()

        form = QFormLayout()
        form.addRow("Название:", self.title_edit)
        form.addRow("URL:", self.url_edit)
        form.addRow("Логин:", self.username_edit)
        form.addRow("Пароль:", password_line)
        form.addRow("", self.strength_label)
        form.addRow("", self.hint_label)
        form.addRow("Заметки:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)

        self.password_edit.textChanged.connect(self._update_strength_indicator)

        if entry_data:
            self.title_edit.setText(entry_data.get("title", ""))
            self.url_edit.setText(entry_data.get("url", ""))
            self.username_edit.setText(entry_data.get("username", ""))
            self.password_edit.setText(entry_data.get("password", ""))
            self.notes_edit.setPlainText(entry_data.get("notes", ""))
            self._update_strength_indicator(entry_data.get("password", ""))

    def _toggle_password_visibility(self, checked):
        if checked:
            self.password_edit.setEchoMode(QLineEdit.Normal)
            self.show_password_btn.setText("Скрыть")
        else:
            self.password_edit.setEchoMode(QLineEdit.Password)
            self.show_password_btn.setText("Показать")

    def _generate_password(self):
        length = 16
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        self.password_edit.setText(password)
        self.password_edit.setEchoMode(QLineEdit.Normal)
        self.show_password_btn.setChecked(True)

    def _check_common_password(self, password: str) -> bool:
        return password in _COMMON_PASSWORDS

    def _evaluate_password(self, password: str):
        if not password:
            return ("", "", "")
        length = len(password)
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in password)

        score = 0
        if length >= 8: score += 1
        if length >= 12: score += 1
        if has_lower: score += 1
        if has_upper: score += 1
        if has_digit: score += 1
        if has_special: score += 1

        if length < 8:
            return ("weak", "red", "Слишком короткий пароль (минимум 8 символов).")
        if score <= 2:
            return ("weak", "red", "Добавьте заглавные буквы, цифры или спецсимволы.")
        if score <= 4:
            return ("medium", "orange", "Неплохо, но можно улучшить.")
        return ("strong", "green", "Отличный пароль!")

    def _update_strength_indicator(self, password: str):
        if self._check_common_password(password):
            self.strength_label.setVisible(True)
            self.strength_label.setText("Осторожно! Пароль слишком распространён!")
            self.strength_label.setStyleSheet("font-weight: bold; color: red;")
            self.hint_label.setText("Этот пароль найден в базах утечек. Выберите более уникальный.")
            return

        strength, color, hint = self._evaluate_password(password)
        if strength:
            self.strength_label.setVisible(True)
            self.strength_label.setText(f"Стойкость: {strength}")
            self.strength_label.setStyleSheet(f"font-weight: bold; color: {color};")
            self.hint_label.setText(hint)
        else:
            self.strength_label.setVisible(False)
            self.hint_label.setText("")

    def _validate_and_accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название не может быть пустым.")
            self.title_edit.setFocus()
            return
        self.accept()

    def get_data(self):
        return {
            "title": self.title_edit.text(),
            "url": self.url_edit.text(),
            "username": self.username_edit.text(),
            "password": self.password_edit.text(),
            "notes": self.notes_edit.toPlainText()
        }