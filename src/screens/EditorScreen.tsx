import { useEffect, useRef, useState } from 'react'
import { Copy, ImagePlus, ListOrdered, Plus, Trash2 } from 'lucide-react'
import { config } from '../config'
import { Thumb } from '../components/Thumb'
import { loadDraft, saveDraft } from '../lib/storage'
import type { Area, Layout, Task, TaskItem } from '../types'

/**
 * Скрытая страница /editor — разметка сцен мышкой.
 * Загрузите картинку, обведите прямоугольник — появится карточка; заполните текст, ранг и пояснение.
 * «Скопировать JSON» — задание целиком, «Скопировать весь tasks.json» — с заменой этого задания в файле.
 */

const DRAFT_KEY = 'biot.editor.draft.v1'

const emptyTask = (): Task => ({ id: 't1', title: 'Новое задание', image: '/scenes/t1.webp', layout: 'list', timeLimitSec: config.defaultTimeLimitSec, items: [] })

type Drag =
  | { kind: 'draw'; x0: number; y0: number }
  | { kind: 'move'; id: string; dx: number; dy: number }
  | { kind: 'resize'; id: string; corner: 'tl' | 'br' }

const r1 = (v: number) => Math.round(v * 10) / 10
const clamp = (v: number, a = 0, b = 100) => Math.min(b, Math.max(a, v))

export default function EditorScreen() {
  const [task, setTask] = useState<Task>(() => loadDraft<Task>(DRAFT_KEY) ?? emptyTask())
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [img, setImg] = useState<{ src: string; w: number; h: number; isPlaceholder: false } | null>(null)
  const [imgError, setImgError] = useState(false)
  const [selId, setSelId] = useState<string | null>(null)
  const [draft, setDraft] = useState<Area | null>(null)
  const [toast, setToast] = useState('')
  const drag = useRef<Drag | null>(null)
  const layer = useRef<HTMLDivElement>(null)

  // Черновик сохраняется в браузере, чтобы не потерять разметку при перезагрузке
  useEffect(() => saveDraft(DRAFT_KEY, task), [task])

  useEffect(() => {
    fetch(config.tasksUrl, { cache: 'no-store' })
      .then((r) => r.json())
      .then((d) => setAllTasks(Array.isArray(d) ? d : (d.tasks ?? [])))
      .catch(() => setAllTasks([]))
  }, [])

  // Загружаем картинку: выбранный файл или путь из задания
  const src = fileUrl ?? task.image
  useEffect(() => {
    let alive = true
    setImgError(false)
    const el = new Image()
    el.onload = () => alive && setImg({ src, w: el.naturalWidth, h: el.naturalHeight, isPlaceholder: false })
    el.onerror = () => {
      if (!alive) return
      setImg(null)
      setImgError(true)
    }
    el.src = src
    return () => {
      alive = false
    }
  }, [src])

  const sel = task.items.find((i) => i.id === selId) ?? null
  const patchTask = (p: Partial<Task>) => setTask((t) => ({ ...t, ...p }))
  const patchItem = (id: string, p: Partial<TaskItem>) => setTask((t) => ({ ...t, items: t.items.map((i) => (i.id === id ? { ...i, ...p } : i)) }))
  const patchArea = (id: string, a: Partial<Area>) =>
    setTask((t) => ({ ...t, items: t.items.map((i) => (i.id === id ? { ...i, area: { ...i.area, ...a } } : i)) }))
  const removeItem = (id: string) => {
    setTask((t) => ({ ...t, items: t.items.filter((i) => i.id !== id) }))
    setSelId(null)
  }

  // Delete / Backspace удаляет выбранную область (если фокус не в поле ввода)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (selId && (e.key === 'Delete' || e.key === 'Backspace') && !['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) removeItem(selId)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  /** Координаты указателя в процентах от картинки */
  const pct = (e: React.PointerEvent) => {
    const r = layer.current!.getBoundingClientRect()
    return { x: clamp(((e.clientX - r.left) / r.width) * 100), y: clamp(((e.clientY - r.top) / r.height) * 100) }
  }

  const onDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return
    layer.current!.setPointerCapture(e.pointerId)
    const p = pct(e)
    const t = e.target as HTMLElement
    const id = t.closest<HTMLElement>('[data-item]')?.dataset.item
    const corner = t.dataset.corner as 'tl' | 'br' | undefined
    if (id && corner) drag.current = { kind: 'resize', id, corner }
    else if (id) {
      const a = task.items.find((i) => i.id === id)!.area
      drag.current = { kind: 'move', id, dx: p.x - a.x, dy: p.y - a.y }
    } else {
      drag.current = { kind: 'draw', x0: p.x, y0: p.y }
      setDraft({ x: p.x, y: p.y, w: 0, h: 0 })
    }
    setSelId(id ?? null)
  }

  const onMove = (e: React.PointerEvent) => {
    const d = drag.current
    if (!d) return
    const p = pct(e)
    if (d.kind === 'draw') {
      setDraft({ x: Math.min(d.x0, p.x), y: Math.min(d.y0, p.y), w: Math.abs(p.x - d.x0), h: Math.abs(p.y - d.y0) })
    } else if (d.kind === 'move') {
      const a = task.items.find((i) => i.id === d.id)!.area
      patchArea(d.id, { x: r1(clamp(p.x - d.dx, 0, 100 - a.w)), y: r1(clamp(p.y - d.dy, 0, 100 - a.h)) })
    } else {
      const a = task.items.find((i) => i.id === d.id)!.area
      if (d.corner === 'br') patchArea(d.id, { w: r1(Math.max(1, p.x - a.x)), h: r1(Math.max(1, p.y - a.y)) })
      else {
        const x2 = a.x + a.w
        const y2 = a.y + a.h
        const nx = Math.min(p.x, x2 - 1)
        const ny = Math.min(p.y, y2 - 1)
        patchArea(d.id, { x: r1(nx), y: r1(ny), w: r1(x2 - nx), h: r1(y2 - ny) })
      }
    }
  }

  const onUp = () => {
    const d = drag.current
    drag.current = null
    if (d?.kind === 'draw' && draft) {
      setDraft(null)
      if (draft.w < 1 || draft.h < 1) return // случайный клик, а не обводка
      let n = task.items.length + 1
      while (task.items.some((i) => i.id === `item-${n}`)) n++
      const violations = task.items.filter((i) => i.isViolation).length
      const item: TaskItem = {
        id: `item-${n}`,
        text: '',
        isViolation: true,
        rank: violations + 1,
        area: { x: r1(draft.x), y: r1(draft.y), w: r1(draft.w), h: r1(draft.h) },
        explanation: '',
      }
      setTask((t) => ({ ...t, items: [...t.items, item] }))
      setSelId(item.id)
    }
  }

  const onFile = (f: File | undefined) => {
    if (!f) return
    if (fileUrl) URL.revokeObjectURL(fileUrl)
    setFileUrl(URL.createObjectURL(f))
    patchTask({ image: `/scenes/${f.name}` })
  }

  const loadTask = (id: string) => {
    if (id === '__new') {
      setTask(emptyTask())
    } else {
      const t = allTasks.find((x) => x.id === id)
      if (t) setTask(structuredClone(t))
    }
    setFileUrl(null)
    setSelId(null)
  }

  /** Ранги 1..N по текущему порядку нарушений в списке */
  const renumber = () => {
    let r = 0
    setTask((t) => ({ ...t, items: t.items.map((i) => (i.isViolation ? { ...i, rank: ++r } : i)) }))
  }

  // Готовый JSON: у отвлекающих вариантов rank убираем, пустой rule не выводим
  const clean = (t: Task): Task => ({
    ...t,
    items: t.items.map(({ rank, rule, ...i }) => ({ ...i, ...(i.isViolation ? { rank } : {}), ...(rule ? { rule } : {}) })),
  })
  const taskJson = JSON.stringify(clean(task), null, 2)
  const fullJson = () => {
    const list = allTasks.some((t) => t.id === task.id) ? allTasks.map((t) => (t.id === task.id ? clean(task) : t)) : [...allTasks, clean(task)]
    return JSON.stringify(list, null, 2)
  }

  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Запасной вариант для http или старых браузеров
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
    }
    setToast(`${what} скопирован`)
    setTimeout(() => setToast(''), 2000)
  }

  // Проверки разметки
  const ranks = task.items.filter((i) => i.isViolation).map((i) => i.rank ?? 0)
  const warnings: string[] = []
  if (new Set(ranks).size !== ranks.length) warnings.push('Есть повторяющиеся ранги')
  if (ranks.some((r, _, a) => r < 1 || r > a.length)) warnings.push(`Ранги должны быть от 1 до ${ranks.length}`)
  if (task.items.some((i) => !i.text.trim())) warnings.push('Есть карточки без текста')
  if (new Set(task.items.map((i) => i.id)).size !== task.items.length) warnings.push('Повторяются id карточек')
  if (task.layout === 'grid' && task.items.length !== 6) warnings.push('Для сетки 3×2 нужно ровно 6 карточек')

  const input = 'w-full rounded-lg border border-line bg-white px-2.5 py-1.5 text-sm outline-none focus:border-accent'

  return (
    <div className="min-h-dvh">
      <header className="flex h-14 items-center gap-3 bg-navy px-4 text-white">
        <img src="/logo.svg" alt="" className="h-8 w-8 rounded-md bg-white p-0.5" />
        <span className="font-semibold">Редактор сцен · БИОТ</span>
        <a href="/" className="ml-auto text-sm text-white/80 underline-offset-2 hover:underline">
          К тренажёру
        </a>
      </header>

      <div className="grid gap-4 p-4 xl:grid-cols-[1fr_420px]">
        {/* Левая часть: параметры задания и холст */}
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-end gap-3 rounded-xl bg-white p-3 shadow-sm">
            <Field label="Задание из tasks.json">
              <select className={input} value={allTasks.some((t) => t.id === task.id) ? task.id : '__new'} onChange={(e) => loadTask(e.target.value)}>
                <option value="__new">— новое —</option>
                {allTasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.id} · {t.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="id" className="w-24">
              <input className={input} value={task.id} onChange={(e) => patchTask({ id: e.target.value.trim() })} />
            </Field>
            <Field label="Название" className="min-w-48 flex-1">
              <input className={input} value={task.title} onChange={(e) => patchTask({ title: e.target.value })} />
            </Field>
            <Field label="Картинка (путь)" className="min-w-44 flex-1">
              <input className={input} value={task.image} onChange={(e) => (setFileUrl(null), patchTask({ image: e.target.value }))} />
            </Field>
            <Field label="Панель" className="w-28">
              <select className={input} value={task.layout} onChange={(e) => patchTask({ layout: e.target.value as Layout })}>
                <option value="list">list</option>
                <option value="grid">grid</option>
              </select>
            </Field>
            <Field label="Время, сек" className="w-24">
              <input type="number" min={5} className={input} value={task.timeLimitSec ?? ''} onChange={(e) => patchTask({ timeLimitSec: Number(e.target.value) || undefined })} />
            </Field>
            <label className="flex cursor-pointer items-center gap-2 rounded-lg bg-action px-3 py-2 text-sm font-semibold text-white hover:bg-action-dark">
              <ImagePlus className="h-4 w-4" /> Загрузить картинку
              <input type="file" accept="image/*" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
            </label>
          </div>

          <p className="px-1 text-sm text-muted">
            Обведите мышкой область на картинке — появится карточка. Перетаскивайте область за середину, размер меняйте за углы. Delete — удалить
            выбранную.
          </p>

          <div className="flex justify-center rounded-xl bg-navy p-3">
            {img ? (
              <div
                ref={layer}
                className="relative w-full touch-none select-none"
                style={{ aspectRatio: `${img.w} / ${img.h}`, maxWidth: `calc(78vh * ${img.w / img.h})`, cursor: 'crosshair' }}
                onPointerDown={onDown}
                onPointerMove={onMove}
                onPointerUp={onUp}
                onPointerCancel={onUp}
              >
                <img src={img.src} alt="" draggable={false} className="pointer-events-none h-full w-full" />
                {task.items.map((it) => {
                  const active = it.id === selId
                  return (
                    <div
                      key={it.id}
                      data-item={it.id}
                      className={`absolute cursor-move border-2 ${
                        it.isViolation ? 'border-bad bg-bad/15' : 'border-ok bg-ok/15'
                      } ${active ? 'z-10 outline-2 outline-offset-1 outline-white' : ''}`}
                      style={{ left: `${it.area.x}%`, top: `${it.area.y}%`, width: `${it.area.w}%`, height: `${it.area.h}%` }}
                    >
                      <span className={`absolute left-0 top-0 max-w-full truncate px-1 text-[11px] font-semibold text-white ${it.isViolation ? 'bg-bad' : 'bg-ok'}`}>
                        {it.isViolation ? `${it.rank}. ` : '○ '}
                        {it.text || it.id}
                      </span>
                      {active && (
                        <>
                          <span data-corner="tl" className="absolute -left-1.5 -top-1.5 h-3 w-3 cursor-nwse-resize rounded-sm border border-navy bg-white" />
                          <span data-corner="br" className="absolute -bottom-1.5 -right-1.5 h-3 w-3 cursor-nwse-resize rounded-sm border border-navy bg-white" />
                        </>
                      )}
                    </div>
                  )
                })}
                {draft && (
                  <div
                    className="pointer-events-none absolute border-2 border-dashed border-white bg-white/20"
                    style={{ left: `${draft.x}%`, top: `${draft.y}%`, width: `${draft.w}%`, height: `${draft.h}%` }}
                  />
                )}
              </div>
            ) : (
              <div className="py-24 text-center text-white/80">
                {imgError ? `Картинка «${task.image}» не найдена — загрузите файл кнопкой выше` : 'Загрузка картинки…'}
              </div>
            )}
          </div>
          {fileUrl && (
            <p className="px-1 text-xs text-muted">
              Картинка загружена только в браузер. Положите файл в <code>public{task.image}</code>, чтобы он появился в тренажёре.
            </p>
          )}
        </div>

        {/* Правая часть: карточки и JSON */}
        <div className="flex flex-col gap-3">
          {sel && (
            <div className="rounded-xl bg-white p-3 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-bold text-navy">Карточка</span>
                <button onClick={() => removeItem(sel.id)} className="flex items-center gap-1 text-sm text-bad hover:underline">
                  <Trash2 className="h-4 w-4" /> Удалить
                </button>
              </div>
              <div className="flex gap-3">
                <Thumb img={img} area={sel.area} className="h-20 w-28 rounded-md" />
                <div className="flex flex-1 flex-col gap-2">
                  <Field label="id">
                    <input className={input} value={sel.id} onChange={(e) => (patchItem(sel.id, { id: e.target.value }), setSelId(e.target.value))} />
                  </Field>
                  <div className="flex gap-2">
                    <label className="flex items-center gap-1.5 text-sm">
                      <input type="checkbox" checked={sel.isViolation} onChange={(e) => patchItem(sel.id, { isViolation: e.target.checked })} />
                      Нарушение
                    </label>
                    {sel.isViolation && (
                      <label className="ml-auto flex items-center gap-1.5 text-sm">
                        Ранг
                        <input
                          type="number"
                          min={1}
                          className={`${input} w-16`}
                          value={sel.rank ?? ''}
                          onChange={(e) => patchItem(sel.id, { rank: Number(e.target.value) || undefined })}
                        />
                      </label>
                    )}
                  </div>
                </div>
              </div>
              <Field label="Текст карточки" className="mt-2">
                <input className={input} value={sel.text} onChange={(e) => patchItem(sel.id, { text: e.target.value })} placeholder="Отсутствует каска" />
              </Field>
              <Field label="Пояснение" className="mt-2">
                <textarea rows={3} className={input} value={sel.explanation} onChange={(e) => patchItem(sel.id, { explanation: e.target.value })} />
              </Field>
              <Field label="Пункт правил (необязательно)" className="mt-2">
                <input className={input} value={sel.rule ?? ''} onChange={(e) => patchItem(sel.id, { rule: e.target.value })} placeholder="Правила ..., п. 12" />
              </Field>
              <div className="mt-2 grid grid-cols-4 gap-2">
                {(['x', 'y', 'w', 'h'] as const).map((k) => (
                  <Field key={k} label={`${k}, %`}>
                    <input type="number" step={0.1} className={input} value={sel.area[k]} onChange={(e) => patchArea(sel.id, { [k]: Number(e.target.value) })} />
                  </Field>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-xl bg-white p-3 shadow-sm">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-bold text-navy">Карточки ({task.items.length})</span>
              <button onClick={renumber} className="flex items-center gap-1 text-sm text-action hover:underline" title="Нарушения получат ранги 1..N в порядке списка">
                <ListOrdered className="h-4 w-4" /> Ранги по порядку
              </button>
            </div>
            {task.items.length === 0 && (
              <p className="flex items-center gap-1.5 text-sm text-muted">
                <Plus className="h-4 w-4" /> Обведите первую область на картинке
              </p>
            )}
            <ul className="flex flex-col gap-1.5">
              {task.items.map((it, idx) => (
                <li key={it.id}>
                  <div
                    className={`flex w-full items-center gap-2 rounded-lg border p-1.5 text-sm ${it.id === selId ? 'border-accent bg-accent/5' : 'border-line'}`}
                  >
                    <button onClick={() => setSelId(it.id)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
                      <Thumb img={img} area={it.area} className="h-9 w-12 rounded" />
                      <span className={`w-6 shrink-0 text-center font-bold ${it.isViolation ? 'text-bad' : 'text-ok'}`}>{it.isViolation ? it.rank : '○'}</span>
                      <span className="truncate">{it.text || <i className="text-muted">без текста</i>}</span>
                    </button>
                    <span className="flex shrink-0 flex-col">
                      <button disabled={idx === 0} onClick={() => swap(idx, idx - 1)} className="px-1 text-xs leading-none text-muted disabled:opacity-30" aria-label="Выше">
                        ▲
                      </button>
                      <button disabled={idx === task.items.length - 1} onClick={() => swap(idx, idx + 1)} className="px-1 text-xs leading-none text-muted disabled:opacity-30" aria-label="Ниже">
                        ▼
                      </button>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
            {warnings.length > 0 && (
              <ul className="mt-3 list-inside list-disc rounded-lg bg-miss/10 p-2 text-xs text-miss">
                {warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl bg-white p-3 shadow-sm">
            <div className="mb-2 flex flex-wrap gap-2">
              <button onClick={() => copy(taskJson, 'JSON задания')} className="flex items-center gap-1.5 rounded-lg bg-action px-3 py-2 text-sm font-semibold text-white hover:bg-action-dark">
                <Copy className="h-4 w-4" /> Скопировать JSON
              </button>
              <button
                onClick={() => copy(fullJson(), 'tasks.json')}
                className="flex items-center gap-1.5 rounded-lg border border-action px-3 py-2 text-sm font-semibold text-action hover:bg-action/5"
                title="Весь файл tasks.json, в котором это задание заменено (или добавлено)"
              >
                <Copy className="h-4 w-4" /> Скопировать весь tasks.json
              </button>
            </div>
            <textarea readOnly rows={12} value={taskJson} className="w-full rounded-lg border border-line bg-page p-2 font-mono text-xs" onFocus={(e) => e.target.select()} />
          </div>
        </div>
      </div>

      {toast && <div className="fixed bottom-5 left-1/2 -translate-x-1/2 rounded-lg bg-navy px-4 py-2 text-sm text-white shadow-lg">{toast}</div>}
    </div>
  )

  function swap(a: number, b: number) {
    setTask((t) => {
      const items = [...t.items]
      ;[items[a], items[b]] = [items[b], items[a]]
      return { ...t, items }
    })
  }
}

function Field({ label, className = '', children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-semibold text-muted">{label}</span>
      {children}
    </label>
  )
}
