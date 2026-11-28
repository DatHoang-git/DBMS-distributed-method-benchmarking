#!/usr/bin/env python3
"""Generate publication-ready vector architecture figures (SVG -> PNG + PDF) for Chapters 1 & 2."""

import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent
FIG_DIR = REPO / "report" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Official IEEE Brand Color Palette
IEEE_BLUE = "#00629B"
IEEE_BLUE_DARK = "#002855"
IEEE_BLUE_LIGHT = "#EBF4FA"
IEEE_BLUE_BORDER = "#7AB2D3"

IEEE_TEAL = "#007377"
IEEE_TEAL_DARK = "#004B4E"
IEEE_TEAL_LIGHT = "#E6F4F4"
IEEE_TEAL_BORDER = "#66B2B5"

IEEE_GREEN = "#00843D"
IEEE_GREEN_DARK = "#005A29"
IEEE_GREEN_LIGHT = "#EAF6EF"
IEEE_GREEN_BORDER = "#6EC194"

IEEE_ORANGE = "#D96B16"
IEEE_ORANGE_DARK = "#8F4207"
IEEE_ORANGE_LIGHT = "#FDF3E7"
IEEE_ORANGE_BORDER = "#E8A46B"

IEEE_GRAY_DARK = "#53565A"
IEEE_GRAY = "#63666A"
IEEE_GRAY_MID = "#A7A8AA"
IEEE_GRAY_LIGHT = "#F4F6F8"
IEEE_INK = "#1A1D20"

FONT = "DejaVu Sans, sans-serif"

ICON_USERS = '''
  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
  <circle cx="9" cy="7" r="4"/>
  <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
'''
ICON_DATABASE = '''
  <ellipse cx="12" cy="5" rx="8.5" ry="3"/>
  <path d="M3.5 5v14c0 1.66 3.8 3 8.5 3s8.5-1.34 8.5-3V5"/>
  <path d="M3.5 12c0 1.66 3.8 3 8.5 3s8.5-1.34 8.5-3"/>
'''
ICON_SERVER = '''
  <rect x="2" y="2" width="20" height="7" rx="2"/>
  <rect x="2" y="13" width="20" height="7" rx="2"/>
  <line x1="6" y1="5.5" x2="6.01" y2="5.5" stroke-width="2.6"/>
  <line x1="6" y1="16.5" x2="6.01" y2="16.5" stroke-width="2.6"/>
  <line x1="11" y1="5.5" x2="18" y2="5.5"/>
  <line x1="11" y1="16.5" x2="18" y2="16.5"/>
'''
ICON_LAYERS = '''
  <polygon points="12 2 2 7 12 12 22 7 12 2"/>
  <polyline points="2 17 12 22 22 17"/>
  <polyline points="2 12 12 17 22 12"/>
'''
ICON_GEAR = '''
  <circle cx="12" cy="12" r="3"/>
  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.6.85 1 1.51 1H21a2 2 0 0 1 0 4h-.09c-.66 0-1.25.4-1.51 1z"/>
'''
ICON_NETWORK = '''
  <circle cx="12" cy="5" r="2.7"/>
  <circle cx="5.5" cy="18" r="2.7"/>
  <circle cx="18.5" cy="18" r="2.7"/>
  <line x1="10.8" y1="7.4" x2="6.7" y2="15.6"/>
  <line x1="13.2" y1="7.4" x2="17.3" y2="15.6"/>
  <line x1="8.2" y1="18" x2="15.8" y2="18"/>
'''
ICON_DOC = '''
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
  <polyline points="14 2 14 8 20 8"/>
  <line x1="8" y1="13" x2="16" y2="13"/>
  <line x1="8" y1="17" x2="13" y2="17"/>
'''
ICON_CPU = '''
  <rect x="6" y="6" width="12" height="12" rx="2"/>
  <rect x="9.5" y="9.5" width="5" height="5" rx="0.8"/>
  <line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/>
  <line x1="9" y1="18" x2="9" y2="22"/><line x1="15" y1="18" x2="15" y2="22"/>
  <line x1="2" y1="9" x2="6" y2="9"/><line x1="2" y1="15" x2="6" y2="15"/>
  <line x1="18" y1="9" x2="22" y2="9"/><line x1="18" y1="15" x2="22" y2="15"/>
'''
ICON_CHECK = '''
  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
  <polyline points="22 4 12 14.01 9 11.01"/>
'''


def svg_header(w, h):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <filter id="cardShadow" x="-6%" y="-6%" width="112%" height="114%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0F172A" flood-opacity="0.08"/>
    </filter>
    <marker id="arrBlue" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
      <path d="M 0 1.2 L 9 5 L 0 8.8 z" fill="{IEEE_BLUE}"/>
    </marker>
    <marker id="arrTeal" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
      <path d="M 0 1.2 L 9 5 L 0 8.8 z" fill="{IEEE_TEAL}"/>
    </marker>
    <marker id="arrGreen" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
      <path d="M 0 1.2 L 9 5 L 0 8.8 z" fill="{IEEE_GREEN}"/>
    </marker>
    <marker id="arrOrange" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
      <path d="M 0 1.2 L 9 5 L 0 8.8 z" fill="{IEEE_ORANGE}"/>
    </marker>
    <marker id="arrGray" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.2 L 9 5 L 0 8.8 z" fill="{IEEE_GRAY_MID}"/>
    </marker>
  </defs>
  <rect x="0" y="0" width="{w}" height="{h}" fill="#FFFFFF"/>
'''


def rounded_path(points, r=8):
    if len(points) < 2:
        return ""
    d = [f"M {points[0][0]},{points[0][1]}"]
    for i in range(1, len(points) - 1):
        p0, p1, p2 = points[i - 1], points[i], points[i + 1]
        dx1, dy1 = p1[0] - p0[0], p1[1] - p0[1]
        dx2, dy2 = p2[0] - p1[0], p2[1] - p1[1]
        len1 = abs(dx1) + abs(dy1)
        len2 = abs(dx2) + abs(dy2)
        cr = min(r, len1 / 2, len2 / 2)
        ux1 = 0 if len1 == 0 else dx1 / len1
        uy1 = 0 if len1 == 0 else dy1 / len1
        ux2 = 0 if len2 == 0 else dx2 / len2
        uy2 = 0 if len2 == 0 else dy2 / len2
        q_start = (p1[0] - ux1 * cr, p1[1] - uy1 * cr)
        q_end = (p1[0] + ux2 * cr, p1[1] + uy2 * cr)
        d.append(f"L {q_start[0]:.1f},{q_start[1]:.1f}")
        d.append(f"Q {p1[0]:.1f},{p1[1]:.1f} {q_end[0]:.1f},{q_end[1]:.1f}")
    d.append(f"L {points[-1][0]},{points[-1][1]}")
    return " ".join(d)


def card_bg(x, y, w, h, rx=10, fill="#FFFFFF", shadow=True):
    filt = ' filter="url(#cardShadow)"' if shadow else ""
    return f'  <g{filt}><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"/></g>\n'


def card_border(x, y, w, h, rx=10, stroke=IEEE_BLUE_BORDER, sw=1.5, dash=""):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="none" stroke="{stroke}" stroke-width="{sw}"{da}/>\n'


def icon_badge(cx, cy, bg, stroke, inner_svg, size=34, icon_scale=0.82):
    half = size / 2
    tx = cx - 12 * icon_scale
    ty = cy - 12 * icon_scale
    return (
        f'  <rect x="{cx - half}" y="{cy - half}" width="{size}" height="{size}" rx="{size * 0.24:.1f}" '
        f'fill="{bg}" stroke="{stroke}" stroke-opacity="0.3" stroke-width="1.2"/>\n'
        f'  <g transform="translate({tx:.2f},{ty:.2f}) scale({icon_scale})" '
        f'fill="none" stroke="{stroke}" stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round">\n'
        f'    {inner_svg}\n  </g>\n'
    )


def text(x, y, s, size=13, weight="normal", fill=IEEE_INK, anchor="start", style="normal"):
    return (
        f'  <text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" font-style="{style}" fill="{fill}" text-anchor="{anchor}">{escape(str(s))}</text>\n'
    )


def build_fig1_1():
    """Fig 1.1: MongoDB node architecture (Document model, B-Tree, 2-layer WiredTiger cache, SSD, Replica Set)."""
    w, h = 1000, 500
    parts = [svg_header(w, h)]

    # Zone headers (clean, no enclosing border clutter)
    parts.append(text(129, 30, "Đầu vào & Mô hình Tài liệu", 13.5, "bold", IEEE_BLUE_DARK, "middle"))
    parts.append(text(484, 30, "Bên trong Nút Lưu trữ (mongod - Primary)", 13.5, "bold", IEEE_TEAL_DARK, "middle"))
    parts.append(text(865, 30, "Sẵn sàng cao (Replica Set)", 13.5, "bold", IEEE_GREEN_DARK, "middle"))

    # --- LEFT COLUMN (x=24..234, w=210) ---
    # Top card: Client Read/Write requests
    parts.append(card_bg(24, 60, 210, 108, 10, "#FFFFFF"))
    parts.append(card_border(24, 60, 210, 108, 10, IEEE_BLUE_BORDER, 1.5))
    parts.append(icon_badge(54, 94, IEEE_BLUE_LIGHT, IEEE_BLUE, ICON_USERS, 34))
    parts.append(text(80, 91, "Truy vấn Đọc / Ghi", 13, "bold", IEEE_BLUE_DARK))
    parts.append(text(80, 109, "Từ ứng dụng hoặc", 11, "normal", IEEE_GRAY))
    parts.append(text(80, 125, "bộ định tuyến mongos", 11, "normal", IEEE_GRAY))
    parts.append(text(129, 152, "Xử lý song song qua MVCC", 10.5, "bold", IEEE_BLUE, "middle"))

    # Bottom card: BSON Document structure
    parts.append(card_bg(24, 200, 210, 266, 10, IEEE_GRAY_LIGHT))
    parts.append(card_border(24, 200, 210, 266, 10, IEEE_GRAY_MID, 1.4))
    parts.append(icon_badge(54, 232, "#FFFFFF", IEEE_GRAY_DARK, ICON_DOC, 32))
    parts.append(text(78, 229, "Tài liệu BSON", 13, "bold", IEEE_INK))
    parts.append(text(78, 245, "Mã hóa nhị phân", 10.5, "normal", IEEE_GRAY))

    # Mini field pills inside BSON card
    for fy, title, sub, bg, bd, tc in [
        (266, "Trường thông tin phẳng", "Mã lượt khám, bệnh nhân, giờ", "#FFFFFF", IEEE_BLUE_BORDER, IEEE_BLUE_DARK),
        (320, "Mảng chẩn đoán nhúng", "Danh sách mã bệnh đi kèm", "#FFFFFF", IEEE_TEAL_BORDER, IEEE_TEAL_DARK),
        (374, "Mảng xét nghiệm nhúng", "Chỉ số sinh học & đơn vị đo", "#FFFFFF", IEEE_TEAL_BORDER, IEEE_TEAL_DARK),
    ]:
        parts.append(f'  <rect x="36" y="{fy}" width="186" height="44" rx="6" fill="{bg}" stroke="{bd}" stroke-width="1.1"/>\n')
        parts.append(text(46, fy + 18, title, 11, "bold", tc))
        parts.append(text(46, fy + 34, sub, 10, "normal", IEEE_GRAY))

    parts.append(text(129, 443, "Gói gọn 1 lượt khám / bản ghi", 10.5, "bold", IEEE_GRAY_DARK, "middle"))
    parts.append(text(129, 458, "(không cần phép nối nhiều bảng)", 10, "italic", IEEE_GRAY, "middle"))

    # --- CENTER ZONE (x=294..674, w=380, y=50..466) ---
    parts.append(card_bg(294, 50, 380, 416, 12, "#FAFBFD"))
    parts.append(card_border(294, 50, 380, 416, 12, IEEE_TEAL_BORDER, 1.8))

    # 1. B-Tree Index
    parts.append(card_bg(314, 64, 340, 66, 9, "#FFFFFF"))
    parts.append(card_border(314, 64, 340, 66, 9, IEEE_BLUE, 1.5))
    parts.append(icon_badge(344, 97, IEEE_BLUE_LIGHT, IEEE_BLUE, ICON_LAYERS, 32, 0.76))
    parts.append(text(370, 91, "Chỉ mục B-Tree (Đơn / Phức hợp / Mảng)", 12.0, "bold", IEEE_BLUE_DARK))
    parts.append(text(370, 110, "Định vị nhanh khóa tìm kiếm, tránh quét toàn bộ", 10.5, "normal", IEEE_GRAY))

    # Arrow B-Tree -> WiredTiger
    parts.append(f'  <line x1="484" y1="130" x2="484" y2="152" stroke="{IEEE_BLUE}" stroke-width="1.8" marker-end="url(#arrBlue)"/>\n')
    parts.append(text(494, 145, "Truy xuất trang chỉ mục & dữ liệu", 10.0, "normal", IEEE_BLUE_DARK))

    # 2. WiredTiger Storage Engine (Tier 1 cache INSIDE mongod/WiredTiger)
    parts.append(card_bg(314, 156, 340, 102, 10, IEEE_TEAL_LIGHT))
    parts.append(card_border(314, 156, 340, 102, 10, IEEE_TEAL, 1.6))
    parts.append(text(326, 177, "Bộ máy WiredTiger", 12.0, "bold", IEEE_TEAL_DARK))
    parts.append(f'  <rect x="478" y="162" width="164" height="22" rx="11" fill="#FFFFFF" stroke="{IEEE_TEAL_BORDER}" stroke-width="1"/>\n')
    parts.append(text(560, 177, "MVCC & Khóa mức tài liệu", 9.8, "bold", IEEE_TEAL_DARK, "middle"))

    # Tier 1: WT Internal Cache
    parts.append(card_bg(328, 192, 312, 56, 8, "#FFFFFF", shadow=False))
    parts.append(card_border(328, 192, 312, 56, 8, IEEE_TEAL, 1.3))
    parts.append(icon_badge(354, 220, IEEE_TEAL_LIGHT, IEEE_TEAL, ICON_CPU, 30, 0.72))
    parts.append(text(378, 214, "Tầng 1: WiredTiger Internal Cache", 11.6, "bold", IEEE_TEAL_DARK))
    parts.append(text(378, 232, "Giữ trang dữ liệu & chỉ mục đã giải nén", 10.3, "normal", IEEE_GRAY))

    # Bidirectional arrow WiredTiger <-> OS Page Cache
    parts.append(f'  <line x1="484" y1="260" x2="484" y2="286" stroke="{IEEE_TEAL}" stroke-width="1.8" marker-start="url(#arrTeal)" marker-end="url(#arrTeal)"/>\n')
    parts.append(text(494, 277, "Đọc / ghi khối tệp nén qua nhân OS", 9.8, "normal", IEEE_TEAL_DARK))

    # 3. Tier 2: OS Page Cache (OUTSIDE WiredTiger, managed by OS Kernel)
    parts.append(card_bg(314, 290, 340, 62, 9, IEEE_BLUE_LIGHT))
    parts.append(card_border(314, 290, 340, 62, 9, IEEE_BLUE, 1.5))
    parts.append(icon_badge(344, 321, "#FFFFFF", IEEE_BLUE, ICON_SERVER, 32, 0.74))
    parts.append(text(370, 314, "Tầng 2: OS Page Cache (Nhân OS)", 11.8, "bold", IEEE_BLUE_DARK))
    parts.append(text(370, 333, "Ngoài WiredTiger; đệm khối tệp nén Snappy", 10.3, "normal", IEEE_GRAY))

    # Bidirectional arrow OS Page Cache <-> SSD (RQ1 overflow)
    parts.append(f'  <line x1="418" y1="354" x2="418" y2="394" stroke="{IEEE_ORANGE}" stroke-width="2.0" marker-start="url(#arrOrange)" marker-end="url(#arrOrange)"/>\n')
    parts.append(f'  <rect x="430" y="363" width="218" height="22" rx="6" fill="{IEEE_ORANGE_LIGHT}" stroke="{IEEE_ORANGE_BORDER}" stroke-width="1"/>\n')
    parts.append(text(539, 378, "Đọc trang từ đĩa khi tràn RAM (RQ1)", 10.5, "bold", IEEE_ORANGE_DARK, "middle"))

    # 4. SSD Disk
    parts.append(card_bg(314, 398, 340, 56, 9, "#FFFFFF"))
    parts.append(card_border(314, 398, 340, 56, 9, IEEE_GRAY_DARK, 1.5))
    parts.append(icon_badge(344, 426, IEEE_GRAY_LIGHT, IEEE_GRAY_DARK, ICON_DATABASE, 32, 0.76))
    parts.append(text(370, 421, "Ổ đĩa SSD (Lưu trữ bền vững)", 12.2, "bold", IEEE_INK))
    parts.append(text(370, 439, "Tệp dữ liệu nén & nhật ký khôi phục", 10.5, "normal", IEEE_GRAY))

    # --- RIGHT COLUMN (x=744..978, w=234) ---
    parts.append(card_bg(744, 60, 234, 406, 12, IEEE_GREEN_LIGHT))
    parts.append(card_border(744, 60, 234, 406, 12, IEEE_GREEN_BORDER, 1.5, "6,4"))
    parts.append(text(861, 86, "Các nút phụ (Secondary)", 12.5, "bold", IEEE_GREEN_DARK, "middle"))

    for ry, name, desc in [
        (106, "Secondary 1", "Đồng bộ nhật ký từ Primary"),
        (210, "Secondary 2", "Dự phòng, sẵn sàng bầu chọn"),
    ]:
        parts.append(card_bg(758, ry, 206, 82, 9, "#FFFFFF"))
        parts.append(card_border(758, ry, 206, 82, 9, IEEE_GREEN, 1.4))
        parts.append(icon_badge(782, ry + 41, IEEE_GREEN_LIGHT, IEEE_GREEN, ICON_SERVER, 30, 0.72))
        parts.append(text(803, ry + 35, name, 12.0, "bold", IEEE_GREEN_DARK))
        parts.append(text(803, ry + 54, desc, 9.6, "normal", IEEE_GRAY))

    # Experimental scope note card
    parts.append(card_bg(758, 322, 206, 124, 9, "#FFFFFF", shadow=False))
    parts.append(card_border(758, 322, 206, 124, 9, IEEE_ORANGE_BORDER, 1.3))
    parts.append(text(861, 346, "Phạm vi thực nghiệm", 11.5, "bold", IEEE_ORANGE_DARK, "middle"))
    parts.append(text(861, 368, "Mỗi nút dữ liệu chạy dạng", 10.5, "normal", IEEE_INK, "middle"))
    parts.append(text(861, 385, "Replica Set 1 thành viên", 10.8, "bold", IEEE_INK, "middle"))
    parts.append(text(861, 404, "(vẫn ghi nhật ký oplog", 10.2, "normal", IEEE_GRAY, "middle"))
    parts.append(text(861, 420, "để đối chứng công bằng)", 10.2, "normal", IEEE_GRAY, "middle"))

    # --- CONNECTING ARROWS BETWEEN COLUMNS ---
    # Left Query -> Center B-Tree / mongod
    parts.append(f'  <path d="{rounded_path([(234, 97), (310, 97)])}" fill="none" stroke="{IEEE_BLUE}" stroke-width="2.2" marker-end="url(#arrBlue)"/>\n')
    # Left BSON -> Center WiredTiger
    parts.append(f'  <path d="{rounded_path([(234, 244), (264, 244), (264, 220), (324, 220)])}" fill="none" stroke="{IEEE_GRAY_DARK}" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arrTeal)"/>\n')
    parts.append(text(264, 208, "Nạp", 10, "bold", IEEE_GRAY_DARK, "middle"))

    # Center -> Right Replica Set via oplog
    parts.append(f'  <path d="{rounded_path([(674, 200), (714, 200), (714, 147), (754, 147)])}" fill="none" stroke="{IEEE_GREEN}" stroke-width="1.9" stroke-dasharray="5,3" marker-end="url(#arrGreen)"/>\n')
    parts.append(f'  <path d="{rounded_path([(714, 200), (714, 251), (754, 251)])}" fill="none" stroke="{IEEE_GREEN}" stroke-width="1.9" stroke-dasharray="5,3" marker-end="url(#arrGreen)"/>\n')
    parts.append(f'  <rect x="679" y="164" width="60" height="22" rx="6" fill="#FFFFFF" stroke="{IEEE_GREEN_BORDER}" stroke-width="1"/>\n')
    parts.append(text(709, 179, "oplog", 10.8, "bold", IEEE_GREEN_DARK, "middle"))

    parts.append("</svg>\n")
    return "".join(parts)


def build_fig2_1():
    """Fig 2.1: Shard Pruning (1/2 shard) vs Scatter-Gather (2/2 shard)."""
    w, h = 1000, 500
    parts = [svg_header(w, h)]

    # Vertical separator
    parts.append(f'  <line x1="500" y1="22" x2="500" y2="482" stroke="{IEEE_GRAY_MID}" stroke-width="1.2" stroke-dasharray="5,5"/>\n')

    # ================= LEFT PANEL: SHARD PRUNING =================
    parts.append(text(250, 32, "Chế độ 1: Định tuyến mục tiêu (Shard Pruning - 1/2 shard)", 13.5, "bold", IEEE_GREEN_DARK, "middle"))

    # Query input
    parts.append(card_bg(42, 52, 416, 60, 9, "#FFFFFF"))
    parts.append(card_border(42, 52, 416, 60, 9, IEEE_GREEN, 1.6))
    parts.append(icon_badge(73, 82, IEEE_GREEN_LIGHT, IEEE_GREEN, ICON_DOC, 30, 0.72))
    parts.append(text(98, 77, "Truy vấn chứa khóa phân mảnh", 12.2, "bold", IEEE_GREEN_DARK))
    parts.append(text(98, 96, "VD: Q1 theo bệnh nhân (băm), Q2/Q3 theo ngày (khoảng)", 10.0, "normal", IEEE_GRAY))

    parts.append(f'  <line x1="250" y1="112" x2="250" y2="142" stroke="{IEEE_GREEN}" stroke-width="2" marker-end="url(#arrGreen)"/>\n')

    # mongos router
    parts.append(card_bg(105, 146, 290, 56, 9, IEEE_BLUE_LIGHT))
    parts.append(card_border(105, 146, 290, 56, 9, IEEE_BLUE, 1.6))
    parts.append(icon_badge(135, 174, "#FFFFFF", IEEE_BLUE, ICON_NETWORK, 30, 0.72))
    parts.append(text(160, 169, "Bộ định tuyến mongos", 12.2, "bold", IEEE_BLUE_DARK))
    parts.append(text(160, 187, "Tra bảng ánh xạ metadata → chốt 1 shard", 10.3, "normal", IEEE_GRAY))

    # Branch left (active) & right (pruned)
    parts.append(f'  <path d="{rounded_path([(195, 202), (195, 224), (138, 224), (138, 250)])}" fill="none" stroke="{IEEE_GREEN}" stroke-width="2.4" marker-end="url(#arrGreen)"/>\n')
    parts.append(f'  <path d="{rounded_path([(305, 202), (305, 224), (362, 224), (362, 250)])}" fill="none" stroke="{IEEE_GRAY_MID}" stroke-width="1.6" stroke-dasharray="4,3" marker-end="url(#arrGray)"/>\n')
    # Cross badge on pruned path
    parts.append(f'  <circle cx="362" cy="224" r="9" fill="#FFFFFF" stroke="{IEEE_ORANGE}" stroke-width="1.5"/>\n')
    parts.append(text(362, 228, "x", 11.5, "bold", IEEE_ORANGE_DARK, "middle"))

    # Shard 1 (Active)
    parts.append(card_bg(42, 254, 192, 92, 9, "#FFFFFF"))
    parts.append(card_border(42, 254, 192, 92, 9, IEEE_GREEN, 2.0))
    parts.append(icon_badge(70, 286, IEEE_GREEN_LIGHT, IEEE_GREEN, ICON_DATABASE, 30, 0.72))
    parts.append(text(94, 282, "Shard 1", 12.5, "bold", IEEE_GREEN_DARK))
    parts.append(text(94, 299, "Chứa dải khóa khớp", 10.3, "normal", IEEE_GRAY))
    parts.append(f'  <rect x="56" y="314" width="164" height="22" rx="5" fill="{IEEE_GREEN_LIGHT}"/>\n')
    parts.append(text(138, 329, "Thực thi đơn mảnh (1/2)", 10.5, "bold", IEEE_GREEN_DARK, "middle"))

    # Shard 2 (Pruned)
    parts.append(card_bg(266, 254, 192, 92, 9, IEEE_GRAY_LIGHT, shadow=False))
    parts.append(card_border(266, 254, 192, 92, 9, IEEE_GRAY_MID, 1.4, "5,3"))
    parts.append(icon_badge(294, 286, "#FFFFFF", IEEE_GRAY_MID, ICON_DATABASE, 30, 0.72))
    parts.append(text(318, 282, "Shard 2", 12.5, "bold", IEEE_GRAY))
    parts.append(text(318, 299, "Không khớp điều kiện", 10.3, "normal", IEEE_GRAY))
    parts.append(f'  <rect x="280" y="314" width="164" height="22" rx="5" fill="#E8ECEF"/>\n')
    parts.append(text(362, 329, "Bỏ qua (Tỉa mảnh)", 10.5, "bold", IEEE_GRAY_DARK, "middle"))

    # Arrow from Shard 1 straight to result
    parts.append(f'  <path d="{rounded_path([(138, 346), (138, 378), (250, 378), (250, 412)])}" fill="none" stroke="{IEEE_GREEN}" stroke-width="2.2" marker-end="url(#arrGreen)"/>\n')
    parts.append(text(255, 396, "Trả thẳng kết quả", 10.5, "bold", IEEE_GREEN_DARK))

    # Result box Left
    parts.append(card_bg(65, 416, 370, 58, 9, IEEE_GREEN_LIGHT))
    parts.append(card_border(65, 416, 370, 58, 9, IEEE_GREEN, 1.6))
    parts.append(icon_badge(96, 445, "#FFFFFF", IEEE_GREEN, ICON_CHECK, 28, 0.68))
    parts.append(text(122, 440, "Kết quả cuối cùng (Không cần trộn)", 12, "bold", IEEE_GREEN_DARK))
    parts.append(text(122, 458, "Tiết kiệm CPU, băng thông mạng và độ trễ điều phối", 10.3, "normal", IEEE_GRAY_DARK))

    # ================= RIGHT PANEL: SCATTER-GATHER =================
    parts.append(text(750, 32, "Chế độ 2: Phát tán - Thu gom (Scatter-Gather - 2/2 shard)", 13.5, "bold", IEEE_BLUE_DARK, "middle"))

    # Query input
    parts.append(card_bg(542, 52, 416, 60, 9, "#FFFFFF"))
    parts.append(card_border(542, 52, 416, 60, 9, IEEE_ORANGE, 1.6))
    parts.append(icon_badge(573, 82, IEEE_ORANGE_LIGHT, IEEE_ORANGE, ICON_DOC, 30, 0.72))
    parts.append(text(598, 77, "Truy vấn không khớp khóa phân mảnh", 12.2, "bold", IEEE_ORANGE_DARK))
    parts.append(text(598, 96, "VD: Q2, Q3 lọc thời gian trên SH-hash; Q1 trên SH-range", 10.0, "normal", IEEE_GRAY))

    parts.append(f'  <line x1="750" y1="112" x2="750" y2="142" stroke="{IEEE_BLUE}" stroke-width="2" marker-end="url(#arrBlue)"/>\n')

    # mongos router
    parts.append(card_bg(605, 146, 290, 56, 9, IEEE_BLUE_LIGHT))
    parts.append(card_border(605, 146, 290, 56, 9, IEEE_BLUE, 1.6))
    parts.append(icon_badge(635, 174, "#FFFFFF", IEEE_BLUE, ICON_NETWORK, 30, 0.72))
    parts.append(text(660, 169, "Bộ định tuyến mongos", 12.2, "bold", IEEE_BLUE_DARK))
    parts.append(text(660, 187, "Phát tán đồng thời tới toàn bộ 2 shard", 10.3, "normal", IEEE_GRAY))

    # Two active branches
    parts.append(f'  <path d="{rounded_path([(695, 202), (695, 224), (638, 224), (638, 246)])}" fill="none" stroke="{IEEE_BLUE}" stroke-width="2.2" marker-end="url(#arrBlue)"/>\n')
    parts.append(f'  <path d="{rounded_path([(805, 202), (805, 224), (862, 224), (862, 246)])}" fill="none" stroke="{IEEE_BLUE}" stroke-width="2.2" marker-end="url(#arrBlue)"/>\n')

    for sx, sname in [(542, "Shard 1"), (766, "Shard 2")]:
        parts.append(card_bg(sx, 250, 192, 78, 9, "#FFFFFF"))
        parts.append(card_border(sx, 250, 192, 78, 9, IEEE_BLUE, 1.6))
        parts.append(icon_badge(sx + 28, 280, IEEE_BLUE_LIGHT, IEEE_BLUE, ICON_DATABASE, 28, 0.68))
        parts.append(text(sx + 50, 276, sname, 12.2, "bold", IEEE_BLUE_DARK))
        parts.append(text(sx + 50, 293, "Quét song song (~50%)", 10.2, "normal", IEEE_GRAY))
        parts.append(text(sx + 96, 317, "Trả tập kết quả trung gian", 10, "bold", IEEE_BLUE, "middle"))

    # Converging arrows to Merge box
    parts.append(f'  <path d="{rounded_path([(638, 328), (638, 346), (695, 346), (695, 360)])}" fill="none" stroke="{IEEE_ORANGE}" stroke-width="2.0" marker-end="url(#arrOrange)"/>\n')
    parts.append(f'  <path d="{rounded_path([(862, 328), (862, 346), (805, 346), (805, 360)])}" fill="none" stroke="{IEEE_ORANGE}" stroke-width="2.0" marker-end="url(#arrOrange)"/>\n')

    # Merge box
    parts.append(card_bg(545, 364, 410, 74, 9, IEEE_ORANGE_LIGHT))
    parts.append(card_border(545, 364, 410, 74, 9, IEEE_ORANGE, 1.6))
    parts.append(text(750, 386, "Gom & Trộn kết quả (Chờ nút chậm nhất + Chi phí mạng)", 11.6, "bold", IEEE_ORANGE_DARK, "middle"))
    parts.append(text(750, 407, "- Truy vấn liệt kê: Trộn luồng tài liệu lớn tại mongos (Q3)", 10.2, "normal", IEEE_INK, "middle"))
    parts.append(text(750, 424, "- Truy vấn tổng hợp: Gom cục bộ trên shard rồi trộn bảng trung gian (Q2)", 10.1, "normal", IEEE_INK, "middle"))

    parts.append(f'  <line x1="750" y1="438" x2="750" y2="454" stroke="{IEEE_BLUE}" stroke-width="2" marker-end="url(#arrBlue)"/>\n')
    parts.append(f'  <rect x="615" y="456" width="270" height="28" rx="7" fill="{IEEE_BLUE_LIGHT}" stroke="{IEEE_BLUE_BORDER}" stroke-width="1.2"/>\n')
    parts.append(text(750, 474, "Kết quả tổng hợp trả về Client", 11.2, "bold", IEEE_BLUE_DARK, "middle"))

    parts.append("</svg>\n")
    return "".join(parts)


def build_fig2_2():
    """Fig 2.2: Overall MongoDB Sharded Cluster Architecture (for Report 2.2 & Presentation Slides)."""
    w, h = 1000, 480
    parts = [svg_header(w, h)]

    parts.append(text(500, 30, "Kiến trúc Tổng thể Cụm MongoDB Sharded (2 Shard)", 14.5, "bold", IEEE_BLUE_DARK, "middle"))

    # --- LEFT: Client (x=24, y=148, w=194, h=148) ---
    parts.append(card_bg(24, 148, 194, 148, 12, "#FFFFFF"))
    parts.append(card_border(24, 148, 194, 148, 12, IEEE_GRAY_DARK, 1.7))
    parts.append(icon_badge(121, 188, IEEE_GRAY_LIGHT, IEEE_GRAY_DARK, ICON_USERS, 40, 0.92))
    parts.append(text(121, 230, "Ứng dụng khách", 13.5, "bold", IEEE_INK, "middle"))
    parts.append(text(121, 249, "(Client / Sinh tải)", 11.2, "normal", IEEE_GRAY, "middle"))
    parts.append(text(121, 274, "Kết nối duy nhất qua mongos", 10.2, "normal", IEEE_GRAY, "middle"))

    # Arrow Client <-> mongos
    parts.append(f'  <path d="{rounded_path([(218, 222), (258, 222), (258, 134), (296, 134)])}" fill="none" stroke="{IEEE_BLUE}" stroke-width="2.4" marker-end="url(#arrBlue)"/>\n')
    parts.append(text(255, 118, "Đọc / Ghi", 11.0, "bold", IEEE_BLUE_DARK, "middle"))

    # --- CENTER TOP: mongos (x=300, y=72, w=254, h=124) ---
    parts.append(card_bg(300, 72, 254, 124, 12, IEEE_BLUE_LIGHT))
    parts.append(card_border(300, 72, 254, 124, 12, IEEE_BLUE, 2.0))
    parts.append(icon_badge(334, 114, "#FFFFFF", IEEE_BLUE, ICON_NETWORK, 38, 0.88))
    parts.append(text(364, 108, "Query Router", 13.8, "bold", IEEE_BLUE_DARK))
    parts.append(text(364, 128, "(Tiến trình mongos)", 11.2, "bold", IEEE_BLUE))
    parts.append(text(427, 158, "- Định tuyến phi trạng thái (1 hoặc nhiều shard)", 10.2, "normal", IEEE_INK, "middle"))
    parts.append(text(427, 177, "- Tách pipeline & trộn kết quả trả về client", 10.2, "normal", IEEE_INK, "middle"))

    # Bidirectional dashed arrow mongos <-> Config Server
    parts.append(f'  <line x1="427" y1="196" x2="427" y2="274" stroke="{IEEE_TEAL}" stroke-width="2.0" stroke-dasharray="5,3" marker-start="url(#arrTeal)" marker-end="url(#arrTeal)"/>\n')
    parts.append(f'  <rect x="439" y="222" width="132" height="24" rx="6" fill="#FFFFFF" stroke="{IEEE_TEAL_BORDER}" stroke-width="1"/>\n')
    parts.append(text(505, 238, "Đồng bộ metadata", 10.8, "bold", IEEE_TEAL_DARK, "middle"))

    # --- CENTER BOTTOM: Config Server (x=300, y=278, w=254, h=136) ---
    parts.append(card_bg(300, 278, 254, 136, 12, IEEE_TEAL_LIGHT))
    parts.append(card_border(300, 278, 254, 136, 12, IEEE_TEAL, 1.8))
    parts.append(icon_badge(334, 320, "#FFFFFF", IEEE_TEAL, ICON_GEAR, 38, 0.88))
    parts.append(text(364, 314, "Config Server", 13.8, "bold", IEEE_TEAL_DARK))
    parts.append(text(364, 334, "(Replica Set cấu hình)", 11.2, "bold", IEEE_TEAL))
    parts.append(text(427, 366, "- Lưu bản đồ dải khóa & vị trí chunk (metadata)", 10.2, "normal", IEEE_INK, "middle"))
    parts.append(text(427, 385, "- Chạy tiến trình nền Balancer điều phối tải", 10.2, "normal", IEEE_INK, "middle"))

    # Routing arrows mongos -> Shard 1 & Shard 2 (wide 132px gap: x=554..686)
    parts.append(f'  <path d="{rounded_path([(554, 118), (682, 118)])}" fill="none" stroke="{IEEE_BLUE}" stroke-width="2.3" marker-end="url(#arrBlue)"/>\n')
    parts.append(f'  <path d="{rounded_path([(554, 152), (620, 152), (620, 344), (682, 344)])}" fill="none" stroke="{IEEE_BLUE}" stroke-width="2.3" marker-end="url(#arrBlue)"/>\n')
    parts.append(text(620, 92, "Chuyển tiếp", 10.8, "bold", IEEE_BLUE_DARK, "middle"))
    parts.append(text(620, 107, "truy vấn", 10.8, "bold", IEEE_BLUE_DARK, "middle"))

    # --- RIGHT: SHARD 1 & SHARD 2 (x=686..976, w=290) ---
    for sy, title, c_labels, color, light, border in [
        (60, "Shard 1 (Replica Set)", ["Chunk A", "Chunk B", "Chunk ..."], IEEE_GREEN, IEEE_GREEN_LIGHT, IEEE_GREEN_BORDER),
        (278, "Shard 2 (Replica Set)", ["Chunk C", "Chunk D", "Chunk ..."], IEEE_BLUE, IEEE_BLUE_LIGHT, IEEE_BLUE_BORDER),
    ]:
        parts.append(card_bg(686, sy, 290, 146, 12, "#FFFFFF"))
        parts.append(card_border(686, sy, 290, 146, 12, color, 1.9))
        parts.append(icon_badge(720, sy + 36, light, color, ICON_DATABASE, 34, 0.8))
        parts.append(text(746, sy + 33, title, 13.5, "bold", IEEE_INK))
        parts.append(text(746, sy + 51, "WiredTiger Cache + Ổ đĩa riêng", 10.8, "normal", IEEE_GRAY))

        # Chunk pills row
        px = 706
        for cl in c_labels:
            parts.append(f'  <rect x="{px}" y="{sy + 72}" width="78" height="30" rx="6" fill="{light}" stroke="{border}" stroke-width="1.2"/>\n')
            parts.append(text(px + 39, sy + 91, cl, 10.8, "bold", IEEE_INK, "middle"))
            px += 86

        parts.append(text(831, sy + 126, "Dải dữ liệu mục tiêu 32 MB / chunk", 10.5, "italic", IEEE_GRAY, "middle"))

    # Migration arrow between Shard 1 & Shard 2
    parts.append(f'  <line x1="831" y1="208" x2="831" y2="274" stroke="{IEEE_ORANGE}" stroke-width="2.0" stroke-dasharray="5,3" marker-start="url(#arrOrange)" marker-end="url(#arrOrange)"/>\n')
    parts.append(f'  <rect x="694" y="229" width="274" height="24" rx="7" fill="{IEEE_ORANGE_LIGHT}" stroke="{IEEE_ORANGE_BORDER}" stroke-width="1.1"/>\n')
    parts.append(text(831, 245, "Di chuyển chunk (Balancer, lệch > 96 MB)", 10.2, "bold", IEEE_ORANGE_DARK, "middle"))

    parts.append("</svg>\n")
    return "".join(parts)


def compile_svg(name, svg_content):
    svg_path = FIG_DIR / f"{name}.svg"
    png_path = FIG_DIR / f"{name}.png"
    pdf_path = FIG_DIR / f"{name}.pdf"

    svg_path.write_text(svg_content, encoding="utf-8")
    subprocess.run(["rsvg-convert", "-w", "2400", "-o", str(png_path), str(svg_path)], check=True)
    subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(pdf_path), str(svg_path)], check=True)
    print(f"Compiled {name}: SVG, PNG (2400px), PDF")


def main():
    compile_svg("fig1_1_mongodb_architecture", build_fig1_1())
    compile_svg("fig2_1_shard_pruning_vs_scatter", build_fig2_1())
    compile_svg("fig2_2_sharded_cluster_arch", build_fig2_2())


if __name__ == "__main__":
    main()
