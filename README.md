# 🫧 VibeChat — AI 驱动的情绪社交

> 先被理解，再去连接。

VibeChat 是一款基于 AI 情绪识别的匿名社交应用。用户写下当下的心情，AI 分析其中的情绪色彩，再将情绪状态相近（或互补）的用户自动匹配到同一段匿名对话中。它把"情绪"真正转化成了匹配、对话和体验。

## 🌐 线上演示

- **前端地址**：`https://你的前端.vercel.app`
- **后端 API**：`https://你的后端.up.railway.app`

> 演示说明：无需注册即可作为游客体验。若想体验历史记录功能，可用邮箱注册或 Google 登录。单人体验时，系统会以 AI 陪聊兜底，可完整跑通对话流程。

---

## ✨ 核心功能

### 情绪识别
- 用户输入一段心情/状态/想说的话，AI 进行情绪分析
- 输出**主情绪 + 情绪强度 + 正负向 + 关键词 + 情绪色彩 + 共情解读**
- **多维度情绪**：识别主情绪之外隐藏的 2~3 个次要情绪及其占比，捕捉复合情绪

### 情绪匹配
- **相似匹配**：把情绪相近的人匹配到一起，抱团取暖
- **互补匹配**：把情绪互补的人匹配到一起（如焦虑配平静），互相调节
- 匹配算法：主情绪为主，结合强度、正负向、**次要情绪重叠度**综合打分
- **双向确认**（互补模式）：匹配后双方各有一次选择机会，都同意才进入对话
- **兜底机制**：30 秒未匹配到真人时，由 AI 扮演情绪相近的匿名陌生人陪聊

### 匿名对话
- 完成匹配后进入实时匿名文本对话（WebSocket）
- 系统生成匿名昵称和头像，不暴露真实身份
- **双方定制破冰语**：进入对话时，AI 根据双方共同情绪生成开场白
- "对方正在输入"实时状态、Emoji 表情、消息时间戳
- **一对一 / 情绪房间**两种模式：前者深度匹配，后者按情绪进入公共多人房

### 安全与体验
- **内容审核**：本地敏感词库 + AI 审核双层防线，违规警告，累计 3 次踢出房间
- **危机干预**：识别极端负面情绪时给出心理援助热线提示
- **房间生命周期**：闲置 30 秒提示、1分50秒预警、2分钟自动关闭；一方退出则房间解散并通知对方
- **情绪轨迹**：游客存本地，登录用户存服务器，可回看历史情绪卡片与聊天记录

### 账号体系
- 邮箱密码注册/登录、Google OAuth 登录（微信/手机号预留接口）
- 游客模式免登录直接使用
- 登录与匿名聊天解耦：**无论哪种方式，聊天全程匿名**

---

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.13 · FastAPI · WebSocket · SQLAlchemy(异步) |
| 前端 | Next.js 14 · TypeScript · Tailwind CSS |
| 数据库 | 本地 SQLite · 生产 PostgreSQL（自动适配 + 自动迁移） |
| AI | OpenAI / Anthropic 双接口（环境变量切换） |
| 部署 | 后端 Railway · 前端 Vercel |

---

## 🚀 本地启动

### 后端

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # 复制后填入你的 API Key
uvicorn app.main:app --reload --port 8000
```

后端启动后：
- 健康检查：http://localhost:8000/health
- API 文档：http://localhost:8000/docs

### 前端

```bash
cd frontend
npm install
cp .env.local.example .env.local   # 本地默认指向 localhost:8000，无需修改
npm run dev
```

访问 http://localhost:3000

---

## 🔑 LLM 配置（OpenAI / Anthropic 切换）

在 `backend/.env` 中通过 `LLM_PROVIDER` 切换，两种接口输出格式一致：

**使用 OpenAI：**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-你的密钥
OPENAI_MODEL=gpt-4o-mini
```

**使用 Anthropic：**
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-你的密钥
ANTHROPIC_MODEL=claude-sonnet-4-6
```

修改后重启后端生效。

### 其他可配置项

```env
MATCH_MODE=similar              # similar 相似匹配 / complementary 互补匹配
ENABLE_AI_MODERATION=true       # 是否启用 AI 内容审核
SECRET_KEY=你的密钥串            # JWT 签名密钥
# Google 登录（可选）
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/account/google/callback
```

---

## ☁️ 部署到公网

### 1. 推送代码到 GitHub

```bash
git init
git add .
git commit -m "VibeChat"
git remote add origin https://github.com/你的用户名/vibechat.git
git push -u origin main
```

### 2. 部署后端到 Railway

1. https://railway.app → Login with GitHub → New Project → Deploy from GitHub repo → 选择仓库
2. 进入服务 Settings：
   - **Root Directory** 填 `backend`
   - **Start Command** 填 `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. 添加 PostgreSQL：项目内 New → Database → Add PostgreSQL
4. 在服务 Variables 添加环境变量：
   ```
   LLM_PROVIDER=openai
   OPENAI_API_KEY=你的密钥
   OPENAI_MODEL=gpt-4o-mini
   SECRET_KEY=随机字符串
   ENABLE_AI_MODERATION=true
   MATCH_MODE=similar
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   FRONTEND_URL=（前端部署后回填）
   ```
5. Settings → Networking → Generate Domain，得到后端公网地址

> 代码会自动把 `postgresql://` 转成异步驱动并自动迁移数据库表结构，无需手动建表。

### 3. 部署前端到 Vercel

1. https://vercel.com → 导入同一个 GitHub 仓库
2. **Root Directory** 设为 `frontend`
3. 添加环境变量（填你的后端地址）：
   ```
   NEXT_PUBLIC_API_URL=https://你的后端.up.railway.app
   NEXT_PUBLIC_WS_URL=wss://你的后端.up.railway.app
   ```
   > 注意 WS 用 `wss://`（加密）
4. Deploy，得到前端公网地址

### 4. 回填 FRONTEND_URL

回到 Railway，把 `FRONTEND_URL` 设为你的 Vercel 前端地址（结尾不加斜杠），保存后自动重新部署。

---

## 🧪 演示测试方法

- **单人体验**：直接输入情绪提交，30 秒后由 AI 陪聊兜底，可完整体验对话
- **双人匹配**：用普通窗口 + 无痕窗口（隔离身份）各提交一次相近情绪，会匹配到同一房间
- **互补匹配**：将 `MATCH_MODE` 设为 `complementary`，一方输入负面情绪、一方输入正面情绪，体验双向确认
- **历史记录**：注册/登录后聊天，在「我的」页面回看情绪卡片与聊天记录

---

## 📁 项目结构

```
vibechat/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口 + 后台清理任务
│   │   ├── config.py          # 环境变量配置
│   │   ├── models.py          # 数据模型 + 自动迁移
│   │   ├── routers/
│   │   │   ├── emotion.py     # 情绪分析 + 匹配入口
│   │   │   ├── match.py       # 匹配状态 / 房间 / 互补确认
│   │   │   ├── chat.py        # WebSocket 实时聊天 + AI 陪聊
│   │   │   └── account.py     # 账号认证 + 历史记录
│   │   └── services/
│   │       ├── llm.py         # LLM 情绪分析（双接口）
│   │       ├── matching.py    # 情绪匹配算法
│   │       ├── pending.py     # 互补确认状态机 + 在线追踪
│   │       ├── companion.py   # AI 陪聊
│   │       ├── icebreaker.py  # 双方定制破冰语
│   │       ├── moderation.py  # 内容审核
│   │       └── account.py     # 账号 / JWT
│   └── requirements.txt
│
└── frontend/
    └── src/
        ├── app/
        │   ├── page.tsx              # 首页：情绪输入 + 模式选择 + 使用指引
        │   ├── login/               # 登录注册
        │   ├── auth/callback/        # Google 回调
        │   ├── profile/             # 个人中心：情绪卡片 + 聊天记录
        │   ├── match/[roomCode]/    # 匹配等待 + 互补确认 + 情绪可视化
        │   └── chat/[roomCode]/     # 匿名实时聊天
        └── lib/api.ts               # API 客户端
```

---

## 📡 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/emotion/analyze` | 情绪分析 + 自动匹配 |
| POST | `/api/emotion/rematch` | 复用情绪重新匹配 |
| GET | `/api/match/status/{room_code}` | 轮询匹配状态 |
| GET | `/api/match/room/{room_code}` | 房间信息 + 破冰语 |
| GET/POST | `/api/match/confirm/*` | 互补模式双向确认 |
| WS | `/ws/chat/{room_code}` | WebSocket 实时聊天 |
| POST | `/api/account/register` `/login` | 邮箱注册 / 登录 |
| GET | `/api/account/google/login` | Google 登录 |
| GET | `/api/account/history/*` | 情绪卡片 / 聊天记录 |

完整交互式文档见后端 `/docs`。
