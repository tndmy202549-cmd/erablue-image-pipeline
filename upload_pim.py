#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erablue PIM Uploader (Đóng gói quy trình Upload HTML bài viết và Ảnh theo từng Heading lên PIM)
=============================================================================================
Tính năng cốt lõi:
1. Đọc dữ liệu sản phẩm từ Google Sheet (tab Description) hoặc tham số dòng lệnh:
   - Tên sản phẩm, Slug, HTML bài viết chứa các thẻ <h2>/<h3>.
2. Quét thư mục ảnh cục bộ theo chuẩn: `<slug>-<thứ_tự>.jpg`.
3. Kết nối Chrome đang đăng nhập PIM qua giao thức Chrome DevTools Protocol (CDP: localhost:9222).
4. Tìm kiếm Model sản phẩm trên hệ thống PIM (mwgroup.vn) với cơ chế tìm kiếm thông minh và fallback.
5. Tự động nhận diện cấu trúc sản phẩm:
   - Tab Biến thể (Smartphones, Tablets, Smartwatches có biến thể màu): Mở từng biến thể để cập nhật.
   - Tab Chung (Điện máy, Máy lạnh, Máy giặt, Cây nước... không chia màu).
6. Upload toàn bộ ảnh lên CDN của PIM qua CKEditor FileRepository adapter, lấy URL CDN vĩnh viễn.
7. Biên dịch mã HTML bài viết: chèn đúng ảnh CDN vào bên dưới thẻ <h2> tương ứng (với alt, width 1020, height 680).
8. Dán mã HTML hoàn chỉnh vào CKEditor (chế độ Source mode).
9. Upload toàn bộ danh sách ảnh vào mục "Hình gallery" của sản phẩm/biến thể.
10. Lưu biến thể và bấm "Lưu" toàn bộ Model thành công.
"""

import os, sys, time, json, base64, urllib.request, csv, re, asyncio, argparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ── XÁC ĐỊNH ĐƯỜNG DẪN TỰ ĐỘNG ───────────────────────────────────────────────
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# Đọc file .env nếu có
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
    except Exception:
        pass

# Thư mục lưu ảnh cục bộ mặc định
DEFAULT_IMG_DIR = os.path.join(PACKAGE_DIR, "..", "Ảnh erablue")
if not os.path.exists(DEFAULT_IMG_DIR):
    DEFAULT_IMG_DIR = os.path.join(PACKAGE_DIR, "output_images")

# Cấu hình PIM & Google Sheet
SHEET_ID        = os.environ.get("SHEET_ID", "1dp3cY7CAs-OGbc4jCyUC3oNmkNA5LB1AkTINKl_n0BU")
SHEET_URL       = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=296011687"
PIM_LIST_URL    = os.environ.get("PIM_LIST_URL", "https://pim.mwgroup.vn/product-model-v2/a697bb55-8b0c-4d79-ba13-57d37d5ea060")
CHROME_CDP_URL  = os.environ.get("CHROME_CDP_URL", "http://localhost:9222")

IMG_WIDTH       = int(os.environ.get("IMAGE_WIDTH", "1020"))
IMG_HEIGHT      = int(os.environ.get("IMAGE_HEIGHT", "680"))

# ── HÀM UPLOAD ẢNH LÊN CDN PIM QUA CKEDITOR ──────────────────────────────────
async def upload_image_to_pim_cdn(page, filepath, filename, is_variant=True):
    with open(filepath, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')

    upload_js = """
    async (args) => {
        const { b64, filename, is_variant } = args;
        const selector = is_variant 
            ? '.ant-modal .form-editor, .panel-collapse.show .form-editor' 
            : '.panel-collapse .form-editor';
        const editorEls = document.querySelectorAll(selector);
        if (!editorEls || editorEls.length === 0) throw new Error("Không tìm thấy editor element");
        
        const editorEl = editorEls[0];
        const editable = editorEl.querySelector('.ck-editor__editable');
        if (!editable || !editable.ckeditorInstance) throw new Error("Không tìm thấy CKEditor instance");
        const editor = editable.ckeditorInstance;
        const fileRepo = editor.plugins.get('FileRepository');
        
        const byteCharacters = atob(b64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'image/jpeg' });
        const file = new File([blob], filename, { type: 'image/jpeg' });
        
        const dummyLoader = { file: Promise.resolve(file) };
        const adapter = fileRepo.createUploadAdapter(dummyLoader);
        const res = await adapter.upload();
        return res.default;
    }
    """
    return await page.evaluate(upload_js, {'b64': b64, 'filename': filename, 'is_variant': is_variant})

# ── HÀM BIÊN DỊCH HTML: CHÈN ẢNH TƯƠNG ỨNG SAU TỪNG HEADING H2/H3 ──────────────
def compile_article_html(article_html, cdn_urls):
    soup = BeautifulSoup(article_html, 'html.parser')
    heading_tags = soup.find_all('h2')
    if not heading_tags:
        heading_tags = soup.find_all('h3')

    for idx, heading in enumerate(heading_tags):
        num = idx + 1
        if num in cdn_urls:
            img_url = cdn_urls[num]
            alt_text = heading.get_text().strip()
            figure = soup.new_tag('figure', **{'class': 'image'})
            img = soup.new_tag('img', **{
                'src': img_url,
                'alt': alt_text,
                'width': str(IMG_WIDTH),
                'height': str(IMG_HEIGHT),
                'loading': 'lazy',
                'style': f'aspect-ratio:{IMG_WIDTH}/{IMG_HEIGHT};'
            })
            figure.append(img)
            heading.insert_after(figure)

    return str(soup)

# ── LẤY DANH SÁCH ẢNH CỤC BỘ ĐƯỢC SẮP XẾP THEO THỨ TỰ ────────────────────────
def get_sorted_images(folder):
    if not os.path.exists(folder):
        return []
    files = [f for f in os.listdir(folder) if f.endswith('.jpg') and not f.startswith('.')]
    def extract_num(f):
        m = re.search(r'(\d+)\.jpg$', f)
        return int(m.group(1)) if m else 999
    return sorted(files, key=extract_num)

# ── TÌM VÀ ĐIỀU HƯỚNG TỚI SẢN PHẨM TRÊN PIM ──────────────────────────────────
async def navigate_to_product(page, product_name, direct_url=None):
    if direct_url:
        print(f"  🔗 Mở trực tiếp Model qua URL: {direct_url}")
        await page.goto(direct_url, timeout=45000)
        await page.wait_for_timeout(3000)
        return True

    # Nếu không có URL trực tiếp, tiến hành tìm kiếm trên PIM
    print(f"  🔍 Đang tìm kiếm Model trên PIM: '{product_name}'...")
    await page.goto(PIM_LIST_URL, timeout=45000)
    await page.wait_for_timeout(2500)

    # Đóng modal cũ nếu còn tồn tại
    try:
        cancel_btn = page.locator('.ant-modal-footer button:has-text("Hủy bỏ")').first
        if await cancel_btn.count() > 0:
            await cancel_btn.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass

    search_input = page.locator('input[placeholder*="nhập tên hoặc mã"]').first
    await search_input.fill(product_name)
    await page.keyboard.press('Enter')
    await page.wait_for_timeout(2500)

    link = page.locator(f'table tbody tr a:has-text("{product_name}")').first
    if await link.count() == 0:
        # Fallback 1: Bỏ các tiền tố ngành hàng
        clean_name = re.sub(r'^(?:Smartphone|AC Split|Air Cooler|Mesin Cuci(?: Top Loading| Front Loading)?|Standing Water Dispenser|Portable Water Dispenser|Water Dispenser|Smart TV|Tivi|Kulkas)\s+', '', product_name, flags=re.IGNORECASE).strip()
        print(f"  Thử tìm với tên rút gọn: '{clean_name}'")
        await search_input.fill(clean_name)
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(2500)
        link = page.locator(f'table tbody tr a:has-text("{clean_name}")').first

    if await link.count() == 0:
        # Fallback 2: Thử lấy link đầu tiên trong bảng nếu có
        total_rows = await page.locator('table tbody tr a').count()
        if total_rows > 0:
            link = page.locator('table tbody tr a').first
            print(f"  ⚠️ Khớp với kết quả đầu tiên trong bảng.")

    if await link.count() == 0:
        print(f"  ❌ Không tìm thấy Model trên PIM cho sản phẩm: {product_name}")
        return False

    link_text = await link.inner_text()
    print(f"  ✅ Tìm thấy Model: '{link_text}' -> Đang mở chi tiết...")
    await link.click()
    await page.wait_for_timeout(3500)
    return True

# ── XỬ LÝ UPLOAD CHO TỪNG SẢN PHẨM ───────────────────────────────────────────
async def process_product(page, p_info):
    name         = p_info['name']
    slug         = p_info['slug']
    folder       = p_info['folder']
    article_html = p_info['article']
    direct_url   = p_info.get('pim_url')
    idx          = p_info.get('index', 1)

    print(f"\n{'='*75}")
    print(f"📦 [{idx:02d}] BẮT ĐẦU ĐĂNG BÀI & GALLERY LÊN PIM: {name}")
    print(f"   Slug: {slug} | Thư mục ảnh: {folder}")
    print(f"{'='*75}")

    img_files = get_sorted_images(folder)
    if not img_files:
        print(f"  ❌ LỖI: Không tìm thấy ảnh JPG nào trong thư mục: {folder}")
        return False, "Không có ảnh JPG"

    print(f"  📸 Tìm thấy {len(img_files)} ảnh JPG sẵn sàng upload.")

    # 1. Điều hướng tới Model
    ok = await navigate_to_product(page, name, direct_url)
    if not ok:
        return False, "Không tìm thấy trên PIM"

    # 2. Kiểm tra xem sản phẩm có Tab Biến thể (Color) hay Tab Chung
    variant_tab = page.locator('div[role="tab"]:has-text("Biến thể"), [id*="tab-pim.product.title.variant"]').first
    has_variant = await variant_tab.count() > 0

    if has_variant:
        print("  🔹 Phát hiện cấu trúc: TAB BIẾN THỂ (Sản phẩm có chia màu sắc)")
        await variant_tab.click()
        await page.wait_for_timeout(2000)

        color_locators = page.locator('text=Color:')
        total_colors = await color_locators.count()
        print(f"  Tìm thấy {total_colors} biến thể màu.")

        if total_colors == 0:
            print("  ⚠️ Không tìm thấy dòng biến thể màu nào!")
            return False, "Không có biến thể màu"

        # Mở biến thể đầu tiên để upload toàn bộ ảnh lên CDN lấy URL
        print(f"  Mở biến thể đầu tiên để nạp {len(img_files)} ảnh lên CDN PIM...")
        await color_locators.first.click()
        await page.wait_for_timeout(2500)

        modal = page.locator('.ant-modal')
        if await modal.count() == 0:
            print("  ❌ Không mở được modal biến thể!")
            return False, "Không mở được modal"

        cdn_urls = {}
        for filename in img_files:
            m = re.search(r'(\d+)\.jpg$', filename)
            if not m:
                continue
            num = int(m.group(1))
            filepath = os.path.join(folder, filename)
            try:
                url = await upload_image_to_pim_cdn(page, filepath, filename, is_variant=True)
                cdn_urls[num] = url
                print(f"    ✅ CDN URL [H2-{num}]: {url}")
            except Exception as e:
                print(f"    ⚠️ Lỗi upload CDN {filename}: {e}")

        # Biên dịch HTML bài viết hoàn chỉnh với hình ảnh CDN tương ứng từng Heading
        compiled_html = compile_article_html(article_html, cdn_urls)
        full_gallery_paths = [os.path.join(folder, f) for f in img_files]

        # Lặp qua từng biến thể màu để điền bài viết và Gallery
        for c_idx in range(total_colors):
            color_row = page.locator('text=Color:').nth(c_idx)
            color_name = await color_row.inner_text()
            print(f"  -> Cập nhật biến thể {c_idx+1}/{total_colors}: '{color_name}'")

            if c_idx > 0:
                await color_row.click()
                await page.wait_for_timeout(2500)

            modal = page.locator('.ant-modal')
            editor = modal.locator('.form-editor').first

            # Dán HTML vào CKEditor qua Source mode
            source_btn = editor.locator('button:has-text("Source"), button[aria-label*="Source"]').first
            is_on = await source_btn.evaluate('btn => btn.classList.contains("ck-on")')
            if not is_on:
                await source_btn.click()
                await page.wait_for_timeout(500)

            textarea = editor.locator('textarea')
            await textarea.fill(compiled_html)
            await page.wait_for_timeout(500)

            await source_btn.click()
            await page.wait_for_timeout(1000)

            # Mở panel Thông tin hình ảnh theo biến thể và upload Gallery
            h5_img = modal.locator('h5:has-text("Thông tin hình ảnh theo biến thể")').first
            panel_gallery = modal.locator('.panel-collapse').filter(has=page.locator('text=Hình gallery'))
            is_open = await panel_gallery.evaluate('p => p.classList.contains("show")') if await panel_gallery.count() > 0 else False
            if not is_open:
                await h5_img.click()
                await page.wait_for_timeout(1000)

            gallery_input = panel_gallery.locator('input[type="file"]').nth(2)
            await gallery_input.set_input_files(full_gallery_paths)
            print(f"     Đã up {len(full_gallery_paths)} ảnh vào Gallery. Chờ 8s...")
            await page.wait_for_timeout(8000)

            # Bấm 'Đồng ý' trong modal
            dong_y_btn = modal.locator('.ant-modal-footer button.ant-btn-primary:has-text("Đồng ý")').first
            await dong_y_btn.click()
            await page.wait_for_timeout(2500)
            print(f"     ✅ Đã lưu biến thể '{color_name}'!")

        # Lưu toàn bộ Model
        print("  Đang lưu Model tổng thể...")
        save_btn = page.locator('button:has-text("Lưu"), .btn-success:has-text("Lưu")').first
        await save_btn.click()
        await page.wait_for_timeout(4000)
        print(f"  🎉 [SUCCESS] Đã lưu thành công Model: {name}")
        return True, "Success"

    else:
        print("  🔹 Phát hiện cấu trúc: TAB CHUNG (Điện máy / Gia dụng không chia màu)")
        editor = page.locator('.panel-collapse').filter(has=page.locator('text=Bài viết sản phẩm')).locator('.form-editor').first
        if await editor.count() == 0:
            print("  ❌ LỖI: Không tìm thấy ô Bài viết sản phẩm ở Tab Chung!")
            return False, "Không thấy editor"

        print(f"  Tải {len(img_files)} ảnh lên CDN PIM qua CKEditor...")
        cdn_urls = {}
        for filename in img_files:
            m = re.search(r'(\d+)\.jpg$', filename)
            if not m:
                continue
            num = int(m.group(1))
            filepath = os.path.join(folder, filename)
            try:
                url = await upload_image_to_pim_cdn(page, filepath, filename, is_variant=False)
                cdn_urls[num] = url
                print(f"    ✅ CDN URL [H2-{num}]: {url}")
            except Exception as e:
                print(f"    ⚠️ Lỗi upload CDN {filename}: {e}")

        compiled_html = compile_article_html(article_html, cdn_urls)

        # Dán vào CKEditor qua chế độ Source
        source_btn = editor.locator('button:has-text("Source"), button[aria-label*="Source"]').first
        is_on = await source_btn.evaluate('btn => btn.classList.contains("ck-on")')
        if not is_on:
            await source_btn.click()
            await page.wait_for_timeout(500)

        textarea = editor.locator('textarea')
        await textarea.fill(compiled_html)
        await page.wait_for_timeout(500)

        await source_btn.click()
        await page.wait_for_timeout(1000)
        print("  Đã dán bài viết vào CKEditor thành công.")

        # Upload vào Hình gallery
        h5_img = page.locator('h5:has-text("Thông tin hình ảnh theo biến thể")').first
        panel_gallery = page.locator('.panel-collapse').filter(has=page.locator('text=Hình gallery'))
        is_open = await panel_gallery.evaluate('p => p.classList.contains("show")') if await panel_gallery.count() > 0 else False
        if not is_open:
            await h5_img.click()
            await page.wait_for_timeout(1000)

        gallery_input = panel_gallery.locator('input[type="file"]').nth(2)
        full_paths = [os.path.join(folder, f) for f in img_files]
        await gallery_input.set_input_files(full_paths)
        print(f"  Đã up {len(full_paths)} ảnh vào mục Hình Gallery. Đang chờ 8s...")
        await page.wait_for_timeout(8000)

        # Bấm 'Lưu' toàn bộ Model
        print("  Đang lưu Model...")
        save_btn = page.locator('button:has-text("Lưu"), .btn-success:has-text("Lưu")').first
        await save_btn.click()
        await page.wait_for_timeout(4000)
        print(f"  🎉 [SUCCESS] Đã lưu thành công Model: {name}")
        return True, "Success"

# ── TẢI DỮ LIỆU SẢN PHẨM TỪ GOOGLE SHEET ─────────────────────────────────────
def fetch_products_from_sheet(target_rows=None, base_dir=None):
    img_dir = base_dir or DEFAULT_IMG_DIR
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
    content = urllib.request.urlopen(req).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(content)))

    products = []
    for idx, r in enumerate(rows[1:], start=2):
        if target_rows and idx not in target_rows:
            continue

        name = r[1].strip() if len(r) > 1 else ""
        url_prod = r[2].strip() if len(r) > 2 else ""
        slug = url_prod.rstrip("/").split("/")[-1] if url_prod else re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        html = r[14].strip() if len(r) > 14 else ""
        folder = os.path.join(img_dir, slug)

        if html:
            products.append({
                "row": idx,
                "index": idx,
                "name": name,
                "slug": slug,
                "url": url_prod,
                "article": html,
                "folder": folder
            })

    return products

# ── MAIN RUNNER ──────────────────────────────────────────────────────────────
async def main_async(args):
    target_rows = set()
    if args.row:
        target_rows.add(args.row)
    elif args.rows:
        parts = args.rows.split("-")
        if len(parts) == 2:
            target_rows = set(range(int(parts[0]), int(parts[1]) + 1))
        else:
            target_rows = {int(p.strip()) for p in args.rows.split(",") if p.strip().isdigit()}

    products = fetch_products_from_sheet(target_rows if target_rows else None, base_dir=args.img_dir)
    if not products:
        print("❌ Không tìm thấy sản phẩm nào có bài viết HTML để upload.")
        return

    print(f"Tìm thấy {len(products)} sản phẩm cần upload lên PIM.")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(args.cdp)
        except Exception as e:
            print("\n" + "!" * 70)
            print(f"❌ KHÔNG THỂ KẾT NỐI CHROME QUA CDP ({args.cdp})!")
            print("Vui lòng khởi động Chrome với cổng remote debugging:")
            print("/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
            print("!" * 70 + "\n")
            return

        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        # Kiểm tra đăng nhập
        await page.goto(PIM_LIST_URL, timeout=45000)
        await page.wait_for_timeout(3000)
        if 'authkey.tgdd.vn' in page.url or 'login' in page.url.lower():
            print("\n" + "!" * 70)
            print("⚠️ CHƯA ĐĂNG NHẬP VÀO PIM (mwgroup.vn)!")
            print("Vui lòng đăng nhập trên cửa sổ Chrome đang mở trên màn hình.")
            print("!" * 70 + "\n")
            return

        success_count = 0
        for p_info in products:
            try:
                ok, msg = await process_product(page, p_info)
                if ok:
                    success_count += 1
            except Exception as e:
                print(f"  ❌ Ngoại lệ khi xử lý {p_info['name']}: {e}")

        print("\n" + "=" * 75)
        print(f"🏁 TỔNG KẾT: {success_count}/{len(products)} sản phẩm đã đăng bài & gallery thành công lên PIM!")
        print("=" * 75)

def main():
    parser = argparse.ArgumentParser(description="Upload HTML bài viết và ảnh tương ứng lên PIM mwgroup.vn")
    parser.add_argument("--row", type=int, default=None, help="Chỉ định đúng số dòng trên Sheet (ví dụ --row 26)")
    parser.add_argument("--rows", type=str, default=None, help="Khoảng dòng cần upload (ví dụ --rows 26-51 hoặc 26,27,28)")
    parser.add_argument("--img-dir", type=str, default=None, help="Thư mục chứa ảnh cục bộ")
    parser.add_argument("--cdp", type=str, default=CHROME_CDP_URL, help="URL Chrome Remote Debugging")

    args = parser.parse_args()
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
