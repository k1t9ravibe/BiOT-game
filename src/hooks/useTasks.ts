import { useEffect, useState } from 'react'
import { config } from '../config'
import type { Task } from '../types'

type State = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; tasks: Task[] }

/** Загружает задания из public/tasks.json */
export function useTasks(): State {
  const [state, setState] = useState<State>({ status: 'loading' })
  useEffect(() => {
    let alive = true
    fetch(config.tasksUrl, { cache: 'no-store' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: unknown) => {
        const tasks = Array.isArray(data) ? (data as Task[]) : ((data as { tasks?: Task[] }).tasks ?? [])
        if (!tasks.length) throw new Error('в файле нет заданий')
        if (alive) setState({ status: 'ready', tasks })
      })
      .catch((e: Error) => alive && setState({ status: 'error', message: e.message }))
    return () => {
      alive = false
    }
  }, [])
  return state
}
