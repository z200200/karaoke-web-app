"""
卡拉OK音轨处理后端服务
功能：YouTube下载 + AI音轨分离
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import yt_dlp
import os
import uuid
import subprocess
from pathlib import Path
import logging

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

# 任务状态存储
tasks = {}

class YouTubeRequest(BaseModel):
    url: str

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, downloading, separating, completed, error
    progress: int
    message: str
    vocal_url: Optional[str] = None
    instrumental_url: Optional[str] = None

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

def separate_audio_demucs(input_file: str, output_dir: str) -> dict:
    """使用Demucs分离音轨"""
    try:
        logger.info(f"开始分离音轨: {input_file}")
        
        # 使用Demucs命令行工具
        # 安装: pip install demucs
        cmd = [
            'demucs',
            '--two-stems=vocals',  # 只分离人声和伴奏
            '-o', output_dir,
            input_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            raise Exception(f"Demucs分离失败: {result.stderr}")
        
        # Demucs输出结构: output_dir/htdemucs/filename/vocals.mp3 和 no_vocals.mp3
        filename = Path(input_file).stem
        base_path = Path(output_dir) / "htdemucs" / filename
        
        return {
            'vocals': str(base_path / "vocals.mp3"),
            'instrumental': str(base_path / "no_vocals.mp3")
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
    """后台任务：处理YouTube链接"""
    try:
        # 更新状态：下载中
        tasks[task_id]['status'] = 'downloading'
        tasks[task_id]['progress'] = 10
        tasks[task_id]['message'] = '正在从YouTube下载音频...'
        
        # 创建任务专属目录
        task_dir = WORK_DIR / task_id
        task_dir.mkdir(exist_ok=True)
        
        # 下载音频
        audio_file = download_youtube_audio(
            youtube_url,
            str(task_dir / "original")
        )
        
        # 更新状态：分离中
        tasks[task_id]['status'] = 'separating'
        tasks[task_id]['progress'] = 40
        tasks[task_id]['message'] = '正在使用AI分离人声和伴奏...'
        
        # 分离音轨
        try:
            # 优先使用Demucs
            separated = separate_audio_demucs(audio_file, str(task_dir))
        except Exception as e:
            logger.warning(f"Demucs失败，尝试Spleeter: {str(e)}")
            # 备用Spleeter
            try:
                separated = separate_audio_spleeter(audio_file, str(task_dir))
            except Exception as e2:
                logger.warning(f"Spleeter 也失败，尝试简单 ffmpeg 方案: {str(e2)}")
                separated = separate_audio_simple_ffmpeg(audio_file, str(task_dir))
        
        # 更新状态：完成
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['message'] = '处理完成！'
        tasks[task_id]['vocal_url'] = f"/download/{task_id}/vocals"
        tasks[task_id]['instrumental_url'] = f"/download/{task_id}/instrumental"
        tasks[task_id]['vocal_file'] = separated['vocals']
        tasks[task_id]['instrumental_file'] = separated['instrumental']
        
        logger.info(f"任务完成: {task_id}")
        
    except Exception as e:
        logger.error(f"任务失败 {task_id}: {str(e)}")
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = f'处理失败: {str(e)}'


async def process_upload_task(task_id: str, input_file: str):
    """后台任务：处理上传的音频文件"""
    try:
        tasks[task_id]['status'] = 'separating'
        tasks[task_id]['progress'] = 40
        tasks[task_id]['message'] = '正在使用AI分离人声和伴奏...'

        # 分离音轨
        try:
            separated = separate_audio_demucs(input_file, str(Path(input_file).parent))
        except Exception as e:
            logger.warning(f"Demucs失败，尝试Spleeter: {str(e)}")
            try:
                separated = separate_audio_spleeter(input_file, str(Path(input_file).parent))
            except Exception as e2:
                logger.warning(f"Spleeter 也失败，尝试简单 ffmpeg 方案: {str(e2)}")
                separated = separate_audio_simple_ffmpeg(input_file, str(Path(input_file).parent))

        # 更新状态：完成
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['message'] = '处理完成！'
        tasks[task_id]['vocal_url'] = f"/download/{task_id}/vocals"
        tasks[task_id]['instrumental_url'] = f"/download/{task_id}/instrumental"
        tasks[task_id]['vocal_file'] = separated['vocals']
        tasks[task_id]['instrumental_file'] = separated['instrumental']

        logger.info(f"上传任务完成: {task_id}")

    except Exception as e:
        logger.error(f"上传任务失败 {task_id}: {str(e)}")
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = f'处理失败: {str(e)}'

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
        'vocal_url': None,
        'instrumental_url': None
    }
    
    # 添加到后台任务
    background_tasks.add_task(process_youtube_task, task_id, request.url)
    
    return tasks[task_id]


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
        'vocal_url': None,
        'instrumental_url': None
    }

    task_dir = WORK_DIR / task_id
    task_dir.mkdir(exist_ok=True)

    save_path = task_dir / ('original' + ext)
    # 保存上传文件
    with open(save_path, 'wb') as out_f:
        content = await file.read()
        out_f.write(content)

    # 任务进入后台处理
    background_tasks.add_task(process_upload_task, task_id, str(save_path))

    return tasks[task_id]

@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return tasks[task_id]

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
        filename = 'vocals.mp3'
    elif track_type == 'instrumental':
        file_path = task.get('instrumental_file')
        filename = 'instrumental.mp3'
    else:
        raise HTTPException(status_code=400, detail="无效的音轨类型")
    
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        file_path,
        media_type='audio/mpeg',
        filename=filename
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    # 首先通过系统 `which` 检查
    demucs_ok = subprocess.run(['which', 'demucs'], capture_output=True).returncode == 0
    ffmpeg_ok = subprocess.run(['which', 'ffmpeg'], capture_output=True).returncode == 0

    # 如果系统没有 ffmpeg，尝试检测 imageio-ffmpeg 提供的内置二进制
    if not ffmpeg_ok:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ff_exe = get_ffmpeg_exe()
            ffmpeg_ok = Path(ff_exe).exists()
        except Exception:
            # 忽略任何导入或检测错误，保留 ffmpeg_ok 的当前状态
            pass

    return {
        "status": "ok",
        "demucs_available": demucs_ok,
        "ffmpeg_available": ffmpeg_ok
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
