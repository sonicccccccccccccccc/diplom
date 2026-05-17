import sys
import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStatusBar,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLabel, QLineEdit,
    QMessageBox, QFileDialog, QInputDialog, QToolBar,
    QListWidget, QSplitter, QDialog, QDialogButtonBox, QFormLayout,
    QMenu
)
from PySide6.QtGui import QAction, QPalette, QColor
from PySide6.QtCore import QTimer, Qt
from db.database import DatabaseManager
from ui.entry_dialog import EntryDialog
from ui.bank_dialog import BankDialog
from ui.crypto_dialog import CryptoDialog
from ui.note_dialog import NoteDialog
from ui.custom_dialog import CustomEntryDialog
from utils import resource_path

CATEGORY_NAMES = ["Пароли", "Банковские счета", "Криптокошельки", "Защищённые заметки"]
CATEGORY_TABLES = ["entries", "bank_accounts", "crypto_wallets", "secure_notes"]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PasswordVault - Менеджер паролей")
        self.resize(1000, 650)
        self.db_manager = None
        self.current_db_path = None
        self.current_category_index = 0
        self._user_category_id = None   # для пользовательских категорий

        self._apply_builtin_style()
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("База данных не открыта")

        self._create_toolbar()
        self._init_ui()
        self._set_controls_enabled(False)
        self._update_info_panel_for_category()

    def _apply_builtin_style(self):
        from PySide6.QtGui import QPalette, QColor
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ToolTipBase, QColor(30, 30, 30))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.instance().setPalette(palette)
        QApplication.instance().setStyle("Fusion")
        self.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: white; border: none;
                border-radius: 4px; padding: 6px 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:pressed { background-color: #004578; }
            QPushButton:disabled { background-color: #555; color: #aaa; }
            QLineEdit, QTextEdit {
                border: 1px solid #555; border-radius: 3px; padding: 3px;
                background-color: #1e1e1e; color: #ddd;
            }
            QHeaderView::section {
                background-color: #333; padding: 5px; border: none;
                border-bottom: 2px solid #0078d4; font-weight: bold; color: #ccc;
            }
            QTableWidget { gridline-color: #444; }
            QListWidget {
                background-color: #2b2b2b; color: #ddd; border-right: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #0078d4; color: white;
            }
        """)

    def _create_toolbar(self):
        toolbar = QToolBar("Основные действия")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_db_action = QAction("Новая база данных", self)
        new_db_action.triggered.connect(self._on_new_database)
        toolbar.addAction(new_db_action)

        open_db_action = QAction("Открыть базу данных", self)
        open_db_action.triggered.connect(self._on_open_database)
        toolbar.addAction(open_db_action)

        toolbar.addSeparator()

        backup_action = QAction("Резервная копия", self)
        backup_action.triggered.connect(self._on_backup_database)
        toolbar.addAction(backup_action)

        emergency_action = QAction("Аварийный комплект", self)
        emergency_action.triggered.connect(self._on_emergency_kit)
        toolbar.addAction(emergency_action)

        toolbar.addSeparator()

        about_action = QAction("Справка", self)
        about_action.triggered.connect(self._on_about)
        toolbar.addAction(about_action)

    def _init_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        # --- Левая панель: список категорий + кнопка "+" ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.category_list = QListWidget()
        self.category_list.addItems(CATEGORY_NAMES)
        self.category_list.setCurrentRow(0)
        self.category_list.currentRowChanged.connect(self._on_category_changed)
        # Подключаем контекстное меню (правая кнопка мыши)
        self.category_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.category_list.customContextMenuRequested.connect(self._on_category_context_menu)
        left_layout.addWidget(self.category_list)

        self.add_category_btn = QPushButton("＋ Добавить категорию")
        self.add_category_btn.setMaximumWidth(180)
        self.add_category_btn.clicked.connect(self._on_add_custom_category)
        self.add_category_btn.clicked.connect(self._on_add_custom_category)
        left_layout.addWidget(self.add_category_btn)

        left_widget.setMaximumWidth(180)
        splitter.addWidget(left_widget)

        # --- Правая часть: поиск, таблица, кнопки, инфопанель ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Поиск
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите текст для поиска...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_edit)
        right_layout.addLayout(search_layout)

        # Таблица записей
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        right_layout.addWidget(self.table)

        # Кнопки действий
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self._on_add_entry)
        btn_layout.addWidget(self.add_btn)
        self.edit_btn = QPushButton("Изменить")
        self.edit_btn.clicked.connect(self._on_edit_entry)
        btn_layout.addWidget(self.edit_btn)
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self._on_delete_entry)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)

        # Информационная панель
        self.info_layout = QHBoxLayout()
        self.info_label = QLabel("Выберите запись")
        self.info_layout.addWidget(self.info_label)
        self.sensitive_label = QLabel("")
        self.sensitive_label.setStyleSheet("font-weight: bold; color: green;")
        self.info_layout.addWidget(self.sensitive_label)
        self.info_layout.addStretch()

        self.copy_primary_btn = QPushButton("Копировать")
        self.copy_primary_btn.clicked.connect(self._on_copy_primary)
        self.info_layout.addWidget(self.copy_primary_btn)
        self.copy_secondary_btn = QPushButton("Копировать")
        self.copy_secondary_btn.clicked.connect(self._on_copy_secondary)
        self.info_layout.addWidget(self.copy_secondary_btn)
        self.show_sensitive_btn = QPushButton("Показать")
        self.show_sensitive_btn.setCheckable(True)
        self.show_sensitive_btn.toggled.connect(self._on_toggle_show_sensitive)
        self.info_layout.addWidget(self.show_sensitive_btn)

        # Кнопки для файлов
        self.attach_file_btn = QPushButton("📎 Прикрепить файл")
        self.attach_file_btn.clicked.connect(self._on_attach_file)
        self.info_layout.addWidget(self.attach_file_btn)
        self.download_file_btn = QPushButton("💾 Скачать файл")
        self.download_file_btn.clicked.connect(self._on_download_file)
        self.info_layout.addWidget(self.download_file_btn)
        self.attachment_name_label = QLabel("")
        self.attachment_name_label.setStyleSheet("color: #aaa; font-style: italic;")
        self.info_layout.addWidget(self.attachment_name_label)

        right_layout.addLayout(self.info_layout)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 4)
        self.setCentralWidget(splitter)

        # Изначально кнопки инфопанели неактивны
        self._set_info_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool):
        self.add_btn.setEnabled(enabled)
        self.edit_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

    def _set_info_controls_enabled(self, enabled: bool):
        self.copy_primary_btn.setEnabled(enabled)
        self.copy_secondary_btn.setEnabled(enabled)
        self.show_sensitive_btn.setEnabled(enabled)
        self.attach_file_btn.setEnabled(enabled)
        self.download_file_btn.setEnabled(enabled)

    def _on_category_changed(self, index):
        if not self.db_manager:
            return
        if index < len(CATEGORY_NAMES):
            self.current_category_index = index
            self._user_category_id = None
        else:
            # Пользовательская категория
            self.current_category_index = -1
            cat_name = self.category_list.item(index).text()
            cats = self.db_manager.get_all_custom_categories()
            self._user_category_id = None
            for cat in cats:
                if cat["name"] == cat_name:
                    self._user_category_id = cat["id"]
                    break
        self._update_table_headers()
        self._update_info_panel_for_category()
        self._refresh_table()
        self._clear_selection()

    def _update_table_headers(self):
        if self.current_category_index == -1:
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["Название", "Содержимое"])
            return
        headers = {
            0: ["Название", "Логин", "URL"],
            1: ["Название", "Банк", "Владелец"],
            2: ["Название", "Валюта", "Адрес кошелька"],
            3: ["Название", "Содержимое"]
        }
        h = headers[self.current_category_index]
        self.table.setColumnCount(len(h))
        self.table.setHorizontalHeaderLabels(h)

    def _update_info_panel_for_category(self):
        if self.current_category_index == -1:
            self.copy_primary_btn.setText("Копировать содержимое")
            self.copy_secondary_btn.setVisible(False)
            self.show_sensitive_btn.setVisible(False)
            self.sensitive_label.setVisible(False)
            return
        if self.current_category_index == 0:
            self.copy_primary_btn.setText("Копировать логин")
            self.copy_secondary_btn.setText("Копировать пароль")
            self.show_sensitive_btn.setText("Показать пароль")
            self.sensitive_label.setVisible(True)
        elif self.current_category_index == 1:
            self.copy_primary_btn.setText("Копировать номер счёта")
            self.copy_secondary_btn.setText("Копировать BIC")
            self.show_sensitive_btn.setText("Показать номер счёта")
            self.sensitive_label.setVisible(True)
        elif self.current_category_index == 2:
            self.copy_primary_btn.setText("Копировать адрес")
            self.copy_secondary_btn.setText("Копировать seed")
            self.show_sensitive_btn.setText("Показать адрес")
            self.sensitive_label.setVisible(True)
        elif self.current_category_index == 3:
            self.copy_primary_btn.setText("Копировать содержимое")
            self.copy_secondary_btn.setVisible(False)
            self.show_sensitive_btn.setVisible(False)
            self.sensitive_label.setVisible(False)
        self.copy_secondary_btn.setVisible(self.current_category_index != 3)

    def _clear_selection(self):
        self.table.clearSelection()
        self.info_label.setText("Выберите запись")
        self.sensitive_label.setText("")
        self._set_info_controls_enabled(False)

    def _on_table_selection_changed(self):
        selected = self.table.currentRow()
        if selected < 0 or not self.db_manager:
            self._clear_selection()
            return
        entries = self._get_current_data()
        if selected >= len(entries):
            return
        entry = entries[selected]
        self.info_label.setText(f"Запись: {entry.get('title', '')}")
        if self.current_category_index == 0:
            sensitive_value = entry['password'] if self.show_sensitive_btn.isChecked() else "********"
            self.sensitive_label.setText(sensitive_value)
        elif self.current_category_index == 1:
            sensitive_value = entry['account_number'] if self.show_sensitive_btn.isChecked() else "********"
            self.sensitive_label.setText(sensitive_value)
        elif self.current_category_index == 2:
            sensitive_value = entry['wallet_address'] if self.show_sensitive_btn.isChecked() else "********"
            self.sensitive_label.setText(sensitive_value)
        self._update_attachment_info()
        self._set_info_controls_enabled(True)

    def _on_toggle_show_sensitive(self, checked):
        if checked:
            self.show_sensitive_btn.setText("Скрыть")
        else:
            self.show_sensitive_btn.setText("Показать")
        self._on_table_selection_changed()

    def _get_current_data(self):
        if self.current_category_index == -1 and self._user_category_id:
            return self.db_manager.get_all_custom_entries(self._user_category_id)
        if self.current_category_index == 0:
            return self.db_manager.get_all_entries()
        elif self.current_category_index == 1:
            return self.db_manager.get_all_bank_accounts()
        elif self.current_category_index == 2:
            return self.db_manager.get_all_crypto_wallets()
        elif self.current_category_index == 3:
            return self.db_manager.get_all_secure_notes()
        return []

    def _refresh_table(self):
        if not self.db_manager:
            return
        data = self._get_current_data()
        self.table.setRowCount(len(data))
        for row, item in enumerate(data):
            if self.current_category_index == 0:
                self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
                self.table.setItem(row, 1, QTableWidgetItem(item["username"]))
                self.table.setItem(row, 2, QTableWidgetItem(item["url"]))
            elif self.current_category_index == 1:
                self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
                self.table.setItem(row, 1, QTableWidgetItem(item["bank_name"]))
                self.table.setItem(row, 2, QTableWidgetItem(item["account_holder"]))
            elif self.current_category_index == 2:
                self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
                self.table.setItem(row, 1, QTableWidgetItem(item["currency"]))
                self.table.setItem(row, 2, QTableWidgetItem(item["wallet_address"]))
            elif self.current_category_index == 3:
                self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
                self.table.setItem(row, 1, QTableWidgetItem(item["content"]))
            elif self.current_category_index == -1:
                self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
                self.table.setItem(row, 1, QTableWidgetItem(item["content"]))
        self._filter_table(self.search_edit.text())

    def _on_search_text_changed(self, text):
        self._filter_table(text)

    def _filter_table(self, text):
        lowercase_text = text.lower()
        for row in range(self.table.rowCount()):
            row_text = ""
            for col in range(self.table.columnCount()):
                it = self.table.item(row, col)
                if it:
                    row_text += " " + it.text().lower()
            self.table.setRowHidden(row, lowercase_text not in row_text)

    def _on_add_entry(self):
        if not self.db_manager:
            return
        dialog = self._create_dialog_for_current_category()
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self._add_to_current_category(data)
            self._refresh_table()
            self.db_manager.create_backup()

    def _on_edit_entry(self):
        if not self.db_manager:
            return
        selected = self.table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите запись")
            return
        items = self._get_current_data()
        if selected >= len(items):
            return
        entry = items[selected]
        dialog = self._create_dialog_for_current_category(entry_data=entry)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self._update_current_category(entry['id'], data)
            self._refresh_table()
            self.db_manager.create_backup()

    def _on_delete_entry(self):
        if not self.db_manager:
            return
        selected = self.table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите запись")
            return
        items = self._get_current_data()
        if selected >= len(items):
            return
        entry = items[selected]
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Удалить '{entry['title']}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._delete_from_current_category(entry['id'])
            self._refresh_table()
            self.db_manager.create_backup()

    def _create_dialog_for_current_category(self, entry_data=None):
        if self.current_category_index == 0:
            return EntryDialog(self, entry_data)
        elif self.current_category_index == 1:
            return BankDialog(self, entry_data)
        elif self.current_category_index == 2:
            return CryptoDialog(self, entry_data)
        elif self.current_category_index == 3:
            return NoteDialog(self, entry_data)
        elif self.current_category_index == -1:
            return CustomEntryDialog(self, entry_data)

    def _add_to_current_category(self, data):
        if self.current_category_index == 0:
            self.db_manager.add_entry(data["title"], data["url"], data["username"],
                                      data["password"], data["notes"])
        elif self.current_category_index == 1:
            self.db_manager.add_bank_account(data["title"], data["bank_name"],
                                             data["account_holder"], data["account_number"],
                                             data["bic_swift"], data["notes"])
        elif self.current_category_index == 2:
            self.db_manager.add_crypto_wallet(data["title"], data["currency"],
                                              data["wallet_address"], data["seed_phrase"],
                                              data["notes"])
        elif self.current_category_index == 3:
            self.db_manager.add_secure_note(data["title"], data["content"])
        elif self.current_category_index == -1:
            self.db_manager.add_custom_entry(self._user_category_id, data["title"], data["content"])

    def _update_current_category(self, item_id, data):
        if self.current_category_index == 0:
            self.db_manager.update_entry(item_id, data["title"], data["url"],
                                         data["username"], data["password"], data["notes"])
        elif self.current_category_index == 1:
            self.db_manager.update_bank_account(item_id, data["title"], data["bank_name"],
                                                data["account_holder"], data["account_number"],
                                                data["bic_swift"], data["notes"])
        elif self.current_category_index == 2:
            self.db_manager.update_crypto_wallet(item_id, data["title"], data["currency"],
                                                 data["wallet_address"], data["seed_phrase"],
                                                 data["notes"])
        elif self.current_category_index == 3:
            self.db_manager.update_secure_note(item_id, data["title"], data["content"])
        elif self.current_category_index == -1:
            self.db_manager.update_custom_entry(item_id, data["title"], data["content"])

    def _delete_from_current_category(self, item_id):
        if self.current_category_index == 0:
            self.db_manager.delete_entry(item_id)
        elif self.current_category_index == 1:
            self.db_manager.delete_bank_account(item_id)
        elif self.current_category_index == 2:
            self.db_manager.delete_crypto_wallet(item_id)
        elif self.current_category_index == 3:
            self.db_manager.delete_secure_note(item_id)
        elif self.current_category_index == -1:
            self.db_manager.delete_custom_entry(item_id)

    def _on_copy_primary(self):
        selected = self.table.currentRow()
        if selected < 0 or not self.db_manager:
            return
        items = self._get_current_data()
        if selected >= len(items):
            return
        entry = items[selected]
        if self.current_category_index == 0:
            text = entry["username"]
        elif self.current_category_index == 1:
            text = entry["account_number"]
        elif self.current_category_index == 2:
            text = entry["wallet_address"]
        elif self.current_category_index == 3 or self.current_category_index == -1:
            text = entry["content"]
        self._copy_to_clipboard(text)
        self.status_bar.showMessage("Скопировано в буфер (30 сек.)", 3000)

    def _on_copy_secondary(self):
        selected = self.table.currentRow()
        if selected < 0 or not self.db_manager:
            return
        items = self._get_current_data()
        if selected >= len(items):
            return
        entry = items[selected]
        if self.current_category_index == 0:
            text = entry["password"]
        elif self.current_category_index == 1:
            text = entry["bic_swift"]
        elif self.current_category_index == 2:
            text = entry["seed_phrase"]
        else:
            return
        self._copy_to_clipboard(text)
        self.status_bar.showMessage("Скопировано в буфер (30 сек.)", 3000)

    def _copy_to_clipboard(self, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        if hasattr(self, 'clipboard_timer') and self.clipboard_timer.isActive():
            self.clipboard_timer.stop()
        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.setSingleShot(True)
        self.clipboard_timer.timeout.connect(self._clear_clipboard)
        self.clipboard_timer.start(30000)

    def _clear_clipboard(self):
        clipboard = QApplication.clipboard()
        if clipboard.text():
            clipboard.setText("")
        self.status_bar.showMessage("Буфер обмена очищен", 3000)

    def _update_attachment_info(self):
        if not self.db_manager or self.table.currentRow() < 0:
            self.attachment_name_label.setText("")
            return
        entry = self._get_current_data()[self.table.currentRow()]
        table_name = self._current_table_name()
        filename, _ = self.db_manager.get_attachment(table_name, entry['id'])
        if filename:
            self.attachment_name_label.setText(f"Вложение: {filename}")
        else:
            self.attachment_name_label.setText("")

    def _current_table_name(self):
        if self.current_category_index == -1:
            return "custom_entries"
        return CATEGORY_TABLES[self.current_category_index]

    def _on_attach_file(self):
        if not self.db_manager or self.table.currentRow() < 0:
            return
        filepath, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if not filepath:
            return
        try:
            with open(filepath, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл: {e}")
            return
        entry = self._get_current_data()[self.table.currentRow()]
        table_name = self._current_table_name()
        filename = Path(filepath).name
        self.db_manager.set_attachment(table_name, entry['id'], filename, file_bytes)
        self._update_attachment_info()
        QMessageBox.information(self, "Готово", "Файл зашифрован и сохранён.")

    def _on_download_file(self):
        if not self.db_manager or self.table.currentRow() < 0:
            return
        entry = self._get_current_data()[self.table.currentRow()]
        table_name = self._current_table_name()
        filename, data = self.db_manager.get_attachment(table_name, entry['id'])
        if not data:
            QMessageBox.warning(self, "Ошибка", "Нет вложенного файла.")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить файл как...", filename)
        if not filepath:
            return
        try:
            with open(filepath, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Готово", f"Файл сохранён как\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")

    def _on_add_custom_category(self):
        if not self.db_manager:
            QMessageBox.warning(self, "Ошибка", "Сначала откройте базу данных.")
            return
        name, ok = QInputDialog.getText(self, "Новая категория", "Название категории:")
        if ok and name.strip():
            # Проверка уникальности
            for i in range(self.category_list.count()):
                if self.category_list.item(i).text() == name.strip():
                    QMessageBox.warning(self, "Ошибка", "Такая категория уже существует.")
                    return
            self.db_manager.add_custom_category(name.strip())
            self._load_custom_categories()

    def _load_custom_categories(self):
        if not self.db_manager:
            return
        # Удаляем старые пользовательские элементы (все, что после встроенных)
        while self.category_list.count() > len(CATEGORY_NAMES):
            self.category_list.takeItem(self.category_list.count() - 1)
        cats = self.db_manager.get_all_custom_categories()
        for cat in cats:
            self.category_list.addItem(cat["name"])

    def _on_new_database(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Создать новую базу",
                                                  str(Path.home()), "Password DB (*.pdb)")
        if filepath:
            if not filepath.endswith(".pdb"):
                filepath += ".pdb"
            self._open_database(filepath, new=True)

    def _on_open_database(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Открыть базу данных",
                                                  str(Path.home()), "Password DB (*.pdb)")
        if filepath:
            self._open_database(filepath, new=False)

    def _open_database(self, db_path: str, new: bool = False):
        if self.db_manager:
            self.db_manager.close()
            self.db_manager = None
            self.current_db_path = None

        db = DatabaseManager(db_path)
        password, ok = QInputDialog.getText(self, "Мастер-пароль",
                                            "Придумайте мастер-пароль:" if new else "Введите мастер-пароль:",
                                            echo=QLineEdit.Password)
        if not ok or not password:
            QMessageBox.warning(self, "Отмена", "Пароль не введён.")
            db.close()
            return
        if new:
            db.initialize_master_password(password)
        else:
            if not db.verify_master_password(password):
                QMessageBox.critical(self, "Ошибка", "Неверный мастер-пароль!")
                db.close()
                return
        self.db_manager = db
        self.current_db_path = db_path
        self.status_bar.showMessage(f"База данных: {db_path}")
        self.search_edit.clear()
        self.category_list.setCurrentRow(0)   # вернуться к паролям
        self._load_custom_categories()
        self._update_table_headers()
        self._refresh_table()
        self._set_controls_enabled(True)
    def _on_category_context_menu(self, pos):
        """Показывает контекстное меню для пользовательской категории."""
        item = self.category_list.itemAt(pos)
        if item is None:
            return
        row = self.category_list.row(item)
        if row < len(CATEGORY_NAMES):
            # Встроенная категория — не даём удалять или переименовывать
            return
        # Это пользовательская категория
        menu = QMenu(self)
        rename_action = menu.addAction("Переименовать")
        delete_action = menu.addAction("Удалить")
        action = menu.exec(self.category_list.mapToGlobal(pos))
        if action == rename_action:
            self._on_rename_category(row, item.text())
        elif action == delete_action:
            self._on_delete_category(row, item.text())
    def _on_rename_category(self, row, old_name):
        new_name, ok = QInputDialog.getText(self, "Переименовать категорию",
                                            "Новое название:", text=old_name)
        if ok and new_name.strip():
            # Проверка на дубликат
            for i in range(self.category_list.count()):
                if i != row and self.category_list.item(i).text() == new_name.strip():
                    QMessageBox.warning(self, "Ошибка", "Категория с таким именем уже существует.")
                    return
            # Обновление в БД
            cat_name = old_name
            cats = self.db_manager.get_all_custom_categories()
            for cat in cats:
                if cat["name"] == cat_name:
                    self.db_manager.rename_custom_category(cat["id"], new_name.strip())
                    break
            # Обновление в интерфейсе
            self.category_list.item(row).setText(new_name.strip())

    def _on_delete_category(self, row, name):
        reply = QMessageBox.question(self, "Удаление категории",
                                     f"Удалить категорию «{name}» и все её записи?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            cats = self.db_manager.get_all_custom_categories()
            cat_id = None
            for cat in cats:
                if cat["name"] == name:
                    cat_id = cat["id"]
                    break
            if cat_id is not None:
                self.db_manager.delete_custom_category(cat_id)
            # Удаляем элемент из списка
            self.category_list.takeItem(row)
    def _on_backup_database(self):
        if not self.db_manager or not self.current_db_path:
            QMessageBox.warning(self, "Ошибка", "Нет открытой базы данных.")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Куда сохранить резервную копию?",
                                                  str(Path.home()), "Password DB backup (*.pdb)")
        if filepath:
            if not filepath.endswith(".pdb"):
                filepath += ".pdb"
            try:
                shutil.copy2(self.current_db_path, filepath)
                QMessageBox.information(self, "Готово", f"Резервная копия сохранена:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать копию:\n{e}")

    def _on_emergency_kit(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить аварийный комплект",
                                                  str(Path.home() / "PasswordVault_Emergency_Kit.txt"),
                                                  "Текстовый файл (*.txt)")
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("""=== Аварийный комплект PasswordVault ===

1. Ваш мастер-пароль:
   [ЗАПИШИТЕ ЕГО И ХРАНИТЕ В НАДЁЖНОМ МЕСТЕ]

2. Резервная копия базы данных:
   Рекомендуется регулярно создавать резервную копию через меню «Резервная копия».
   Храните копию на отдельном носителе (флешке, облаке).

3. Как восстановить доступ:
   - Установите PasswordVault на компьютер.
   - Откройте резервный файл .pdb через «Открыть базу данных».
   - Введите ваш мастер-пароль.

4. Если мастер-пароль утерян:
   Восстановить данные невозможно, так как они надёжно зашифрованы.
   Берегите пароль!

5. Контакты:
   Разработчик: Алексей Ещенко
   Дипломный проект БФУ им. Канта, 2026""")
                QMessageBox.information(self, "Готово", f"Аварийный комплект сохранён:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать комплект:\n{e}")

    def _on_about(self):
        QMessageBox.about(
            self,
            "О программе",
            "PasswordVault\n"
            "Локальный менеджер паролей\n"
            "Версия: 1.0\n\n"
            "Разработчик: Алексей Ещенко\n"
            "Дипломный проект БФУ им. Канта, 2026\n\n"
            "Безопасное хранение и управление конфиденциальными данными."
        )

    def closeEvent(self, event):
        if self.db_manager:
            self.db_manager.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())