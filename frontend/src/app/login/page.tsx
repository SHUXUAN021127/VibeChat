'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { registerAccount, loginAccount, googleLoginUrl } from '@/lib/api'

export default function LoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!email || !password || loading) return
    setError('')
    setLoading(true)
    try {
      const result = mode === 'login'
        ? await loginAccount(email, password)
        : await registerAccount(email, password)
      localStorage.setItem('vibe_account_token', result.token)
      localStorage.setItem('vibe_account', JSON.stringify({
        account_id: result.account_id,
        email: result.email,
        display_name: result.display_name,
        provider: result.provider,
      }))
      router.push('/')
    } catch (e: any) {
      setError(e.message || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  const handleGuest = () => {
    localStorage.removeItem('vibe_account_token')
    localStorage.removeItem('vibe_account')
    router.push('/')
  }

  const thirdPartyBtn = (label: string, emoji: string, onClick: () => void, note?: string) => (
    <button
      onClick={onClick}
      className="w-full py-3 rounded-xl text-sm font-medium bg-white/5 hover:bg-white/10 text-white/70 transition-colors flex items-center justify-center gap-2"
    >
      <span>{emoji}</span> {label}
      {note && <span className="text-white/25 text-xs">{note}</span>}
    </button>
  )

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/3 w-96 h-96 rounded-full opacity-10 blur-3xl"
          style={{ background: 'radial-gradient(circle, #a78bfa, transparent)' }} />
      </div>

      <div className="w-full max-w-sm relative z-10">
        <div className="text-center mb-8">
          <div className="text-4xl mb-3">🫧</div>
          <h1 className="text-2xl font-bold gradient-text">VibeChat</h1>
          <p className="text-white/40 text-sm mt-1">登录后可保存你的情绪轨迹</p>
        </div>

        <div className="glass rounded-2xl p-6">
          {/* 登录/注册切换 */}
          <div className="flex bg-white/5 rounded-xl p-1 mb-5">
            <button onClick={() => { setMode('login'); setError('') }}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${mode === 'login' ? 'bg-white/10 text-white' : 'text-white/40'}`}>
              登录
            </button>
            <button onClick={() => { setMode('register'); setError('') }}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${mode === 'register' ? 'bg-white/10 text-white' : 'text-white/40'}`}>
              注册
            </button>
          </div>

          <input
            type="email" placeholder="邮箱" value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full bg-white/5 rounded-xl px-4 py-3 text-sm text-white placeholder-white/25 border border-white/10 focus:border-white/30 transition-colors mb-3"
          />
          <input
            type="password" placeholder={mode === 'register' ? '密码（至少6位）' : '密码'} value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            className="w-full bg-white/5 rounded-xl px-4 py-3 text-sm text-white placeholder-white/25 border border-white/10 focus:border-white/30 transition-colors mb-3"
          />

          {error && <div className="mb-3 p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-xs">{error}</div>}

          <button
            onClick={handleSubmit} disabled={loading}
            className="w-full py-3 rounded-xl text-sm font-medium text-white bg-gradient-to-r from-violet-500 to-blue-500 hover:from-violet-400 hover:to-blue-400 transition-all disabled:opacity-50 mb-4"
          >
            {loading ? '处理中…' : mode === 'login' ? '登录' : '创建账号'}
          </button>

          {/* 第三方 */}
          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-white/30 text-xs">或</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <div className="space-y-2.5">
            {thirdPartyBtn('使用 Google 登录', '🔵', () => { window.location.href = googleLoginUrl() })}
            {thirdPartyBtn('使用微信登录', '💚', () => alert('微信登录需企业认证，演示环境暂未接入，接口已预留'), '')}
            {thirdPartyBtn('使用手机号登录', '📱', () => alert('手机号登录需短信服务，演示环境暂未接入，接口已预留'), '')}
          </div>
        </div>

        {/* 游客入口 */}
        <button
          onClick={handleGuest}
          className="w-full text-center text-white/40 hover:text-white/70 text-sm mt-5 transition-colors"
        >
          以游客身份继续 →
        </button>
        <p className="text-center text-white/25 text-xs mt-3">
          无论哪种方式，聊天全程匿名
        </p>
      </div>
    </main>
  )
}
