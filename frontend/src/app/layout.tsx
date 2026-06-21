import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'VibeChat — 情绪社交',
  description: '基于 AI 情绪识别的匿名社交平台',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
