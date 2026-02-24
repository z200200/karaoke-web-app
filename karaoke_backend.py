"""
卡拉OK音轨处理后端服务
功能：YouTube下载 + AI音轨分离
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import yt_dlp
import os
import uuid
import subprocess
from pathlib import Path
import logging
import asyncio
import json
import hashlib
import shutil

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Karaoke Audio Processor")

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 工作目录
WORK_DIR = Path("./audio_workspace")
WORK_DIR.mkdir(exist_ok=True)

# 缓存目录
CACHE_DIR = Path("./audio_cache")
CACHE_DIR.mkdir(exist_ok=True)

# 任务状态存储
tasks = {}

# 任务历史记录
history = {}

# 任务日志队列
task_logs = {}

class YouTubeRequest(BaseModel):
    url: str

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, downloading, separating, completed, error
    progress: int
    message: str
    title: Optional[str] = None
    vocal_url: Optional[str] = None
    instrumental_url: Optional[str] = None
    lyrics: Optional[str] = None

def add_task_log(task_id: str, message: str):
    """添加任务日志"""
    if task_id not in task_logs:
        task_logs[task_id] = []
    task_logs[task_id].append(message)
    logger.info(f"[{task_id}] {message}")

def get_cache_key(youtube_url: str) -> str:
    """生成 YouTube URL 的缓存键"""
    return hashlib.md5(youtube_url.encode()).hexdigest()

def check_cache(youtube_url: str) -> Optional[dict]:
    """检查 YouTube URL 是否已经处理过并缓存"""
    cache_key = get_cache_key(youtube_url)
    cache_path = CACHE_DIR / cache_key

    if cache_path.exists():
        vocal_file = cache_path / "vocals.wav"
        instrumental_file = cache_path / "no_vocals.wav"
        metadata_file = cache_path / "metadata.json"

        if vocal_file.exists() and instrumental_file.exists():
            logger.info(f"缓存命中: {youtube_url} -> {cache_key}")
            metadata = {}
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except Exception as e:
                    logger.warning(f"读取元数据失败: {e}")

            return {
                'vocals': str(vocal_file),
                'instrumental': str(instrumental_file),
                'title': metadata.get('title', 'Cached Audio'),
                'cached': True
            }

    return None

def save_to_cache(youtube_url: str, vocal_file: str, instrumental_file: str, title: str = "Unknown"):
    """保存处理结果到缓存"""
    try:
        cache_key = get_cache_key(youtube_url)
        cache_path = CACHE_DIR / cache_key
        cache_path.mkdir(exist_ok=True)

        # 复制文件到缓存目录
        shutil.copy2(vocal_file, cache_path / "vocals.wav")
        shutil.copy2(instrumental_file, cache_path / "no_vocals.wav")

        # 保存元数据
        metadata = {
            'url': youtube_url,
            'title': title,
            'cached_at': str(Path(vocal_file).stat().st_mtime)
        }

        with open(cache_path / "metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"已保存到缓存: {youtube_url} -> {cache_key}")
    except Exception as e:
        logger.error(f"保存缓存失败: {e}")

def detect_gpu_support() -> tuple[bool, str]:
    """检测 GPU 支持"""
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"检测到 CUDA GPU: {device_name}")
            return True, "cuda"
        else:
            logger.info("未检测到 CUDA GPU, 使用 CPU")
            return False, "cpu"
    except ImportError:
        logger.info("PyTorch 未安装, 使用 CPU")
        return False, "cpu"

def download_youtube_audio(url: str, output_path: str) -> str:
    """下载YouTube音频"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"开始下载: {url}")
            ydl.download([url])
            # 返回实际的mp3文件路径
            return output_path + '.mp3'
    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        raise

def separate_audio_demucs(input_file: str, output_dir: str, use_gpu: bool = None) -> dict:
    """使用Demucs分离音轨 (优化版)"""
    try:
        logger.info(f"开始分离音轨: {input_file}")

        # 自动检测 GPU 支持
        if use_gpu is None:
            has_gpu, device = detect_gpu_support()
        else:
            device = "cuda" if use_gpu else "cpu"
            has_gpu = use_gpu

        # 使用优化的 Demucs 命令行参数
        cmd = [
            'demucs',
            '--two-stems=vocals',  # 只分离人声和伴奏
            '-n', 'htdemucs_ft',  # 使用 fine-tuned 模型 (更快更准)
            '--device', device,  # GPU 或 CPU
            '-o', output_dir,
            input_file
        ]

        logger.info(f"使用设备: {device} {'(GPU加速)' if has_gpu else '(CPU)'}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            raise Exception(f"Demucs分离失败: {result.stderr}")
        
        # Demucs输出结构: output_dir/htdemucs/filename/vocals.wav 和 no_vocals.wav
        filename = Path(input_file).stem
        base_path = Path(output_dir) / "htdemucs" / filename

        return {
            'vocals': str(base_path / "vocals.wav"),
            'instrumental': str(base_path / "no_vocals.wav")
        }
        
    except subprocess.TimeoutExpired:
        logger.error("音轨分离超时")
        raise Exception("处理超时，请尝试较短的音频")
    except Exception as e:
        logger.error(f"音轨分离失败: {str(e)}")
        raise

def separate_audio_spleeter(input_file: str, output_dir: str) -> dict:
    """使用Spleeter分离音轨（备选方案）"""
    try:
        logger.info(f"使用Spleeter分离: {input_file}")
        
        # 安装: pip install spleeter
        from spleeter.separator import Separator
        
        separator = Separator('spleeter:2stems')
        separator.separate_to_file(input_file, output_dir)
        
        filename = Path(input_file).stem
        base_path = Path(output_dir) / filename
        
        return {
            'vocals': str(base_path / "vocals.wav"),
            'instrumental': str(base_path / "accompaniment.wav")
        }
    except Exception as e:
        logger.error(f"Spleeter分离失败: {str(e)}")
        raise


def separate_audio_simple_ffmpeg(input_file: str, output_dir: str) -> dict:
    """使用 ffmpeg 做简单的声道中间声道消除（center-channel cancellation），仅生成伴奏（instrumental）。
    这是一种轻量、近似的去人声方法，效果有限但快速。
    返回 dict，若只能生成伴奏则 `vocals` 为 None。
    """
    try:
        logger.info(f"尝试简单 ffmpeg 分离: {input_file}")
        # 尝试获取 imageio-ffmpeg 的 ffmpeg 二进制
        ffmpeg_exe = None
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg_exe = get_ffmpeg_exe()
            logger.info(f"使用 imageio-ffmpeg: {ffmpeg_exe}")
        except Exception as e:
            logger.warning(f"imageio-ffmpeg 获取失败: {e}")
            ffmpeg_exe = 'ffmpeg'  # fallback to system ffmpeg

        out_inst = str(Path(output_dir) / 'instrumental.mp3')

        # 中间声道消除（center channel cancellation）生成伴奏
        cmd = [
            ffmpeg_exe,
            '-y',
            '-i', input_file,
            '-af', 'pan=stereo|c0=0.5*FL-0.5*FR|c1=0.5*FR-0.5*FL',
            '-vn',
            '-acodec', 'libmp3lame',
            '-q:a', '3',
            out_inst
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise Exception(f"ffmpeg 处理失败: {result.stderr}")

        return {'vocals': None, 'instrumental': out_inst}
    except subprocess.TimeoutExpired:
        logger.error("简单 ffmpeg 分离超时")
        raise Exception("处理超时")
    except Exception as e:
        logger.error(f"简单 ffmpeg 分离失败: {str(e)}")
        raise

async def process_youtube_task(task_id: str, youtube_url: str):
    """后台任务：处理YouTube链接 (带缓存优化)"""
    try:
        # 检查缓存
        add_task_log(task_id, "Checking cache...")
        cached_result = check_cache(youtube_url)

        if cached_result:
            # 缓存命中!
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = '从缓存加载完成 (秒级响应)!'
            tasks[task_id]['title'] = cached_result.get('title', 'Cached Audio')
            tasks[task_id]['vocal_url'] = f"/download/{task_id}/vocals"
            tasks[task_id]['instrumental_url'] = f"/download/{task_id}/instrumental"
            tasks[task_id]['vocal_file'] = cached_result['vocals']
            tasks[task_id]['instrumental_file'] = cached_result['instrumental']
            add_task_log(task_id, "✓ Cache hit! Loaded instantly.")
            logger.info(f"任务完成 (缓存): {task_id}")
            return

        # 缓存未命中,开始处理
        add_task_log(task_id, "Cache miss. Starting fresh processing...")

        # 更新状态：下载中
        tasks[task_id]['status'] = 'downloading'
        tasks[task_id]['progress'] = 10
        tasks[task_id]['message'] = '正在从YouTube下载音频...'
        add_task_log(task_id, "Fetching YouTube metadata...")

        # 创建任务专属目录
        task_dir = WORK_DIR / task_id
        task_dir.mkdir(exist_ok=True)

        # 下载音频
        add_task_log(task_id, "Downloading audio track...")
        audio_file = download_youtube_audio(
            youtube_url,
            str(task_dir / "original")
        )
        add_task_log(task_id, "Download completed!")

        # 更新状态：分离中
        tasks[task_id]['status'] = 'separating'
        tasks[task_id]['progress'] = 40
        tasks[task_id]['message'] = '正在使用AI分离人声和伴奏...'
        add_task_log(task_id, "Booting AI Engine...")

        # 分离音轨
        try:
            # 优先使用Demucs
            add_task_log(task_id, "Running Demucs separation...")
            separated = separate_audio_demucs(audio_file, str(task_dir))
        except Exception as e:
            logger.warning(f"Demucs失败，尝试Spleeter: {str(e)}")
            add_task_log(task_id, "Demucs failed, trying Spleeter...")
            # 备用Spleeter
            try:
                separated = separate_audio_spleeter(audio_file, str(task_dir))
            except Exception as e2:
                logger.warning(f"Spleeter 也失败，尝试简单 ffmpeg 方案: {str(e2)}")
                add_task_log(task_id, "Spleeter failed, using simple ffmpeg method...")
                separated = separate_audio_simple_ffmpeg(audio_file, str(task_dir))

        add_task_log(task_id, "Separation completed!")

        # 保存到缓存
        title = Path(youtube_url).name[:50]
        if separated['vocals'] and separated['instrumental']:
            add_task_log(task_id, "Saving to cache for future use...")
            save_to_cache(youtube_url, separated['vocals'], separated['instrumental'], title)

        add_task_log(task_id, "TASK_COMPLETED")

        # 更新状态：完成
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['message'] = '处理完成！'
        tasks[task_id]['title'] = title
        tasks[task_id]['vocal_url'] = f"/download/{task_id}/vocals"
        tasks[task_id]['instrumental_url'] = f"/download/{task_id}/instrumental"
        tasks[task_id]['vocal_file'] = separated['vocals']
        tasks[task_id]['instrumental_file'] = separated['instrumental']

        # 添加到历史记录
        history[task_id] = {
            'title': tasks[task_id]['title'],
            'date': 'recent'
        }

        logger.info(f"任务完成: {task_id}")

    except Exception as e:
        logger.error(f"任务失败 {task_id}: {str(e)}")
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = f'处理失败: {str(e)}'
        add_task_log(task_id, f"ERROR: {str(e)}")


async def process_upload_task(task_id: str, input_file: str, filename: str):
    """后台任务：处理上传的音频文件"""
    try:
        tasks[task_id]['status'] = 'separating'
        tasks[task_id]['progress'] = 40
        tasks[task_id]['message'] = '正在使用AI分离人声和伴奏...'
        add_task_log(task_id, "Booting AI Engine...")

        # 分离音轨
        try:
            add_task_log(task_id, "Running Demucs separation...")
            separated = separate_audio_demucs(input_file, str(Path(input_file).parent))
        except Exception as e:
            logger.warning(f"Demucs失败，尝试Spleeter: {str(e)}")
            add_task_log(task_id, "Demucs failed, trying Spleeter...")
            try:
                separated = separate_audio_spleeter(input_file, str(Path(input_file).parent))
            except Exception as e2:
                logger.warning(f"Spleeter 也失败，尝试简单 ffmpeg 方案: {str(e2)}")
                add_task_log(task_id, "Spleeter failed, using simple ffmpeg method...")
                separated = separate_audio_simple_ffmpeg(input_file, str(Path(input_file).parent))

        add_task_log(task_id, "Separation completed!")
        add_task_log(task_id, "TASK_COMPLETED")

        # 更新状态：完成
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['message'] = '处理完成！'
        tasks[task_id]['title'] = Path(filename).stem[:50]
        tasks[task_id]['vocal_url'] = f"/download/{task_id}/vocals"
        tasks[task_id]['instrumental_url'] = f"/download/{task_id}/instrumental"
        tasks[task_id]['vocal_file'] = separated['vocals']
        tasks[task_id]['instrumental_file'] = separated['instrumental']

        # 添加到历史记录
        history[task_id] = {
            'title': tasks[task_id]['title'],
            'date': 'recent'
        }

        logger.info(f"上传任务完成: {task_id}")

    except Exception as e:
        logger.error(f"上传任务失败 {task_id}: {str(e)}")
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = f'处理失败: {str(e)}'
        add_task_log(task_id, f"ERROR: {str(e)}")

@app.post("/api/process", response_model=TaskStatus)
async def process_youtube(request: YouTubeRequest, background_tasks: BackgroundTasks):
    """提交YouTube链接进行处理"""

    # 验证URL
    if not request.url or 'youtube.com' not in request.url and 'youtu.be' not in request.url:
        raise HTTPException(status_code=400, detail="无效的YouTube链接")

    # 创建任务
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'progress': 0,
        'message': '任务已创建，等待处理...',
        'title': None,
        'vocal_url': None,
        'instrumental_url': None,
        'lyrics': None
    }

    # 初始化日志
    task_logs[task_id] = []

    # 添加到后台任务
    background_tasks.add_task(process_youtube_task, task_id, request.url)

    return tasks[task_id]

@app.post("/api/process_youtube", response_model=TaskStatus)
async def process_youtube_alias(request: YouTubeRequest, background_tasks: BackgroundTasks):
    """提交YouTube链接进行处理（前端兼容端点）"""
    return await process_youtube(request, background_tasks)


@app.post("/api/upload", response_model=TaskStatus)
async def upload_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """上传音频文件并开始分离处理（multipart/form-data）"""
    # 基本校验：文件类型或扩展
    allowed_ext = {'.mp3', '.wav', '.m4a', '.flac', '.ogg'}
    filename = file.filename or 'upload'
    ext = Path(filename).suffix.lower()
    if ext == '':
        # 尝试根据 content type
        if not (file.content_type and file.content_type.startswith('audio')):
            raise HTTPException(status_code=400, detail='只支持音频文件上传')
        ext = '.mp3'
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f'不支持的文件类型: {ext}')

    # 创建任务
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'progress': 0,
        'message': '任务已创建，等待处理...',
        'title': None,
        'vocal_url': None,
        'instrumental_url': None,
        'lyrics': None
    }

    # 初始化日志
    task_logs[task_id] = []

    task_dir = WORK_DIR / task_id
    task_dir.mkdir(exist_ok=True)

    save_path = task_dir / ('original' + ext)
    # 保存上传文件
    with open(save_path, 'wb') as out_f:
        content = await file.read()
        out_f.write(content)

    # 任务进入后台处理
    background_tasks.add_task(process_upload_task, task_id, str(save_path), filename)

    return tasks[task_id]

@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return tasks[task_id]

@app.get("/api/logs/{task_id}")
async def stream_logs(task_id: str):
    """Server-Sent Events 日志流"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        last_index = 0
        while True:
            # 获取新日志
            if task_id in task_logs:
                logs = task_logs[task_id]
                if len(logs) > last_index:
                    for log in logs[last_index:]:
                        yield f"data: {log}\n\n"
                    last_index = len(logs)

            # 检查任务是否完成
            if task_id in tasks and tasks[task_id]['status'] in ['completed', 'error']:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/history")
async def get_history():
    """获取历史记录"""
    return history

@app.delete("/api/history/{task_id}")
async def delete_history(task_id: str):
    """删除历史记录"""
    if task_id in history:
        del history[task_id]
    # 可选：删除相关文件
    task_dir = WORK_DIR / task_id
    if task_dir.exists():
        import shutil
        shutil.rmtree(task_dir, ignore_errors=True)
    return {"status": "deleted"}

@app.post("/api/stop/{task_id}")
async def stop_task(task_id: str):
    """停止任务（简单实现）"""
    if task_id in tasks:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = '任务已取消'
        add_task_log(task_id, "Task cancelled by user")
    return {"status": "stopped"}

@app.get("/download/{task_id}/{track_type}")
async def download_track(task_id: str, track_type: str):
    """下载分离后的音轨"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="任务未完成")

    # 获取文件路径
    if track_type == 'vocals':
        file_path = task.get('vocal_file')
        if not file_path:
            raise HTTPException(status_code=404, detail="人声文件未生成（可能使用了简单ffmpeg方案）")
        # 根据实际文件扩展名确定
        ext = Path(file_path).suffix
        filename = f'vocals{ext}'
        media_type = 'audio/wav' if ext == '.wav' else 'audio/mpeg'
    elif track_type == 'instrumental':
        file_path = task.get('instrumental_file')
        ext = Path(file_path).suffix if file_path else '.mp3'
        filename = f'instrumental{ext}'
        media_type = 'audio/wav' if ext == '.wav' else 'audio/mpeg'
    else:
        raise HTTPException(status_code=400, detail="无效的音轨类型")

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )

@app.get("/api/cache/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    if not CACHE_DIR.exists():
        return {"cached_items": 0, "total_size_mb": 0, "items": []}

    items = []
    total_size = 0

    for cache_path in CACHE_DIR.iterdir():
        if cache_path.is_dir():
            metadata_file = cache_path / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    # 计算目录大小
                    dir_size = sum(f.stat().st_size for f in cache_path.rglob('*') if f.is_file())
                    total_size += dir_size

                    items.append({
                        'cache_key': cache_path.name,
                        'title': metadata.get('title', 'Unknown'),
                        'url': metadata.get('url', ''),
                        'size_mb': round(dir_size / 1024 / 1024, 2),
                        'cached_at': metadata.get('cached_at', '')
                    })
                except Exception as e:
                    logger.error(f"读取缓存元数据失败: {e}")

    return {
        "cached_items": len(items),
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "items": items
    }

@app.delete("/api/cache/{cache_key}")
async def delete_cache_item(cache_key: str):
    """删除特定缓存项"""
    cache_path = CACHE_DIR / cache_key

    if not cache_path.exists():
        raise HTTPException(status_code=404, detail="缓存项不存在")

    try:
        shutil.rmtree(cache_path)
        logger.info(f"已删除缓存: {cache_key}")
        return {"status": "ok", "message": "缓存已删除"}
    except Exception as e:
        logger.error(f"删除缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@app.delete("/api/cache")
async def clear_all_cache():
    """清空所有缓存"""
    try:
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            CACHE_DIR.mkdir(exist_ok=True)
        logger.info("已清空所有缓存")
        return {"status": "ok", "message": "所有缓存已清空"}
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")

@app.get("/health")
async def health_check():
    """健康检查 (增强版)"""
    import shutil
    import platform

    # 跨平台检查命令是否存在
    system = platform.system()

    # 检查 demucs
    demucs_ok = shutil.which('demucs') is not None

    # 检查 ffmpeg
    ffmpeg_ok = shutil.which('ffmpeg') is not None

    # 如果系统没有 ffmpeg，尝试检测 imageio-ffmpeg 提供的内置二进制
    if not ffmpeg_ok:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ff_exe = get_ffmpeg_exe()
            ffmpeg_ok = Path(ff_exe).exists()
        except Exception:
            pass

    # 检测 GPU 支持
    has_gpu, device = detect_gpu_support()

    # 统计缓存
    cache_count = len(list(CACHE_DIR.iterdir())) if CACHE_DIR.exists() else 0

    return {
        "status": "ok",
        "platform": system,
        "demucs_available": demucs_ok,
        "ffmpeg_available": ffmpeg_ok,
        "gpu_available": has_gpu,
        "device": device,
        "cache_enabled": True,
        "cached_items": cache_count,
        "optimization_level": "high" if has_gpu else "standard"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
