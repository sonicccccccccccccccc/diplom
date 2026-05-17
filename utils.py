import sys
import os

def resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу; работает и в разработке, и в PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)