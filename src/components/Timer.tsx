import { Timer as TimerIcon } from 'lucide-react'
import { config } from '../config'
import { mmss } from '../lib/format'

/** Таймер в тёмной плашке; последние секунды — красный */
export function Timer({ remaining }: { remaining: number }) {
  const warn = remaining <= config.timerWarningSec
  return (
    <div
      className={`flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 sm:gap-2 sm:px-3.5 ${warn ? 'bg-bad' : 'bg-[#061a3b]'} ${
        warn && remaining > 0 ? 'animate-pulse' : ''
      }`}
      role="timer"
      aria-label={`Осталось ${mmss(remaining)}`}
    >
      <TimerIcon className="h-5 w-5 text-white sm:h-6 sm:w-6" strokeWidth={2.2} />
      <span className="tabular text-lg font-bold leading-none text-white sm:text-2xl">{mmss(remaining)}</span>
    </div>
  )
}
