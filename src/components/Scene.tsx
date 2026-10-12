import { X } from 'lucide-react'
import { config } from '../config'
import { fitRect } from '../lib/crop'
import { itemStatus, type ItemStatus } from '../lib/review'
import { useElementSize } from '../hooks/useElementSize'
import type { SceneImage } from '../hooks/useSceneImage'
import type { Task } from '../types'

interface Props {
  task: Task
  img: SceneImage | null
  phase: 'select' | 'review'
  selected: string[]
  onToggle: (id: string) => void
  hoveredId: string | null
  onHover: (id: string | null) => void
  showHint: boolean
  onCloseHint: () => void
}

const reviewColors: Record<ItemStatus, string> = {
  correct: 'border-ok bg-ok/20',
  extra: 'border-bad bg-bad/20',
  missed: 'border-miss border-dashed bg-miss/15',
  neutral: 'border-white/70 border-dashed bg-white/10',
}

/**
 * Сцена: картинка вписана как object-fit (cover/contain из конфига), поверх — зоны нарушений в процентах.
 * До подтверждения зоны невидимы (но кликабельны), выбранные отмечаются номером.
 * В разборе зоны подсвечиваются цветом статуса при наведении на сцену (на сенсорных экранах — всегда).
 */
export function Scene({ task, img, phase, selected, onToggle, hoveredId, onHover, showHint, onCloseHint }: Props) {
  const [ref, box] = useElementSize<HTMLDivElement>()
  const rect = img && box.w ? fitRect(box, img, config.sceneFit) : null
  const review = phase === 'review'
  // Большие зоны снизу, маленькие сверху — чтобы вложенные области оставались кликабельными
  const zones = [...task.items].sort((a, b) => b.area.w * b.area.h - a.area.w * a.area.h)

  return (
    <div ref={ref} className="group relative aspect-video w-full overflow-hidden bg-navy lg:aspect-auto lg:h-full">
      {rect && img && (
        <div className="absolute" style={{ left: rect.left, top: rect.top, width: rect.w, height: rect.h }}>
          <img src={img.src} alt={task.title} draggable={false} className="h-full w-full select-none" />
          {zones.map((it) => {
            const pos = selected.indexOf(it.id)
            const status = itemStatus(it, selected)
            const hovered = hoveredId === it.id
            return (
              <button
                key={it.id}
                type="button"
                aria-label={review ? it.text : `Область сцены`}
                onClick={() => (review ? onHover(hovered ? null : it.id) : onToggle(it.id))}
                onMouseEnter={() => review && onHover(it.id)}
                onMouseLeave={() => review && onHover(null)}
                className={`absolute rounded-lg border-[3px] transition ${
                  review
                    ? `${reviewColors[status]} cursor-help ${hovered ? 'opacity-100 shadow-[0_0_0_4px_rgba(255,255,255,.6)]' : 'opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100'}`
                    : pos >= 0
                      ? 'cursor-default border-dashed border-accent bg-accent/15'
                      : 'cursor-default border-transparent'
                }`}
                style={{ left: `${it.area.x}%`, top: `${it.area.y}%`, width: `${it.area.w}%`, height: `${it.area.h}%` }}
              >
                {!review && pos >= 0 && <Badge className="bg-accent">{pos + 1}</Badge>}
                {review && status !== 'neutral' && (
                  <Badge className={status === 'correct' ? 'bg-ok' : status === 'extra' ? 'bg-bad' : 'bg-miss'}>
                    {it.isViolation ? it.rank : '✕'}
                  </Badge>
                )}
                {review && hovered && (
                  <span className="pointer-events-none absolute left-0 top-full z-10 mt-1 w-max max-w-56 rounded-md bg-navy/95 px-2 py-1 text-left text-xs font-medium text-white">
                    {it.text}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      {showHint && (
        <button
          type="button"
          onClick={onCloseHint}
          className="absolute left-3 top-3 z-20 max-w-sm rounded-xl bg-navy/85 p-3 pr-9 text-left text-sm leading-snug text-white shadow-lg backdrop-blur-sm sm:left-5 sm:top-5 sm:p-4 sm:pr-10 sm:text-[15px]"
        >
          Внимательно изучите сцену. Выберите и расположите нарушения в правильной последовательности (от наиболее критичного к менее
          значимому).
          <X className="absolute right-2.5 top-2.5 h-4 w-4 opacity-80" />
        </button>
      )}
    </div>
  )
}

function Badge({ children, className }: { children: React.ReactNode; className: string }) {
  return (
    <span
      className={`absolute -left-3 -top-3 flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold text-white shadow-md ring-2 ring-white ${className}`}
    >
      {children}
    </span>
  )
}
