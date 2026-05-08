#!/usr/bin/env bash
# ==============================================================================
# ATMstockMarket 自动发布脚本
# 功能：更新README → 提交代码 → 创建Release → 上传资产
# 使用方法: bash publish.sh [版本号]
# 示例: bash publish.sh v7.2.0
# ==============================================================================

set -e

cd "$(dirname "$0")"

# ------------------------------------------------------------------------------
# 配置区域
# ------------------------------------------------------------------------------
GITHUB_TOKEN_FILE=".github_token"
OWNER="superherocheng"
REPO="ATMstockMarket"
README_FILE="README.md"

# ------------------------------------------------------------------------------
# 函数定义
# ------------------------------------------------------------------------------

function error_exit {
    echo "❌ $1"
    exit 1
}

function check_git_status {
    if ! git diff --quiet; then
        echo "⚠️  有未提交的更改，先提交..."
        git add -u
        git commit -m "Auto commit before release"
    fi
}

function update_readme {
    echo "📝 更新 README.md..."
    
    local VERSION="$1"
    local DATE=$(date "+%Y-%m-%d")
    
    # 更新版本号
    sed -i.bak "s/version.*:.*/version: $VERSION/g" "$README_FILE" 2>/dev/null || true
    sed -i.bak "s/V[0-9]*\.[0-9]*\.[0-9]*/$VERSION/g" "$README_FILE" 2>/dev/null || true
    
    # 更新日期
    sed -i.bak "s/updated.*:.*/updated: $DATE/g" "$README_FILE" 2>/dev/null || true
    
    rm -f "${README_FILE}.bak"
    
    echo "✅ README.md 已更新"
}

function get_next_version {
    # 获取最新tag并自动递增
    local latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "v1.0.0")
    local major=$(echo "$latest_tag" | cut -d. -f1 | sed 's/v//')
    local minor=$(echo "$latest_tag" | cut -d. -f2)
    local patch=$(echo "$latest_tag" | cut -d. -f3)
    
    # 递增版本号
    patch=$((patch + 1))
    if [ $patch -ge 10 ]; then
        patch=0
        minor=$((minor + 1))
    fi
    if [ $minor -ge 10 ]; then
        minor=0
        major=$((major + 1))
    fi
    
    echo "v${major}.${minor}.${patch}"
}

function store_token {
    echo "🔐 存储 GitHub Token..."
    read -p "请输入 GitHub Access Token: " TOKEN_INPUT
    
    if [ -z "$TOKEN_INPUT" ]; then
        error_exit "Token 不能为空"
    fi
    
    echo "$TOKEN_INPUT" > "$GITHUB_TOKEN_FILE"
    chmod 600 "$GITHUB_TOKEN_FILE"
    
    echo "✅ Token 已安全存储"
}

function load_token {
    if [ ! -f "$GITHUB_TOKEN_FILE" ]; then
        store_token
    fi
    export GITHUB_TOKEN=$(cat "$GITHUB_TOKEN_FILE")
}

function create_release {
    local TAG="$1"
    local RELEASE_NAME="Version ${TAG#v}"
    
    echo "📦 打包项目..."
    bash package.sh
    
    echo "📝 创建 Release: $TAG..."
    
    local BODY=$(cat <<EOF
## ✨ 更新内容

- 自动发布: $TAG
- 更新日期: $(date "+%Y-%m-%d")

## 📁 文件结构

\`\`\`
ATMstockMarket/
├── tushare-py/          # 数据获取层
├── web/                 # Web 应用层
│   ├── static/          # 静态资源
│   ├── templates/       # HTML模板
│   └── app.py           # FastAPI后端
└── 启动脚本/配置文件
\`\`\`

## 🚀 快速开始

\`\`\`bash
git clone https://github.com/$OWNER/$REPO.git
cd $REPO
bash setup.sh
cp tushare-py/config.py.example tushare-py/config.py
# 编辑 config.py 填入 Tushare Token
cd tushare-py && python fetch_data.py
cd ../web && python -m uvicorn app:app --host 0.0.0.0 --port 8000
\`\`\`
EOF
)
    
    local RELEASE_RESPONSE=$(curl -s -X POST "https://api.github.com/repos/$OWNER/$REPO/releases" \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"tag_name\": \"$TAG\",
        \"target_commitish\": \"main\",
        \"name\": \"$RELEASE_NAME\",
        \"body\": $(printf '%s' "$BODY" | jq -Rs .),
        \"draft\": false,
        \"prerelease\": false
      }")
    
    local UPLOAD_URL=$(echo "$RELEASE_RESPONSE" | jq -r '.upload_url' | sed 's/{.*}//')
    
    if [ -z "$UPLOAD_URL" ] || [ "$UPLOAD_URL" = "null" ]; then
        echo "❌ 创建 Release 失败"
        echo "$RELEASE_RESPONSE"
        exit 1
    fi
    
    echo "📤 上传资产..."
    local ASSET_RESPONSE=$(curl -s -X POST "$UPLOAD_URL?name=$REPO.zip" \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Content-Type: application/zip" \
      --data-binary @"../$REPO.zip")
    
    echo "✅ Release 创建完成!"
    echo "🔗 https://github.com/$OWNER/$REPO/releases/tag/$TAG"
}

# ------------------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------------------

echo "========================================="
echo "  ATMstockMarket 自动发布脚本"
echo "========================================="

# 1. 获取版本号
if [ -n "$1" ]; then
    VERSION="$1"
else
    VERSION=$(get_next_version)
    echo "📌 使用自动递增版本号: $VERSION"
fi

# 2. 加载/存储 Token
load_token

# 3. 更新 README
update_readme "$VERSION"

# 4. 检查并提交更改
check_git_status

# 5. 推送代码
echo "📤 推送代码到 GitHub..."
git push origin main

# 6. 创建 Release
create_release "$VERSION"

echo "========================================="
echo "🎉 发布完成!"
echo "版本: $VERSION"
echo "========================================="