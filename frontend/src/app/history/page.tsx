'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getEmotionHistory, clearEmotionHistory, EmotionHistoryItem } from '@/lib/api'

export default function HistoryPage() {
  const router = useRouter()
  const [history, setHistory] = useState<EmotionHistoryItem[]>([])

  useEffect(() => {
    setHistory(getEmotionHistory())
  }, [])

  const handleClear = () => {
    if (confirm('确定要清空所有情绪记录吗？此操作无法撤销。')) {
      clearEmotionHistory()
      setHistory([])
    }
  }

  const formatDate = (ts: string) => {
    try {
      const d = new Date(ts)
      return d.toLocaleString('zh-CN', {
        month: 'numeric', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch { return '' }
  }

  // 计算情绪走向（正负向平均）
  const avgValence = history.length
    ? history.reduce((s, h) => s + h.emotion_valence, 0) / history.length
    : 0

  return (
    <main className="min-h-screen px-4 py-8 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full opacity-5 blur-3xl"
          style={{ background: 'radial-gradient(circle, #a78bfa, transparent)' }} />
      </div>

      <div className="w-full max-w-lg mx-auto relative z-10">
        {/* 顶部 */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={() => router.push('/')}
            className="text-white/50 hover:text-white/80 text-sm transition-colors"
          >
            ← 返回
          </button>
          <h1 className="text-lg font-bold gradient-text">情绪轨迹</h1>
          {history.length > 0 ? (
            <button onClick={handleClear} className="text-white/30 hover:text-red-400 text-xs transition-colors">
              清空
            </button>
          ) : <span className="w-8" />}
        </div>

        {history.length === 0 ? (
          <div className="text-center py-20 text-white/30">
            <div className="text-4xl mb-3">🫧</div>
            <p className="text-sm">还没有情绪记录</p>
            <button
              onClick={() => router.push('/')}
              className="mt-4 text-violet-400 hover:text-violet-300 text-sm underline underline-offset-2"
            >
              去记录第一段心情
            </button>
          </div>
        ) : (
          <>
            {/* 情绪概览 */}
            <div className="glass rounded-2xl p-5 mb-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-white/40 text-xs mb-1">共记录</div>
                  <div className="text-2xl font-bold text-white/90">{history.length} <span className="text-sm font-normal text-white/40">次</span></div>
                </div>
                <div className="text-right">
                  <div className="text-white/40 text-xs mb-1">整体情绪</div>
                  <div className="text-sm font-medium" style={{ color: avgValence >= 0 ? '#6ee7b7' : '#a78bfa' }}>
                    {avgValence >= 0.2 ? '😊 偏积极' : avgValence <= -0.2 ? '🌧 偏低落' : '😌 平稳'}
                  </div>
                </div>
              </div>

              {/* 情绪正负向走势条 */}
              <div className="mt-4 flex items-end gap-1 h-12">
                {history.slice(0, 15).reverse().map((h, i) => {
                  const height = 20 + Math.abs(h.emotion_valence) * 30
                  return (
                    <div
                      key={i}
                      className="flex-1 rounded-t transition-all"
                      style={{
                        height: `${height}px`,
                        background: h.emotion_color,
                        opacity: 0.7,
                      }}
                      title={`${h.emotion_label} · ${formatDate(h.timestamp)}`}
                    />
                  )
                })}
              </div>
              <div className="text-white/25 text-xs mt-2 text-center">最近 15 次情绪强度走势</div>
            </div>

            {/* 历史列表 */}
            <div className="space-y-3">
              {history.map((h, i) => (
                <div key={i} className="glass rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className="text-xs px-2.5 py-1 rounded-full font-medium"
                      style={{ background: `${h.emotion_color}22`, color: h.emotion_color, border: `1px solid ${h.emotion_color}44` }}
                    >
                      {h.emotion_label}
                    </span>
                    <span className="text-white/30 text-xs">{formatDate(h.timestamp)}</span>
                  </div>
                  <p className="text-white/60 text-sm mb-2 line-clamp-2">"{h.text}"</p>
                  <p className="text-white/40 text-xs leading-relaxed">{h.emotion_summary}</p>
                </div>
              ))}
            </div>
          </>
        )}

        <p className="text-center text-white/20 text-xs mt-8">
          情绪记录仅保存在你本地浏览器，不会上传服务器
        </p>
      </div>
    </main>
  )
}
