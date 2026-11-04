#!/usr/bin/env bash
set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🚀 Đang cài đặt bộ Skill Erablue Image Pipeline từ: $SKILL_DIR"

# 1. Cài đặt Python venv & dependencies
if [ ! -d "$SKILL_DIR/.venv" ]; then
    echo "📦 Tạo môi trường ảo Python (.venv)..."
    python3 -m venv "$SKILL_DIR/.venv"
fi

echo "📥 Cài đặt thư viện Python..."
"$SKILL_DIR/.venv/bin/pip" install --upgrade pip -q
"$SKILL_DIR/.venv/bin/pip" install -r "$SKILL_DIR/requirements.txt" -q

# 2. Tự động khởi tạo ~/.config/gws/client_secret.json qua pipeline.py
echo "🔑 Cấu hình Google Workspace OAuth..."
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/pipeline.py" --help >/dev/null

# 3. Tự động liên kết vào thư mục .agents/skills/erablue-image-pipeline nếu đang ở trong workspace
WORKSPACE_SKILLS_DIR="$(cd "$SKILL_DIR/.." && pwd)/.agents/skills"
if [ -d "$WORKSPACE_SKILLS_DIR" ] && [ "$SKILL_DIR" != "$WORKSPACE_SKILLS_DIR/erablue-image-pipeline" ]; then
    mkdir -p "$WORKSPACE_SKILLS_DIR/erablue-image-pipeline"
    cp -f "$SKILL_DIR/SKILL.md" "$WORKSPACE_SKILLS_DIR/erablue-image-pipeline/SKILL.md"
    echo "✅ Đã đồng bộ SKILL.md vào $WORKSPACE_SKILLS_DIR/erablue-image-pipeline/"
fi

echo ""
echo "🎉 CÀI ĐẶT HOÀN TẤT!"
echo "👉 Bước tiếp theo (nếu máy mới chưa đăng nhập Google Drive/Sheet CLI):"
echo "   npx -y @googleworkspace/cli auth login"
echo ""
echo "👉 Chạy kiểm tra trạng thái Sheet ngay:"
echo "   $SKILL_DIR/.venv/bin/python $SKILL_DIR/pipeline.py status"
