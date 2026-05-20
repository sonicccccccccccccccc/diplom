import os
import shutil
import datetime
import hashlib
import hmac
from pathlib import Path
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import sqlite3

# ---------- Безопасное зануление данных в памяти ----------
def _secure_erase(data: bytearray):
    if data:
        data[:] = b'\x00' * len(data)

SALT_SIZE = 16
MASTER_KEY_SIZE = 32
NONCE_SIZE = 12

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._kek = None
        self._master_key = None
        self._temp_path = None
        self.conn = None
        self._salt = None
        self._encrypted_master_key = None

    # ----------------------------------------------------------------------
    # Вспомогательные функции
    # ----------------------------------------------------------------------
    def _get_kek(self, password: str, salt: bytes) -> bytes:
        kdf = Argon2id(
            salt=salt,
            length=32,
            memory_cost=65536,
            iterations=4,
            lanes=2,
        )
        return kdf.derive(password.encode('utf-8'))

    def _encrypt_master_key(self, master_key: bytes, kek: bytes) -> bytes:
        aesgcm = AESGCM(kek)
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = aesgcm.encrypt(nonce, master_key, None)
        return nonce + ciphertext

    def _decrypt_master_key(self, encrypted_key: bytes, kek: bytes) -> bytes:
        nonce = encrypted_key[:NONCE_SIZE]
        ciphertext = encrypted_key[NONCE_SIZE:]
        aesgcm = AESGCM(kek)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _encrypt_blob(self, data: bytes, key: bytes) -> bytes:
        aesgcm = AESGCM(key)
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def _decrypt_blob(self, data: bytes, key: bytes) -> bytes:
        nonce = data[:NONCE_SIZE]
        ciphertext = data[NONCE_SIZE:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT DEFAULT '',
                username TEXT DEFAULT '',
                password TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                attachment BLOB DEFAULT '',
                attachment_name TEXT DEFAULT ''
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                bank_name TEXT DEFAULT '',
                account_holder TEXT DEFAULT '',
                account_number TEXT DEFAULT '',
                bic_swift TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                attachment BLOB DEFAULT '',
                attachment_name TEXT DEFAULT ''
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS crypto_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                currency TEXT DEFAULT '',
                wallet_address TEXT DEFAULT '',
                seed_phrase TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                attachment BLOB DEFAULT '',
                attachment_name TEXT DEFAULT ''
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS secure_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                attachment BLOB DEFAULT '',
                attachment_name TEXT DEFAULT ''
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
                content TEXT DEFAULT '',
                attachment BLOB DEFAULT '',
                attachment_name TEXT DEFAULT '',
                FOREIGN KEY (category_id) REFERENCES custom_categories(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def _ensure_attachment_columns(self):
        tables = ["entries", "bank_accounts", "crypto_wallets", "secure_notes", "custom_entries"]
        for table in tables:
            try:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN attachment BLOB DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            try:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN attachment_name TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        self.conn.commit()

    # ----------------------------------------------------------------------
    # Инициализация новой базы (полное шифрование)
    # ----------------------------------------------------------------------
    def initialize_master_password(self, password: str):
        salt = os.urandom(SALT_SIZE)
        master_key = os.urandom(MASTER_KEY_SIZE)
        kek = self._get_kek(password, salt)
        encrypted_master_key = self._encrypt_master_key(master_key, kek)

        self._salt = salt
        self._encrypted_master_key = encrypted_master_key
        self._master_key = master_key
        self._kek = kek

        self._temp_path = self.db_path + ".tmp"
        self.conn = sqlite3.connect(self._temp_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._ensure_attachment_columns()

    # ----------------------------------------------------------------------
    # Проверка мастер-пароля и открытие существующей базы
    # ----------------------------------------------------------------------
    def verify_master_password(self, password: str) -> bool:
        if not os.path.exists(self.db_path):
            return False

        with open(self.db_path, 'rb') as f:
            salt = f.read(SALT_SIZE)
            if len(salt) < SALT_SIZE:
                return self._verify_old_format(password)
            encrypted_master_key = f.read(MASTER_KEY_SIZE + NONCE_SIZE + 16)
            ciphertext = f.read()

        try:
            kek = self._get_kek(password, salt)
            master_key = self._decrypt_master_key(encrypted_master_key, kek)
            plaintext = self._decrypt_blob(ciphertext, master_key)
        except Exception:
            return False

        self._temp_path = self.db_path + ".tmp"
        with open(self._temp_path, 'wb') as f:
            f.write(plaintext)

        self.conn = sqlite3.connect(self._temp_path)
        self.conn.row_factory = sqlite3.Row
        self._master_key = master_key
        self._kek = kek
        self._salt = salt
        self._encrypted_master_key = encrypted_master_key
        return True

    def _verify_old_format(self, password: str) -> bool:
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute("SELECT salt, key_hash FROM master_meta WHERE id = 1;")
            row = cursor.fetchone()
            if not row:
                self.conn.close()
                self.conn = None
                return False
            salt = row["salt"]
            stored_hash = row["key_hash"] if "key_hash" in row.keys() else None
            kek = self._get_kek(password, salt)
            if stored_hash:
                computed_hash = hashlib.sha256(kek).digest()
                if not hmac.compare_digest(computed_hash, stored_hash):
                    self.conn.close()
                    self.conn = None
                    return False
            self._kek = kek
            return True
        except Exception:
            if self.conn:
                self.conn.close()
                self.conn = None
            return False

    # ----------------------------------------------------------------------
    # Закрытие базы (сохранение в зашифрованный .pdb)
    # ----------------------------------------------------------------------
    def close(self):
        # Сохраняем изменения во временный файл и перешифровываем в .pdb
        if self.conn and self._temp_path and self._master_key:
            self.conn.commit()
            self.conn.close()
            self.conn = None

            with open(self._temp_path, 'rb') as f:
                plaintext = f.read()
            ciphertext = self._encrypt_blob(plaintext, self._master_key)

            with open(self.db_path, 'wb') as f:
                if self._salt and self._encrypted_master_key:
                    f.write(self._salt)
                    f.write(self._encrypted_master_key)
                else:
                    raise RuntimeError("Нет соли или зашифрованного мастер-ключа для сохранения")
                f.write(ciphertext)

            os.remove(self._temp_path)
            self._temp_path = None
        elif self.conn and not self._temp_path:
            self.conn.close()
            self.conn = None

        if self._kek:
            _secure_erase(bytearray(self._kek))
            self._kek = None
        if self._master_key:
            _secure_erase(bytearray(self._master_key))
            self._master_key = None
    # ----------------------------------------------------------------------
    # Управление вложениями
    # ----------------------------------------------------------------------
    def set_attachment(self, table: str, item_id: int, filename: str, file_bytes: bytes):
        self.conn.execute(
            f"UPDATE {table} SET attachment = ?, attachment_name = ? WHERE id = ?;",
            (file_bytes, filename, item_id)
        )
        self.conn.commit()

    def get_attachment(self, table: str, item_id: int):
        cursor = self.conn.execute(
            f"SELECT attachment_name, attachment FROM {table} WHERE id = ?;", (item_id,))
        row = cursor.fetchone()
        if row and row["attachment"]:
            return row["attachment_name"], row["attachment"]
        return None, None

    def remove_attachment(self, table: str, item_id: int):
        self.conn.execute(
            f"UPDATE {table} SET attachment = '', attachment_name = '' WHERE id = ?;", (item_id,))
        self.conn.commit()

    # ----------------------------------------------------------------------
    # CRUD-операции
    # ----------------------------------------------------------------------
    def add_entry(self, title, url, username, password, notes):
        self.conn.execute(
            "INSERT INTO entries (title, url, username, password, notes) VALUES (?, ?, ?, ?, ?);",
            (title, url, username, password, notes))
        self.conn.commit()

    def get_all_entries(self):
        cursor = self.conn.execute("SELECT * FROM entries ORDER BY id;")
        return [dict(row) for row in cursor]

    def update_entry(self, entry_id, title, url, username, password, notes):
        self.conn.execute(
            "UPDATE entries SET title=?, url=?, username=?, password=?, notes=? WHERE id=?;",
            (title, url, username, password, notes, entry_id))
        self.conn.commit()

    def delete_entry(self, entry_id):
        self.conn.execute("DELETE FROM entries WHERE id=?;", (entry_id,))
        self.conn.commit()

    def add_bank_account(self, title, bank_name, account_holder, account_number, bic_swift, notes):
        self.conn.execute(
            "INSERT INTO bank_accounts (title, bank_name, account_holder, account_number, bic_swift, notes) VALUES (?, ?, ?, ?, ?, ?);",
            (title, bank_name, account_holder, account_number, bic_swift, notes))
        self.conn.commit()

    def get_all_bank_accounts(self):
        cursor = self.conn.execute("SELECT * FROM bank_accounts ORDER BY id;")
        return [dict(row) for row in cursor]

    def update_bank_account(self, account_id, title, bank_name, account_holder, account_number, bic_swift, notes):
        self.conn.execute(
            "UPDATE bank_accounts SET title=?, bank_name=?, account_holder=?, account_number=?, bic_swift=?, notes=? WHERE id=?;",
            (title, bank_name, account_holder, account_number, bic_swift, notes, account_id))
        self.conn.commit()

    def delete_bank_account(self, account_id):
        self.conn.execute("DELETE FROM bank_accounts WHERE id=?;", (account_id,))
        self.conn.commit()

    def add_crypto_wallet(self, title, currency, wallet_address, seed_phrase, notes):
        self.conn.execute(
            "INSERT INTO crypto_wallets (title, currency, wallet_address, seed_phrase, notes) VALUES (?, ?, ?, ?, ?);",
            (title, currency, wallet_address, seed_phrase, notes))
        self.conn.commit()

    def get_all_crypto_wallets(self):
        cursor = self.conn.execute("SELECT * FROM crypto_wallets ORDER BY id;")
        return [dict(row) for row in cursor]

    def update_crypto_wallet(self, wallet_id, title, currency, wallet_address, seed_phrase, notes):
        self.conn.execute(
            "UPDATE crypto_wallets SET title=?, currency=?, wallet_address=?, seed_phrase=?, notes=? WHERE id=?;",
            (title, currency, wallet_address, seed_phrase, notes, wallet_id))
        self.conn.commit()

    def delete_crypto_wallet(self, wallet_id):
        self.conn.execute("DELETE FROM crypto_wallets WHERE id=?;", (wallet_id,))
        self.conn.commit()

    def add_secure_note(self, title, content):
        self.conn.execute(
            "INSERT INTO secure_notes (title, content) VALUES (?, ?);",
            (title, content))
        self.conn.commit()

    def get_all_secure_notes(self):
        cursor = self.conn.execute("SELECT * FROM secure_notes ORDER BY id;")
        return [dict(row) for row in cursor]

    def update_secure_note(self, note_id, title, content):
        self.conn.execute(
            "UPDATE secure_notes SET title=?, content=? WHERE id=?;",
            (title, content, note_id))
        self.conn.commit()

    def delete_secure_note(self, note_id):
        self.conn.execute("DELETE FROM secure_notes WHERE id=?;", (note_id,))
        self.conn.commit()

    def add_custom_category(self, name: str):
        self.conn.execute("INSERT INTO custom_categories (name) VALUES (?);", (name,))
        self.conn.commit()

    def get_all_custom_categories(self):
        cursor = self.conn.execute("SELECT * FROM custom_categories ORDER BY name;")
        return cursor.fetchall()

    def rename_custom_category(self, category_id: int, new_name: str):
        self.conn.execute(
            "UPDATE custom_categories SET name = ? WHERE id = ?;",
            (new_name, category_id))
        self.conn.commit()

    def delete_custom_category(self, category_id: int):
        self.conn.execute("DELETE FROM custom_entries WHERE category_id = ?;", (category_id,))
        self.conn.execute("DELETE FROM custom_categories WHERE id = ?;", (category_id,))
        self.conn.commit()

    def add_custom_entry(self, category_id, title, content):
        self.conn.execute(
            "INSERT INTO custom_entries (category_id, title, content) VALUES (?, ?, ?);",
            (category_id, title, content))
        self.conn.commit()

    def get_all_custom_entries(self, category_id):
        cursor = self.conn.execute(
            "SELECT * FROM custom_entries WHERE category_id = ? ORDER BY id;", (category_id,))
        return [dict(row) for row in cursor]

    def update_custom_entry(self, entry_id, title, content):
        self.conn.execute(
            "UPDATE custom_entries SET title=?, content=? WHERE id=?;",
            (title, content, entry_id))
        self.conn.commit()

    def delete_custom_entry(self, entry_id):
        self.conn.execute("DELETE FROM custom_entries WHERE id=?;", (entry_id,))
        self.conn.commit()

    # ---------- Резервное копирование ----------
    def create_backup(self, max_backups=5):
        if not self.conn:
            return

        backup_dir = Path(self.db_path).parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(self.db_path).stem
        backup_path = backup_dir / f"{base_name}_{timestamp}{Path(self.db_path).suffix}"

        if self._temp_path and self._master_key:
            self.conn.commit()
            with open(self._temp_path, 'rb') as f:
                plaintext = f.read()
            ciphertext = self._encrypt_blob(plaintext, self._master_key)
            with open(backup_path, 'wb') as f:
                if self._salt and self._encrypted_master_key:
                    f.write(self._salt)
                    f.write(self._encrypted_master_key)
                else:
                    raise RuntimeError("Нет соли или зашифрованного мастер-ключа для сохранения")
                f.write(ciphertext)
        else:
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, backup_path)
            else:
                return

        backups = sorted(backup_dir.glob(f"{base_name}_*{Path(self.db_path).suffix}"))
        if len(backups) > max_backups:
            for old_backup in backups[:-max_backups]:
                old_backup.unlink()
        return str(backup_path)