"""PoC: forced self-replacing update (kieu rekordbox) - Windows only.

Chien luoc: build local ra 1 FOLDER (PyInstaller onedir), zip lai thanh app.zip,
upload tay len GitHub Release. App tu update bang cach thay the ca folder.

Logic update nam trong updater.py (module tach rieng, copy sang project khac
duoc). File nay chi goi check_update().
"""

import tkinter as tk

from updater import check_update

APP_VERSION = "1.0.4"  # sua so nay moi lan release
REPO = "quangnhan/poc-desktop-app-updater"


def main():
    check_update(app_version=APP_VERSION, repo=REPO)
    root = tk.Tk()
    root.title("PoC Updater")
    root.geometry("400x200")
    tk.Label(root, text=f"App Version: {APP_VERSION}", font=("Segoe UI", 24)).pack(
        expand=True
    )
    root.mainloop()


if __name__ == "__main__":
    main()
