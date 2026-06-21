'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getHistoryEmotions, getHistorySessions, getSessionMessages } from '@/lib/api'

export default function ProfilePage() {
  const router = useRouter()
  const [account, setAccount] = useState<any>(null)
  const [tab, setTab] = useState<'emotions' | 'sessions'>('emotions')
  const [emotions, setEmotions] = useState<any[]>([])
  const [sessions, setSessions] = useState<any[]>([])
  const [openSession, setOpenSession] = useState<number | null>(null)
  const [sessionMsgs, setSessionMsgs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('vibe_account_token')
    const acc = localStorage.getItem('vibe_account')
    if (!token || !acc) { router.push('/login'); return }
    setAccount(JSON.parse(acc))

    Promise.all([
      getHistoryEmotions(token).catch(() => []),
      getHistorySessions(token).catch(() => []),
    ]).then(([em, ses]) => {
      setEmotions(em)
      setSessions(ses)
      setLoading(false)
    })
  }, [router])

  const openSessionMessages = async (matchId: number) => {
    if (openSession === matchId) { setOpenSession(null); return }
    const token = localStorage.getItem('vibe_account_token')!
    const msgs = await getSessionMessages(matchId, token).catch(() => [])
    setSessionMsgs(msgs)
    setOpenSession(matchId)
  }

  const handleLogout = () => {
    localStorage.removeItem('vibe_account_token')
    localStorage.removeItem('vibe_account')
    router.push('/login')
  }

  const fmt = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('zh-CN', {
        year: 'numeric', month: 'numeric', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch { return '' }
  }

  return (
    <main className="min-h-screen px-4 py-8 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full opacity-5 blur-3xl"
          style={{ background: 'radial-gradient(circle, #a78bfa, transparent)' }} />
      </div>

      <div className="w-full max-w-lg mx-auto relative z-10">
        {/* 顶部 */}
        <div className="flex items-center justify-between mb-6">
          <button onClick={() => router.push('/')} className="text-white/50 hover:text-white/80 text-sm transition-colors">← 返回</button>
          <h1 className="text-lg font-bold gradient-text">我的</h1>
          <button onClick={handleLogout} className="text-white/30 hover:text-red-400 text-xs transition-colors">退出登录</button>
        </div>

        {/* 账号卡片 */}
        {account && (
          <div className="glass rounded-2xl p-5 mb-5 flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center text-lg font-bold">
              {(account.display_name || account.email || 'U')[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white/90 font-medium text-sm truncate">{account.display_name || '用户'}</div>
              <div className="text-white/40 text-xs truncate">{account.email || account.provider}</div>
            </div>
            <span className="text-xs text-white/30 bg-white/5 px-2 py-1 rounded-full">
              {account.provider === 'google' ? 'Google' : account.provider === 'email' ? '邮箱' : account.provider}
            </span>
          </div>
        )}

        {/* Tab */}
        <div className="flex bg-white/5 rounded-xl p-1 mb-5">
          <button onClick={() => setTab('emotions')}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${tab === 'emotions' ? 'bg-white/10 text-white' : 'text-white/40'}`}>
            🎨 情绪卡片
          </button>
          <button onClick={() => setTab('sessions')}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${tab === 'sessions' ? 'bg-white/10 text-white' : 'text-white/40'}`}>
            💬 聊天记录
          </button>
        </div>

        {loading ? (
          <div className="text-center py-16 text-white/30 text-sm">加载中…</div>
        ) : tab === 'emotions' ? (
          emotions.length === 0 ? (
            <div className="text-center py-16 text-white/30">
              <div className="text-3xl mb-2">🫧</div>
              <p className="text-sm">还没有情绪记录</p>
            </div>
          ) : (
            <div className="space-y-3">
              {emotions.map(e => (
                <div key={e.id} className="glass rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs px-2.5 py-1 rounded-full font-medium"
                      style={{ background: `${e.emotion_color}22`, color: e.emotion_color, border: `1px solid ${e.emotion_color}44` }}>
                      {e.emotion_label}
                    </span>
                    <span className="text-white/30 text-xs">{fmt(e.created_at)}</span>
                  </div>
                  <p className="text-white/60 text-sm mb-2 line-clamp-2">"{e.input_text}"</p>
                  <p className="text-white/40 text-xs leading-relaxed">{e.emotion_summary}</p>
                </div>
              ))}
            </div>
          )
        ) : (
          sessions.length === 0 ? (
            <div className="text-center py-16 text-white/30">
              <div className="text-3xl mb-2">💬</div>
              <p className="text-sm">还没有聊天记录</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sessions.map(s => (
                <div key={s.match_id} className="glass rounded-xl overflow-hidden">
                  <button
                    onClick={() => openSessionMessages(s.match_id)}
                    className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xs px-2.5 py-1 rounded-full font-medium flex-shrink-0"
                        style={{ background: `${s.emotion_color}22`, color: s.emotion_color }}>
                        {s.emotion_label}
                      </span>
                      <span className="text-white/40 text-xs">{s.message_count} 条消息</span>
                      <span className="text-white/30 text-xs">{s.room_type === 'group' ? '群聊' : '一对一'}</span>
                    </div>
                    <span className="text-white/30 text-xs flex-shrink-0 ml-2">{fmt(s.created_at)}</span>
                  </button>

                  {openSession === s.match_id && (
                    <div className="px-4 pb-4 space-y-2 border-t border-white/5 pt-3">
                      {sessionMsgs.length === 0 ? (
                        <p className="text-white/30 text-xs text-center py-2">无消息</p>
                      ) : sessionMsgs.map((m, i) => (
                        <div key={i} className="flex gap-2 items-start">
                          <span className="text-base flex-shrink-0">{m.anonymous_avatar}</span>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-white/50 text-xs font-medium">{m.anonymous_name}</span>
                              <span className="text-white/25 text-xs">{fmt(m.created_at)}</span>
                            </div>
                            <p className="text-white/70 text-sm break-words">{m.content}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        )}

        <p className="text-center text-white/20 text-xs mt-8">
          聊天记录中只显示匿名身份，不会暴露真实账号
        </p>
      </div>
    </main>
  )
}
