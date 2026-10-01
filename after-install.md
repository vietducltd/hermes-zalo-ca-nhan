# Đã cài plugin Zalo cá nhân

Làm tiếp theo thứ tự (thay `zalo-bot` bằng tên profile của bạn):

1. Cài thư viện: `hermes -p zalo-bot zalo-ca-nhan setup`
2. Quét QR: `hermes -p zalo-bot zalo-ca-nhan login`
3. Lấy ID nhóm và người: `hermes -p zalo-bot zalo-ca-nhan groups` và `friends`
4. Chép `mau/SOUL.md.example` và `mau/config.yaml.example` vào profile, điền thông tin (xem `README.md`)
5. Chạy thử: `hermes -p zalo-bot gateway run`

Bot mặc định chặn tất cả cho tới khi bạn thêm ID vào danh sách cho phép.

Không chia sẻ `session.json` hay ảnh QR cho bất kỳ ai.
