import type { AttemptRecord, Player } from '../types'

// localStorage может быть недоступен (приватный режим, запрет cookies) — всё обёрнуто в try/catch
const KEY_PLAYER = 'biot.player.v1'
const KEY_HISTORY = 'biot.history.v1'

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* хранилище недоступно — молча продолжаем */
  }
}

export const loadLastPlayer = () => read<Player | null>(KEY_PLAYER, null)
export const saveLastPlayer = (p: Player) => write(KEY_PLAYER, p)

export function saveAttempt(rec: AttemptRecord) {
  const history = read<AttemptRecord[]>(KEY_HISTORY, [])
  history.unshift(rec)
  write(KEY_HISTORY, history.slice(0, 50))
}

export function loadDraft<T>(key: string): T | null {
  return read<T | null>(key, null)
}
export function saveDraft(key: string, value: unknown) {
  write(key, value)
}
