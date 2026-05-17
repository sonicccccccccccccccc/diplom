import secrets
import string
import os
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit,
    QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox,
    QDialogButtonBox, QLabel
)
from PySide6.QtCore import Qt

class EntryDialog(QDialog):
    # Общий список популярных паролей (загружается один раз при старте)
    COMMON_PASSWORDS = None

    @classmethod
    def load_common_passwords(cls, filepath=None):
        """Загружает список популярных паролей из файла (по умолчанию — рядом с этим скриптом)."""
        if filepath is None:
            # Путь к файлу относительно папки, где лежит entry_dialog.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(current_dir, "common_passwords.txt")
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                cls.COMMON_PASSWORDS = set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            cls.COMMON_PASSWORDS = set()   # Если файла нет — просто пустой набор
            print(f"Предупреждение: файл {filepath} не найден. Проверка на распространённость отключена.")

    def __init__(self, parent=None, entry_data=None):
        super().__init__(parent)
        # Убедимся, что список загружен (вызовем загрузку, если ещё не)
        if EntryDialog.COMMON_PASSWORDS is None:
            EntryDialog.load_common_passwords()

        self.setWindowTitle("Добавить запись" if entry_data is None else "Изменить запись")
        self.resize(450, 400)

        # Поля ввода
        self.title_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.username_edit = QLineEdit()

        # Пароль и кнопки управления
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

        # Индикатор стойкости + предупреждение о распространённости
        self.strength_label = QLabel("")
        self.strength_label.setVisible(False)
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("font-size: 11px; color: gray;")
        self.hint_label.setWordWrap(True)

        # Заметки
        self.notes_edit = QTextEdit()

        # Собираем форму
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

        # Связываем изменение пароля с обновлением индикатора
        self.password_edit.textChanged.connect(self._update_strength_indicator)

        # Загрузка старых данных при редактировании
        if entry_data:
            self.title_edit.setText(entry_data.get("title", ""))
            self.url_edit.setText(entry_data.get("url", ""))
            self.username_edit.setText(entry_data.get("username", ""))
            self.password_edit.setText(entry_data.get("password", ""))
            self.notes_edit.setPlainText(entry_data.get("notes", ""))
            self._update_strength_indicator(entry_data.get("password", ""))

    # ---------- Вспомогательные методы ----------
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
        """Возвращает True, если пароль найден в списке распространённых."""
        if not password or not EntryDialog.COMMON_PASSWORDS:
            return False
        return password in EntryDialog.COMMON_PASSWORDS

    def _evaluate_password(self, password: str):
        if not password:
            return ("", "", "")
        length = len(password)
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in password)

        score = 0
        if length >= 8:
            score += 1
        if length >= 12:
            score += 1
        if has_lower:
            score += 1
        if has_upper:
            score += 1
        if has_digit:
            score += 1
        if has_special:
            score += 1

        if length < 8:
            return ("weak", "red", "Слишком короткий пароль (минимум 8 символов).")
        if score <= 2:
            return ("weak", "red", "Добавьте заглавные буквы, цифры или спецсимволы.")
        if score <= 4:
            return ("medium", "orange", "Неплохо, но можно улучшить (добавьте больше разных символов).")
        return ("strong", "green", "Отличный пароль!")

    def _update_strength_indicator(self, password: str):
        # Сначала проверяем распространённость
        if self._check_common_password(password):
            self.strength_label.setVisible(True)
            self.strength_label.setText("Осторожно! Пароль слишком распространён!")
            self.strength_label.setStyleSheet("font-weight: bold; color: red;")
            self.hint_label.setText("Этот пароль найден в базах утечек. Выберите более уникальный.")
            return

        # Обычная оценка стойкости
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
        title = self.title_edit.text().strip()
        if not title:
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