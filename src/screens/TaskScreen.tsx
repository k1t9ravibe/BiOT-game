import { useEffect, useState } from 'react'
import { Header } from '../components/Header'
import { Panel } from '../components/Panel'
import { Scene } from '../components/Scene'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { useSceneImage } from '../hooks/useSceneImage'
import { useGame } from '../store/useGame'

/** Оставшееся время; обновляется, пока задание активно, и «замирает» после подтверждения */
function useRemaining(deadline: number, active: boolean) {
  const [left, setLeft] = useState(() => (deadline - Date.now()) / 1000)
  useEffect(() => {
    if (!active) return
    const tick = () => setLeft(Math.max(0, (deadline - Date.now()) / 1000))
    tick()
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [deadline, active])
  return left
}

export function TaskScreen() {
  const g = useGame()
  const task = g.tasks[g.index]
  const img = useSceneImage(task)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [exitOpen, setExitOpen] = useState(false)
  const active = g.phase === 'select'
  const remaining = useRemaining(g.deadline, active)
  const result = g.results.find((r) => r.taskId === task?.id)

  // Время вышло — подтверждаем автоматически
  useEffect(() => {
    // Сверяемся с реальным временем, а не с «замёрзшим» значением от прошлого задания
    if (active && remaining <= 0 && Date.now() >= g.deadline) g.confirm(true)
  }, [active, remaining, g])

  // Новое задание — сбрасываем подсветку и прокручиваем вверх
  useEffect(() => {
    setHoveredId(null)
    window.scrollTo({ top: 0 })
  }, [g.index])

  if (!task) return null

  return (
    <div className="flex min-h-dvh flex-col lg:h-dvh">
      <Header current={g.index} total={g.tasks.length} remaining={remaining} onExit={() => setExitOpen(true)} />

      <main className="flex flex-1 flex-col gap-4 p-3 sm:p-4 lg:min-h-0 lg:flex-row lg:gap-5 lg:p-5">
        <section className="overflow-hidden rounded-2xl shadow-[0_8px_30px_rgba(11,42,91,.12)] lg:w-[65%] lg:min-h-0">
          <Scene
            task={task}
            img={img}
            phase={g.phase}
            selected={g.phase === 'review' && result ? result.selected : g.selected}
            onToggle={g.toggle}
            hoveredId={hoveredId}
            onHover={setHoveredId}
            showHint={g.index === 0 && !g.hintClosed && active}
            onCloseHint={g.closeHint}
          />
        </section>

        <aside className="flex lg:w-[35%] lg:min-h-0">
          <Panel
            task={task}
            img={img}
            phase={g.phase}
            selected={g.selected}
            result={result}
            isLast={g.index === g.tasks.length - 1}
            hoveredId={hoveredId}
            onHover={setHoveredId}
            onToggle={g.toggle}
            onMove={g.move}
            onConfirm={() => g.confirm(false)}
            onNext={g.next}
          />
        </aside>
      </main>

      <ConfirmDialog
        open={exitOpen}
        title="Выйти из тренажёра?"
        text="Прогресс текущей попытки будет потерян."
        okText="Выйти"
        onOk={() => {
          setExitOpen(false)
          g.exit()
        }}
        onCancel={() => setExitOpen(false)}
      />
    </div>
  )
}
