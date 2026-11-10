"""
frontend/views/camera.py  —  MODULE M1 · F1.1 Thiet lap nguon hinh & Live Stream (FR-01, NFR-03)
Phu trach: MINH.
Trang thai va luong hinh anh truc tiep (Live Stream) tu 2 camera chan cau.
Tu dong nhan luong MJPEG tu FastAPI backend (/bridge/stream/{id}).
"""

import streamlit as st

from common import badge, fmt_time, page_header, public_api_base, safe_get

page_header("Hệ thống · Nguồn hình & Giám sát", "Camera Chân Cầu",
            "Giám sát hình ảnh trực tiếp (Live Stream) và tình trạng kết nối 2 camera chân cầu Chùa Cầu.")

base = public_api_base()


def render_live_view(rows):
    st.markdown('<div class="sc-eyebrow" style="margin-bottom:8px">GIÁM SÁT TRỰC TIẾP TẬP TRUNG</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    cam_labels = {
        1: "Đầu Chùa Cầu (Cổng Chính / Cam 1)",
        2: "Đầu Cầu đối diện (Cổng Ra / Cam 2)",
    }

    for col, c in zip(cols, rows):
        cid = c["camera_id"]
        stream_url = f"{base}/bridge/stream/{cid}"
        snapshot_url = f"{base}/bridge/stream_snapshot/{cid}"
        is_online = c.get("online", False)
        has_stream = c.get("has_stream", False)

        with col, st.container(border=True):
            st.markdown(f'<div class="sc-eyebrow">CHÂN CẦU {cid}</div>'
                        f'<div class="sc-title" style="font-size:1.45rem; margin-bottom: 6px;">{cam_labels.get(cid, f"Camera {cid}")}</div>',
                        unsafe_allow_html=True)

            status_cols = st.columns([2, 1])
            with status_cols[0]:
                if is_online:
                    st.markdown(badge(f"Online · {c.get('fps', 0)} FPS", "ok"), unsafe_allow_html=True)
                elif c.get("last_seen"):
                    st.markdown(badge(f"Mất tín hiệu ({fmt_time(c['last_seen'], '%H:%M:%S')})", "danger"), unsafe_allow_html=True)
                else:
                    st.markdown(badge("Chưa kết nối", "muted"), unsafe_allow_html=True)
            with status_cols[1]:
                st.caption(f"Nguồn: `{c.get('source') or 'Chưa rõ'}`")

            # Video feed container
            if is_online or has_stream:
                st.markdown(
                    f"""
                    <div style="background-color: #151311; border-radius: 4px; overflow: hidden; position: relative; border: 1px solid #4a3e35; margin-top: 10px; margin-bottom: 10px; text-align: center;">
                        <div style="position: absolute; top: 8px; left: 8px; z-index: 10; background: rgba(125, 35, 24, 0.9); color: #fff; padding: 2px 8px; border-radius: 2px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;">
                            ● LIVE STREAM
                        </div>
                        <img src="{stream_url}" style="width: 100%; height: auto; min-height: 260px; max-height: 480px; display: block; object-fit: contain; margin: 0 auto;" alt="Live stream Camera {cid}" onerror="this.onerror=null; this.src='{snapshot_url}';" />
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="background-color: #24201D; border-radius: 4px; padding: 48px 16px; text-align: center; border: 1px dashed #5A3E2B; color: #B9AE9F; margin-top: 10px; margin-bottom: 10px;">
                        <div style="font-size: 32px; margin-bottom: 10px; color: #776B5F;">📷</div>
                        <div style="font-weight: 600; font-size: 15px; color: #F5F0E6; margin-bottom: 6px;">Camera {cid} hiện chưa phát luồng trực tiếp</div>
                        <div style="font-size: 12px; color: #B9AE9F; margin-bottom: 8px;">Khởi chạy camera bridge trên máy trạm hoặc máy chủ:</div>
                        <code style="background: #151311; color: #C9A45C; padding: 4px 10px; border-radius: 3px; font-size: 12px;">python ai_engine/camera_bridge.py --camera-id {cid} --source 0</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.expander(f"Thao tác & Ảnh chụp Camera {cid}", expanded=False):
                st.write(f"- Đường dẫn xem trực tiếp MJPEG: [{stream_url}]({stream_url})")
                st.write(f"- Ảnh snapshot tức thời: [{snapshot_url}]({snapshot_url})")
                if st.button(f"Tải lại khung hình Camera {cid}", key=f"snap_btn_{cid}"):
                    st.rerun()


@st.fragment(run_every=5)
def render_status_view():
    rows = safe_get("/bridge/cameras")
    if rows is None:
        return
    st.markdown('<div class="sc-eyebrow" style="margin-top:12px; margin-bottom:8px">THÔNG SỐ KỸ THUẬT & NHỊP TIM CAMERA</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for col, c in zip(cols, rows):
        with col, st.container(border=True):
            st.markdown(f'<div class="sc-eyebrow">Chân cầu {c["camera_id"]}</div>'
                        f'<div class="sc-title" style="font-size:1.5rem">Camera {c["camera_id"]}</div>', unsafe_allow_html=True)
            if c["online"]:
                st.markdown(badge(f"Đang hoạt động · {c['fps']} khung hình/giây", "ok"), unsafe_allow_html=True)
            elif c["last_seen"]:
                st.markdown(badge(f"Mất tín hiệu từ {fmt_time(c['last_seen'], '%H:%M:%S %d/%m')}", "danger"),
                            unsafe_allow_html=True)
            else:
                st.markdown(badge("Chưa từng kết nối", "muted"), unsafe_allow_html=True)
            st.markdown(f"""
- **Máy chạy camera:** {c.get('machine') or '–'}
- **Nguồn hình:** `{c['source'] or '–'}`
- **Vạch kẻ:** {c['line'] or '–'}
- **Gửi mức cảnh báo:** {'Có' if c['sends_alerts'] else 'Không'}
- **Nhận diện giới tính / tuổi / nguồn khách:** {'Bật' if c['demographics'] else 'Tắt'}
- **Luồng Live Stream:** {'Đang phát' if c.get('has_stream') else 'Chưa có'}
- **Khởi động từ:** {fmt_time(c['started_at'], '%H:%M %d/%m/%Y')}
""")


# Tabs giao dien
tab_stream, tab_info = st.tabs(["🎥 Xem Trực Tiếp (Live Stream)", "⚙️ Cấu Hình & Tình Trạng Thiết Bị"])

with tab_stream:
    current_rows = safe_get("/bridge/cameras") or [
        {"camera_id": 1, "online": False, "source": "", "has_stream": False},
        {"camera_id": 2, "online": False, "source": "", "has_stream": False},
    ]
    render_live_view(current_rows)

with tab_info:
    render_status_view()
