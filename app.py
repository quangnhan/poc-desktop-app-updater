"""PoC: forced self-replacing update (kieu rekordbox) - Windows only."""
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from urllib.request import Request, urlopen

APP_VERSION = "1.0.0"  # sua so nay moi lan release
RELEASE_API = "https://api.github.com/repos/quangnhan/poc-desktop-app-updater/releases/latest"


def parse_version(s):
    return tuple(int(x) for x in s.lstrip("v").split("."))


def get_latest_release():
    req = Request(RELEASE_API, headers={"User-Agent": "poc-updater"})
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)


def do_update(release):
    # Duong dan exe dang chay. Voi Nuitka onefile, sys.argv[0] la file .exe goc.
    exe_path = os.path.abspath(sys.argv[0])
    exe_dir = os.path.dirname(exe_path)
    new_exe = os.path.join(exe_dir, "app_new.exe")

    # 1. Tai app.exe moi tu asset cua release
    url = next(a["browser_download_url"] for a in release["assets"] if a["name"] == "app.exe")
    req = Request(url, headers={"User-Agent": "poc-updater"})
    with urlopen(req, timeout=60) as resp, open(new_exe, "wb") as f:
        f.write(resp.read())

    # 2. Generate updater.bat.
    # Ly do can process phu: tren Windows, 1 process KHONG the xoa/ghi de
    # file .exe cua chinh no khi dang chay (file bi lock). Nen app phai thoat,
    # va 1 process khac (bat script) lam viec copy-de + restart.
    bat_path = os.path.join(exe_dir, "updater.bat")
    with open(bat_path, "w") as f:
        f.write(
            "@echo off\n"
            ":wait\n"
            # ping = cach sleep 1s hoat dong ca khi khong co console (timeout thi khong)
            "ping -n 2 127.0.0.1 >nul\n"
            # copy fail khi app.exe cu chua thoat het (con bi lock) -> thu lai
            f'copy /y "{new_exe}" "{exe_path}" >nul 2>&1 || goto wait\n'
            f'del "{new_exe}"\n'
            f'start "" "{exe_path}"\n'
            'del "%~f0"\n'
        )

    # 3. Chay updater.bat doc lap (khong chet theo app cha), roi thoat ngay
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        cwd=exe_dir,
    )
    sys.exit(0)


def check_update():
    # Chi check khi da build bang Nuitka (chay `python app.py` thi bo qua,
    # vi khong co file .exe de ghi de)
    if "__compiled__" not in globals():
        return
    try:
        release = get_latest_release()
    except Exception:
        return  # khong co mang / chua co release -> cho dung tam
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
