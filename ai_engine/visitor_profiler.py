"""
visitor_profiler.py  —  F3.2 Uoc luong gioi tinh, khoang tuoi, trong nuoc / nuoc ngoai cho khach VAO cau
=========================================================================================================
Phu trach: MINH.   Yeu cau: FR-09, BRULE-05, BRULE-06 (BRD Sprint 1).

Tach tu phan nhan khau hoc trong camera_in.py (YOLO-pose keypoints +
DemographicsEngine bo phieu theo thoi gian + luu ho so 1 lan) de dung cho he
thong 2 camera chan cau (camera_bridge.py). Loi AI van nam o
demographics_engine.py / age_gender_estimator.py / region_mapping.py.

Hien tren camera: "Nam/Nu · khoang tuoi · Trong nuoc/chau A | Quoc te"
ngay khi bo phieu du tin cay >= 70%, ke ca truoc khi khach qua vach.

Luu vao CSDL (POST /visit_events) CHI khi khach thuc su VAO cau, 1 lan / nguoi:
  - du tin cay -> gioi tinh, khoang tuoi, nguon khach
  - vao cau ma sau ``give_up_sec`` giay van chua du tin cay -> "Khong xac dinh"
    (BRULE-06: van tinh 1 luot, khong dua vao ty le)

TRONG NUOC / NUOC NGOAI la UOC LUONG tu nhom khu vuc rong cua DeepFace:
    "Dong A / Noi dia" -> Trong nuoc;  Phuong Tay, Nam A, Khac -> Nuoc ngoai
DeepFace KHONG phan biet duoc khach Viet voi khach Han / Nhat / Trung, nen
khach Dong A deu bi tinh la "Trong nuoc". Con so chi dung de xem xu huong.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

GENDER_VI = {"Man": "Nam", "Woman": "Nữ"}
ORIGIN_VI = {"Trong nuoc": "Trong nước/châu Á", "Nuoc ngoai": "Quốc tế"}
UNKNOWN_AGE = "Khong xac dinh"
REGION_TO_ORIGIN = {"Dong A / Noi dia": "Trong nuoc", "Phuong Tay": "Nuoc ngoai",
                    "Nam A": "Nuoc ngoai", "Khac": "Nuoc ngoai"}
ORIGIN_MIN_SHARE = 0.55   # nhom khu vuc phai chiem >= 55% trong so phieu moi ket luan


# ---------------------------------------------------------------- chat luong mat
# Chi dua khung hinh vao DeepFace khi mat DU TO, NHIN GAN THANG, KHONG NHOE.
# Khung hinh xau (nghieng, xa, mo do chuyen dong) la nguon chinh gay doan sai
# gioi tinh / tuoi; bo qua chung lam phieu bau sach hon (xem docs/AI_CAI_THIEN.md).
MIN_EYE_PX = 14          # khoang cach 2 mat toi thieu (px) ~ mat rong >= 35 px
MIN_SHARPNESS = 35.0     # phuong sai Laplacian vung dau; thap = nhoe
MIN_BOX_H = 110          # khi khong co keypoint (model khong phai pose): khung nguoi toi thieu (px)
_NOSE, _LEYE, _REYE = 0, 1, 2


def face_quality(frame, box, keypoints=None, kp_conf=None):
    """Tra ve (dat?, ly_do). ly_do: 'ok' | 'nho' | 'nghieng' | 'nhoe' | 'khong_thay_mat'."""
    import cv2
    x, y, w, h = box
    if keypoints is not None and kp_conf is not None and len(keypoints) > 2:
        if min(kp_conf[_NOSE], kp_conf[_LEYE], kp_conf[_REYE]) < 0.5:
            return False, "khong_thay_mat"              # quay lung / che mat
        (nx, _), (lx, ly), (rx, ry) = keypoints[_NOSE], keypoints[_LEYE], keypoints[_REYE]
        eye = ((lx - rx) ** 2 + (ly - ry) ** 2) ** 0.5
        if eye < MIN_EYE_PX:
            return False, "nho"
        lo, hi = min(lx, rx), max(lx, rx)
        if not (lo - 0.15 * eye <= nx <= hi + 0.15 * eye):
            return False, "nghieng"                     # mui lech ra ngoai 2 mat -> nghieng manh
        cx, cy, half = (lx + rx) / 2, (ly + ry) / 2, eye * 1.6
        x0, y0, x1, y1 = int(cx - half), int(cy - half), int(cx + half), int(cy + half * 1.4)
    else:
        if h < MIN_BOX_H:
            return False, "nho"
        x0, y0, x1, y1 = x + w // 5, y, x + w - w // 5, y + max(20, h // 5)
    fh, fw = frame.shape[:2]
    crop = frame[max(0, y0):min(fh, y1), max(0, x0):min(fw, x1)]
    if crop.size == 0:
        return False, "khong_thay_mat"
    sharp = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    if sharp < MIN_SHARPNESS:
        return False, "nhoe"
    return True, "ok"


QUALITY_HINT = {"nho": "Lại gần camera hơn", "nghieng": "Chờ nhìn thẳng", "nhoe": "Hình bị nhòe",
                "khong_thay_mat": "Chưa thấy mặt"}


def extract_keypoints(results, idx):
    """(keypoints_xy, keypoints_conf) cua nguoi thu idx tu ket qua YOLO-pose,
    hoac (None, None) neu model khong co keypoints (model detect thuong)."""
    kp = getattr(results, "keypoints", None)
    if kp is None or kp.xy is None:
        return None, None
    try:
        xy = kp.xy[idx].tolist()
        conf = kp.conf[idx].tolist() if kp.conf is not None else [1.0] * len(xy)
        return xy, conf
    except (IndexError, TypeError):
        return None, None


class AsyncEngine:
    """Chay DeepFace o LUONG NEN de vong lap camera khong phai cho (DeepFace ~0.1-0.5 giay/lan tren CPU).

    update() gui 1 yeu cau phan tich (neu track do chua co yeu cau dang cho) va tra ve
    ket qua MOI NHAT da co; "_seq" tang moi khi co ket qua moi."""

    def __init__(self, engine, max_pending: int = 3):
        import queue
        import threading
        self.engine, self.max_pending = engine, max_pending
        self.avg_ms = 0.0                     # thoi gian trung binh 1 lan phan tich mat (hien tren HUD)
        self.q = queue.Queue()
        self.results, self.pending = {}, set()
        self.lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True, name="deepface").start()

    def _run(self):
        while True:
            op, tid, args = self.q.get()
            if op == "forget":
                self.engine.forget(tid)
                with self.lock:
                    self.results.pop(tid, None)
                continue
            try:
                import time as _t
                t0 = _t.time()
                res = dict(self.engine.update(tid, *args[:2], keypoints=args[2], kp_conf=args[3]))
                ms = (_t.time() - t0) * 1000
                self.avg_ms = ms if not self.avg_ms else 0.8 * self.avg_ms + 0.2 * ms
            except Exception as e:   # 1 khung loi khong lam dung nhan dien
                print(f"[nhận diện] Lỗi phân tích: {e}")
                res = None
            with self.lock:
                self.pending.discard(tid)
                if res is not None:
                    res["_seq"] = self.results.get(tid, {}).get("_seq", 0) + 1
                    self.results[tid] = res

    def update(self, tid, frame, box, keypoints=None, kp_conf=None) -> dict:
        with self.lock:
            if tid not in self.pending and len(self.pending) < self.max_pending:
                self.pending.add(tid)
                self.q.put(("update", tid, (frame, box, keypoints, kp_conf)))   # frame khong bi ve len -> khong can copy
            return self.results.get(tid) or {"ready": False, "n_votes": 0, "_seq": 0}

    def forget(self, tid):
        self.q.put(("forget", tid, None))


@dataclass
class _Track:
    first_seen: float
    last_seen: float
    last_analyzed: float = -1e9
    entered_at: Optional[float] = None
    info: Optional[dict] = None
    region_votes: Dict[str, float] = field(default_factory=dict)
    last_reject: Optional[str] = None
    done: bool = False
    saved: Optional[dict] = None
    last_seq: int = -1


class VisitorProfiler:
    """Quan ly nhan khau hoc theo track_id cho 1 camera chan cau.

        profiler.observe(tid, frame, box, now, keypoints, kp_conf)   # moi frame
        profiler.mark_entered(tid, now)                              # qua vach VAO cau
        profiler.mark_exited(tid)                                    # qua vach RA
        profiler.step(now)                                           # cuoi moi frame
        lines = profiler.label(tid)                                  # chu hien canh khung nguoi
    """

    def __init__(self, post: Callable[[str, dict], object], engine=None, with_origin: bool = True,
                 camera_id: Optional[int] = None, analyze_interval: float = 0.3, give_up_sec: float = 5.0,
                 gone_sec: float = 1.5, forget_sec: float = 30.0, quality_gate: bool = True):
        if engine is None:
            from demographics_engine import DemographicsEngine
            engine = AsyncEngine(DemographicsEngine(enable_region=with_origin))
        self.engine, self.post, self.with_origin, self.camera_id = engine, post, with_origin, camera_id
        self.analyze_interval, self.give_up_sec = analyze_interval, give_up_sec
        self.ready_interval = 1.5
        self.gone_sec, self.forget_sec = gone_sec, forget_sec
        self.quality_gate = quality_gate
        self.rejected = {}
        self._tracks: Dict[int, _Track] = {}
        self.saved_count = 0
        self.unknown_count = 0

    # ----------------------------------------------------------- vong lap
    def wants(self, tid: int) -> bool:
        t = self._tracks.get(tid)
        return t is None or not t.done

    def observe(self, tid: int, frame, box, now: float, keypoints=None, kp_conf=None):
        t = self._tracks.get(tid)
        if t is None:
            t = self._tracks[tid] = _Track(first_seen=now, last_seen=now)
        t.last_seen = now
        # Da chot ket qua (cho qua vach) -> phan tich thua hon de nhuong DeepFace cho nguoi khac
        interval = self.ready_interval if t.info and t.info.get("ready") else self.analyze_interval
        if t.done or now - t.last_analyzed < interval:
            return
        t.last_analyzed = now
        if self.quality_gate:
            ok, why = face_quality(frame, box, keypoints, kp_conf)
            if not ok:
                t.last_reject = why
                self.rejected[why] = self.rejected.get(why, 0) + 1
                return
        t.last_reject = None
        t.info = self.engine.update(tid, frame, box, keypoints=keypoints, kp_conf=kp_conf)
        seq = t.info.get("_seq")
        fresh = seq is None or seq != t.last_seq      # engine chay nen: chi bo phieu khu vuc khi co ket qua MOI
        t.last_seq = seq if seq is not None else t.last_seq
        region, conf = t.info.get("region"), float(t.info.get("region_confidence") or 0)
        if region and fresh:
            t.region_votes[region] = t.region_votes.get(region, 0.0) + max(conf, 0.05)
        if t.entered_at is not None and t.info.get("ready"):
            self._save(tid, t)

    def mark_entered(self, tid: int, now: float):
        t = self._tracks.get(tid)
        if t is None:
            t = self._tracks[tid] = _Track(first_seen=now, last_seen=now)
        if t.done and t.saved is None:
            t.done = False                     # da ra roi quay lai vao -> lap ho so tiep
        if t.done:
            return
        t.entered_at = now
        if t.info and t.info.get("ready"):
            self._save(tid, t)

    def mark_exited(self, tid: int):
        """Di RA (chua vao o camera nay) -> ngung phan tich, khong lap ho so."""
        t = self._tracks.get(tid)
        if t is not None and t.entered_at is None and not t.done:
            t.done = True
            self.engine.forget(tid)

    def step(self, now: float):
        for tid, t in list(self._tracks.items()):
            if t.entered_at is not None and not t.done:
                if now - t.entered_at >= self.give_up_sec or now - t.last_seen >= self.gone_sec:
                    self._save_unknown(tid, t)
            if now - t.last_seen > self.forget_sec:
                self.engine.forget(tid)
                del self._tracks[tid]

    # ---------------------------------------------------------- ket qua
    def origin_of(self, tid: int) -> Optional[str]:
        t = self._tracks.get(tid)
        if t is None or not self.with_origin or not t.region_votes:
            return None
        total = sum(t.region_votes.values())
        best = max(t.region_votes, key=t.region_votes.get)
        if t.region_votes[best] / total < ORIGIN_MIN_SHARE:
            return None
        return REGION_TO_ORIGIN.get(best)

    def label(self, tid: int) -> Optional[List[str]]:
        """Dong chu hien tren camera (co dau tieng Viet)."""
        t = self._tracks.get(tid)
        if t is None:
            return None
        head = f"VÀO CẦU · ID {tid}" if t.entered_at is not None else f"ID {tid}"
        res = t.saved if t.saved is not None else (t.info if t.info and t.info.get("ready") else None)
        if t.saved is not None and t.saved["gender"] is None:
            return [head, "Không xác định"]
        if res is not None:
            lines = [head, f"{GENDER_VI.get(res['gender'], res['gender'])} · {res.get('age_range') or '?'}"]
            if self.with_origin:
                origin = res.get("origin") if t.saved is not None else self.origin_of(tid)
                lines.append(ORIGIN_VI.get(origin, "Chưa rõ nguồn khách"))
            return lines
        if t.last_reject and not t.done:
            return [head, QUALITY_HINT.get(t.last_reject, "Chờ thấy rõ mặt")]
        if t.info is not None and not t.done:
            return [head, f"Đang nhận diện {min(t.info.get('n_votes', 0), 3)}/3"]
        if not t.done:
            return [head, "Đang nhận diện…"]
        return None

    # -------------------------------------------------------------- ghi
    def _save(self, tid: int, t: _Track):
        info = t.info
        payload = {"track_id": tid, "age": info.get("age"),
                   "age_range": info.get("age_range") or UNKNOWN_AGE, "gender": info.get("gender"),
                   "origin": self.origin_of(tid), "camera_id": self.camera_id}
        self.post("/visit_events", payload)
        t.saved, t.done = payload, True
        self.saved_count += 1
        self.engine.forget(tid)

    def _save_unknown(self, tid: int, t: _Track):
        payload = {"track_id": tid, "age": None, "age_range": UNKNOWN_AGE, "gender": None,
                   "origin": None, "camera_id": self.camera_id}
        self.post("/visit_events", payload)
        t.saved, t.done = payload, True
        self.unknown_count += 1
        self.engine.forget(tid)
