import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, Info, Lock, X } from 'lucide-react'
import { CityEngine } from '../city/engine'
import { Header } from '../components/Header'
import { config } from '../config'
import { isCityUnlocked, loadCityAnswers, saveCityAnswers } from '../lib/progress'
import type { CityData, CitySite } from '../types'

/**
 * Локация 2 «Город» (/city): улица с прокруткой, шесть зданий-организаций, у каждого — вопросы.
 * Открывается после прохождения локации 1 (не ниже порога допуска). Вопросы — public/city.json,
 * ответы хранятся в браузере. В режиме разработки город можно открыть ссылкой /city?open.
 */

const DATA_URL = '/city.json'
const SCENE_URL = '/models/city.glb'
const SITUATION_NUMBER = 2

export default function CityScreen() {
  const unlocked = useMemo(() => isCityUnlocked() || (import.meta.env.DEV && new URLSearchParams(location.search).has('open')), [])
  return unlocked ? <City /> : <Locked />
}

function Locked() {
  return (
    <div className="flex h-dvh flex-col">
      <Header onExit={() => (location.href = '/')} />
      <div className="flex flex-1 items-center justify-center bg-[#a9d6f5] p-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-6 text-center shadow-2xl">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-page text-navy">
            <Lock className="h-6 w-6" />
          </div>
          <h2 className="text-lg font-bold text-navy">Локация 2 «Город» пока закрыта</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Она откроется после прохождения локации 1 с результатом не ниже {config.passThresholdPercent}%.
          </p>
          <a href="/walk" className="mt-5 block rounded-[10px] bg-action py-2.5 font-semibold text-white transition hover:bg-action-dark">
            Пройти локацию 1
          </a>
        </div>
      </div>
    </div>
  )
}

function City() {
  const mountRef = useRef<HTMLDivElement>(null)
  const engineRef = useRef<CityEngine | null>(null)
  const [data, setData] = useState<CityData | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | string>('loading')
  const [answers, setAnswers] = useState<Record<string, number>>(loadCityAnswers)
  const [started, setStarted] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)
  const [qi, setQi] = useState(0)
  const [hover, setHover] = useState<string | null>(null)
  const [hint, setHint] = useState(true)
  const [finalClosed, setFinalClosed] = useState(false)

  useEffect(() => {
    fetch(DATA_URL, { cache: 'no-store' })
      .then((r) => r.json())
      .then(setData)
      .catch((e: Error) => setStatus(e.message))
  }, [])

  const sites = data?.sites ?? []
  const siteDone = (s: CitySite) => s.questions.every((q) => answers[q.id] !== undefined)
  const siteScore = (s: CitySite) => s.questions.filter((q) => answers[q.id] === q.correct).length
  const doneIds = sites.filter(siteDone).map((s) => s.id)
  const total = sites.reduce((n, s) => n + s.questions.length, 0)
  const correct = sites.reduce((n, s) => n + siteScore(s), 0)
  const allDone = sites.length > 0 && doneIds.length === sites.length
  const percent = total ? Math.round((correct / total) * 100) : 0
  const anyAnswered = Object.keys(answers).length > 0

  const openSite = (id: string) => {
    const s = sites.find((x) => x.id === id)
    if (!s) return
    const first = s.questions.findIndex((q) => answers[q.id] === undefined)
    setQi(first < 0 ? 0 : first)
    setOpenId(id)
    engineRef.current?.focus(id)
  }
  const openRef = useRef(openSite)
  openRef.current = openSite

  useEffect(() => {
    const engine = new CityEngine(mountRef.current!, SCENE_URL, {
      onReady: () => setStatus('ready'),
      onError: (m) => setStatus(m),
      onSelect: (id) => openRef.current(id),
      onHover: setHover,
    })
    engineRef.current = engine
    return () => engine.dispose()
  }, [])

  const doneKey = doneIds.join('|')
  useEffect(() => {
    if (status === 'ready') engineRef.current?.setDone(doneKey ? doneKey.split('|') : [])
  }, [doneKey, status])

  const modal = !started || openId !== null || (allDone && !finalClosed)
  useEffect(() => engineRef.current?.setInputEnabled(!modal), [modal])

  const answer = (qid: string, option: number) => {
    if (answers[qid] !== undefined) return // засчитывается первая попытка
    const next = { ...answers, [qid]: option }
    setAnswers(next)
    saveCityAnswers(next)
  }

  const restart = () => {
    setAnswers({})
    saveCityAnswers({})
    setFinalClosed(false)
  }

  const site = sites.find((s) => s.id === openId) ?? null
  const hoverSite = sites.find((s) => s.id === hover)

  return (
    <div className="flex h-dvh flex-col">
      <Header onExit={() => (location.href = '/')} />

      <div className="relative flex-1 overflow-hidden bg-[#a9d6f5]">
        <div ref={mountRef} className="absolute inset-0" />

        {status !== 'ready' && (
          <div className="absolute inset-0 flex items-center justify-center bg-navy/70 p-6 text-center text-white">
            {status === 'loading' ? 'Загрузка города…' : `Не удалось загрузить город: ${status}`}
          </div>
        )}

        {/* Ситуация перед началом */}
        {status === 'ready' && data && !started && (
          <Modal>
            <h2 className="px-5 pb-2 pt-5 text-lg font-bold text-navy">Ситуация {SITUATION_NUMBER}</h2>
            <div className="thin-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-5 pb-4 text-[15px] leading-relaxed text-ink">
              {data.briefing.split(/\n\s*\n/).map((p, i) => (
                <p key={i}>{p}</p>
              ))}
            </div>
            <div className="border-t border-line p-4">
              <button onClick={() => setStarted(true)} autoFocus className="w-full rounded-[10px] bg-action py-2.5 font-semibold text-white transition hover:bg-action-dark">
                {anyAnswered ? 'Продолжить' : 'Начать'}
              </button>
            </div>
          </Modal>
        )}

        {/* Подсказка и прогресс */}
        {started && status === 'ready' && hint && (
          <div className="absolute left-3 top-3 max-w-sm rounded-xl bg-navy/85 p-4 pr-9 text-sm leading-snug text-white shadow-lg backdrop-blur-sm">
            <button onClick={() => setHint(false)} className="absolute right-2.5 top-2.5 opacity-80" aria-label="Закрыть">
              <X className="h-4 w-4" />
            </button>
            <b className="mb-1 block">{data?.title ?? 'Город'}</b>
            Прокручивайте улицу и нажимайте на здания с метками, чтобы ответить на вопросы.
            <span className="mt-2 block text-white/75">Перетащите сцену, колесо мыши или ← → — прокрутка.</span>
          </div>
        )}
        {started && status === 'ready' && !hint && (
          <button onClick={() => setHint(true)} className="absolute left-3 top-3 rounded-full bg-navy/85 p-2 text-white" aria-label="Подсказка">
            <Info className="h-5 w-5" />
          </button>
        )}

        {started && status === 'ready' && sites.length > 0 && (
          <div className="absolute right-3 top-3 w-64 rounded-2xl bg-white/95 p-3 shadow-lg max-sm:w-auto">
            <div className="mb-1 flex items-baseline justify-between gap-3 text-sm font-bold text-navy">
              <span>Объекты</span>
              <span className="tabular text-muted">
                {doneIds.length} из {sites.length}
              </span>
            </div>
            <ul className="space-y-0.5 max-sm:hidden">
              {sites.map((s, i) => {
                const done = siteDone(s)
                return (
                  <li key={s.id}>
                    <button onClick={() => openSite(s.id)} className="flex w-full items-center gap-2.5 rounded-lg px-1.5 py-1 text-left text-sm hover:bg-page">
                      <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${done ? 'bg-ok' : 'bg-accent'}`}>
                        {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
                      </span>
                      <span className="flex-1 truncate font-medium text-ink">{s.title}</span>
                      {done && (
                        <span className="tabular text-xs text-muted">
                          {siteScore(s)}/{s.questions.length}
                        </span>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {/* Подпись здания под курсором */}
        {started && hoverSite && !modal && (
          <div className="pointer-events-none absolute bottom-20 left-1/2 -translate-x-1/2 rounded-xl bg-white/95 px-4 py-2 text-center shadow-lg">
            <div className="text-sm font-bold text-navy">{hoverSite.title}</div>
            <div className="text-xs text-muted">{siteDone(hoverSite) ? 'Вопросы пройдены — нажмите, чтобы посмотреть разбор' : 'Нажмите, чтобы ответить на вопросы'}</div>
          </div>
        )}

        {/* Прокрутка кнопками */}
        {started && status === 'ready' && (
          <>
            <button
              onClick={() => engineRef.current?.scrollBy(-24)}
              className="absolute bottom-4 left-4 flex h-12 w-12 items-center justify-center rounded-full bg-navy/85 text-white shadow-lg transition hover:bg-navy"
              aria-label="Прокрутить влево"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
            <button
              onClick={() => engineRef.current?.scrollBy(24)}
              className="absolute bottom-4 right-4 flex h-12 w-12 items-center justify-center rounded-full bg-navy/85 text-white shadow-lg transition hover:bg-navy"
              aria-label="Прокрутить вправо"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          </>
        )}

        {/* Вопросы по зданию */}
        {site && <Quiz site={site} num={sites.indexOf(site) + 1} qi={qi} setQi={setQi} answers={answers} onAnswer={answer} onClose={() => setOpenId(null)} />}

        {/* Итог локации */}
        {started && allDone && !openId && !finalClosed && (
          <Modal>
            <h2 className="px-5 pb-1 pt-5 text-lg font-bold text-navy">Итог: {data?.title}</h2>
            <div className="px-5 pb-4">
              <div className={`text-4xl font-bold ${percent >= config.passThresholdPercent ? 'text-ok' : 'text-bad'}`}>{percent}%</div>
              <div className="mt-1 text-sm text-muted">
                Верных ответов: {correct} из {total} · порог допуска {config.passThresholdPercent}%
              </div>
              <div className={`mt-3 rounded-lg px-3 py-2 text-sm font-semibold ${percent >= config.passThresholdPercent ? 'bg-ok/10 text-ok' : 'bg-bad/10 text-bad'}`}>
                {percent >= config.passThresholdPercent ? 'Локация 2 пройдена' : 'Локация 2 не пройдена — разберите ошибки и попробуйте ещё раз'}
              </div>
              <ul className="mt-3 space-y-1 text-sm">
                {sites.map((s) => (
                  <li key={s.id} className="flex justify-between gap-3">
                    <span className="text-ink">{s.title}</span>
                    <span className="tabular text-muted">
                      {siteScore(s)}/{s.questions.length}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="grid grid-cols-2 gap-3 border-t border-line p-4">
              <button onClick={restart} className="rounded-[10px] border-2 border-action py-2.5 font-semibold text-action">
                Пройти заново
              </button>
              <button onClick={() => setFinalClosed(true)} className="rounded-[10px] bg-action py-2.5 font-semibold text-white">
                Посмотреть разбор
              </button>
            </div>
          </Modal>
        )}
      </div>
    </div>
  )
}

function Modal({ children }: { children: React.ReactNode }) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-navy/60 p-3">
      <div className="flex max-h-full w-full max-w-lg flex-col rounded-2xl bg-white shadow-2xl">{children}</div>
    </div>
  )
}

function Quiz({
  site,
  num,
  qi,
  setQi,
  answers,
  onAnswer,
  onClose,
}: {
  site: CitySite
  num: number
  qi: number
  setQi: (i: number) => void
  answers: Record<string, number>
  onAnswer: (qid: string, option: number) => void
  onClose: () => void
}) {
  const q = site.questions[qi]
  const chosen = answers[q.id]
  const answered = chosen !== undefined
  const last = qi === site.questions.length - 1

  return (
    <Modal>
      <div className="flex items-start gap-3 px-5 pb-3 pt-5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-bold text-white">{num}</span>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold leading-tight text-navy">{site.title}</h2>
          <p className="mt-0.5 text-xs leading-snug text-muted">{site.org}</p>
        </div>
        <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-page" aria-label="Закрыть">
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="flex items-center gap-2 px-5 pb-2">
        <span className="text-xs font-semibold text-muted">
          Вопрос {qi + 1} из {site.questions.length}
        </span>
        <div className="flex gap-1">
          {site.questions.map((x, i) => {
            const a = answers[x.id]
            const color = a === undefined ? 'bg-line' : a === x.correct ? 'bg-ok' : 'bg-bad'
            return <button key={x.id} onClick={() => setQi(i)} className={`h-2 w-6 rounded-full ${color} ${i === qi ? 'ring-2 ring-accent ring-offset-1' : ''}`} aria-label={`Вопрос ${i + 1}`} />
          })}
        </div>
      </div>

      <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-5 pb-4">
        <p className="mb-3 text-[15px] font-semibold leading-snug text-ink">{q.text}</p>
        <div className="space-y-2">
          {q.options.map((opt, i) => {
            const isCorrect = i === q.correct
            const isChosen = i === chosen
            let cls = 'border-line bg-white hover:border-accent hover:bg-page'
            if (answered) cls = isCorrect ? 'border-ok bg-ok/10' : isChosen ? 'border-bad bg-bad/10' : 'border-line bg-white opacity-60'
            return (
              <button
                key={i}
                onClick={() => onAnswer(q.id, i)}
                disabled={answered}
                className={`flex w-full items-start gap-3 rounded-xl border-2 px-3 py-2.5 text-left text-sm leading-snug text-ink transition ${cls}`}
              >
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-current text-[11px] font-bold text-muted">
                  {answered && isCorrect ? <Check className="h-3.5 w-3.5 text-ok" /> : answered && isChosen ? <X className="h-3.5 w-3.5 text-bad" /> : 'АБВГ'[i]}
                </span>
                <span className="flex-1">{opt}</span>
              </button>
            )
          })}
        </div>
        {answered && (
          <div className={`mt-3 rounded-xl px-3 py-2.5 text-sm leading-snug ${chosen === q.correct ? 'bg-ok/10' : 'bg-bad/10'}`}>
            <b className={chosen === q.correct ? 'text-ok' : 'text-bad'}>{chosen === q.correct ? 'Верно. ' : 'Неверно. '}</b>
            <span className="text-ink">{q.explanation}</span>
            {q.rule && <div className="mt-1 text-xs text-muted">{q.rule}</div>}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 border-t border-line p-4">
        <button
          onClick={() => setQi(qi - 1)}
          disabled={qi === 0}
          className="rounded-[10px] border-2 border-action py-2.5 font-semibold text-action disabled:opacity-40"
        >
          Назад
        </button>
        <button
          onClick={() => (last ? onClose() : setQi(qi + 1))}
          disabled={!answered}
          className="rounded-[10px] bg-action py-2.5 font-semibold text-white transition hover:bg-action-dark disabled:opacity-50"
        >
          {last ? 'Готово' : 'Следующий вопрос'}
        </button>
      </div>
    </Modal>
  )
}
