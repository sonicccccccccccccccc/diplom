import sqlite3
import os
import shutil
import datetime
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._ensure_attachment_columns()   # <-- автоматически добавим столбцы, если их нет
        self._key = None

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS master_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                salt BLOB NOT NULL,
                iv BLOB NOT NULL,
                test_cipher BLOB NOT NULL
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT DEFAULT '',
                username TEXT DEFAULT '',
                password BLOB DEFAULT '',
                notes BLOB DEFAULT ''
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                bank_name TEXT DEFAULT '',
                account_holder TEXT DEFAULT '',
                account_number BLOB DEFAULT '',
                bic_swift TEXT DEFAULT '',
                notes BLOB DEFAULT ''
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS crypto_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                currency TEXT DEFAULT '',
                wallet_address BLOB DEFAULT '',
                seed_phrase BLOB DEFAULT '',
                notes BLOB DEFAULT ''
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS secure_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content BLOB DEFAULT ''
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content BLOB DEFAULT '',
                FOREIGN KEY (category_id) REFERENCES custom_categories(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def _ensure_attachment_columns(self):
        """Добавляет столбцы attachment и attachment_name во все таблицы записей, если их нет."""
        tables = ["entries", "bank_accounts", "crypto_wallets", "secure_notes"]
        for table in tables:
            try:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN attachment BLOB DEFAULT ''")
            except sqlite3.OperationalError:
                pass   # уже существует
            try:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN attachment_name TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        self.conn.commit()

    def _get_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        return kdf.derive(password.encode('utf-8'))

    def initialize_master_password(self, password: str):
        salt = os.urandom(16)
        key = self._get_key(password, salt)
        aesgcm = AESGCM(key)
        iv = os.urandom(12)
        test_plaintext = b"password_check"
        test_cipher = aesgcm.encrypt(iv, test_plaintext, None)
        self.conn.execute(
            "INSERT INTO master_meta (id, salt, iv, test_cipher) VALUES (1, ?, ?, ?);",
            (salt, iv, test_cipher)
        )
        self.conn.commit()
        self._key = key

    def verify_master_password(self, password: str) -> bool:
        cursor = self.conn.execute("SELECT salt, iv, test_cipher FROM master_meta WHERE id = 1;")
        row = cursor.fetchone()
        if not row:
            return False
        salt = row["salt"]
        iv = row["iv"]
        test_cipher = row["test_cipher"]
        key = self._get_key(password, salt)
        aesgcm = AESGCM(key)
        try:
            decrypted = aesgcm.decrypt(iv, test_cipher, None)
            if decrypted == b"password_check":
                self._key = key
                return True
        except Exception:
            pass
        return False

    # ---------- Шифрование строк и байтов ----------
    def _encrypt_field(self, plaintext: str) -> bytes:
        return self._encrypt_blob(plaintext.encode('utf-8'))

    def _decrypt_field(self, data: bytes) -> str:
        return self._decrypt_blob(data).decode('utf-8')

    def _encrypt_blob(self, data: bytes) -> bytes:
        if not self._key:
            raise RuntimeError("Нет ключа шифрования")
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def _decrypt_blob(self, data: bytes) -> bytes:
        if not self._key:
            raise RuntimeError("Нет ключа шифрования")
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self._key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    # ---------- Управление вложениями (общее для всех таблиц) ----------
    def set_attachment(self, table: str, item_id: int, filename: str, file_bytes: bytes):
        enc_data = self._encrypt_blob(file_bytes)
        self.conn.execute(
            f"UPDATE {table} SET attachment = ?, attachment_name = ? WHERE id = ?;",
            (enc_data, filename, item_id)
        )
        self.conn.commit()
    def add_custom_category(self, name: str):
        self.conn.execute("INSERT INTO custom_categories (name) VALUES (?);", (name,))
        self.conn.commit()
    def add_custom_entry(self, category_id, title, content):
        enc_content = self._encrypt_field(content)
        self.conn.execute(
            "INSERT INTO custom_entries (category_id, title, content) VALUES (?, ?, ?);",
            (category_id, title, enc_content))
        self.conn.commit()

    def get_all_custom_entries(self, category_id):
        cursor = self.conn.execute(
            "SELECT * FROM custom_entries WHERE category_id = ? ORDER BY id;", (category_id,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d['content'] = self._decrypt_field(d['content'])
            result.append(d)
        return result

    def update_custom_entry(self, entry_id, title, content):
        enc_content = self._encrypt_field(content)
        self.conn.execute(
            "UPDATE custom_entries SET title = ?, content = ? WHERE id = ?;",
            (title, enc_content, entry_id))
        self.conn.commit()
    def rename_custom_category(self, category_id: int, new_name: str):
        self.conn.execute(
            "UPDATE custom_categories SET name = ? WHERE id = ?;",
            (new_name, category_id)
        )
        self.conn.commit()
    def delete_custom_entry(self, entry_id):
        self.conn.execute("DELETE FROM custom_entries WHERE id = ?;", (entry_id,))
        self.conn.commit()
    def get_all_custom_categories(self):
        cursor = self.conn.execute("SELECT * FROM custom_categories ORDER BY name;")
        return cursor.fetchall()

    def delete_custom_category(self, category_id: int):
        self.conn.execute("DELETE FROM custom_entries WHERE category_id = ?;", (category_id,))
        self.conn.execute("DELETE FROM custom_categories WHERE id = ?;", (category_id,))
        self.conn.commit()
    def get_attachment(self, table: str, item_id: int):
        """Возвращает (filename, decrypted_bytes) или (None, None)."""
        cursor = self.conn.execute(
            f"SELECT attachment_name, attachment FROM {table} WHERE id = ?;", (item_id,))
        row = cursor.fetchone()
        if row and row["attachment"]:
            return row["attachment_name"], self._decrypt_blob(row["attachment"])
        return None, None

    def remove_attachment(self, table: str, item_id: int):
        self.conn.execute(
            f"UPDATE {table} SET attachment = '', attachment_name = '' WHERE id = ?;", (item_id,))
        self.conn.commit()

    # ---------- CRUD сущностей (как раньше, но без изменений) ----------
    def add_entry(self, title, url, username, password, notes):
        enc_pw = self._encrypt_field(password)
        enc_notes = self._encrypt_field(notes)
        self.conn.execute(
            "INSERT INTO entries (title, url, username, password, notes) VALUES (?, ?, ?, ?, ?);",
            (title, url, username, enc_pw, enc_notes))
        self.conn.commit()

    def get_all_entries(self):
        cursor = self.conn.execute("SELECT * FROM entries ORDER BY id;")
        return [self._decrypt_entry(row) for row in cursor]

    def _decrypt_entry(self, row):
        d = dict(row)
        d['password'] = self._decrypt_field(d['password'])
        d['notes'] = self._decrypt_field(d['notes'])
        return d

    def update_entry(self, entry_id, title, url, username, password, notes):
        enc_pw = self._encrypt_field(password)
        enc_notes = self._encrypt_field(notes)
        self.conn.execute(
            "UPDATE entries SET title=?, url=?, username=?, password=?, notes=? WHERE id=?;",
            (title, url, username, enc_pw, enc_notes, entry_id))
        self.conn.commit()

    def delete_entry(self, entry_id):
        self.conn.execute("DELETE FROM entries WHERE id=?;", (entry_id,))
        self.conn.commit()

    # ---------- Банковские счета ----------
    def add_bank_account(self, title, bank_name, account_holder, account_number, bic_swift, notes):
        enc_number = self._encrypt_field(account_number)
        enc_notes = self._encrypt_field(notes)
        self.conn.execute(
            "INSERT INTO bank_accounts (title, bank_name, account_holder, account_number, bic_swift, notes) VALUES (?, ?, ?, ?, ?, ?);",
            (title, bank_name, account_holder, enc_number, bic_swift, enc_notes)
        )
        self.conn.commit()

    def get_all_bank_accounts(self):
        cursor = self.conn.execute("SELECT * FROM bank_accounts ORDER BY id;")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['account_number'] = self._decrypt_field(item['account_number'])
            item['notes'] = self._decrypt_field(item['notes'])
            result.append(item)
        return result

    def update_bank_account(self, account_id, title, bank_name, account_holder, account_number, bic_swift, notes):
        enc_number = self._encrypt_field(account_number)
        enc_notes = self._encrypt_field(notes)
        self.conn.execute(
            "UPDATE bank_accounts SET title=?, bank_name=?, account_holder=?, account_number=?, bic_swift=?, notes=? WHERE id=?;",
            (title, bank_name, account_holder, enc_number, bic_swift, enc_notes, account_id)
        )
        self.conn.commit()

    def delete_bank_account(self, account_id):
        self.conn.execute("DELETE FROM bank_accounts WHERE id=?;", (account_id,))
        self.conn.commit()

    # ---------- Криптокошельки ----------
    def add_crypto_wallet(self, title, currency, wallet_address, seed_phrase, notes):
        enc_address = self._encrypt_field(wallet_address)
        enc_seed = self._encrypt_field(seed_phrase)
        enc_notes = self._encrypt_field(notes)
        self.conn.execute(
            "INSERT INTO crypto_wallets (title, currency, wallet_address, seed_phrase, notes) VALUES (?, ?, ?, ?, ?);",
            (title, currency, enc_address, enc_seed, enc_notes)
        )
        self.conn.commit()

    def get_all_crypto_wallets(self):
        cursor = self.conn.execute("SELECT * FROM crypto_wallets ORDER BY id;")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['wallet_address'] = self._decrypt_field(item['wallet_address'])
            item['seed_phrase'] = self._decrypt_field(item['seed_phrase'])
            item['notes'] = self._decrypt_field(item['notes'])
            result.append(item)
        return result

    def update_crypto_wallet(self, wallet_id, title, currency, wallet_address, seed_phrase, notes):
        enc_address = self._encrypt_field(wallet_address)
        enc_seed = self._encrypt_field(seed_phrase)
        enc_notes = self._encrypt_field(notes)
        self.conn.execute(
            "UPDATE crypto_wallets SET title=?, currency=?, wallet_address=?, seed_phrase=?, notes=? WHERE id=?;",
            (title, currency, enc_address, enc_seed, enc_notes, wallet_id)
        )
        self.conn.commit()

    def delete_crypto_wallet(self, wallet_id):
        self.conn.execute("DELETE FROM crypto_wallets WHERE id=?;", (wallet_id,))
        self.conn.commit()

    # ---------- Защищённые заметки ----------
    def add_secure_note(self, title, content):
        enc_content = self._encrypt_field(content)
        self.conn.execute(
            "INSERT INTO secure_notes (title, content) VALUES (?, ?);",
            (title, enc_content)
        )
        self.conn.commit()

    def get_all_secure_notes(self):
        cursor = self.conn.execute("SELECT * FROM secure_notes ORDER BY id;")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['content'] = self._decrypt_field(item['content'])
            result.append(item)
        return result

    def update_secure_note(self, note_id, title, content):
        enc_content = self._encrypt_field(content)
        self.conn.execute(
            "UPDATE secure_notes SET title=?, content=? WHERE id=?;",
            (title, enc_content, note_id)
        )
        self.conn.commit()

    def delete_secure_note(self, note_id):
        self.conn.execute("DELETE FROM secure_notes WHERE id=?;", (note_id,))
        self.conn.commit()

    # ---------- Резервное копирование ----------
    def create_backup(self, max_backups=5):
        if not self.conn or not self.db_path:
            return
        db_path = Path(self.db_path)
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{db_path.stem}_{timestamp}{db_path.suffix}"
        backup_path = backup_dir / backup_name
        shutil.copy2(self.db_path, backup_path)
        backups = sorted(backup_dir.glob(f"{db_path.stem}_*{db_path.suffix}"))
        if len(backups) > max_backups:
            for old_backup in backups[:-max_backups]:
                old_backup.unlink()
        return str(backup_path)

    def close(self):
        if self.conn:
            self.conn.close()