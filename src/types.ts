/** Прямоугольная область на картинке сцены, все значения — в процентах от ширины/высоты */
export interface Area {
  x: number
  y: number
  w: number
  h: number
}

export interface TaskItem {
  id: string
  text: string
  /** true — нарушение; false — отвлекающий вариант (на сцене сделано правильно) */
  isViolation: boolean
  /** Позиция по критичности, 1 — самое опасное. Только у нарушений */
  rank?: number
  area: Area
  explanation: string
  /** Необязательная ссылка на пункт правил, показывается под пояснением */
  rule?: string
}

export type Layout = 'list' | 'grid'

export interface Task {
  id: string
  title: string
  image: string
  layout: Layout
  timeLimitSec?: number
  items: TaskItem[]
}

export interface Player {
  fio: string
  tabNo: string
  department: string
}

/** Итог одного задания */
export interface TaskResult {
  taskId: string
  title: string
  /** Выбранные игроком id в его порядке */
  selected: string[]
  score: number
  maxScore: number
  found: number
  totalViolations: number
  extras: number
  /** Доля пар нарушений в верном порядке, 0..1 */
  orderRatio: number
  perfectOrder: boolean
  orderBonus: number
  timeSpentSec: number
  timedOut: boolean
}

/** Запись в истории прохождений (localStorage) */
export interface AttemptRecord {
  player: Player
  finishedAt: string
  percent: number
  passed: boolean
  totalTimeSec: number
  results: TaskResult[]
}
