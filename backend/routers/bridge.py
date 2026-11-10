"""
backend/routers/bridge.py  —  MODULE M1 · F1 Dem khach tren cau bang 2 camera
==============================================================================
Phu trach: MINH.   Chuc nang BFD: F1.2, F1.3   (FR-02, FR-03)

Moi chan cau co 1 camera (camera_id = 1 hoac 2) chay ai_engine/camera_bridge.py.
Moi khi 1 khach qua vach ke, camera goi POST /bridge/crossing.

Bien dem (luu trong bang bridge_state, chi 1 dong id=1):
    num1, num2 : so khach con lai tren cau tinh theo camera 1 / camera 2
                 - khach VAO o camera k: num_k += 1, dem += 1
                 - khach RA  o camera k: num_k -= 1
                 (num_k co the AM: vd khach vao o cam 1, ra o cam 2
                  -> num1 = 1, num2 = -1)
    onbridge   : num1 + num2 = so khach DANG o tren cau
                 - neu onbridge <= 0 -> dat lai num1 = num2 = 0 (cau da
                   trong; truong hop < 0 la do camera bo sot 1 luot vao,
                   tu dong sua sai)
    dem        : tong luot khach VAO cau trong NGAY (gio Viet Nam), tu
                 dat lai = 0 khi sang ngay moi

Moi luot qua vach con duoc ghi 1 dong vao bang bridge_crossings de thong
ke theo gio / ngay / thang / nam / khoang thoi gian bat ky
(GET /bridge/stats).

So onbridge duoc dong bo vao occupancy_state -> GET /stats/occupancy,
/stats/current, Tong quan, Bang LED dung duoc ngay ma khong phai sua.
"""

import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from ..database import Base, get_db
from ..models import get_state, log_audit
from ..security import require_api_key, require_roles
from ..timeutil import LOCAL_UTC_OFFSET, iso, local_now

router = APIRouter(prefix="/bridge", tags=["F1 - Dem khach tren cau (2 camera)"])

CAMERA_IDS = (1, 2)

# 2 camera gui gan nhu cung luc -> khoa de phep tinh doc-sua-ghi khong bi chen nhau.
_LOCK = threading.Lock()


# ------------------------------------------------------------------ bang CSDL
class BridgeState(Base):
    __tablename__ = "bridge_state"
    id = Column(Integer, primary_key=True)
    num1 = Column(Integer, default=0)
    num2 = Column(Integer, default=0)
    dem = Column(Integer, default=0)
    dem_date = Column(String, nullable=True)   # "YYYY-MM-DD" (gio dia phuong) cua bien dem
    updated_at = Column(DateTime, default=datetime.utcnow)


class BridgeCrossing(Base):
    """1 dong = 1 luot qua vach. local_time = gio Viet Nam (de thong ke)."""
    __tablename__ = "bridge_crossings"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    local_time = Column(DateTime, index=True)
    camera_id = Column(Integer, index=True)
    direction = Column(String, index=True)   # "in" | "out"
    track_id = Column(Integer, nullable=True)
    onbridge_after = Column(Integer)


class CameraStatus(Base):
    """F1.1 / NFR-03 - trang thai tung camera chan cau (camera gui nhip tim moi 5 giay)."""
    __tablename__ = "camera_status"
    camera_id = Column(Integer, primary_key=True)
    source = Column(String, default="")
    fps = Column(Integer, default=0)
    line = Column(String, default="")
    sends_alerts = Column(Integer, default=0)
    demographics = Column(Integer, default=0)
    machine = Column(String, default="")        # ten may tinh dang chay camera nay
    last_seen = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, default=datetime.utcnow)


class HeartbeatIn(BaseModel):
    camera_id: int
    machine: str = ""
    source: str = ""
    fps: float = 0
    line: str = ""
    sends_alerts: bool = False
    demographics: bool = False


class CrossingIn(BaseModel):
    camera_id: int
    direction: str          # "in" | "out"
    track_id: Optional[int] = None


# ------------------------------------------------------------------ tien ich
def _local_now() -> datetime:
    return local_now()


def _get_bridge_state(db: Session) -> BridgeState:
    st = db.query(BridgeState).filter(BridgeState.id == 1).first()
    if st is None:
        st = BridgeState(id=1, num1=0, num2=0, dem=0, dem_date=_local_now().strftime("%Y-%m-%d"))
        db.add(st)
        db.flush()
    return st


def _roll_day(st: BridgeState, today: str):
    """Sang ngay moi -> dem = 0."""
    if st.dem_date != today:
        st.dem = 0
        st.dem_date = today


def _state_json(st: BridgeState) -> dict:
    return {"num1": st.num1, "num2": st.num2, "onbridge": st.num1 + st.num2,
            "dem": st.dem, "date": st.dem_date}


# ------------------------------------------------------------------ Live Stream Buffer
# Luu frame JPEG moi nhat cua moi camera de phat truc tiep len web
_LATEST_FRAMES: dict[int, bytes] = {}
_FRAME_LOCK = threading.Lock()


@router.post("/stream_frame/{camera_id}", dependencies=[Depends(require_api_key)])
async def upload_stream_frame(camera_id: int, request: Request):
    """Camera bridge gui frame JPEG len server de phat live stream (F1.5)."""
    if camera_id not in CAMERA_IDS:
        raise HTTPException(status_code=400, detail="camera_id phải là 1 hoặc 2.")
    body = await request.body()
    if body:
        with _FRAME_LOCK:
            _LATEST_FRAMES[camera_id] = body
    return {"ok": True}


@router.get("/stream_snapshot/{camera_id}")
def stream_snapshot(camera_id: int):
    """Lay 1 anh JPEG moi nhat cua camera (cho polling / snapshot tren web)."""
    if camera_id not in CAMERA_IDS:
        raise HTTPException(status_code=400, detail="camera_id phải là 1 hoặc 2.")
    with _FRAME_LOCK:
        frame = _LATEST_FRAMES.get(camera_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Chưa có khung hình từ camera này.")
    return Response(content=frame, media_type="image/jpeg")


@router.get("/stream/{camera_id}")
def live_stream(camera_id: int):
    """Phat live stream MJPEG lien tuc cho trinh duyet / web Streamlit."""
    if camera_id not in CAMERA_IDS:
        raise HTTPException(status_code=400, detail="camera_id phải là 1 hoặc 2.")

    def gen():
        while True:
            with _FRAME_LOCK:
                frame = _LATEST_FRAMES.get(camera_id)
            if frame:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(0.08)  # ~12-15 fps

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


# ------------------------------------------------------------------ endpoint
@router.post("/crossing", dependencies=[Depends(require_api_key)])
def record_crossing(ev: CrossingIn, db: Session = Depends(get_db)):
    if ev.camera_id not in CAMERA_IDS:
        raise HTTPException(status_code=400, detail="camera_id phải là 1 hoặc 2.")
    if ev.direction not in ("in", "out"):
        raise HTTPException(status_code=400, detail="direction phải là 'in' hoặc 'out'.")

    with _LOCK:
        now_local = _local_now()
        st = _get_bridge_state(db)
        _roll_day(st, now_local.strftime("%Y-%m-%d"))

        delta = 1 if ev.direction == "in" else -1
        if ev.camera_id == 1:
            st.num1 += delta
        else:
            st.num2 += delta
        if ev.direction == "in":
            st.dem += 1

        onbridge = st.num1 + st.num2
        reset = False
        if onbridge <= 0:
            st.num1, st.num2, onbridge = 0, 0, 0
            reset = True
        st.updated_at = datetime.utcnow()

        get_state(db).current_count = onbridge   # dong bo cho dashboard / bang LED
        db.add(BridgeCrossing(local_time=now_local, camera_id=ev.camera_id,
                              direction=ev.direction, track_id=ev.track_id,
                              onbridge_after=onbridge))
        db.commit()
        db.refresh(st)
        return {**_state_json(st), "reset": reset}


@router.post("/heartbeat", dependencies=[Depends(require_api_key)])
def heartbeat(hb: HeartbeatIn, db: Session = Depends(get_db)):
    if hb.camera_id not in CAMERA_IDS:
        raise HTTPException(status_code=400, detail="camera_id phải là 1 hoặc 2.")
    row = db.query(CameraStatus).filter(CameraStatus.camera_id == hb.camera_id).first()
    now = datetime.utcnow()
    if row is None:
        row = CameraStatus(camera_id=hb.camera_id, started_at=now)
        db.add(row)
    elif now - row.last_seen > timedelta(seconds=OFFLINE_AFTER_SEC):
        row.started_at = now
    row.source, row.fps, row.line = hb.source, int(round(hb.fps)), hb.line
    row.sends_alerts, row.demographics, row.last_seen = int(hb.sends_alerts), int(hb.demographics), now
    row.machine = hb.machine[:60]
    db.commit()
    return {"ok": True}


OFFLINE_AFTER_SEC = 30   # NFR-03: bao mat tin hieu camera trong 30 giay


@router.get("/cameras")
def cameras(db: Session = Depends(get_db)):
    rows = {r.camera_id: r for r in db.query(CameraStatus).all()}
    now = datetime.utcnow()
    out = []
    for cid in CAMERA_IDS:
        has_stream = (cid in _LATEST_FRAMES)
        r = rows.get(cid)
        if r is None:
            out.append({"camera_id": cid, "online": False, "last_seen": None, "source": "", "fps": 0,
                        "line": "", "sends_alerts": False, "demographics": False, "started_at": None, "machine": "",
                        "has_stream": has_stream})
            continue
        out.append({"camera_id": cid, "online": (now - r.last_seen).total_seconds() <= OFFLINE_AFTER_SEC,
                    "last_seen": iso(r.last_seen), "seconds_ago": int((now - r.last_seen).total_seconds()),
                    "source": r.source, "fps": r.fps, "line": r.line, "sends_alerts": bool(r.sends_alerts),
                    "demographics": bool(r.demographics), "started_at": iso(r.started_at),
                    "machine": r.machine or "", "has_stream": has_stream})
    return out


@router.get("/state")
def bridge_state(db: Session = Depends(get_db)):
    with _LOCK:
        st = _get_bridge_state(db)
        _roll_day(st, _local_now().strftime("%Y-%m-%d"))
        db.commit()
        db.refresh(st)
        return _state_json(st)


@router.post("/reset", dependencies=[Depends(require_roles("admin", "quan_ly"))])
def reset_bridge(reset_dem: bool = False, db: Session = Depends(get_db)):
    """Dat lai num1 = num2 = 0 (vd cuoi ngay, hoac sau khi dem tay thay
    lech). reset_dem=true thi dat lai ca luot qua cau trong ngay."""
    with _LOCK:
        st = _get_bridge_state(db)
        st.num1 = st.num2 = 0
        if reset_dem:
            st.dem = 0
        get_state(db).current_count = 0
        log_audit(db, "web", "Đặt lại số người trên cầu", "reset_dem" if reset_dem else "")
        db.commit()
        db.refresh(st)
        return _state_json(st)


_GROUP_FORMAT = {"hour": "%Y-%m-%d %H:00", "day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}


def _parse_day(s: str, name: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name} phải có dạng YYYY-MM-DD.")


@router.get("/stats")
def bridge_stats(group: str = "day", date_from: str = "", date_to: str = "",
                 db: Session = Depends(get_db)):
    """Thong ke luot VAO / RA cau theo gio, ngay, thang hoac nam trong khoang
    [date_from, date_to] (gio Viet Nam, tinh ca 2 ngay dau mut).

    Mac dinh khoang thoi gian: group=hour -> hom nay; day -> 30 ngay gan nhat;
    month -> tu dau nam; year -> toan bo du lieu."""
    if group not in _GROUP_FORMAT:
        raise HTTPException(status_code=400, detail="group phải là hour, day, month hoặc year.")

    today = _local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    default_from = {"hour": today, "day": today - timedelta(days=29),
                    "month": today.replace(month=1, day=1), "year": datetime(2000, 1, 1)}[group]
    start = _parse_day(date_from, "date_from") if date_from else default_from
    end = _parse_day(date_to, "date_to") if date_to else today
    if end < start:
        raise HTTPException(status_code=400, detail="Ngày kết thúc phải sau ngày bắt đầu.")

    rows = (db.query(BridgeCrossing)
            .filter(BridgeCrossing.local_time >= start,
                    BridgeCrossing.local_time < end + timedelta(days=1))
            .order_by(BridgeCrossing.local_time).all())

    fmt = _GROUP_FORMAT[group]
    buckets: "OrderedDict[str, dict]" = OrderedDict()
    for r in rows:
        key = r.local_time.strftime(fmt)
        b = buckets.setdefault(key, {"period": key, "entries": 0, "exits": 0,
                                     "entries_cam1": 0, "entries_cam2": 0})
        if r.direction == "in":
            b["entries"] += 1
            b[f"entries_cam{r.camera_id}"] += 1
        else:
            b["exits"] += 1

    items = list(buckets.values())
    return {
        "group": group,
        "date_from": start.strftime("%Y-%m-%d"),
        "date_to": end.strftime("%Y-%m-%d"),
        "total_entries": sum(b["entries"] for b in items),
        "total_exits": sum(b["exits"] for b in items),
        "rows": items,
    }
