import { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { config } from '../config'
import { loadLastPlayer } from '../lib/storage'
import { useGame } from '../store/useGame'

export function StartScreen() {
  const start = useGame((s) => s.start)
  const count = useGame((s) => s.tasks.length)
  const last = loadLastPlayer()
  const [fio, setFio] = useState(last?.fio ?? '')
  const [tabNo, setTabNo] = useState(last?.tabNo ?? '')
  const [department, setDepartment] = useState(last?.department ?? '')
  const [touched, setTouched] = useState(false)

  const valid = fio.trim().split(/\s+/).length >= 2 && tabNo.trim().length > 0 && department.length > 0

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (valid) start({ fio: fio.trim().replace(/\s+/g, ' '), tabNo: tabNo.trim(), department })
  }

  const field = 'w-full rounded-[10px] border border-line bg-white px-3.5 py-3 text-[15px] outline-none transition focus:border-accent focus:ring-4 focus:ring-accent/15'

  return (
    <div className="flex min-h-dvh flex-col bg-navy">
      <div className="flex flex-1 items-center justify-center p-4">
        <form onSubmit={submit} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl sm:p-8" noValidate>
          <div className="flex items-center gap-3">
            <img src="/logo.svg" alt="" className="h-12 w-12" />
            <span className="text-lg font-bold tracking-wide text-navy">КАЗАХТЕЛЕКОМ</span>
          </div>
          <h1 className="mt-6 text-2xl font-bold text-navy sm:text-[28px]">БИОТ – Допуск к работе</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            {count} заданий: на сценах у сельской АТС найдите нарушения техники безопасности и расставьте их от наиболее
            критичного к менее значимому. Для допуска нужно набрать не менее {config.passThresholdPercent}%.
          </p>

          <div className="mt-6 flex flex-col gap-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-ink">ФИО</span>
              <input className={field} value={fio} onChange={(e) => setFio(e.target.value)} placeholder="Иванов Иван Иванович" autoComplete="name" />
              {touched && fio.trim().split(/\s+/).length < 2 && <Err>Укажите фамилию и имя</Err>}
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-ink">Табельный номер</span>
              <input className={field} value={tabNo} onChange={(e) => setTabNo(e.target.value)} placeholder="000000" inputMode="numeric" />
              {touched && !tabNo.trim() && <Err>Укажите табельный номер</Err>}
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-ink">Подразделение</span>
              <select className={`${field} ${department ? '' : 'text-muted'}`} value={department} onChange={(e) => setDepartment(e.target.value)}>
                <option value="" disabled>
                  Выберите подразделение
                </option>
                {config.departments.map((d) => (
                  <option key={d} value={d} className="text-ink">
                    {d}
                  </option>
                ))}
              </select>
              {touched && !department && <Err>Выберите подразделение</Err>}
            </label>
          </div>

          <button
            type="submit"
            className="mt-7 flex w-full items-center justify-center gap-2 rounded-[10px] bg-action py-3.5 text-base font-semibold text-white transition hover:bg-action-dark"
          >
            <ShieldCheck className="h-5 w-5" />
            Начать
          </button>
        </form>
      </div>
    </div>
  )
}

function Err({ children }: { children: React.ReactNode }) {
  return <span className="mt-1 block text-xs font-medium text-bad">{children}</span>
}
