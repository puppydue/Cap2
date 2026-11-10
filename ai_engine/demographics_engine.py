"""
demographics_engine.py
-------------------------
"Demographics Engine" (nang cap Phase 2 + Phase 3) - gop nhieu TIN HIEU lai
voi nhau (signal fusion) de doan gioi tinh ON DINH hon, thay vi chi doc 1
LAN DUY NHAT tu DeepFace nhu ban cu (age_gender_estimator.py goc).

3 TIN HIEU duoc dung:
  1. DeepFace gender (baseline) - tin hieu chinh, do chinh xac cao nhat
     trong 3 tin hieu, lay tu estimate_demographics_from_person_box().
  2. Ty le vai/hong tu YOLO POSE (body proportions) - tin hieu PHU, THO,
     dua tren quan sat thong ke chung (vai rong hon hong thuong gan voi
     nam, nguoc lai voi nu) - CHI dung de HO TRO khi DeepFace khong chac
     chan, KHONG dung mot minh vi do chinh xac thap hon nhieu va CO THE
     SAI voi tung ca nhan (day la xu huong thong ke, khong phai quy luat
     dung cho moi nguoi).
  3. Temporal voting (bo phieu theo thoi gian) - 1 nguoi (track_id) di
     qua camera trong NHIEU frame lien tiep, moi frame la 1 "phieu bau"
     rieng; ket qua cuoi la gioi tinh duoc bau NHIEU NHAT, co TRONG SO
     theo do tin cay tung phieu - giam anh huong cua 1 frame doc (goc
     nghieng xau, anh sang kem...) lam sai lech ket qua.

NGUONG TIN CAY: ket qua CHI duoc coi la "san sang" (ready=True, cho phep
hien thi/luu ho so) khi do tin cay bo phieu >= CONFIDENCE_THRESHOLD (mac
dinh 0.70 = 70%, dung theo yeu cau nang cap Phase 2). Duoi nguong nay, van
tiep tuc thu thap them phieu (hien "dang xac dinh...") thay vi hien ket
qua chua chac chan.

SMOOTHING: 1 khi gioi tinh da duoc "chot" (ready=True) cho 1 track_id, KHONG
tu doi sang gioi tinh khac chi vi 1-2 frame sau co ket qua khac - phai co
DU so phieu MOI (xem _FLIP_MARGIN) nghieng han ve phia khac thi moi doi,
tranh hien tuong nhay gioi tinh lien tuc giua cac frame (yeu cau "khong
doi gioi tinh lien tuc giua cac frame" trong Phase 2).

=== SUA LOI LAN 5 (gioi tinh/khoang tuoi hay bi sai, nguoi dung bao loi
thuc te khi test camera that) ===
2 nguyen nhan duoc tim thay va sua trong ban nay:

1. KHOANG TUOI KHONG CO BO PHIEU THEO THOI GIAN (day la loi CHINH, nang
   nhat): ban truoc, gioi tinh thi co bo phieu qua nhieu frame (TemporalVoter,
   xem tren) nen on dinh - nhung KHOANG TUOI thi KHONG, chi don gian LAY
   KET QUA CUA FRAME MOI NHAT roi GHI DE len frame truoc do (ham set_age() cu,
   goi moi frame). Vi 1 frame rieng le co the bi mo, goc nghieng, bieu cam
   la, anh sang doi lien tuc... nen khoang tuoi hien thi cu "nhay" thay doi
   het lan nay den lan khac, KHONG dang tin cay du anh webcam da xac dinh
   duoc mat that. Sua: them age_votes (hang doi bo phieu rieng cho tuoi,
   cung co che voi gioi tinh) - khoang tuoi hien thi la khoang duoc nhieu
   frame "bau" nhat trong VOTE_WINDOW frame gan nhat, khong con la 1 frame
   doc lap nua.

2. TIN HIEU PHU TU TY LE VAI/HONG (estimate_gender_signal_from_pose) MAC
   DINH DA TAT (_POSE_SIGNAL_ENABLED = False): day la 1 heuristic THO, tu
   nhan la "CHUA duoc kiem chung bang du lieu that" ngay trong docstring
   ban dau - va noi dung dung no CHINH XAC o truong hop DeepFace da KHONG
   chac chan (do tin cay < 60%), tuc la truong hop DE SAI NHAT lai la truong
   hop duoc "tro giup" bang 1 tin hieu con kem tin cay hon. Qua thu nghiem
   thuc te, heuristic nay co ve dang KEO sai lech ket qua (dac biet voi
   trang phuc/ao khoac VN khong khop voi gia dinh "vai rong = nam" kieu
   phuong Tay dung de hieu chuan) nhieu hon la giup. Sua: TAT heuristic nay,
   CHI dung 100% ket qua DeepFace (da la tin hieu chinh, dang tin cay nhat
   trong 3 tin hieu) cho gioi tinh. Co the BAT LAI (set _POSE_SIGNAL_ENABLED
   = True) de thu nghiem rieng neu muon, nhung KHONG khuyen nghi dua vao
   ket qua thuc te da ghi nhan.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple

from age_gender_estimator import (align_face_from_keypoints, estimate_demographics_from_person_box,
                                  estimate_from_aligned_face)
from region_mapping import classify_region_from_deepface_race

CONFIDENCE_THRESHOLD = 0.70   # Phase 2: chi hien ket qua khi do tin cay >= 70%
VOTE_WINDOW = 6                # so phieu (frame) gan nhat duoc xet cho 1 track_id
MIN_VOTES_BEFORE_READY = 3     # it nhat 3 phieu moi bat dau xet "san sang"
RACE_VOTES = 4                 # du 4 lan uoc luong khu vuc thi thoi chay "race" cho nguoi do (nhanh hon)
_FLIP_MARGIN = 0.15            # ket qua moi phai thang ket qua da chot >= 15% moi duoc doi (smoothing)

# Tin hieu phu tu ty le vai/hong CHI duoc cong vao khi DeepFace that su
# khong chac chan (duoi nguong nay) - tranh lam nhieu tin hieu chinh xac
# hon bang 1 tin hieu tho hon.
_POSE_SIGNAL_ONLY_BELOW_DEEPFACE_CONF = 60.0  # % (thang do goc cua DeepFace, 0-100)

# SUA LOI LAN 5: TAT heuristic vai/hong theo mac dinh - xem giai thich chi
# tiet trong docstring dau file ("SUA LOI LAN 5", muc 2). Chi dung 100%
# ket qua DeepFace cho gioi tinh. Doi thanh True chi de THU NGHIEM rieng.
_POSE_SIGNAL_ENABLED = False

# COCO keypoint index (chuan cua YOLOv8/11-pose va hau het model pose COCO):
KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER = 5, 6
KP_LEFT_HIP, KP_RIGHT_HIP = 11, 12
_MIN_KP_CONF = 0.35


def estimate_gender_signal_from_pose(keypoints, kp_conf) -> Optional[Tuple[str, float]]:
    """Uoc luong THO gioi tinh tu ty le ROI VAI/HONG (YOLO Pose). Day la
    TIN HIEU PHU, dua tren xu huong thong ke chung (KHONG dung rieng le):
    vai rong hon hong -> nghieng ve "Man"; hong rong hon/bang vai -> nghieng
    ve "Woman". Tra ve (gender, do_tin_cay_0_den_1) hoac None neu thieu du
    lieu keypoint dang tin cay (vd nguoi quay lung, bi che khuat vai/hong).

    `keypoints`: mang 17x2 (x, y) theo chuan COCO-pose.
    `kp_conf`: mang 17 gia tri do tin cay tuong ung (0-1).
    """
    if keypoints is None or kp_conf is None or len(keypoints) < 13:
        return None
    needed = [KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER, KP_LEFT_HIP, KP_RIGHT_HIP]
    if any(kp_conf[i] < _MIN_KP_CONF for i in needed):
        return None

    lsx, lsy = keypoints[KP_LEFT_SHOULDER]
    rsx, rsy = keypoints[KP_RIGHT_SHOULDER]
    lhx, lhy = keypoints[KP_LEFT_HIP]
    rhx, rhy = keypoints[KP_RIGHT_HIP]

    shoulder_w = ((lsx - rsx) ** 2 + (lsy - rsy) ** 2) ** 0.5
    hip_w = ((lhx - rhx) ** 2 + (lhy - rhy) ** 2) ** 0.5
    if shoulder_w <= 0 or hip_w <= 0:
        return None

    ratio = shoulder_w / hip_w  # > 1: vai rong hon hong
    # Doi ratio thanh "male_score" 0..1 bang 1 duong dich chuyen tuyen tinh
    # don gian, cat nguong 0..1 - day la heuristic THO, CHUA duoc kiem
    # chung bang du lieu that, chi mang tinh THAM KHAO/HO TRO.
    male_score = max(0.0, min(1.0, (ratio - 0.85) / 0.5))
    if male_score >= 0.5:
        return "Man", (male_score - 0.5) * 2  # quy ve do "chac chan" 0..1
    return "Woman", (0.5 - male_score) * 2


def _weighted_tally(votes) -> Tuple[Optional[str], float, float]:
    """Dung CHUNG cho ca bo phieu gioi tinh VA khoang tuoi (SUA LOI LAN 5).
    `votes`: iterable cac (nhan, trong_so). Tra ve (nhan_thang,
    do_tin_cay_0_1, tong_trong_so) - do_tin_cay = ty le trong so cua nhan
    thang tren TONG trong so tat ca phieu."""
    totals: Dict[str, float] = {}
    for label, weight in votes:
        totals[label] = totals.get(label, 0.0) + weight
    total_weight = sum(totals.values())
    if total_weight <= 0:
        return None, 0.0, 0.0
    winner = max(totals, key=totals.get)
    return winner, totals[winner] / total_weight, total_weight


@dataclass
class _TrackState:
    votes: Deque[Tuple[str, float]] = field(default_factory=lambda: deque(maxlen=VOTE_WINDOW))
    locked_gender: Optional[str] = None
    locked_confidence: float = 0.0
    # SUA LOI LAN 5: khoang tuoi gio CUNG duoc bo phieu qua nhieu frame
    # giong gioi tinh, thay vi chi lay 1 frame moi nhat (xem docstring dau
    # file). Moi phieu: (age_range_label, trong_so, tuoi_so_le_hoac_None).
    age_votes: Deque[Tuple[str, float, Optional[int]]] = field(
        default_factory=lambda: deque(maxlen=VOTE_WINDOW)
    )
    age: Optional[int] = None
    age_range: str = "Khong ro"
    region: Optional[str] = None
    region_confidence: float = 0.0


class TemporalVoter:
    """Theo doi nhieu track_id cung luc, moi track_id co 1 hang doi phieu
    bau gioi tinh rieng (toi da VOTE_WINDOW phieu gan nhat). Phieu co
    TRONG SO theo do tin cay (0..1) - 1 phieu "rat chac chan" anh huong
    nhieu hon 1 phieu "hoi chac chan"."""

    def __init__(self):
        self._tracks: Dict[int, _TrackState] = {}

    def _state(self, track_id: int) -> _TrackState:
        if track_id not in self._tracks:
            self._tracks[track_id] = _TrackState()
        return self._tracks[track_id]

    def add_vote(self, track_id: int, gender: str, weight: float):
        """weight: do tin cay 0..1 cua phieu nay (dung lam trong so bau)."""
        weight = max(0.0, min(1.0, weight))
        if weight <= 0:
            return
        self._state(track_id).votes.append((gender, weight))

    def add_age_vote(self, track_id: int, age_range: str, age: Optional[int], weight: float = 1.0):
        """SUA LOI LAN 5: thay cho set_age() cu (ghi de 1 frame moi nhat).
        Them 1 phieu khoang tuoi vao hang doi (toi da VOTE_WINDOW phieu gan
        nhat) - khoang tuoi cuoi cung se la khoang duoc bau NHIEU NHAT,
        giong co che voi gioi tinh, thay vi bi 1 frame doc lam nhay lien tuc."""
        if not age_range or age_range == "Khong ro":
            return
        weight = max(0.0, min(1.0, weight)) or 1.0
        self._state(track_id).age_votes.append((age_range, weight, age))

    def set_region(self, track_id: int, region: Optional[str], confidence: float):
        st = self._state(track_id)
        st.region, st.region_confidence = region, confidence

    def tally(self, track_id: int) -> Tuple[Optional[str], float, int]:
        """Cong don trong so cac phieu hien co, tra ve (gioi_tinh_thang,
        do_tin_cay_0_1, so_phieu). do_tin_cay = ty le trong so cua gioi
        tinh thang tren TONG trong so tat ca phieu."""
        st = self._state(track_id)
        if not st.votes:
            return None, 0.0, 0
        winner, confidence, _ = _weighted_tally(st.votes)
        return winner, confidence, len(st.votes)

    def _current_share(self, track_id: int, label: str) -> float:
        """SUA LOI LAN 7: ty le phieu (0..1) cua 1 nhan CU THE (vd gioi
        tinh da "chot" truoc do) TRONG CUA SO phieu HIEN TAI - dung de so
        sanh CONG BANG voi nhan moi dang thang, xem giai thich "SUA LOI LAN
        7" trong docstring dau file."""
        st = self._state(track_id)
        if not st.votes:
            return 0.0
        totals: Dict[str, float] = {}
        for g, w in st.votes:
            totals[g] = totals.get(g, 0.0) + w
        total_weight = sum(totals.values())
        if total_weight <= 0:
            return 0.0
        return totals.get(label, 0.0) / total_weight

    def _tally_age(self, track_id: int) -> Tuple[str, Optional[int]]:
        """SUA LOI LAN 5: khoang tuoi "thang" (bau nhieu nhat) trong
        age_votes hien co, cung voi 1 tuoi so le THAM KHAO (trung binh cac
        phieu THUOC dung khoang thang do, de hien thi ben canh khoang tuoi
        neu can). Tra ve ("Khong ro", None) khi chua co phieu nao."""
        st = self._state(track_id)
        if not st.age_votes:
            return "Khong ro", None
        winner, _, _ = _weighted_tally([(label, w) for label, w, _ in st.age_votes])
        if winner is None:
            return "Khong ro", None
        matching_raw = [raw for label, _, raw in st.age_votes if label == winner and raw is not None]
        avg_age = round(sum(matching_raw) / len(matching_raw)) if matching_raw else None
        return winner, avg_age

    def result(self, track_id: int) -> Dict:
        """Tra ve ket qua CUOI CUNG cho track_id nay, da ap dung SMOOTHING
        (khong doi gioi tinh da "chot" tru khi phieu moi nghieng han hon).
        Dict: {"gender", "confidence", "ready", "age", "age_range",
               "region", "region_confidence", "n_votes"}."""
        st = self._state(track_id)
        winner, confidence, n_votes = self.tally(track_id)

        ready = False
        if winner is not None and n_votes >= MIN_VOTES_BEFORE_READY and confidence >= CONFIDENCE_THRESHOLD:
            if st.locked_gender is None:
                st.locked_gender, st.locked_confidence = winner, confidence
            elif winner != st.locked_gender:
                # SMOOTHING: chi doi "chot" khi ket qua moi thang DAM voi
                # bien do >= _FLIP_MARGIN, tranh nhay gioi tinh lien tuc.
                #
                # SUA LOI LAN 7 (nguoi dung phat hien qua test thuc te: 1
                # khi da "chot" voi do tin cay = 1.0 (vd 3/3 phieu dau tien
                # DONG THUAN), thi KHONG BAO GIO doi duoc nua, du sau do co
                # 100% phieu moi deu dung) - truoc day so sanh confidence
                # (toi da = 1.0) voi st.locked_confidence (cung co the da la
                # 1.0 tu luc chot) -> hieu so toi da = 0, khong bao gio >=
                # _FLIP_MARGIN (0.15) duoc, "tran" vinh vien o do tin cay
                # 1.0 ban dau. Sua: so sanh do tin cay nhan MOI voi ty le
                # phieu CUA CHINH nhan DA CHOT (locked_gender) TRONG CUNG 1
                # cua so phieu HIEN TAI (_current_share), khong con dung con
                # so CU da luu tu luc chot nua - 2 so nay luon cung "mat
                # thang do" (cung 1 cua so, cung thoi diem) nen so sanh cong
                # bang, khong con bi tran som.
                locked_share_now = self._current_share(track_id, st.locked_gender)
                if confidence - locked_share_now >= _FLIP_MARGIN:
                    st.locked_gender, st.locked_confidence = winner, confidence
            else:
                st.locked_confidence = confidence
            ready = st.locked_gender is not None

        age_range, age = self._tally_age(track_id)

        return {
            "gender": st.locked_gender,
            "confidence": round(st.locked_confidence, 2),
            "ready": ready,
            "age": age,
            "age_range": age_range,
            "region": st.region,
            "region_confidence": round(st.region_confidence, 2),
            "n_votes": n_votes,
        }

    def forget(self, track_id: int):
        """Xoa het trang thai cua 1 track_id (vd khi nguoi da ra khoi
        khung hinh hoac da ghi nhan xong, giai phong bo nho)."""
        self._tracks.pop(track_id, None)


class DemographicsEngine:
    """Lop bao boc toan bo pipeline: nhan 1 frame + 1 khung nguoi (box) +
    (tuy chon) keypoints tu YOLO-pose cho track_id do, goi DeepFace, cong
    THEM tin hieu pose neu can, bo phieu theo thoi gian, tra ve ket qua.

    `enable_region`: TAT theo mac dinh (xem region_mapping.py - GIOI HAN
    CO CHU DICH). CHI bat len khi da doc va hieu ro cac nguyen tac su
    dung trong docstring cua region_mapping.py."""

    def __init__(self, enable_region: bool = False):
        self.enable_region = enable_region
        self.voter = TemporalVoter()
        self._race_n: Dict[int, int] = {}     # so lan da uoc luong khu vuc cho moi track
        self.last_path = ""                   # "keypoint" (nhanh) | "detector" (du phong)
        if enable_region:
            print(
                "[DemographicsEngine] DA BAT tinh nang uoc luong KHU VUC (Phase 3).\n"
                "  - Day la UOC LUONG THO, CHI phan nhom rong, KHONG xac dinh quoc tich/chung toc ca nhan.\n"
                "  - Du lieu CHI duoc tong hop theo gio (xem RegionStat trong backend/),\n"
                "    KHONG gan nhan khu vuc cho tung ho so/track_id ca nhan.\n"
                "  - Xem day du nguyen tac su dung trong region_mapping.py."
            )

    def update(self, track_id: int, frame, box, keypoints=None, kp_conf=None) -> Dict:
        """Goi 1 LAN MOI FRAME cho moi track_id dang theo doi (co the goi
        lai nhieu lan cho CUNG 1 track_id - ham se tu bo phieu don dan,
        KHONG can tu quan ly cache ben ngoai nhu ban cu)."""
        # Race (de uoc luong nguon khach) chi chay toi khi du phieu -> moi lan phan tich nhanh hon
        want_race = self.enable_region and self._race_n.get(track_id, 0) < RACE_VOTES
        face = align_face_from_keypoints(frame, keypoints, kp_conf)
        if face is not None:            # nhanh: cat mat theo keypoint, khong can tim mat
            info = estimate_from_aligned_face(face, include_race=want_race)
            self.last_path = "keypoint"
        else:                           # du phong: model khong co keypoint -> DeepFace tu tim mat
            info = estimate_demographics_from_person_box(frame, box, include_race=want_race)
            self.last_path = "detector"

        if info["gender"] is not None:
            # Trong so = muc "chac chan" (50% -> 0, 100% -> 1): ket qua 55% gan nhu khong duoc tinh,
            # truoc day 55% van co trong so 0.55 gan bang 99% -> de bi keo sai.
            df_conf = max(0.0, min(1.0, (info["gender_confidence"] - 50.0) / 50.0))
            self.voter.add_vote(track_id, info["gender"], df_conf)
            if info["age"] is not None:
                # SUA LOI LAN 5: dung weight = do tin cay DeepFace cua CHINH
                # frame nay (df_conf) - frame nao DeepFace tim duoc mat ro/
                # chinh dien hon (gender_confidence cao hon) thi phieu tuoi
                # cua frame do cung duoc tin hon, hop ly vi ca 2 cung doc
                # tu CUNG 1 lan phan tich/1 vung mat.
                self.voter.add_age_vote(track_id, info["age_range"], info["age"], weight=df_conf)

            if want_race and info.get("race_probs"):
                region, region_conf = classify_region_from_deepface_race(info.get("race_probs"))
                if region is not None:
                    self._race_n[track_id] = self._race_n.get(track_id, 0) + 1
                    self.voter.set_region(track_id, region, region_conf)

            # Tin hieu pose CHI duoc cong them khi DA BAT (_POSE_SIGNAL_ENABLED,
            # mac dinh TAT - xem "SUA LOI LAN 5" dau file) VA DeepFace con mo
            # ho (duoi nguong) - neu DeepFace da rat chac chan roi thi khong can.
            if (
                _POSE_SIGNAL_ENABLED
                and info["gender_confidence"] < _POSE_SIGNAL_ONLY_BELOW_DEEPFACE_CONF
                and keypoints is not None
            ):
                pose_signal = estimate_gender_signal_from_pose(keypoints, kp_conf)
                if pose_signal is not None:
                    pose_gender, pose_conf = pose_signal
                    # Giam trong so tin hieu pose xuong con 1 nua - day la
                    # tin hieu PHU, khong duoc "nang" ngang DeepFace.
                    self.voter.add_vote(track_id, pose_gender, pose_conf * 0.5)

        return self.voter.result(track_id)

    def forget(self, track_id: int):
        self.voter.forget(track_id)
        self._race_n.pop(track_id, None)
