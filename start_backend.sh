#!/bin/bash

# 卡拉OK系统一键启动脚本

echo "🎤 卡拉OK系统启动脚本"
echo "========================"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未检测到 Python3，请先安装"
    exit 1
fi

# 检查FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ 未检测到 FFmpeg，请先安装"
    echo "   Ubuntu/Debian: sudo apt install ffmpeg"
    echo "   macOS: brew install ffmpeg"
    exit 1
fi

# 安装依赖
echo "📦 检查Python依赖..."
pip3 install -q -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ 依赖安装完成"
else
    echo "❌ 依赖安装失败"
    exit 1
fi

# 创建工作目录
mkdir -p audio_workspace
echo "✅ 工作目录创建完成"

# 启动后端
echo ""
echo "🚀 启动后端服务器..."
echo "========================"
echo "访问地址: http://localhost:8000"
echo "健康检查: http://localhost:8000/health"
echo "API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "========================"

python3 karaoke_backend.py
