@echo off
REM 卡拉OK系统Windows启动脚本

echo ============================================
echo          卡拉OK系统启动脚本
echo ============================================

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装
    pause
    exit /b 1
)

REM 安装依赖
echo.
echo [信息] 检查Python依赖...
python -m pip install -q -r requirements.txt

if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo [成功] 依赖安装完成

REM 创建工作目录
if not exist audio_workspace mkdir audio_workspace
echo [成功] 工作目录创建完成

REM 启动后端
echo.
echo ============================================
echo          启动后端服务器
echo ============================================
echo 访问地址: http://localhost:8000
echo 健康检查: http://localhost:8000/health
echo API文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务器
echo ============================================
echo.

python karaoke_backend.py
