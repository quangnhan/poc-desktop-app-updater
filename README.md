# poc-desktop-app-updater

PoC cơ chế **forced self-replacing update** (kiểu rekordbox) cho desktop app Windows.

Chiến lược: build **local** bằng PyInstaller ra **nguyên 1 folder**, nén thành `app.zip`,
upload tay lên GitHub Release. App tự update bằng cách tải zip mới về và **thay thế cả folder**.

> **Điều kiện bắt buộc**: repo phải để **public**, vì app gọi GitHub API không có token.

## Flow

```
app.exe (bản cũ, trong folder cài đặt) khởi động
  → gọi GitHub API /releases/latest, so sánh tag_name với APP_VERSION
  → nếu có bản mới: dialog chỉ có nút OK (chặn hoàn toàn UI chính)
  → OK: tải app.zip mới → giải nén ra folder app_new\ (nằm CẠNH folder cài đặt)
  → ghi %TEMP%\poc_updater.bat, chạy nó độc lập, rồi app cũ sys.exit()
  → poc_updater.bat: lặp rmdir folder cũ đến khi xóa sạch (đợi app thoát hết lock)
      → move app_new\ vào thay chỗ folder cũ
      → start app.exe (giờ là bản mới) → tự xóa chính nó
  → app.exe bản mới hiển thị version mới
```

**Tại sao cần `updater.bat`?** App đang chạy bị Windows lock file exe và các dll trong
folder của nó — một process không thể tự xóa/thay folder của chính mình. Nên app phải
thoát và nhờ một process ngoài làm việc đó.

**Tại sao bat nằm trong `%TEMP%`?** Vì nó sắp xóa nguyên folder cài đặt — nếu nó nằm
trong đó thì nó tự xóa mình trước khi làm xong việc. (Tương tự, folder `app_new\` và
`cwd` của process bat cũng phải nằm ngoài folder bị xóa.)

## Step-by-step

### 0. Chuẩn bị (1 lần)

```powershell
pip install -r requirements.txt
```

### 1. Build folder app

```powershell
pyinstaller --noconsole --name app app.py
```

Kết quả: folder `dist\app\` chứa `app.exe` + `_internal\` (toàn bộ runtime).

### 2. Nén thành app.zip

```powershell
Compress-Archive -Path dist\app\* -DestinationPath app.zip -Force
```

Chú ý dấu `\*`: zip **nội dung bên trong** folder — `app.exe` phải nằm ở root của zip,
không bọc thêm một lớp folder, vì code giải nén thẳng zip ra folder cài đặt mới.

### 3. Tạo Release trên GitHub (upload tay)

Vào repo → **Releases** → **Draft a new release**:
- **Choose a tag** → gõ `v1.0.0` → "Create new tag on publish"
- Kéo thả `app.zip` vào ô assets
- **Publish release**

(Nhanh hơn nếu có GitHub CLI: `gh release create v1.0.0 app.zip`)

### 4. "Cài đặt" bản cũ để test

Giải nén `app.zip` (bản v1.0.0) vào một thư mục ngoài repo, ví dụ `D:\test-update\app\`.
Chạy `D:\test-update\app\app.exe` → SmartScreen cảnh báo (không code signing) →
"More info → Run anyway" → thấy cửa sổ **App Version: 1.0.0**.

### 5. Phát hành bản mới

1. Sửa `APP_VERSION = "1.0.1"` trong `app.py`
2. Lặp lại bước 1 (build) + bước 2 (zip) + bước 3 (release với tag `v1.0.1`)

### 6. Xem cơ chế forced update chạy

Chạy lại `D:\test-update\app\app.exe` (bản 1.0.0):
- Dialog "Có bản cập nhật mới (v1.0.1). Bấm OK để cập nhật." — chỉ có nút OK,
  không vào được UI chính.
- Bấm OK → app thoát, vài giây sau tự mở lại → **App Version: 1.0.1**.
- Mở sẵn `D:\test-update\` trước khi bấm OK để quan sát: folder `app_new\` xuất hiện,
  folder `app\` biến mất rồi được thay bằng folder mới.

## Module `updater.py` (dùng lại cho project khác)

Toàn bộ logic update nằm trong `updater.py` — file độc lập, copy sang project khác
là dùng được ngay:

```python
from updater import check_update

check_update(app_version="1.0.2", repo="owner/repo")  # goi truoc mainloop() chinh
```

`app.py` chỉ còn khai báo `APP_VERSION`, `REPO` rồi gọi hàm trên.

## Debug nhanh, không cần build lại

Test flow tải + progress bar + giải nén + bat thay thế mà không cần PyInstaller build
hay publish release mới mỗi lần — dùng `debug_force_update()`, bỏ qua hoàn toàn check
`sys.frozen` và so sánh version, luôn lấy Release mới nhất hiện có trên repo:

```powershell
New-Item -ItemType Directory .debug_test\app -Force
Copy-Item C:\Windows\System32\notepad.exe .debug_test\app\app.exe
python -c "from updater import debug_force_update as f; f('quangnhan/poc-desktop-app-updater', '.debug_test/app', '.debug_test/app/app.exe')"
```

- `.debug_test\app` là folder giả lập "thư mục cài đặt", nằm trong repo nhưng đã được
  thêm vào `.gitignore`.
- `notepad.exe` chỉ đóng vai `app.exe` giả để bat script có gì để `start` ở bước cuối
  (thấy Notepad tự mở lên = bat chạy đúng).
- ⚠️ `app_dir` truyền vào (`.debug_test/app`) sẽ bị `rmdir /s /q` xóa sạch mỗi lần chạy —
  không được trỏ vào thư mục chứa source code hay `python.exe` thật.
- Chạy lại lệnh trên nhiều lần tùy ý để test lại từ đầu, không cần bump `APP_VERSION`
  hay tạo Release mới.

## Ghi chú

- Chạy `python app.py` trực tiếp (chưa đóng gói) sẽ bỏ qua check update, vì không có
  folder cài đặt nào để thay thế.
- Chiến lược "xóa folder cũ rồi move folder mới" có khoảnh khắc rủi ro (tắt máy giữa
  chừng → không còn bản nào chạy được). Updater thật (Squirrel, electron-updater...)
  tránh việc này bằng cách cài mỗi version một folder riêng + launcher trỏ vào bản mới
  nhất. PoC này chọn cách xóa-rồi-move để giữ nguyên lý lộ rõ nhất.
