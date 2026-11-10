"""
tests/test_visitor_profiler.py  —  Kiem thu lap ho so nhan khau hoc (F3.2, FR-09, BRULE-06)
Dung engine GIA (khong can DeepFace) de kiem tra logic.
CHAY: pytest tests/test_visitor_profiler.py -q
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai_engine"))

from visitor_profiler import VisitorProfiler  # noqa: E402


class FakeEngine:
    """Tra ve 'san sang' sau `ready_after` lan goi update (gia lap bo phieu 3/3)."""

    def __init__(self, ready_after=3, gender="Woman", age_range="25-34", region=None):
        self.calls, self.ready_after = {}, ready_after
        self.gender, self.age_range, self.region = gender, age_range, region
        self.forgotten = []

    def update(self, tid, frame, box, keypoints=None, kp_conf=None):
        n = self.calls[tid] = self.calls.get(tid, 0) + 1
        ready = self.ready_after is not None and n >= self.ready_after
        return {"gender": self.gender if ready else None, "ready": ready, "age": 28,
                "age_range": self.age_range, "n_votes": n,
                "region": self.region, "region_confidence": 0.8}

    def forget(self, tid):
        self.forgotten.append(tid)


def make(engine, **kw):
    posts = []
    kw.setdefault("quality_gate", False)   # khung hinh gia 10x10 -> tat cong chat luong trong test logic
    p = VisitorProfiler(post=lambda path, payload: posts.append((path, payload)),
                        engine=engine, analyze_interval=0.0, **kw)
    return p, posts


FRAME = np.zeros((10, 10, 3), np.uint8)
BOX = (0, 0, 5, 5)


def test_profile_saved_only_after_entering():
    """Du phieu khi con o ngoai nhung CHUA vao cau -> chua luu; vao cau -> luu ngay 1 lan."""
    p, posts = make(FakeEngine(ready_after=3))
    for t in range(5):
        p.observe(1, FRAME, BOX, t)
    assert posts == []
    p.mark_entered(1, 5)
    assert posts == [("/visit_events", {"track_id": 1, "age": 28, "age_range": "25-34", "gender": "Woman",
                                        "origin": None, "camera_id": None})]
    p.observe(1, FRAME, BOX, 6)
    p.mark_entered(1, 7)
    assert len(posts) == 1                      # khong luu lap
    assert p.label(1) == ["VÀO CẦU · ID 1", "Nữ · 25-34", "Chưa rõ nguồn khách"]


def test_unknown_when_confidence_never_reached():
    """BRULE-06: vao cau ma 5 giay van chua du tin cay -> 'Khong xac dinh'."""
    p, posts = make(FakeEngine(ready_after=None), give_up_sec=5)
    p.observe(2, FRAME, BOX, 0)
    p.mark_entered(2, 1)
    for t in (2, 3, 4, 5):
        p.observe(2, FRAME, BOX, t)
        p.step(t)
    assert posts == []
    p.step(6)
    assert posts == [("/visit_events", {"track_id": 2, "age": None, "age_range": "Khong xac dinh", "gender": None,
                                        "origin": None, "camera_id": None})]
    assert p.label(2) == ["VÀO CẦU · ID 2", "Không xác định"]


def test_unknown_when_person_leaves_view_before_ready():
    p, posts = make(FakeEngine(ready_after=None), give_up_sec=99, gone_sec=1.5)
    p.observe(3, FRAME, BOX, 0)
    p.mark_entered(3, 0.5)
    p.step(1.0)
    assert posts == []
    p.step(2.1)                                 # khong thay nua > 1.5 giay
    assert posts[0][1]["gender"] is None


def test_exit_stops_analysis_and_reentry_resumes():
    p, posts = make(FakeEngine(ready_after=2))
    p.observe(4, FRAME, BOX, 0)
    p.mark_exited(4)
    assert not p.wants(4)
    p.mark_entered(4, 1)                        # quay lai vao cau
    assert p.wants(4)
    p.observe(4, FRAME, BOX, 2)
    assert posts and posts[0][1]["gender"] == "Woman"


def test_origin_shown_and_saved():
    """Nhom Dong A -> 'Trong nuoc', con lai -> 'Nuoc ngoai'; hien ngay khi du tin cay."""
    p, posts = make(FakeEngine(ready_after=1, region="Phuong Tay"))
    p.observe(5, FRAME, BOX, 0)
    assert p.label(5) == ["ID 5", "Nữ · 25-34", "Quốc tế"]      # hien truoc khi vao cau
    assert posts == []
    p.mark_entered(5, 1)
    assert posts[0][1]["origin"] == "Nuoc ngoai"
    assert p.label(5)[0] == "VÀO CẦU · ID 5"
    p2, posts2 = make(FakeEngine(ready_after=1, region="Dong A / Noi dia"))
    p2.observe(1, FRAME, BOX, 0)
    p2.mark_entered(1, 0.5)
    assert posts2[0][1]["origin"] == "Trong nuoc"


def test_origin_disabled():
    p, posts = make(FakeEngine(ready_after=1, region="Phuong Tay"), with_origin=False)
    p.observe(1, FRAME, BOX, 0)
    p.mark_entered(1, 0.5)
    assert posts[0][1]["origin"] is None and p.label(1) == ["VÀO CẦU · ID 1", "Nữ · 25-34"]


def test_analyze_interval_limits_deepface_calls():
    eng = FakeEngine(ready_after=None)
    p = VisitorProfiler(post=lambda *a: None, engine=eng, analyze_interval=0.3, quality_gate=False)
    for i in range(30):                         # 30 frame trong 1 giay
        p.observe(6, FRAME, BOX, i / 30)
    assert eng.calls[6] <= 4


def test_pending_label():
    p, _ = make(FakeEngine(ready_after=5))
    p.observe(7, FRAME, BOX, 0)
    assert p.label(7) == ["ID 7", "Đang nhận diện 1/3"]


def test_face_quality_gate():
    from visitor_profiler import face_quality
    rng = np.random.default_rng(0)
    sharp = rng.integers(0, 255, (300, 300, 3), dtype=np.uint8)          # nhieu chi tiet
    blurry = np.full((300, 300, 3), 128, np.uint8)                       # phang = nhoe
    box = (100, 60, 100, 220)

    def kps(nose_x=150, eye_gap=30, conf=0.9):
        k = [[nose_x, 110], [150 - eye_gap / 2, 100], [150 + eye_gap / 2, 100]] + [[0, 0]] * 14
        return k, [conf] * 3 + [0] * 14

    assert face_quality(sharp, box, *kps()) == (True, "ok")
    assert face_quality(sharp, box, *kps(eye_gap=8))[1] == "nho"
    assert face_quality(sharp, box, *kps(nose_x=200))[1] == "nghieng"
    assert face_quality(sharp, box, *kps(conf=0.2))[1] == "khong_thay_mat"
    assert face_quality(blurry, box, *kps())[1] == "nhoe"
    assert face_quality(sharp, (0, 0, 40, 60))[1] == "nho"               # khong keypoint, khung nho


def test_rejected_frames_do_not_vote():
    eng = FakeEngine(ready_after=1)
    p = VisitorProfiler(post=lambda *a: None, engine=eng, analyze_interval=0.0)
    blurry = np.full((300, 300, 3), 128, np.uint8)
    k = [[150, 110], [135, 100], [165, 100]] + [[0, 0]] * 14
    c = [0.9] * 3 + [0] * 14
    p.observe(1, blurry, (100, 60, 100, 220), 0, k, c)
    assert 1 not in eng.calls and p.label(1) == ["ID 1", "Hình bị nhòe"] and p.rejected["nhoe"] == 1
