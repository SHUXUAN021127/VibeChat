'use client'
import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { analyzeEmotion, saveEmotionHistory } from '@/lib/api'

const PLACEHOLDER_TEXTS = [
  '今天有点累，但说不清楚为什么……',
  '感觉很兴奋，有件事想和人分享',
  '心里有些事压着，需要说出来',
  '最近有点迷茫，不知道自己在做什么',
  '刚经历了一件很开心的事！',
]

export default function HomePage() {
  const router = useRouter()
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [placeholder] = useState(() =>
    PLACEHOLDER_TEXTS[Math.floor(Math.random() * PLACEHOLDER_TEXTS.length)]
  )
  const [chatMode, setChatMode] = useState<'one_on_one' | 'group'>('one_on_one')
  const [account, setAccount] = useState<any>(null)

  useEffect(() => {
    const acc = localStorage.getItem('vibe_account')
    if (acc) try { setAccount(JSON.parse(acc)) } catch {}
  }, [])

  const handleSubmit = async () => {
    if (!text.trim() || loading) return
    setError('')
    setLoading(true)
    try {
      const sessionToken = localStorage.getItem('vibe_token') || undefined
      const result = await analyzeEmotion(text, sessionToken, chatMode)
      // 保存用户信息
      localStorage.setItem('vibe_token', result.session_token)
      localStorage.setItem('vibe_user', JSON.stringify({
        user_id: result.user_id,
        anonymous_name: result.anonymous_name,
        anonymous_avatar: result.anonymous_avatar,
      }))
      // 保存情绪结果，传递给下一页
      localStorage.setItem('vibe_emotion', JSON.stringify(result))
      localStorage.setItem('vibe_last_text', text)
      // 保存到历史轨迹
      saveEmotionHistory(result, text)
      // 多人房：直接进聊天室；1对1：走匹配流程
      if (chatMode === 'group') {
        router.push(`/chat/${result.match_room_code}`)
      } else if (result.match_status === 'pending' && result.pair_id) {
        router.push(`/match/pending-${result.pair_id}`)
      } else {
        router.push(`/match/${result.match_room_code}`)
      }
    } catch (e: any) {
      setError(e.message || '出了点问题，请稍后再试')
    } finally {
      setLoading(false)
    }
  }

  const charCount = text.length
  const maxChars = 500

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden">
      {/* 背景光效 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full opacity-10 blur-3xl"
          style={{ background: 'radial-gradient(circle, #a78bfa, transparent)' }} />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full opacity-10 blur-3xl"
          style={{ background: 'radial-gradient(circle, #60a5fa, transparent)' }} />
      </div>

      <div className="w-full max-w-lg relative z-10">
        {/* 账号入口 */}
        <div className="flex justify-end mb-2">
          {account ? (
            <button
              onClick={() => router.push('/profile')}
              className="flex items-center gap-2 text-white/50 hover:text-white/80 text-sm transition-colors"
            >
              <span className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 flex items-center justify-center text-xs font-bold text-white">
                {(account.display_name || account.email || 'U')[0].toUpperCase()}
              </span>
              我的
            </button>
          ) : (
            <button
              onClick={() => router.push('/login')}
              className="text-white/40 hover:text-white/70 text-sm transition-colors"
            >
              登录 / 注册
            </button>
          )}
        </div>

        {/* Logo */}
        <div className="text-center mb-10">
          <div className="text-5xl mb-4">🫧</div>
          <h1 className="text-3xl font-bold gradient-text mb-2">VibeChat</h1>
          <p className="text-white/50 text-sm">先被理解，再去连接</p>
        </div>

        {/* 输入卡片 */}
        <div className="glass rounded-2xl p-6">
          {/* 模式选择 */}
          <div className="flex bg-white/5 rounded-xl p-1 mb-4">
            <button
              onClick={() => setChatMode('one_on_one')}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                chatMode === 'one_on_one' ? 'bg-white/10 text-white' : 'text-white/40'
              }`}
            >
              💬 一对一
            </button>
            <button
              onClick={() => setChatMode('group')}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                chatMode === 'group' ? 'bg-white/10 text-white' : 'text-white/40'
              }`}
            >
              👥 情绪房间
            </button>
          </div>

          <label className="block text-white/70 text-sm mb-3 font-medium">
            现在的你，感觉怎么样？
          </label>
          <textarea
            value={text}
            onChange={e => setText(e.target.value.slice(0, maxChars))}
            placeholder={placeholder}
            rows={5}
            className="w-full bg-white/5 rounded-xl p-4 text-white placeholder-white/25
              resize-none text-sm leading-relaxed border border-white/10
              focus:border-white/30 transition-colors"
            onKeyDown={e => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit()
            }}
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-white/30 text-xs">{charCount}/{maxChars}</span>
            <span className="text-white/25 text-xs">⌘ + Enter 发送</span>
          </div>

          {error && (
            <div className="mt-3 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm">
              ⚠️ {error}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={!text.trim() || loading}
            className="mt-4 w-full py-3 rounded-xl font-medium text-sm transition-all duration-300
              disabled:opacity-40 disabled:cursor-not-allowed
              bg-gradient-to-r from-violet-500 to-blue-500 hover:from-violet-400 hover:to-blue-400
              text-white shadow-lg hover:shadow-violet-500/25"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                AI 正在感受你的情绪…
              </span>
            ) : chatMode === 'group' ? '加入情绪房间' : '感知情绪，寻找同频'}
          </button>
        </div>

        {/* 底部说明 */}
        <p className="text-center text-white/25 text-xs mt-6">
          完全匿名 · 不需要注册 · 情绪相近的人会被匹配在一起
        </p>

        {/* 情绪轨迹入口 */}
        <div className="text-center mt-4">
          <button
            onClick={() => router.push('/history')}
            className="text-white/40 hover:text-white/70 text-xs transition-colors underline underline-offset-2"
          >
            📈 查看我的情绪轨迹
          </button>
        </div>
      </div>
    </main>
  )
}
