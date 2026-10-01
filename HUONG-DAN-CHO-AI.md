# Hướng dẫn cho AI: cài bot Zalo cá nhân trên Hermes

Tài liệu này viết cho coding agent (Claude Code, Codex, Cursor). Người dùng thường không phải lập trình viên. Hãy hỏi **từng câu một**, dùng lời dễ hiểu, và không tự đoán thông tin doanh nghiệp hay ID Zalo.

Trong tài liệu, `<profile>` là tên profile người dùng chọn. Mọi lệnh đều chạy dạng `hermes -p <profile> ...`.

## Nguyên tắc an toàn

1. Trước khi tạo profile, cài plugin, sửa file cấu hình, bật hoặc dừng gateway, xoá phiên: nói rõ sắp làm gì và chờ người dùng đồng ý.
2. Không đọc, in ra, sao chép hay commit `session.json` và ảnh QR. Không dùng phiên của profile khác.
3. Một tài khoản Zalo chỉ có một bot nghe. Nếu `hermes profile list` cho thấy profile khác cũng chạy Zalo bằng cùng tài khoản, dừng lại và báo người dùng; chỉ làm tiếp khi họ xác nhận đã tắt bên kia.
4. Không tự gửi tin vào nhóm có người thật để thử. Việc nhắn thử do người dùng hoặc một tài khoản phụ của họ làm.
5. Không thêm ID nào vào danh sách cho phép nếu người dùng chưa xác nhận đúng tên người hoặc tên nhóm đó.
6. AI không quét QR thay người dùng được. Đến bước đó, hướng dẫn họ mở Zalo trên điện thoại.

## Bước 1. Xem hiện trạng (chỉ đọc)

```powershell
hermes --version
node --version
git --version
hermes profile list
```

- Thiếu Hermes, Node.js (cần từ 18) hoặc Git: hướng dẫn cài rồi mới làm tiếp.
- Nếu profile định dùng đã tồn tại: chạy `hermes -p <profile> zalo-ca-nhan status` để biết đã làm tới đâu.

## Bước 2. Hỏi người dùng

Hỏi lần lượt, chờ trả lời xong mới hỏi câu sau:

1. Đặt tên profile là gì? (gợi ý `zalo-bot`, chỉ gồm chữ thường, số, gạch nối)
2. Tài khoản Zalo nào làm bot? Tài khoản đó có đang chạy bot nào khác hay mở Zalo Web không?
3. Bot trả lời về chủ đề gì? Thông tin lấy từ đâu (bảng giá, chính sách, tài liệu khoá học)? Xin nội dung hoặc file.
4. Khi khách hỏi ngoài phạm vi hoặc bot không có dữ liệu, bot nói câu gì?
5. Xưng hô thế nào (em với anh/chị, mình với bạn)? Trả lời ngắn hay chi tiết?
6. Tình huống nào phải chuyển cho người thật, và ai tiếp nhận? Có cụm từ riêng nào cần thêm (ví dụ "bảo hành", "đổi trả")?
7. Bot có trả lời tin nhắn riêng không? Nếu có, của những ai? (khuyên: chỉ thêm ID cụ thể)
8. Bot hoạt động ở nhóm nào? Có bắt buộc `@nhắc tên` không? (khuyên: có)
9. Ai là người quản trị nhận thông báo nội bộ của Hermes?

Câu 7, 8, 9 cần ID. Sau khi đăng nhập QR ở bước 3, chạy các lệnh sau và đưa danh sách **tên kèm ID** cho người dùng chọn:

```powershell
hermes -p <profile> zalo-ca-nhan groups
hermes -p <profile> zalo-ca-nhan friends
hermes -p <profile> zalo-ca-nhan find-group "<link mời nhóm>"
```

Tóm tắt lại toàn bộ câu trả lời, các ID đã chọn kèm tên, và chính sách cho phép. Chờ người dùng duyệt rồi mới ghi file.

## Bước 3. Cài đặt (sau khi được đồng ý)

1. Tạo profile trống, không sao chép từ profile khác:
   `hermes profile create <profile> --no-skills`
2. Nếu profile chưa có model: nhờ người dùng chạy `hermes -p <profile> model` và chọn.
3. Cài plugin:
   `hermes -p <profile> plugins install vietducltd/hermes-zalo-ca-nhan --enable`
4. Cài thư viện Node:
   `hermes -p <profile> zalo-ca-nhan setup`
5. Nhờ người dùng tự chạy và quét QR:
   `hermes -p <profile> zalo-ca-nhan login`
6. Tạo `SOUL.md` trong thư mục profile từ `plugins/zalo-ca-nhan/mau/SOUL.md.example`, chỉ điền thông tin người dùng đã xác nhận. Giữ nguyên phần "An toàn và chuyển người".
7. Ghép `plugins/zalo-ca-nhan/mau/config.yaml.example` vào `config.yaml` của profile. Giữ các khoá sẵn có khác trong file. Bắt buộc có:
   - `platforms.zalo_ca_nhan.enabled: true`
   - `home_channel.chat_id` là User ID người quản trị (không phải nhóm khách)
   - `allowed_users`, `allowed_groups` đúng danh sách đã duyệt, mọi ID đặt trong ngoặc kép
   - `platform_toolsets.zalo_ca_nhan: []` và danh sách `agent.disabled_toolsets` như file mẫu, để AI không có công cụ nào ngoài việc trả lời

Thư mục profile: `%LOCALAPPDATA%\hermes\profiles\<profile>` trên Windows, `~/.hermes/profiles/<profile>` trên macOS và Linux.

## Bước 4. Chạy và nghiệm thu

1. Xin phép rồi chạy thử ở cửa sổ đang mở: `hermes -p <profile> gateway run`
2. Nhờ người dùng dùng **tài khoản Zalo khác** thử lần lượt:
   - Nhắn riêng từ tài khoản được phép: bot trả lời.
   - Nhắn riêng từ tài khoản không được phép: bot im lặng.
   - Trong nhóm được phép, không nhắc tên: bot im lặng. Có `@nhắc tên`: bot trả lời.
   - Nhắn "tôi muốn hoàn tiền": bot báo chuyển người rồi im lặng. Nhắn `trợ lý trả lời tiếp`: bot quay lại.
3. Khi mọi thứ đúng, hỏi người dùng có muốn chạy nền và tự bật khi mở máy không. Nếu có: `hermes -p <profile> gateway install`, rồi kiểm tra bằng `hermes -p <profile> gateway status`.

## Bước 5. Bàn giao

Báo lại cho người dùng bằng một bảng ngắn:

- Tên profile và thư mục profile
- Nhóm và người được phép (tên kèm ID), có bắt buộc nhắc tên không
- File `SOUL.md` lấy nội dung từ đâu
- Lệnh bật, dừng, xem trạng thái
- Cách đăng nhập lại khi phiên hết hạn: dừng gateway, `zalo-ca-nhan login`, bật lại
- Nhắc: không chia sẻ `session.json`, không mở Zalo Web bằng tài khoản bot khi bot đang chạy

Khi người dùng sửa `SOUL.md` hoặc `config.yaml` về sau: xin phép rồi `hermes -p <profile> gateway restart`.
