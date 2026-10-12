import { ArrowRight } from 'lucide-react'
import type { SceneImage } from '../hooks/useSceneImage'
import type { Task, TaskResult } from '../types'
import { GridCards } from './GridCards'
import { ListCards } from './ListCards'
import { ReviewList } from './ReviewList'

interface Props {
  task: Task
  img: SceneImage | null
  phase: 'select' | 'review'
  selected: string[]
  result: TaskResult | undefined
  isLast: boolean
  hoveredId: string | null
  onHover: (id: string | null) => void
  onToggle: (id: string) => void
  onMove: (fromId: string, toId: string) => void
  onConfirm: () => void
  onNext: () => void
}

/** Правая панель: выбор карточек (list / grid) или разбор после подтверждения */
export function Panel(p: Props) {
  const review = p.phase === 'review' && p.result
  return (
    <div className="flex w-full flex-col rounded-2xl bg-white shadow-[0_8px_30px_rgba(11,42,91,.12)] lg:min-h-0">
      <h2 className="px-4 pb-3 pt-4 text-[17px] font-bold leading-snug text-navy sm:px-5 sm:pt-5">
        {review ? `Разбор: ${p.task.title}` : 'Выберите нарушения и расположите их в правильной последовательности:'}
      </h2>

      <div className="thin-scroll flex-1 px-4 pb-3 sm:px-5 lg:min-h-0 lg:overflow-y-auto">
        {review ? (
          <ReviewList task={p.task} img={p.img} result={p.result!} hoveredId={p.hoveredId} onHover={p.onHover} />
        ) : p.task.layout === 'grid' ? (
          <GridCards task={p.task} img={p.img} selected={p.selected} onToggle={p.onToggle} />
        ) : (
          <ListCards task={p.task} img={p.img} selected={p.selected} onToggle={p.onToggle} onMove={p.onMove} />
        )}
      </div>

      {/* На телефоне кнопка прилипает к низу экрана */}
      <div className="sticky bottom-0 rounded-b-2xl border-t border-line bg-white p-4 sm:px-5 lg:static">
        {review ? (
          <button
            onClick={p.onNext}
            className="flex w-full items-center justify-center gap-2 rounded-[10px] bg-action py-3.5 text-base font-semibold text-white transition hover:bg-action-dark"
          >
            {p.isLast ? 'Показать итог' : 'Следующее задание'}
            <ArrowRight className="h-5 w-5" />
          </button>
        ) : (
          <button
            onClick={p.onConfirm}
            disabled={p.selected.length === 0}
            className="w-full rounded-[10px] bg-action py-3.5 text-base font-semibold text-white transition hover:bg-action-dark disabled:cursor-not-allowed disabled:opacity-50"
          >
            Подтвердить порядок
          </button>
        )}
      </div>
    </div>
  )
}
