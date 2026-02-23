import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, SkipBack, SkipForward, Mic, Music, Volume2, VolumeX, Upload, Loader, CheckCircle, AlertCircle } from 'lucide-react';

export default function KaraokeApp() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [vocalVolume, setVocalVolume] = useState(50);
  const [musicVolume, setMusicVolume] = useState(80);
  const [vocalFile, setVocalFile] = useState(null);
  const [musicFile, setMusicFile] = useState(null);
  const [audioReady, setAudioReady] = useState(false);
  
  // YouTube处理相关状态
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [processing, setProcessing] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
  
  const vocalAudioRef = useRef(null);
  const musicAudioRef = useRef(null);
  const audioContextRef = useRef(null);
  const vocalGainRef = useRef(null);
  const musicGainRef = useRef(null);
  const pollingIntervalRef = useRef(null);

  // 后端API地址
  const API_BASE = 'http://localhost:8000';

  // 初始化Web Audio API
  useEffect(() => {
    if (!audioContextRef.current) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContext();
      
      vocalGainRef.current = audioContextRef.current.createGain();
      musicGainRef.current = audioContextRef.current.createGain();
      
      vocalGainRef.current.connect(audioContextRef.current.destination);
      musicGainRef.current.connect(audioContextRef.current.destination);
    }
  }, []);

  // 处理YouTube链接
  const handleYoutubeProcess = async () => {
    if (!youtubeUrl) {
      alert('请输入YouTube链接');
      return;
    }

    try {
      setProcessing(true);
      setTaskStatus(null);

      // 提交处理任务
      const response = await fetch(`${API_BASE}/api/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: youtubeUrl })
      });

      if (!response.ok) {
        throw new Error('提交任务失败');
      }

      const data = await response.json();
      setTaskId(data.task_id);
      setTaskStatus(data);

      // 开始轮询任务状态
      startPolling(data.task_id);

    } catch (error) {
      alert(`处理失败: ${error.message}`);
      setProcessing(false);
    }
  };

  // 轮询任务状态
  const startPolling = (id) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    pollingIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/api/status/${id}`);
        const data = await response.json();
        setTaskStatus(data);

        if (data.status === 'completed') {
          clearInterval(pollingIntervalRef.current);
          setProcessing(false);
          
          // 自动加载音频文件
          await loadAudioFromBackend(id);
        } else if (data.status === 'error') {
          clearInterval(pollingIntervalRef.current);
          setProcessing(false);
          alert(`处理失败: ${data.message}`);
        }
      } catch (error) {
        console.error('轮询失败:', error);
      }
    }, 2000); // 每2秒查询一次
  };

  // 从后端加载音频
  const loadAudioFromBackend = async (id) => {
    try {
      const vocalUrl = `${API_BASE}/download/${id}/vocals`;
      const instrumentalUrl = `${API_BASE}/download/${id}/instrumental`;

      setVocalFile(vocalUrl);
      setMusicFile(instrumentalUrl);

      if (vocalAudioRef.current) {
        vocalAudioRef.current.src = vocalUrl;
      }
      if (musicAudioRef.current) {
        musicAudioRef.current.src = instrumentalUrl;
      }
    } catch (error) {
      console.error('加载音频失败:', error);
      alert('加载音频失败');
    }
  };

  // 手动上传文件
  const handleVocalUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setVocalFile(url);
      if (vocalAudioRef.current) {
        vocalAudioRef.current.src = url;
      }
    }
  };

  const handleMusicUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setMusicFile(url);
      if (musicAudioRef.current) {
        musicAudioRef.current.src = url;
      }
    }
  };

  const handleAudioLoaded = () => {
    if (vocalAudioRef.current && musicAudioRef.current) {
      if (vocalAudioRef.current.readyState >= 2 && musicAudioRef.current.readyState >= 2) {
        setDuration(Math.max(vocalAudioRef.current.duration, musicAudioRef.current.duration));
        setAudioReady(true);
      }
    }
  };

  // 更新音量
  useEffect(() => {
    if (vocalAudioRef.current) {
      vocalAudioRef.current.volume = vocalVolume / 100;
    }
  }, [vocalVolume]);

  useEffect(() => {
    if (musicAudioRef.current) {
      musicAudioRef.current.volume = musicVolume / 100;
    }
  }, [musicVolume]);

  // 更新播放时间
  useEffect(() => {
    const updateTime = () => {
      if (vocalAudioRef.current && !vocalAudioRef.current.paused) {
        setCurrentTime(vocalAudioRef.current.currentTime);
      }
    };

    if (isPlaying) {
      const interval = setInterval(updateTime, 100);
      return () => clearInterval(interval);
    }
  }, [isPlaying]);

  const togglePlayPause = async () => {
    if (!vocalAudioRef.current || !musicAudioRef.current || !audioReady) {
      alert('请先上传或处理音频文件');
      return;
    }

    if (audioContextRef.current.state === 'suspended') {
      await audioContextRef.current.resume();
    }

    if (isPlaying) {
      vocalAudioRef.current.pause();
      musicAudioRef.current.pause();
      setIsPlaying(false);
    } else {
      try {
        await vocalAudioRef.current.play();
        await musicAudioRef.current.play();
        setIsPlaying(true);
      } catch (err) {
        console.error('播放错误:', err);
        alert('播放失败，请检查音频文件');
      }
    }
  };

  const handleSeek = (e) => {
    if (!audioReady) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const newTime = percentage * duration;
    
    if (vocalAudioRef.current) vocalAudioRef.current.currentTime = newTime;
    if (musicAudioRef.current) musicAudioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleMuteAll = () => { setVocalVolume(0); setMusicVolume(0); };
  const handleInstrumentalOnly = () => { setVocalVolume(0); setMusicVolume(80); };
  const handleLearnMode = () => { setVocalVolume(80); setMusicVolume(40); };
  const handleResetVolume = () => { setVocalVolume(50); setMusicVolume(80); };

  // 获取进度条颜色
  const getProgressColor = () => {
    if (!taskStatus) return 'bg-slate-700';
    if (taskStatus.status === 'error') return 'bg-red-500';
    if (taskStatus.status === 'completed') return 'bg-green-500';
    return 'bg-blue-500';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Hidden Audio Elements */}
        <audio ref={vocalAudioRef} onLoadedMetadata={handleAudioLoaded} onEnded={() => setIsPlaying(false)} />
        <audio ref={musicAudioRef} onLoadedMetadata={handleAudioLoaded} />

        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-6xl font-bold mb-3 bg-gradient-to-r from-pink-400 via-purple-400 to-blue-400 text-transparent bg-clip-text" style={{ fontFamily: 'Georgia, serif' }}>
            🎤 Karaoke Studio Pro
          </h1>
          <p className="text-slate-400 text-lg">一键式 AI 音轨分离 · YouTube 直接处理</p>
        </div>

        {/* YouTube One-Click Processing */}
        <div className="bg-gradient-to-r from-red-500/10 to-pink-500/10 backdrop-blur rounded-2xl p-6 mb-6 border-2 border-red-500/30">
          <h3 className="text-xl font-semibold text-red-300 mb-4 flex items-center gap-2">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
            </svg>
            🚀 一键处理 YouTube 歌曲
          </h3>
          
          <div className="space-y-4">
            <div>
              <input
                type="text"
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                placeholder="粘贴 YouTube 链接 (https://www.youtube.com/watch?v=...)"
                disabled={processing}
                className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-xl text-slate-100 placeholder-slate-500 focus:border-red-500 focus:outline-none disabled:opacity-50"
              />
            </div>

            <button
              onClick={handleYoutubeProcess}
              disabled={!youtubeUrl || processing}
              className={`w-full py-4 rounded-xl font-semibold transition-all flex items-center justify-center gap-3 ${
                youtubeUrl && !processing
                  ? 'bg-gradient-to-r from-red-500 to-pink-500 hover:from-red-600 hover:to-pink-600 text-white transform hover:scale-105'
                  : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }`}
            >
              {processing ? (
                <>
                  <Loader className="animate-spin" size={24} />
                  处理中...
                </>
              ) : (
                <>
                  ⚡ 一键处理（下载 + AI分离）
                </>
              )}
            </button>

            {/* 处理进度 */}
            {taskStatus && (
              <div className="bg-slate-800/70 rounded-xl p-5 border border-slate-700">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {taskStatus.status === 'completed' ? (
                      <CheckCircle className="text-green-400" size={24} />
                    ) : taskStatus.status === 'error' ? (
                      <AlertCircle className="text-red-400" size={24} />
                    ) : (
                      <Loader className="text-blue-400 animate-spin" size={24} />
                    )}
                    <div>
                      <p className="font-semibold text-slate-100">{taskStatus.message}</p>
                      <p className="text-sm text-slate-400">进度: {taskStatus.progress}%</p>
                    </div>
                  </div>
                </div>
                
                {/* 进度条 */}
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 ${getProgressColor()}`}
                    style={{ width: `${taskStatus.progress}%` }}
                  />
                </div>

                {taskStatus.status === 'completed' && (
                  <div className="mt-4 text-center text-green-400 text-sm">
                    ✓ 音频已自动加载，可以开始播放！
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Manual Upload Section */}
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-6 mb-6 border-2 border-slate-700">
          <h3 className="text-xl font-semibold text-purple-300 mb-4 flex items-center gap-2">
            <Upload size={24} />
            或手动上传已分离的音频
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Vocal Upload */}
            <div className={`relative p-6 rounded-xl border-2 border-dashed transition-all ${
              vocalFile ? 'border-pink-500 bg-pink-500/10' : 'border-slate-600 hover:border-slate-500'
            }`}>
              <input type="file" accept="audio/*" onChange={handleVocalUpload} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
              <div className="text-center pointer-events-none">
                <Mic className={`mx-auto mb-3 ${vocalFile ? 'text-pink-400' : 'text-slate-500'}`} size={40} />
                <p className="font-semibold text-slate-100 mb-1">原唱音轨</p>
                <p className="text-sm text-slate-400">{vocalFile ? '✓ 已上传' : '点击上传 MP3/WAV'}</p>
              </div>
            </div>

            {/* Music Upload */}
            <div className={`relative p-6 rounded-xl border-2 border-dashed transition-all ${
              musicFile ? 'border-blue-500 bg-blue-500/10' : 'border-slate-600 hover:border-slate-500'
            }`}>
              <input type="file" accept="audio/*" onChange={handleMusicUpload} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
              <div className="text-center pointer-events-none">
                <Music className={`mx-auto mb-3 ${musicFile ? 'text-blue-400' : 'text-slate-500'}`} size={40} />
                <p className="font-semibold text-slate-100 mb-1">伴奏音轨</p>
                <p className="text-sm text-slate-400">{musicFile ? '✓ 已上传' : '点击上传 MP3/WAV'}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Player Section */}
        <div className="bg-gradient-to-br from-slate-800/70 to-purple-900/30 backdrop-blur rounded-3xl p-8 mb-6 border-2 border-purple-500/30 shadow-2xl shadow-purple-500/20">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-slate-100 mb-2">卡拉OK播放器</h2>
            {audioReady && (
              <div className="mt-3 inline-block px-4 py-2 rounded-full bg-green-500/20 border border-green-500/30">
                <span className="text-green-400 text-sm font-medium">● 音频就绪</span>
              </div>
            )}
          </div>

          {/* Waveform */}
          <div className="min-h-[120px] flex items-center justify-center mb-8 bg-slate-900/50 rounded-xl border border-slate-700">
            {isPlaying ? (
              <div className="flex items-center gap-2">
                {[...Array(20)].map((_, i) => (
                  <div key={i} className="w-2 bg-gradient-to-t from-purple-500 to-pink-500 rounded-full animate-pulse"
                    style={{ height: `${20 + Math.random() * 60}px`, animationDelay: `${i * 0.1}s` }} />
                ))}
              </div>
            ) : (
              <div className="text-center text-slate-500">
                <Music size={48} className="mx-auto mb-2 opacity-30" />
                <p>{audioReady ? '按播放键开始' : '等待音频加载'}</p>
              </div>
            )}
          </div>

          {/* Progress Bar */}
          <div className="mb-6">
            <div className="h-2 bg-slate-700 rounded-full cursor-pointer overflow-hidden" onClick={handleSeek}>
              <div className="h-full bg-gradient-to-r from-blue-400 to-purple-400 transition-all" style={{ width: `${(currentTime / duration) * 100}%` }} />
            </div>
            <div className="flex justify-between text-sm text-slate-400 mt-2">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* Playback Controls */}
          <div className="flex items-center justify-center gap-4 mb-8">
            <button className="p-3 rounded-full bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors">
              <SkipBack size={24} />
            </button>
            <button onClick={togglePlayPause} className="p-6 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white transition-all transform hover:scale-105 shadow-lg">
              {isPlaying ? <Pause size={32} /> : <Play size={32} className="ml-1" />}
            </button>
            <button className="p-3 rounded-full bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors">
              <SkipForward size={24} />
            </button>
          </div>

          {/* Volume Controls */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-slate-800/50 rounded-2xl p-5 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-pink-500/20"><Mic className="text-pink-400" size={24} /></div>
                  <div>
                    <h4 className="font-semibold text-slate-100">原唱音量</h4>
                    <p className="text-sm text-slate-400">Vocal Track</p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-pink-400">{vocalVolume}%</span>
              </div>
              <input type="range" min="0" max="100" value={vocalVolume} onChange={(e) => setVocalVolume(Number(e.target.value))}
                className="w-full h-3 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                style={{ background: `linear-gradient(to right, #ec4899 0%, #ec4899 ${vocalVolume}%, #334155 ${vocalVolume}%, #334155 100%)` }} />
            </div>

            <div className="bg-slate-800/50 rounded-2xl p-5 border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-500/20"><Music className="text-blue-400" size={24} /></div>
                  <div>
                    <h4 className="font-semibold text-slate-100">背景音乐</h4>
                    <p className="text-sm text-slate-400">Music Track</p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-blue-400">{musicVolume}%</span>
              </div>
              <input type="range" min="0" max="100" value={musicVolume} onChange={(e) => setMusicVolume(Number(e.target.value))}
                className="w-full h-3 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                style={{ background: `linear-gradient(to right, #3b82f6 0%, #3b82f6 ${musicVolume}%, #334155 ${musicVolume}%, #334155 100%)` }} />
            </div>
          </div>
        </div>

        {/* Quick Controls */}
        <div className="bg-slate-800/50 backdrop-blur rounded-2xl p-5 border-2 border-slate-700">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <button onClick={handleMuteAll} className="p-4 rounded-xl bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-300 transition-all hover:scale-105">
              <VolumeX className="mx-auto mb-2" size={24} />
              <p className="text-sm font-medium">全部静音</p>
            </button>
            <button onClick={handleInstrumentalOnly} className="p-4 rounded-xl bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-300 transition-all hover:scale-105">
              <Music className="mx-auto mb-2" size={24} />
              <p className="text-sm font-medium">只听伴奏</p>
            </button>
            <button onClick={handleLearnMode} className="p-4 rounded-xl bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-300 transition-all hover:scale-105">
              <Mic className="mx-auto mb-2" size={24} />
              <p className="text-sm font-medium">学唱模式</p>
            </button>
            <button onClick={handleResetVolume} className="p-4 rounded-xl bg-slate-700/50 hover:bg-slate-700 border border-slate-600 text-slate-300 transition-all hover:scale-105">
              <Volume2 className="mx-auto mb-2" size={24} />
              <p className="text-sm font-medium">重置音量</p>
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        input[type="range"]::-webkit-slider-thumb {
          appearance: none;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: white;
          cursor: pointer;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        input[type="range"]::-moz-range-thumb {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: white;
          cursor: pointer;
          border: none;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
      `}</style>
    </div>
  );
}
