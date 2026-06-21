const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export interface EmotionResult {
  session_token: string
  user_id: number
  anonymous_name: string
  anonymous_avatar: string
  emotion_label: string
  emotion_score: number
  emotion_valence: number
  emotion_keywords: string[]
  secondary_emotions: { label: string; weight: number }[]
  emotion_color: string
  emotion_summary: string
  opening_line: string
  is_crisis: boolean
  match_room_code: string
  match_status: string
  emotion_record_id: number
  pair_id: string | null
}

export interface ConfirmStatus {
  state: string  // waiting_choice / confirmed / rejected / not_found
  other_emotion_label: string
  other_emotion_color: string
  other_emotion_summary: string
  room_code: string
  my_choice: boolean | null
  seconds_left: number
}

export async function getConfirmStatus(pairId: string, userId: number): Promise<ConfirmStatus> {
  const res = await fetch(`${API_URL}/api/match/confirm/status/${pairId}?user_id=${userId}`)
  if (!res.ok) throw new Error('获取确认状态失败')
  return res.json()
}

export async function submitConfirmChoice(pairId: string, userId: number, agree: boolean): Promise<ConfirmStatus> {
  const res = await fetch(`${API_URL}/api/match/confirm/choice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pair_id: pairId, user_id: userId, agree }),
  })
  if (!res.ok) throw new Error('提交选择失败')
  return res.json()
}

export interface MatchStatus {
  room_code: string
  status: string
  emotion_label: string
  emotion_color: string
  participant_count: number
  timed_out: boolean
}

export interface ChatMessage {
  id?: number
  type: 'message' | 'system'
  anonymous_name?: string
  anonymous_avatar?: string
  content: string
  timestamp: string
  is_self?: boolean
}

export interface RoomInfo {
  room_code: string
  status: string
  room_type: string
  emotion_label: string
  emotion_color: string
  participant_count: number
  messages: ChatMessage[]
  opening_line: string
}

export async function analyzeEmotion(text: string, sessionToken?: string, chatMode: string = 'one_on_one'): Promise<EmotionResult> {
  const accountToken = typeof window !== 'undefined' ? localStorage.getItem('vibe_account_token') : null
  const res = await fetch(`${API_URL}/api/emotion/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, session_token: sessionToken, chat_mode: chatMode, account_token: accountToken }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '请求失败，请稍后重试')
  }
  return res.json()
}

export async function rematch(emotionRecordId: number, sessionToken: string): Promise<EmotionResult> {
  const res = await fetch(`${API_URL}/api/emotion/rematch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emotion_record_id: emotionRecordId, session_token: sessionToken }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '重新匹配失败')
  }
  return res.json()
}

export async function getMatchStatus(roomCode: string, userId: number): Promise<MatchStatus> {
  const res = await fetch(`${API_URL}/api/match/status/${roomCode}?user_id=${userId}`)
  if (!res.ok) throw new Error('获取匹配状态失败')
  return res.json()
}

export async function getRoomInfo(roomCode: string, userId: number): Promise<RoomInfo> {
  const res = await fetch(`${API_URL}/api/match/room/${roomCode}?user_id=${userId}`)
  if (!res.ok) throw new Error('获取房间信息失败')
  return res.json()
}

// ===== 账号 =====
export interface AuthResult {
  token: string
  account_id: number
  email: string | null
  display_name: string | null
  provider: string
}

export async function registerAccount(email: string, password: string): Promise<AuthResult> {
  const res = await fetch(`${API_URL}/api/account/register`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || '注册失败') }
  return res.json()
}

export async function loginAccount(email: string, password: string): Promise<AuthResult> {
  const res = await fetch(`${API_URL}/api/account/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || '登录失败') }
  return res.json()
}

export function googleLoginUrl(): string {
  return `${API_URL}/api/account/google/login`
}

export async function getMyAccount(token: string) {
  const res = await fetch(`${API_URL}/api/account/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return null
  return res.json()
}

export async function getHistoryEmotions(token: string) {
  const res = await fetch(`${API_URL}/api/account/history/emotions`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('获取情绪历史失败')
  return res.json()
}

export async function getHistorySessions(token: string) {
  const res = await fetch(`${API_URL}/api/account/history/sessions`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('获取会话历史失败')
  return res.json()
}

export async function getSessionMessages(matchId: number, token: string) {
  const res = await fetch(`${API_URL}/api/account/history/session/${matchId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('获取会话消息失败')
  return res.json()
}

export function createChatWebSocket(
  roomCode: string,
  userId: number,
  sessionToken: string
): WebSocket {
  return new WebSocket(
    `${WS_URL}/ws/chat/${roomCode}?user_id=${userId}&session_token=${sessionToken}`
  )
}

// ===== 情绪历史轨迹（本地存储）=====
export interface EmotionHistoryItem {
  text: string
  emotion_label: string
  emotion_score: number
  emotion_valence: number
  emotion_color: string
  emotion_summary: string
  timestamp: string
}

const HISTORY_KEY = 'vibe_history'
const MAX_HISTORY = 30

export function saveEmotionHistory(result: EmotionResult, inputText: string) {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    const list: EmotionHistoryItem[] = raw ? JSON.parse(raw) : []
    list.unshift({
      text: inputText,
      emotion_label: result.emotion_label,
      emotion_score: result.emotion_score,
      emotion_valence: result.emotion_valence,
      emotion_color: result.emotion_color,
      emotion_summary: result.emotion_summary,
      timestamp: new Date().toISOString(),
    })
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, MAX_HISTORY)))
  } catch {}
}

export function getEmotionHistory(): EmotionHistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function clearEmotionHistory() {
  localStorage.removeItem(HISTORY_KEY)
}
