# poc-desktop-app-updater

PoC cơ chế **forced self-replacing update** (kiểu rekordbox) cho desktop app Windows:
Python + tkinter, build 1 file `app.exe` bằng Nuitka, phân phối qua GitHub Releases.

## Flow

```
app.exe (bản cũ) khởi động
  → gọi GitHub API /releases/latest, so sánh tag_name với APP_VERSION
  → nếu có bản mới: dialog chỉ có nút OK (chặn hoàn toàn UI chính)
  → OK: tải app.exe mới về thành app_new.exe (cùng thư mục)
  → ghi updater.bat ra đĩa, chạy nó độc lập, rồi app cũ sys.exit()
  → updater.bat: đợi app cũ thoát hẳn (retry copy đến khi hết lock)
      → copy app_new.exe đè lên app.exe → xóa app_new.exe
      → start app.exe (giờ là bản mới) → tự xóa chính nó
  → app.exe bản mới hiển thị version mới
```

**Tại sao cần `updater.bat`?** Trên Windows, một process không thể xóa/ghi đè
file `.exe` đang chạy của chính nó (file bị lock). Nên app phải thoát và nhờ
một process ngoài (batch script) làm việc ghi đè rồi khởi động lại.
`updater.bat` được generate động trong `app.py` lúc runtime để đỡ 1 file trong repo.

## Cấu trúc

- `app.py` — toàn bộ logic: UI + check update + self-update flow
- `.github/workflows/release.yml` — push tag `v*` → build Nuitka → tạo Release kèm `app.exe`
- `requirements.txt` — chỉ có `nuitka`

## Cách test

1. **Release bản 1.0.0**: giữ `APP_VERSION = "1.0.0"` trong `app.py`, rồi:

   ```
   git add -A && git commit -m "v1.0.0"
   git tag v1.0.0 && git push origin dev v1.0.0
   ```

   Đợi Actions chạy xong → Release `v1.0.0` có `app.exe`. Tải `app.exe` này về
   một thư mục bất kỳ (đây là "bản đã cài" của user).

2. **Release bản 1.0.1**: sửa `APP_VERSION = "1.0.1"`, commit, rồi:

   ```
   git tag v1.0.1 && git push origin dev v1.0.1
   ```

3. **Chạy `app.exe` bản 1.0.0 đã tải ở bước 1**:
   - Thấy dialog "Có bản cập nhật mới (v1.0.1). Bấm OK để cập nhật." — chỉ có nút OK.
   - Bấm OK → app thoát, vài giây sau app tự mở lại, hiển thị **App Version: 1.0.1**.
   - Kiểm tra thư mục: `app_new.exe` và `updater.bat` đã tự xóa, chỉ còn `app.exe` mới.

Ghi chú:

- Không code signing → SmartScreen sẽ cảnh báo khi chạy lần đầu, chọn "Run anyway".
- Chạy `python app.py` trực tiếp (chưa compile) thì bỏ qua check update, vì không có
  file `.exe` để ghi đè.
