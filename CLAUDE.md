# Karaoke Web App

## 项目概述
一键式卡拉OK应用：输入YouTube链接 → AI分离人声/伴奏 → 浏览器内唱歌

**GitHub**: https://github.com/<YOUR_GITHUB_USERNAME>/karaoke-web-app
**版本**: v2.0 (性能优化版)

## 技术栈
- **后端**: FastAPI + Python
- **AI模型**: Demucs 4.0 (Meta AI音轨分离, htdemucs_ft)
- **视频下载**: yt-dlp
- **前端**: 原生HTML/CSS/JS + Tailwind CSS
- **播放**: Web Audio API
- **容器**: Docker

## 目录结构
```
├── karaoke_backend.py       # FastAPI后端 (712行)
├── index.html               # 前端页面 (Aura Studio设计)
├── karaoke_app_oneclick.jsx # React版本（备用）
├── requirements.txt         # Python依赖
├── Dockerfile              # Docker配置
├── start_backend.sh        # Unix启动脚本
├── start_backend.bat       # Windows启动脚本
├── test_system.py          # 系统验证脚本
├── vercel.json             # Vercel路由配置
├── README.md               # 快速入门指南
├── DEPLOYMENT_GUIDE.md     # 完整部署文档
└── OPTIMIZATION_GUIDE.md   # 性能优化说明
```

## 常用命令
```bash
# 后端
./start_backend.sh                    # 启动后端
uvicorn karaoke_backend:app --reload  # 开发模式
python3 test_system.py                # 系统测试

# 前端
python3 -m http.server 3000           # 本地预览

# Docker
docker build -t karaoke-backend .
docker run -p 8000:8000 karaoke-backend
```

## API端点
- `POST /api/process` - 处理YouTube链接
- `GET /api/status/{task_id}` - 查询任务状态
- `GET /download/{task_id}/{track_type}` - 下载音轨
- `GET /api/cache/stats` - 缓存统计
- `DELETE /api/cache` - 清除缓存
- `GET /health` - 健康检查

## 部署信息
- **前端**: Vercel (<YOUR_VERCEL_URL>)
- **后端**: Render

## 性能优化 (v2.0)

| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| 首次处理 (GPU) | 3-5 分钟 | 30-60 秒 |
| 重复处理 | 3-5 分钟 | < 1 秒 |

- **智能缓存**: 重复请求 <1秒 (提升180-300倍)
- **GPU加速**: CUDA自动检测，5-8倍提速
- **三层降级**: Demucs → Spleeter → FFmpeg

## 依赖安装
```bash
pip3 install -r requirements.txt
# 需要FFmpeg: apt install ffmpeg / brew install ffmpeg
```

详细优化信息: [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)
