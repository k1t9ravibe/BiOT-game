import { CheckCircle2, CircleDashed, XCircle, MinusCircle } from 'lucide-react'
import { itemStatus, playerPosition, reviewOrder, type ItemStatus } from '../lib/review'
import type { SceneImage } from '../hooks/useSceneImage'
import type { Task, TaskResult } from '../types'
import { Thumb } from './Thumb'

const styles: Record<ItemStatus, { box: string; label: string; icon: React.ReactNode }> = {
  correct: { box: 'border-2 border-ok bg-ok/[.04]', label: 'Найдено', icon: <CheckCircle2 className="h-4 w-4 text-ok" /> },
  extra: { box: 'border-2 border-bad bg-bad/[.04]', label: 'Лишнее — это не нарушение', icon: <XCircle className="h-4 w-4 text-bad" /> },
  missed: { box: 'border-2 border-dashed border-miss bg-miss/[.04]', label: 'Пропущено', icon: <CircleDashed className="h-4 w-4 text-miss" /> },
  neutral: { box: 'border border-line opacity-75', label: 'Верно не выбрано', icon: <MinusCircle className="h-4 w-4 text-muted" /> },
}

/** Разбор задания: статус каждой карточки, ваша и верная позиция, пояснение со ссылкой на правила */
export function ReviewList({ task, img, result, hoveredId, onHover }: {
  task: Task
  img: SceneImage | null | undefined
  result: TaskResult
  hoveredId: string | null
  onHover: (id: string | null) => void
}) {
  const sel = result.selected
  return (
    <div className="flex flex-col gap-3">
      <Summary result={result} />
      {reviewOrder(task, sel).map((it) => {
        const st = itemStatus(it, sel)
        const s = styles[st]
        const mine = it.isViolation ? playerPosition(task, sel, it.id) : null
        return (
          <div
            key={it.id}
            onMouseEnter={() => onHover(it.id)}
            onMouseLeave={() => onHover(null)}
            className={`rounded-[10px] bg-white p-2.5 transition ${s.box} ${hoveredId === it.id ? 'ring-2 ring-accent/50' : ''}`}
          >
            <div className="flex gap-3">
              <Thumb img={img} area={it.area} className="h-14 w-20 rounded-md" />
              <div className="min-w-0 flex-1">
                <div className="text-[15px] font-semibold leading-snug text-ink">{it.text}</div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                  <span className="flex items-center gap-1 font-semibold">
                    {s.icon}
                    {s.label}
                  </span>
                  {it.isViolation && (
                    <span>
                      Верная позиция: <b className="text-ink">{it.rank}</b>
                      {mine !== null && (
                        <>
                          {' · '}ваша: <b className={mine === it.rank ? 'text-ok' : 'text-bad'}>{mine}</b>
                        </>
                      )}
                    </span>
                  )}
                </div>
              </div>
            </div>
            {st !== 'neutral' && (it.explanation || it.rule) && (
              <p className="mt-2 text-[13px] leading-snug text-[#3d4d68]">
                {it.explanation}
                {it.rule && <span className="mt-0.5 block font-semibold text-action">{it.rule}</span>}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function Summary({ result: r }: { result: TaskResult }) {
  return (
    <div className="rounded-[10px] bg-page p-3 text-sm">
      {r.timedOut && <div className="mb-1.5 font-semibold text-bad">Время вышло — ответ подтверждён автоматически</div>}
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-semibold text-navy">Баллы за задание</span>
        <span className="tabular text-xl font-bold text-navy">
          {r.score} <span className="text-sm font-medium text-muted">/ {r.maxScore}</span>
        </span>
      </div>
      <div className="mt-1.5 grid grid-cols-1 gap-x-4 gap-y-0.5 text-[13px] text-muted sm:grid-cols-2">
        <span>
          Найдено нарушений: <b className="text-ink">{r.found} из {r.totalViolations}</b>
        </span>
        <span>
          Лишних: <b className={r.extras ? 'text-bad' : 'text-ink'}>{r.extras}</b>
        </span>
        <span className="sm:col-span-2">
          Порядок:{' '}
          <b className={r.perfectOrder ? 'text-ok' : 'text-ink'}>
            {r.perfectOrder ? 'полностью верный' : `${Math.round(r.orderRatio * 100)}% пар на своих местах`}
          </b>{' '}
          (+{r.orderBonus})
        </span>
      </div>
    </div>
  )
}
