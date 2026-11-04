# HƯỚNG DẪN VẬN HÀNH ERABLUE IMAGE PIPELINE (DÀNH CHO ANTIGRAVITY & KỸ THUẬT VIÊN)

Gói thư mục này chứa toàn bộ mã nguồn, dữ liệu prompt mẫu và công cụ tự động hóa **Quy trình 6 bước tạo ảnh sản phẩm, upload Google Drive và sửa ảnh QC thay thế (in-place replacement)** cho website **Erablue Indonesia**.

Bạn có thể chuyển giao thư mục này sang bất kỳ môi trường **Google Antigravity**, **Cursor**, hoặc máy tính khác để chạy tự động 100% mà không bị gián đoạn.

---

## 📁 CẤU TRÚC GÓI CÔNG CỤ (`erablue_image_pipeline_package`)

```
erablue_image_pipeline_package/
├── pipeline.py               # Script điều phối trung tâm (toàn bộ 6 bước)
├── Era_Promt_tao_anh.csv     # Bộ 461 Prompt mẫu chi tiết theo từng ngành hàng
├── .env                      # File cấu hình chứa Token OpenRouter & Model AI
├── requirements.txt          # Thư viện Python cần thiết (requests, Pillow, bs4)
├── SKILL.md                  # File định nghĩa Skill cho Antigravity AI Agent
├── HUONG_DAN_SU_DUNG.md      # Tài liệu hướng dẫn chi tiết tiếng Việt (file này)
└── README.md                 # Bản sao hướng dẫn tiện tra cứu
```

---

## 🔑 CẤU HÌNH API TOKEN & MODEL TẠO ẢNH (ĐÃ KÈM SẴN 100%)

Gói công cụ đã được **tích hợp sẵn đầy đủ API Token và Model AI** ở cả 2 tầng (chạy ngay lập tức mà không cần cấu hình thêm):

1. **File cấu hình độc lập `.env` & Fallback tự động trong `pipeline.py`:**
   - **API Key:** Đã tích hợp sẵn tự động trong `pipeline.py` (tài khoản OpenRouter của dự án) hoặc cấu hình qua biến `OPENROUTER_KEY` trong `.env`.
   - **Model tạo ảnh:** `openai/gpt-image-2.5-sunburst` (Model tạo ảnh tối ưu nhất cho banner thương mại điện tử, giữ chi tiết ảnh gốc cực tốt).
   - **Chất lượng:** `medium` (Cân bằng hoàn hảo giữa độ nét cao và tốc độ sinh ảnh).
   - **Kích thước ảnh:** `1020 x 680 px`, dung lượng `< 500 KB`.
   
2. **Cơ chế Fallback an toàn trong [`pipeline.py`](file:///Users/trannguyenmy/Desktop/Antigravity/erablue_image_pipeline_package/pipeline.py):**
   - Nếu bạn di chuyển script sang thư mục khác hoặc file `.env` bị ẩn/mất, script vẫn có sẵn token và model mặc định bên trong code để đảm bảo luôn chạy được 100%.

---

## ⚙️ CÀI ĐẶT MÔI TRƯỜNG TRONG 1 PHÚT

Trên máy mới hoặc môi trường Antigravity mới, mở Terminal tại thư mục dự án và chạy:

```bash
# 1. Tạo và kích hoạt môi trường ảo Python
python3 -m venv .venv
source .venv/bin/activate

# 2. Cài đặt các thư viện bắt buộc
pip install -r erablue_image_pipeline_package/requirements.txt

# 3. Cấu hình Google Workspace OAuth (Drive & Sheets)
# File client_secret.json đã được đính kèm sẵn trong gói erablue_image_pipeline_package/!
# Script pipeline.py sẽ tự động copy file này vào ~/.config/gws/client_secret.json.
# Hoặc bạn có thể copy thủ công:
mkdir -p ~/.config/gws && cp erablue_image_pipeline_package/client_secret.json ~/.config/gws/

# 4. Đăng nhập liên kết Google Drive & Sheets một lần duy nhất:
npx -y @googleworkspace/cli auth login
# (Trình duyệt sẽ mở ra -> Chọn tài khoản Google quản lý Drive/Sheet -> Bấm Cho phép/Allow)
```

> **Sau khi chạy `auth login` thành công 1 lần**, token truy cập sẽ được lưu vĩnh viễn trên máy, toàn bộ các lệnh upload, replace in-place trên Drive và cập nhật Sheet sẽ hoạt động trơn tru 100%!

---

## 🔄 CHI TIẾT QUY TRÌNH 6 BƯỚC TỰ ĐỘNG HÓA

```mermaid
flowchart TD
    subgraph BƯỚC 1 ĐẾN 4: TẠO MỚI & UPLOAD DRIVE
        A[Bước 1: Quét Sheet Description<br/>Lọc Row có HTML Cột O nhưng Cột P trống] --> B[Bước 2: Tạo ảnh AI theo ngành hàng<br/>• Tham chiếu ảnh Thumbnail Cột H<br/>• Prompt mẫu 461 ngành hàng<br/>• 100% Tiếng Bahasa Indonesia<br/>• Kích thước chuẩn 1020x680 JPG < 500KB]
        B --> C[Bước 3: Đặt tên chuẩn slug-index.jpg<br/>Lưu vào thư mục cục bộ]
        C --> D[Bước 4: Upload Google Drive<br/>• Tạo subfolder trong Parent Drive<br/>• Dán link folder vào Cột P Google Sheet]
    end

    subgraph BƯỚC 5 & 6: KIỂM SOÁT CHẤT LƯỢNG (QC) & REPLACE DRIVE
        E[Bước 5: Quét QC Cột Q & Cột R<br/>• Tìm Cột Q = 'need to fix'<br/>• Parser bóc tách số Jpeg và nội dung cần sửa] --> F[Bước 6: Tái tạo & Thay thế in-place<br/>• Chỉ sinh lại các ảnh bị reviewer bắt lỗi<br/>• Dùng lệnh update đè file cũ trên Drive<br/>• Giữ nguyên File ID & các ảnh đạt chuẩn khác<br/>• Đổi Cột Q thành 'Fixed']
    end

    D -.-> E
```

### 1. Thông tin kết nối hệ thống
- **Google Sheet:**
  - ID: `1dp3cY7CAs-OGbc4jCyUC3oNmkNA5LB1AkTINKl_n0BU`
  - Tab: `Description`
  - Cột O: Mã nguồn HTML bài viết sản phẩm (chứa các thẻ `<h2>`/`<h3>` tương ứng từng ảnh).
  - Cột P: Link thư mục Google Drive chứa ảnh thành phẩm.
  - Cột Q: Trạng thái duyệt (`Approve`, `need to fix`, `Fixed`).
  - Cột R: Ghi chú phản hồi chi tiết từ reviewer Indonesia.
- **Google Drive:**
  - Thư mục cha (Parent Folder ID): `1wwT7biwT8BDtcOhhf-Nxtt8ddkidWDEN`
  - Mỗi sản phẩm có 1 subfolder riêng mang tên `slug` của sản phẩm.
- **AI Image Generation Engine:**
  - Model: `openai/gpt-image-2.5-sunburst` (qua OpenRouter API).
  - Khóa API: Đã tích hợp sẵn trong script (hoặc có thể cấu hình qua biến môi trường `export OPENROUTER_KEY="..."`).

---

## 💻 BẢNG LỆNH THỰC THI (CLI COMMANDS)

Tất cả thao tác đều được điều khiển qua file `pipeline.py`:

### 1. Xem tổng quan tiến độ Google Sheet
```bash
python3 erablue_image_pipeline_package/pipeline.py status
```
*Lệnh này quét toàn bộ 2640 dòng của Sheet và báo cáo:*
- Số sản phẩm đã có ảnh Drive (Cột P có link).
- Số sản phẩm đang chờ tạo ảnh (Cột O có bài, Cột P trống).
- Danh sách các sản phẩm đang bị đánh dấu `need to fix` kèm nội dung ghi chú.

### 2. Tạo ảnh cho các bài viết mới chưa có ảnh (Bước 1 - 4)
```bash
# Chạy cho tất cả các sản phẩm đang chờ trong Sheet:
python3 erablue_image_pipeline_package/pipeline.py create

# Hoặc thử nghiệm với số lượng giới hạn (ví dụ 3 sản phẩm đầu tiên):
python3 erablue_image_pipeline_package/pipeline.py create --limit 3
```

### 3. Kiểm tra danh sách feedback cần sửa từ Reviewer Indonesia (Bước 5)
```bash
python3 erablue_image_pipeline_package/pipeline.py check-qc
```
*Lệnh này in ra danh sách chi tiết: Tên sản phẩm, link Drive, ghi chú gốc, và danh sách các Jpeg được parser tự động bóc tách cùng yêu cầu sửa đổi.*

### 4. Sửa ảnh và Replace trực tiếp trên Google Drive (Bước 5 - 6)
```bash
# Tự động sửa và Replace Drive cho TOÀN BỘ sản phẩm có trạng thái 'need to fix':
python3 erablue_image_pipeline_package/pipeline.py fix-qc

# Hoặc chỉ định sửa riêng 1 dòng cụ thể trên Sheet (ví dụ dòng 26):
python3 erablue_image_pipeline_package/pipeline.py fix-qc --row 26
```

### 5. Đăng bài viết HTML & ảnh tương ứng từng Heading lên PIM
```bash
# Upload bài viết và ảnh Gallery cho 1 sản phẩm cụ thể (ví dụ dòng 26 trên Google Sheet):
python3 erablue_image_pipeline_package/pipeline.py upload-pim --row 26

# Hoặc upload hàng loạt theo khoảng dòng (ví dụ từ dòng 26 đến dòng 51):
python3 erablue_image_pipeline_package/pipeline.py upload-pim --rows 26-51

# Hoặc chạy script riêng lẻ trực tiếp:
python3 erablue_image_pipeline_package/upload_pim.py --row 26
```

---

## 🌐 QUY TRÌNH UPLOAD HTML & ẢNH HEADING LÊN PIM (mwgroup.vn)

Quy trình tự động hóa đăng bài hoàn chỉnh từ Google Sheet và kho ảnh cục bộ lên hệ thống **PIM MWG (https://pim.mwgroup.vn)**:

### 1. Chuẩn bị Chrome Remote Debugging
PIM sử dụng hệ thống đăng nhập SSO nội bộ. Để AI Agent có thể thao tác với PIM mà không bị chặn captcha/auth, mở trình duyệt Chrome với cổng điều khiển `9222`:

- **Trên macOS:**
  ```bash
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
  ```
- **Trên Windows:**
  ```cmd
  chrome.exe --remote-debugging-port=9222
  ```
- Đăng nhập tài khoản nội bộ tại: `https://pim.mwgroup.vn`

### 2. Cách thức tự động chèn ảnh tương ứng vào từng Heading
1. **Bóc tách tiêu đề:** Script đọc HTML bài viết từ **Cột O** và tìm tất cả các thẻ tiêu đề `<h2>` (hoặc `<h3>`).
2. **Nạp ảnh lên CDN PIM:** Script quét thư mục ảnh cục bộ `<slug>/` và tải từng ảnh (`<slug>-1.jpg`, `<slug>-2.jpg`...) lên CDN PIM thông qua API CKEditor FileRepository adapter để lấy URL CDN vĩnh viễn (`https://cdnv2.tgdd.vn/...`).
3. **Biên dịch mã HTML:** Tự động chèn thẻ HTML ảnh chuẩn SEO ngay bên dưới thẻ `<h2>` tương ứng:
   ```html
   <figure class="image">
       <img src="https://cdnv2.tgdd.vn/pim/..." alt="Tiêu đề H2" width="1020" height="680" loading="lazy" style="aspect-ratio:1020/680;" />
   </figure>
   ```
4. **Bơm bài viết vào Editor:** Chuyển CKEditor sang chế độ `Source mode`, dán mã HTML đã biên dịch hoàn chỉnh.
5. **Nạp Gallery:** Mở mục **Thông tin hình ảnh theo biến thể** -> **Hình gallery**, tự động nạp toàn bộ danh sách ảnh JPG vào file input.
6. **Xử lý thông minh theo cấu trúc sản phẩm:**
   - **Tab Biến thể (Smartphone, Tablet, Smartwatch):** Tự động duyệt qua từng biến thể màu, dán bài viết và up Gallery cho từng màu, bấm "Đồng ý", sau đó bấm "Lưu" Model.
   - **Tab Chung (Điện máy, Máy lạnh, Máy giặt, Cây nước...):** Dán bài viết và up Gallery trực tiếp ở panel chính, sau đó bấm "Lưu" Model.

---

## 🤖 PROMPT MẪU ĐỂ GIAO VIỆC CHO CON ANTIGRAVITY MỚI

Khi bạn mở một phiên làm việc mới trên một con Antigravity khác, bạn chỉ cần copy đoạn prompt sau và gửi cho nó:

```markdown
Chào bạn, tôi đã chuẩn bị sẵn gói công cụ tự động hóa ảnh Erablue tại thư mục `erablue_image_pipeline_package/`.
Nhiệm vụ của bạn:
1. Đọc kỹ file `erablue_image_pipeline_package/HUONG_DAN_SU_DUNG.md` và `erablue_image_pipeline_package/SKILL.md`.
2. Chạy lệnh:
   source .venv/bin/activate
   python3 erablue_image_pipeline_package/pipeline.py status
3. Báo cáo cho tôi tình trạng hiện tại của Google Sheet (bao nhiêu bài chờ tạo ảnh, bao nhiêu bài cần fix QC).
4. Thực hiện theo yêu cầu của tôi:
   - Nếu tôi yêu cầu tạo ảnh mới: chạy `python3 erablue_image_pipeline_package/pipeline.py create`
   - Nếu tôi yêu cầu sửa ảnh QC: chạy `python3 erablue_image_pipeline_package/pipeline.py fix-qc`
   - Nếu tôi yêu cầu đăng bài lên PIM: chạy `python3 erablue_image_pipeline_package/pipeline.py upload-pim --row <số_dòng>` (hoặc `--rows <từ>-<đến>`)
Lưu ý quan trọng: Luôn tuân thủ quy chuẩn 100% Bahasa Indonesia, giữ nguyên File ID khi replace Drive, và không làm ảnh hưởng đến các ảnh đạt chuẩn khác.
```

---

## ⚠️ CÁC QUY TẮC BẤT BIẾN (CORE INVIOLABLE RULES)

1. **Thay thế in-place trên Google Drive:**
   - Khi sửa ảnh ở Bước 6, bắt buộc dùng lệnh `drive files update` để đè dữ liệu mới lên đúng fileId cũ.
   - Tuyệt đối không xóa folder hay tạo file mới làm đổi link chia sẻ.
   - Giữ nguyên 100% các file ảnh khác trong folder không bị reviewer bắt lỗi.
2. **Ngôn ngữ bắt buộc 100% Bahasa Indonesia:**
   - Tất cả tiêu đề, nhãn công nghệ, từ ngữ hiển thị trên ảnh banner phải là tiếng Indonesia tự nhiên.
   - Tuyệt đối không dùng tiếng Việt, không để lẫn tiếng Anh máy dịch thô.
3. **Đồng nhất ngoại hình sản phẩm từ Thumbnail:**
   - Nếu reviewer ghi chú `every design have a different product picture`, AI phải tải ảnh Thumbnail ở Cột H làm tham chiếu vision để tái tạo tất cả các slide có cùng hình khối, màu sắc, chi tiết nắp/vòi/nút bấm đồng nhất.
4. **Quy chuẩn đồ họa & dung lượng:**
   - Kích thước: `1020 x 680 px`.
   - Định dạng: `JPG`.
   - Dung lượng: Nén tối ưu `< 500 KB`.
   - Typography: Font Sans-serif hình học hiện đại, ALL CAPS, tối đa 3 tầng thông tin rõ ràng, không chồng chéo chữ.
