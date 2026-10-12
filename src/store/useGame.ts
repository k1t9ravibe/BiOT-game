import { create } from 'zustand'
import { taskTimeLimit } from '../config'
import { scoreTask, totals } from '../lib/scoring'
import { saveAttempt, saveLastPlayer } from '../lib/storage'
import type { Player, Task, TaskResult } from '../types'

type Screen = 'start' | 'task' | 'result'
type Phase = 'select' | 'review'

interface GameState {
  screen: Screen
  tasks: Task[]
  player: Player | null
  index: number
  phase: Phase
  /** Выбранные id в порядке игрока */
  selected: string[]
  /** Момент начала и окончания текущего задания (мс) */
  startedAt: number
  deadline: number
  results: TaskResult[]
  /** Подсказка на первом задании уже закрыта */
  hintClosed: boolean

  setTasks: (tasks: Task[]) => void
  start: (player: Player) => void
  toggle: (id: string) => void
  move: (fromId: string, toId: string) => void
  confirm: (timedOut?: boolean) => void
  next: () => void
  restart: () => void
  exit: () => void
  closeHint: () => void
}

function beginTask(tasks: Task[], index: number) {
  const now = Date.now()
  return {
    index,
    phase: 'select' as Phase,
    selected: [],
    startedAt: now,
    deadline: now + taskTimeLimit(tasks[index]?.timeLimitSec) * 1000,
  }
}

export const useGame = create<GameState>((set, get) => ({
  screen: 'start',
  tasks: [],
  player: null,
  index: 0,
  phase: 'select',
  selected: [],
  startedAt: 0,
  deadline: 0,
  results: [],
  hintClosed: false,

  setTasks: (tasks) => set({ tasks }),

  start: (player) => {
    saveLastPlayer(player)
    set({ player, screen: 'task', results: [], hintClosed: false, ...beginTask(get().tasks, 0) })
  },

  // Клик по карточке или зоне на сцене: добавить в конец или снять выбор (номера пересчитываются сами)
  toggle: (id) => {
    const { phase, selected } = get()
    if (phase !== 'select') return
    set({ selected: selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id] })
  },

  // Перетаскивание: поставить fromId на место toId
  move: (fromId, toId) => {
    const sel = [...get().selected]
    const from = sel.indexOf(fromId)
    const to = sel.indexOf(toId)
    if (from < 0 || to < 0 || from === to) return
    sel.splice(to, 0, ...sel.splice(from, 1))
    set({ selected: sel })
  },

  confirm: (timedOut = false) => {
    const { phase, tasks, index, selected, startedAt, deadline, results } = get()
    if (phase !== 'select') return
    const task = tasks[index]
    const spent = Math.round((Math.min(Date.now(), deadline) - startedAt) / 1000)
    set({ phase: 'review', results: [...results, scoreTask(task, selected, spent, timedOut)] })
  },

  next: () => {
    const { index, tasks, results, player } = get()
    if (index + 1 < tasks.length) {
      set({ hintClosed: true, ...beginTask(tasks, index + 1) })
      return
    }
    const t = totals(results)
    if (player)
      saveAttempt({
        player,
        finishedAt: new Date().toISOString(),
        percent: t.percent,
        passed: t.passed,
        totalTimeSec: t.timeSec,
        results,
      })
    set({ screen: 'result' })
  },

  restart: () => {
    const { player } = get()
    if (player) get().start(player)
  },

  exit: () => set({ screen: 'start', phase: 'select', selected: [], results: [], index: 0 }),

  closeHint: () => set({ hintClosed: true }),
}))
