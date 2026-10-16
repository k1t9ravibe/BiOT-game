import { config } from '../config'
import { loadDraft, saveDraft } from './storage'

/**
 * Прогресс по локациям режима ходьбы (в браузере, localStorage).
 * Локация 2 «Город» открывается, когда локация 1 пройдена не ниже порога допуска.
 */

const KEY = 'biot.progress.v1'

interface Progress {
  /** Лучший результат локации 1, % */
  loc1Best?: number
}

const load = (): Progress => loadDraft<Progress>(KEY) ?? {}
const save = (p: Progress) => saveDraft(KEY, p)

/** Сохраняет результат локации 1; возвращает true, если город открыт */
export function saveLoc1Result(percent: number): boolean {
  const p = load()
  p.loc1Best = Math.max(p.loc1Best ?? 0, percent)
  save(p)
  return isCityUnlocked()
}

export function isCityUnlocked(): boolean {
  return (load().loc1Best ?? 0) >= config.passThresholdPercent
}

