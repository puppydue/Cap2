# Ghi chú giao diện web — những gì đã gỡ khỏi màn hình

Để giao diện gọn và giống sản phẩm hoàn thiện, các dòng hướng dẫn, ghi chú và mã yêu cầu (FR, NFR, BRULE, KPI) đã được gỡ khỏi các trang web. Toàn bộ nội dung đó được giữ lại ở đây, sắp theo từng trang, để nhóm đọc lại và đối chiếu với BRD / Sprint 0.

## Bảng mã yêu cầu ↔ trang web

| Trang | Module · chức năng BFD | Yêu cầu |
|---|---|---|
| Tổng quan | M6 · F5.1 Dashboard trực tiếp | FR-10, FR-17, AC-06.1, NFR-01 |
| Trực ca & sự cố | M3 · F2.4 Ghi nhận xử lý sự cố | FR-07, AC-04.1, AC-04.2, KPI O4, O5 |
| Bảng LED hai đầu cầu | M3 · F2.2 Tín hiệu tại chỗ | FR-05, FR-17, AC-03.1 |
| Lượt qua cầu | M1 · F1.2, F1.3 | FR-02, FR-03 |
| Đối chiếu vé | M5 · F4.1, F4.2 | FR-14, BRULE-08 |
| Cơ cấu khách | M4 · F3.3 | FR-09, BRULE-06 |
| Lịch sử lượt khách | M6 · F3.2, F5.1 | FR-09, FR-10 |
| Báo cáo định kỳ | M4 · F5.2, F5.3 | FR-11, AC-07.1, KPI O1, O4, O5, O8 |
| Camera | M1 · F1.1 Thiết lập nguồn hình | FR-01, NFR-03 |
| Ngưỡng & giờ hoạt động | M7 · F6.2 | FR-13, BRULE-01, BRULE-07 |
| Người nhận cảnh báo | M7 · F6.3 | FR-13, FR-06 |
| Tài khoản | M2 · F6.1 | FR-12, NFR-04 |
| Quyền riêng tư | M7 · PB-06 | NFR-05, BRULE-05, BRULE-06, BRULE-09 |
| Google Sheets | Tiện ích ngoài BFD | — |

Mã yêu cầu vẫn được ghi ở phần đầu mỗi tệp `frontend/views/*.py`, chỉ không hiện trên màn hình nữa.

## Đăng nhập
- Lần đầu sử dụng: tài khoản **admin**, mật khẩu **admin123**. Hệ thống bắt đổi mật khẩu ngay sau khi đăng nhập.
- Nếu trang báo chưa kết nối được máy chủ, chạy backend trước:
  `uvicorn backend.main:app --host 0.0.0.0 --port 8000` (bỏ `--host 0.0.0.0` nếu chỉ dùng một máy).

## Tổng quan
- Ô **Thời gian chờ** (FR-17) chỉ có giá trị khi cầu đầy (mức Đỏ).
- **Dự báo lượt vào trong ngày** = trung bình cùng thứ, cùng giờ của các tuần trước × mức đông của hôm nay so với ngày thường. Chỉ dùng để chuẩn bị nhân sự điều tiết.

## Trực ca & sự cố
- **Xử lý trong 3 phút** là KPI **O4** (mục tiêu ≥ 90%); **Báo sai** là KPI **O5** (mục tiêu ≤ 5%).

## Bảng LED hai đầu cầu
- Trên máy đặt ở mỗi đầu cầu: mở `http://<IP máy chủ>:8000/led/?dau=1` (đầu cầu 1) hoặc `?dau=2` (đầu cầu 2) bằng Chrome hoặc Edge, rồi nhấn **F11**.
- Địa chỉ hiện trong web tự đổi theo máy chủ đang truy cập, dùng được cho máy LED khác trong cùng mạng.
- Thêm `&scene=3` để khóa một cảnh. Thêm `&debug=1` (hoặc nhấn phím **D**) để mở bảng giả lập Xanh / Vàng / Đỏ và thử từng clip.
- Vai nhân vật mỗi đầu cầu đổi được trong `CONFIG.ends` ở đầu tệp `backend/led_display/led.js`.
- Xem song song: `http://<IP>:8000/led/hai-man-hinh.html`.

## Lượt qua cầu (thuật toán đếm)
- Khách đi qua vạch về phía cầu: **num += 1, dem += 1**. Đi qua vạch ra ngoài: **num −= 1**.
- **onbridge = num1 + num2.** Khi onbridge về 0 (hoặc âm do camera bỏ sót), hệ thống đặt lại num1 = num2 = 0.
- **dem** tự về 0 lúc 0 giờ mỗi ngày.

## Đối chiếu vé (BRULE-08)
- Chỉ so **lượt vào lòng cầu** (2 camera chân cầu), không dùng lượt qua mặt tiền.
- Kết quả chỉ dùng để điều phối lực lượng soát vé, **không dùng làm bằng chứng xử phạt**.
- Tỷ lệ chênh lệch = (lượt vào − số vé) / lượt vào × 100%.
- Tệp CSV / Excel nhập số vé có các cột: `date` (YYYY-MM-DD), `hour` (để trống = cả ngày), `ticket_count`.

## Cơ cấu khách và nguồn khách
- Nhãn hiển thị: **Trong nước/châu Á** và **Quốc tế** (dữ liệu trong CSDL vẫn là `Trong nuoc` / `Nuoc ngoai`).
- Đây là ước lượng từ nhóm khu vực rộng của mô hình AI: nhóm Đông Á → Trong nước/châu Á, các nhóm khác → Quốc tế. Mô hình không phân biệt được khách Việt Nam với khách Hàn Quốc, Nhật Bản, Trung Quốc, vì vậy mới gộp thành "Trong nước/châu Á".
- Số liệu chỉ dùng để xem xu hướng, không dùng để xác định quốc tịch từng người. Hệ thống không lưu ảnh hay đặc trưng khuôn mặt.
- Kết quả có độ tin cậy dưới 70% được ghi là "Không xác định" và không tính vào tỷ lệ (BRULE-06).
- Nếu trang không có hồ sơ khách: camera chân cầu chưa chạy, hoặc đang chạy với `--no-demographics`, hoặc DeepFace lỗi (xem cửa sổ lệnh camera).

## Báo cáo định kỳ (KPI Sprint 0)
| Ô trên trang | KPI | Cách tính |
|---|---|---|
| Phút vượt sức chứa | O1 | Số phút có ít nhất một lần đo vượt sức chứa |
| Xử lý trong 3 phút | O4 | Trên sự cố cảnh báo Đỏ thật (không tính báo sai), mục tiêu ≥ 90% |
| Cảnh báo sai | O5 | Sự cố người trực đánh dấu "Báo sai" ở trang Trực ca & sự cố, mục tiêu ≤ 5% |
| Chênh lệch vé | O8 | Chỉ tính những ngày đã nhập số cuống vé |

## Camera (Giám sát trực tiếp & Cấu hình camera)
- Giao diện **Camera** (`frontend/views/camera.py`) tích hợp 2 tab:
  - **Xem Trực Tiếp (Live Stream):** Truyền trực tiếp hình ảnh (luồng MJPEG thời gian thực `http://<IP máy chủ>:8000/bridge/stream/{camera_id}`) cùng lớp vẽ vạch kẻ, khung nhận diện, HUD thông số tức thời. Cho phép xem nhanh cả 2 đầu cầu tập trung trên Web hoặc phóng to, lấy ảnh snapshot tức thời.
  - **Cấu Hình & Tình Trạng Thiết Bị:** Giám sát nhịp tim (tự cập nhật 5 giây/lần), trạng thái Online/Offline, FPS, nguồn hình, tình trạng vạch kẻ.
- Trên **máy đặt camera** (có thể khác máy chủ, cùng mạng), mở cửa sổ lệnh tại thư mục dự án:
```
python ai_engine/camera_bridge.py --camera-id 1 --source 0 --api http://<IP máy chủ>:8000
python ai_engine/camera_bridge.py --camera-id 2 --source 0 --api http://<IP máy chủ>:8000
```
- Mặc định camera **tự động phát live stream** lên máy chủ. Nếu muốn tắt stream để tiết kiệm băng thông mạng, thêm cờ `--no-stream`.
- Nhận diện giới tính / tuổi / nguồn khách **bật sẵn**. Thêm `--no-demographics` để chỉ đếm người. Lệnh cũ có `--demographics` vẫn chạy được.
- `--source` nhận số webcam (0, 1…), đường dẫn tệp video hoặc địa chỉ RTSP của camera IP.
- Trên cửa sổ camera: **L** (hoặc chuột phải) để kẻ lại vạch (click 2 đầu vạch rồi click 1 điểm ở phía cầu), **R** về vạch mặc định, **Q** để thoát.
- Chỉ camera 1 gửi mức cảnh báo Vàng / Đỏ. Khi mất tín hiệu, camera báo ngay về máy chủ và tự kết nối lại; người trực nhận tin nhắn để chuyển sang điều tiết thủ công.
- Kiểm tra kết nối từ máy camera: `python tools/kiem_tra_mang.py http://<IP máy chủ>:8000`.
- Thanh dưới cùng của cửa sổ camera ghi "Nhận diện: LỖI DeepFace" nếu không nạp được DeepFace; "Đang nhận diện…" dưới khung người nghĩa là đang chờ thấy rõ mặt.

## Ngưỡng & giờ hoạt động
- Sức chứa mặc định 20 người theo quy định năm 2019 (BRULE-01). Vàng từ 75% sức chứa, Đỏ khi vượt sức chứa liên tục 15 giây.
- Ngoài giờ hoạt động (BRULE-07) hệ thống không gửi tin nhắn cảnh báo Vàng và đoàn khách; cảnh báo Đỏ và mất tín hiệu camera vẫn luôn được gửi.

## Người nhận cảnh báo (Telegram)
Tạo bot (làm 1 lần, khoảng 3 phút):
1. Mở Telegram, tìm **@BotFather** (có dấu tích xanh) và bấm **Start**.
2. Gửi lệnh `/newbot`, đặt tên hiển thị (vd *SmartCau Chùa Cầu*), rồi đặt username kết thúc bằng `bot` (vd `smartcau_hoian_bot`).
3. BotFather trả về một token dạng `7012345678:AAH3k...`. Dán vào ô **Token của bot** trên trang rồi bấm **Kết nối**.

Thêm người nhận:
- Mỗi người nhận mở Telegram, tìm bot, bấm **Start** rồi gửi một tin bất kỳ. Muốn gửi vào nhóm trực: thêm bot vào nhóm và nhắn một tin trong nhóm. Sau đó bấm **Tìm người vừa nhắn cho bot**.

Tin nhắn được gửi khi có: cảnh báo Vàng, cảnh báo Đỏ (nhắc lại tối đa 1 lần mỗi 3 phút), đoàn khách lớn, mất tín hiệu camera, sự cố đóng, và báo cáo ngày (kèm tệp PDF) sau giờ đóng cửa. Kênh Zalo OA chưa hỗ trợ trong MVP: Zalo yêu cầu OA đã xác thực doanh nghiệp và mẫu tin ZNS có phí.

## Tài khoản (phân quyền FR-12)
- **Quản trị viên:** toàn quyền.
- **Quản lý:** xem vận hành, phân tích, báo cáo, camera, quyền riêng tư.
- **Người trực:** tổng quan, trực ca, bảng LED, lượt qua cầu, đối chiếu vé — không vào được trang cấu hình.
- Mật khẩu được lưu dạng băm (PBKDF2). Khóa tài khoản sẽ đăng xuất người đó ngay.

## Quyền riêng tư
- Số liệu tổng hợp và nhật ký sự cố phải giữ tối thiểu 24 tháng (BRULE-09), nên chỉ xóa được dữ liệu cũ hơn 730 ngày.
- Làm mờ khuôn mặt trên màn hình camera (NFR-05) đã được bỏ theo yêu cầu của nhóm; khung hình vẫn chỉ xử lý trong bộ nhớ.

## Google Sheets
Tạo khóa Google (làm 1 lần, khoảng 10 phút):
1. Vào **console.cloud.google.com**, đăng nhập bằng tài khoản Google của nhóm, bấm **Select a project → New project**, đặt tên (vd *SmartCau*) rồi **Create**.
2. Mở **APIs & Services → Library**, bấm **Enable** cho **Google Sheets API** và **Google Drive API**.
3. Vào **APIs & Services → Credentials → Create credentials → Service account**, đặt tên (vd *smartcau-sync*) → **Done**.
4. Bấm vào service account vừa tạo → thẻ **Keys → Add key → Create new key → JSON → Create**. Tệp `.json` tải về là **tệp khóa**.
5. Tạo một Google Sheet mới (sheets.new), bấm **Share** và chia sẻ quyền **Editor** cho email của service account (dạng `...@....iam.gserviceaccount.com`, hiện trên trang sau khi tải tệp khóa lên).
6. Dán đường link Google Sheet và tải tệp khóa trên trang, rồi bấm **Đồng bộ ngay**.

Tệp khóa được lưu ở thư mục `config/` trên máy chạy giao diện và không được đưa lên GitHub. Không gửi tệp này cho người ngoài nhóm.

## Tin nhắn Telegram và tự động hóa
Mọi tin cảnh báo có định dạng (in đậm, biểu tượng) và kèm **tình hình hiện tại**: số người / sức chứa (thanh màu), từng chân cầu, tốc độ vào / ra 5 phút qua, dự kiến bao lâu nữa đầy, thời gian chờ, lượt vào hôm nay, camera nào đang chạy, sự cố đang mở.

| Tin | Khi nào | Nút bấm |
|---|---|---|
| 🟡 Cảnh báo Vàng | Cầu sắp đầy (trong giờ mở cửa) | 📍 Tình hình · 📊 Hôm nay |
| 🔴 Cảnh báo Đỏ / ⏰ Nhắc lại | Quá tải liên tục 15 giây, nhắc lại tối đa mỗi 3 phút | **✅ Đã xử lý** · 📍 · 📊 |
| 🙋 Đã nhận xử lý | Có người bấm "Đã xử lý" (trên web hoặc Telegram) — báo cho cả nhóm để không ra trùng | 📍 · 📊 |
| ✅ Hết quá tải | Sự cố tự đóng / đóng tay: thời lượng, cao nhất, ai xử lý | 📍 · 📊 |
| 👥 Đoàn khách lớn · 📷 Mất / có lại tín hiệu camera | Theo sự kiện camera | 📍 · 📊 |
| ☀️ Bản tin đầu ngày | Trong 1 giờ đầu sau giờ mở cửa: lượt hôm qua, dự báo hôm nay, giờ cao điểm, camera nào chưa bật | 📍 · 📊 |
| 🎟 Nhắc nhập số cuống vé | 30 phút trước giờ đóng cửa nếu hôm nay chưa nhập | — |
| 📋 Báo cáo ngày + PDF | Sau giờ đóng cửa; nhắc nếu thiếu số cuống vé | — |

Lệnh gõ cho bot (chỉ người có trong danh sách nhận cảnh báo; người lạ nhận lại chat_id của họ để gửi quản trị viên):
`/tinhhinh` tình hình ngay lúc này · `/homnay` tổng kết hôm nay + dự báo · `/suco` sự cố đang mở · `/help`.

Muốn tin nhắn có nút **🖥 Mở trang quản lý**: đặt biến môi trường `SMARTCAU_WEB_URL=http://<IP máy chủ>:8501` trước khi chạy backend.
Bot đọc tin nhắn bằng luồng nền của backend; tắt bằng `SMARTCAU_DISABLE_BOT=1`.

## Đối chiếu vé — nhập liệu
- Chọn **Cả ngày** hoặc **Từng giờ**; khung giờ chỉ hiện khi chọn Từng giờ, liệt kê theo giờ mở cửa và cho biết khung nào đã nhập.
- **Tải mẫu Excel / CSV**: tệp đã có sẵn ngày đang chọn và các khung giờ, chỉ cần điền cột `ticket_count` rồi tải lên. Dòng để trống bị bỏ qua.

## Chọn loại tin cho từng người nhận
Trang **Người nhận cảnh báo** → mỗi người có ô chọn loại tin và **mẫu nhanh**:

| Mẫu | Loại tin nhận |
|---|---|
| Người trực | Đỏ & sự cố, Vàng, đoàn khách, camera, bản tin đầu ngày, nhắc nhập vé |
| Quản lý | Đỏ & sự cố, báo cáo ngày, báo cáo tuần |
| Tất cả | mọi loại (kể cả kết quả đồng bộ Google Sheets) |

Người nhận cũ chưa chọn gì thì vẫn nhận tất cả. Lệnh bot (`/tinhhinh`...) và nút "Đã xử lý" không phụ thuộc loại tin.

## Báo cáo tuần
- Tự gửi **sáng thứ Hai** (từ giờ mở cửa) cho người chọn "Báo cáo tuần": tuần Thứ Hai – Chủ nhật vừa qua so với tuần trước nữa (tổng lượt, % tăng giảm, trung bình/ngày, ngày đông nhất và vắng nhất, biểu đồ cột 7 ngày, giờ cao điểm, sự cố, KPI, cơ cấu khách), kèm **PDF**.
- Trang **Báo cáo định kỳ** → mục *Báo cáo tuần*: tải PDF hoặc bấm **Gửi báo cáo tuần ngay**.

## Tự đồng bộ Google Sheets
- Sau khi lập báo cáo ngày (sau giờ đóng cửa), backend tự đồng bộ sang Google Sheet đã cấu hình. Bật / tắt bằng công tắc ở trang **Google Sheets**.
- Kết quả ghi vào cột trạng thái của báo cáo ngày và gửi cho người chọn loại tin "Đồng bộ Google Sheets".
- Backend cần cài `gspread google-auth` và đọc cùng thư mục `config/` với giao diện web (chạy cả hai trên máy chủ). Nếu backend không chạy ở cổng 8000, đặt `SMARTCAU_SELF_URL=http://127.0.0.1:<cổng>`.

## Camera bớt lag
- Webcam / RTSP được đọc ở luồng riêng và **luôn xử lý khung hình mới nhất** → hình không còn trễ vài giây khi AI chạy chậm.
- **DeepFace chạy nền**: nhận diện giới tính / tuổi không còn làm đứng hình mỗi lần phân tích.
- Chữ tiếng Việt vẽ theo từng ô nhỏ thay vì cả khung hình; khung 1080p tự thu về 1280 px (`--max-width`, 0 = giữ nguyên).
- Thanh dưới cùng hiện thời gian AI mỗi khung (`AI xx ms/khung`). Máy yếu: thêm `--imgsz 480` (nhanh hơn, vẫn đếm tốt khi người ở gần), hoặc `--no-origin` để bỏ ước lượng nguồn khách.
