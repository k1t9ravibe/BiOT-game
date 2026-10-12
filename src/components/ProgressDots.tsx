/** Прогресс из точек на линии: пройденные и текущая — ярко-синие, остальные серые */
export function ProgressDots({ current, total }: { current: number; total: number }) {
  return (
    <div className="relative flex w-40 items-center justify-between sm:w-56" aria-hidden>
      <div className="absolute inset-x-1 top-1/2 h-0.5 -translate-y-1/2 bg-white/25" />
      <div
        className="absolute left-1 top-1/2 h-0.5 -translate-y-1/2 bg-accent transition-all"
        style={{ width: total > 1 ? `calc(${(current / (total - 1)) * 100}% - 0.5rem)` : 0 }}
      />
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`relative rounded-full transition-all ${
            i < current ? 'h-2.5 w-2.5 bg-accent' : i === current ? 'h-3.5 w-3.5 bg-accent ring-4 ring-accent/30' : 'h-2.5 w-2.5 bg-[#7f8db0]'
          }`}
        />
      ))}
    </div>
  )
}
