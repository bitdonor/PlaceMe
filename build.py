import os
import shutil
import subprocess
import sys

def build():
    print("Начинаем сборку проекта...")
    
    # 1. Запускаем PyInstaller
    # --noconfirm: перезаписывать папку dist без спроса
    # --onefile: один .exe файл
    # --windowed: без консоли
    # --icon: иконка приложения
    # --name: имя файла
    cmd = [
        os.path.join(".venv", "Scripts", "python.exe"), "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--icon", "Graduate_icon.ico",
        "--name", "PlaceMe",
        "main.py"
    ]
    
    print(f"Выполняем команду: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    print("\nPyInstaller завершил работу. Формируем папку Release...")
    
    # 2. Создаем папку Release
    release_dir = "Release"
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir)
    
    # 3. Перемещаем .exe в Release
    exe_name = "PlaceMe.exe"
    dist_exe = os.path.join("dist", exe_name)
    if os.path.exists(dist_exe):
        shutil.move(dist_exe, os.path.join(release_dir, exe_name))
        print(f"Файл {exe_name} перемещен в папку {release_dir}.")
    else:
        print(f"Ошибка: файл {dist_exe} не найден!")
        return

    # 4. Копируем папку data, иконку и руководство в Release
    shutil.copy("Graduate_icon.ico", os.path.join(release_dir, "Graduate_icon.ico"))
    if os.path.exists("manual.html"):
        shutil.copy("manual.html", os.path.join(release_dir, "manual.html"))
        print("Файл manual.html скопирован в Release.")
    
    data_src = "data"
    data_dst = os.path.join(release_dir, "data")
    if os.path.exists(data_src):
        shutil.copytree(data_src, data_dst)
        print(f"Папка {data_src} скопирована в {release_dir}.")
        
    # 5. Очищаем мусор после сборки (по желанию, можно оставить, но лучше убрать)
    print("Очистка временных файлов сборки...")
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    if os.path.exists("PlaceMe.spec"):
        os.remove("PlaceMe.spec")
        
    print("\nСборка успешно завершена! Готовое приложение лежит в папке Release.")

if __name__ == "__main__":
    build()
