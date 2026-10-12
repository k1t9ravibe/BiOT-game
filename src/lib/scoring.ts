import { config } from '../config'
import type { Task, TaskResult } from '../types'

/**
 * Подсчёт баллов за задание.
 * +found за каждое найденное нарушение, −distractorPenalty за каждый отвлекающий вариант,
 * бонус за порядок: полный — если найдены все нарушения и все пары стоят верно,
 * иначе частичный — пропорционально доле пар в верном порядке и доле найденных.
 */
export function scoreTask(task: Task, selected: string[], timeSpentSec: number, timedOut: boolean): TaskResult {
  const w = config.score
  const byId = new Map(task.items.map((i) => [i.id, i]))
  const violations = task.items.filter((i) => i.isViolation)
  const picked = selected.map((id) => byId.get(id)).filter((i) => i !== undefined)

  const foundItems = picked.filter((i) => i.isViolation)
  const extras = picked.length - foundItems.length
  const found = foundItems.length
  const total = violations.length

  // Порядок оцениваем только среди найденных нарушений: сколько пар (a раньше b) стоят так же, как в эталоне
  const ranks = foundItems.map((i) => i.rank ?? 0)
  let pairs = 0
  let good = 0
  for (let a = 0; a < ranks.length; a++)
    for (let b = a + 1; b < ranks.length; b++) {
      pairs++
      if (ranks[a] < ranks[b]) good++
    }
  // Одно найденное нарушение — порядок не с чем сравнивать
  const orderRatio = pairs ? good / pairs : found === 1 && total === 1 ? 1 : 0
  const perfectOrder = total > 0 && found === total && orderRatio === 1

  const orderBonus = perfectOrder
    ? w.perfectOrderBonus
    : Math.round(w.partialOrderBonusMax * orderRatio * (total ? found / total : 0))

  const raw = found * w.found - extras * w.distractorPenalty + orderBonus
  const maxScore = total * w.found + w.perfectOrderBonus

  return {
    taskId: task.id,
    title: task.title,
    selected: [...selected],
    score: Math.max(0, raw),
    maxScore,
    found,
    totalViolations: total,
    extras,
    orderRatio,
    perfectOrder,
    orderBonus,
    timeSpentSec,
    timedOut,
  }
}

export function totals(results: TaskResult[]) {
  const score = results.reduce((s, r) => s + r.score, 0)
  const max = results.reduce((s, r) => s + r.maxScore, 0)
  const percent = max ? Math.round((score / max) * 100) : 0
  const timeSec = results.reduce((s, r) => s + r.timeSpentSec, 0)
  return { score, max, percent, timeSec, passed: percent >= config.passThresholdPercent }
}
