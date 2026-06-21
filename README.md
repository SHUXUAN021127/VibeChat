# 🫧 VibeChat — AI 驱动的情绪社交

基于 AI 情绪识别的匿名社交平台。用户输入心情后，AI 分析情绪，自动匹配情绪相近的陌生人进入匿名对话。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI + WebSocket |
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 数据库 | SQLite (本地) / PostgreSQL (生产) |
| AI | OpenAI GPT-4o-mini 或 Anthropic Claude |
| 部署 | 后端 Railway · 前端 Vercel |

---

## 功能

核心功能（必做）：情绪输入 + AI 分析（标签/强度/正负向/关键词/颜色/解读）、情绪相似度匹配 + 30 秒兜底单人房间、匿名身份 + WebSocket 实时对话、OpenAI/Anthropic 双接口切换、AI 异常降级。

开放发挥（加分）：
- 🎨 情绪可视化（颜色光环、强度条、关键词）
- 😊 Emoji 表情选择器
- ⌨️ "对方正在输入"实时提示
- 🔄 双匹配模式：相似 / 互补情绪（环境变量切换）
- 💬 AI 破冰开场白
- 📈 情绪历史轨迹回顾（本地存储，含走势图）
- 🆘 极端负面情绪危机求助提示
- 🛡️ 内容审核：本地词库 + AI 双层，违规警告，累计3次踢出房间
- 👤 账号体系：邮箱密码 + Google 登录（微信/手机号接口骨架），游客可免登录使用
- 📚 历史持久化：登录用户的情绪卡片和聊天记录存服务器，可跨设备回看（含时间）

### 账号与登录

- **游客模式**：无需登录直接用，情绪轨迹存本地浏览器
- **登录模式**：邮箱密码或 Google 登录，情绪卡片和聊天记录存服务器，可在「我的」页面回看
- **始终匿名**：无论游客还是登录用户，聊天时都用系统生成的临时身份，别人看不到真实账号

Google 登录配置：在 Google Cloud Console 创建 OAuth 客户端，把 `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET` 填入 `.env`，回调地址设为 `{后端地址}/api/account/google/callback`。微信/手机号因需企业资质和短信服务，仅预留接口骨架。

### 内容审核

`ENABLE_AI_MODERATION` 控制是否启用 AI 审核：
- `true` — 本地词库 + AI 审核（更智能，每条消息多调一次 LLM）
- `false` — 仅本地词库（快、免费、零延迟）

违规处理：每个房间内累计计数，第 1/2 次警告并拦截消息，第 3 次踢出当前房间（仍可重新匹配）。

### 匹配模式切换

在 `backend/.env` 中通过 `MATCH_MODE` 控制：
- `similar` — 相似情绪：焦虑配焦虑，抱团取暖
- `complementary` — 互补情绪：焦虑配平静，互相调节

修改后重启后端生效。

---

## 本地启动

### 1. 后端

```bash
cd backend

# 创建 Python 虚拟环境
python -m venv venv

# 激活虚拟环境
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制并填写环境变量
cp .env.example .env
# 用编辑器打开 .env，填入你的 API Key

# 启动
uvicorn app.main:app --reload --port 8000
```

后端启动后访问 http://localhost:8000 可看到 `{"status":"ok"}`
API 文档：http://localhost:8000/docs

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 复制环境变量
cp .env.local.example .env.local
# 本地开发不需要修改，默认指向 localhost:8000

# 启动
npm run dev
```

前端启动后访问 http://localhost:3000

---

## LLM 配置说明

### 使用 OpenAI（默认）

在 `backend/.env` 中：

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-你的OpenAI密钥
OPENAI_MODEL=gpt-4o-mini
```

### 使用 Anthropic Claude

在 `backend/.env` 中：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-你的Anthropic密钥
ANTHROPIC_MODEL=claude-sonnet-4-6
```

**切换方式**：只需修改 `LLM_PROVIDER` 的值，重启后端即可。两种接口使用完全相同的 Prompt，输出格式一致。

---

## 部署到公网（详细教程）

### 第一步：准备 GitHub 仓库

1. 打开 https://github.com，注册账号（已有跳过）
2. 点右上角 **+** → **New repository**
3. 仓库名填 `vibechat`，选 **Private**，点 **Create repository**
4. 在你电脑的终端里：

```bash
cd /你的项目路径/vibechat
git init
git add .
git commit -m "init"
git remote add origin https://github.com/你的用户名/vibechat.git
git push -u origin main
```

---

### 第二步：部署后端到 Railway

1. 打开 https://railway.app，点 **Login with GitHub** 登录
2. 点 **New Project** → **Deploy from GitHub repo**
3. 选择刚才创建的 `vibechat` 仓库
4. Railway 会自动检测到两个目录，选择 **backend** 文件夹

**配置环境变量**（Railway 控制台 → Variables 标签页）：

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-你的key
OPENAI_MODEL=gpt-4o-mini
SECRET_KEY=随机生成一个字符串
DATABASE_URL=sqlite+aiosqlite:///./vibechat.db
FRONTEND_URL=https://你的前端地址.vercel.app
```

**配置启动命令**（Settings 标签页 → Start Command）：

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. 点 **Deploy**，等待部署完成（约 2 分钟）
6. 在 Settings → Networking → Generate Domain，获得后端域名，例如：
   `https://vibechat-backend.railway.app`

---

### 第三步：部署前端到 Vercel

1. 打开 https://vercel.com，点 **Login with GitHub** 登录
2. 点 **Add New Project** → 选择 `vibechat` 仓库
3. 重要：**Root Directory** 改为 `frontend`
4. 点 **Environment Variables**，添加：

```
NEXT_PUBLIC_API_URL=https://vibechat-backend.railway.app
NEXT_PUBLIC_WS_URL=wss://vibechat-backend.railway.app
```

5. 点 **Deploy**，等待约 1 分钟
6. 获得前端域名，例如：`https://vibechat.vercel.app`

---

### 第四步：更新后端 CORS 配置

回到 Railway 控制台，把 `FRONTEND_URL` 改为你的 Vercel 域名：

```
FRONTEND_URL=https://vibechat.vercel.app
```

Railway 会自动重新部署。

---

### 演示测试方法

赛题要求可以 mock 多用户测试聊天：

1. 用普通浏览器打开 https://你的域名.vercel.app，输入一段心情提交
2. 用**无痕/隐私模式**再开一个窗口，输入情绪相近的文字提交
3. 两个用户会被匹配到同一房间，可以互相聊天

---

## 项目结构

```
vibechat/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口
│   │   ├── config.py          # 环境变量配置
│   │   ├── models.py          # 数据库模型
│   │   ├── routers/
│   │   │   ├── emotion.py     # 情绪分析 API
│   │   │   ├── match.py       # 匹配 & 房间 API
│   │   │   └── chat.py        # WebSocket 聊天
│   │   └── services/
│   │       ├── llm.py         # LLM 调用（OpenAI/Anthropic）
│   │       ├── matching.py    # 情绪匹配算法
│   │       └── auth.py        # 匿名身份管理
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    ├── src/app/
    │   ├── page.tsx           # 首页：情绪输入
    │   ├── match/[roomCode]/  # 匹配等待页
    │   └── chat/[roomCode]/   # 匿名聊天页
    ├── src/lib/
    │   └── api.ts             # API 客户端
    └── .env.local.example
```

## API 文档

启动后端后访问：http://localhost:8000/docs（Swagger 自动文档）

主要接口：
- `POST /api/emotion/analyze` — 情绪分析 + 自动匹配
- `GET /api/match/status/{room_code}` — 轮询匹配状态
- `GET /api/match/room/{room_code}` — 获取房间信息
- `WS /ws/chat/{room_code}` — WebSocket 实时聊天
