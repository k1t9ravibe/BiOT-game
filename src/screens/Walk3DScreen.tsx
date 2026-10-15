import { useCallback, useEffect, useRef, useState } from 'react'
import { Flag, Info, Search, X } from 'lucide-react'
import { config } from '../config'
import { Header } from '../components/Header'
import { ListCards } from '../components/ListCards'
import { ReviewList } from '../components/ReviewList'
import { scoreTask } from '../lib/scoring'
import { WalkEngine } from '../walk/engine'
import type { Task, TaskResult } from '../types'

/**
 * Режим ходьбы (/walk): 3D-сцена из Blender, игрок идёт от точки A к точке B,
 * по пути осматривает объекты и отмечает нарушения. Карточки и баллы — в формате tasks.json.
 * Объекты сцены с именем item_<id> соответствуют карточкам задания с тем же id.
 */

/** Задание и маршрут для каждой сцены. Задания режима ходьбы лежат отдельно (walk-tasks.json),
 *  чтобы не попасть в основной тренажёр с картинками */
const SCENES: Record<string, { tasksUrl: string; taskId: string; title: string; route: string }> = {
  landscape: { tasksUrl: '/walk-tasks.json', taskId: 'landscape', title: 'Улица у КТПН', route: 'Пройдите по улице от точки A мимо КТПН до фургона (B).' },
  t1: { tasksUrl: config.tasksUrl, taskId: 't1', title: 'Опора у сельской АТС', route: 'Дойдите от фургона (A) до опоры (B).' },
}
/** По умолчанию ландшафт; другую сцену можно выбрать параметром: /walk?scene=t1 → /models/t1.glb */
const SCENE_NAME = new URLSearchParams(location.search).get('scene')?.replace(/[^\w-]/g, '') || 'landscape'
const SCENE = SCENES[SCENE_NAME] ?? SCENES.landscape
const SCENE_URL = `/models/${SCENE_NAME}.glb`
const WORKER_URL = '/models/worker.glb'
/** На каком расстоянии от B можно завершить осмотр */
const GOAL_RADIUS = 2

export default function Walk3DScreen() {
  const mountRef = useRef<HTMLDivElement>(null)
  const engineRef = useRef<WalkEngine | null>(null)
  const [task, setTask] = useState<Task | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | string>('loading')
  const [near, setNear] = useState<string[]>([])
  const [marked, setMarked] = useState<string[]>([])
  const [distB, setDistB] = useState<number | null>(null)
  const [result, setResult] = useState<TaskResult | null>(null)
  const [hint, setHint] = useState(true)
  /** Задание начинается после окна «Ситуация»: до этого игрок стоит, время не идёт */
  const [started, setStarted] = useState(false)
  const startedAt = useRef(0)
  const start = () => {
    startedAt.current = Date.now()
    setStarted(true)
  }

  // Карточки задания — из tasks.json
  useEffect(() => {
    fetch(SCENE.tasksUrl, { cache: 'no-store' })
      .then((r) => r.json())
      .then((d: Task[]) => setTask(d.find((t) => t.id === SCENE.taskId) ?? null))
      .catch((e: Error) => setStatus(e.message))
  }, [])

  const toggle = useCallback((id: string) => setMarked((m) => (m.includes(id) ? m.filter((x) => x !== id) : [...m, id])), [])
  const nearRef = useRef(near)
  nearRef.current = near
  const markedRef = useRef(marked)
  markedRef.current = marked
  const resultRef = useRef(result)
  resultRef.current = result
  /** Карточка, которую отметит E: первая неотмеченная рядом. У одного объекта бывает несколько карточек */
  const nextId = near.find((id) => !marked.includes(id))

  useEffect(() => {
    const engine = new WalkEngine(mountRef.current!, SCENE_URL, WORKER_URL, {
      onNear: setNear,
      onDistB: setDistB,
      onInspectKey: () => {
        const id = nearRef.current.find((x) => !markedRef.current.includes(x))
        if (id) toggle(id)
      },
      onReady: () => setStatus('ready'),
      onError: (m) => setStatus(m),
    })
    engineRef.current = engine
    return () => engine.dispose()
  }, [toggle])

  // Цифры 1–9 отмечают или снимают карточку с этим номером в списке «рядом»
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (resultRef.current || e.repeat || (e.target as HTMLElement).closest('input, textarea, select')) return
      const m = /^(?:Digit|Numpad)([1-9])$/.exec(e.code)
      const id = m && nearRef.current[Number(m[1]) - 1]
      if (id) toggle(id)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggle])

  useEffect(() => engineRef.current?.setMarked(marked), [marked])
  useEffect(() => engineRef.current?.setPaused(!started || !!result), [started, result])
  // Если у задания нет описания ситуации, начинаем сразу
  useEffect(() => {
    if (task && !task.briefing && !started) start()
  }, [task, started])

  const move = (from: string, to: string) =>
    setMarked((m) => {
      const a = [...m]
      a.splice(a.indexOf(to), 0, ...a.splice(a.indexOf(from), 1))
      return a
    })

  const finish = () => task && setResult(scoreTask(task, marked, Math.round((Date.now() - startedAt.current) / 1000), false))

  const itemText = (id: string) => task?.items.find((i) => i.id === id)?.text ?? id
  const atGoal = distB !== null && distB <= GOAL_RADIUS
  const markedTask = task && { ...task, items: marked.map((id) => task.items.find((i) => i.id === id)!).filter(Boolean) }
  const touch = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches

  return (
    <div className="flex h-dvh flex-col">
      <Header onExit={() => (location.href = '/')} />

      <div className="relative flex-1 overflow-hidden bg-[#a9d6f5]">
        <div ref={mountRef} className="absolute inset-0" />

        {status !== 'ready' && (
          <div className="absolute inset-0 flex items-center justify-center bg-navy/70 p-6 text-center text-white">
            {status === 'loading' ? 'Загрузка 3D-сцены…' : `Не удалось загрузить сцену: ${status}`}
          </div>
        )}

        {/* Задание и управление */}
        {/* Ситуация перед началом задания */}
        {status === 'ready' && !started && task?.briefing && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-navy/60 p-3">
            <div className="flex max-h-full w-full max-w-lg flex-col rounded-2xl bg-white shadow-2xl">
              <div className="px-5 pb-2 pt-5">
                <div className="text-xs font-semibold uppercase tracking-wide text-accent">Ситуация</div>
                <h2 className="text-lg font-bold text-navy">{task.title}</h2>
              </div>
              <div className="thin-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-5 pb-4 text-[15px] leading-relaxed text-ink">
                {task.briefing.split(/\n\s*\n/).map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>
              <div className="border-t border-line p-4">
                <button onClick={start} autoFocus className="w-full rounded-[10px] bg-action py-2.5 font-semibold text-white transition hover:bg-action-dark">
                  Начать осмотр
                </button>
              </div>
            </div>
          </div>
        )}

        {hint && status === 'ready' && started && (
          <div className="absolute left-3 top-3 max-w-sm rounded-xl bg-navy/85 p-4 pr-9 text-sm leading-snug text-white shadow-lg backdrop-blur-sm">
            <button onClick={() => setHint(false)} className="absolute right-2.5 top-2.5 opacity-80" aria-label="Закрыть">
              <X className="h-4 w-4" />
            </button>
            <b className="mb-1 block">{task?.title ?? SCENE.title}</b>
            {SCENE.route} По пути подходите к объектам и отмечайте нарушения — в порядке от наиболее критичного.
            <span className="mt-2 block text-white/75">
              {touch ? 'Джойстик — ходьба, проведите по сцене — поворот камеры.' : 'WASD / стрелки — ходьба, Shift — бег, мышь — поворот камеры, колесо — зум, E — отметить следующее, 1–9 — отметить или снять карточку по номеру.'}
            </span>
          </div>
        )}
        {!hint && (
          <button onClick={() => setHint(true)} className="absolute left-3 top-3 rounded-full bg-navy/85 p-2 text-white" aria-label="Подсказка">
            <Info className="h-5 w-5" />
          </button>
        )}

        {/* Отмеченные нарушения — их порядок можно менять перетаскиванием */}
        {markedTask && marked.length > 0 && !result && (
          <div className="thin-scroll absolute right-3 top-3 max-h-[45%] w-72 overflow-y-auto rounded-2xl bg-white/95 p-3 shadow-lg sm:max-h-[60%] sm:w-80">
            <div className="mb-1 text-sm font-bold text-navy">Отмечено: {marked.length}</div>
            <ListCards task={markedTask} img={undefined} selected={marked} onToggle={toggle} onMove={move} />
          </div>
        )}

        {/* Что рядом с игроком */}
        {!result && started && near.length > 0 && (
          <div className="absolute bottom-40 left-1/2 flex w-[min(92vw,420px)] -translate-x-1/2 flex-col gap-2 sm:bottom-6">
            {near.map((id, i) => {
              const n = marked.indexOf(id)
              return (
                <div key={id} className="flex items-center gap-3 rounded-xl bg-white/95 p-2.5 pl-3.5 shadow-lg">
                  {touch ? (
                    <Search className="h-4 w-4 shrink-0 text-accent" />
                  ) : (
                    <kbd className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-line text-xs font-semibold text-muted" title={`Клавиша ${i + 1}`}>
                      {i + 1}
                    </kbd>
                  )}
                  <span className="flex-1 text-sm font-medium text-ink">{itemText(id)}</span>
                  <button
                    onClick={() => toggle(id)}
                    className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-semibold ${n >= 0 ? 'border border-line text-muted' : 'bg-action text-white'}`}
                  >
                    {n >= 0 ? `№${n + 1} · снять` : 'Отметить'}
                    {id === nextId && !touch && <kbd className="ml-1.5 rounded bg-white/20 px-1 text-xs">E</kbd>}
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* До точки B и завершение */}
        {!result && started && status === 'ready' && (
          <div className="absolute bottom-3 right-3 flex items-center gap-2">
            {distB !== null && !atGoal && (
              <span className="rounded-lg bg-navy/85 px-3 py-2 text-sm font-semibold text-white">До точки B: {distB} м</span>
            )}
            <button
              onClick={finish}
              disabled={!atGoal}
              className="flex items-center gap-2 rounded-[10px] bg-action px-4 py-2.5 font-semibold text-white shadow-lg transition hover:bg-action-dark disabled:opacity-50"
              title={atGoal ? '' : 'Сначала дойдите до точки B'}
            >
              <Flag className="h-4 w-4" /> Завершить осмотр
            </button>
          </div>
        )}

        {touch && !result && started && status === 'ready' && <Joystick onChange={(x, y) => engineRef.current?.setStick(x, y)} />}

        {/* Разбор — тот же, что в основном тренажёре */}
        {result && task && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-navy/60 p-3">
            <div className="flex max-h-full w-full max-w-lg flex-col rounded-2xl bg-white shadow-2xl">
              <h2 className="px-5 pb-2 pt-5 text-lg font-bold text-navy">Разбор: {task.title}</h2>
              <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-5 pb-3">
                <ReviewList task={task} img={undefined} result={result} hoveredId={null} onHover={() => {}} />
              </div>
              <div className="grid grid-cols-2 gap-3 border-t border-line p-4">
                <button onClick={() => location.reload()} className="rounded-[10px] border-2 border-action py-2.5 font-semibold text-action">
                  Ещё раз
                </button>
                <a href="/" className="rounded-[10px] bg-action py-2.5 text-center font-semibold text-white">
                  В тренажёр
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** Экранный джойстик для телефона */
function Joystick({ onChange }: { onChange: (x: number, y: number) => void }) {
  const [knob, setKnob] = useState({ x: 0, y: 0 })
  const base = useRef<HTMLDivElement>(null)
  const R = 48

  const update = (e: React.PointerEvent) => {
    const r = base.current!.getBoundingClientRect()
    let dx = e.clientX - (r.left + r.width / 2)
    let dy = e.clientY - (r.top + r.height / 2)
    const len = Math.hypot(dx, dy)
    if (len > R) {
      dx = (dx / len) * R
      dy = (dy / len) * R
    }
    setKnob({ x: dx, y: dy })
    onChange(dx / R, -dy / R)
  }
  const end = () => {
    setKnob({ x: 0, y: 0 })
    onChange(0, 0)
  }

  return (
    <div
      ref={base}
      className="absolute bottom-5 left-5 h-32 w-32 touch-none rounded-full border-2 border-white/60 bg-navy/30 backdrop-blur-sm"
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId)
        update(e)
      }}
      onPointerMove={(e) => e.buttons && update(e)}
      onPointerUp={end}
      onPointerCancel={end}
    >
      <div
        className="absolute left-1/2 top-1/2 h-14 w-14 rounded-full bg-white/90 shadow-lg"
        style={{ transform: `translate(calc(-50% + ${knob.x}px), calc(-50% + ${knob.y}px))` }}
      />
    </div>
  )
}
