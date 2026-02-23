#!/usr/bin/env python3
"""
卡拉OK系统测试脚本
用于验证系统是否正常运行
"""

import requests
import time
import sys

API_BASE = "http://localhost:8000"

def test_health():
    """测试后端健康状态"""
    print("🔍 测试1: 后端健康检查...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 后端运行正常")
            print(f"   - Demucs可用: {data.get('demucs_available', False)}")
            print(f"   - FFmpeg可用: {data.get('ffmpeg_available', False)}")
            return True
        else:
            print(f"   ❌ 后端响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 无法连接到后端 ({API_BASE})")
        print(f"   请确保后端已启动: python3 karaoke_backend.py")
        return False
    except Exception as e:
        print(f"   ❌ 错误: {str(e)}")
        return False

def test_youtube_processing():
    """测试YouTube处理（使用短视频）"""
    print("\n🔍 测试2: YouTube处理功能...")
    
    # 使用一个很短的测试视频
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # YouTube官方测试视频
    
    print(f"   提交测试任务...")
    try:
        response = requests.post(
            f"{API_BASE}/api/process",
            json={"url": test_url},
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"   ❌ 提交失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
        
        data = response.json()
        task_id = data['task_id']
        print(f"   ✅ 任务已创建: {task_id}")
        
        # 轮询任务状态（最多等待5分钟）
        print(f"   等待处理完成（这可能需要几分钟）...")
        max_wait = 300  # 5分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = requests.get(f"{API_BASE}/api/status/{task_id}")
            status_data = status_response.json()
            
            status = status_data['status']
            progress = status_data['progress']
            message = status_data['message']
            
            print(f"   进度: {progress}% - {message}")
            
            if status == 'completed':
                print(f"   ✅ 处理完成！")
                print(f"   - 人声音轨: {status_data['vocal_url']}")
                print(f"   - 伴奏音轨: {status_data['instrumental_url']}")
                return True
            elif status == 'error':
                print(f"   ❌ 处理失败: {message}")
                return False
            
            time.sleep(5)  # 每5秒查询一次
        
        print(f"   ⚠️  处理超时（超过{max_wait}秒）")
        return False
        
    except Exception as e:
        print(f"   ❌ 错误: {str(e)}")
        return False

def main():
    print("🎤 卡拉OK系统测试")
    print("=" * 50)
    
    # 测试1: 健康检查
    if not test_health():
        print("\n❌ 基础测试失败，请检查后端是否正常启动")
        sys.exit(1)
    
    # 询问是否进行完整测试
    print("\n" + "=" * 50)
    answer = input("是否进行完整的YouTube处理测试？(这需要几分钟) [y/N]: ")
    
    if answer.lower() == 'y':
        if test_youtube_processing():
            print("\n✅ 所有测试通过！系统运行正常")
        else:
            print("\n⚠️  YouTube处理测试失败")
            print("可能原因:")
            print("1. 网络问题（无法访问YouTube）")
            print("2. Demucs未正确安装")
            print("3. 内存不足")
    else:
        print("\n✅ 基础测试通过！")
    
    print("\n" + "=" * 50)
    print("💡 提示:")
    print("- 前端访问: 在浏览器中打开前端应用")
    print("- API文档: http://localhost:8000/docs")
    print("- 健康检查: http://localhost:8000/health")

if __name__ == "__main__":
    main()
