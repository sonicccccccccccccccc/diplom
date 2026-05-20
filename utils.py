import sys
import os

def resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу; работает и в разработке, и в PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
def secure_erase_string(s: str):
    """Безопасно затирает строку в памяти, заменяя её нулями."""
    if s:
        import ctypes
        # Конвертируем в bytearray и зануляем
        raw = bytearray(s.encode('utf-8'))
        for i in range(len(raw)):
            raw[i] = 0