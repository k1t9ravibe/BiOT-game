import { useEffect, useState } from 'react'
import { BookOpen, CheckCircle2, ChevronLeft, Footprints, RotateCcw, XCircle } from 'lucide-react'
import { config } from '../config'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Header } from '../components/Header'
import { mmss } from '../lib/format'
import { saveDraft, loadDraft, saveLastPlayer } from '../lib/storage'
import type { Player, TaskResult } from '../types'
import { PlayerForm } from './StartScreen'
import { SCENES, WalkGame } from './Walk3DScreen'

/**
 * Экзамен (/exam): вход → блок теоретических вопросов → переход в симулятор →
 * сцены режима ходьбы по очереди (следующая — после завершения задания) → сводка «сдан / не сдан».
 * Вопросы — public/exam-theory.json, сцены и порог — config.exam / config.passThresholdPercent.
 */

interface Question {
  id: string
  text: string
  options: string[]
  /** Индекс верного варианта */
  correct: number
  explanation?: string
  rule?: string
}
interface TheoryBlock {
  id: string
  title: string
  questions: Question[]
}

type Step = { kind: 'login' } | { kind: 'theory' } | { kind: 'toSim' } | { kind: 'scene'; index: number } | { kind: 'summary' }

const SCENE_IDS = config.exam.scenes.filter((s) => SCENES[s])
/** Этапы в шапке: теория + сцены */
const STAGES = 1 + SCENE_IDS.length
const KEY_HISTORY = 'biot.exam.history.v1'

const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0)

export default function ExamScreen() {
  const [blocks, setBlocks] = useState<TheoryBlock[] | null>(null)
  const [error, setError] = useState('')
  const [step, setStep] = useState<Step>({ kind: 'login' })
  const [player, setPlayer] = useState<Player | null>(null)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [sceneResults, setSceneResults] = useState<TaskResult[]>([])
  const [startedAt, setStartedAt] = useState(0)
  const [exitOpen, setExitOpen] = useState(false)

  useEffect(() => {
    fetch(config.exam.theoryUrl, { cache: 'no-store' })
      .then((r) => r.json())
      .then(setBlocks)
      .catch((e: Error) => setError(e.message))
  }, [])

  const questions = blocks?.flatMap((b) => b.questions) ?? []
  const theoryRight = questions.filter((q) => answers[q.id] === q.correct).length
  const theoryPercent = pct(theoryRight, questions.length)
  const simScore = sceneResults.reduce((s, r) => s + r.score, 0)
  const simMax = sceneResults.reduce((s, r) => s + r.maxScore, 0)
  const simPercent = pct(simScore, simMax)
  const theoryPassed = theoryPercent >= config.passThresholdPercent
  const simPassed = simPercent >= config.passThresholdPercent
  const passed = theoryPassed && simPassed

  const reset = () => {
    setAnswers({})
    setSceneResults([])
    setStep({ kind: 'login' })
    setExitOpen(false)
  }
  const askExit = () => setExitOpen(true)

  const sceneDone = (r: TaskResult) => {
    const results = [...sceneResults, r]
    setSceneResults(results)
    if (step.kind === 'scene' && step.index + 1 < SCENE_IDS.length) setStep({ kind: 'scene', index: step.index + 1 })
    else finish(results)
  }

  const finish = (results: TaskResult[]) => {
    const score = results.reduce((s, r) => s + r.score, 0)
    const max = results.reduce((s, r) => s + r.maxScore, 0)
    const history = loadDraft<unknown[]>(KEY_HISTORY) ?? []
    history.unshift({
      player,
      finishedAt: new Date().toISOString(),
      theoryPercent,
      simPercent: pct(score, max),
      passed: theoryPassed && pct(score, max) >= config.passThresholdPercent,
      answers,
      sceneResults: results,
    })
    saveDraft(KEY_HISTORY, history.slice(0, 50))
    setStep({ kind: 'summary' })
  }

  if (error) return <Center>Не удалось загрузить вопросы ({config.exam.theoryUrl}): {error}</Center>
  if (!blocks) return <Center>Загрузка…</Center>

  const exitDialog = (
    <ConfirmDialog
      open={exitOpen}
      title="Прервать экзамен?"
      text="Ответы этой попытки не сохранятся."
      okText="Прервать"
      onOk={reset}
      onCancel={() => setExitOpen(false)}
    />
  )

  if (step.kind === 'login')
    return (
      <PlayerForm
        title="БИОТ – Экзамен"
        description={`Экзамен из двух частей: ${questions.length} теоретических вопросов, затем симулятор — ${SCENE_IDS.length} ${SCENE_IDS.length === 1 ? 'сцена' : 'сцены'}, где нужно найти нарушения. Для сдачи нужно набрать не менее ${config.passThresholdPercent}% в каждой части.`}
        onSubmit={(p) => {
          saveLastPlayer(p)
          setPlayer(p)
          setStartedAt(Date.now())
          setStep({ kind: 'theory' })
        }}
      />
    )

  if (step.kind === 'theory')
    return (
      <>
        <Theory
          blocks={blocks}
          answers={answers}
          onAnswer={(id, i) => setAnswers((a) => ({ ...a, [id]: i }))}
          onDone={() => setStep({ kind: 'toSim' })}
          onExit={askExit}
        />
        {exitDialog}
      </>
    )

  if (step.kind === 'toSim')
    return (
      <div className="flex min-h-dvh flex-col">
        <Header onExit={askExit} current={1} total={STAGES} />
        <div className="flex flex-1 items-center justify-center bg-navy p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 text-center shadow-2xl sm:p-8">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-page text-accent">
              <Footprints className="h-7 w-7" />
            </div>
            <h2 className="text-xl font-bold text-navy">Теория завершена</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Дальше — симулятор: {SCENE_IDS.length} {SCENE_IDS.length === 1 ? 'сцена' : 'сцены'} по очереди. В каждой пройдите маршрут, отметьте
              нарушения от наиболее критичного и завершите осмотр — после этого откроется следующая сцена.
            </p>
            <ol className="mt-4 space-y-1.5 text-left text-sm">
              {SCENE_IDS.map((id, i) => (
                <li key={id} className="flex items-center gap-2.5 rounded-lg bg-page px-3 py-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy text-xs font-bold text-white">{i + 1}</span>
                  <span className="font-medium text-ink">{SCENES[id].title}</span>
                </li>
              ))}
            </ol>
            <button
              onClick={() => setStep({ kind: 'scene', index: 0 })}
              autoFocus
              className="mt-6 w-full rounded-[10px] bg-action py-3 font-semibold text-white transition hover:bg-action-dark"
            >
              Перейти в симулятор
            </button>
          </div>
        </div>
        {exitDialog}
      </div>
    )

  if (step.kind === 'scene')
    return (
      <>
        <WalkGame key={SCENE_IDS[step.index]} sceneName={SCENE_IDS[step.index]} onComplete={sceneDone} stage={{ current: 1 + step.index, total: STAGES }} onExit={askExit} />
        {exitDialog}
      </>
    )

  // Сводка
  const totalSec = Math.round((Date.now() - startedAt) / 1000)
  const wrong = questions.filter((q) => answers[q.id] !== q.correct)
  return (
    <div className="flex min-h-dvh flex-col">
      <Header onExit={reset} />
      <main className="mx-auto w-full max-w-3xl flex-1 p-3 sm:p-6">
        <section className="rounded-2xl bg-white p-5 shadow-[0_8px_30px_rgba(11,42,91,.12)] sm:p-8">
          <div className="text-center sm:text-left">
            <div className="text-sm text-muted">
              {player?.fio} · таб. № {player?.tabNo} · {player?.department}
            </div>
            <div className={`mt-3 inline-flex items-center gap-2 rounded-full px-4 py-2 text-lg font-bold text-white ${passed ? 'bg-ok' : 'bg-bad'}`}>
              {passed ? <CheckCircle2 className="h-6 w-6" /> : <XCircle className="h-6 w-6" />}
              {passed ? 'Экзамен сдан' : 'Экзамен не сдан'}
            </div>
            <div className="mt-2 text-sm text-muted">
              Порог в каждой части: <b className="text-ink">{config.passThresholdPercent}%</b> · время: <b className="tabular text-ink">{mmss(totalSec)}</b>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <PartCard icon={<BookOpen className="h-5 w-5" />} title="Теория" percent={theoryPercent} passed={theoryPassed} detail={`Верно ${theoryRight} из ${questions.length}`} />
            <PartCard icon={<Footprints className="h-5 w-5" />} title="Симулятор" percent={simPercent} passed={simPassed} detail={`Баллы ${simScore} из ${simMax}`} />
          </div>

          <button
            onClick={reset}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-[10px] border-2 border-action py-3 font-semibold text-action transition hover:bg-action/5"
          >
            <RotateCcw className="h-5 w-5" /> Пройти заново
          </button>
        </section>

        <h2 className="mb-3 mt-8 px-1 text-lg font-bold text-navy">Симулятор по сценам</h2>
        <div className="flex flex-col gap-2">
          {sceneResults.map((r, i) => (
            <div key={r.taskId} className="flex items-center gap-3 rounded-xl border border-line bg-white p-4 text-sm">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy text-sm font-bold text-white">{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold text-ink">{r.title}</span>
                <span className="text-muted">
                  Найдено {r.found} из {r.totalViolations} · лишних {r.extras} · порядок {r.perfectOrder ? 'верный' : `${Math.round(r.orderRatio * 100)}%`}
                </span>
              </span>
              <span className={`tabular font-bold ${pct(r.score, r.maxScore) >= config.passThresholdPercent ? 'text-ok' : 'text-bad'}`}>
                {pct(r.score, r.maxScore)}%
              </span>
            </div>
          ))}
        </div>

        <h2 className="mb-3 mt-8 px-1 text-lg font-bold text-navy">Ошибки в теории</h2>
        {wrong.length === 0 ? (
          <p className="rounded-xl border border-line bg-white p-4 text-sm text-ok">На все вопросы даны верные ответы.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {wrong.map((q) => (
              <li key={q.id} className="rounded-xl border border-line bg-white p-4 text-sm">
                <div className="font-semibold text-ink">{q.text}</div>
                <div className="mt-1.5 text-bad">Ваш ответ: {answers[q.id] !== undefined ? q.options[answers[q.id]] : 'нет ответа'}</div>
                <div className="text-ok">Верно: {q.options[q.correct]}</div>
                {q.explanation && (
                  <div className="mt-1 text-[13px] text-muted">
                    {q.explanation} {q.rule && <b className="text-action">{q.rule}</b>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}

/** Теория: вопросы по одному, можно вернуться назад; итог виден только в сводке */
function Theory({
  blocks,
  answers,
  onAnswer,
  onDone,
  onExit,
}: {
  blocks: TheoryBlock[]
  answers: Record<string, number>
  onAnswer: (id: string, i: number) => void
  onDone: () => void
  onExit: () => void
}) {
  const list = blocks.flatMap((b) => b.questions.map((q) => ({ q, block: b.title })))
  const [i, setI] = useState(0)
  const { q, block } = list[i]
  const last = i === list.length - 1
  const chosen = answers[q.id]
  const next = () => (last ? onDone() : setI(i + 1))

  // 1–9 выбирают вариант, Enter — дальше
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const m = /^(?:Digit|Numpad)([1-9])$/.exec(e.code)
      if (m && Number(m[1]) <= q.options.length) onAnswer(q.id, Number(m[1]) - 1)
      if (e.code === 'Enter' && chosen !== undefined) {
        e.preventDefault()
        next()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="flex min-h-dvh flex-col">
      <Header onExit={onExit} current={0} total={STAGES} />
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col p-3 sm:p-6">
        <div className="mb-3 flex items-center justify-between px-1 text-sm">
          <span className="font-semibold text-navy">{block}</span>
          <span className="tabular text-muted">
            Вопрос {i + 1} из {list.length}
          </span>
        </div>
        <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-line">
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${((i + 1) / list.length) * 100}%` }} />
        </div>

        <section className="rounded-2xl bg-white p-5 shadow-[0_8px_30px_rgba(11,42,91,.12)] sm:p-7">
          <h2 className="text-lg font-bold leading-snug text-ink sm:text-xl">{q.text}</h2>
          <div className="mt-5 flex flex-col gap-2.5">
            {q.options.map((o, k) => (
              <button
                key={k}
                onClick={() => onAnswer(q.id, k)}
                className={`flex items-start gap-3 rounded-xl border-2 p-3.5 text-left text-[15px] transition ${
                  chosen === k ? 'border-accent bg-accent/5' : 'border-line hover:border-accent/50'
                }`}
              >
                <span
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${
                    chosen === k ? 'border-accent bg-accent text-white' : 'border-line text-muted'
                  }`}
                >
                  {k + 1}
                </span>
                <span className="text-ink">{o}</span>
              </button>
            ))}
          </div>
        </section>

        <div className="mt-4 flex gap-3">
          <button
            onClick={() => setI(i - 1)}
            disabled={i === 0}
            className="flex items-center gap-1 rounded-[10px] border-2 border-action px-4 py-2.5 font-semibold text-action transition hover:bg-action/5 disabled:invisible"
          >
            <ChevronLeft className="h-5 w-5" /> Назад
          </button>
          <button
            onClick={next}
            disabled={chosen === undefined}
            className="flex-1 rounded-[10px] bg-action py-2.5 font-semibold text-white transition hover:bg-action-dark disabled:opacity-50"
          >
            {last ? 'Завершить теорию' : 'Далее'}
          </button>
        </div>
      </main>
    </div>
  )
}

function PartCard({ icon, title, percent, passed, detail }: { icon: React.ReactNode; title: string; percent: number; passed: boolean; detail: string }) {
  return (
    <div className={`rounded-xl border-2 p-4 ${passed ? 'border-ok/40 bg-ok/5' : 'border-bad/40 bg-bad/5'}`}>
      <div className="flex items-center gap-2 font-semibold text-navy">
        {icon} {title}
      </div>
      <div className={`tabular mt-1 text-3xl font-bold ${passed ? 'text-ok' : 'text-bad'}`}>{percent}%</div>
      <div className="text-sm text-muted">
        {detail} · {passed ? 'сдано' : 'не сдано'}
      </div>
    </div>
  )
}

function Center({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-dvh items-center justify-center bg-navy p-6 text-center text-white">{children}</div>
}
