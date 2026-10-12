import { LogOut } from 'lucide-react'
import { ProgressDots } from './ProgressDots'
import { Timer } from './Timer'

interface Props {
  /** Номер текущего задания с нуля; null — не показывать прогресс */
  current?: number | null
  total?: number
  /** Оставшиеся секунды; null — не показывать таймер */
  remaining?: number | null
  onExit?: () => void
}

/** Шапка во всю ширину: логотип и название, прогресс по заданиям, таймер, «Выйти» */
export function Header({ current = null, total = 0, remaining = null, onExit }: Props) {
  return (
    <header className="sticky top-0 z-30 flex h-16 w-full shrink-0 items-center gap-3 bg-navy px-3 text-white shadow-md sm:px-6">
      <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
        <img src="/logo.svg" alt="" className="h-8 w-8 shrink-0 rounded-md bg-white p-0.5 sm:h-9 sm:w-9" />
        <span className="hidden text-sm font-bold tracking-wide lg:inline">КАЗАХТЕЛЕКОМ</span>
        <span className="hidden h-7 w-px bg-white/30 lg:block" />
        <span className="hidden truncate text-sm font-semibold md:inline lg:text-base">БИОТ – Допуск к работе</span>
      </div>

      <div className="flex flex-1 items-center justify-center gap-3 sm:gap-5">
        {current !== null && total > 0 && (
          <div className="flex flex-col items-center gap-1.5">
            <span className="text-xs font-semibold sm:text-sm">
              Задание {current + 1} из {total}
            </span>
            <ProgressDots current={current} total={total} />
          </div>
        )}
        {remaining !== null && <Timer remaining={remaining} />}
      </div>

      {onExit && (
        <button
          onClick={onExit}
          className="flex shrink-0 items-center gap-2 rounded-lg border border-white/80 px-3 py-1.5 text-sm font-semibold transition hover:bg-white/10 sm:px-4"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Выйти</span>
        </button>
      )}
    </header>
  )
}
