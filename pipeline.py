#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erablue Image Pipeline Automation (Gói tự động hóa trọn gói ảnh Erablue Indonesia)
=============================================================================
Quy trình 6 bước chuẩn:
- Bước 1: Quét Google Sheet (tab Description). Lọc row có Cột O (HTML) nhưng Cột P trống.
- Bước 2: Tạo ảnh theo Prompt chi tiết ngành hàng + Thumbnail tham chiếu (Cột H) + Quy chuẩn Bahasa Indonesia + Kích thước 1020x680.
- Bước 3: Đặt tên theo chuẩn: <slug>-<thứ_tự>.jpg.
- Bước 4: Tự động tạo folder con trên Google Drive (Parent: 1wwT7biwT8BDtcOhhf-Nxtt8ddkidWDEN), upload toàn bộ ảnh và dán link vào Cột P.
- Bước 5: Quét kiểm tra Cột Q (tìm giá trị "need to fix") và Cột R (đọc ghi chú cần sửa).
- Bước 6: Sau khi fix ảnh thành công, mở folder Drive của sản phẩm, upload THAY THẾ (replace) đúng ảnh đã fix, giữ nguyên toàn bộ ảnh đạt chuẩn, cập nhật Cột Q thành "Fixed".
"""

import os, io, sys, time, json, base64, urllib.request, csv, re, subprocess, argparse
import requests
from PIL import Image
from bs4 import BeautifulSoup

# ── XÁC ĐỊNH ĐƯỜNG DẪN TỰ ĐỘNG (PORTABLE PATHS) ──────────────────────────────
PACKAGE_DIR     = os.path.dirname(os.path.abspath(__file__))

# File CSV Prompt mẫu (Ưu tiên file trong package, fallback file ngoài)
PROMPT_CSV = os.path.join(PACKAGE_DIR, "Era_Promt_tao_anh.csv")
if not os.path.exists(PROMPT_CSV):
    alt_csv = os.path.join(PACKAGE_DIR, "..", "Ảnh erablue", "Era_Promt tạo ảnh - Prompt Ảnh.csv")
    if os.path.exists(alt_csv):
        PROMPT_CSV = alt_csv

# Thư mục lưu ảnh cục bộ (Ưu tiên 'Ảnh erablue' nếu có sẵn, hoặc tạo 'output_images')
DEFAULT_LOCAL_DIR = os.path.join(PACKAGE_DIR, "..", "Ảnh erablue")
if not os.path.exists(DEFAULT_LOCAL_DIR):
    DEFAULT_LOCAL_DIR = os.path.join(PACKAGE_DIR, "output_images")

# ── LOAD .ENV NẾU CÓ SẴN (KHÔNG CẦN CÀI THÊM THƯ VIỆN) ────────────────────────
env_path = os.path.join(PACKAGE_DIR, ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k and v and k not in os.environ:
                        os.environ[k] = v
    except Exception as e:
        pass

# ── TỰ ĐỘNG CẤU HÌNH GOOGLE OAUTH CLIENT SECRET ──────────────────────────────
GWS_CONFIG_DIR = os.path.expanduser("~/.config/gws")
GWS_SECRET_PATH = os.path.join(GWS_CONFIG_DIR, "client_secret.json")
PKG_SECRET_PATH = os.path.join(PACKAGE_DIR, "client_secret.json")
_DEFAULT_GWS_SECRET_B64 = (
    "eyJpbnN0YWxsZWQiOnsiY2xpZW50X2lkIjoiNDcyNTkxMzEzNjQ4LXFrNWg5YTNoMHViM3VibmRu"
    "YzhqZjBtdGV2dWhpdG9rLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwicHJvamVjdF9pZCI6"
    "Im44bi1tLTQ2NDIwOCIsImF1dGhfdXJpIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28v"
    "b2F1dGgyL2F1dGgiLCJ0b2tlbl91cmkiOiJodHRwczovL29hdXRoMi5nb29nbGVhcGlzLmNvbS90"
    "b2tlbiIsImF1dGfcHJvdmlkZXJfeDUwOV9jZXJ0X3VybCI6Imh0dHBzOi8vd3d3Lmdvb2dsZWFw"
    "aXMuY29tL29hdXRoMi92MS9jZXJ0cyIsImNsaWVudF9zZWNyZXQiOiJHT0NTUFgtTHVGZ3ZMb0ky"
    "TUhLWXZXal9SVDFHR2IyRm42YiIsInJlZGlyZWN0X3VyaXMiOlsiaHR0cDovL2xvY2FsaG9zdCJd"
    "fX0="
)

if not os.path.exists(GWS_SECRET_PATH):
    try:
        os.makedirs(GWS_CONFIG_DIR, exist_ok=True)
        if os.path.exists(PKG_SECRET_PATH):
            import shutil
            shutil.copyfile(PKG_SECRET_PATH, GWS_SECRET_PATH)
        else:
            with open(GWS_SECRET_PATH, "wb") as f:
                f.write(base64.b64decode(_DEFAULT_GWS_SECRET_B64))
        print(f"🔑 Đã tự động cấu hình client_secret.json vào: {GWS_SECRET_PATH}")
    except Exception as e:
        print(f"⚠️ Không thể tự động cấu hình client_secret.json: {e}")

# ── HẰNG SỐ CẤU HÌNH HỆ THỐNG ────────────────────────────────────────────────
_DEFAULT_OR_KEY_B64 = "c2stb3ItdjEtODBjODRmODNiMWE5Y2MzMDg1OTY5YmUwODA2OWYzOGEwYWJjN2EyODQwN2YxOGRlOWU0YTJhZDBmNmI2M2I3NA=="
OPENROUTER_KEY  = os.environ.get("OPENROUTER_KEY") or base64.b64decode(_DEFAULT_OR_KEY_B64).decode("utf-8")
GEN_URL         = "https://openrouter.ai/api/v1/images/generations"
MODEL           = os.environ.get("MODEL", "openai/gpt-image-2.5-sunburst")
QUALITY         = os.environ.get("QUALITY", "medium")
IMG_W           = int(os.environ.get("IMAGE_WIDTH", "1020"))
IMG_H           = int(os.environ.get("IMAGE_HEIGHT", "680"))
MAX_KB          = int(os.environ.get("MAX_FILE_SIZE_KB", "500"))

DRIVE_PARENT_ID = os.environ.get("DRIVE_PARENT_ID", "1wwT7biwT8BDtcOhhf-Nxtt8ddkidWDEN")
SHEET_ID        = os.environ.get("SHEET_ID", "1dp3cY7CAs-OGbc4jCyUC3oNmkNA5LB1AkTINKl_n0BU")
SHEET_URL       = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=296011687"

AUTH_HEADERS    = {"Authorization": f"Bearer {OPENROUTER_KEY}"}

# ── MAPPING MẪU PROMPT NGÀNH HÀNG ─────────────────────────────────────────────
def get_prompt_key(category, name_lower):
    cat = category.lower().strip()
    # 1. Điện máy lạnh & Quạt
    if "ac" in cat or "máy lạnh" in cat:
        return "máy lạnh - làm lạnh nhanh"
    if "air-cooler" in cat or "quạt" in cat or "kipas" in name_lower:
        return "quạt điều hoà - trung cấp"
    # 2. Máy giặt
    if "mesin-cuci" in cat or "máy giặt" in cat:
        if "front loading" in name_lower or "inverter" in name_lower:
            return "máy giặt - cao cấp chăm sóc vải"
        return "máy giặt - phổ thông gia đình"
    # 3. Cây nước & Máy lọc nước
    if "water-dispenser" in cat or "nước" in cat or "dispenser" in name_lower:
        if any(k in name_lower for k in ["toshiba", "electrolux", "uv"]):
            return "cây nước nóng lạnh - cao cấp"
        if any(k in name_lower for k in ["sanken", "midea", "standing"]):
            return "cây nước nóng lạnh - trung cấp"
        return "cây nước nóng lạnh - bình dân"
    # 4. Điện thoại (Smartphone)
    if "handphone" in cat or "smartphone" in cat or "điện thoại" in cat:
        if any(k in name_lower for k in ["find x", "xiaomi 17t pro", "flagship"]):
            return "điện thoại - cao cấp flagship - công nghệ và phong cách sang trọng"
        if any(k in name_lower for k in ["oppo a", "hot 70", "vivo y", "a17", "redmi a"]):
            return "điện thoại - tầm trung - phong cách sống trẻ năng động"
        return "điện thoại - phổ thông - học tập và kết nối hằng ngày"
    # 5. Máy tính bảng (Tablet)
    if "tablet" in cat or "máy tính bảng" in cat or "pad" in name_lower:
        if any(k in name_lower for k in ["ipad", "xiaomi pad"]):
            return "máy tính bảng - sáng tạo nội dung và thiết kế"
        return "máy tính bảng - học tập và giải trí tại nhà"
    # 6. Đồng hồ thông minh (Smartwatch)
    if "smartwatch" in cat or "đồng hồ" in cat or "watch" in name_lower:
        return "đồng hồ thông minh - chăm sóc sức khỏe hằng ngày"
    # 7. Tivi & Tủ lạnh
    if "tivi" in cat or "tv" in cat:
        return "tivi - điện ảnh cao cấp"
    if "tủ lạnh" in cat or "refrigerator" in cat:
        return "tủ lạnh - bình dân"
    return "máy lạnh - làm lạnh nhanh"

# ── LOAD PROMPT TEMPLATES TỪ CSV MASTER ───────────────────────────────────────
def load_prompts(path):
    prompts = {}
    if not os.path.exists(path):
        print(f"⚠️ Cảnh báo: Không tìm thấy file CSV prompt tại: {path}")
        return prompts
    with open(path, encoding="utf-8", errors="ignore") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            cat = row[0].strip().lower()
            prompt = row[1].strip() if len(row) > 1 else ""
            if prompt:
                clean = re.sub(r'=IFERROR\(.*?"(Hãy)', r'Hãy', prompt)
                clean = clean.rstrip('")')
                if not clean.startswith("Hãy"):
                    clean = prompt
                prompts[cat] = clean
    return prompts

def find_prompt(prompts, key):
    key_l = key.lower()
    if key_l in prompts:
        return prompts[key_l]
    for k, v in prompts.items():
        if key_l in k:
            return v
    return list(prompts.values())[0] if prompts else ""

# ── BÓC TÁCH CÁC THẺ H2 TỪ HTML BÀI VIẾT ──────────────────────────────────────
def extract_h2_sections(html):
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup
    sections, current_h2, content = [], None, []
    for el in article.find_all(["h2", "h3", "p", "ul", "ol", "div"]):
        if el.name in ["h2", "h3"]:
            if current_h2:
                sections.append({"h2": current_h2, "content": " ".join(content).strip()})
            current_h2, content = el.get_text(strip=True), []
        elif current_h2:
            t = el.get_text(separator=" ", strip=True)
            if t and t not in content:
                content.append(t)
    if current_h2:
        sections.append({"h2": current_h2, "content": " ".join(content).strip()})
    return sections

# ── TẢI THUMBNAIL THAM CHIẾU TỪ CỘT H ─────────────────────────────────────────
def download_thumbnail(url, cache_dir="/tmp/thumb_cache_erablue"):
    if not url:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    fname = re.sub(r"[^a-z0-9._-]", "_", url.split("/")[-1].lower())
    path = os.path.join(cache_dir, fname)
    png_path = path.rsplit(".", 1)[0] + ".png"
    if os.path.exists(png_path):
        return png_path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=30).read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.save(png_path, "PNG")
        return png_path
    except Exception as e:
        print(f"      ⚠️ Lỗi tải thumbnail ({url}): {e}")
        return None

# ── GHÉP PROMPT HOÀN CHỈNH VỚI RULE BAHASA INDONESIA ──────────────────────────
def build_prompt(template, product_name, category, h2, content, qc_fix_instruction=None):
    feature = f"Section title: {h2}\n\n{content[:700]}"
    result = template
    result = re.sub(r'\[THÔNG TIN H[23] / MÔ TẢ TÍNH NĂNG\].*?(?=\n\n|\Z)', feature, result, flags=re.DOTALL)
    result = re.sub(r'Dán đoạn mô tả tính năng tại đây\.?', '', result)
    result = re.sub(r'\[ẢNH THAM CHIẾU\].*?(?=NHIỆM VỤ:|$)', '', result, flags=re.DOTALL)
    result = re.sub(r'Workflow sẽ gửi kèm.*?\.', '', result, flags=re.DOTALL)
    
    fix_part = ""
    if qc_fix_instruction:
        fix_part = f"""
CRITICAL REVIEWER FEEDBACK — MUST FIX:
{qc_fix_instruction}
Ensure the exact corrected Indonesian words or consistent product design are applied!
"""

    result += f"""

PRODUCT: {product_name}
CATEGORY: {category}
SECTION: {h2}
{fix_part}
MANDATORY RULES — READ CAREFULLY:
1. ALL TEXT in the image MUST be in BAHASA INDONESIA (never Vietnamese, never unnatural machine English).
2. Product image MUST match the reference photo exactly — same body shape, buttons, door/lid orientation, dispenser taps, color, textures.
3. ONLY show specs/features mentioned in the section content above — DO NOT fabricate.
4. Typography: Modern bold geometric sans-serif, ALL CAPS, max 3 tiers (Tech Label, Headline, 1-2 short Benefit Notes).
5. Do NOT overlap words between tiers. Keep text crisp, legible and balanced.
6. This image is a commercial e-commerce banner for Erablue Indonesia."""
    return result.strip()

# ── GỌI API SINH ẢNH GPT-IMAGE-2.5-SUNBURST ──────────────────────────────────
def generate_image(prompt, thumb_path=None, retries=2):
    b64_img = None
    if thumb_path and os.path.exists(thumb_path):
        with open(thumb_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": QUALITY,
        "response_format": "b64_json"
    }
    if b64_img:
        payload["image"] = f"data:image/png;base64,{b64_img}"

    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                GEN_URL,
                headers={**AUTH_HEADERS, "Content-Type": "application/json"},
                json=payload,
                timeout=180
            )
            resp.raise_for_status()
            d = resp.json()
            if "data" in d:
                return base64.b64decode(d["data"][0]["b64_json"]), d.get("usage", {}).get("cost", 0)
            elif "error" in d:
                raise Exception(str(d["error"]))
        except Exception as e:
            if attempt < retries:
                time.sleep(4)
            else:
                raise
    return None, 0

# ── RESIZE CHUẨN 1020x680 JPG < 500KB ─────────────────────────────────────────
def save_resized(img_bytes, out_path):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail((IMG_W, IMG_H), Image.LANCZOS)
    canvas = Image.new("RGB", (IMG_W, IMG_H), (0, 0, 0))
    canvas.paste(img, ((IMG_W - img.width) // 2, (IMG_H - img.height) // 2))
    q = 88
    while q >= 60:
        buf = io.BytesIO()
        canvas.save(buf, "JPEG", quality=q)
        if buf.tell() <= MAX_KB * 1024:
            break
        q -= 5
    with open(out_path, "wb") as f:
        f.write(buf.getvalue())
    return buf.tell() // 1024

# ── CÁC THAO TÁC GOOGLE DRIVE QUA CLI ─────────────────────────────────────────
def get_drive_folder_files(folder_id):
    query = f"'{folder_id}' in parents and trashed = false"
    cmd = [
        "npx", "-y", "@googleworkspace/cli", "drive", "files", "list",
        "--params", json.dumps({"q": query, "pageSize": 100, "fields": "files(id, name, mimeType)"})
    ]
    try:
        res = subprocess.check_output(cmd)
        data = json.loads(res.decode("utf-8"))
        return {f["name"]: f["id"] for f in data.get("files", [])}
    except Exception as e:
        print(f"      ⚠️ Lỗi list files trên Drive ({folder_id}): {e}")
        return {}

def get_or_create_drive_subfolder(parent_id, folder_name):
    query = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    cmd = [
        "npx", "-y", "@googleworkspace/cli", "drive", "files", "list",
        "--params", json.dumps({"q": query, "pageSize": 10, "fields": "files(id, name)"})
    ]
    try:
        res = subprocess.check_output(cmd)
        data = json.loads(res.decode("utf-8"))
        files = data.get("files", [])
        if files:
            return files[0]["id"]
    except Exception as e:
        pass

    cmd_create = [
        "npx", "-y", "@googleworkspace/cli", "drive", "files", "create",
        "--json", json.dumps({
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id]
        })
    ]
    try:
        res = subprocess.check_output(cmd_create)
        data = json.loads(res.decode("utf-8"))
        return data.get("id")
    except Exception as e:
        print(f"      ❌ Lỗi tạo folder Drive {folder_name}: {e}")
        return None

def upload_file_to_drive(folder_id, local_filepath, filename):
    cmd = [
        "npx", "-y", "@googleworkspace/cli", "drive", "files", "create",
        "--json", json.dumps({"name": filename, "parents": [folder_id]}),
        "--upload", filename
    ]
    cwd = os.path.dirname(local_filepath)
    try:
        subprocess.check_output(cmd, cwd=cwd)
        return True
    except Exception as e:
        print(f"         ❌ Lỗi upload mới {filename}: {e}")
        return False

def replace_file_on_drive(file_id, local_filepath, filename):
    cmd = [
        "npx", "-y", "@googleworkspace/cli", "drive", "files", "update",
        "--params", json.dumps({"fileId": file_id}),
        "--upload", filename
    ]
    cwd = os.path.dirname(local_filepath)
    try:
        subprocess.check_output(cmd, cwd=cwd)
        return True
    except Exception as e:
        print(f"         ❌ Lỗi replace {filename} (id={file_id}): {e}")
        return False

# ── CẬP NHẬT GOOGLE SHEET QUA CLI ─────────────────────────────────────────────
def get_sheet_all_rows():
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
    sheet_data = urllib.request.urlopen(req).read().decode("utf-8")
    return list(csv.reader(io.StringIO(sheet_data)))

def update_sheet_cell(row_idx, col_letter, value):
    cell_range = f"Description!{col_letter}{row_idx}"
    cmd = [
        "npx", "-y", "@googleworkspace/cli", "sheets", "spreadsheets", "values", "update",
        "--params", json.dumps({
            "spreadsheetId": SHEET_ID,
            "range": cell_range,
            "valueInputOption": "USER_ENTERED"
        }),
        "--json", json.dumps({
            "values": [[value]]
        })
    ]
    for attempt in range(3):
        try:
            subprocess.check_output(cmd)
            return True
        except Exception:
            time.sleep(2)
    return False

# ── PARSE GHI CHÚ FEEDBACK CỘT R ─────────────────────────────────────────────
def parse_qc_notes(note_text):
    if not note_text or not note_text.strip():
        return {}

    note = note_text.strip()
    result = {}

    # Trường hợp sai ảnh sản phẩm toàn bộ
    if "every design" in note.lower():
        result["ALL"] = "CRITICAL: Every design MUST show the exact product from reference thumbnail. Consistent shape, color and features across all images."

    # Tìm các mục Jpeg cụ thể theo dòng hoặc đoạn
    lines = [l.strip() for l in note.splitlines() if l.strip()]
    for l in lines:
        m = re.search(r'(?:Jpeg|gbr|gbr\.)\s*(?:No\.?\s*)?(\d+)', l, re.IGNORECASE)
        if m:
            num = int(m.group(1))
            instruction = l.replace(m.group(0), '').strip(" -/.,:\"'\t\r\n")
            result[num] = instruction

    # Tìm tiếp các pattern inline dạng Jpeg X ... Jpeg Y
    inline_matches = re.finditer(r'(?:Jpeg|gbr|gbr\.)\s*(?:No\.?\s*)?(\d+)\s*(.*?)(?=(?:Jpeg|gbr|gbr\.)|\Z)', note, re.IGNORECASE | re.DOTALL)
    for im in inline_matches:
        num = int(im.group(1))
        inst = im.group(2).strip(" -/.,:\"'\t\r\n")
        if num not in result or len(inst) > len(result[num]):
            result[num] = inst

    return result

# ── LỆNH 1: STATUS (Xem tổng quan hệ thống) ──────────────────────────────────
def cmd_status():
    print("\n🔍 ĐANG KIỂM TRA TRẠNG THÁI TOÀN BỘ GOOGLE SHEET...")
    rows = get_sheet_all_rows()
    total_rows = len(rows) - 1

    has_html_no_drive = []
    need_to_fix = []
    completed = []

    for idx, r in enumerate(rows[1:], start=2):
        name = r[1].strip() if len(r) > 1 else ""
        html = r[14].strip() if len(r) > 14 else ""
        col_p = r[15].strip() if len(r) > 15 else ""
        col_q = r[16].strip().lower() if len(r) > 16 else ""
        col_r = r[17].strip() if len(r) > 17 else ""

        if html and not col_p:
            has_html_no_drive.append((idx, name))
        elif html and col_p:
            completed.append((idx, name))

        if col_q == "need to fix" or (col_p and col_r and col_q not in ["approve", "fixed"]):
            need_to_fix.append((idx, name, col_r))

    print(f"\n📊 TỔNG KẾT SHEET DESCRIPTION ({total_rows} dòng dữ liệu):")
    print(f"   ✅ Đã có đầy đủ bài viết & ảnh Drive (Cột P): {len(completed)} sản phẩm")
    print(f"   ⏳ [BƯỚC 1] Cần tạo ảnh (Cột O có HTML, Cột P trống): {len(has_html_no_drive)} sản phẩm")
    print(f"   ⚠️ [BƯỚC 5] Cần sửa ảnh (Cột Q='need to fix' hoặc có note Cột R): {len(need_to_fix)} sản phẩm")

    if has_html_no_drive:
        print("\n📋 DANH SÁCH CHỜ TẠO ẢNH (BƯỚC 1 - 4):")
        for row_num, name in has_html_no_drive[:15]:
            print(f"   - Row {row_num:02d}: {name}")
        if len(has_html_no_drive) > 15:
            print(f"   ... và {len(has_html_no_drive) - 15} sản phẩm khác.")

    if need_to_fix:
        print("\n🛠️ DANH SÁCH CHỜ SỬA ẢNH (BƯỚC 5 - 6):")
        for row_num, name, note in need_to_fix[:15]:
            print(f"   - Row {row_num:02d}: {name} -> {note[:60].replace(chr(10), ' ')}")
        if len(need_to_fix) > 15:
            print(f"   ... và {len(need_to_fix) - 15} sản phẩm khác.")

# ── LỆNH 2: CREATE (Bước 1 -> Bước 4) ─────────────────────────────────────────
def cmd_create(limit=None, base_dir=None):
    local_base = base_dir or DEFAULT_LOCAL_DIR
    print("\n🚀 BẮT ĐẦU BƯỚC 1 - 4: TẠO ẢNH, UPLOAD DRIVE & CẬP NHẬT SHEET")
    print("=" * 75)
    print(f"📂 Thư mục lưu ảnh cục bộ: {local_base}")

    prompts = load_prompts(PROMPT_CSV)
    rows = get_sheet_all_rows()

    pending = []
    for idx, r in enumerate(rows[1:], start=2):
        name = r[1].strip() if len(r) > 1 else ""
        url_prod = r[2].strip() if len(r) > 2 else ""
        slug = url_prod.rstrip("/").split("/")[-1] if url_prod else re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        cat = r[0].strip().lower()
        thumb = r[7].strip() if len(r) > 7 else ""
        html = r[14].strip() if len(r) > 14 else ""
        col_p = r[15].strip() if len(r) > 15 else ""

        if html and not col_p:
            pending.append({
                "row": idx,
                "name": name,
                "slug": slug,
                "category": cat,
                "thumbnail": thumb,
                "html": html
            })

    if not pending:
        print("✅ Tuyệt vời! Không có dòng nào ở Cột O có bài viết mà Cột P bị trống.")
        return

    print(f"Tìm thấy {len(pending)} sản phẩm cần tạo ảnh.")
    if limit:
        pending = pending[:limit]
        print(f"Giới hạn xử lý: {len(pending)} sản phẩm.")

    for pi, prod in enumerate(pending, 1):
        row_num   = prod["row"]
        name      = prod["name"]
        slug      = prod["slug"]
        cat       = prod["category"]
        thumb_url = prod["thumbnail"]
        html      = prod["html"]

        print(f"\n{'═'*75}")
        print(f"📦 [{pi:02d}/{len(pending)}] (Row {row_num}) {name}")
        print(f"   Slug: {slug} | Ngành hàng: {cat}")

        local_dir = os.path.join(local_base, slug)
        os.makedirs(local_dir, exist_ok=True)

        thumb_path = download_thumbnail(thumb_url) if thumb_url else None
        sections = extract_h2_sections(html)
        print(f"   Số lượng H2: {len(sections)} ảnh.")

        prompt_key = get_prompt_key(cat, name.lower())
        template = find_prompt(prompts, prompt_key)

        for si, sec in enumerate(sections, 1):
            h2 = sec["h2"]
            content = sec["content"]
            fname = f"{slug}-{si}.jpg"
            out_path = os.path.join(local_dir, fname)

            if os.path.exists(out_path):
                print(f"   ⏭️  [{si}/{len(sections)}] Bỏ qua (Đã có): {fname}")
                continue

            print(f"   🎨 [{si}/{len(sections)}] H2: {h2[:50]}...")
            full_prompt = build_prompt(template, name, cat, h2, content)
            try:
                img_bytes, cost = generate_image(full_prompt, thumb_path)
                save_resized(img_bytes, out_path)
                print(f"      ✅ Đã lưu {fname} | ${cost:.4f}")
            except Exception as e:
                print(f"      ❌ Lỗi tạo {fname}: {e}")
            time.sleep(2)

        # Upload Drive
        print(f"   ☁️ Đồng bộ lên Google Drive...")
        folder_id = get_or_create_drive_subfolder(DRIVE_PARENT_ID, slug)
        if folder_id:
            drive_url = f"https://drive.google.com/drive/folders/{folder_id}"
            existing_drive_files = get_drive_folder_files(folder_id)
            local_files = sorted([f for f in os.listdir(local_dir) if f.endswith(".jpg")])

            for fname in local_files:
                fpath = os.path.join(local_dir, fname)
                if fname not in existing_drive_files:
                    upload_file_to_drive(folder_id, fpath, fname)
                    print(f"      ➕ Uploaded: {fname}")

            update_sheet_cell(row_num, "P", drive_url)
            print(f"      📝 Đã cập nhật Sheet Description!P{row_num} -> {drive_url}")

# ── LỆNH 3: CHECK-QC (Bước 5: Kiểm tra feedback) ──────────────────────────────
def cmd_check_qc():
    print("\n🔍 ĐANG QUÉT FEEDBACK CỘT Q & CỘT R...")
    rows = get_sheet_all_rows()
    qc_items = []

    for idx, r in enumerate(rows[1:], start=2):
        name = r[1].strip() if len(r) > 1 else ""
        col_p = r[15].strip() if len(r) > 15 else ""
        col_q = r[16].strip().lower() if len(r) > 16 else ""
        col_r = r[17].strip() if len(r) > 17 else ""

        if col_q == "need to fix" or (col_p and col_r and col_q not in ["approve", "fixed"]):
            notes = parse_qc_notes(col_r)
            qc_items.append({
                "row": idx,
                "name": name,
                "drive_url": col_p,
                "raw_note": col_r,
                "parsed_notes": notes
            })

    print(f"\n📋 TÌM THẤY {len(qc_items)} SẢN PHẨM CẦN FIX THEO FEEDBACK:")
    for item in qc_items:
        print(f"\n👉 Row {item['row']:02d}: {item['name']}")
        print(f"   Drive: {item['drive_url']}")
        print(f"   Ghi chú gốc: {item['raw_note'].replace(chr(10), ' ')}")
        if item["parsed_notes"]:
            print(f"   Ảnh cần sửa: {list(item['parsed_notes'].keys())}")
            for k, v in item["parsed_notes"].items():
                print(f"     • Jpeg {k}: {v}")

# ── LỆNH 4: FIX-QC (Bước 5 & 6: Sửa ảnh và Upload thay thế Drive) ──────────────
def cmd_fix_qc(target_row=None, base_dir=None):
    local_base = base_dir or DEFAULT_LOCAL_DIR
    print("\n🛠️ BẮT ĐẦU BƯỚC 5 & 6: FIX ẢNH VÀ UPLOAD THAY THẾ (REPLACE) VÀO DRIVE")
    print("=" * 75)
    print(f"📂 Thư mục lưu ảnh cục bộ: {local_base}")

    prompts = load_prompts(PROMPT_CSV)
    rows = get_sheet_all_rows()

    qc_items = []
    for idx, r in enumerate(rows[1:], start=2):
        if target_row and idx != target_row:
            continue
        name = r[1].strip() if len(r) > 1 else ""
        url_prod = r[2].strip() if len(r) > 2 else ""
        slug = url_prod.rstrip("/").split("/")[-1] if url_prod else re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        cat = r[0].strip().lower()
        thumb = r[7].strip() if len(r) > 7 else ""
        html = r[14].strip() if len(r) > 14 else ""
        col_p = r[15].strip() if len(r) > 15 else ""
        col_q = r[16].strip().lower() if len(r) > 16 else ""
        col_r = r[17].strip() if len(r) > 17 else ""

        if col_q == "need to fix" or (col_p and col_r and col_q not in ["approve", "fixed"]):
            notes = parse_qc_notes(col_r)
            m = re.search(r'folders/([a-zA-Z0-9_-]+)', col_p)
            folder_id = m.group(1) if m else None

            qc_items.append({
                "row": idx,
                "name": name,
                "slug": slug,
                "category": cat,
                "thumbnail": thumb,
                "html": html,
                "drive_url": col_p,
                "folder_id": folder_id,
                "raw_note": col_r,
                "parsed_notes": notes
            })

    if not qc_items:
        print("✅ Không có sản phẩm nào cần fix.")
        return

    print(f"Sẽ tiến hành fix cho {len(qc_items)} sản phẩm.")

    for pi, item in enumerate(qc_items, 1):
        row_num   = item["row"]
        name      = item["name"]
        slug      = item["slug"]
        cat       = item["category"]
        thumb_url = item["thumbnail"]
        html      = item["html"]
        folder_id = item["folder_id"]
        parsed    = item["parsed_notes"]

        print(f"\n{'═'*75}")
        print(f"📦 [{pi:02d}/{len(qc_items)}] FIX SẢN PHẨM: Row {row_num} — {name}")
        print(f"   Drive Folder ID: {folder_id}")
        print(f"   Ghi chú: {item['raw_note'].replace(chr(10), ' ')[:75]}...")

        local_dir = os.path.join(local_base, slug)
        os.makedirs(local_dir, exist_ok=True)
        thumb_path = download_thumbnail(thumb_url) if thumb_url else None

        sections = extract_h2_sections(html)
        prompt_key = get_prompt_key(cat, name.lower())
        template = find_prompt(prompts, prompt_key)

        # Lấy danh sách file hiện có trên Google Drive
        drive_files = get_drive_folder_files(folder_id) if folder_id else {}

        # Xác định danh sách số index cần tạo lại
        indices_to_fix = set()
        if "ALL" in parsed:
            indices_to_fix = set(range(1, len(sections) + 1))
        else:
            for k in parsed.keys():
                if isinstance(k, int) and 1 <= k <= len(sections):
                    indices_to_fix.add(k)

        if not indices_to_fix:
            print("   ⚠️ Không nhận diện được index ảnh cụ thể, kiểm tra các index xuất hiện trong ghi chú...")
            num_finds = re.findall(r'(\d+)', item['raw_note'])
            for nf in num_finds:
                if 1 <= int(nf) <= len(sections):
                    indices_to_fix.add(int(nf))

        print(f"   Các ảnh sẽ được tạo lại & thay thế: {sorted(list(indices_to_fix))}")

        fixed_count = 0
        for si in sorted(list(indices_to_fix)):
            sec = sections[si - 1]
            h2 = sec["h2"]
            content = sec["content"]
            fname = f"{slug}-{si}.jpg"
            out_path = os.path.join(local_dir, fname)

            fix_instruction = parsed.get(si) or parsed.get("ALL") or item["raw_note"]
            print(f"\n   🎨 Sửa ảnh [{si}/{len(sections)}] {fname}...")
            print(f"      Chỉ dẫn: {fix_instruction[:60]}...")

            full_prompt = build_prompt(template, name, cat, h2, content, qc_fix_instruction=fix_instruction)

            try:
                img_bytes, cost = generate_image(full_prompt, thumb_path)
                save_resized(img_bytes, out_path)
                print(f"      ✅ Đã tạo ảnh mới: {fname}")

                # [BƯỚC 6] Thay thế (replace) ảnh trên Google Drive
                if folder_id:
                    if fname in drive_files:
                        fid = drive_files[fname]
                        replace_file_on_drive(fid, out_path, fname)
                        print(f"      🔄 Đã REPLACE ảnh cũ trên Drive (fileId: {fid})")
                    else:
                        upload_file_to_drive(folder_id, out_path, fname)
                        print(f"      ➕ Đã upload vào Drive: {fname}")
                fixed_count += 1
            except Exception as e:
                print(f"      ❌ Lỗi fix {fname}: {e}")

            time.sleep(2)

        # Cập nhật Cột Q thành 'Fixed'
        if fixed_count > 0:
            update_sheet_cell(row_num, "Q", "Fixed")
            print(f"   📝 Đã cập nhật Sheet Description!Q{row_num} -> 'Fixed'")

    print("\n" + "=" * 75)
    print("🏁 HOÀN TẤT BƯỚC 5 & 6 (FIX QC & REPLACE GOOGLE DRIVE)")
    print("=" * 75)

# ── MAIN ENTRY POINT ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Erablue Image Pipeline Automation")
    parser.add_argument("--output-dir", type=str, default=None, help="Đường dẫn thư mục lưu ảnh cục bộ")
    subparsers = parser.add_subparsers(dest="command", help="Lệnh thực thi")

    # Command: status
    subparsers.add_parser("status", help="Xem tổng quan tiến độ Google Sheet")

    # Command: create
    parser_create = subparsers.add_parser("create", help="Chạy Bước 1 - 4: Tạo ảnh cho các dòng trống Cột P")
    parser_create.add_argument("--limit", type=int, default=None, help="Giới hạn số sản phẩm cần tạo")

    # Command: check-qc
    subparsers.add_parser("check-qc", help="Kiểm tra Cột Q/R tìm feedback cần sửa")

    # Command: fix-qc
    parser_fix = subparsers.add_parser("fix-qc", help="Chạy Bước 5 & 6: Sửa ảnh theo Cột R và Replace Drive")
    parser_fix.add_argument("--row", type=int, default=None, help="Chỉ sửa một dòng cụ thể")

    # Command: upload-pim
    parser_pim = subparsers.add_parser("upload-pim", help="Upload HTML bài viết và ảnh tương ứng từng Heading lên PIM")
    parser_pim.add_argument("--row", type=int, default=None, help="Số dòng trên Sheet")
    parser_pim.add_argument("--rows", type=str, default=None, help="Khoảng dòng trên Sheet (ví dụ 26-51)")
    parser_pim.add_argument("--cdp", type=str, default="http://localhost:9222", help="Chrome CDP URL")

    # Command: run (Tất cả)
    subparsers.add_parser("run", help="Chạy toàn bộ quy trình")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "create":
        cmd_create(limit=args.limit, base_dir=args.output_dir)
    elif args.command == "check-qc":
        cmd_check_qc()
    elif args.command == "fix-qc":
        cmd_fix_qc(target_row=args.row, base_dir=args.output_dir)
    elif args.command == "upload-pim":
        try:
            import upload_pim
            import asyncio
            args.img_dir = args.output_dir
            asyncio.run(upload_pim.main_async(args))
        except ImportError:
            import subprocess
            cmd = [sys.executable, os.path.join(PACKAGE_DIR, "upload_pim.py")]
            if args.row: cmd.extend(["--row", str(args.row)])
            if args.rows: cmd.extend(["--rows", args.rows])
            if args.output_dir: cmd.extend(["--img-dir", args.output_dir])
            if args.cdp: cmd.extend(["--cdp", args.cdp])
            subprocess.run(cmd)
    elif args.command == "run":
        cmd_create(base_dir=args.output_dir)
        cmd_check_qc()
    else:
        parser.print_help()
