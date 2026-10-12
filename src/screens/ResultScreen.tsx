import { useMemo, useRef, useState } from 'react'
import { CheckCircle2, Download, RotateCcw, XCircle } from 'lucide-react'
import { config } from '../config'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Header } from '../components/Header'
import { formatDate, mmss } from '../lib/format'
import { elementToPdf } from '../lib/pdf'
import { playerPosition } from '../lib/review'
import { totals } from '../lib/scoring'
import { useGame } from '../store/useGame'
import type { Task, TaskResult } from '../types'

/** Ошибки по заданию: пропущенные нарушения, лишние выборы, нарушения не на своём месте */
function mistakes(task: Task, r: TaskResult) {
  const missed = task.items.filter((i) => i.isViolation && !r.selected.includes(i.id))
  const extra = task.items.filter((i) => !i.isViolation && r.selected.includes(i.id))
  const misplaced = task.items
    .filter((i) => i.isViolation && r.selected.includes(i.id))
    .map((i) => ({ item: i, mine: playerPosition(task, r.selected, i.id) }))
    .filter((x) => x.mine !== x.item.rank)
  return { missed, extra, misplaced }
}

export function ResultScreen() {
  const { tasks, results, player, restart, exit } = useGame()
  const t = totals(results)
  const finishedAt = useMemo(() => new Date(), [])
  const sheetRef = useRef<HTMLDivElement>(null)
  const [busy, setBusy] = useState(false)
  const [exitOpen, setExitOpen] = useState(false)

  const download = async () => {
    if (!sheetRef.current) return
    setBusy(true)
    try {
      const name = (player?.fio ?? 'result').replace(/\s+/g, '_')
      await elementToPdf(sheetRef.current, `БИОТ_${name}_${finishedAt.toISOString().slice(0, 10)}.pdf`)
    } catch (e) {
      alert('Не удалось сформировать PDF: ' + (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <Header onExit={() => setExitOpen(true)} />
      <main className="mx-auto w-full max-w-4xl flex-1 p-3 sm:p-6">
        <section className="rounded-2xl bg-white p-5 shadow-[0_8px_30px_rgba(11,42,91,.12)] sm:p-8">
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
            <ScoreRing percent={t.percent} passed={t.passed} />
            <div className="flex-1 text-center sm:text-left">
              <div className="text-sm text-muted">{player?.fio}</div>
              <div
                className={`mt-2 inline-flex items-center gap-2 rounded-full px-4 py-2 text-lg font-bold text-white ${t.passed ? 'bg-ok' : 'bg-bad'}`}
              >
                {t.passed ? <CheckCircle2 className="h-6 w-6" /> : <XCircle className="h-6 w-6" />}
                {t.passed ? 'Допущен к работе' : 'Не допущен'}
              </div>
              <div className="mt-3 flex flex-wrap justify-center gap-x-6 gap-y-1 text-sm text-muted sm:justify-start">
                <span>
                  Баллы: <b className="tabular text-ink">{t.score} из {t.max}</b>
                </span>
                <span>
                  Время: <b className="tabular text-ink">{mmss(t.timeSec)}</b>
                </span>
                <span>
                  Порог: <b className="text-ink">{config.passThresholdPercent}%</b>
                </span>
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <button
              onClick={restart}
              className="flex items-center justify-center gap-2 rounded-[10px] border-2 border-action py-3 font-semibold text-action transition hover:bg-action/5"
            >
              <RotateCcw className="h-5 w-5" /> Пройти заново
            </button>
            <button
              onClick={download}
              disabled={busy}
              className="flex items-center justify-center gap-2 rounded-[10px] bg-action py-3 font-semibold text-white transition hover:bg-action-dark disabled:opacity-60"
            >
              <Download className="h-5 w-5" /> {busy ? 'Формируем PDF…' : 'Скачать результат'}
            </button>
          </div>
        </section>

        <h2 className="mb-3 mt-8 px-1 text-lg font-bold text-navy">Разбор ошибок по заданиям</h2>
        <div className="flex flex-col gap-3">
          {results.map((r, i) => {
            const task = tasks.find((x) => x.id === r.taskId)
            return task ? <TaskBreakdown key={r.taskId} n={i + 1} task={task} r={r} /> : null
          })}
        </div>
      </main>

      {/* Бланк для PDF: рендерится за пределами экрана */}
      <div className="fixed -left-[10000px] top-0" aria-hidden>
        <ResultSheet ref={sheetRef} tasks={tasks} results={results} finishedAt={finishedAt} />
      </div>

      <ConfirmDialog
        open={exitOpen}
        title="Вернуться на старт?"
        text="Результат уже сохранён в истории этого браузера."
        okText="Выйти"
        onOk={exit}
        onCancel={() => setExitOpen(false)}
      />
    </div>
  )
}

function ScoreRing({ percent, passed }: { percent: number; passed: boolean }) {
  const r = 52
  const c = 2 * Math.PI * r
  return (
    <div className="relative h-36 w-36 shrink-0">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#E6EBF3" strokeWidth="10" />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={passed ? 'var(--color-ok)' : 'var(--color-bad)'}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${(c * percent) / 100} ${c}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="tabular text-4xl font-bold text-navy">{percent}%</span>
      </div>
    </div>
  )
}

function TaskBreakdown({ n, task, r }: { n: number; task: Task; r: TaskResult }) {
  const m = mistakes(task, r)
  const clean = !m.missed.length && !m.extra.length && !m.misplaced.length
  return (
    <details className="group rounded-xl border border-line bg-white" open={!clean}>
      <summary className="flex cursor-pointer list-none items-center gap-3 p-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy text-sm font-bold text-white">{n}</span>
        <span className="min-w-0 flex-1 font-semibold text-ink">{task.title}</span>
        {r.timedOut && <span className="hidden rounded-full bg-bad/10 px-2 py-0.5 text-xs font-semibold text-bad sm:inline">время вышло</span>}
        <span className={`tabular font-bold ${clean ? 'text-ok' : 'text-navy'}`}>
          {r.score}/{r.maxScore}
        </span>
      </summary>
      <div className="border-t border-line px-4 pb-4 pt-3 text-sm">
        {clean ? (
          <p className="text-ok">Все нарушения найдены, порядок верный.</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {m.missed.map((i) => (
              <Li key={i.id} tone="miss" label="Пропущено" text={i.text} note={i.explanation} rule={i.rule} />
            ))}
            {m.extra.map((i) => (
              <Li key={i.id} tone="bad" label="Лишнее" text={i.text} note={i.explanation} rule={i.rule} />
            ))}
            {m.misplaced.map(({ item, mine }) => (
              <Li key={item.id} tone="muted" label={`Порядок: ваш ${mine}, верный ${item.rank}`} text={item.text} />
            ))}
          </ul>
        )}
      </div>
    </details>
  )
}

function Li({ tone, label, text, note, rule }: { tone: 'miss' | 'bad' | 'muted'; label: string; text: string; note?: string; rule?: string }) {
  const color = tone === 'miss' ? 'bg-miss/10 text-miss' : tone === 'bad' ? 'bg-bad/10 text-bad' : 'bg-page text-muted'
  return (
    <li>
      <span className={`mr-2 rounded px-1.5 py-0.5 text-xs font-semibold ${color}`}>{label}</span>
      <span className="font-medium text-ink">{text}</span>
      {note && (
        <span className="mt-0.5 block text-[13px] text-muted">
          {note} {rule && <b className="text-action">{rule}</b>}
        </span>
      )}
    </li>
  )
}

/** Бланк результата для PDF (фиксированная ширина A4 при 96 dpi) */
function ResultSheet({ ref, tasks, results, finishedAt }: { ref: React.Ref<HTMLDivElement>; tasks: Task[]; results: TaskResult[]; finishedAt: Date }) {
  const player = useGame((s) => s.player)
  const t = totals(results)
  return (
    <div ref={ref} style={{ width: 794, padding: 56, background: '#fff', color: '#13233F', fontFamily: 'Inter Variable, Inter, sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, borderBottom: '3px solid #0B2A5B', paddingBottom: 16 }}>
        <img src="/logo.svg" alt="" style={{ width: 48, height: 48 }} />
        <div>
          <div style={{ fontWeight: 700, letterSpacing: 1, color: '#0B2A5B' }}>КАЗАХТЕЛЕКОМ</div>
          <div style={{ fontSize: 13, color: '#5F6F89' }}>БИОТ – Допуск к работе · результат тестирования</div>
        </div>
      </div>

      <table style={{ marginTop: 24, fontSize: 14, borderCollapse: 'collapse', width: '100%' }}>
        <tbody>
          {[
            ['ФИО', player?.fio],
            ['Табельный номер', player?.tabNo],
            ['Подразделение', player?.department],
            ['Дата и время', formatDate(finishedAt)],
            ['Время прохождения', mmss(t.timeSec)],
          ].map(([k, v]) => (
            <tr key={k}>
              <td style={{ padding: '5px 0', color: '#5F6F89', width: 200 }}>{k}</td>
              <td style={{ padding: '5px 0', fontWeight: 600 }}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 24, padding: 20, borderRadius: 12, background: '#EEF2F8' }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: '#0B2A5B' }}>{t.percent}%</div>
        <div>
          <div style={{ fontSize: 14, color: '#5F6F89' }}>
            Баллы: {t.score} из {t.max} · порог {config.passThresholdPercent}%
          </div>
          <div style={{ marginTop: 6, fontSize: 20, fontWeight: 700, color: t.passed ? '#16A34A' : '#DC2626' }}>
            {t.passed ? 'ДОПУЩЕН К РАБОТЕ' : 'НЕ ДОПУЩЕН'}
          </div>
        </div>
      </div>

      <table style={{ marginTop: 24, width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#0B2A5B', color: '#fff', textAlign: 'left' }}>
            {['№', 'Задание', 'Найдено', 'Лишних', 'Порядок', 'Баллы'].map((h) => (
              <th key={h} style={{ padding: '8px 10px', fontWeight: 600 }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={r.taskId} style={{ borderBottom: '1px solid #DCE3EE' }}>
              <td style={{ padding: '8px 10px' }}>{i + 1}</td>
              <td style={{ padding: '8px 10px' }}>{tasks.find((x) => x.id === r.taskId)?.title ?? r.title}</td>
              <td style={{ padding: '8px 10px' }}>
                {r.found}/{r.totalViolations}
              </td>
              <td style={{ padding: '8px 10px' }}>{r.extras}</td>
              <td style={{ padding: '8px 10px' }}>{r.perfectOrder ? 'верный' : `${Math.round(r.orderRatio * 100)}%`}</td>
              <td style={{ padding: '8px 10px', fontWeight: 600 }}>
                {r.score}/{r.maxScore}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: 56, display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#5F6F89' }}>
        <span>Подпись работника ____________________</span>
        <span>Проверил ____________________</span>
      </div>
    </div>
  )
}
