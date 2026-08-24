# PoC: Forced Self-Replacing Update (kiểu rekordbox) — Windows

## Mục đích project

Đây là **Proof of Concept để học cơ chế**, KHÔNG phải app hoàn chỉnh. Minh họa flow
forced update: app phát hiện bản mới trên GitHub Releases → chặn hoàn toàn UI (dialog
chỉ có nút OK) → tải bản mới → thay thế chính nó → tự khởi động lại bản mới.

Nguyên tắc khi sửa code: **ít code nhất có thể**. Không thêm error handling/retry/
progress bar/checksum, không refactor cho đẹp, không dùng thư viện update chuyên dụng
(PyUpdater, Squirrel...) — mục tiêu là để lộ rõ cơ chế thủ công.

## Chiến lược build & phân phối (hiện tại)

- Build **local** bằng PyInstaller **onedir** → ra nguyên folder `dist\app\`
  (`app.exe` + `_internal\`). KHÔNG dùng CI — workflow GitHub Actions đã bị xóa
  có chủ đích (từng tồn tại với Nuitka onefile, xem git history).
- Nén folder thành `app.zip`, **upload tay** lên GitHub Release (tạo tag `vX.Y.Z`
  ngay lúc tạo release trên web).
- Repo: `quangnhan/poc-desktop-app-updater`, branch làm việc: `dev`.
- **Repo PHẢI để public** — app gọi GitHub API không có token; repo private thì
  check update thất bại im lặng (rơi vào `except` trong `check_update`).

## Cơ chế update (toàn bộ nằm trong `app.py`, ~110 dòng)

1. Khởi động: gọi `GET /repos/.../releases/latest`, so `tag_name` với `APP_VERSION`
   (hardcode ở đầu file — mỗi lần release chỉ sửa số này).
2. Có bản mới → dialog bắt buộc (chỉ nút OK) → `do_update()`:
   - Tải asset **tên đúng là `app.zip`** → giải nén ra `app_new\` **cạnh** folder cài đặt.
   - Ghi `%TEMP%\poc_updater.bat` (generate động bằng string, path nhúng cứng;
     tên có tiền tố `poc_` vì %TEMP% là thư mục dùng chung, tránh đụng tên app khác).
   - Chạy bat với `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, `cwd=%TEMP%`, rồi `sys.exit(0)`.
   - Bat: lặp `rmdir /s /q` folder cũ đến khi xóa sạch (đợi app thoát hết file lock)
     → `move` `app_new\` vào thay → `start` app.exe mới → tự xóa (`del "%~f0"`).

### Các ràng buộc kỹ thuật KHÔNG được phá (đã đúc kết từ lúc làm)

- **Cần process phụ (bat)**: Windows lock exe + dll của process đang chạy → app không
  thể tự xóa/ghi đè folder của chính nó. Đây là nguyên lý trung tâm của PoC.
- **Bat phải nằm NGOÀI folder bị xóa** (`%TEMP%`) — nằm trong thì nó tự xóa mình giữa chừng.
- **`cwd` của process bat phải ngoài folder bị xóa** — process đứng cwd ở đâu sẽ lock
  folder đó, `rmdir` không xóa được.
- **`app_new\` phải nằm ngoài folder cài đặt** (đặt cạnh, cùng cấp).
- Trong bat dùng `ping -n 2 127.0.0.1` để sleep — `timeout` LỖI khi chạy detached
  không có console ("Input redirection is not supported").
- `app.zip` phải chứa **nội dung** folder build ở root zip (`app.exe` ở root, không
  bọc thêm 1 lớp folder) — code `extractall` thẳng ra folder mới.
- Guard `getattr(sys, "frozen", False)`: chạy `python app.py` trực tiếp thì bỏ qua
  check update (không có folder cài đặt để thay).

## Quy trình release một bản mới

```powershell
# 1. Sửa APP_VERSION trong app.py (vd "1.0.1")
pyinstaller --noconsole --name app app.py --noconfirm   # -> dist\app\
Compress-Archive -Path dist\app\* -DestinationPath app.zip -Force
# 2. GitHub web: Releases -> Draft a new release -> tag mới vX.Y.Z -> đính app.zip -> Publish
```

Test: giải nén app.zip bản CŨ ra `D:\test-update\app\`, chạy `app.exe` → dialog ép
update → OK → app thoát, vài giây sau tự mở lại với version mới.

## Gotchas đã gặp (tránh mất thời gian lại)

- `Compress-Archive` ngay sau khi build có thể lỗi "file being used by another process"
  (antivirus quét file mới) → chạy lại lệnh là được.
- Xóa Release trên GitHub web có thể xóa (hoặc không xóa) tag kèm theo tùy thao tác —
  kiểm tra bằng `git ls-remote --tags origin`. Xóa tag remote không ảnh hưởng tag local.
- Push lại tag đã tồn tại trên remote = no-op. (Trước đây quan trọng với CI; giờ tag
  được tạo trên web lúc publish release nên ít đụng lệnh tag.)
- API `releases/latest` chọn release theo **ngày commit** được tag (không phải ngày tạo
  release), bỏ qua draft/prerelease.
- Không code signing → SmartScreen cảnh báo khi chạy exe, chọn "Run anyway" — chấp nhận,
  không xử lý gì trong code.
- PoC dùng chiến lược "xóa folder cũ rồi move folder mới" — có khoảnh khắc rủi ro nếu
  tắt máy giữa chừng. Updater thật dùng versioned folders + launcher. Đã biết, chấp
  nhận để giữ code tối giản.

## Cấu trúc repo

- `app.py` — toàn bộ logic (UI tkinter 1 cửa sổ hiện version + check update + self-update)
- `requirements.txt` — chỉ `pyinstaller`
- `README.md` — hướng dẫn step-by-step cho người dùng
- `CLAUDE.md` — file này (context cho AI)
- Không commit: `dist/`, `build/`, `*.spec`, `app.zip` (đã ignore)
