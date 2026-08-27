"""Reusable forced-update module (PyInstaller onedir apps, Windows only).

Copy file nay sang project khac va goi:

    from updater import check_update
    check_update(app_version="1.0.2", repo="owner/repo")

Goi check_update() truoc khi dung tkinter mainloop chinh. Neu co ban moi,
ham nay se hien dialog bat buoc + progress bar tai ve, roi tu thoat app
(khong return) de bat script thay the folder va khoi dong lai ban moi.

Gia dinh BAT BUOC (khong thoa man -> check_update tu bo qua hoac update fail):
- Windows only (dung cmd.exe + creationflags rieng cua Windows).
- Build bang PyInstaller ONEDIR (co folder "_internal" canh exe). Onefile bi
  bo qua co chu dich - xem guard trong check_update.
- Goi TRUOC khi tao Tk() chinh cua app: module nay tu tao/destroy root rieng.
- Ten exe phai giu nguyen qua cac ban release: bat khoi dong lai dung path exe
  cu, doi --name giua 2 version thi app khong tu mo lai duoc.
- Thu muc CHA cua folder cai dat phai ghi duoc (folder moi giai nen ra do).
  Cai vao C:\\Program Files thi can quyen admin.
- Asset trong release phai la 1 zip chua NOI DUNG folder build o root zip
  (exe o root, khong boc them 1 lop folder).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

ASSET_NAME = "app.zip"


def parse_version(s):
    return tuple(int(x) for x in s.lstrip("v").split("."))


def _get_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = Request(url, headers={"User-Agent": "poc-updater"})
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)


def _download_with_progress(url, dest_path, on_progress):
    req = Request(url, headers={"User-Agent": "poc-updater"})
    with urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)


def _do_update(release, asset_name, on_progress, app_dir=None, exe_path=None):
    # PyInstaller onedir: sys.executable = ...\<folder cai dat>\app.exe
    # app_dir/exe_path co the duoc override (dung khi debug/test, xem
    # debug_force_update ben duoi) de khong dam vao thu muc that dang chay.
    exe_path = exe_path or sys.executable
    app_dir = app_dir or os.path.dirname(exe_path)
    parent = os.path.dirname(app_dir)
    # Ten tam duoc derive tu ten exe (khong hardcode "app_new"/"poc_updater.bat"):
    # %TEMP% va parent la thu muc dung chung - 2 app cung nhung module nay ma cai
    # canh nhau se tranh cung 1 ten -> xoa folder cua nhau.
    slug = os.path.splitext(os.path.basename(exe_path))[0]
    # folder moi phai nam NGOAI app_dir, vi app_dir sap bi xoa nguyen cum
    new_dir = os.path.join(parent, f"{slug}_new")
    zip_path = os.path.join(parent, f"{slug}_new.zip")

    # next(...) tran StopIteration khi thieu asset -> message rong tren dialog loi
    assets = {a["name"]: a["browser_download_url"] for a in release["assets"]}
    if asset_name not in assets:
        raise RuntimeError(f"Release {release['tag_name']} khong co asset {asset_name}")
    url = assets[asset_name]
    _download_with_progress(url, zip_path, on_progress)

    shutil.rmtree(new_dir, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(new_dir)
    os.remove(zip_path)

    # Generate updater.bat vao %TEMP%. Can process phu vi Windows lock exe/dll
    # cua process dang chay -> app khong the tu xoa/ghi de folder cua chinh no.
    # Bat phai nam NGOAI folder bi xoa, neu khong no tu xoa chinh minh giua chung.
    bat_path = os.path.join(tempfile.gettempdir(), f"{slug}_updater.bat")
    # Ghi UTF-8 (KHONG BOM - co BOM thi dong "@echo off" bi hong) + "chcp 65001"
    # ngay dau bat: cmd.exe decode file .bat theo codepage hien hanh, mac dinh la
    # OEM (cp437/850) khong bieu dien duoc ky tu tieng Viet -> path co dau (vd
    # C:\Users\Nhan\...) bi meo, rmdir/move tro sai cho dung luc app da tu thoat.
    # chcp doi codepage cho CA cac dong doc sau no, nen 2 dong dau phai la ASCII.
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(
            "@echo off\n"
            "chcp 65001 >nul\n"
            ":wait\n"
            "ping -n 2 127.0.0.1 >nul\n"
            f'rmdir /s /q "{app_dir}" 2>nul\n'
            f'if exist "{app_dir}" goto wait\n'
            f'move "{new_dir}" "{app_dir}" >nul\n'
            f'start "" "{exe_path}"\n'
            'del "%~f0"\n'
        )
    # CREATE_NO_WINDOW (khong phai DETACHED_PROCESS) - vi cmd.exe van tu cap phat
    # console rieng cho no du process bi "detach" khoi console cha, gay nhap
    # nhay 1 cua so den ngay sau progress bar.
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
        cwd=tempfile.gettempdir(),
    )


def _run_update_with_progress_ui(release, asset_name, app_dir=None, exe_path=None):
    win = tk.Tk()
    win.title("Updating")
    win.geometry("320x100")
    win.resizable(False, False)
    tk.Label(win, text="Downloading update...").pack(pady=(15, 5))
    bar = ttk.Progressbar(win, length=280, maximum=100)
    bar.pack(pady=5)
    pct_label = tk.Label(win, text="0%")
    pct_label.pack()

    # Tai o thread rieng - main thread chi ve UI qua vong lap after(), khong bi
    # block boi network I/O. Cap nhat truc tiep widget tu thread khac khong an
    # toan trong Tkinter, nen worker chi ghi vao "state", main thread doc va ve.
    state = {"done": 0, "total": 0, "finished": False, "error": None}

    def on_progress(done, total):
        state["done"] = done
        state["total"] = total

    def worker():
        # Phai bat exception: neu worker chet (release thieu asset dung ten, mang
        # dut, parent khong ghi duoc) ma khong set "finished" thi poll() chay vo
        # han -> cua so treo o 0%, khong dong duoc, user khong biet chuyen gi.
        try:
            _do_update(
                release, asset_name, on_progress, app_dir=app_dir, exe_path=exe_path
            )
        except Exception as e:
            state["error"] = e
        state["finished"] = True

    def poll():
        total = state["total"]
        pct = int(state["done"] * 100 / total) if total else 0
        bar["value"] = pct
        pct_label.config(text=f"{pct}%")
        if state["error"] is not None:
            # showerror TRUOC destroy: goi khi khong con root nao song thi tkinter
            # phai tu tao root tam, de sinh chuyen la.
            e = state["error"]
            messagebox.showerror("Update failed", f"{type(e).__name__}: {e}", parent=win)
            win.destroy()
            os._exit(1)
        if state["finished"]:
            # sys.exit() trong callback tkinter bi report_callback_exception
            # nuot mat, nen thoat process truc tiep - bat da chay doc lap roi.
            os._exit(0)
        win.after(50, poll)

    threading.Thread(target=worker, daemon=True).start()
    win.after(50, poll)
    win.mainloop()


def check_update(app_version, repo, asset_name=ASSET_NAME):
    """Chi check khi da dong goi bang PyInstaller (chay `python app.py` thi bo
    qua, vi khong co folder cai dat nao de thay the)."""
    if not getattr(sys, "frozen", False):
        return
    # Chi ho tro PyInstaller ONEDIR. Voi onefile, sys.executable nam o thu muc bat
    # ky (Desktop, Downloads...) -> app_dir se la thu muc do va bat se rmdir /s /q
    # ca thu muc do. Nhan dien onedir bang su ton tai cua "_internal".
    if not os.path.isdir(os.path.join(os.path.dirname(sys.executable), "_internal")):
        return
    try:
        release = _get_latest_release(repo)
        # parse_version phai nam trong try: tag kieu "v1.2-beta" hay "release-3"
        # se raise ValueError -> crash app ngay luc khoi dong.
        latest = release["tag_name"]
        newer = parse_version(latest) > parse_version(app_version)
    except Exception:
        return  # khong co mang / repo private / chua release / tag la -> dung tam
    if newer:
        # Dialog chi co nut OK -> ep buoc update, khong cho vao UI chinh
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "Update required", f"Co ban cap nhat moi ({latest}). Bam OK de cap nhat."
        )
        root.destroy()
        _run_update_with_progress_ui(release, asset_name)


def debug_force_update(repo, app_dir, exe_path, asset_name=ASSET_NAME):
    """CHI DUNG DE TEST THU CONG. Bo qua check sys.frozen va so sanh version,
    luon tai release moi nhat ve va chay full flow (tai + progress bar + giai
    nen + bat thay the + khoi dong lai) - de test updater ma khong can build
    lai bang PyInstaller hay publish release moi moi lan.

    app_dir/exe_path BAT BUOC tro toi 1 THU MUC TEST RIENG, vd ".debug_test\\app"
    ngay trong repo (da them vao .gitignore) - KHONG duoc tro vao thu muc chua
    source code hay python.exe that, vi flow nay se `rmdir /s /q` nguyen app_dir.
    Chuan bi truoc: tao app_dir, bo vao do 1 file .exe bat ky (vd copy
    notepad.exe, doi ten thanh app.exe) de "start" o buoc cuoi co gi de chay thu.

    Vi du chay tu thu muc goc repo:
        mkdir .debug_test\\app
        copy C:\\Windows\\System32\\notepad.exe .debug_test\\app\\app.exe
        python -c "from updater import debug_force_update as f; f('owner/repo', '.debug_test/app', '.debug_test/app/app.exe')"
    """
    # bat chay voi cwd=%TEMP%, nen path phai la absolute - neu khong "start" o
    # buoc cuoi se resolve nham theo %TEMP% thay vi thu muc goc cua ban.
    app_dir = os.path.abspath(app_dir)
    exe_path = os.path.abspath(exe_path)
    release = _get_latest_release(repo)
    _run_update_with_progress_ui(release, asset_name, app_dir=app_dir, exe_path=exe_path)
