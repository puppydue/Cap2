# SmartCau AI — Tài liệu tổng thể mã nguồn

> **Dành cho người và cho AI.** Khi cần sửa lỗi hay thêm tính năng, gửi cho AI (ChatGPT, Claude, Gemini…):
> 1. **Toàn bộ tệp này**,
> 2. **Nguyên văn lỗi** (ảnh chụp màn hình, dòng báo lỗi trong cửa sổ lệnh, hoặc mô tả "bấm X thì thấy Y"),
> 3. **Các tệp code** mà mục "Tra cứu nhanh: lỗi ở đâu" (phần 9) chỉ tới.
>
> Mẫu câu gửi AI:
> ```
> Đây là tài liệu dự án SmartCau AI (đính kèm TONG_QUAN_MA_NGUON.md).
> Lỗi: <dán nguyên văn>. Lúc đó tôi đang: <chạy lệnh gì / bấm trang nào>.
> Theo tài liệu, lỗi này liên quan tệp <...>; nội dung tệp đó như sau: <dán tệp>.
> Hãy chỉ ra nguyên nhân và đưa đoạn code sửa, giữ nguyên quy ước của dự án (mục 10).
> ```

Phiên bản tài liệu: sau PR #9 (11/2026). Tài liệu khác trong `docs/`: `GHI_CHU_GIAO_DIEN.md` (hướng dẫn và mã yêu cầu đã gỡ khỏi web), `TRIEN_KHAI_NHIEU_MAY.md` (chạy nhiều máy), `CAMERA_NGOAI.md` (webcam USB, điện thoại làm camera), `AI_CAI_THIEN.md` (độ chính xác AI), `API_CONTRACT.md`, `PHAN_CONG.md`.

Các thay đổi lớn theo thời gian: PR #4–#5 (7 module, LED Linh Thân, nhiều máy) · #6 (LED hai đầu cầu, nhận diện bật sẵn, dọn web) · #7 (Telegram 2 chiều, tự động hóa, loại tin, camera bớt lag) · #8 (PDF hành chính có logo chìm + biểu đồ, kỳ năm / tùy chọn, đối chiếu vé theo ngày, AI Nam/Nữ cắt mặt theo keypoint) · #9 (webcam USB / điện thoại làm camera).

---

## Mục lục
1. Dự án làm gì
2. Kiến trúc và luồng dữ liệu
3. Cách chạy, cổng, biến môi trường, tệp cấu hình
4. Cây thư mục và vai trò từng tệp
5. Danh sách chức năng (chi tiết, kèm tệp liên quan)
6. Chi tiết từng tệp code
7. Danh sách API (endpoint → tệp → quyền → ai gọi)
8. Cơ sở dữ liệu (bảng → cột → tệp định nghĩa)
9. Tra cứu nhanh: lỗi ở đâu, sửa tệp nào
10. Quy ước code và những điều không được phá
11. Kiểm thử

---

## 1. Dự án làm gì

**SmartCau AI** (Nhóm 50, Đại học Kinh tế Đà Nẵng) là hệ thống camera AI quản lý lượng khách trên **Chùa Cầu (Hội An)**:

- **2 camera đặt ở 2 chân cầu** đếm người qua một vạch kẻ: đi vào cầu / đi ra khỏi cầu. Từ đó biết **số người đang trên cầu** (`onbridge`) và **tổng lượt vào trong ngày** (`dem`).
- **Cảnh báo quá tải**: Vàng khi từ 75% sức chứa (mặc định 15/20 người); Đỏ khi vượt sức chứa (trên 20 người) liên tục 15 giây. Hết Đỏ khi số người ≤ ngưỡng Vàng liên tục 15 giây. Tin Đỏ nhắc lại tối đa 1 lần mỗi 3 phút.
- **Ước lượng nhân khẩu học** khi khách vào cầu: Nam/Nữ, nhóm tuổi, nguồn khách "Trong nước/châu Á" hoặc "Quốc tế" (mặc định dùng mô hình nhẹ, chính xác cao **InsightFace buffalo_s** qua ONNX Runtime, có DeepFace dự phòng). Không lưu ảnh khuôn mặt.
- **Web quản lý** (Streamlit) theo vai trò: người trực, quản lý, quản trị viên.
- **Bảng LED 2 đầu cầu** (trang HTML) với 2 mascot **Linh Thân** (khỉ) và **Linh Khuyển** (chó), phông nền động, câu thoại theo mức cảnh báo.
- **Telegram**: tin cảnh báo kèm tình hình hiện tại, bot nhận lệnh, nút "Đã xử lý", báo cáo ngày / tuần tự động kèm PDF.
- **Báo cáo, KPI, đối chiếu vé, Google Sheets**.

Thuật ngữ:

| Từ | Nghĩa |
|---|---|
| `num1`, `num2` | Số người đang trên cầu tính theo từng camera (chân cầu 1, 2). Vào: +1, ra: −1 |
| `onbridge` | `num1 + num2` = số người đang trên cầu |
| `dem` | Tổng lượt vào cầu trong ngày, về 0 lúc 0 giờ |
| Mức `OK` / `WARNING` / `ALERT` / `CRITICAL` | Bình thường / Vàng / Vàng đang chờ xác nhận 15 giây / Đỏ |
| Sự cố (incident) | Một lần cảnh báo Đỏ, từ lúc vào Đỏ đến lúc hết quá tải |
| Lượt mặt tiền (facade) | Người đi ngang phía ngoài vạch, không lên cầu |
| Đoàn khách | Từ 10 người trở lên cùng đi về phía cầu trong 10 giây |
| `Trong nuoc` / `Nuoc ngoai` | Mã lưu trong CSDL; hiển thị là "Trong nước/châu Á" / "Quốc tế" |
| `Man` / `Woman` | Mã giới tính lưu CSDL; hiển thị "Nam" / "Nữ" |
| KPI O1, O4, O5, O8 | Phút vượt sức chứa; % sự cố xử lý trong 3 phút; % báo sai; % chênh lệch vé |

---

## 2. Kiến trúc và luồng dữ liệu

```
 MÁY CAMERA (1 hoặc 2)                MÁY CHỦ                                   NGƯỜI DÙNG
 ┌──────────────────────┐   HTTP     ┌──────────────────────────────────┐
 │ ai_engine/           │ ─────────► │ backend/ (FastAPI, cổng 8000)    │ ◄── Web quản lý: frontend/ (Streamlit, cổng 8501)
 │  camera_bridge.py    │  X-API-Key │  - routers/*.py  (API)           │ ◄── Bảng LED: http://IP:8000/led/?dau=1|2
 │  YOLO pose + tracker │ ◄───────── │  - SQLite backend/smartcau.db    │
 │  DeepFace (nền)      │  /bridge/  │  - luồng nền: báo cáo ngày/tuần, │ ──► Telegram (bot + tin cảnh báo + PDF)
 │  vạch kẻ, HUD        │   state    │    bản tin sáng, nhắc vé, Sheets │ ──► Google Sheets (tự đồng bộ)
 └──────────────────────┘            │  - luồng nền: bot Telegram       │
                                     └──────────────────────────────────┘
```

**Luồng một khách đi vào cầu:**
1. `camera_bridge.py` đọc khung hình (`LatestFrameReader`, luồng riêng) → YOLO `model.track()` ra khung người + ID.
2. Điểm chân (`foot_point`) đi qua vạch (`LineCrossingCounter.update`) từ phía ngoài vào phía cầu → sự kiện `"in"`.
3. Camera gửi `POST /bridge/crossing {camera_id, direction:"in"}` qua hàng đợi nền (`Net.post`).
4. `backend/routers/bridge.py::record_crossing`: `num_k += 1`, `dem += 1`, `onbridge = num1 + num2`; nếu `onbridge <= 0` thì đặt `num1 = num2 = 0`; ghi `BridgeCrossing`; cập nhật `OccupancyState.current_count`.
5. Camera đọc lại `/bridge/state` mỗi giây (`Net._poller`) → hiện "Trên cầu: x/20".
6. Camera 1 chạy `AlertLevelTracker` (crowd_counter.py) → mỗi 2 giây `POST /occupancy {count, status}`; khi cần thì `POST /system_events` (WARNING / CRITICAL_ALERT / CRITICAL_CLEARED).
7. `backend/routers/alerts.py::create_system_event` mở / cập nhật / đóng sự cố, dựng tin nhắn đẹp (`backend/messages.py`) và gửi Telegram (`backend/notify.py`) cho người nhận đã chọn loại tin đó.
8. Song song, `VisitorProfiler` (visitor_profiler.py) đưa ảnh vào DeepFace ở luồng nền (`AsyncEngine`); khi đủ tin cậy và khách đã vào cầu → `POST /visit_events` (giới tính, tuổi, nguồn khách).
9. Web (`frontend/views/*.py`) và bảng LED (`backend/led_display/led.js` gọi `/display/state` mỗi giây) đọc lại từ backend.

**Chỉ máy chủ có CSDL.** Camera và trình duyệt chỉ gửi / đọc qua API.

---

## 3. Cách chạy, cổng, biến môi trường, tệp cấu hình

Chạy từ **thư mục gốc dự án** (có `backend/`, `frontend/`, `ai_engine/`), trong môi trường ảo `.venv`.

| Thành phần | Lệnh | Cổng |
|---|---|---|
| Backend (API + CSDL + bảng LED + luồng nền + bot) | `uvicorn backend.main:app --host 0.0.0.0 --port 8000` | 8000 |
| Web quản lý | `streamlit run frontend/app.py --server.address 0.0.0.0` | 8501 |
| Camera chân cầu 1 (gửi mức cảnh báo) | `python ai_engine/camera_bridge.py --camera-id 1 --source 0 --api http://<IP>:8000` | — |
| Camera chân cầu 2 | `python ai_engine/camera_bridge.py --camera-id 2 --source 0 --api http://<IP>:8000` | — |
| Kiểm tra mạng nhiều máy | `python tools/kiem_tra_mang.py` (máy chủ) / `python tools/kiem_tra_mang.py http://<IP>:8000` (máy khác) | — |
| Giả lập khách qua cầu (không cần camera) | `python tools/simulate_bridge.py` | — |
| Kiểm thử | `pytest -q` | — |

Đăng nhập lần đầu: `admin` / `admin123` (bắt đổi mật khẩu).

**Cờ dòng lệnh của camera** (`ai_engine/camera_bridge.py::parse_args`):

| Cờ | Mặc định | Ý nghĩa |
|---|---|---|
| `--camera-id 1\|2` | bắt buộc | Chân cầu. Chỉ camera 1 gửi mức cảnh báo |
| `--source` | `0` | Webcam `0` (laptop) / `1`, `2` (USB); điện thoại `phone:<IP>` (IP Webcam), `droidcam:<IP>`; `http://...`, `rtsp://...`; tệp video. Xử lý ở `camera_backend.resolve_source`. Hướng dẫn: `docs/CAMERA_NGOAI.md` |
| `--cam-res` | `1280x720` | Độ phân giải xin webcam USB |
| `--api` | `SMARTCAU_API` hoặc `http://127.0.0.1:8000` | Địa chỉ máy chủ |
| `--api-key` | — | Khóa camera nếu máy chủ đặt `SMARTCAU_API_KEY` |
| `--no-demographics` | tắt | Tắt nhận diện giới tính / tuổi / nguồn khách (mặc định **bật**). `--demographics` vẫn được nhận (không làm gì) |
| `--no-origin` | tắt | Bỏ ước lượng nguồn khách |
| `--no-alerts` | tắt | Camera 1 không gửi mức cảnh báo |
| `--group-size` | 10 | Số người tối thiểu của một đoàn |
| `--model` | `yolov8n-pose.pt` (hoặc `yolov8n.pt` khi tắt nhận diện) | Model YOLO |
| `--imgsz` | 640 | Kích thước ảnh vào YOLO (480 nhanh hơn, 960 đếm xa tốt hơn) |
| `--max-width` | 1280 | Thu nhỏ khung hình rộng hơn mức này; 0 = giữ nguyên |
| `--conf` | 0.35 | Ngưỡng tin cậy phát hiện người |
| `--tracker` | `ai_engine/trackers/smartcau_botsort.yaml` | Cấu hình bộ theo dõi |
| `--face-detector` | `yunet` | Bộ tìm mặt của DeepFace (`retinaface`, `mtcnn`, `opencv`...) |
| `--no-face-gate` | tắt | Tắt cổng chất lượng mặt |

Phím trên cửa sổ camera: **L** / **l** / **1** / **K** hoặc **chuột phải** = kẻ lại vạch (click 2 đầu vạch rồi 1 điểm phía cầu); **R** = vạch mặc định; **Q** / **Esc** = thoát.

**Biến môi trường:**

| Biến | Dùng ở | Ý nghĩa |
|---|---|---|
| `SMARTCAU_DATABASE_URL` | backend/database.py | Chuỗi kết nối CSDL (mặc định SQLite `backend/smartcau.db`) |
| `SMARTCAU_UTC_OFFSET_HOURS` | backend/timeutil.py | Múi giờ (mặc định 7) |
| `SMARTCAU_API_KEY` | backend/security.py, camera, tools | Khóa camera gửi số liệu (rỗng = không cần) |
| `ADMIN_API_KEY` | backend/security.py | Khóa quản trị qua header `X-Admin-Key` (cho script) |
| `SMARTCAU_API` | frontend/common.py, ai_engine, tools | Địa chỉ backend mà web / camera gọi |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | backend/notify.py, ai_engine/telegram_alert.py | Token bot (ưu tiên hơn token lưu trong CSDL); chat dự phòng khi chưa có người nhận |
| `SMARTCAU_WEB_URL` | backend/notify.py | Thêm nút "🖥 Mở trang quản lý" vào tin Telegram |
| `SMARTCAU_SELF_URL` | backend/sheets_auto.py | Backend tự gọi API của chính nó khi đồng bộ Sheets (mặc định `http://127.0.0.1:8000`) |
| `SMARTCAU_DISABLE_SCHEDULER` | backend/daily_report.py, telegram_bot.py | `1` = tắt luồng nền (dùng khi chạy test) |
| `SMARTCAU_DISABLE_BOT` | backend/telegram_bot.py | `1` = tắt bot Telegram |
| `GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_CREDENTIALS_FILE` | sheets_auto.py, dong_bo_sheets.py, tools/google_sheets_sync.py | Ưu tiên hơn cấu hình trong `config/` |
| `SMARTCAU_FONT`, `SMARTCAU_FONT_BOLD` | backend/report_export.py, ai_engine/camera_ui.py | Đường dẫn font .ttf tiếng Việt (thường / đậm) cho PDF và chữ trên camera |
| `SMARTCAU_ORG_PARENT`, `SMARTCAU_ORG_NAME`, `SMARTCAU_ORG_PLACE` | backend/report_export.py | Tên cơ quan chủ quản, đơn vị lập báo cáo, địa danh trên PDF (mặc định: Trung tâm QLBT DSVH Hội An / Bộ phận vận hành hệ thống SmartCau AI / Hội An) |
| `SMARTCAU_FACE_DETECTOR` | ai_engine/age_gender_estimator.py, camera_bridge.py | Bộ tìm mặt mặc định |
| `SMARTCAU_BUZZER_WEBHOOK` | ai_engine/telegram_alert.py | URL gọi khi Đỏ (còi / đèn ngoài, tùy chọn) |
| `SMARTCAU_ENABLE_REGION`, `SMARTCAU_SOLO_DEMO` | ai_engine/camera_in.py (cũ) | Chỉ cho camera cũ |

**Tệp cấu hình sinh ra khi chạy (không đưa lên GitHub, có trong `.gitignore`):**

| Tệp | Tạo bởi | Nội dung |
|---|---|---|
| `backend/smartcau.db` | backend | Toàn bộ dữ liệu |
| `ai_engine/config/line_cam1.json`, `line_cam2.json` | camera khi kẻ vạch | Tọa độ vạch (chuẩn hóa 0–1) và điểm phía cầu |
| `config/google_sheets.json` | trang Google Sheets | `{"sheet_id": "...", "auto": true}` |
| `config/google_service_account.json` | trang Google Sheets | Tệp khóa service account |
| `ai_engine/calibration/age_calibration.json` | `tools/eval_demographics.py --save-calibration` | Hệ số hiệu chỉnh tuổi `a*x+b` |

Giao diện: `.streamlit/config.toml` (màu chủ đạo `#7D2318`, nền `#F5F0E6`, thanh bên tối `#1E1814`).

---

## 4. Cây thư mục và vai trò từng tệp

```
Cap2/
├── backend/                      MÁY CHỦ (FastAPI)
│   ├── main.py                   tạo app, gắn router, mount /led, khởi động luồng nền, /health
│   ├── database.py               engine SQLAlchemy, get_db, ensure_schema (tự thêm cột mới)
│   ├── models.py                 bảng dùng chung: VisitEvent, OccupancySnapshot, OccupancyState, SystemEvent,
│   │                             RegionStat, SystemConfig, User, AuthToken, AuditLog; get_state, get_config, log_audit
│   ├── schemas.py                Pydantic đầu vào: VisitEventIn, OccupancyIn, SystemEventIn, RegionStatIn
│   ├── security.py               khóa camera, mật khẩu băm, phiên đăng nhập, phân quyền
│   ├── timeutil.py               giờ Việt Nam ↔ UTC
│   ├── notify.py                 gọi Telegram Bot API: gửi tin HTML, nút bấm, gửi tệp PDF
│   ├── messages.py               nội dung mọi tin Telegram (cảnh báo, tình hình, hôm nay, sáng, báo cáo ngày/tuần)
│   ├── telegram_bot.py           bot 2 chiều: lệnh /tinhhinh /homnay /suco /help, nút "Đã xử lý"
│   ├── daily_report.py           lịch tự động: báo cáo ngày, bản tin sáng, nhắc nhập vé, báo cáo tuần
│   ├── sheets_auto.py            tự đồng bộ Google Sheets sau báo cáo ngày
│   ├── report_export.py          bảng báo cáo, xuất Excel và PDF (font tiếng Việt)
│   ├── routers/
│   │   ├── accounts.py           M2: đăng nhập / đăng xuất / đổi mật khẩu / tài khoản / nhật ký
│   │   ├── bridge.py             M1: đếm qua vạch 2 camera (num1, num2, dem), nhịp tim camera, thống kê
│   │   ├── counting.py           M1: số người hiện tại, lịch sử mức cảnh báo, lượt mặt tiền
│   │   ├── alerts.py             M3: sự kiện camera → sự cố Đỏ, xác nhận, đóng, báo sai, gửi Telegram
│   │   ├── demographics.py       M1/M4: hồ sơ khách (giới tính, tuổi, nguồn khách), tổng hợp
│   │   ├── tickets.py            M5: số cuống vé, đối chiếu với lượt vào
│   │   ├── reports.py            M4: báo cáo ngày/tuần/tháng, KPI, biểu đồ nhiệt, PDF ngày/tuần
│   │   ├── insights.py           xu hướng 5 phút, dự báo, thời gian chờ, câu nhận định tự động
│   │   ├── admin.py              M7: ngưỡng & giờ mở cửa, người nhận + loại tin, quyền riêng tư, Telegram
│   │   └── display.py            dữ liệu cho bảng LED
│   └── led_display/              BẢNG LED (HTML/JS tĩnh, phục vụ ở /led/)
│       ├── index.html            khung trang LED
│       ├── led.js                toàn bộ logic LED (CONFIG, mascot, phông nền, câu thoại, debug)
│       ├── led.css               giao diện LED
│       ├── hai-man-hinh.html     xem song song 2 màn hình đầu cầu
│       └── media/                video đã xử lý: than_*.webm, khuyen_*.webm (nền trong suốt), scene1–4 (.webm/.mp4)
├── frontend/                     WEB QUẢN LÝ (Streamlit)
│   ├── app.py                    đăng nhập, menu theo vai trò, thanh bên, theo dõi sự cố
│   ├── common.py                 giao diện chung (CSS Hội An), gọi API, phiên đăng nhập, định dạng, sơ đồ cầu
│   ├── assets/logo.svg           logo
│   └── views/                    mỗi tệp = 1 trang (xem mục 5)
├── ai_engine/                    CAMERA + AI
│   ├── camera_bridge.py          ★ chương trình camera chân cầu (dùng chính)
│   ├── camera_backend.py         mở webcam đúng hệ điều hành; LatestFrameReader (đọc khung mới nhất)
│   ├── camera_ui.py              vẽ khung người, chữ tiếng Việt (TextLayer), ô thông tin
│   ├── line_crossing.py          vạch kẻ: LineCrossingCounter, foot_point, FacadeCounter (lượt mặt tiền)
│   ├── crowd_counter.py          ngưỡng (CameraThresholds), AlertLevelTracker (Vàng/Đỏ có thời gian), CrowdCounter (cũ)
│   ├── group_detector.py         phát hiện đoàn khách
│   ├── visitor_profiler.py       cổng chất lượng mặt, AsyncEngine (DeepFace nền), VisitorProfiler (hồ sơ khách)
│   ├── demographics_engine.py    bỏ phiếu theo thời gian cho giới tính / tuổi / khu vực
│   ├── age_gender_estimator.py   gọi DeepFace, lọc kết quả giả, hiệu chỉnh tuổi
│   ├── region_mapping.py         nhóm chủng tộc DeepFace → nhóm khu vực
│   ├── telegram_alert.py         trigger_buzzer_signal (còi ngoài) + gửi Telegram kiểu cũ
│   ├── trackers/smartcau_botsort.yaml  cấu hình BoT-SORT tích hợp ReID chống nhảy ID (with_reid: true, model: auto, track_buffer: 90)
│   ├── camera_in.py, camera_out.py     camera kiểu CŨ (1 camera vào, 1 camera ra) — không dùng nữa, giữ tham khảo
├── tools/                        CÔNG CỤ
│   ├── kiem_tra_mang.py          kiểm tra kết nối nhiều máy
│   ├── simulate_bridge.py        giả lập khách qua 2 chân cầu
│   ├── seed_demo_data.py         tạo dữ liệu demo qua API
│   ├── google_sheets_sync.py     đồng bộ sang Google Sheets (dùng bởi web và sheets_auto)
│   ├── eval_counting.py          đo độ chính xác đếm (NFR-02)
│   ├── eval_demographics.py      đo độ chính xác giới tính / tuổi (FR-09, NFR-08), học hệ số tuổi
│   ├── data_simulator.py, generate_dashboard.py, demo_run.py   bản demo cũ (dashboard HTML tĩnh)
├── tests/                        pytest (mục 11)
├── media/                        TỆP GỐC nhóm gửi: mascot/linh_than, mascot/linh_khuyen, phong_nen, tai_lieu (BRD, BFD, BPMN, Sprint0)
├── docs/                         tài liệu
├── legacy_demos/                 demo đầu tiên (không dùng)
├── sample_data/                  dữ liệu mẫu CSV, ảnh thử
├── requirements.txt, pytest.ini, .streamlit/config.toml, yolov8n.pt, yolov8n-pose.pt
```

---

## 5. Danh sách chức năng (chi tiết, kèm tệp liên quan)

Mỗi chức năng ghi: **làm gì → quy tắc → tệp code → API → bảng CSDL → test**.

### 5.1 Đếm người qua vạch bằng 2 camera (M1)
- **Làm gì:** mỗi chân cầu 1 camera; khách bước qua vạch từ ngoài vào là "vào", ngược lại là "ra".
- **Quy tắc:** vào → `num_k += 1`, `dem += 1`; ra → `num_k −= 1`; `onbridge = num1 + num2`; nếu `onbridge <= 0` → `num1 = num2 = 0` (chống âm do camera bỏ sót); sang ngày mới `dem = 0` (`_roll_day`). Có khóa `_LOCK` để 2 camera gửi cùng lúc không lệch số.
- **Nhận diện vào / ra:** điểm chân = giữa cạnh dưới khung người (`foot_point`); dấu khoảng cách tới vạch đổi từ âm sang dương = vào (`LineCrossingCounter.update`, có chống rung).
- **Tệp:** `ai_engine/camera_bridge.py` (vòng lặp chính, gửi `/bridge/crossing`, cập nhật số tạm thời trên màn hình), `ai_engine/line_crossing.py`, `backend/routers/bridge.py::record_crossing`, `_roll_day`, `_state_json`.
- **API:** `POST /bridge/crossing`, `GET /bridge/state`, `POST /bridge/reset` (quản lý), `GET /bridge/stats`.
- **CSDL:** `bridge_state` (1 dòng, id=1), `bridge_crossings`, `occupancy_state.current_count`.
- **Web:** trang **Lượt qua cầu** (`frontend/views/luot_qua_cau.py`).
- **Test:** `tests/test_api.py::test_bridge_counting_rules`, `test_bridge_validation`, `test_bridge_dem_resets_on_new_day`, `test_bridge_stats_grouping`; `tests/test_line_crossing.py`.

### 5.2 Kẻ vạch trên camera
- **Làm gì:** người dùng vẽ vạch bằng chuột trên cửa sổ camera; lưu lại cho lần sau.
- **Tệp:** `ai_engine/camera_bridge.py::draw_line_setup`, `load_line`, `_line_path`, `draw_line_overlay` (vẽ vạch + mũi tên "VÀO CẦU"); `ai_engine/line_crossing.py::LineCrossingCounter.save/load/to_dict`. Lưu ở `ai_engine/config/line_cam<id>.json`.
- **Phím:** xem mục 3. Vạch mặc định: ngang giữa hình, phía cầu = nửa dưới.

### 5.3 Thống kê lượt qua cầu theo giờ / ngày / tháng / năm
- **Tệp:** `backend/routers/bridge.py::bridge_stats` (gom theo `local_time` bằng `_GROUP_FORMAT`), `frontend/views/luot_qua_cau.py` (biểu đồ, bấm cột để xem chi tiết).
- **API:** `GET /bridge/stats?group=hour|day|month|year&date_from=&date_to=`.

### 5.4 Cảnh báo Vàng / Đỏ (M3, FR-04, FR-06)
- **Quy tắc** (`ai_engine/crowd_counter.py`):
  - `CameraThresholds`: `alert` = sức chứa (mặc định 20), `warning = round(alert*0.75)` (15), `red_hold_sec = clear_hold_sec = 15`.
  - `AlertLevelTracker.update(count, now)`: vào Đỏ khi `count > alert` liên tục 15 giây; giữ Đỏ đến khi `count <= warning` liên tục 15 giây. Trả `OK/WARNING/ALERT/CRITICAL`.
  - `pop_notification`: Vàng gửi khi chuyển từ OK lên; Đỏ gửi ngay khi vào, nhắc lại mỗi 180 giây; mỗi loại không lặp trong 3 phút.
- **Chỉ camera 1** tính mức và gửi `POST /occupancy` (mỗi 2 giây) và `POST /system_events` (`WARNING`, `CRITICAL_ALERT`, `CRITICAL_CLEARED`). Ngưỡng đọc từ `/config` mỗi 15 giây (`Net._poller`).
- **Gửi tin:** `backend/routers/alerts.py::create_system_event`. Tin Vàng, đoàn khách, camera có lại chỉ gửi **trong giờ mở cửa** (`NOTIFY_IN_HOURS`, `admin.is_open_now`); Đỏ và mất camera gửi **mọi lúc** (`ALWAYS_NOTIFY`).
- **Tệp liên quan:** `ai_engine/camera_bridge.py` (phần `tracker.update`, `pop_notification`, `trigger_buzzer_signal`), `ai_engine/telegram_alert.py::trigger_buzzer_signal` (còi ngoài), `backend/routers/alerts.py`, `backend/messages.py::event_message`, `backend/notify.py`.
- **Test:** `tests/test_crowd_counter.py`, `tests/test_api.py::test_incident_lifecycle`, `test_rich_telegram_messages_include_live_status`.

### 5.5 Sự cố quá tải: mở, xác nhận, đóng, báo sai (M3 · F2.4)
- **Vòng đời** (`backend/routers/alerts.py`): `CRITICAL_ALERT` lần đầu → tạo `Incident`; lần sau → `alert_count += 1`, cập nhật `peak_count`. `CRITICAL_CLEARED` → tự đóng (`_close`, `close_reason="auto"`). Người trực bấm **Đã xử lý** → `acknowledge()` ghi `acked_at/acked_by` và báo cho cả nhóm ("🙋 X đã nhận xử lý"). **Đóng tay** → `close_incident`. **Báo sai** → `mark_false_alarm` (tính KPI O5).
- **Xác nhận từ Telegram:** nút `ack:<id>` → `backend/telegram_bot.py::handle_update` → `alerts.acknowledge(via="telegram")`.
- **Web:** **Trực ca & sự cố** (`frontend/views/truc_ca.py`): sự cố đang mở, nút Đã xử lý / Báo sai / Đóng, KPI xử lý trong 3 phút và báo sai, nhật ký sự kiện. Thanh bên mọi trang: `common.alert_watcher` hiện thông báo nổi khi có sự cố mới.
- **API:** `GET /incidents`, `POST /incidents/{id}/ack`, `/close`, `/false_alarm`, `GET /system_events`.
- **CSDL:** `incidents`, `system_events`.

### 5.6 Nhận diện giới tính, tuổi, nguồn khách (M1 · F3.2)
- **Luồng:** `VisitorProfiler.observe` (mỗi 0,3 giây / người; đã chốt kết quả thì 1,5 giây) → `face_quality` (mắt đủ to ≥18 px, nhìn thẳng, không nhòe ≥45) → `AsyncEngine.update` (đẩy việc sang luồng nền `deepface`, đo `avg_ms`) → `DemographicsEngine.update`:
  - **Đường nhanh (mặc định với model pose):**
    - Nếu dùng **InsightFace** (mặc định): `age_gender_estimator.align_face_for_insightface` cắt & xoay khuôn mặt chuẩn 96×96 (trường nhìn rộng hơn với `eye_span=0.26`, `eye_y=0.40`) → `_predict_genderage_insightface` suy luận qua ONNX Runtime (~4 ms/mặt, độ chính xác cao cho người Châu Á).
    - Nếu dùng **DeepFace**: `align_face_from_keypoints` cắt 224×224 → `estimate_from_aligned_face` gọi DeepFace `skip`.
    - Cả 2 đều hỗ trợ TTA (lật gương lấy trung bình khi độ tin cậy < 85%).
  - **Đường dự phòng** (model không có keypoint): `estimate_demographics_from_person_box` (DeepFace tự tìm mặt trong khung người).
  - `TemporalVoter` bỏ phiếu nhiều khung (≥4 phiếu, tỷ lệ ≥75%, cửa sổ 8 phiếu gần nhất). **Trọng số phiếu = (độ chắc − 50%) / 50%**: phiếu 55% gần như không tính, phiếu 99% tính gần đủ.
  - Ước lượng chủng tộc (`race`, cho nguồn khách) chỉ chạy tới khi đủ `RACE_VOTES = 4` lần cho mỗi người, sau đó chỉ chạy tuổi + giới tính → nhanh hơn.
  - HUD hiện `mặt xx ms` = thời gian trung bình một lần phân tích mặt.
- **Nguồn khách:** DeepFace `race` → `region_mapping.classify_region_from_deepface_race` → `REGION_TO_ORIGIN` ("Dong A / Noi dia" → `Trong nuoc`, còn lại → `Nuoc ngoai`); phải chiếm ≥55% phiếu (`ORIGIN_MIN_SHARE`).
- **Lưu:** khi khách **đã qua vạch vào** và kết quả sẵn sàng → `POST /visit_events`. Sau 5 giây vào cầu mà chưa ra kết quả → lưu "Không xác định" (`_save_unknown`). Khách đi **ra** mà chưa vào → không lưu.
- **Hiển thị trên camera** (`VisitorProfiler.label`): "VÀO CẦU · ID n", "Nữ · 25-34", "Trong nước/châu Á"/"Quốc tế"; hoặc "Đang nhận diện…", "Lại gần camera hơn", "Chờ nhìn thẳng", "Hình bị nhòe".
- **Hiệu chỉnh tuổi:** `age_gender_estimator.calibrate_age` đọc `ai_engine/calibration/age_calibration.json`.
- **DeepFace lỗi:** `_load_deepface` in lỗi gốc 1 lần; camera vẫn đếm, thanh dưới ghi "Nhận diện: LỖI DeepFace".
- **Web:** **Cơ cấu khách** (`co_cau_khach.py`), **Lịch sử lượt khách** (`lich_su.py`).
- **API:** `POST /visit_events`, `GET /visit_events`, `GET /stats/demographics`.
- **CSDL:** `visit_events`.
- **Test:** `tests/test_visitor_profiler.py`, `test_api.py::test_demographics_excludes_unknown`.

### 5.7 Lượt qua mặt tiền và đoàn khách (F1.4, F3.1)
- **Mặt tiền:** người ở phía ngoài vạch ≥1 giây rồi biến mất mà không qua vạch → 1 lượt (`line_crossing.FacadeCounter`). Gửi `POST /facade_pass`.
- **Đoàn khách:** `group_detector.GroupDetector.update`: cụm ≥10 người đang tiến về phía cầu, giữ trong 10 giây → `POST /system_events GROUP_DETECTED`.
- **Tệp:** `ai_engine/line_crossing.py`, `ai_engine/group_detector.py`, `ai_engine/camera_bridge.py`, `backend/routers/counting.py::facade_pass, facade_stats`.
- **Test:** `tests/test_group_facade.py`.

### 5.8 Camera: Live Stream trực tiếp, chống nhảy ID (ReID), nhịp tim và mất tín hiệu (NFR-03)
- **Live Stream trực tiếp tập trung (F1.5):**
  - Camera `camera_bridge.py` tự động nén khung hình đã vẽ vạch kẻ và HUD sang định dạng JPEG (chất lượng 65, chiều rộng tối đa 960px để tối ưu băng thông) và đưa vào hàng đợi luồng gửi nền `Net.send_stream_frame`.
  - Khung hình được gửi lên backend qua `POST /bridge/stream_frame/{camera_id}` (~10–12 khung/giây). Tắt truyền luồng bằng cờ `--no-stream`.
  - Backend `routers/bridge.py` phát luồng liên tục dạng MJPEG tại `GET /bridge/stream/{camera_id}` và cung cấp ảnh chụp tức thời `GET /bridge/stream_snapshot/{camera_id}`.
  - Web Streamlit `frontend/views/camera.py` tích hợp tab **Xem Trực Tiếp (Live Stream)** hiển thị video 2 đầu cầu tập trung, tự động chuyển sang snapshot dự phòng nếu luồng bị ngắt.
- **Bộ theo dõi chống "Nhảy ID / Đổi ID" (Tracking ID Switch) bằng ReID:**
  - Tệp cấu hình `ai_engine/trackers/smartcau_botsort.yaml` kích hoạt **ReID** (`with_reid: true`) sử dụng đặc trưng native backbone detector (`model: auto`) kết hợp khoảng cách vị trí và Kalman filter.
  - Tăng `track_buffer: 90` (~6 giây ở 15 khung hình/giây) giúp ghi nhớ đặc trưng vóc dáng/quần áo và duy trì ID liên tục khi khách đi khuất sau người khác hoặc quay lưng lại; ngưỡng đặc trưng ngoại quan `appearance_thresh: 0.25`.
- **Nguồn hình:** webcam laptop `0`, webcam USB `1`/`2`, điện thoại `phone:<IP>` (IP Webcam) / `droidcam:<IP>`, `rtsp://...`, tệp video — `camera_backend.resolve_source`; webcam xin 1280x720 (`--cam-res`); luồng mạng mở bằng FFmpeg. Dò camera: `tools/tim_camera.py`. Hướng dẫn: `docs/CAMERA_NGOAI.md`.
- **Đọc khung mới nhất:** `camera_backend.LatestFrameReader` (luồng `camera-reader`, bỏ khung cũ → hết trễ hình). Chỉ dùng cho webcam / RTSP, không dùng cho tệp video.
- **Mạng chạy nền:** `camera_bridge.Net` — hàng đợi gửi (`_sender`) + luồng đọc trạng thái / ngưỡng (`_poller`) + luồng streaming (`_streamer`). Mất mạng không làm chậm camera; thanh trên hiện "MẤT KẾT NỐI SERVER".
- **Thu nhỏ khung:** `--max-width` (mặc định 1280).
- **Chữ tiếng Việt:** `camera_ui.TextLayer.render` vẽ từng ô nhỏ bằng Pillow.
- **HUD:** `draw_hud` — camera, trên cầu x/sức chứa, mức, lượt hôm nay, vào/ra của camera này, mặt tiền, khung/giây, `AI xx ms/khung` hoặc trạng thái nhận diện, gợi ý phím, dải đỏ "QUÁ TẢI" khi Đỏ.
- **Mất tín hiệu:** đọc khung lỗi → `CAMERA_LOST`, thử mở lại mỗi 3 giây → `CAMERA_RESTORED`.
- **Nhịp tim:** mỗi 5 giây `POST /bridge/heartbeat` (nguồn, fps, vạch, tên máy, có gửi cảnh báo, có nhận diện). Quá 30 giây không có → coi là mất (`bridge.OFFLINE_AFTER_SEC`).
- **Lỗi OpenCV 5 / bản headless:** `OPENCV_FIX_MSG` in cách sửa.
- **Web:** **Camera** (`frontend/views/camera.py`), tab Xem Trực Tiếp và tab Cấu hình & Trạng thái, tự cập nhật 5 giây.

### 5.9 Tổng quan thời gian thực (M6 · F5.1)
- **Trang:** `frontend/views/tong_quan.py` (fragment 2 giây): sơ đồ cầu (`common.bridge_svg`, chấm = người), mức cảnh báo, sức chứa, tốc độ vào/ra 5 phút, dự kiến bao lâu đầy, thời gian chờ, diễn biến 60 phút, dự báo lượt vào trong ngày, nhận định tự động, sự cố đang mở, camera.
- **API:** `/stats/current`, `/config`, `/insights/live`, `/stats/occupancy/history`, `/incidents`, `/bridge/cameras`, `/insights/summary`.

### 5.10 Xu hướng, dự báo, thời gian chờ, nhận định (insights)
- **Tệp:** `backend/routers/insights.py`.
  - `live()`: tốc độ vào / ra 5 phút (`TREND_MIN`), xu hướng tăng / giảm / ổn định, `minutes_to_full`, thời gian chờ khi đầy = (số người vượt + 1) / tốc độ ra (`wait_bucket`: "Dưới 3 phút", "3–5 phút", "Trên 5 phút"), dự báo theo giờ = trung bình cùng thứ 8 tuần trước (`_hourly_profile`) × hệ số đông hôm nay.
  - `summary()`: các câu nhận định `{tone, title, text}` (lượt hôm nay, so tuần trước, dự báo cao điểm, cầu sắp đầy, cơ cấu khách, sự cố, mặt tiền).
- **Test:** `test_insights_live_trend_wait_and_forecast`, `test_insights_summary_sentences`, `test_wait_buckets`.

### 5.11 Bảng LED 2 đầu cầu (M3 · F2.2)
- **Địa chỉ:** `http://<IP>:8000/led/?dau=1` (đầu cầu 1), `?dau=2` (đầu cầu 2), `/led/hai-man-hinh.html` (song song). Tham số: `&scene=1..4` khóa cảnh, `&debug=1` hoặc phím **D** mở bảng giả lập, `&api=http://...` khi mở từ nơi khác.
- **Dữ liệu:** `GET /display/state` mỗi giây (`backend/routers/display.py`): `onbridge, level, stale, dem, capacity, warning_threshold, wait_label(_en), is_open_now, utc_offset_hours, server_time`.
- **Vai nhân vật** (`led.js` → `CONFIG.ends`): đầu cầu 1 Linh Thân đón khách, Linh Khuyển ra ngăn khi Đỏ; đầu cầu 2 đổi vai.
- **8 clip mỗi nhân vật** (`CONFIG.clips`): idle, wave, bow, yellow, red, walkOn, walkOff, walkLoop. Clip đi rộng hơn khung, có `shift` (căn vị trí) và `arrive` / `from` (giây).
- **Hành vi** (`handleLevel`, hàng đợi `queueMascot` để không cắt ngang): khởi động = đi vào + vẫy + câu giới thiệu; Xanh = idle, xen wave/bow mỗi 25–35 giây; khách mới (dem tăng) = wave (cách 30 giây); Vàng = yellow mỗi 20 giây; lên Đỏ = biển báo đổi ngay, host đi ra, guard đi vào, giơ tay mỗi 18 giây; Đỏ hạ = guard cúi chào, đi ra, host vào; vắng khách >60 giây = câu mời; mất dữ liệu >10 giây = chip "mất kết nối".
- **Phông nền** (`BG`, `clockScene`, `startTour`): ngày 06:00–17:30 cảnh 1 xen cảnh 4 mỗi 5 phút; đêm cảnh 3 xen cảnh 2; Vàng thêm tông ấm; Đỏ tour 4 cảnh, mỗi cảnh 30 giây kèm thuyết minh; đổi cảnh mờ chéo 0,8 giây ở ranh giới vòng lặp.
- **Câu thoại:** `CONFIG.lines` (intro, green, greenBow, guest, toYellow, yellow, yellowToGreen, toRed, red, redDown, quiet); `{chao}`, `{onbridge}`, `{dem}`, `{ten}` tự thay; tối đa 2 dòng (tự thu nhỏ chữ).
- **Biển báo song ngữ:** `CONFIG.sign`.
- **Tệp:** `backend/led_display/index.html`, `led.js`, `led.css`, `hai-man-hinh.html`, `media/`; web nhúng ở `frontend/views/bang_led.py`. Tệp gốc ở `media/mascot/`, `media/phong_nen/`.
- **Lưu ý:** WebM trong suốt chỉ chạy đúng trên Chrome / Edge. Trình duyệt chặn tự phát → hiện "Chạm để bắt đầu".
- **Test:** `test_display_state_and_led_page` (có kiểm tra đủ 16 clip).

### 5.12 Tin nhắn Telegram (F2.3)
- **Gửi:** `backend/notify.py` — `_send_telegram` (HTML, lỗi định dạng thì gửi lại dạng chữ thường), `keyboard` (nút), `deliver` / `deliver_async`, `deliver_document` (PDF). Token: `TELEGRAM_BOT_TOKEN` hoặc lưu trong CSDL (`SystemConfig.telegram_token`, nạp bởi `admin.load_telegram_token`).
- **Nội dung:** `backend/messages.py`:
  - `status_block`: mức, x/sức chứa, thanh màu, từng chân cầu, xu hướng 5 phút, dự kiến đầy, thời gian chờ, lượt hôm nay, camera, sự cố mở.
  - `event_message`: WARNING, CRITICAL_ALERT (lần đầu / nhắc lại), GROUP_DETECTED, CAMERA_LOST, CAMERA_RESTORED.
  - `incident_closed_message`, `status_message`, `today_message`, `morning_message`, `daily_report_message`, `weekly_message`.
- **Nút** (`alerts.buttons`): "✅ Đã xử lý" (chỉ khi Đỏ chưa ai nhận), "📍 Tình hình", "📊 Hôm nay", "🖥 Mở trang quản lý" (nếu có `SMARTCAU_WEB_URL`).
- **Test:** `test_rich_telegram_messages_include_live_status`, `test_telegram_connect_and_find_chats`.

### 5.13 Bot Telegram 2 chiều
- **Tệp:** `backend/telegram_bot.py` — luồng `telegram-bot` gọi `getUpdates` (long polling 25 giây), `handle_update` xử lý.
- **Lệnh:** `/tinhhinh` (`/status`), `/homnay` (`/today`), `/suco` (`/incidents`), `/start` `/help` `/trogiup`. Nút: `ack:<id>`, `status`, `today`.
- **Bảo mật:** chỉ chat có trong bảng `recipients` mới xem số liệu / bấm nút; chat lạ nhận lại chat_id để gửi quản trị viên.
- **Khi bot chạy**, trang Người nhận lấy danh sách chat từ `telegram_bot.SEEN` (vì `getUpdates` chỉ một nơi đọc được) — xem `admin.telegram_chats`.
- **Test:** `test_telegram_bot_commands_and_ack_button`.

### 5.14 Người nhận cảnh báo và loại tin (M7 · F6.3)
- **Loại tin** (`admin.TOPICS`): `red`, `yellow`, `group`, `camera`, `morning`, `ticket`, `daily`, `weekly`, `system`. Mẫu `admin.PRESETS`: Người trực / Quản lý / Tất cả. `Recipient.topics = NULL` = nhận tất cả.
- **Lọc:** `admin.active_recipients(db, topic)`; sự kiện → loại tin ở `alerts.TOPIC_OF`.
- **Web:** **Người nhận cảnh báo** (`frontend/views/nguoi_nhan.py`): kết nối bot (dán token), tìm người vừa nhắn cho bot, thêm / bật tắt / gửi thử / xóa, chọn loại tin, thêm bằng tay.
- **API:** `/recipients` (GET/POST), `/recipients/{id}` (PUT/DELETE), `/recipients/{id}/test`, `/recipients/topics`, `/telegram/status`, `/telegram/token` (PUT/DELETE), `/telegram/chats`.
- **Test:** `test_recipients_crud`, `test_recipient_topics_filter_messages`.

### 5.15 Lịch tự động (luồng nền `daily-report`, mỗi phút)
`backend/daily_report.py::run_due` (gọi bởi `start_scheduler`). Mỗi việc chỉ làm 1 lần (`_once` ghi `system_events` loại `MORNING_BRIEF` / `TICKET_REMINDER` / `WEEKLY_REPORT`):

| Việc | Khi nào | Hàm | Loại tin |
|---|---|---|---|
| Bản tin đầu ngày | Trong 60 phút đầu sau giờ mở cửa | `_send_morning` → `messages.morning_message` | morning |
| Nhắc nhập số cuống vé | 30 phút trước giờ đóng cửa, nếu chưa nhập | trong `run_due` | ticket |
| Báo cáo ngày + PDF | Sau giờ đóng cửa (và lập bù hôm qua nếu thiếu) | `generate` → `_deliver` | daily |
| Tự đồng bộ Google Sheets | Ngay sau gửi báo cáo ngày, nếu bật | `sheets_auto.auto_sync_after_report` | system |
| Báo cáo tuần + PDF | Thứ Hai, từ giờ mở cửa | `send_weekly` → `messages.weekly_message` | weekly |

- **Test:** `test_daily_report_after_closing_time`, `test_morning_brief_and_ticket_reminder_once_per_day`, `test_weekly_report_compares_previous_week`, `test_sheets_auto_sync_skips_when_not_configured`.

### 5.16 Báo cáo định kỳ, KPI, biểu đồ nhiệt (M4 · F5.2, F5.3)
- **Kỳ báo cáo** (`reports.period_range`): `day` = 1 ngày; `week` = 7 ngày kết thúc ở `date`; `month` = tháng dương lịch chứa `date`; `year` = năm dương lịch; `custom` = `date_from` → `date_to` (tối đa 3 năm).
- **So với kỳ trước** (`previous`): tháng → tháng trước, năm → năm trước, còn lại lùi đúng số ngày; kỳ đang diễn ra thì so cùng số ngày đã qua (`same_elapsed_days`).
- **Tính toán:** `backend/routers/reports.py::report_summary(period, date, date_from, date_to)` — thêm `by_month`, `tickets` (đối chiếu vé từng ngày), `capacity`, `previous`; tổng lượt vào / ra / mặt tiền, theo ngày / giờ / 15 phút / khung buổi, đông nhất, sự kiện, sự cố, cơ cấu khách, KPI:
  - O1 = số phút có ít nhất 1 lần đo vượt sức chứa,
  - O4 = % sự cố thật được xác nhận trong 180 giây,
  - O5 = % sự cố bị đánh dấu báo sai,
  - O8 = % chênh lệch (lượt vào − vé) / lượt vào, chỉ ngày đã nhập vé.
- **Biểu đồ nhiệt** giờ × thứ: `heatmap()` (8 tuần, theo `local_time`).
- **PDF** (`backend/report_export.py::to_pdf(r, options)`), theo thể thức văn bản hành chính (Nghị định 30/2020): lề trái 30 / phải 15 / trên-dưới 20 mm; font Times New Roman 13 (Linux: Liberation Serif / DejaVu Serif); phần đầu 2 cột (tên cơ quan chủ quản + đơn vị + "Số: …/BC-SCAI" | Quốc hiệu, tiêu ngữ, "Hội An, ngày … tháng … năm …"); tiêu đề "BÁO CÁO"; các mục I–VI (`SECTIONS`); bảng và hình đánh số; nơi nhận + chữ ký; "Trang x/y"; **logo SmartCau in chìm** giữa mỗi trang (`Doc.watermark`, vẽ vector, độ mờ 7%).
  - Biểu đồ (matplotlib → PNG): `chart_trend` (15 phút / ngày / tháng + đường bình quân), `chart_hours_slots`, `chart_demographics`, `chart_tickets`.
  - Đoạn văn tự sinh: `_narrative` (tổng lượt, bình quân, so kỳ trước, ngày đông nhất, giờ cao điểm), `_assessment` (đánh giá, kiến nghị theo KPI).
  - Tùy chỉnh (`PDF_DEFAULTS`): `sections`, `charts`, `report_no`, `prepared_by`, `approver`, `recipients`, `notes`, `org_parent`, `org_name`, `place`. Tên cơ quan mặc định đổi bằng `SMARTCAU_ORG_PARENT`, `SMARTCAU_ORG_NAME`, `SMARTCAU_ORG_PLACE`.
  - Ngày / tháng chưa tới trong kỳ đang diễn ra bị bỏ khỏi bảng và biểu đồ (`_until_today`).
  - Báo cáo ngày / tuần tự động gửi Telegram dùng cùng mẫu PDF này.
- **Web:** **Báo cáo định kỳ** (`frontend/views/bao_cao.py`): chọn kỳ Ngày / Tuần / Tháng / Năm / Tùy chọn; khung "Xuất báo cáo" với **Tùy chỉnh nội dung báo cáo PDF**; nút **Lập báo cáo PDF** rồi **Tải PDF vừa lập**; Xuất Excel; KPI, biểu đồ (kỳ năm theo tháng), biểu đồ nhiệt, bảng, báo cáo tuần, danh sách báo cáo ngày.
- **API:** `/reports/summary`, `/reports/heatmap`, `/reports/daily`, `/reports/daily/{date}/pdf`, `/reports/daily/{date}/send`, `/reports/weekly/pdf`, `/reports/weekly/send`.
- **Test:** `test_report_summary_real_data`, `test_false_alarm_and_kpis`, `test_heatmap_shape_and_totals`.

### 5.17 Đối chiếu vé (M5 · F4.1, F4.2)
- **Quy tắc:** chỉ so lượt **vào lòng cầu** (không tính mặt tiền); nhập cả ngày hoặc từng giờ; nhập lại cùng ngày / giờ thì ghi đè (`_upsert`); khi nhập theo giờ chỉ so các giờ đã nhập (`compared_entries`).
- **Hai cách xem:** **Theo ngày (nhiều ngày)** — chọn khoảng ngày, mỗi ngày so lượt vào với tổng vé ngày đó (`reconciliation_range`; ngày nhập theo giờ thì chỉ so các giờ đã nhập), KPI tổng, biểu đồ cột + đường tỷ lệ, bảng, tải Excel; **Theo giờ trong 1 ngày** — như cũ.
- **Tệp:** `backend/routers/tickets.py` (`TicketCount`, `reconciliation`, `reconciliation_range`), `frontend/views/doi_chieu_ve.py` (chọn Cả ngày / Từng giờ, khung giờ theo giờ mở cửa và cho biết khung đã nhập, tải mẫu Excel / CSV `template_df`, `to_xlsx`, tải tệp lên bỏ dòng trống, biểu đồ theo giờ, danh sách vé đã nhập).
- **API:** `POST /tickets`, `POST /tickets/bulk`, `GET /tickets`, `DELETE /tickets/{id}`, `GET /tickets/reconciliation?date=`, `GET /tickets/reconciliation_range?date_from=&date_to=`.
- **Test:** `test_ticket_reconciliation`.

### 5.18 Ngưỡng và giờ hoạt động (M7 · F6.2)
- **Tệp:** `backend/routers/admin.py::read_config, update_config, is_open_now`; `frontend/views/cau_hinh.py` (sức chứa, giờ mở / đóng cửa, nhật ký thay đổi).
- **API:** `GET /config` (công khai, camera đọc), `PUT /config` (admin).
- **CSDL:** `system_config` (1 dòng). Đổi ngưỡng → camera áp dụng trong ≤15 giây.

### 5.19 Tài khoản, đăng nhập, phân quyền (M2 · F6.1)
- **Vai trò:** `admin` (Quản trị viên), `quan_ly` (Quản lý), `nguoi_truc` (Người trực).
- **Backend:** `routers/accounts.py` (đăng nhập tạo token 12 giờ, đăng xuất, đổi mật khẩu, CRUD tài khoản, không xóa được admin cuối cùng, nhật ký), `security.py` (PBKDF2 200 000 vòng, `current_principal` đọc `Authorization: Bearer` hoặc `X-Admin-Key`, `require_roles`, `require_staff/manager/admin`).
- **Web:** `frontend/app.py` (menu theo vai trò ở danh sách `PAGES`; chưa đăng nhập hoặc bắt đổi mật khẩu thì ẩn menu), `common.login_page`, `restore_session` (giữ phiên qua F5 bằng `?s=<token>` trên URL), `logout`, `change_password_form`; trang **Tài khoản** (`tai_khoan.py`).
- **Test:** `test_default_admin_must_change_password`, `test_wrong_password_and_no_token`, `test_roles_and_account_lifecycle`, `test_cannot_remove_last_admin`, `test_config_roundtrip_and_audit`.

Menu theo vai trò (`frontend/app.py::PAGES`):

| Trang | Tệp | Người trực | Quản lý | Admin |
|---|---|---|---|---|
| Tổng quan | views/tong_quan.py | ✓ | ✓ | ✓ |
| Trực ca & sự cố | views/truc_ca.py | ✓ | ✓ | ✓ |
| Bảng LED hai đầu cầu | views/bang_led.py | ✓ | ✓ | ✓ |
| Lượt qua cầu | views/luot_qua_cau.py | ✓ | ✓ | ✓ |
| Đối chiếu vé | views/doi_chieu_ve.py | ✓ | ✓ | ✓ |
| Cơ cấu khách | views/co_cau_khach.py | | ✓ | ✓ |
| Lịch sử lượt khách | views/lich_su.py | | ✓ | ✓ |
| Báo cáo định kỳ | views/bao_cao.py | | ✓ | ✓ |
| Camera | views/camera.py | | ✓ | ✓ |
| Quyền riêng tư | views/quyen_rieng_tu.py | | ✓ | ✓ |
| Ngưỡng & giờ hoạt động | views/cau_hinh.py | | | ✓ |
| Người nhận cảnh báo | views/nguoi_nhan.py | | | ✓ |
| Tài khoản | views/tai_khoan.py | | | ✓ |
| Google Sheets | views/dong_bo_sheets.py | | | ✓ |

### 5.20 Quyền riêng tư (PB-06)
- Không lưu ảnh / đặc trưng mặt; khung hình chỉ xử lý trong bộ nhớ. Đã bỏ làm mờ mặt theo yêu cầu nhóm.
- Dữ liệu phải giữ tối thiểu 730 ngày (`admin.RETENTION_MIN_DAYS`); chỉ xóa được dữ liệu cũ hơn.
- **Tệp:** `admin.privacy_summary`, `admin.purge`; `frontend/views/quyen_rieng_tu.py` (mô tả, biển thông báo song ngữ, số dòng đang lưu, xóa dữ liệu cũ).
- **Test:** `test_privacy_purge_respects_retention`.

### 5.21 Google Sheets
- **Đồng bộ tay:** trang `frontend/views/dong_bo_sheets.py` (dán link Sheet, tải tệp khóa, công tắc tự đồng bộ, nút Đồng bộ ngay) → `tools/google_sheets_sync.sync_all` (trang tính `LuotKhach` và `TongQuan`).
- **Tự động:** `backend/sheets_auto.py` sau báo cáo ngày. Cần `pip install gspread google-auth` và chạy backend cùng máy với web (chung thư mục `config/`).

### 5.22 Chạy nhiều máy
- `tools/kiem_tra_mang.py` (in IP, kiểm tra cổng 8000 / 8501, lệnh cho máy khác), `common.public_api_base()` (đổi địa chỉ LED theo máy đang truy cập), tên máy camera trong nhịp tim. Chi tiết: `docs/TRIEN_KHAI_NHIEU_MAY.md`.

### 5.23 Đo độ chính xác
- `tools/eval_counting.py` (so lượt đếm với số thật, NFR-02), `tools/eval_demographics.py` (FairFace / UTKFace, độ chính xác giới tính / tuổi / nguồn khách, `--save-calibration` học hệ số tuổi). Test: `tests/test_eval_tools.py`.

---

## 6. Chi tiết từng tệp code

### 6.1 backend/
| Tệp | Thành phần chính | Ghi chú |
|---|---|---|
| `main.py` | `app = FastAPI(...)`, `include_router` cho 10 router, `app.mount("/led", StaticFiles(led_display))`, `ensure_schema()`, `accounts.ensure_default_admin`, `admin.load_telegram_token`, `@startup _start_background_jobs` (gọi `daily_report.start_scheduler()` và `telegram_bot.start()`), `GET /health` | Thêm router mới phải import và `include_router` ở đây |
| `database.py` | `DATABASE_URL`, `engine`, `SessionLocal`, `Base`, `get_db()`, `ensure_schema()` | `ensure_schema` tự `ALTER TABLE ADD COLUMN` cho cột mới → tệp `.db` cũ vẫn chạy. Không tự đổi kiểu / xóa cột |
| `models.py` | Bảng chung (mục 8), `ROLES`, `get_state` (tạo dòng `occupancy_state` id=1), `get_config` (tạo `system_config` mặc định 20 người, 07:00–21:30), `log_audit` | |
| `schemas.py` | `VisitEventIn`, `OccupancyIn`, `SystemEventIn` (event_type, count, message, camera_id), `RegionStatIn` | |
| `security.py` | `API_KEY`, `ADMIN_API_KEY`, `hash_password`, `verify_password`, `require_api_key` (header `X-API-Key`), `Principal`, `current_principal`, `require_roles`, `require_staff`, `require_manager`, `require_admin` | Lỗi 401 / 403 đều xuất phát ở đây |
| `timeutil.py` | `UTC_OFFSET_HOURS`, `LOCAL_UTC_OFFSET`, `utcnow`, `local_now`, `to_local`, `local_day_range_utc`, `parse_day`, `iso` | CSDL lưu **UTC**; thống kê theo **giờ Việt Nam** |
| `notify.py` | `telegram_token`, `set_db_token`, `token_source`, `telegram_api(method, **params)` (timeout HTTP = 10 + timeout Telegram), `keyboard`, `_send_telegram`, `deliver`, `deliver_async`, `deliver_document`, `WEB_URL` | Không có người nhận → dùng `TELEGRAM_CHAT_ID` |
| `messages.py` | `LEVEL`, `bar`, `status_block`, `status_message`, `event_message`, `incident_closed_message`, `today_message`, `morning_message`, `daily_report_message`, `weekly_message`, `WEEKDAY_VI` | Chỉ đọc CSDL; tin dạng HTML (`<b>`, `<i>`, `<code>`); chữ người dùng nhập phải `html.escape` |
| `telegram_bot.py` | `SEEN`, `HELP`, `running`, `handle_update(upd, send, answer)`, `_loop`, `start` | `handle_update` nhận `send`/`answer` để test không cần mạng |
| `daily_report.py` | Bảng `DailyReport`, `summary_text`, `_tickets_missing`, `pdf_of`, `_deliver` (gửi + Sheets), `generate`, `_has_data`, `run_due`, `_recipients`, `_once`, `_send_morning`, `weekly_summaries`, `send_weekly`, `start_scheduler` | Thời điểm truyền vào `run_due(db, now_local)` để test được |
| `sheets_auto.py` | `load_conf`, `sync_now`, `auto_sync_after_report`, `CONF_FILE`, `KEY_FILE`, `SELF_URL` | Không ném lỗi, trả câu tóm tắt |
| `report_export.py` | `FONT_SETS` (Times New Roman → Liberation Serif → DejaVu Serif → Arial), `PERIOD_VI`, `WEEKDAY_VI`, `ORG_PARENT`, `ORG_NAME`, `ORG_PLACE`, `SECTIONS`, `PDF_DEFAULTS`, `period_label`, `_until_today`, `report_tables`, `to_excel`, biểu đồ `chart_trend` / `chart_hours_slots` / `chart_demographics` / `chart_tickets` (matplotlib), `_make_doc_class` (lớp `Doc`: `header` + `watermark` logo chìm, `footer` số trang), `_narrative`, `_assessment`, `to_pdf(r, options)`, `_strip_accents` | Dùng chung cho web (Excel / PDF) và báo cáo ngày / tuần tự động. Cần `fpdf2`, `matplotlib`, `Pillow` |

### 6.2 backend/routers/
| Tệp | Bảng định nghĩa ở đây | Hàm / endpoint |
|---|---|---|
| `accounts.py` | (User, AuthToken, AuditLog ở models.py) | `ensure_default_admin`, `login`, `logout`, `me`, `change_password`, `list_users`, `create_user`, `update_user`, `audit_log`; `TOKEN_HOURS = 12` |
| `bridge.py` | `BridgeState`, `BridgeCrossing`, `CameraStatus` | `record_crossing`, `heartbeat`, `cameras`, `bridge_state`, `reset_bridge`, `bridge_stats`, `upload_stream_frame`, `stream_snapshot`, `live_stream`; `_get_bridge_state`, `_roll_day`, `_state_json`, `_LOCK`, `_LATEST_FRAMES`, `OFFLINE_AFTER_SEC = 30` |
| `counting.py` | `FacadePass` | `person_entry`, `person_exit` (API cũ `/entry` `/exit`), `create_occupancy`, `occupancy_stats`, `current_stats`, `occupancy_history`, `facade_pass`, `facade_stats` |
| `alerts.py` | `Incident` | `EVENT_LABELS`, `TOPIC_OF`, `ALWAYS_NOTIFY`, `NOTIFY_IN_HOURS`, `buttons`, `_close`, `create_system_event`, `list_system_events`, `list_incidents`, `ack_incident`, `acknowledge`, `close_incident`, `mark_false_alarm` |
| `demographics.py` | (VisitEvent, RegionStat ở models.py) | `AGE_ORDER`, `ORIGINS`, `create_visit_event`, `list_visit_events` (lọc giới tính / tuổi / nguồn / ngày), `summarize_visits` (bỏ "không xác định" khỏi tỷ lệ), `demographics_summary`, `bump_region_stat`, `region_stats` |
| `tickets.py` | `TicketCount` | `_validate`, `_upsert`, `add_ticket_count`, `add_bulk`, `list_tickets`, `delete_ticket`, `reconciliation` (1 ngày, theo giờ), `reconciliation_range` (nhiều ngày, theo ngày), `_rate` |
| `reports.py` | — | `HANDLE_TARGET_SEC = 180`, `TIME_SLOTS`, `PERIODS`, `MAX_CUSTOM_DAYS`, `period_range`, `report_summary` (trả thêm `by_month`, `tickets`, `capacity`, `previous`), `heatmap`, `list_daily`, `daily_pdf`, `resend_daily`, `weekly_pdf`, `send_weekly_now` |
| `insights.py` | — | `WEEKS = 8`, `TREND_MIN = 5`, `_crossings_between`, `_hourly_profile`, `wait_bucket`, `wait_bucket_en`, `live`, `summary` |
| `admin.py` | `Recipient` | `CHANNELS`, `RETENTION_MIN_DAYS`, `TOPICS`, `PRESETS`, `_topics_of`, `active_recipients`, `is_open_now`, `read_config`, `update_config`, `recipient_topics`, CRUD người nhận, `test_recipient`, `privacy_summary`, `purge`, `load_telegram_token`, `telegram_status`, `set_telegram_token` (kiểm tra `getMe`), `clear_telegram_token`, `telegram_chats` |
| `display.py` | — | `display_state` (`STALE_SEC = 30`) |

### 6.3 backend/led_display/led.js (theo thứ tự trong tệp)
- `CONFIG`: `apiBase`, `pollMs`, `offlineAfterMs`, `dayStart/dayEnd`, `sceneMode`, `altEveryMin`, `altDurationSec`, `tourSceneSec`, `tourFollowsClock`, `crossfadeMs`, `scenes`, `clock`, `ends`, `names`, `clips`, `timing`, `lines`, `sign`.
- Tiện ích: `END_NO`, `END`, `pick` (câu ngẫu nhiên không lặp), `vnNow`, `isDay`, `chao`, `fill`, `levelOf`.
- `say(key)`: bóng thoại, tự thu nhỏ chữ.
- `Mascot`: `init`, `show`, `idle`, `play(action, line)`, `waitClip`, `walkOff`, `walkOn(who)`, `swapTo(who)`; hằng `STATIC_W = 644`, `CROP_X = 293.6`, `WIDE_W = 1182` (kích thước clip đã xử lý).
- `BG`: 2 lớp video `bgA` / `bgB`, `request`, `onTime`, `swap` (mờ chéo).
- `S`: trạng thái (level, onbridge, dem, offline, tour, override...).
- `applySign`, `onLevelChange` → `queueMascot` → `handleLevel`, `periodic`, `clockScene`, `startTour`, `stopTour`, `desiredScene`, `sceneTick`, `poll`, `boot`, `clockTick`, `needTap`, `DBG` (bảng debug: giả lập mức, +1 khách, chọn cảnh, thử clip, đi ra → đi vào).

### 6.4 frontend/
| Tệp | Nội dung |
|---|---|
| `app.py` | `set_page_config`; chưa đăng nhập → `st.navigation([login_page], position="hidden")` và ẩn thanh bên; `must_change_password` → trang đổi mật khẩu; `PAGES` + vai trò; `st.logo`; thanh bên: tên, vai trò, "Đã kết nối / Mất kết nối máy chủ" (`api_is_up`), Mật khẩu, Đăng xuất, `alert_watcher()` |
| `common.py` | `API_BASE`, `public_api_base`, bảng màu `C`, `COLORS`, `SERIES`, `GENDER_VI`, `ORIGIN_VI`, `AGE_ORDER`, `ROLE_VI`, `STATUS_META`, `EVENT_TONE`; CSS `_THEME_CSS` (đã bỏ dòng trống — **dòng trống trong `<style>` làm CSS hiện ra thành chữ**); `apply_theme`, `page_header`, `section`, `kpi`, `kpi_row`, `badge`, `status_badge`, `note`, `alert_box`, `empty`, `capacity_bar`, `style_fig`; thời gian `utc_offset_hours`, `to_local`, `fmt_time`, `fmt_duration`, `fmt_mmss`, `local_now`, `local_today`; API `ApiError`, `_headers`, `_call`, `api_get`, `api_get_bytes`, `api_post`, `api_put`, `api_delete`, `safe_get` (lỗi thì hiện hộp đỏ, trả None), `api_is_up`; phiên `current_user`, `has_role`, `restore_session`, `login_page`, `change_password_form`, `logout`; `bridge_svg`, `insight_list`, `alert_watcher` |
| `views/tong_quan.py` | Mục 5.9 |
| `views/truc_ca.py` | Mục 5.5 |
| `views/bang_led.py` | 2 iframe LED (`?dau=1`, `?dau=2`), chọn Song song / Đầu cầu 1 / Đầu cầu 2, nút toàn màn hình / debug; `_iframe` = `st.iframe` hoặc `components.iframe` |
| `views/luot_qua_cau.py` | Fragment 2 giây: num1, num2, onbridge, dem, sơ đồ; nút đặt lại (quản lý); thống kê theo giờ / ngày / tháng / năm, bấm cột xem chi tiết |
| `views/doi_chieu_ve.py` | Mục 5.17: nhập vé (Cả ngày / Từng giờ), tải mẫu Excel / CSV, tải tệp lên, xem **Theo ngày (nhiều ngày)** hoặc **Theo giờ trong 1 ngày**, tải bảng đối chiếu Excel |
| `views/co_cau_khach.py` | Chọn ngày; KPI; biểu đồ giới tính, nhóm tuổi, nguồn khách, theo giờ |
| `views/lich_su.py` | Lọc theo ngày / giới tính / nhóm tuổi / nguồn khách; bảng hồ sơ; KPI |
| `views/bao_cao.py` | Mục 5.16: chọn kỳ Ngày / Tuần / Tháng / Năm / Tùy chọn, tùy chỉnh và lập PDF, Excel, KPI, biểu đồ, biểu đồ nhiệt, báo cáo tuần, báo cáo ngày |
| `views/camera.py` | Tab Xem Trực Tiếp (luồng Live Stream MJPEG 2 camera, fallback snapshot) và Tab Cấu Hình & Trạng Thái (thẻ 2 camera: trạng thái, fps, máy, nguồn, vạch, gửi cảnh báo, nhận diện, chạy từ) |
| `views/cau_hinh.py` | Mục 5.18 |
| `views/nguoi_nhan.py` | Mục 5.14 |
| `views/tai_khoan.py` | Tạo tài khoản, đổi vai trò, khóa / mở, đặt lại mật khẩu |
| `views/quyen_rieng_tu.py` | Mục 5.20 |
| `views/dong_bo_sheets.py` | Mục 5.21 |

### 6.5 ai_engine/
| Tệp | Thành phần chính |
|---|---|
| `camera_bridge.py` | Hằng: `API_BASE`, `STATE_POLL_SEC=1`, `CONFIG_POLL_SEC=15`, `REPORT_SEC=2`, `HEARTBEAT_SEC=5`, `ALERT_REPEAT_SEC=180`, `RECONNECT_SEC=3`, `OPENCV_FIX_MSG`, `MACHINE`, `LEVEL_VI`, `LEVEL_BGR`. Hàm: `_post`, `_post_bytes`, `_get` (gọi HTTP đồng bộ, timeout 2 giây), lớp `Net` (gửi / đọc nền + luồng phát live stream `_streamer`, `send_stream_frame`), `_line_path`, `load_line`, `draw_line_setup`, `draw_line_overlay`, `draw_hud`, `parse_args` (hỗ trợ cờ `--no-stream`), `main` (mở camera `open_src`, nạp bộ nhận diện, tạo `VisitorProfiler`, vòng lặp: đọc khung → thu nhỏ → YOLO BoT-SORT ReID track → từng người: vạch / mặt tiền / nhóm / hồ sơ → gửi sự kiện & live stream JPEG → HUD → phím) |
| `camera_backend.py` | `_pick_backend_for_platform` (Windows `CAP_DSHOW`, Linux `CAP_V4L2`, macOS `CAP_AVFOUNDATION`), `PHONE_APPS`, `resolve_source` (gõ tắt `phone:`/`droidcam:`/IP), `is_network_source`, `open_camera` (webcam xin 1280x720; luồng mạng dùng `CAP_FFMPEG`), `LatestFrameReader`, `parse_camera_source` (cho camera cũ) |
| `camera_ui.py` | `draw_person_box`, `draw_info_panel`, `draw_status_bar`, `draw_capacity_banner`, `draw_gate_banner`, `draw_countdown`, font `_FONT_CANDIDATES`, `vietnamese_text_supported`, `TextLayer` (`text`, `measure`, `render`), `panel_lines` |
| `line_crossing.py` | `LineCrossingCounter` (`p1`, `p2`, `bridge_point`, `signed_distance`, `update`, `save`, `load`), `foot_point`, `FacadeCounter` (`update`, `mark_crossed`, `collect`) |
| `crowd_counter.py` | `CameraThresholds`, `AlertLevelTracker`, `STATUS_COLOR_BGR`, `STATUS_LABEL_VI`, `CrowdCounter` (YOLO / HOG, dùng ở bản demo cũ) |
| `group_detector.py` | `GroupDetector(min_size=10, hold_sec=10, gap_factor=1.2)`: `_approaching`, `_largest_cluster`, `update`, `current_size` |
| `visitor_profiler.py` | `GENDER_VI`, `ORIGIN_VI`, `REGION_TO_ORIGIN`, `ORIGIN_MIN_SHARE`, `MIN_EYE_PX=18`, `MIN_SHARPNESS=45.0`, `MIN_BOX_H=130`, `face_quality`, `QUALITY_HINT`, `extract_keypoints`, `AsyncEngine` (luồng nền, `avg_ms`), `_Track`, `VisitorProfiler` (`analyze_interval = 0.3`, `ready_interval = 1.5`, `wants`, `observe`, `mark_entered`, `mark_exited`, `step`, `origin_of`, `label`, `_save`, `_save_unknown`) |
| `demographics_engine.py` | `CONFIDENCE_THRESHOLD=0.75`, `VOTE_WINDOW=8`, `MIN_VOTES_BEFORE_READY=4`, `_FLIP_MARGIN`, `RACE_VOTES = 4`, `TemporalVoter`, `DemographicsEngine(enable_region)` (`update`: đường keypoint hoặc dự phòng, trọng số phiếu (độ chắc − 50)/50, `last_path`; `forget`), tín hiệu dáng người (`estimate_gender_signal_from_pose`, mặc định tắt) |
| `age_gender_estimator.py` | `DEMOGRAPHICS_BACKEND` (mặc định `insightface`, có fallback `deepface`), `_load_insightface`, `_predict_genderage_insightface`, `align_face_for_insightface` (cắt 96×96 chuẩn InsightFace với trường nhìn rộng `eye_span=0.26`, `eye_y=0.40`), `age_to_range`, `_is_fake_full_image_region`, `_apply_clahe`, `DEFAULT_DETECTOR`, `load_age_calibration`, `calibrate_age`, `_load_deepface`, `demographics_status`, `estimate_age_gender`, `estimate_demographics_from_person_box`, `FACE_SIZE`, `TTA_BELOW = 85`, `align_face_from_keypoints` (cắt mặt 224×224 cho DeepFace), `_analyze_skip`, `estimate_from_aligned_face`, `annotate_age_gender` |
| `region_mapping.py` | `REGION_ORDER`, `REGION_LABEL_DISPLAY`, `DISCLAIMER_VI`, `nationality_to_region`, `classify_region_from_deepface_race` |
| `telegram_alert.py` | `trigger_buzzer_signal` (gọi `SMARTCAU_BUZZER_WEBHOOK` nếu có), `send_telegram_alert` (kiểu cũ) |
| `camera_in.py`, `camera_out.py` | Bản cũ dùng `/entry`, `/exit`, không dùng vạch. **Không sửa lỗi ở đây** nếu đang chạy `camera_bridge.py` |

### 6.6 tools/
| Tệp | Chạy | Làm gì |
|---|---|---|
| `kiem_tra_mang.py` | `python tools/kiem_tra_mang.py [http://IP:8000]` | `lan_ips`, `port_open`, `server_mode`, `client_mode` |
| `tim_camera.py` | `python tools/tim_camera.py [phone:<IP> \| droidcam:<IP> \| rtsp://...]` | Dò webcam số 0–5 hoặc thử 1 luồng điện thoại; in độ phân giải, khung/giây, lệnh chạy; lưu ảnh thử vào `tools/anh_camera/` |
| `simulate_bridge.py` | `python tools/simulate_bridge.py` | Gửi kịch bản vào / ra (`SCENARIO`) tới `/bridge/crossing` |
| `seed_demo_data.py` | `python tools/seed_demo_data.py` | Tạo hồ sơ khách / lượt demo |
| `google_sheets_sync.py` | gọi từ web / `sheets_auto` (hoặc `python tools/google_sheets_sync.py`) | `sync_all(api_base, sheet_id, creds_path)` |
| `eval_counting.py` | xem `docs/AI_CAI_THIEN.md` | `count_crossings`, `count_presence`, `error_pct`, `write_report` |
| `eval_demographics.py` | xem `docs/AI_CAI_THIEN.md` | `load_fairface`, `load_utkface`, `evaluate`, `fit_age_calibration`, `deepface_predictor` |
| `data_simulator.py`, `generate_dashboard.py`, `demo_run.py` | bản demo cũ | Sinh dữ liệu giả và dashboard HTML tĩnh |

---

## 7. Danh sách API

Quyền: **cam** = header `X-API-Key` (chỉ khi máy chủ đặt `SMARTCAU_API_KEY`); **staff** = đã đăng nhập (mọi vai trò); **manager** = admin hoặc quan_ly; **admin**; **—** = công khai.

| Method · Path | Tệp::hàm | Quyền | Ai gọi |
|---|---|---|---|
| GET /health | main.py::health | — | web, tools |
| POST /auth/login · /auth/logout | accounts.py | — / staff | web |
| GET /auth/me · POST /auth/change_password | accounts.py | staff | web |
| GET·POST /users · PUT /users/{id} | accounts.py | admin | tai_khoan.py |
| GET /audit | accounts.py::audit_log | manager | cau_hinh.py |
| POST /bridge/crossing | bridge.py::record_crossing | cam | camera_bridge.py, simulate_bridge.py |
| POST /bridge/heartbeat | bridge.py::heartbeat | cam | camera_bridge.py |
| GET /bridge/state | bridge.py::bridge_state | — | camera, luot_qua_cau.py |
| GET /bridge/cameras | bridge.py::cameras | — | camera.py, tong_quan.py, messages.py |
| POST /bridge/stream_frame/{camera_id} | bridge.py::upload_stream_frame | cam | camera_bridge.py |
| GET /bridge/stream_snapshot/{camera_id} | bridge.py::stream_snapshot | — | web, trình duyệt |
| GET /bridge/stream/{camera_id} | bridge.py::live_stream | — | web (MJPEG), trình duyệt |
| POST /bridge/reset | bridge.py::reset_bridge | manager | luot_qua_cau.py |
| GET /bridge/stats | bridge.py::bridge_stats | — | luot_qua_cau.py |
| POST /entry · /exit | counting.py | cam | camera cũ |
| POST /occupancy | counting.py::create_occupancy | cam | camera_bridge.py (camera 1) |
| GET /stats/occupancy · /stats/current · /stats/occupancy/history | counting.py | — | tong_quan.py |
| POST /facade_pass · GET /stats/facade | counting.py | cam / — | camera_bridge.py / web |
| POST /system_events | alerts.py::create_system_event | cam | camera_bridge.py |
| GET /system_events | alerts.py | — | truc_ca.py |
| GET /incidents | alerts.py | — | truc_ca.py, tong_quan.py, app (alert_watcher) |
| POST /incidents/{id}/ack · /close · /false_alarm | alerts.py | staff | truc_ca.py |
| POST /visit_events · GET /visit_events | demographics.py | cam / — | visitor_profiler.py / lich_su.py, google_sheets_sync.py |
| GET /stats/demographics | demographics.py | — | co_cau_khach.py |
| POST /region_stats · GET /stats/region | demographics.py | cam / — | camera cũ |
| POST /tickets · /tickets/bulk · DELETE /tickets/{id} | tickets.py | staff | doi_chieu_ve.py |
| GET /tickets · /tickets/reconciliation · /tickets/reconciliation_range | tickets.py | — | doi_chieu_ve.py, reports.py |
| GET /reports/summary · /reports/heatmap · /reports/daily · /reports/daily/{d}/pdf · /reports/weekly/pdf | reports.py | — | bao_cao.py |
| POST /reports/daily/{d}/send · /reports/weekly/send | reports.py | manager | bao_cao.py |
| GET /insights/live · /insights/summary | insights.py | — | tong_quan.py, bao_cao.py, messages.py, display.py |
| GET /config · PUT /config | admin.py | — / admin | camera, web |
| GET /recipients · /recipients/topics | admin.py | staff / — | nguoi_nhan.py |
| POST /recipients · PUT·DELETE /recipients/{id} · POST /recipients/{id}/test | admin.py | admin | nguoi_nhan.py |
| GET /privacy/summary · POST /privacy/purge | admin.py | manager / admin | quyen_rieng_tu.py |
| GET /telegram/status · PUT·DELETE /telegram/token · GET /telegram/chats | admin.py | admin | nguoi_nhan.py |
| GET /display/state | display.py | — | led.js |
| GET /led/... | main.py (StaticFiles) | — | trình duyệt LED |

Tài liệu tương tác: `http://<IP>:8000/docs`.

---

## 8. Cơ sở dữ liệu

SQLite `backend/smartcau.db`. Thời gian lưu **UTC** (trừ `bridge_crossings.local_time` lưu giờ Việt Nam).

| Bảng | Định nghĩa ở | Cột chính | Ghi bởi |
|---|---|---|---|
| `bridge_state` | routers/bridge.py::BridgeState | id=1, num1, num2, dem, dem_date, updated_at | record_crossing, reset |
| `bridge_crossings` | routers/bridge.py::BridgeCrossing | timestamp, local_time, camera_id, direction (in/out), track_id, onbridge_after | record_crossing |
| `camera_status` | routers/bridge.py::CameraStatus | camera_id, last_seen, source, fps, line, sends_alerts, demographics, started_at, machine | heartbeat |
| `occupancy_state` | models.py::OccupancyState | id=1, current_count | record_crossing |
| `occupancy_snapshots` | models.py::OccupancySnapshot | timestamp, count, status | POST /occupancy (camera 1) |
| `system_events` | models.py::SystemEvent | timestamp, event_type, count, message, camera_id | POST /system_events; lịch tự động (MORNING_BRIEF, TICKET_REMINDER, WEEKLY_REPORT) |
| `incidents` | routers/alerts.py::Incident | opened_at, peak_count, alert_count, acked_at/by, note, closed_at, close_reason, closed_by, false_alarm, false_note, false_by | alerts.py |
| `visit_events` | models.py::VisitEvent | track_id, timestamp, age, age_range, gender (Man/Woman/None), origin (Trong nuoc/Nuoc ngoai/None), camera_id | POST /visit_events |
| `facade_passes` | routers/counting.py::FacadePass | timestamp, camera_id (mỗi dòng = 1 lượt) | POST /facade_pass |
| `region_stats` | models.py::RegionStat | date, hour, region, count | camera cũ |
| `ticket_counts` | routers/tickets.py::TicketCount | date (YYYY-MM-DD), hour (NULL = cả ngày), ticket_count, entered_by, created_at | tickets.py |
| `daily_reports` | daily_report.py::DailyReport | date, data (JSON), total_entries, incidents, created_at, sent_at, delivery | daily_report.py |
| `recipients` | routers/admin.py::Recipient | name, channel, address (chat_id), active, created_at, topics | admin.py |
| `system_config` | models.py::SystemConfig | alert_threshold (20), open_time (07:00), close_time (21:30), updated_at/by, telegram_token | admin.py |
| `users` | models.py::User | username, full_name, password_hash, role, active, must_change_password, created_at, last_login | accounts.py |
| `auth_tokens` | models.py::AuthToken | token, user_id, created_at, expires_at | accounts.py |
| `audit_log` | models.py::AuditLog | timestamp, username, action, detail | log_audit |

**Thêm cột mới:** khai báo `Column(...)` trong lớp → khởi động backend → `ensure_schema` tự thêm. Không cần xóa tệp `.db`.

---

## 9. Tra cứu nhanh: lỗi ở đâu, sửa tệp nào

### Camera
| Hiện tượng / nguyên văn lỗi | Nguyên nhân thường gặp | Tệp cần xem |
|---|---|---|
| `cv2.error ... The function is not implemented` / `namedWindow` | OpenCV 5 hoặc bản headless | `ai_engine/camera_bridge.py::OPENCV_FIX_MSG`, `requirements.txt` (opencv-python>=4.9,<5) |
| `Chưa cài ultralytics` / `requests` | Thiếu thư viện | `pip install -r requirements.txt` |
| `[LỖI NHẬN DIỆN] Không nạp được DeepFace` / thanh dưới "Nhận diện: LỖI DeepFace" | DeepFace / TensorFlow / Keras chưa đúng | `ai_engine/age_gender_estimator.py::_load_deepface`; README mục DeepFace |
| Không hiện Nam/Nữ, chỉ "ID n" | Chạy `--no-demographics`, hoặc DeepFace lỗi | `camera_bridge.py::parse_args`, `main` (khối `ai_status`) |
| Dưới khung người mãi "Đang nhận diện…" / "Lại gần camera hơn" / "Chờ nhìn thẳng" / "Hình bị nhòe" | Mặt nhỏ, nghiêng, nhòe | `visitor_profiler.py::face_quality` (`MIN_EYE_PX`, `MIN_SHARPNESS`), cờ `--no-face-gate` |
| Giới tính / tuổi sai nhiều | Mô hình, ánh sáng, mặt nhỏ | `age_gender_estimator.py::align_face_from_keypoints`, `estimate_from_aligned_face` (`TTA_BELOW`), `demographics_engine.py` (`CONFIDENCE_THRESHOLD`, `MIN_VOTES_BEFORE_READY`, trọng số phiếu), `docs/AI_CAI_THIEN.md`, `tools/eval_demographics.py` |
| Nhận diện chậm (`mặt xx ms` cao) | Máy yếu, đang ước lượng nguồn khách | `--no-origin`; `demographics_engine.RACE_VOTES`; `visitor_profiler.ready_interval` |
| Nguồn khách sai | Ước lượng thô từ chủng tộc | `visitor_profiler.py::REGION_TO_ORIGIN`, `ORIGIN_MIN_SHARE`, `region_mapping.py` |
| Camera giật / chậm, `AI xx ms/khung` cao | Máy yếu | `--imgsz 480`, `--max-width`, `--no-origin`; `camera_bridge.py` vòng lặp; `camera_ui.py::TextLayer.render` |
| Hình trễ so với thực tế | Bộ đệm webcam | `camera_backend.py::LatestFrameReader` |
| Không mở được webcam USB / camera điện thoại | Sai số webcam, khác Wi-Fi, app chưa Start | `python tools/tim_camera.py`, `camera_backend.resolve_source`, `docs/CAMERA_NGOAI.md` |
| Đếm sai vào / ra, đếm 2 lần | Vạch, hướng phía cầu, tracker mất ID | `line_crossing.py::LineCrossingCounter.update`, `camera_bridge.py::draw_line_setup`, `trackers/smartcau_botsort.yaml`, `--conf` |
| Bấm phím kẻ vạch không ăn | Chưa click vào cửa sổ camera | `camera_bridge.py` (xử lý phím cuối vòng lặp, `on_main_mouse`) |
| "MẤT KẾT NỐI SERVER" trên camera | Sai IP, tường lửa, backend chưa `--host 0.0.0.0` | `camera_bridge.py::Net`, `tools/kiem_tra_mang.py`, `docs/TRIEN_KHAI_NHIEU_MAY.md` |
| `[API] /... trả về 401` | Máy chủ đặt `SMARTCAU_API_KEY` mà camera thiếu `--api-key` | `backend/security.py::require_api_key` |
| Chữ trên camera không có dấu | Không tìm thấy font | `camera_ui.py::_FONT_CANDIDATES`, biến `SMARTCAU_FONT` |
| Camera 2 không gây cảnh báo | Đúng thiết kế: chỉ camera 1 gửi mức | `camera_bridge.py::parse_args` (`send_alerts`) |

### Số liệu / cảnh báo
| Hiện tượng | Tệp |
|---|---|
| onbridge âm, num1/num2 không về 0, dem không reset | `backend/routers/bridge.py::record_crossing`, `_roll_day` |
| Vàng / Đỏ lên sai lúc, không tự hết Đỏ | `ai_engine/crowd_counter.py::AlertLevelTracker`, `CameraThresholds.from_alert_threshold` |
| Sự cố không tự đóng / không mở | `backend/routers/alerts.py::create_system_event`, `_open_incident`, `_close` |
| Đổi sức chứa trên web mà camera không đổi | `camera_bridge.py::Net._poller` (15 giây), `admin.update_config` |
| Giờ thống kê lệch 7 tiếng | `backend/timeutil.py`, `SMARTCAU_UTC_OFFSET_HOURS`; thống kê phải dùng `local_time` / `to_local` |
| Tổng quan báo mức cũ / "chưa nhận mức cảnh báo" | Camera 1 không gửi `/occupancy` trong 30 giây — `counting.py::current_stats` |
| Dự báo / thời gian chờ lạ | `backend/routers/insights.py::live`, `_hourly_profile` |
| KPI O1/O4/O5/O8 sai | `backend/routers/reports.py::report_summary` (khối `kpis`), `tickets.py::reconciliation` |
| Biểu đồ nhiệt không khớp | `reports.py::heatmap` (dùng `local_time`) |
| Chênh lệch vé sai | `tickets.py::reconciliation` (`compared_entries`) |

### Web
| Hiện tượng / nguyên văn lỗi | Tệp |
|---|---|
| `ImportError: cannot import name ... from 'common'` | Streamlit giữ module cũ: tắt hẳn và chạy lại Streamlit; hàm có trong `frontend/common.py` |
| CSS hiện ra thành chữ ở đầu trang | Dòng trống trong `<style>` — `frontend/common.py::_THEME_CSS` |
| Ô nhập xấu / mất viền | `.streamlit/config.toml` (`showWidgetBorder`), CSS trong `common.py` |
| F5 bị đăng xuất | `common.restore_session` (token ở `?s=` trên URL) |
| Đăng xuất còn sót menu | `frontend/app.py` (khối chưa đăng nhập dùng `st.navigation(..., position="hidden")`) |
| Trang không có trong menu / sai quyền | `frontend/app.py::PAGES` và `backend/security.py` |
| Hộp đỏ "Không kết nối được máy chủ" | `common._call` / `safe_get`; backend chưa chạy hoặc sai `SMARTCAU_API` |
| `use_container_width` deprecated | Dùng `width="stretch"` |
| Lỗi trên một trang cụ thể | Tệp `frontend/views/<trang>.py` (bảng mục 5.19), API ở mục 7 |
| Tải PDF lỗi / PDF mất dấu / sai font | `backend/report_export.py::to_pdf`, `FONT_SETS`, biến `SMARTCAU_FONT` (+ `SMARTCAU_FONT_BOLD`) |
| PDF thiếu biểu đồ | Chưa cài `matplotlib`, hoặc tắt "Kèm biểu đồ" — `report_export.chart_*` |
| Sai tên cơ quan / địa danh trên PDF | Ô "Cơ quan chủ quản / Đơn vị" ở trang Báo cáo, hoặc `SMARTCAU_ORG_PARENT`, `SMARTCAU_ORG_NAME`, `SMARTCAU_ORG_PLACE` |
| Đối chiếu vé: tệp tải lên báo sai định dạng | `frontend/views/doi_chieu_ve.py` (cột `date`, `hour`, `ticket_count`) |
| Google Sheets lỗi 403 / SERVICE_DISABLED | Chưa chia sẻ Sheet cho email service account / chưa bật API — `dong_bo_sheets.py`, `tools/google_sheets_sync.py` |

### Bảng LED
| Hiện tượng | Tệp |
|---|---|
| Trang trắng / không có số | `led.js::poll` gọi `/display/state`; tường lửa cổng 8000; `&api=` |
| "Chạm để bắt đầu" che màn hình | Trình duyệt chặn tự phát — `led.js::needTap`; `led.css` có `[hidden]{display:none!important}` |
| Mascot nền xanh / không trong suốt | Không phải Chrome / Edge, hoặc clip chưa xử lý — `backend/led_display/media/*.webm` |
| Nhân vật nhảy vị trí khi đi vào / ra | `CONFIG.clips.<ai>.walkOn/walkOff.shift`, `arrive`, `from`; hằng `STATIC_W`, `CROP_X`, `WIDE_W` |
| Câu thoại / thời gian / cảnh sai | `CONFIG.lines`, `CONFIG.timing`, `CONFIG.scenes`, `CONFIG.clock`, `dayStart/dayEnd` |
| Đổi vai nhân vật mỗi đầu cầu | `CONFIG.ends` |
| Tab LED trong web chỉ có 1 màn | Đang chạy code cũ (tên trang cũ "Bảng LED tại chỗ") — pull rồi chạy lại Streamlit; `frontend/views/bang_led.py` |

### Telegram / tự động
| Hiện tượng / nguyên văn | Tệp |
|---|---|
| "Chưa kết nối bot Telegram" | `notify.NO_TOKEN`; dán token ở trang Người nhận (`admin.set_telegram_token`) |
| `Unauthorized` khi dán token | Token sai — `admin.set_telegram_token` (gọi `getMe`) |
| Không nhận được tin | Người nhận tắt, chưa chọn loại tin, ngoài giờ mở cửa (Vàng / đoàn khách) — `admin.active_recipients`, `alerts.TOPIC_OF`, `NOTIFY_IN_HOURS` |
| Tin hiện thẻ `<b>` thô | `parse_mode` HTML — `notify._send_telegram`; ký tự `<` `>` `&` chưa `escape` trong `messages.py` |
| Bot không trả lời lệnh | Luồng bot chưa chạy (`SMARTCAU_DISABLE_SCHEDULER` / `SMARTCAU_DISABLE_BOT`), chat chưa có trong người nhận — `telegram_bot.py` |
| Nút "Đã xử lý" báo "chưa có trong danh sách" | Chat_id chưa thêm vào người nhận — `telegram_bot._allowed` |
| Trang Người nhận không tìm thấy chat | Khi bot chạy, danh sách lấy từ `telegram_bot.SEEN` — `admin.telegram_chats` |
| Báo cáo ngày / tuần / bản tin sáng không gửi | `daily_report.run_due` (giờ mở / đóng cửa trong `system_config`), `_once` (đã gửi hôm nay chưa — xem bảng `system_events`), backend có chạy lúc đó không |
| Báo cáo ngày ghi "Chưa gửi được: ..." | Lý do in trong cột `delivery` — `daily_report._deliver` |
| Sheets tự đồng bộ không chạy | Chưa cấu hình / tắt công tắc / thiếu `gspread` / backend khác máy với web — `backend/sheets_auto.py` |

### Mạng nhiều máy
| Hiện tượng | Xử lý |
|---|---|
| Máy khác không vào được `http://IP:8501` | Tường lửa (luật Block của python.exe), mạng trường chặn máy nói chuyện với nhau → dùng điểm phát điện thoại; `docs/TRIEN_KHAI_NHIEU_MAY.md`, `tools/kiem_tra_mang.py` |
| `ConnectionResetError: [WinError 10054]` trong cửa sổ Streamlit | Vô hại (trình duyệt đóng kết nối), bỏ qua |

---

## 10. Quy ước code và những điều không được phá

1. **Mã lưu CSDL không đổi**: giới tính `Man`/`Woman`, nguồn khách `Trong nuoc`/`Nuoc ngoai`, mức `OK`/`WARNING`/`ALERT`/`CRITICAL`, loại sự kiện `WARNING`/`CRITICAL_ALERT`/`CRITICAL_CLEARED`/`GROUP_DETECTED`/`CAMERA_LOST`/`CAMERA_RESTORED`. Chữ hiển thị nằm ở `GENDER_VI`, `ORIGIN_VI`, `EVENT_LABELS`, `STATUS_META`, `LEVEL`.
2. **Thời gian**: lưu UTC (`datetime.utcnow()`), hiển thị / thống kê theo giờ Việt Nam qua `backend/timeutil.py` hoặc `common.to_local`.
3. **Chữ trên giao diện có dấu tiếng Việt**; chú thích trong code viết không dấu.
4. **Không đưa ghi chú, hướng dẫn, mã FR/BRULE lên giao diện web**; ghi vào `docs/GHI_CHU_GIAO_DIEN.md`.
5. **Camera không được chờ mạng**: mọi gọi máy chủ trong vòng lặp phải qua `Net.post` / `Net` poller.
6. **DeepFace không chạy trên luồng camera**: dùng `AsyncEngine`.
7. **Tin Telegram là HTML**: chữ do người dùng nhập phải `html.escape`.
8. **Gửi Telegram cho người nhận phải truyền loại tin**: `active_recipients(db, "<topic>")`.
9. **Việc tự động chạy 1 lần**: dùng `daily_report._once`.
10. **Thêm bảng / cột**: khai báo trong lớp SQLAlchemy; `ensure_schema` tự thêm cột. Bảng mới phải được import trước `ensure_schema()` (thường là import router trong `backend/main.py`).
11. **Thêm trang web**: tạo `frontend/views/<ten>.py`, thêm 1 dòng vào `PAGES` trong `frontend/app.py`, dùng `page_header`, `section`, `kpi`, `safe_get` của `common.py`; dùng `width="stretch"` thay `use_container_width`.
12. **Thêm API**: viết trong router tương ứng, gắn quyền bằng `Depends(require_*)`, thêm test vào `tests/test_api.py`.
13. **Chạy test trước khi đẩy code**: `pytest -q` phải xanh.
14. Sau khi `git pull`, **tắt hẳn và chạy lại** backend, Streamlit và camera.

---

## 11. Kiểm thử

Chạy: `pytest -q` (72 test). `tests/test_api.py` dùng CSDL trong bộ nhớ và thay `notify.deliver*` bằng hàm ghi vào danh sách `SENT` / `DOCS` (không gửi Telegram thật).

| Tệp test | Kiểm tra |
|---|---|
| `tests/test_api.py` | Đăng nhập / quyền / tài khoản; kỳ báo cáo ngày / tuần / tháng / năm / tùy chọn; đối chiếu vé theo khoảng ngày; cấu hình & nhật ký; người nhận & loại tin; quyền riêng tư; vòng đời sự cố; nhãn sự kiện; quy tắc đếm 2 camera, reset ngày, thống kê; nhịp tim camera; mặt tiền; cơ cấu khách; báo cáo & KPI; đối chiếu vé; báo sai; biểu đồ nhiệt; báo cáo ngày tự động; kết nối Telegram; insights; bảng LED (16 clip); tin Telegram có tình hình; bot lệnh + nút Đã xử lý; bản tin sáng & nhắc vé không lặp; báo cáo tuần; Sheets chưa cấu hình |
| `tests/test_crowd_counter.py` | Ngưỡng 15/20, Đỏ sau 15 giây, hết Đỏ sau 15 giây, nhắc lại 3 phút |
| `tests/test_line_crossing.py` | Vào / ra qua vạch, chống rung, lưu / đọc vạch; cách gõ tắt `--source` (`phone:`, `droidcam:`, IP) |
| `tests/test_group_facade.py` | Đoàn khách, lượt mặt tiền |
| `tests/test_visitor_profiler.py` | Lưu hồ sơ khi vào cầu, "Không xác định" sau 5 giây, nhãn hiển thị, cổng chất lượng mặt |
| `tests/test_eval_tools.py` | Công cụ đo độ chính xác |
| `tests/test_face_align.py` | Cắt mặt theo keypoint, bỏ bước tìm mặt, lật ảnh khi chưa chắc, trọng số phiếu, dừng ước lượng chủng tộc khi đủ |
