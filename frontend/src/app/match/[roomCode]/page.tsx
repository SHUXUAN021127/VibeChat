'use client'
import { useEffect, useState, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { getMatchStatus, getConfirmStatus, submitConfirmChoice, EmotionResult } from '@/lib/api'

const CRISIS_RESOURCES = '如果你正处于困难时刻，请联系心理援助热线：北京 010-82951332 / 全国 400-161-9995'

export default function MatchPage() {
  const router = useRouter()
  const params = useParams()
  const rawParam = params.roomCode as string
  // pending-xxx 表示互补模式待确认；否则是普通等待房间
  const isPending = rawParam?.startsWith('pending-')
  const pairId = isPending ? rawParam.replace('pending-', '') : ''
  const roomCode = rawParam

  const [emotion, setEmotion] = useState<EmotionResult | null>(null)
  const [status, setStatus] = useState<'waiting' | 'matched' | 'solo'>('waiting')
  const [countdown, setCountdown] = useState(30)
  const [dots, setDots] = useState('.')
  const pollingRef = useRef<NodeJS.Timeout>()
  const countdownRef = useRef<NodeJS.Timeout>()

  // 互补确认相关
  const [confirmState, setConfirmState] = useState<'choosing' | 'waiting_other' | 'rejected'>('choosing')
  const [confirmSeconds, setConfirmSeconds] = useState(10)
  const [otherEmotion, setOtherEmotion] = useState<{ label: string; color: string; summary: string } | null>(null)
  const confirmPollRef = useRef<NodeJS.Timeout>()
  const confirmCountRef = useRef<NodeJS.Timeout>()

  useEffect(() => {
    const raw = localStorage.getItem('vibe_emotion')
    if (!raw) { router.push('/'); return }
    const data: EmotionResult = JSON.parse(raw)
    setEmotion(data)

    // 互补确认模式：走单独的确认流程
    if (isPending) {
      // 初始拉一次对方情绪
      const pollConfirm = async () => {
        try {
          const s = await getConfirmStatus(pairId, data.user_id)
          if (s.state === 'waiting_choice') {
            setOtherEmotion({
              label: s.other_emotion_label,
              color: s.other_emotion_color,
              summary: s.other_emotion_summary,
            })
            // 我已选了同意，但对方还没选 → 等待对方
            if (s.my_choice === true) setConfirmState('waiting_other')
          } else if (s.state === 'confirmed') {
            clearInterval(confirmPollRef.current)
            clearInterval(confirmCountRef.current)
            router.push(`/chat/${s.room_code}`)
          } else if (s.state === 'rejected') {
            clearInterval(confirmPollRef.current)
            clearInterval(confirmCountRef.current)
            setConfirmState('rejected')
            // 1.5 秒后回到原等待房间继续匹配
            setTimeout(() => {
              if (s.room_code) router.push(`/match/${s.room_code}`)
              else router.push('/')
            }, 1800)
          } else if (s.state === 'not_found') {
            clearInterval(confirmPollRef.current)
            clearInterval(confirmCountRef.current)
            router.push('/')
          }
        } catch {}
      }
      pollConfirm()
      confirmPollRef.current = setInterval(pollConfirm, 1500)

      // 10 秒确认倒计时
      confirmCountRef.current = setInterval(() => {
        setConfirmSeconds(c => {
          if (c <= 1) { clearInterval(confirmCountRef.current); return 0 }
          return c - 1
        })
      }, 1000)

      return () => {
        clearInterval(confirmPollRef.current)
        clearInterval(confirmCountRef.current)
      }
    }

    // ===== 以下是普通等待匹配流程 =====
    // 如果已经直接匹配成功（active 状态），直接进入
    if (data.match_status === 'active') {
      setStatus('matched')
      setTimeout(() => router.push(`/chat/${roomCode}`), 1500)
      return
    }

    // 轮询匹配状态
    const poll = async () => {
      try {
        const s = await getMatchStatus(roomCode, data.user_id)
        if (s.status === 'active') {
          clearInterval(pollingRef.current)
          clearInterval(countdownRef.current)
          setStatus('matched')
          setTimeout(() => router.push(`/chat/${roomCode}`), 1500)
        }
        if (s.timed_out) {
          clearInterval(pollingRef.current)
          clearInterval(countdownRef.current)
          setStatus('matched')
          setTimeout(() => router.push(`/chat/${roomCode}`), 1500)
        }
      } catch {}
    }

    pollingRef.current = setInterval(poll, 2000)

    // 倒计时
    countdownRef.current = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { clearInterval(countdownRef.current); return 0 }
        return c - 1
      })
    }, 1000)

    // 省略号动效
    const dotInterval = setInterval(() => {
      setDots(d => d.length >= 3 ? '.' : d + '.')
    }, 500)

    return () => {
      clearInterval(pollingRef.current)
      clearInterval(countdownRef.current)
      clearInterval(dotInterval)
    }
  }, [roomCode, router, isPending, pairId])

  // 用户点击同意/拒绝
  const handleConfirmChoice = async (agree: boolean) => {
    if (!emotion) return
    try {
      const s = await submitConfirmChoice(pairId, emotion.user_id, agree)
      if (!agree) {
        setConfirmState('rejected')
        clearInterval(confirmPollRef.current)
        clearInterval(confirmCountRef.current)
        setTimeout(() => router.push('/'), 1500)
        return
      }
      // 同意后等待对方
      if (s.state === 'confirmed') {
        router.push(`/chat/${s.room_code}`)
      } else {
        setConfirmState('waiting_other')
      }
    } catch {}
  }

  if (!emotion) return null

  const color = emotion.emotion_color || '#6366f1'

  // ===== 互补确认界面 =====
  if (isPending) {
    const otherColor = otherEmotion?.color || '#a78bfa'
    return (
      <main className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 opacity-5"
            style={{ background: `radial-gradient(ellipse at center, ${otherColor}, transparent 70%)` }} />
        </div>

        <div className="w-full max-w-md relative z-10 text-center">
          {confirmState === 'rejected' ? (
            <div className="glass rounded-3xl p-8">
              <div className="text-4xl mb-4">🍃</div>
              <h2 className="text-lg font-bold text-white/90 mb-2">这次没有相遇</h2>
              <p className="text-white/50 text-sm">正在为你回到匹配队列…</p>
            </div>
          ) : (
            <div className="glass rounded-3xl p-8">
              {/* 双情绪对撞可视化 */}
              <div className="flex items-center justify-center gap-3 mb-6">
                <div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl"
                  style={{ background: `${color}22`, border: `2px solid ${color}66` }}>
                  {emotion.emotion_label?.[0]}
                </div>
                <div className="text-white/30 text-xl">✦</div>
                <div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl animate-pulse-slow"
                  style={{ background: `${otherColor}22`, border: `2px solid ${otherColor}66` }}>
                  {otherEmotion?.label?.[0] || '?'}
                </div>
              </div>

              <h2 className="text-lg font-bold gradient-text mb-2">找到了和你情绪互补的人</h2>
              <p className="text-white/60 text-sm mb-1">
                你此刻 <span style={{ color }}>{emotion.emotion_label}</span>
                ，对方此刻 <span style={{ color: otherColor }}>{otherEmotion?.label || '…'}</span>
              </p>
              {otherEmotion?.summary && (
                <p className="text-white/40 text-xs leading-relaxed mt-3 mb-2">
                  「{otherEmotion.summary}」
                </p>
              )}

              {confirmState === 'choosing' ? (
                <>
                  <p className="text-white/50 text-sm mb-5 mt-4">要和 ta 聊聊吗？</p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleConfirmChoice(false)}
                      className="flex-1 py-3 rounded-xl text-sm font-medium bg-white/5 hover:bg-white/10 text-white/60 transition-colors"
                    >
                      这次算了
                    </button>
                    <button
                      onClick={() => handleConfirmChoice(true)}
                      className="flex-1 py-3 rounded-xl text-sm font-medium text-white transition-all"
                      style={{ background: `linear-gradient(135deg, ${color}, ${otherColor})` }}
                    >
                      好，聊聊 ({confirmSeconds}s)
                    </button>
                  </div>
                </>
              ) : (
                <div className="mt-5">
                  <div className="flex items-center justify-center gap-1 mb-2">
                    <span className="w-2 h-2 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <p className="text-white/50 text-sm">你已同意，正在等待对方确认…</p>
                  <p className="text-white/30 text-xs mt-1">{confirmSeconds}s</p>
                </div>
              )}
            </div>
          )}

          <p className="text-center text-white/25 text-xs mt-6">
            互补匹配 · 双方都同意才会开始对话
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden">
      {/* 动态背景 */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute inset-0 opacity-5"
          style={{ background: `radial-gradient(ellipse at center, ${color}, transparent 70%)` }}
        />
      </div>

      <div className="w-full max-w-md relative z-10 text-center">

        {/* 情绪可视化卡片 */}
        <div className="glass rounded-3xl p-8 mb-6">
          {/* 情绪光环 - 升级版 */}
          <div className="relative flex items-center justify-center mb-6" style={{ height: '140px' }}>
            {/* 外层呼吸光晕 */}
            <div
              className="absolute w-36 h-36 rounded-full animate-breathe"
              style={{ background: `radial-gradient(circle, ${color}55, transparent 70%)`, filter: 'blur(12px)' }}
            />
            {/* 扩散波纹 */}
            <div className="absolute w-28 h-28 rounded-full opacity-30 animate-ripple" style={{ border: `2px solid ${color}` }} />
            <div className="absolute w-28 h-28 rounded-full opacity-20 animate-ripple" style={{ border: `1px solid ${color}`, animationDelay: '0.75s' }} />

            {/* 轨道光点 */}
            {[0, 1, 2].map(i => (
              <div key={i} className="absolute" style={{
                width: '8px', height: '8px',
                ['--orbit-r' as any]: `${48 + i * 8}px`,
                ['--orbit-speed' as any]: `${6 + i * 2}s`,
              }}>
                <div className="animate-orbit" style={{
                  ['--orbit-r' as any]: `${48 + i * 8}px`,
                  ['--orbit-speed' as any]: `${6 + i * 2}s`,
                }}>
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
                </div>
              </div>
            ))}

            {/* 中心核心 */}
            <div
              className="relative w-20 h-20 rounded-full flex items-center justify-center text-3xl animate-breathe"
              style={{ background: `${color}22`, border: `2px solid ${color}88`, boxShadow: `0 0 24px ${color}66` }}
            >
              {status === 'matched' ? '✨' : status === 'solo' ? '🌙' : '🫧'}
            </div>
          </div>

          {/* 情绪标签 */}
          <div
            className="inline-block px-4 py-1.5 rounded-full text-sm font-medium mb-4"
            style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
          >
            {emotion.emotion_label}
          </div>

          {/* 情绪解读 */}
          <p className="text-white/70 text-sm leading-relaxed mb-4">
            {emotion.emotion_summary}
          </p>

          {/* 情绪关键词 */}
          {emotion.emotion_keywords?.length > 0 && (
            <div className="flex flex-wrap justify-center gap-2 mb-4">
              {emotion.emotion_keywords.map((kw, i) => (
                <span key={i} className="text-xs px-2 py-1 rounded-full bg-white/5 text-white/40">
                  {kw}
                </span>
              ))}
            </div>
          )}

          {/* 多维度情绪：次要情绪占比 */}
          {emotion.secondary_emotions?.length > 0 && (
            <div className="mb-4 text-left">
              <div className="text-xs text-white/30 mb-2 text-center">你的情绪里还藏着</div>
              <div className="space-y-1.5">
                {emotion.secondary_emotions.map((se, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs text-white/50 w-12 flex-shrink-0">{se.label}</span>
                    <div className="flex-1 h-1.5 bg-white/8 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${Math.round(se.weight * 100)}%`, background: `${color}99` }} />
                    </div>
                    <span className="text-xs text-white/30 w-8 text-right">{Math.round(se.weight * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 情绪强度条 */}
          <div className="mt-4">
            <div className="flex justify-between text-xs text-white/30 mb-1">
              <span>情绪强度</span>
              <span>{Math.round(emotion.emotion_score * 100)}%</span>
            </div>
            <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{ width: `${emotion.emotion_score * 100}%`, background: color }}
              />
            </div>
          </div>
        </div>

        {/* 匹配状态 */}
        {status === 'waiting' && (
          <div className="glass rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-white/60 text-sm">正在寻找同频的人{dots}</span>
              <span className="text-white/30 text-xs">{countdown}s</span>
            </div>
            <div className="h-1 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{
                  width: `${((30 - countdown) / 30) * 100}%`,
                  background: `linear-gradient(to right, ${color}, #60a5fa)`
                }}
              />
            </div>
            <p className="text-white/30 text-xs mt-3">
              系统正在寻找情绪相近的陌生人，最多等待 30 秒
            </p>
          </div>
        )}

        {status === 'matched' && (
          <div className="glass rounded-2xl p-5 border border-green-500/20">
            <div className="text-green-400 text-sm font-medium mb-1">✨ 找到同频的人了！</div>
            <p className="text-white/50 text-xs">正在进入对话…</p>
          </div>
        )}

        {status === 'solo' && (
          <div className="glass rounded-2xl p-5">
            <div className="text-white/70 text-sm font-medium mb-1">🌙 暂时没有找到匹配</div>
            <p className="text-white/40 text-xs">已为你开启独立空间，进入后可以自由表达</p>
          </div>
        )}

        {/* 危机提示 */}
        {emotion.is_crisis && (
          <div className="mt-4 p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-left">
            <p className="text-red-300 text-xs font-medium mb-1">💙 我们注意到你可能正经历困难时刻</p>
            <p className="text-red-300/70 text-xs">{CRISIS_RESOURCES}</p>
          </div>
        )}
      </div>
    </main>
  )
}
