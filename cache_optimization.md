# 缓存优化方案

## 实现 YouTube URL 缓存

```python
import hashlib
from pathlib import Path

def get_cache_key(youtube_url: str) -> str:
    """生成 YouTube URL 的缓存键"""
    return hashlib.md5(youtube_url.encode()).hexdigest()

def check_cache(url: str) -> Optional[dict]:
    """检查是否已处理过"""
    cache_key = get_cache_key(url)
    cache_dir = WORK_DIR / "cache" / cache_key
    
    if cache_dir.exists():
        vocal_file = cache_dir / "vocals.wav"
        instrumental_file = cache_dir / "no_vocals.wav"
        
        if vocal_file.exists() and instrumental_file.exists():
            return {
                'vocals': str(vocal_file),
                'instrumental': str(instrumental_file)
            }
    return None

# 在 process_youtube_task 中使用
cached = check_cache(youtube_url)
if cached:
    tasks[task_id]['status'] = 'completed'
    tasks[task_id]['vocal_file'] = cached['vocals']
    tasks[task_id]['instrumental_file'] = cached['instrumental']
    return
```

## 预期效果
- 重复请求响应时间从 3-5 分钟降至 < 1 秒
- 减少 95% 的 CPU/GPU 使用
- 节省带宽和存储
