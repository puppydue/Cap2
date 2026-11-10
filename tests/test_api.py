"""
tests/test_api.py  —  Kiem thu backend (7 module)
=================================================
CHAY (tu thu muc goc):   pytest tests/ -q
Dung CSDL rieng trong bo nho (khong dung toi backend/smartcau.db that).
"""

import os
import sys
from datetime import datetime, timedelta

os.environ["SMARTCAU_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SMARTCAU_DISABLE_SCHEDULER"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import backend.database as database  # noqa: E402

database.engine = database.create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
database.SessionLocal.configure(bind=database.engine)

from backend import notify  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)
SENT = []
notify.deliver_async = lambda recipients, text, buttons=None: SENT.append(text)   # khong gui Telegram that
notify.deliver = lambda recipients, text, buttons=None: [{"name": "x", "channel": "telegram", "status": "ok"}] if SENT.append(text) is None else []
DOCS = []
notify.deliver_document = lambda recipients, fn, content, caption="": DOCS.append((fn, content)) or [
    {"name": "x", "channel": "telegram", "status": "ok"}]


def login(username="admin", password="admin123"):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


ADMIN = login()


# ------------------------------------------------------------- M2 nen tang
def test_health():
    d = client.get("/health").json()
    assert d["status"] == "ok" and d["utc_offset_hours"] == 7


def test_default_admin_must_change_password():
    me = client.get("/auth/me", headers=ADMIN).json()
    assert me["role"] == "admin" and me["must_change_password"] is True


def test_wrong_password_and_no_token():
    assert client.post("/auth/login", json={"username": "admin", "password": "sai"}).status_code == 401
    assert client.get("/users").status_code == 401
    assert client.get("/users", headers={"Authorization": "Bearer khong-hop-le"}).status_code == 401


def test_roles_and_account_lifecycle():
    r = client.post("/users", headers=ADMIN, json={"username": "truc1", "full_name": "Lê Hoan",
                                                    "password": "truc123", "role": "nguoi_truc"})
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    assert client.post("/users", headers=ADMIN, json={"username": "truc1", "password": "abcdef"}).status_code == 400
    truc = login("truc1", "truc123")
    # FR-12: nguoi truc khong vao duoc chuc nang cau hinh
    assert client.put("/config", headers=truc, json={"alert_threshold": 30}).status_code == 403
    assert client.get("/users", headers=truc).status_code == 403
    # doi mat khau
    assert client.post("/auth/change_password", headers=truc,
                       json={"old_password": "truc123", "new_password": "moi12345"}).status_code == 200
    login("truc1", "moi12345")
    # khoa tai khoan -> token cu mat hieu luc, khong dang nhap duoc
    assert client.put(f"/users/{uid}", headers=ADMIN, json={"active": False}).status_code == 200
    assert client.get("/auth/me", headers=truc).status_code == 401
    assert client.post("/auth/login", json={"username": "truc1", "password": "moi12345"}).status_code == 403


def test_cannot_remove_last_admin():
    me = client.get("/auth/me", headers=ADMIN).json()
    assert client.put(f"/users/{me['id']}", headers=ADMIN, json={"role": "quan_ly"}).status_code == 400


# ------------------------------------------------------------- M7 quan tri
def test_config_roundtrip_and_audit():
    r = client.put("/config", headers=ADMIN, json={"alert_threshold": 25, "open_time": "06:30"})
    assert r.status_code == 200
    d = client.get("/config").json()
    assert d["alert_threshold"] == 25 and d["warning_threshold"] == 19 and d["open_time"] == "06:30"
    assert client.put("/config", headers=ADMIN, json={"alert_threshold": 0}).status_code == 400
    assert client.put("/config", headers=ADMIN, json={"close_time": "25:00"}).status_code == 400
    log = client.get("/audit", headers=ADMIN).json()
    assert any(e["action"] == "Đổi cấu hình" and "25" in e["detail"] for e in log)
    client.put("/config", headers=ADMIN, json={"alert_threshold": 20, "open_time": "00:00", "close_time": "23:59"})


def test_recipients_crud():
    r = client.post("/recipients", headers=ADMIN, json={"name": "Trực đầu cầu", "channel": "telegram",
                                                         "address": "12345"})
    rid = r.json()["id"]
    assert any(x["id"] == rid for x in client.get("/recipients", headers=ADMIN).json())
    assert client.put(f"/recipients/{rid}", headers=ADMIN, json={"active": False}).json()["active"] is False
    assert client.post("/recipients", headers=ADMIN, json={"name": "", "address": "1"}).status_code == 400
    assert client.delete(f"/recipients/{rid}", headers=ADMIN).status_code == 200


def test_privacy_purge_respects_retention():
    assert client.get("/privacy/summary", headers=ADMIN).json()["face_images_stored"] == 0
    assert client.post("/privacy/purge", headers=ADMIN, params={"older_than_days": 30}).status_code == 400
    assert client.post("/privacy/purge", headers=ADMIN, params={"older_than_days": 730}).status_code == 200


# ------------------------------------------------------------- M3 su co
def test_incident_lifecycle():
    SENT.clear()
    client.post("/system_events", json={"event_type": "CRITICAL_ALERT", "count": 22, "message": "Đỏ"})
    client.post("/system_events", json={"event_type": "CRITICAL_ALERT", "count": 25, "message": "Nhắc lại"})
    opened = client.get("/incidents", params={"status": "open"}).json()
    assert len(opened) == 1 and opened[0]["peak_count"] == 25 and opened[0]["alert_count"] == 2
    iid = opened[0]["id"]
    acked = client.post(f"/incidents/{iid}/ack", headers=ADMIN, json={"note": "Đã điều tiết"}).json()
    assert acked["acknowledged"] and acked["handle_seconds"] is not None
    client.post("/system_events", json={"event_type": "CRITICAL_CLEARED", "count": 14})
    closed = client.get("/incidents", params={"status": "closed"}).json()
    assert closed[0]["id"] == iid and closed[0]["close_reason"] == "auto"
    assert any("ĐÃ ĐÓNG" in t for t in SENT)               # bao cao su co gui quan ly
    assert client.post(f"/incidents/{iid}/ack").status_code == 401


def test_events_have_vietnamese_labels():
    client.post("/system_events", json={"event_type": "GROUP_DETECTED", "count": 12})
    e = client.get("/system_events", params={"event_type": "GROUP_DETECTED"}).json()[0]
    assert e["label"] == "Đoàn khách lớn"


# ------------------------------------------------------------- M1 dem + nhan khau hoc
def _cross(cam, direction):
    r = client.post("/bridge/crossing", json={"camera_id": cam, "direction": direction})
    assert r.status_code == 200, r.text
    return r.json()


def test_bridge_counting_rules():
    client.post("/bridge/reset", headers=ADMIN, params={"reset_dem": True})
    assert client.get("/bridge/state").json()["dem"] == 0
    s = _cross(1, "in")
    assert (s["num1"], s["num2"], s["onbridge"], s["dem"]) == (1, 0, 1, 1)
    _cross(1, "in")
    s = _cross(2, "in")
    assert (s["num1"], s["num2"], s["onbridge"], s["dem"]) == (2, 1, 3, 3)
    _cross(2, "out")
    s = _cross(2, "out")
    assert (s["num1"], s["num2"], s["onbridge"]) == (2, -1, 1)
    s = _cross(1, "out")
    assert (s["num1"], s["num2"], s["onbridge"], s["reset"]) == (0, 0, 0, True)
    assert s["dem"] == 3
    s = _cross(2, "out")
    assert (s["num1"], s["num2"], s["onbridge"]) == (0, 0, 0)
    _cross(1, "in")
    assert client.get("/stats/occupancy").json()["current_count"] == 1
    assert client.post("/bridge/reset").status_code == 401


def test_bridge_validation():
    assert client.post("/bridge/crossing", json={"camera_id": 3, "direction": "in"}).status_code == 400
    assert client.post("/bridge/crossing", json={"camera_id": 1, "direction": "len"}).status_code == 400
    assert client.get("/bridge/stats", params={"group": "tuan"}).status_code == 400


def test_bridge_dem_resets_on_new_day(monkeypatch):
    import backend.routers.bridge as bridge
    client.post("/bridge/reset", headers=ADMIN, params={"reset_dem": True})
    _cross(1, "in")
    _cross(2, "in")
    assert client.get("/bridge/state").json()["dem"] == 2
    tomorrow = datetime.utcnow() + bridge.LOCAL_UTC_OFFSET + timedelta(days=1)
    monkeypatch.setattr(bridge, "_local_now", lambda: tomorrow)
    s = client.get("/bridge/state").json()
    assert s["dem"] == 0 and s["date"] == tomorrow.strftime("%Y-%m-%d")
    assert _cross(1, "in")["dem"] == 1


def test_bridge_stats_grouping():
    today = client.get("/bridge/state").json()["date"]
    for group in ("hour", "day", "month", "year"):
        d = client.get("/bridge/stats", params={"group": group, "date_from": today, "date_to": today}).json()
        assert d["total_entries"] == sum(r["entries"] for r in d["rows"])


def test_camera_heartbeat():
    client.post("/bridge/heartbeat", json={"camera_id": 1, "source": "0", "fps": 14.6, "sends_alerts": True,
                                           "machine": "LAPTOP-HOAN"})
    cams = {c["camera_id"]: c for c in client.get("/bridge/cameras").json()}
    assert cams[1]["online"] and cams[1]["fps"] == 15 and cams[2]["online"] is False
    assert cams[1]["machine"] == "LAPTOP-HOAN" and cams[2]["machine"] == ""


def test_camera_stream_endpoints():
    dummy_frame = b"\xff\xd8\xff\xe0dummy_jpeg_stream_data\xff\xd9"
    # Upload frame cho Camera 1
    r = client.post("/bridge/stream_frame/1", content=dummy_frame, headers={"Content-Type": "image/jpeg"})
    assert r.status_code == 200 and r.json().get("ok") is True

    # Kiem tra snapshot camera 1
    snap = client.get("/bridge/stream_snapshot/1")
    assert snap.status_code == 200
    assert snap.headers["content-type"] == "image/jpeg"
    assert snap.content == dummy_frame

    # Kiem tra /bridge/cameras co has_stream
    cams = {c["camera_id"]: c for c in client.get("/bridge/cameras").json()}
    assert cams[1]["has_stream"] is True
    assert cams[2]["has_stream"] is False

    # Camera 2 chua co frame -> snapshot 404
    assert client.get("/bridge/stream_snapshot/2").status_code == 404

    # Camera ID khong hop le -> 400
    assert client.post("/bridge/stream_frame/3", content=dummy_frame).status_code == 400
    assert client.get("/bridge/stream_snapshot/3").status_code == 400


def test_facade_and_current_stats():
    client.post("/facade_pass", json={"camera_id": 1})
    client.post("/facade_pass", json={"camera_id": 2, "count": 2})
    assert client.get("/stats/facade").json()["total"] >= 3
    cur = client.get("/stats/current").json()
    assert cur["facade_today"] >= 3 and cur["entries_today"] >= 1 and "open_incidents" in cur


def test_demographics_excludes_unknown():
    for g, a, o in [("Woman", "25-34", "Trong nuoc"), ("Man", "18-24", "Nuoc ngoai"),
                    ("Woman", "25-34", "Nuoc ngoai"), (None, "Khong xac dinh", None)]:
        client.post("/visit_events", json={"gender": g, "age_range": a, "origin": o})
    d = client.get("/stats/demographics").json()
    assert d["unknown"] >= 1 and d["identified"] == d["total"] - d["unknown"]
    assert d["gender"]["Woman"] >= 2 and d["origin"]["Nuoc ngoai"] >= 2
    rows = client.get("/visit_events", params={"gender": "unknown"}).json()
    assert rows and all(r["gender"] is None for r in rows)
    rows = client.get("/visit_events", params={"origin": "Trong nuoc"}).json()
    assert rows and all(r["origin"] == "Trong nuoc" for r in rows)


# ------------------------------------------------------------- M4 bao cao
def test_report_summary_real_data():
    import calendar
    today = datetime.utcnow() + timedelta(hours=7)
    for period in ("day", "week", "month", "year"):
        d = client.get("/reports/summary", params={"period": period}).json()
        assert "mock" not in d
        assert d["total_entries"] == sum(x["entries"] for x in d["by_day"]) == sum(x["entries"] for x in d["by_month"])
        assert len(d["by_day"]) == {"day": 1, "week": 7, "month": calendar.monthrange(today.year, today.month)[1],
                                    "year": 366 if calendar.isleap(today.year) else 365}[period]
    y = client.get("/reports/summary", params={"period": "year"}).json()
    assert len(y["by_month"]) == 12 and y["date_from"].endswith("-01-01") and y["date_to"].endswith("-12-31")
    c = client.get("/reports/summary", params={"period": "custom", "date_from": "2026-01-05", "date_to": "2026-01-20"}).json()
    assert len(c["by_day"]) == 16
    assert client.get("/reports/summary", params={"period": "custom", "date_from": "2026-02-01",
                                                  "date_to": "2026-01-01"}).status_code == 400
    day = client.get("/reports/summary", params={"period": "day"}).json()
    assert day["total_entries"] == sum(x["entries"] for x in day["by_15min"])
    assert len(day["time_slots"]) == 4 and day["incidents"] >= 1
    assert client.get("/reports/summary", params={"period": "nam"}).status_code == 400


# ------------------------------------------------------------- M5 doi chieu ve
def test_ticket_reconciliation():
    today = client.get("/bridge/state").json()["date"]
    entries = client.get("/tickets/reconciliation", params={"date": today}).json()["entries_counted"]
    assert entries > 0
    assert client.post("/tickets", json={"date": today, "ticket_count": 1}).status_code == 401
    client.post("/tickets", headers=ADMIN, json={"date": today, "ticket_count": entries - 1})
    client.post("/tickets", headers=ADMIN, json={"date": today, "ticket_count": entries - 1})  # ghi de, khong nhan doi
    d = client.get("/tickets/reconciliation", params={"date": today}).json()
    assert d["tickets_sold"] == entries - 1 and d["gap"] == 1
    assert d["gap_rate_pct"] == pytest.approx(round(1 / entries * 100, 1))
    assert len(client.get("/tickets", params={"date_from": today, "date_to": today}).json()) == 1
    assert client.post("/tickets", headers=ADMIN, json={"date": "04/11/2026", "ticket_count": 1}).status_code == 400


# ------------------------------------------------- KPI O1/O4/O5, bao sai, heatmap, bao cao ngay
def test_false_alarm_and_kpis():
    client.post("/system_events", json={"event_type": "CRITICAL_ALERT", "count": 24})
    iid = client.get("/incidents", params={"status": "open"}).json()[0]["id"]
    assert client.post(f"/incidents/{iid}/false_alarm", json={"note": "bóng người"}).status_code == 401
    d = client.post(f"/incidents/{iid}/false_alarm", headers=ADMIN, json={"note": "bóng người"}).json()
    assert d["false_alarm"] and d["false_note"] == "bóng người"
    client.post("/system_events", json={"event_type": "CRITICAL_CLEARED", "count": 10})
    client.post("/occupancy", json={"count": 99, "status": "CRITICAL"})
    k = client.get("/reports/summary", params={"period": "day"}).json()["kpis"]
    assert k["o1_minutes_over"] >= 1
    assert k["o5_false_alarms"] >= 1 and 0 < k["o5_false_alarm_pct"] <= 100
    assert k["o4_real_incidents"] >= 1 and k["o4_handled_within_3min_pct"] is not None
    # bo danh dau
    assert client.post(f"/incidents/{iid}/false_alarm", headers=ADMIN, json={"is_false": False}).json()["false_alarm"] is False


def test_heatmap_shape_and_totals():
    d = client.get("/reports/heatmap").json()
    assert len(d["cells"]) == 7 and all(len(r) == 24 for r in d["cells"])
    total = sum(map(sum, d["cells"]))
    bridge_total = client.get("/bridge/stats", params={"group": "year", "date_from": d["date_from"],
                                                         "date_to": d["date_to"]}).json()["total_entries"]
    assert total == bridge_total and sum(d["days"]) == 56
    assert client.get("/reports/heatmap", params={"date_from": "2026-12-01", "date_to": "2026-11-01"}).status_code == 400


def test_daily_report_after_closing_time():
    from datetime import datetime as dt
    from backend import daily_report
    from backend.database import SessionLocal
    from backend.timeutil import local_now
    client.put("/config", headers=ADMIN, json={"open_time": "07:00", "close_time": "21:30"})
    today = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        before = daily_report.run_due(db, today.replace(hour=12), send=False)
        assert today.strftime("%Y-%m-%d") not in before          # chua toi gio dong cua
        DOCS.clear()
        made = daily_report.run_due(db, today.replace(hour=21, minute=31), send=True)
        assert today.strftime("%Y-%m-%d") in made
        assert daily_report.run_due(db, today.replace(hour=22), send=True) == []   # khong lap lai
    lst = client.get("/reports/daily").json()
    assert lst[0]["date"] == today.strftime("%Y-%m-%d")
    pdf = client.get(f"/reports/daily/{lst[0]['date']}/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    r = client.post(f"/reports/daily/{lst[0]['date']}/send", headers=ADMIN).json()
    assert r["sent_at"] and "Đã gửi" in r["delivery"] and DOCS and DOCS[-1][1][:4] == b"%PDF"
    assert "BÁO CÁO NGÀY" in daily_report.summary_text(client.get("/reports/summary").json())
    assert client.post(f"/reports/daily/{lst[0]['date']}/send").status_code == 401
    client.put("/config", headers=ADMIN, json={"open_time": "00:00", "close_time": "23:59"})


# ------------------------------------------------- ket noi Telegram tren giao dien
class _FakeResp:
    def __init__(self, data, code=200):
        self._d, self.status_code = data, code

    def json(self):
        return self._d


def test_telegram_connect_and_find_chats(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None, **kw):
        calls.append(url)
        if "BADTOKEN" in url:
            return _FakeResp({"ok": False, "description": "Unauthorized"}, 401)
        if url.endswith("/getMe"):
            return _FakeResp({"ok": True, "result": {"username": "smartcau_bot", "first_name": "SmartCau"}})
        if url.endswith("/getUpdates"):
            return _FakeResp({"ok": True, "result": [
                {"message": {"chat": {"id": 111, "first_name": "Lê", "last_name": "Hoan", "type": "private"}}},
                {"message": {"chat": {"id": -222, "title": "Nhóm trực Chùa Cầu", "type": "group"}}},
                {"message": {"chat": {"id": 111, "first_name": "Lê", "last_name": "Hoan", "type": "private"}}}]})
        return _FakeResp({"ok": True, "result": {}})

    monkeypatch.setattr(notify.requests, "post", fake_post)
    monkeypatch.setattr(notify, "ENV_TELEGRAM_TOKEN", "")
    notify.set_db_token("")
    assert client.get("/telegram/status", headers=ADMIN).json()["connected"] is False
    assert client.put("/telegram/token", headers=ADMIN, json={"token": "khong-hop-le"}).status_code == 400
    assert client.put("/telegram/token", headers=ADMIN, json={"token": "1:BADTOKEN"}).status_code == 400
    r = client.put("/telegram/token", headers=ADMIN, json={"token": "123:GOODTOKEN"}).json()
    assert r["bot"]["username"] == "smartcau_bot"
    st = client.get("/telegram/status", headers=ADMIN).json()
    assert st["connected"] and st["source"] == "db"
    chats = client.get("/telegram/chats", headers=ADMIN).json()
    assert {c["chat_id"] for c in chats} == {"111", "-222"} and any(c["name"] == "Lê Hoan" for c in chats)
    assert notify._send_telegram("111", "thử") == "ok"
    assert client.get("/telegram/chats").status_code == 401
    assert client.delete("/telegram/token", headers=ADMIN).json()["connected"] is False
    assert "Chưa kết nối bot" in notify._send_telegram("111", "thử")


# ------------------------------------------------- nhan dinh & du bao
def test_insights_live_trend_wait_and_forecast():
    from backend.database import SessionLocal
    from backend.routers.bridge import BridgeCrossing
    from backend.timeutil import local_now
    now = local_now()
    with SessionLocal() as db:            # lich su: cung thu 1 tuan truoc, moi gio 10 luot
        for h in range(24):
            for _ in range(10):
                t = (now - timedelta(days=7)).replace(hour=h, minute=30)
                db.add(BridgeCrossing(timestamp=t, local_time=t, camera_id=1, direction="in", onbridge_after=0))
        db.commit()
    client.post("/bridge/reset", headers=ADMIN, params={"reset_dem": True})
    for _ in range(12):
        _cross(1, "in")
    _cross(2, "out")
    d = client.get("/insights/live").json()
    assert d["trend"] == "tăng" and d["in_per_min"] >= round(12 / 5, 1) and d["net_per_min"] > 0
    assert len(d["forecast"]) == 24 and d["history_days"] >= 1
    assert d["forecast"][23]["actual"] is None or now.hour == 23
    if d["onbridge"] <= d["capacity"]:
        assert d["minutes_to_full"] is not None
    # FR-17: qua tai -> thoi gian cho
    for _ in range(15):
        _cross(1, "in")
    d = client.get("/insights/live").json()
    assert d["onbridge"] > d["capacity"] and d["wait_label"] in ("Dưới 3 phút", "3–5 phút", "Trên 5 phút")


def test_insights_summary_sentences():
    items = client.get("/insights/summary").json()["items"]
    assert items and all({"tone", "title", "text"} <= set(i) for i in items)
    assert any(i["title"] in ("So với tuần trước", "Lượt khách hôm nay") for i in items)


def test_wait_buckets():
    from backend.routers.insights import wait_bucket
    assert wait_bucket(1) == "Dưới 3 phút" and wait_bucket(4) == "3–5 phút" and wait_bucket(9) == "Trên 5 phút"
    assert wait_bucket(None) is None


# ------------------------------------------------- bang LED mascot
def test_display_state_and_led_page():
    client.post("/occupancy", json={"count": 23, "status": "CRITICAL"})
    d = client.get("/display/state").json()
    assert d["level"] == "CRITICAL" and d["stale"] is False
    assert {"onbridge", "dem", "capacity", "wait_label", "utc_offset_hours"} <= set(d)
    page = client.get("/led/")
    assert page.status_code == 200 and "led.js" in page.text
    assert client.get("/led/led.js").status_code == 200
    assert client.get("/led/hai-man-hinh.html").status_code == 200
    for who in ("than", "khuyen"):
        for clip in ("idle", "wave", "bow", "yellow", "red", "walk_on", "walk_off", "walk_loop"):
            assert client.get(f"/led/media/{who}_{clip}.webm").status_code == 200, (who, clip)
    v = client.get("/led/media/than_idle.webm")
    assert v.status_code == 200 and len(v.content) > 10000
    for n in (1, 2, 3, 4):
        assert client.get(f"/led/media/scene{n}.webm").status_code == 200


# ------------------------------------------------------------------ tin nhan Telegram + bot
def test_rich_telegram_messages_include_live_status():
    from backend import messages
    from backend.database import SessionLocal
    SENT.clear()
    client.post("/bridge/reset", headers=ADMIN)
    for _ in range(3):
        client.post("/bridge/crossing", json={"camera_id": 1, "direction": "in"})
    client.post("/occupancy", json={"count": 3, "status": "WARNING"})
    client.post("/system_events", json={"event_type": "WARNING", "count": 16, "camera_id": 1})
    txt = SENT[-1]
    assert "CẢNH BÁO VÀNG" in txt and "<b>" in txt and "Chân cầu 1: <b>3</b>" in txt and "Cam 1" in txt
    client.post("/system_events", json={"event_type": "CRITICAL_ALERT", "count": 22, "camera_id": 1})
    assert "CẢNH BÁO ĐỎ" in SENT[-1] and "Sự cố #" in SENT[-1]
    client.post("/system_events", json={"event_type": "CRITICAL_ALERT", "count": 25, "camera_id": 1})
    assert "NHẮC LẠI" in SENT[-1] and "cao nhất 25" in SENT[-1]
    client.post("/system_events", json={"event_type": "CRITICAL_CLEARED", "count": 10, "camera_id": 1})
    assert "ĐÃ ĐÓNG" in SENT[-1] and "Cao nhất <b>25</b>" in SENT[-1]
    with SessionLocal() as db:
        assert "TÌNH HÌNH CHÙA CẦU" in messages.status_message(db)
        assert "HÔM NAY" in messages.today_message(db)
        assert "CHÀO BUỔI SÁNG" in messages.morning_message(db)
    assert messages.bar(25, 20).count("🟥") == 10 and messages.bar(0, 20) == "⬜" * 10


def test_telegram_bot_commands_and_ack_button():
    from backend import telegram_bot
    out, answers = [], []
    send = lambda cid, text, btn=None: out.append((cid, text, btn))   # noqa: E731
    answer = lambda qid, text: answers.append(text)                    # noqa: E731
    chat = {"id": 555, "first_name": "Khánh", "type": "private"}
    # chat la: chi nhan chat_id, khong xem duoc so lieu
    assert telegram_bot.handle_update({"message": {"chat": chat, "text": "/tinhhinh"}}, send, answer) == "unknown-chat"
    assert "555" in out[-1][1] and "TÌNH HÌNH" not in out[-1][1]
    assert telegram_bot.SEEN["555"]["name"] == "Khánh"
    client.post("/recipients", headers=ADMIN, json={"name": "Khánh", "channel": "telegram", "address": "555"})
    assert telegram_bot.handle_update({"message": {"chat": chat, "text": "/tinhhinh@smartcau_bot"}}, send, answer) == "status"
    assert "TÌNH HÌNH CHÙA CẦU" in out[-1][1] and out[-1][2]
    assert telegram_bot.handle_update({"message": {"chat": chat, "text": "/homnay"}}, send, answer) == "today"
    # nut "Da xu ly" duoi tin canh bao Do
    inc_id = client.post("/system_events", json={"event_type": "CRITICAL_ALERT", "count": 23}).json()["incident_id"]
    cq = {"callback_query": {"id": "q1", "data": f"ack:{inc_id}", "from": {"first_name": "Khánh"},
                             "message": {"chat": chat}}}
    SENT.clear()
    assert telegram_bot.handle_update(cq, send, answer) == "ack"
    inc = next(i for i in client.get("/incidents").json() if i["id"] == inc_id)
    assert inc["acknowledged"] and inc["acked_by"] == "Khánh"
    assert any("đã nhận xử lý" in t for t in SENT)
    assert telegram_bot.handle_update(cq, send, answer) == "ack-dup"
    client.post("/system_events", json={"event_type": "CRITICAL_CLEARED", "count": 5})


def test_morning_brief_and_ticket_reminder_once_per_day():
    from backend import daily_report
    from backend.database import SessionLocal
    from backend.timeutil import local_now
    client.put("/config", headers=ADMIN, json={"open_time": "07:00", "close_time": "21:30"})
    day = local_now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=30)
    SENT.clear()
    with SessionLocal() as db:
        assert "morning" in daily_report.run_due(db, day.replace(hour=7, minute=5))
        assert "morning" not in daily_report.run_due(db, day.replace(hour=7, minute=6))   # khong gui lap
        assert "ticket-reminder" in daily_report.run_due(db, day.replace(hour=21, minute=5))
        assert "ticket-reminder" not in daily_report.run_due(db, day.replace(hour=21, minute=10))
    assert any("CHÀO BUỔI SÁNG" in t for t in SENT) and any("CUỐNG VÉ" in t for t in SENT)
    client.put("/config", headers=ADMIN, json={"open_time": "00:00", "close_time": "23:59"})


def test_recipient_topics_filter_messages():
    from backend.database import SessionLocal
    from backend.routers.admin import active_recipients
    r = client.post("/recipients", headers=ADMIN, json={"name": "Quản lý Hùng", "channel": "telegram",
                                                         "address": "9001", "topics": ["red", "daily", "weekly"]}).json()
    assert r["topics"] == ["red", "daily", "weekly"]
    assert client.post("/recipients", headers=ADMIN, json={"name": "x", "address": "1", "topics": ["sai"]}).status_code == 400
    meta = client.get("/recipients/topics").json()
    assert "red" in meta["topics"] and meta["presets"]["Quản lý"] == ["red", "daily", "weekly"]
    with SessionLocal() as db:
        names_yellow = {x["name"] for x in active_recipients(db, "yellow")}
        names_red = {x["name"] for x in active_recipients(db, "red")}
    assert "Quản lý Hùng" not in names_yellow and "Quản lý Hùng" in names_red
    r = client.put(f"/recipients/{r['id']}", headers=ADMIN, json={"topics": list(meta["topics"])}).json()
    assert r["topics"] == list(meta["topics"])         # chon tat ca -> luu NULL, nhan moi loai tin
    client.delete(f"/recipients/{r['id']}", headers=ADMIN)


def test_weekly_report_compares_previous_week():
    from backend import daily_report
    from backend.database import SessionLocal
    from backend.messages import weekly_message
    from backend.timeutil import local_now
    DOCS.clear()
    res = client.post("/reports/weekly/send", headers=ADMIN).json()
    assert res["date_from"] < res["date_to"] and res["sent_ok"] >= 0
    pdf = client.get("/reports/weekly/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.post("/reports/weekly/send").status_code == 401
    with SessionLocal() as db:
        today = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        cur, prev = daily_report.weekly_summaries(db, today)
        assert len(cur["by_day"]) == 7
        from datetime import datetime as _dt
        assert _dt.strptime(cur["date_from"], "%Y-%m-%d").weekday() == 0      # Thu 2
        txt = weekly_message(cur, prev)
        assert "BÁO CÁO TUẦN" in txt and "Tổng lượt vào cầu" in txt
        monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7, hours=8)
        client.put("/config", headers=ADMIN, json={"open_time": "07:00", "close_time": "21:30"})
        assert "weekly" in daily_report.run_due(db, monday)
        assert "weekly" not in daily_report.run_due(db, monday + timedelta(hours=1))
        client.put("/config", headers=ADMIN, json={"open_time": "00:00", "close_time": "23:59"})


def test_sheets_auto_sync_skips_when_not_configured(monkeypatch):
    from backend import sheets_auto
    monkeypatch.setattr(sheets_auto, "CONF_FILE", "/khong/co.json")
    monkeypatch.setattr(sheets_auto, "KEY_FILE", "/khong/co_key.json")
    monkeypatch.delenv("GOOGLE_SHEETS_ID", raising=False)
    assert sheets_auto.load_conf()["configured"] is False
    assert sheets_auto.auto_sync_after_report() == "" and sheets_auto.sync_now() == "chưa cấu hình"


def test_ticket_reconciliation_by_day_range():
    from backend.timeutil import local_now
    t = local_now().strftime("%Y-%m-%d")
    y = (local_now() - timedelta(days=1)).strftime("%Y-%m-%d")
    client.post("/tickets", headers=ADMIN, json={"date": y, "hour": None, "ticket_count": 7})
    r = client.get("/tickets/reconciliation_range", params={"date_from": y, "date_to": t}).json()
    assert [d["date"] for d in r["days"]] == [y, t]
    assert r["days"][0]["tickets"] == 7 and r["days_with_tickets"] >= 1
    assert r["total_tickets"] == sum(d["tickets"] for d in r["days"] if d["tickets"] is not None)
    assert client.get("/tickets/reconciliation_range", params={"date_from": t, "date_to": y}).status_code == 400
