"""
camera_bridge.py  —  Camera tai 1 CHAN CAU (dung chung cho camera 1 va camera 2)
================================================================================
Phu trach: MINH.   Chuc nang: F1.1-F1.4, F2.1-F2.3, F3.1, F3.2 (FR-01..FR-09, FR-16)

Moi chan cau dat 1 camera, quay tu cau RA chan cau, vuong goc voi cau. Tren
hinh ke 1 vach ngang qua loi di. Khi khach qua vach:
    tu phia ngoai vao phia cau -> "in"  -> server: num_k += 1, dem += 1
    tu phia cau ra phia ngoai  -> "out" -> server: num_k -= 1
Server tinh onbridge = num1 + num2 (xem backend/routers/bridge.py).

Them:
  - Nguoi chi di ngang phia ngoai, khong qua vach -> 1 luot mat tien (F1.4)
  - Doan >= 10 nguoi cung di toi cau trong 10 giay -> canh bao doan khach (F3.1)
  - Nhan dien (MAC DINH BAT): hien Nam/Nu, khoang tuoi, Trong nuoc/chau A - Quoc te
    canh khung nguoi va luu cho khach VAO cau (F3.2, xem visitor_profiler.py).
    Tat bang --no-demographics.
  - Gui / doc may chu chay o LUONG NEN: mang LAN cham hay mat ket noi khong lam
    camera giat (truoc day moi lan goi API cho toi 2 giay -> chi con ~1 khung/giay).
  - Camera 1 xac dinh muc Vang/Do va bao server; server gui Telegram (F2)
  - Mat tin hieu camera -> bao server ngay, tu ket noi lai (NFR-03)

CHAY (tu THU MUC GOC Cap2/, backend phai chay truoc):
    python ai_engine/camera_bridge.py --camera-id 1 --source 0
    python ai_engine/camera_bridge.py --camera-id 2 --source 1 --api http://192.168.1.10:8000
    python ai_engine/camera_bridge.py --camera-id 2 --source video_chan_cau_2.mp4
    python ai_engine/camera_bridge.py --camera-id 1 --source rtsp://user:pass@ip/stream

KE VACH (FR-01): mac dinh vach ngang giua hinh, phia cau = nua duoi. Nhan
L (hoac chuot phai) de ve lai bang chuot: click 2 dau vach, roi click 1 diem o PHIA CAU.
Vach luu o ai_engine/config/line_cam<id>.json.

Tuy chon:
    --no-demographics  tat nhan dien gioi tinh / tuoi / nguon khach (chi dem nguoi, nhanh hon)
    --no-origin      bo uoc luong Trong nuoc/chau A - Quoc te cho nhanh hon
    --no-alerts      camera 1 khong gui muc canh bao (mac dinh chi camera 1 gui)
    --group-size     so nguoi toi thieu cua 1 doan (mac dinh 10, BRULE-03)
    --model          model YOLO (mac dinh yolov8n-pose.pt, hoac yolov8n.pt khi --no-demographics).
                     May manh: yolov8s.pt / yolo11s.pt (pose: yolov8s-pose.pt) chinh xac hon
    --imgsz 960      anh vao YOLO lon hon -> dem tot hon nguoi o xa, dong (mac dinh 640)
    --face-detector  yunet (mac dinh) | retinaface (chinh xac nhat, cham) | mtcnn | opencv
    Xem docs/AI_CAI_THIEN.md de chon cau hinh theo may.

Phim (click vao cua so camera truoc): L / so 1 / chuot phai = ke lai vach · R = vach mac dinh · Q = thoat.
"""

import argparse
import os
import queue
import sys
import threading
import time

import cv2

try:
    import requests
except ImportError:
    print("Chưa cài requests. Chạy: pip install requests")
    sys.exit(1)

try:
    from ultralytics import YOLO
except ImportError:
    print("Chưa cài ultralytics. Chạy: pip install ultralytics")
    sys.exit(1)

from camera_backend import LatestFrameReader, is_network_source, open_camera, resolve_source
from camera_ui import TextLayer, draw_person_box, panel_lines, vietnamese_text_supported
from crowd_counter import AlertLevelTracker, CameraThresholds
from group_detector import GroupDetector
from line_crossing import FacadeCounter, LineCrossingCounter, foot_point
from telegram_alert import trigger_buzzer_signal
from visitor_profiler import VisitorProfiler, extract_keypoints

API_BASE = os.environ.get("SMARTCAU_API", "http://127.0.0.1:8000")   # doi bang --api khi may chu la may khac
API_KEY = os.environ.get("SMARTCAU_API_KEY", "")
_HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

STATE_POLL_SEC = 1.0      # doc onbridge (gom ca camera kia)
CONFIG_POLL_SEC = 15.0    # doc nguong Admin dat
REPORT_SEC = 2.0          # gui so nguoi + muc canh bao (NFR-01)
HEARTBEAT_SEC = 5.0       # nhip tim -> trang "Camera" biet camera con song (NFR-03)
ALERT_REPEAT_SEC = 180.0  # BRULE-04
RECONNECT_SEC = 3.0

OPENCV_FIX_MSG = """
[LỖI] OpenCV {ver} trên máy này không mở được cửa sổ camera.
Nguyên nhân: đang cài lẫn bản OpenCV 5 hoặc bản "headless" (không có giao diện),
thường do pip cài kèm khi cài DeepFace / YOLO. Cách sửa (chạy trong .venv):

  1) pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python opencv-contrib-python-headless
     (chạy lại lệnh này đến khi cả 4 gói đều báo "not installed")
  2) pip install --force-reinstall --no-deps "opencv-python>=4.9,<5"
  3) python -c "import cv2; print(cv2.__version__); cv2.namedWindow('test'); print('OK')"
"""

MACHINE = __import__("platform").node() or "?"
LEVEL_VI = {"OK": "Bình thường", "WARNING": "Cảnh báo Vàng", "ALERT": "Vàng · đang xác nhận 15 giây",
            "CRITICAL": "CẢNH BÁO ĐỎ · QUÁ TẢI"}
LEVEL_BGR = {"OK": (80, 160, 60), "WARNING": (0, 170, 240), "ALERT": (0, 120, 255), "CRITICAL": (40, 40, 210)}
GREEN, ORANGE, YELLOW = (90, 200, 90), (0, 150, 255), (0, 230, 255)


# ------------------------------------------------------------------ API
def _post(path, payload):
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, headers=_HEADERS, timeout=2)
        if r.status_code == 200:
            return r.json()
        print(f"[API] {path} trả về {r.status_code}: {r.text[:120]}")
    except requests.RequestException as e:
        print(f"[API] Không gửi được {path}: {e}")
    return None


def _post_bytes(path, data, content_type="image/jpeg"):
    try:
        h = dict(_HEADERS)
        h["Content-Type"] = content_type
        requests.post(f"{API_BASE}{path}", data=data, headers=h, timeout=1.5)
    except requests.RequestException:
        pass


def _get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=2)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


class Net:
    """Moi lan gui / doc may chu chay o luong nen, vong lap camera khong bao gio phai cho mang.
    - post(): xep hang roi gui lan luot (day hang thi bo ban tin cu nhat).
    - send_stream_frame(): cap nhat khung hinh live moi nhat de stream ve web.
    - Luong doc: moi STATE_POLL_SEC doc /bridge/state, moi CONFIG_POLL_SEC doc nguong /config."""

    def __init__(self, enable_stream=True):
        self.q = queue.Queue(maxsize=300)
        self.state = None
        self.alert_threshold = None
        self.ok = True
        self.enable_stream = enable_stream
        self._stream_frames = {}
        self._stream_lock = threading.Lock()
        threading.Thread(target=self._sender, daemon=True, name="net-send").start()
        threading.Thread(target=self._poller, daemon=True, name="net-poll").start()
        if self.enable_stream:
            threading.Thread(target=self._streamer, daemon=True, name="net-stream").start()

    def post(self, path, payload):
        try:
            self.q.put_nowait((path, payload))
        except queue.Full:
            try:
                self.q.get_nowait()
            except queue.Empty:
                pass
            self.q.put_nowait((path, payload))

    def send_stream_frame(self, camera_id: int, jpeg_bytes: bytes):
        if not self.enable_stream:
            return
        with self._stream_lock:
            self._stream_frames[camera_id] = jpeg_bytes

    def _streamer(self):
        while True:
            time.sleep(0.08)  # ~12 FPS
            to_send = {}
            with self._stream_lock:
                if self._stream_frames:
                    to_send = dict(self._stream_frames)
                    self._stream_frames.clear()
            for cam_id, data in to_send.items():
                _post_bytes(f"/bridge/stream_frame/{cam_id}", data)

    def _sender(self):
        while True:
            path, payload = self.q.get()
            res = _post(path, payload)
            if path == "/bridge/crossing" and res:
                self.state = res

    def _poller(self):
        last_cfg = 0.0
        while True:
            s = _get("/bridge/state")
            self.ok = s is not None
            if s:
                self.state = s
            if time.time() - last_cfg >= CONFIG_POLL_SEC:
                c = _get("/config")
                if c and c.get("alert_threshold"):
                    self.alert_threshold = c["alert_threshold"]
                last_cfg = time.time()
            time.sleep(STATE_POLL_SEC)


# ------------------------------------------------------------- ke vach
def _line_path(camera_id):
    return os.path.join(CONFIG_DIR, f"line_cam{camera_id}.json")


def load_line(camera_id) -> LineCrossingCounter:
    path = _line_path(camera_id)
    if os.path.exists(path):
        try:
            line = LineCrossingCounter.load(path)
            print(f"[CAMERA {camera_id}] Đã đọc vạch kẻ từ {path}")
            return line
        except Exception as e:
            print(f"[CAMERA {camera_id}] File vạch kẻ lỗi ({e}) -> dùng vạch mặc định.")
    print(f"[CAMERA {camera_id}] Dùng vạch mặc định (ngang giữa hình, phía cầu = nửa dưới). Nhấn 'l' để kẻ lại.")
    return LineCrossingCounter()


def draw_line_setup(cap, window, camera_id, restore_cb=None):
    """Ke lai vach bang chuot: click 2 dau vach, roi click 1 diem o PHIA CAU.
    Vach hien xem truoc theo con tro. Esc / chuot phai = huy."""
    clicks, cursor, cancel = [], [None], [False]

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE:
            cursor[0] = (x, y)
        elif event == cv2.EVENT_LBUTTONDOWN and len(clicks) < 3:
            clicks.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN:
            cancel[0] = True

    cv2.setMouseCallback(window, on_mouse)
    hints = ["Bước 1/3 · Click ĐẦU THỨ NHẤT của vạch", "Bước 2/3 · Click ĐẦU THỨ HAI của vạch",
             "Bước 3/3 · Click 1 điểm ở PHÍA CẦU"]
    frame, layer = None, TextLayer()

    def done(result):
        cv2.setMouseCallback(window, restore_cb or (lambda *a: None))
        return result

    while len(clicks) < 3:
        ok, f = cap.read()
        if ok:
            frame = f
        if frame is None:
            continue
        out = frame.copy()
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (out.shape[1], out.shape[0]), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.35, out, 0.65, 0, dst=out)
        for p in clicks:
            cv2.circle(out, p, 7, YELLOW, -1)
        if len(clicks) == 1 and cursor[0]:
            cv2.line(out, clicks[0], cursor[0], YELLOW, 2, cv2.LINE_AA)
        if len(clicks) >= 2:
            cv2.line(out, clicks[0], clicks[1], YELLOW, 3, cv2.LINE_AA)
        if cursor[0]:
            cv2.drawMarker(out, cursor[0], (255, 255, 255), cv2.MARKER_CROSS, 18, 1)
        layer.text(f"KẺ VẠCH CAMERA {camera_id} · {hints[len(clicks)]}", (14, 12), size=19, bold=True,
                   bg=(30, 30, 30))
        layer.text("Esc hoặc chuột phải: hủy", (14, 48), size=14, bg=(30, 30, 30))
        layer.render(out)
        cv2.imshow(window, out)
        if (cv2.waitKey(30) & 0xFF) == 27 or cancel[0]:
            print(f"[CAMERA {camera_id}] Đã hủy kẻ vạch.")
            return done(None)
    h, w = frame.shape[:2]
    p1, p2, b = [(x / w, y / h) for x, y in clicks]
    try:
        line = LineCrossingCounter(p1=p1, p2=p2, bridge_point=b)
    except ValueError as e:
        print(f"[CAMERA {camera_id}] Vạch không hợp lệ: {e}")
        return done(None)
    line.save(_line_path(camera_id))
    print(f"[CAMERA {camera_id}] Đã lưu vạch kẻ vào {_line_path(camera_id)}")
    return done(line)


def draw_line_overlay(frame, layer, line: LineCrossingCounter):
    h, w = frame.shape[:2]
    p1 = (int(line.p1[0] * w), int(line.p1[1] * h))
    p2 = (int(line.p2[0] * w), int(line.p2[1] * h))
    cv2.line(frame, p1, p2, YELLOW, 3, cv2.LINE_AA)
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    nx, ny = -dy / length, dx / length
    if line.signed_distance(((mx + nx * 10) / w, (my + ny * 10) / h)) < 0:
        nx, ny = -nx, -ny
    tip = (int(mx + nx * 55), int(my + ny * 55))
    cv2.arrowedLine(frame, (int(mx), int(my)), tip, YELLOW, 3, tipLength=0.3)
    layer.text("VÀO CẦU", (tip[0] + 8, tip[1] - 10), size=18, bold=True, color=(20, 20, 20), bg=YELLOW, pad=4)


def draw_hud(frame, layer, cam, state, level, thresholds, local_in, local_out, facade, fps, api_ok, group_size,
             ai_status=""):
    fh, fw = frame.shape[:2]
    onbridge = int(state.get("onbridge", 0))
    big = 19 if fw >= 900 else 16
    small = 16 if fw >= 900 else 13
    cv2.rectangle(frame, (0, 0), (fw, big + 26), (25, 25, 25), -1)
    cv2.rectangle(frame, (0, 0), (7, big + 26), LEVEL_BGR[level], -1)
    x = 16
    for text, kw in ((f"CAMERA {cam}", {"bold": True}),
                     (f"Trên cầu: {onbridge}/{thresholds.alert}", {"bold": True}),
                     (LEVEL_VI[level], {"bold": True, "bg": LEVEL_BGR[level], "pad": 4})):
        layer.text(text, (x, 12), size=big, **kw)
        x += layer.measure(text, big, True)[0] + 22
    if not api_ok:
        t = "MẤT KẾT NỐI SERVER"
        layer.text(t, (fw - layer.measure(t, small, True)[0] - 14, 12), size=small, bold=True, bg=(40, 40, 200), pad=4)
    stats = (f"Hôm nay {state.get('dem', 0)} lượt vào cầu · Camera này: vào {local_in} / ra {local_out} · "
             f"Mặt tiền {facade} · {fps:.0f} khung/giây" + (f" · {ai_status}" if ai_status else ""))
    while layer.measure(stats, small)[0] > fw - 24 and small > 10:
        small -= 1
    layer.text(stats, (12, fh - small - 16), size=small, bg=(25, 25, 25), pad=6)
    hint = "L / chuột phải: kẻ vạch · R: mặc định · Q: thoát"
    hs = max(11, small - 2)
    layer.text(hint, (fw - layer.measure(hint, hs)[0] - 16, big + 34), size=hs, color=(220, 220, 220),
               bg=(25, 25, 25), pad=4)
    if group_size >= 5:
        layer.text(f"Nhóm {group_size} người đang đi tới", (12, big + 36), size=small + 1, bold=True, bg=ORANGE, pad=5)
    if level == "CRITICAL":
        bh = 64
        y0 = fh // 2 - bh // 2
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, y0), (fw, y0 + bh), (30, 30, 200), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, dst=frame)
        msg = f"QUÁ TẢI · {onbridge}/{thresholds.alert} người trên cầu · TẠM DỪNG CHO KHÁCH LÊN"
        size = 22
        while layer.measure(msg, size, True)[0] > fw - 24 and size > 12:
            size -= 1
        layer.text(msg, (fw // 2, y0 + 20), size=size, bold=True, anchor="mt")


# ------------------------------------------------------------------ main
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Camera chân cầu - SmartCau AI")
    ap.add_argument("--camera-id", type=int, choices=(1, 2), required=True)
    ap.add_argument("--api", default=None,
                    help="Dia chi may chu khi chay nhieu may, vd http://192.168.1.10:8000 (mac dinh SMARTCAU_API hoac 127.0.0.1)")
    ap.add_argument("--api-key", default=None, help="Khoa camera neu may chu dat SMARTCAU_API_KEY")
    ap.add_argument("--source", default="0",
                    help="Webcam: 0 (laptop), 1, 2 (webcam USB). Điện thoại: phone:<IP> (IP Webcam), "
                         "droidcam:<IP> (DroidCam), hoặc http://... / rtsp://... ; cũng nhận đường dẫn tệp video. "
                         "Dò camera đang có: python tools/tim_camera.py")
    ap.add_argument("--cam-res", default="1280x720", help="Độ phân giải xin webcam (mặc định 1280x720)")
    ap.add_argument("--demographics", action="store_true", help="(Mặc định đã bật, giữ để lệnh cũ vẫn chạy)")
    ap.add_argument("--no-demographics", action="store_true",
                    help="Tắt nhận diện giới tính / tuổi / nguồn khách, chỉ đếm người")
    ap.add_argument("--no-origin", action="store_true", help="Bỏ ước lượng trong/ngoài nước")
    ap.add_argument("--no-alerts", action="store_true", help="Camera này không gửi mức cảnh báo")
    ap.add_argument("--group-size", type=int, default=10)
    ap.add_argument("--model", default=None)
    ap.add_argument("--imgsz", type=int, default=640,
                    help="Kich thuoc anh dua vao YOLO. 960 hoac 1280 dem tot hon nguoi o xa / dong (cham hon)")
    ap.add_argument("--max-width", type=int, default=1280,
                    help="Thu nho khung hinh rong hon muc nay truoc khi xu ly (1080p -> 1280). 0 = giu nguyen")
    ap.add_argument("--conf", type=float, default=0.35, help="Nguong tin cay phat hien nguoi")
    ap.add_argument("--tracker", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      "trackers", "smartcau_botsort.yaml"),
                    help="Tep cau hinh bo theo doi (botsort.yaml / bytetrack.yaml / tep rieng)")
    ap.add_argument("--face-detector", default=os.environ.get("SMARTCAU_FACE_DETECTOR", "yunet"),
                    choices=("yunet", "retinaface", "mtcnn", "opencv", "ssd", "mediapipe"),
                    help="Bo tim khuon mat cua DeepFace. retinaface chinh xac nhat nhung cham nhat")
    ap.add_argument("--no-face-gate", action="store_true",
                    help="Tat cong chat luong mat (mac dinh chi phan tich khi mat du to, nhin thang, khong nhoe)")
    ap.add_argument("--no-stream", action="store_true",
                    help="Tat live stream khung hinh truc tiep len Web Streamlit qua may chu")
    args = ap.parse_args(argv)
    args.demographics = not args.no_demographics
    args.stream = not args.no_stream
    if args.model is None:
        args.model = "yolov8n-pose.pt" if args.demographics else "yolov8n.pt"
    args.source = resolve_source(args.source)
    try:
        w, h = (int(v) for v in args.cam_res.lower().split("x"))
        args.cam_res = (w, h)
    except ValueError:
        ap.error("--cam-res phải có dạng 1280x720")
    args.send_alerts = (args.camera_id == 1) and not args.no_alerts
    args.is_file = isinstance(args.source, str) and os.path.isfile(args.source)
    return args


def main():
    args = parse_args()
    global API_BASE, _HEADERS
    if args.api:
        API_BASE = args.api.rstrip("/")
    if args.api_key:
        _HEADERS = {"X-API-Key": args.api_key}
    cam = args.camera_id
    if not _get("/health"):
        print(f"[CAMERA {cam}] KHÔNG kết nối được máy chủ {API_BASE}. Kiểm tra: máy chủ đã chạy "
              "'uvicorn backend.main:app --host 0.0.0.0 --port 8000', cùng mạng Wi-Fi, tường lửa mở cổng 8000. "
              "Thử: python tools/kiem_tra_mang.py " + API_BASE)
    else:
        print(f"[CAMERA {cam}] Đã kết nối máy chủ {API_BASE}.")
    window = f"SmartCau AI - Camera chan cau {cam}"
    if not vietnamese_text_supported():
        print("[CẢNH BÁO] Không tìm thấy font tiếng Việt - chữ trên camera sẽ không có dấu. "
              "Đặt biến SMARTCAU_FONT=<đường dẫn .ttf> hoặc cài Pillow.")

    thresholds = CameraThresholds()
    remote = (_get("/config") or {}).get("alert_threshold")
    if remote:
        thresholds = CameraThresholds.from_alert_threshold(remote)
    tracker = AlertLevelTracker(thresholds, repeat_sec=ALERT_REPEAT_SEC)
    groups = GroupDetector(min_size=args.group_size)
    facade = FacadeCounter()

    profiler = None
    ai_status = "Nhận diện: TẮT (--no-demographics)"
    if args.demographics:
        import age_gender_estimator
        age_gender_estimator.DEFAULT_DETECTOR = args.face_detector
        print(f"[CAMERA {cam}] Đang nạp DeepFace (lần đầu có thể mất 10–30 giây)...")
        ok_df, _err = age_gender_estimator.deepface_status()
        if not ok_df:
            print(f"[CAMERA {cam}] DeepFace lỗi -> camera vẫn ĐẾM người bình thường nhưng KHÔNG nhận diện "
                  "giới tính / tuổi. Sửa theo hướng dẫn ở trên rồi chạy lại.")
            ai_status = "Nhận diện: LỖI DeepFace (xem cửa sổ lệnh)"
        else:
            ai_status = ""
            print(f"[CAMERA {cam}] Nhận diện giới tính, tuổi{'' if args.no_origin else ', trong nước/châu Á - quốc tế'}: BẬT.")

    net = Net(enable_stream=args.stream)
    if args.demographics and not ai_status:
        profiler = VisitorProfiler(post=net.post, with_origin=not args.no_origin, camera_id=cam,
                                   quality_gate=not args.no_face_gate)
    model = YOLO(args.model)
    line = load_line(cam)
    def open_src(warm=2.0):
        c = open_camera(args.source, warmup_sec=warm, resolution=args.cam_res)
        # webcam / RTSP: doc o luong rieng, luon lay khung MOI NHAT (het tre hinh khi AI cham)
        return c if args.is_file or not c.isOpened() else LatestFrameReader(c)

    cap = open_src()
    if not cap.isOpened():
        print(f"Không mở được camera/video: {args.source}")
        if is_network_source(args.source):
            print("  - Điện thoại và máy này phải cùng mạng Wi-Fi; ứng dụng camera trên điện thoại đang bật (Start server).\n"
                  "  - Thử mở địa chỉ trên bằng trình duyệt của máy này: thấy hình là đúng.\n"
                  "  - IP Webcam: phone:<IP>  ·  DroidCam: droidcam:<IP>  (IP hiện trên màn hình ứng dụng).")
        else:
            print("  - Chạy: python tools/tim_camera.py  để xem số của từng camera (laptop thường là 0, webcam USB là 1).\n"
                  "  - Tắt Zoom / Meet / ứng dụng Camera đang giữ webcam.")
        sys.exit(1)
    try:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    except cv2.error:
        print(OPENCV_FIX_MSG.format(ver=cv2.__version__))
        sys.exit(1)
    edit_request = [False]

    def on_main_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_RBUTTONDOWN:      # chuot phai -> ke lai vach
            edit_request[0] = True

    cv2.setMouseCallback(window, on_main_mouse)
    print(f"[CAMERA {cam}] Phím tắt (click vào cửa sổ camera trước): L hoặc chuột phải = kẻ lại vạch · "
          "R = vạch mặc định · Q = thoát.")

    state = _get("/bridge/state") or {"num1": 0, "num2": 0, "onbridge": 0, "dem": 0}
    last_report = last_hb = 0.0
    local_in = local_out = facade_total = 0
    prev_level = "OK"
    fps, frames, fps_t0 = 0.0, 0, time.time()
    ai_ms = 0.0
    last_stream = 0.0
    layer = TextLayer()
    source_label = str(args.source) if not isinstance(args.source, str) or "@" not in args.source \
        else args.source.split("@")[-1]

    print(f"CAMERA CHÂN CẦU {cam} đang chạy. Gửi mức cảnh báo: {'CÓ' if args.send_alerts else 'KHÔNG'}.")
    while True:
        ok, frame = cap.read()
        if not ok:
            if args.is_file:
                print("Hết video.")
                break
            # NFR-03: mat tin hieu -> bao ngay, tu ket noi lai
            print(f"[CAMERA {cam}] Mất tín hiệu camera, đang kết nối lại...")
            net.post("/system_events", {"event_type": "CAMERA_LOST", "camera_id": cam,
                                     "message": f"[SmartCau AI] Camera chân cầu {cam} mất tín hiệu lúc "
                                                f"{time.strftime('%H:%M:%S %d/%m/%Y')}. Chuyển sang điều tiết thủ công."})
            while True:
                cap.release()
                time.sleep(RECONNECT_SEC)
                cap = open_src(1.0)
                if cap.isOpened() and cap.read()[0]:
                    break
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    return
            net.post("/system_events", {"event_type": "CAMERA_RESTORED", "camera_id": cam,
                                     "message": f"[SmartCau AI] Camera chân cầu {cam} đã hoạt động lại."})
            print(f"[CAMERA {cam}] Đã kết nối lại.")
            continue

        now = time.time()
        frames += 1
        if now - fps_t0 >= 2.0:
            fps, frames, fps_t0 = frames / (now - fps_t0), 0, now
        if args.max_width and frame.shape[1] > args.max_width:
            scale = args.max_width / frame.shape[1]
            frame = cv2.resize(frame, (args.max_width, int(frame.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        fh, fw = frame.shape[:2]

        t_ai = time.time()
        results = model.track(frame, persist=True, classes=[0], conf=args.conf, imgsz=args.imgsz,
                              tracker=args.tracker, verbose=False)[0]
        ai_ms = 0.9 * ai_ms + 0.1 * (time.time() - t_ai) * 1000
        out = frame.copy()
        draw_line_overlay(out, layer, line)

        people = []
        if results.boxes is not None and results.boxes.id is not None:
            for i, (box, tid) in enumerate(zip(results.boxes, results.boxes.id)):
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                b = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
                kp_xy, kp_conf = extract_keypoints(results, i)
                people.append((int(tid), b, kp_xy, kp_conf))

        group_input = []
        for tid, b, kp_xy, kp_conf in people:
            fx, fy = foot_point(b, fw, fh)
            d = line.signed_distance((fx, fy))
            color = GREEN if d > 0 else ORANGE
            draw_person_box(out, b, tid, color)
            cv2.circle(out, (int(fx * fw), int(fy * fh)), 5, color, -1)
            facade.update(tid, outside=d < 0, now=now)
            group_input.append((tid, fx, fy, b[3] / fh, d))

            event = line.update(tid, (fx, fy), now)
            if event:
                facade.mark_crossed(tid)
                if event == "in":
                    local_in += 1
                    if profiler is not None:
                        profiler.mark_entered(tid, now)
                else:
                    local_out += 1
                    if profiler is not None:
                        profiler.mark_exited(tid)
                net.post("/bridge/crossing", {"camera_id": cam, "direction": event, "track_id": tid})
                # hien ngay tren camera, so chinh xac (gom ca camera kia) ve sau <= 1 giay
                key = f"num{cam}"
                state = dict(state)
                if event == "in":
                    state[key] = state.get(key, 0) + 1
                    state["dem"] = state.get("dem", 0) + 1
                else:
                    state[key] = state.get(key, 0) - 1
                state["onbridge"] = max(0, state.get("num1", 0) + state.get("num2", 0))
                print(f"[CAMERA {cam}] ID {tid} {'VÀO' if event == 'in' else 'RA'} cầu -> trên cầu: {state.get('onbridge')}")

            if profiler is not None:
                if profiler.wants(tid):
                    profiler.observe(tid, frame, b, now, kp_xy, kp_conf)
                lines = profiler.label(tid)
                if lines:
                    accent = (60, 120, 20) if lines[0].startswith("VÀO") else (150, 90, 20)
                    panel_lines(layer, out, b, lines, accent=accent)

        if profiler is not None:
            profiler.step(now)

        n_facade = facade.collect(now)
        if n_facade:
            facade_total += n_facade
            net.post("/facade_pass", {"camera_id": cam, "count": n_facade})

        group = groups.update(group_input, now)
        if group:
            net.post("/system_events", {"event_type": "GROUP_DETECTED", "count": group, "camera_id": cam,
                                     "message": f"[SmartCau AI] Đoàn khoảng {group} người đang đến chân cầu {cam} "
                                                f"lúc {time.strftime('%H:%M:%S')}. Chuẩn bị điều tiết và kiểm tra vé đoàn."})
            print(f"[CAMERA {cam}] Phát hiện đoàn khoảng {group} người.")

        if net.state is not None:
            state, net.state = net.state, None
        api_ok = net.ok
        remote = net.alert_threshold
        if remote and remote != thresholds.alert:
            thresholds = CameraThresholds.from_alert_threshold(remote)
            tracker.set_thresholds(thresholds)
            print(f"[CAMERA {cam}] Ngưỡng mới: Vàng từ {thresholds.warning}, tối đa {thresholds.alert}.")
        if now - last_hb >= HEARTBEAT_SEC:
            net.post("/bridge/heartbeat", {"camera_id": cam, "source": source_label, "fps": fps, "machine": MACHINE,
                                        "line": f"{line.p1} → {line.p2}", "sends_alerts": args.send_alerts,
                                        "demographics": profiler is not None})
            last_hb = now

        onbridge = int(state.get("onbridge", 0))
        level = tracker.update(onbridge, now)
        if args.send_alerts:
            if now - last_report >= REPORT_SEC:
                net.post("/occupancy", {"count": onbridge, "status": level})
                last_report = now
            kind = tracker.pop_notification(now)
            stamp = time.strftime("%H:%M:%S %d/%m/%Y")
            if kind == "CRITICAL":
                msg = (f"[SmartCau AI] CẢNH BÁO ĐỎ - QUÁ TẢI: {onbridge} người đang trên cầu "
                       f"(tối đa {thresholds.alert}), vượt ngưỡng liên tục {int(thresholds.red_hold_sec)} giây. "
                       f"Thời điểm: {stamp}. Tạm dừng cho khách lên cầu.")
                trigger_buzzer_signal(msg)
                net.post("/system_events", {"event_type": "CRITICAL_ALERT", "count": onbridge, "message": msg, "camera_id": cam})
            elif kind == "WARNING":
                msg = (f"[SmartCau AI] CẢNH BÁO VÀNG - CẦU SẮP ĐẦY: {onbridge} người đang trên cầu "
                       f"(tối đa {thresholds.alert}). Thời điểm: {stamp}.")
                net.post("/system_events", {"event_type": "WARNING", "count": onbridge, "message": msg, "camera_id": cam})
            if prev_level == "CRITICAL" and level != "CRITICAL":
                net.post("/system_events", {"event_type": "CRITICAL_CLEARED", "count": onbridge, "camera_id": cam,
                                         "message": f"[SmartCau AI] Hết quá tải: còn {onbridge} người trên cầu."})
        prev_level = level

        draw_hud(out, layer, cam, state, level, thresholds, local_in, local_out, facade_total, fps, api_ok,
                 groups.current_size, ai_status or (f"AI {ai_ms:.0f} ms/khung"
                                                    + (f" · mặt {profiler.engine.avg_ms:.0f} ms"
                                                       if profiler is not None and getattr(profiler.engine, "avg_ms", 0) else "")))
        layer.render(out)
        if args.stream and (now - last_stream >= 0.08):
            # Gui khung hinh nen JPEG qua luong nen de stream ve Web Streamlit (max rong 960px)
            sh, sw = out.shape[:2]
            s_out = out
            if sw > 960:
                s_scale = 960.0 / sw
                s_out = cv2.resize(out, (960, int(sh * s_scale)), interpolation=cv2.INTER_AREA)
            ok_enc, buf = cv2.imencode('.jpg', s_out, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
            if ok_enc:
                net.send_stream_frame(cam, buf.tobytes())
            last_stream = now

        cv2.imshow(window, out)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        # Phim L (chu L thuong / hoa), so 1, phim K, hoac CHUOT PHAI -> ke lai vach.
        # Luu y: phai click vao cua so camera truoc de cua so nhan phim.
        if key in (ord("l"), ord("L"), ord("1"), ord("k"), ord("K")) or edit_request[0]:
            edit_request[0] = False
            new_line = draw_line_setup(cap, window, cam, restore_cb=on_main_mouse)
            if new_line is not None:
                line = new_line
        if key in (ord("r"), ord("R")):
            try:
                os.remove(_line_path(cam))
            except FileNotFoundError:
                pass
            line = LineCrossingCounter()
            print(f"[CAMERA {cam}] Đã về vạch mặc định.")

    cap.release()
    cv2.destroyAllWindows()
    print(f"Kết thúc camera {cam}: {local_in} lượt vào, {local_out} lượt ra, {facade_total} lượt mặt tiền.")
    if profiler is not None:
        print(f"Hồ sơ khách: {profiler.saved_count} đã nhận diện, {profiler.unknown_count} 'Không xác định'.")


if __name__ == "__main__":
    main()
