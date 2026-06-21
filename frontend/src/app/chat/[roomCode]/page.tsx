'use client'
import { useEffect, useState, useRef, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { createChatWebSocket, getRoomInfo, EmotionResult, ChatMessage, RoomInfo } from '@/lib/api'

const EMOJIS = [
  '😊', '😂', '🥹', '😭', '😮‍💨', '😴', '🤔', '😌',
  '🥰', '😔', '😅', '😢', '🫠', '😤', '🙃', '😶‍🌫️',
  '❤️', '🩵', '💔', '✨', '🌙', '🫂', '👍', '🙏',
  '🔥', '🌈', '☕', '🍃', '💭', '🎵', '🌧', '⭐',
]

export default function ChatPage() {
  const router = useRouter()
  const params = useParams()
  const roomCode = params.roomCode as string

  const [emotion, setEmotion] = useState<EmotionResult | null>(null)
  const [room, setRoom] = useState<RoomInfo | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [connected, setConnected] = useState(false)
  const [myName, setMyName] = useState('')
  const [myAvatar, setMyAvatar] = useState('')
  const [userId, setUserId] = useState<number>(0)
  const [showEmoji, setShowEmoji] = useState(false)
  const [typingUser, setTypingUser] = useState<{ name: string; avatar: string } | null>(null)
  const [idleWarning, setIdleWarning] = useState<'none' | 'quiet' | 'closing'>('none')
  const [roomClosed, setRoomClosed] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [peerLeft, setPeerLeft] = useState(false)
  const [peerLeftReason, setPeerLeftReason] = useState<'left' | 'kicked'>('left')
  const [isGroupRoom, setIsGroupRoom] = useState(false)
  const [warning, setWarning] = useState<string>('')
  const [kicked, setKicked] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const typingTimerRef = useRef<NodeJS.Timeout>()
  const lastTypingSentRef = useRef<number>(0)
  const idleTimersRef = useRef<NodeJS.Timeout[]>([])

  useEffect(() => {
    const emotionRaw = localStorage.getItem('vibe_emotion')
    const userRaw = localStorage.getItem('vibe_user')
    const token = localStorage.getItem('vibe_token')

    if (!emotionRaw || !userRaw || !token) { router.push('/'); return }

    const em: EmotionResult = JSON.parse(emotionRaw)
    const user = JSON.parse(userRaw)
    setEmotion(em)
    setMyName(user.anonymous_name)
    setMyAvatar(user.anonymous_avatar)
    setUserId(user.user_id)

    // 加载历史消息
    getRoomInfo(roomCode, user.user_id).then(info => {
      setRoom(info)
      setIsGroupRoom(info.room_type === 'group')
      // 将历史消息转为 ChatMessage 格式
      const hist: ChatMessage[] = info.messages.map((m: any) => ({
        ...m,
        type: 'message',
        timestamp: m.created_at || m.timestamp,
      }))
      setMessages(hist)
      // 若破冰语还没生成（对方刚来），稍后再拉一次
      if (!info.opening_line && info.room_type === 'one_on_one') {
        setTimeout(() => {
          getRoomInfo(roomCode, user.user_id).then(info2 => setRoom(info2)).catch(() => {})
        }, 3000)
      }
    }).catch(() => {})

    // 建立 WebSocket
    const ws = createChatWebSocket(roomCode, user.user_id, token)
    wsRef.current = ws

    ws.onopen = () => { setConnected(true); resetIdleTimer() }
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = (e) => {
      const data: any = JSON.parse(e.data)
      if (data.type === 'typing') {
        // 显示对方正在输入，2.5秒后自动消失
        setTypingUser({ name: data.anonymous_name, avatar: data.anonymous_avatar })
        if (typingTimerRef.current) clearTimeout(typingTimerRef.current)
        typingTimerRef.current = setTimeout(() => setTypingUser(null), 2500)
        return
      }
      if (data.type === 'room_dismissed') {
        // 对方退出/被踢，房间解散
        idleTimersRef.current.forEach(t => clearTimeout(t))
        setPeerLeftReason(data.reason === 'peer_kicked' ? 'kicked' : 'left')
        setPeerLeft(true)
        return
      }
      if (data.type === 'warning') {
        // 违规警告，消息未发送
        setWarning(data.content)
        setTimeout(() => setWarning(''), 5000)
        return
      }
      if (data.type === 'kicked') {
        // 被踢出，自动返回首页
        idleTimersRef.current.forEach(t => clearTimeout(t))
        setKicked(true)
        setTimeout(() => router.push('/'), 3000)
        return
      }
      // 收到真实消息时，清除"正在输入"并重置闲置计时
      if (data.type === 'message') {
        setTypingUser(null)
        resetIdleTimer()
      }
      setMessages(prev => [...prev, data])
    }

    return () => {
      ws.close()
      idleTimersRef.current.forEach(t => clearTimeout(t))
    }
  }, [roomCode, router])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = () => {
    const content = input.trim()
    if (!content || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify({ type: 'message', content }))
    setInput('')
    setShowEmoji(false)
    resetIdleTimer()
  }

  // 通知对方"正在输入"（节流：最多每1.5秒发一次）
  const notifyTyping = () => {
    const now = Date.now()
    if (now - lastTypingSentRef.current > 1500) {
      lastTypingSentRef.current = now
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'typing' }))
      }
    }
  }

  const insertEmoji = (emoji: string) => {
    setInput(prev => (prev + emoji).slice(0, 1000))
  }

  // 重置闲置计时器：30秒安静提示 / 1分50秒即将关闭 / 2分钟关闭
  const resetIdleTimer = () => {
    idleTimersRef.current.forEach(t => clearTimeout(t))
    idleTimersRef.current = []
    setIdleWarning('none')

    const t1 = setTimeout(() => setIdleWarning('quiet'), 30 * 1000)
    const t2 = setTimeout(() => setIdleWarning('closing'), 110 * 1000)
    const t3 = setTimeout(() => {
      setRoomClosed(true)
      wsRef.current?.close()
    }, 120 * 1000)
    idleTimersRef.current = [t1, t2, t3]
  }

  // 点返回：群聊直接走，1对1 先确认
  const handleBackClick = () => {
    if (isGroupRoom) {
      router.push('/')
    } else {
      setShowExitConfirm(true)
    }
  }

  // 确认退出：通知后端解散房间
  const confirmExit = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'leave_room' }))
    }
    idleTimersRef.current.forEach(t => clearTimeout(t))
    router.push('/')
  }

  // 对方退出后，B 选择重新匹配（复用已有情绪，不重新调用 LLM，更快）
  const handleRematch = async () => {
    const emotionRaw = localStorage.getItem('vibe_emotion')
    if (!emotionRaw) { router.push('/'); return }
    try {
      const { rematch } = await import('@/lib/api')
      const em = JSON.parse(emotionRaw)
      const token = localStorage.getItem('vibe_token')
      const result = await rematch(em.emotion_record_id, token!)
      localStorage.setItem('vibe_emotion', JSON.stringify(result))
      if (result.match_status === 'pending' && result.pair_id) {
        router.push(`/match/pending-${result.pair_id}`)
      } else {
        router.push(`/match/${result.match_room_code}`)
      }
    } catch {
      router.push('/')
    }
  }

  const color = emotion?.emotion_color || '#6366f1'

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    } catch { return '' }
  }

  return (
    <div className="h-screen flex flex-col" style={{ background: '#0a0a0f' }}>
      {/* 退出确认弹窗 */}
      {showExitConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="glass rounded-3xl p-7 max-w-sm w-full text-center">
            <div className="text-3xl mb-3">👋</div>
            <h2 className="text-base font-bold text-white/90 mb-2">确定退出对话吗？</h2>
            <p className="text-white/50 text-sm mb-6">
              这是一对一对话，退出后房间将解散，对方也会离开。
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowExitConfirm(false)}
                className="flex-1 py-3 rounded-xl text-sm font-medium bg-white/5 hover:bg-white/10 text-white/60 transition-colors"
              >
                取消
              </button>
              <button
                onClick={confirmExit}
                className="flex-1 py-3 rounded-xl text-sm font-medium bg-white/10 hover:bg-red-500/20 text-white/80 hover:text-red-300 transition-colors"
              >
                确定退出
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 对方退出弹窗 */}
      {peerLeft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="glass rounded-3xl p-8 max-w-sm w-full text-center">
            <div className="text-4xl mb-4">{peerLeftReason === 'kicked' ? '🚫' : '🍃'}</div>
            <h2 className="text-lg font-bold text-white/90 mb-2">
              {peerLeftReason === 'kicked' ? '对方已离开对话' : '对方退出了聊天'}
            </h2>
            <p className="text-white/50 text-sm mb-6">
              {peerLeftReason === 'kicked'
                ? '对方因不当言论被移出了对话。要再遇见一个同频的人吗？'
                : '这段对话结束了。要再遇见一个同频的人吗？'}
            </p>
            <div className="flex flex-col gap-2.5">
              <button
                onClick={handleRematch}
                className="w-full py-3 rounded-xl text-sm font-medium text-white bg-gradient-to-r from-violet-500 to-blue-500 hover:from-violet-400 hover:to-blue-400 transition-all"
              >
                重新匹配
              </button>
              <button
                onClick={() => router.push('/')}
                className="w-full py-3 rounded-xl text-sm font-medium bg-white/5 hover:bg-white/10 text-white/60 transition-colors"
              >
                回到首页
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 被踢出遮罩 */}
      {kicked && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="glass rounded-3xl p-8 max-w-sm w-full text-center">
            <div className="text-4xl mb-4">🚫</div>
            <h2 className="text-lg font-bold text-white/90 mb-2">你已被移出对话</h2>
            <p className="text-white/50 text-sm mb-6">
              因多次发送不当内容，你已被移出此对话。请文明友善地与他人交流。即将自动返回首页…
            </p>
            <button
              onClick={() => router.push('/')}
              className="w-full py-3 rounded-xl text-sm font-medium text-white bg-gradient-to-r from-violet-500 to-blue-500"
            >
              回到首页
            </button>
          </div>
        </div>
      )}

      {/* 房间关闭遮罩 */}
      {roomClosed && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="glass rounded-3xl p-8 max-w-sm text-center">
            <div className="text-4xl mb-4">🌙</div>
            <h2 className="text-lg font-bold text-white/90 mb-2">对话已结束</h2>
            <p className="text-white/50 text-sm mb-6">
              这个房间因长时间无人发言而关闭了。<br />感谢这段安静的陪伴。
            </p>
            <button
              onClick={() => router.push('/')}
              className="w-full py-3 rounded-xl text-sm font-medium text-white bg-gradient-to-r from-violet-500 to-blue-500"
            >
              回到首页，重新开始
            </button>
          </div>
        </div>
      )}

      {/* 顶部栏 */}
      <header className="glass border-b border-white/5 px-4 py-3 flex items-center gap-3">
        <button onClick={handleBackClick} className="text-white/40 hover:text-white/70 transition-colors text-sm">
          ←
        </button>
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
          style={{ background: `${color}22`, border: `1.5px solid ${color}66`, color }}
        >
          {emotion?.emotion_label?.[0] || '?'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white/90 truncate">
            {emotion?.emotion_label || '情绪频道'}
          </div>
          <div className="text-xs text-white/35 flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
            {connected ? `${room?.participant_count || 1} 人在线` : '连接中…'}
          </div>
        </div>
        <div className="text-xs text-white/30 bg-white/5 px-2 py-1 rounded-full">
          {myAvatar} {myName}
        </div>
      </header>

      {/* 破冰语：优先用双方定制的，否则用单方的 */}
      {(room?.opening_line || emotion?.opening_line) && (
        <div className="px-4 py-2 text-center">
          <span
            className="text-xs px-3 py-1.5 rounded-full inline-flex items-center gap-1"
            style={{ background: `${color}15`, color: `${color}cc` }}
          >
            💬 {room?.opening_line || emotion?.opening_line}
          </span>
        </div>
      )}

      {/* 闲置提示 */}
      {idleWarning === 'quiet' && !roomClosed && (
        <div className="px-4 py-1.5 text-center">
          <span className="text-xs text-white/40 bg-white/5 px-3 py-1 rounded-full">
            🤫 有点安静了，说点什么让对话继续吧
          </span>
        </div>
      )}
      {idleWarning === 'closing' && !roomClosed && (
        <div className="px-4 py-1.5 text-center">
          <span className="text-xs text-amber-300/80 bg-amber-500/10 px-3 py-1 rounded-full">
            ⏳ 房间长时间无人发言，即将自动关闭
          </span>
        </div>
      )}

      {/* 消息区域 */}
      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-white/25 text-sm py-8">
            <div className="text-3xl mb-2">🫧</div>
            <p>对话刚刚开始，说点什么吧</p>
          </div>
        )}

        {messages.map((msg, i) => {
          if (msg.type === 'system') {
            return (
              <div key={i} className="text-center">
                <span className="text-xs text-white/25 bg-white/5 px-3 py-1 rounded-full">
                  {msg.content}
                </span>
              </div>
            )
          }
          const isSelf = msg.is_self
          return (
            <div key={msg.id || i} className={`flex gap-2 ${isSelf ? 'flex-row-reverse' : 'flex-row'}`}>
              {/* 头像 */}
              {!isSelf && (
                <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-base"
                  style={{ background: `${color}15`, border: `1px solid ${color}33` }}>
                  {msg.anonymous_avatar}
                </div>
              )}
              <div className={`max-w-[78%] sm:max-w-[70%] ${isSelf ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                {!isSelf && (
                  <span className="text-xs text-white/30 ml-1">{msg.anonymous_name}</span>
                )}
                <div
                  className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                    isSelf
                      ? 'text-white rounded-tr-sm'
                      : 'bg-white/8 text-white/85 rounded-tl-sm'
                  }`}
                  style={isSelf ? { background: color } : {}}
                >
                  {msg.content}
                </div>
                <span className="text-xs text-white/20 px-1">
                  {formatTime(msg.timestamp)}
                </span>
              </div>
            </div>
          )
        })}
        {/* 对方正在输入 */}
        {typingUser && (
          <div className="flex gap-2 items-end">
            <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-base"
              style={{ background: `${color}15`, border: `1px solid ${color}33` }}>
              {typingUser.avatar}
            </div>
            <div className="bg-white/8 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 输入区域 */}
      <div className="glass border-t border-white/5 px-4 py-3 relative">
        {/* 违规警告提示 */}
        {warning && (
          <div className="absolute bottom-full left-4 right-4 mb-2 p-3 rounded-xl bg-red-500/15 border border-red-500/30 text-red-200 text-xs leading-relaxed">
            ⚠️ {warning}
          </div>
        )}
        {/* Emoji 选择面板 */}
        {showEmoji && (
          <div className="absolute bottom-full left-4 right-4 mb-2 glass rounded-2xl p-3 grid grid-cols-8 gap-1">
            {EMOJIS.map((em, i) => (
              <button
                key={i}
                onClick={() => insertEmoji(em)}
                className="text-xl p-1.5 rounded-lg hover:bg-white/10 transition-colors"
              >
                {em}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2 items-end">
          {/* Emoji 按钮 */}
          <button
            onClick={() => setShowEmoji(v => !v)}
            className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center text-xl
              transition-colors ${showEmoji ? 'bg-white/15' : 'bg-white/5 hover:bg-white/10'}`}
          >
            😊
          </button>
          <textarea
            value={input}
            onChange={e => { setInput(e.target.value.slice(0, 1000)); notifyTyping() }}
            placeholder="说点什么…"
            rows={1}
            className="flex-1 bg-white/5 rounded-xl px-4 py-2.5 text-sm text-white
              placeholder-white/25 resize-none border border-white/10 focus:border-white/25
              transition-colors leading-relaxed"
            style={{ maxHeight: '120px' }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
            onInput={e => {
              const t = e.target as HTMLTextAreaElement
              t.style.height = 'auto'
              t.style.height = Math.min(t.scrollHeight, 120) + 'px'
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || !connected}
            className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center
              transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
            style={{ background: connected && input.trim() ? color : 'rgba(255,255,255,0.1)' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="text-white">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
        <p className="text-white/20 text-xs mt-2 text-center">
          Enter 发送 · Shift+Enter 换行 · 完全匿名
        </p>
      </div>
    </div>
  )
}
