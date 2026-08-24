"""PoC: forced self-replacing update (kieu rekordbox) - Windows only.

Chien luoc: build local ra 1 FOLDER (PyInstaller onedir), zip lai thanh app.zip,
upload tay len GitHub Release. App tu update bang cach thay the ca folder.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
import zipfile
from tkinter import messagebox
from urllib.request import Request, urlopen

APP_VERSION = "1.0.1"  # sua so nay moi lan release
RELEASE_API = "https://api.github.com/repos/quangnhan/poc-desktop-app-updater/releases/latest"


def parse_version(s):
    return tuple(int(x) for x in s.lstrip("v").split("."))


def get_latest_release():
    req = Request(RELEASE_API, headers={"User-Agent": "poc-updater"})
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)


def do_update(release):
    # PyInstaller onedir: sys.executable = ...\<folder cai dat>\app.exe
    exe_path = sys.executable
    app_dir = os.path.dirname(exe_path)
    parent = os.path.dirname(app_dir)
    # folder moi phai nam NGOAI app_dir, vi app_dir sap bi xoa nguyen cum
    new_dir = os.path.join(parent, "app_new")
    zip_path = os.path.join(parent, "app_new.zip")

    # 1. Tai app.zip tu asset cua release, giai nen ra folder app_new
    url = next(a["browser_download_url"] for a in release["assets"] if a["name"] == "app.zip")
    req = Request(url, headers={"User-Agent": "poc-updater"})
    with urlopen(req, timeout=120) as resp, open(zip_path, "wb") as f:
        f.write(resp.read())
    shutil.rmtree(new_dir, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(new_dir)
    os.remove(zip_path)

    # 2. Generate updater.bat vao %TEMP%.
    # Ly do can process phu: app dang chay bi Windows lock exe + cac dll trong
    # folder cua no, nen KHONG the tu xoa/ghi de folder cua chinh minh. App phai
    # thoat, roi 1 process ngoai (bat script) xoa folder cu, dua folder moi vao
    # thay, va khoi dong lai. Bat script phai nam NGOAI folder bi xoa (o day dat
    # trong %TEMP%), neu khong no se tu xoa chinh minh giua chung.
    bat_path = os.path.join(tempfile.gettempdir(), "poc_updater.bat")
    with open(bat_path, "w") as f:
        f.write(
            "@echo off\n"
            ":wait\n"
            # ping = sleep 1s, hoat dong ca khi khong co console (timeout thi khong)
            "ping -n 2 127.0.0.1 >nul\n"
            # rmdir se fail-mot-phan khi app cu chua thoat het (file con lock)
            # -> folder van ton tai -> lap lai den khi xoa sach
            f'rmdir /s /q "{app_dir}" 2>nul\n'
            f'if exist "{app_dir}" goto wait\n'
            f'move "{new_dir}" "{app_dir}" >nul\n'
            f'start "" "{exe_path}"\n'
            'del "%~f0"\n'
        )

    # 3. Chay updater.bat doc lap (khong chet theo app cha). cwd cung phai nam
    # ngoai app_dir - process dung cwd o dau se lock folder do, rmdir khong xoa duoc.
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        cwd=tempfile.gettempdir(),
    )
    sys.exit(0)


def check_update():
    # Chi check khi da dong goi bang PyInstaller (chay `python app.py` thi bo qua,
    # vi khong co folder cai dat nao de thay the)
    if not getattr(sys, "frozen", False):
        return
    try:
        release = get_latest_release()
    except Exception:
        return  # khong co mang / repo private / chua co release -> cho dung tam
    latest = release["tag_name"]
    if parse_version(latest) > parse_version(APP_VERSION):
        # Dialog chi co nut OK -> ep buoc update, khong cho vao UI chinh
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Update required", f"Co ban cap nhat moi ({latest}). Bam OK de cap nhat.")
        do_update(release)


def main():
    check_update()
    root = tk.Tk()
    root.title("PoC Updater")
    root.geometry("400x200")
    tk.Label(root, text=f"App Version: {APP_VERSION}", font=("Segoe UI", 24)).pack(expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
