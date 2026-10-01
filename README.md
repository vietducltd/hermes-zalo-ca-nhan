# Hermes Zalo cá nhân

Plugin cho [Hermes Agent](https://github.com/NousResearch/hermes-agent): biến **một tài khoản Zalo cá nhân** thành trợ lý AI trả lời khách. Đăng nhập bằng mã QR, chạy hoàn toàn trên máy của bạn. Không cần Zalo OA, không cần đăng ký Zalo App, không cần webhook hay ngrok.

> **Đọc trước khi dùng.** Zalo không cung cấp API chính thức cho tài khoản cá nhân; plugin dùng thư viện cộng đồng `zca-js`. Zalo có thể giới hạn tài khoản hoặc bắt đăng nhập lại bất kỳ lúc nào. Hãy dùng một tài khoản phụ, không gửi tin hàng loạt, và mỗi tài khoản chỉ chạy **một** bot.

## Bot làm được gì

- Trả lời tin nhắn riêng của những người bạn cho phép.
- Trả lời trong nhóm bạn cho phép, mặc định chỉ khi được `@nhắc tên`.
- Tự dừng 24 giờ và báo "đã chuyển người phụ trách" khi khách nhắc tới khiếu nại, hoàn tiền, thanh toán, mật khẩu, OTP... hoặc gửi ảnh, file, ghi âm.
- Tự nhường khi chính bạn gõ tay trả lời khách trong tin nhắn riêng.
- Khách nhắn `trợ lý trả lời tiếp` để bot quay lại.

Mặc định bot **chặn tất cả**. Bạn phải chủ động thêm từng người, từng nhóm vào danh sách cho phép.

## Cách nhanh nhất: nhờ AI cài

Mở Claude Code (hoặc Codex, Cursor) tại một thư mục bất kỳ và nói:

> Đọc file HUONG-DAN-CHO-AI.md trong repo `vietducltd/hermes-zalo-ca-nhan`, hỏi tôi từng câu rồi cài bot Zalo cá nhân cho tôi.

AI sẽ kiểm tra máy, hỏi thông tin doanh nghiệp, xin xác nhận trước mỗi thay đổi. Riêng bước quét QR bạn phải tự làm trên điện thoại.

## Cài thủ công

Các lệnh dưới đây dùng profile tên `zalo-bot`. Muốn tên khác thì thay ở mọi lệnh.

### Bước 1. Kiểm tra máy

Cần Hermes (đã chọn model), Node.js 18 trở lên và Git.

```powershell
hermes --version
node --version
git --version
```

### Bước 2. Tạo profile riêng

Dùng profile riêng để bot Zalo không dính tới token hay cấu hình của các bot khác.

```powershell
hermes profile create zalo-bot --no-skills
hermes -p zalo-bot model
```

### Bước 3. Cài plugin và đăng nhập

```powershell
hermes -p zalo-bot plugins install vietducltd/hermes-zalo-ca-nhan --enable
hermes -p zalo-bot zalo-ca-nhan setup
hermes -p zalo-bot zalo-ca-nhan login
```

Ảnh QR tự mở trên máy. Mở Zalo trên điện thoại của **tài khoản sẽ làm bot**, quét mã rồi bấm xác nhận. Phiên đăng nhập chỉ lưu trong thư mục profile trên máy bạn.

Kiểm tra lại:

```powershell
hermes -p zalo-bot zalo-ca-nhan status
```

### Bước 4. Viết tính cách cho bot

Thư mục profile nằm ở `%LOCALAPPDATA%\hermes\profiles\zalo-bot` (Windows) hoặc `~/.hermes/profiles/zalo-bot` (macOS, Linux). Chép file mẫu rồi điền thông tin doanh nghiệp của bạn:

```powershell
$profile = Join-Path $env:LOCALAPPDATA 'hermes\profiles\zalo-bot'
Copy-Item "$profile\plugins\zalo-ca-nhan\mau\SOUL.md.example" "$profile\SOUL.md"
notepad "$profile\SOUL.md"
```

### Bước 5. Lấy ID người và nhóm

Cả ba lệnh đều chỉ đọc, không gửi tin nào.

```powershell
hermes -p zalo-bot zalo-ca-nhan groups
hermes -p zalo-bot zalo-ca-nhan find-group "https://zalo.me/g/xxxxxxxx"
hermes -p zalo-bot zalo-ca-nhan friends
```

- `groups`: các nhóm tài khoản bot đang tham gia, kèm Group ID.
- `find-group`: lấy Group ID từ link mời nhóm.
- `friends`: bạn bè của tài khoản bot, kèm User ID. Dùng để lấy ID của người quản trị.

Người chưa kết bạn thì dùng `contacts` sau khi gateway đã chạy và họ đã nhắn cho bot:

```powershell
hermes -p zalo-bot zalo-ca-nhan contacts
```

### Bước 6. Cấu hình

Mở `config.yaml` của profile và ghép nội dung từ `plugins\zalo-ca-nhan\mau\config.yaml.example`. Phần quan trọng nhất:

```yaml
platforms:
  zalo_ca_nhan:
    enabled: true
    home_channel:
      platform: zalo_ca_nhan
      chat_id: "USER_ID_NGUOI_QUAN_TRI"
      name: "Quản trị Zalo"
    extra:
      allowed_users:
        - "USER_ID_DUOC_NHAN_RIENG"
      allowed_groups:
        "GROUP_ID_DA_KIEM_TRA":
          enabled: true
          require_mention: true
      handoff_seconds: 86400
```

`home_channel` là nơi Hermes gửi thông báo nội bộ. Hãy điền User ID của người quản trị, đừng điền nhóm khách.

### Bước 7. Chạy thử

```powershell
hermes -p zalo-bot gateway run
```

Nhờ **một tài khoản Zalo khác** nhắn cho bot (hoặc `@nhắc tên` bot trong nhóm đã cho phép). Tin do chính tài khoản bot gửi sẽ không được trả lời. Bấm `Ctrl+C` để dừng.

Khi đã ổn, cho chạy nền và tự bật khi mở máy:

```powershell
hermes -p zalo-bot gateway install
hermes -p zalo-bot gateway status
```

Dừng bot: `hermes -p zalo-bot gateway stop`. Gỡ chạy nền: `hermes -p zalo-bot gateway uninstall`.

## Tuỳ chỉnh trong `extra`

| Khoá | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `allowed_users` | `[]` | User ID được bot trả lời tin nhắn riêng. Rỗng là không trả lời ai. |
| `allowed_groups` | `{}` | Group ID được bot trả lời. Rỗng là không trả lời nhóm nào. |
| `require_mention` | `true` | Trong nhóm chỉ trả lời khi được `@nhắc tên`. Có thể đặt riêng cho từng nhóm. |
| `handoff_seconds` | `86400` | Số giây bot tạm dừng sau khi chuyển người thật. |
| `handoff_keywords` | `[]` | Thêm cụm từ riêng của bạn khiến bot chuyển người, ví dụ `["bảo hành", "đổi trả"]`. |
| `owner_takeover` | `true` | Bạn gõ tay trả lời khách (tin nhắn riêng) thì bot tạm dừng với khách đó. |
| `handoff_message` | có sẵn | Câu bot gửi khi chuyển người thật. |
| `media_message` | có sẵn | Câu bot gửi khi khách gửi ảnh, file, ghi âm. |
| `resume_message` | có sẵn | Câu bot gửi khi khách nhắn `trợ lý trả lời tiếp`. |

Sửa `config.yaml` hoặc `SOUL.md` xong cần khởi động lại gateway: `hermes -p zalo-bot gateway restart`.

## Xử lý sự cố

| Hiện tượng | Cách xử lý |
| --- | --- |
| Bot không trả lời | Xem gateway có đang chạy không, ID đã nằm trong `allowed_users` / `allowed_groups` chưa, trong nhóm đã `@nhắc tên` bot chưa. |
| Tự nhắn bằng tài khoản bot mà không thấy trả lời | Đúng thiết kế. Dùng một tài khoản Zalo khác để thử. |
| Bot im lặng với một khách | Khách đó đang trong 24 giờ chuyển người thật. Nhờ khách nhắn `trợ lý trả lời tiếp`. |
| Báo chưa đăng nhập hoặc phiên hết hạn | Dừng gateway, chạy lại `zalo-ca-nhan login`, rồi bật gateway. |
| Báo "mở phiên nghe ở nơi khác" | Tài khoản đang mở Zalo Web hoặc một bot khác. Tắt bên kia rồi khởi động lại gateway. |
| Trả lời hai lần | Có hai gateway cùng dùng một tài khoản Zalo. Tắt bớt một cái. |
| Đổi `SOUL.md` mà bot vẫn trả lời kiểu cũ | Khởi động lại gateway. Nếu vẫn vậy, xoá phiên hội thoại cũ: `hermes -p zalo-bot sessions list --source zalo_ca_nhan` rồi `sessions delete`. |
| `setup` báo lỗi | Kiểm tra `node --version` từ 18 trở lên và máy có mạng. |

## Bảo mật và riêng tư

- Plugin không cấp cho AI công cụ nào để tự gửi tin, tạo nhóm hay đọc danh bạ. AI chỉ trả lời đúng cuộc hội thoại đang hỏi.
- Dữ liệu lưu trên máy gồm: phiên đăng nhập (`session.json`) và một file SQLite chứa ID tin đã xử lý, ID người và nhóm đã thấy, ai đang tạm dừng. **Không lưu nội dung tin nhắn.**
- Log chỉ ghi ID đã băm.
- Không gửi `session.json` hay ảnh QR cho bất kỳ ai. Ai có file đó là đăng nhập được Zalo của bạn.

Xoá phiên khỏi máy: `hermes -p zalo-bot zalo-ca-nhan logout --yes`.

## Dành cho người sửa mã

```powershell
npm install
npm test
python -m unittest tests.test_policy tests.test_store tests.test_link
```

`tests/test_adapter.py` cần Python của Hermes: `hermes --run-module unittest discover -s tests -t .`

Kiểm tra plugin theo chuẩn Hermes: `hermes plugins validate .`

## Giấy phép

MIT. Kiến trúc ban đầu tham khảo dự án mã nguồn mở [zalo-hermes](https://github.com/congthuanmmm/zalo-hermes) (MIT); xem file `LICENSE`.
