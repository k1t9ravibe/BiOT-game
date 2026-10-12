import type { Task, TaskItem } from '../types'

/** Статус карточки в разборе */
export type ItemStatus = 'correct' | 'extra' | 'missed' | 'neutral'

export function itemStatus(item: TaskItem, selected: string[]): ItemStatus {
  const picked = selected.includes(item.id)
  if (item.isViolation) return picked ? 'correct' : 'missed'
  return picked ? 'extra' : 'neutral'
}

/** Порядок карточек в разборе: нарушения по рангу, затем лишние, затем верно не выбранные */
export function reviewOrder(task: Task, selected: string[]): TaskItem[] {
  const weight = (i: TaskItem) => {
    const s = itemStatus(i, selected)
    return s === 'correct' || s === 'missed' ? (i.rank ?? 99) : s === 'extra' ? 1000 : 2000
  }
  return [...task.items].sort((a, b) => weight(a) - weight(b))
}

/** Позиция нарушения среди найденных игроком нарушений (без учёта лишних) */
export function playerPosition(task: Task, selected: string[], id: string): number | null {
  const found = selected.filter((s) => task.items.find((i) => i.id === s)?.isViolation)
  const p = found.indexOf(id)
  return p < 0 ? null : p + 1
}
