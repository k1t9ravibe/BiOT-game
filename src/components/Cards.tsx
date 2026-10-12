import { Check } from 'lucide-react'
import type { SceneImage } from '../hooks/useSceneImage'
import type { TaskItem } from '../types'
import { Thumb } from './Thumb'

/** Синий круглый номер; пустой кружок — карточка не выбрана */
export function NumberBadge({ n, className = '' }: { n: number | null; className?: string }) {
  return (
    <span
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold transition ${
        n ? 'bg-accent text-white shadow-[0_2px_6px_rgba(30,107,255,.4)]' : 'border-2 border-[#c3cddd] bg-white text-transparent'
      } ${className}`}
    >
      {n ?? '·'}
    </span>
  )
}

interface CardProps {
  item: TaskItem
  img: SceneImage | null | undefined
  n: number | null
  onToggle: () => void
}

/** Карточка режима list: номер, миниатюра, текст */
export function ListCard({ item, img, n, onToggle, handle }: CardProps & { handle?: React.ReactNode }) {
  return (
    <div
      className={`flex items-center gap-3 rounded-[10px] border bg-white p-2 pr-2.5 transition ${
        n ? 'border-accent shadow-[0_0_0_1px_#1E6BFF]' : 'border-line hover:border-[#a9b8d0]'
      }`}
    >
      <button type="button" onClick={onToggle} aria-pressed={!!n} className="flex min-w-0 flex-1 items-center gap-3 text-left">
        <NumberBadge n={n} />
        <Thumb img={img} area={item.area} className="h-14 w-20 rounded-md" />
        <span className="text-[15px] font-medium leading-snug text-ink">{item.text}</span>
      </button>
      {handle}
    </div>
  )
}

/** Карточка режима grid: миниатюра сверху, подпись снизу, номер в углу */
export function GridCard({ item, img, n, onToggle }: CardProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={!!n}
      className={`relative flex flex-col overflow-hidden rounded-[10px] border bg-white text-left transition ${
        n ? 'border-accent shadow-[0_0_0_1px_#1E6BFF]' : 'border-line hover:border-[#a9b8d0]'
      }`}
    >
      <Thumb img={img} area={item.area} className="aspect-[4/3] w-full" />
      <NumberBadge n={n} className="absolute left-2 top-2" />
      {n && (
        <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-white/90">
          <Check className="h-4 w-4 text-accent" strokeWidth={3} />
        </span>
      )}
      <span className="flex-1 p-2.5 text-sm font-medium leading-snug text-ink">{item.text}</span>
    </button>
  )
}
