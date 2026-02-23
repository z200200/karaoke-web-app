# 卡拉OK一键式系统 - 部署指南

## 📋 系统架构

```
用户输入YouTube链接
    ↓
前端React应用
    ↓
后端FastAPI服务器
    ↓
1. yt-dlp 下载音频
2. Demucs AI分离音轨
    ↓
返回：人声 + 伴奏
    ↓
前端自动播放
```

---

## 🚀 快速开始

### 1️⃣ 后端部署（服务器端）

#### 系统要求
- Python 3.8+
- 至少 4GB RAM
- 10GB 存储空间
- （推荐）NVIDIA GPU + CUDA（加速AI处理）

#### 安装步骤

```bash
# 1. 安装Python依赖
pip install fastapi uvicorn yt-dlp demucs python-multipart

# 2. 安装FFmpeg（必需）
# Ubuntu/Debian:
sudo apt update && sudo apt install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# 下载 https://ffmpeg.org/download.html 并添加到PATH

# 3. 验证安装
python -c "import demucs; print('Demucs安装成功')"
ffmpeg -version

# 4. 启动后端服务器
python karaoke_backend.py

# 服务器将运行在 http://localhost:8000
```

#### Docker部署（推荐生产环境）

```dockerfile
# Dockerfile
FROM python:3.10-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip install --no-cache-dir \
    fastapi uvicorn yt-dlp demucs python-multipart

# 复制代码
COPY karaoke_backend.py /app/
WORKDIR /app

# 创建工作目录
RUN mkdir -p /app/audio_workspace

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["uvicorn", "karaoke_backend:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# 构建和运行
docker build -t karaoke-backend .
docker run -p 8000:8000 -v $(pwd)/audio_workspace:/app/audio_workspace karaoke-backend
```

---

### 2️⃣ 前端部署

#### 方式A：直接在Claude Artifacts中使用

1. 将 `karaoke_app_oneclick.jsx` 的内容复制
2. 在Claude对话中说"创建artifact"
3. 粘贴代码
4. **重要**：修改API地址
   ```javascript
   const API_BASE = 'http://YOUR_SERVER_IP:8000';
   ```

#### 方式B：独立React项目

```bash
# 1. 创建React项目
npx create-react-app karaoke-frontend
cd karaoke-frontend

# 2. 安装依赖
npm install lucide-react

# 3. 替换 src/App.js
# 将 karaoke_app_oneclick.jsx 的内容复制进去

# 4. 启动开发服务器
npm start

# 访问 http://localhost:3000
```

---

## 🎯 使用流程

### 一键式处理（推荐）

1. **粘贴YouTube链接**
   - 在顶部输入框粘贴 YouTube 视频链接
   - 例如：`https://www.youtube.com/watch?v=dQw4w9WgXcQ`

2. **点击"一键处理"按钮**
   - 系统自动下载音频（约30秒-2分钟）
   - AI分离人声和伴奏（约2-5分钟）
   - 实时显示处理进度

3. **开始唱歌**
   - 处理完成后自动加载音频
   - 点击播放按钮开始
   - 调节原唱和伴奏音量

### 手动上传模式

如果你已有分离好的音频文件：
1. 点击"原唱音轨"区域上传人声文件
2. 点击"伴奏音轨"区域上传伴奏文件
3. 开始播放

---

## ⚙️ 配置优化

### 后端性能调优

#### 使用GPU加速（推荐）

```python
# 在 karaoke_backend.py 中修改
cmd = [
    'demucs',
    '--two-stems=vocals',
    '--device', 'cuda',  # 使用GPU
    '-o', output_dir,
    input_file
]
```

#### 调整音质

```python
# 高质量模式（更慢）
cmd = [
    'demucs',
    '--two-stems=vocals',
    '--mp3',  # 输出MP3格式
    '--mp3-bitrate=320',  # 最高音质
    '-o', output_dir,
    input_file
]

# 快速模式（更快但音质略低）
cmd = [
    'demucs',
    '--two-stems=vocals',
    '--float32',  # 更快的处理
    '--shifts=0',  # 减少计算量
    '-o', output_dir,
    input_file
]
```

### 前端API配置

如果后端在远程服务器：

```javascript
// 修改 API_BASE
const API_BASE = 'https://your-domain.com';  // 使用HTTPS
```

启用CORS（如果跨域）：
```python
# 在 karaoke_backend.py 中
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],  # 指定前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🔧 故障排除

### 常见问题

#### 1. "提交任务失败"
**原因**：后端服务器未启动或地址错误

**解决**：
```bash
# 检查后端是否运行
curl http://localhost:8000/health

# 应返回：{"status": "ok", ...}
```

#### 2. "处理超时"
**原因**：视频太长或服务器性能不足

**解决**：
- 选择较短的视频（< 5分钟推荐）
- 增加超时时间：
  ```python
  result = subprocess.run(cmd, timeout=1200)  # 20分钟
  ```

#### 3. "Demucs分离失败"
**原因**：内存不足或依赖问题

**解决**：
```bash
# 重新安装Demucs
pip uninstall demucs
pip install demucs

# 如果内存不足，使用Spleeter（更轻量）
pip install spleeter
# 代码会自动fallback到Spleeter
```

#### 4. "下载失败"
**原因**：YouTube地区限制或yt-dlp版本过旧

**解决**：
```bash
# 更新yt-dlp
pip install --upgrade yt-dlp

# 或使用代理
export HTTP_PROXY=http://your-proxy:port
```

#### 5. CORS错误
**原因**：跨域请求被阻止

**解决**：确保后端允许前端域名（见上方CORS配置）

---

## 📊 性能基准

| 视频长度 | 下载时间 | 分离时间（CPU） | 分离时间（GPU） |
|---------|---------|----------------|----------------|
| 3分钟   | 20-40秒  | 3-5分钟        | 30-60秒        |
| 5分钟   | 30-60秒  | 5-8分钟        | 1-2分钟        |
| 10分钟  | 1-2分钟  | 10-15分钟      | 2-4分钟        |

**建议**：
- 开发测试：使用较短视频（< 3分钟）
- 生产环境：使用GPU服务器
- 大量用户：考虑任务队列（Celery + Redis）

---

## 🌐 生产部署建议

### 1. 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;  # React前端
    }

    location /api {
        proxy_pass http://localhost:8000;  # FastAPI后端
        proxy_read_timeout 600s;  # 增加超时时间
    }
}
```

### 2. 使用进程管理器（PM2）

```bash
# 安装PM2
npm install -g pm2

# 启动后端
pm2 start "uvicorn karaoke_backend:app --host 0.0.0.0 --port 8000" --name karaoke-api

# 启动前端
pm2 start "npm start" --name karaoke-frontend

# 查看状态
pm2 status

# 设置开机自启
pm2 startup
pm2 save
```

### 3. 添加任务队列（高并发）

```python
# 使用Celery处理长时间任务
from celery import Celery

celery = Celery('karaoke', broker='redis://localhost:6379/0')

@celery.task
def process_youtube_async(task_id, youtube_url):
    # 原处理逻辑
    pass

# 在API中调用
@app.post("/api/process")
async def process_youtube(request: YouTubeRequest):
    task = process_youtube_async.delay(task_id, request.url)
    return {"task_id": task.id}
```

---

## 📁 文件结构

```
karaoke-system/
├── backend/
│   ├── karaoke_backend.py      # FastAPI服务器
│   ├── requirements.txt        # Python依赖
│   └── audio_workspace/        # 临时音频存储
│
├── frontend/
│   ├── src/
│   │   └── App.js             # React主应用
│   ├── package.json
│   └── public/
│
├── docker/
│   ├── Dockerfile.backend
│   └── docker-compose.yml
│
└── README.md                   # 本文档
```

---

## 🎓 技术栈说明

### 后端
- **FastAPI**: 高性能Python Web框架
- **yt-dlp**: YouTube视频/音频下载工具
- **Demucs**: Meta开源的AI音轨分离模型
- **FFmpeg**: 音频处理工具

### 前端
- **React**: UI框架
- **Web Audio API**: 浏览器原生音频处理
- **Lucide React**: 图标库

### AI模型
- **Demucs (htdemucs)**: 
  - 基于深度学习的源分离模型
  - 支持人声、鼓、贝斯、其他乐器分离
  - 模型大小：~200MB
  - 首次运行会自动下载模型

---

## 💰 成本估算

### 本地部署（免费）
- 硬件：个人电脑即可
- 软件：全部开源免费
- 网络：需要能访问YouTube

### 云服务器部署
- **基础方案**（CPU）：$10-20/月
  - 2核 4GB内存
  - 处理速度：1首歌约5分钟
  
- **推荐方案**（GPU）：$50-100/月
  - 4核 16GB + NVIDIA T4
  - 处理速度：1首歌约1分钟
  - 例如：AWS g4dn.xlarge, GCP n1-standard-4 + T4

---

## 📞 支持和反馈

遇到问题？
1. 查看上方"故障排除"章节
2. 检查后端日志：`journalctl -u karaoke-backend -f`
3. 前端控制台：F12 查看浏览器控制台
4. GitHub Issues（如果你托管在GitHub）

---

## 🔐 安全注意事项

1. **YouTube版权**：仅用于个人学习，不要用于商业用途
2. **API限流**：建议添加速率限制防止滥用
3. **文件清理**：定期清理 audio_workspace 目录
4. **HTTPS**：生产环境使用HTTPS保护数据传输

```python
# 添加速率限制示例
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/process")
@limiter.limit("5/minute")  # 每分钟最多5次请求
async def process_youtube(request: YouTubeRequest):
    ...
```

---

## ✅ 验证清单

部署完成后，验证以下功能：

- [ ] 后端健康检查：`curl http://localhost:8000/health`
- [ ] YouTube下载测试：提交一个短视频链接
- [ ] 音轨分离成功：查看 audio_workspace 目录
- [ ] 前端连接后端：检查浏览器Network面板
- [ ] 音频播放正常：两个音轨都能听到声音
- [ ] 音量控制生效：拖动滑块能调节音量

全部通过 = 部署成功！🎉

---

祝你唱歌愉快！🎤🎵
