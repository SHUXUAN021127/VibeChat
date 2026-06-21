'use client'
import { Suspense, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { getMyAccount } from '@/lib/api'

function CallbackInner() {
  const router = useRouter()
  const params = useSearchParams()

  useEffect(() => {
    const token = params.get('token')
    if (!token) { router.push('/login'); return }
    localStorage.setItem('vibe_account_token', token)
    getMyAccount(token).then(acc => {
      if (acc) {
        localStorage.setItem('vibe_account', JSON.stringify(acc))
      }
      router.push('/')
    }).catch(() => router.push('/'))
  }, [params, router])

  return (
    <div className="text-center">
      <div className="text-4xl mb-3 animate-pulse">🫧</div>
      <p className="text-white/50 text-sm">登录中…</p>
    </div>
  )
}

export default function AuthCallback() {
  return (
    <main className="min-h-screen flex items-center justify-center">
      <Suspense fallback={
        <div className="text-center">
          <div className="text-4xl mb-3 animate-pulse">🫧</div>
          <p className="text-white/50 text-sm">加载中…</p>
        </div>
      }>
        <CallbackInner />
      </Suspense>
    </main>
  )
}
