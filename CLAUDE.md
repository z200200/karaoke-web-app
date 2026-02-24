# 卡拉OK Web App

## 项目信息

**项目名称**: 卡拉OK Web App

**GitHub**: https://github.com/z200200/karaoke-web-app

**版本**: v2.0 (性能优化版)

## 文件结构

### 前端文件
- `index.html` - 主前端页面 (Aura Studio 设计)
- `karaoke_app_oneclick.jsx` - React 组件版本

### 后端文件
- `karaoke_backend.py` - FastAPI 后端服务 (已优化)

### 文档文件
- `README.md` - 快速入门指南
- `DEPLOYMENT_GUIDE.md` - 完整部署文档
- `OPTIMIZATION_GUIDE.md` - 性能优化说明 ⭐ 新增

## 部署信息

### 前端部署
- **平台**: Vercel
- **地址**: karaoke-web-app-alpha.vercel.app

### 后端部署
- **平台**: Render

## 技术栈
- **后端**: Python + FastAPI + Demucs AI
- **前端**: HTML/JSX + Web Audio API
- **容器化**: Docker
- **AI 模型**: Meta Demucs v4 (htdemucs_ft)
- **视频下载**: yt-dlp

## 性能优化 (v2.0)

### ✅ 已实现的优化

1. **智能缓存系统**
   - YouTube URL 自动缓存
   - 重复请求 < 1 秒响应
   - 提升 180-300 倍速度

2. **GPU 自动加速**
   - 自动检测 CUDA GPU
   - GPU 处理快 5-8 倍
   - CPU 降级支持

3. **优化的 AI 模型**
   - 使用 htdemucs_ft 模型
   - 更高质量的音频分离
   - 更快的处理速度

### 性能对比

| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| 首次处理 (GPU) | 3-5 分钟 | 30-60 秒 |
| 重复处理 | 3-5 分钟 | < 1 秒 |

详细信息请查看: [OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)
