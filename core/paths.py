import os
import sys


def get_base_dir() -> str:
    """
    Возвращает базовую директорию приложения.
    Если запущено как скомпилированный .exe (onefile), возвращает папку,
    в которой находится сам .exe файл.
    Если запущено как обычный скрипт, возвращает корень проекта.
    """
    if getattr(sys, 'frozen', False):
        # Запущено через PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Запущено как python main.py (поднимаемся на уровень выше от core)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_dir() -> str:
    """Возвращает путь к папке data/configurations"""
    return os.path.join(get_base_dir(), "data", "configurations")


def get_results_dir() -> str:
    """Возвращает путь к папке results"""
    return os.path.join(get_base_dir(), "results")


def get_icon_path() -> str:
    return os.path.join(get_base_dir(), "Graduate_icon.ico")


def get_manual_path() -> str:
    return os.path.join(get_base_dir(), "manual.html")
