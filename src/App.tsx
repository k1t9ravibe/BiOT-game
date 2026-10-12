import { useEffect } from 'react'
import { preloadScenes } from './hooks/useSceneImage'
import { useTasks } from './hooks/useTasks'
import { ResultScreen } from './screens/ResultScreen'
import { StartScreen } from './screens/StartScreen'
import { TaskScreen } from './screens/TaskScreen'
import { useGame } from './store/useGame'

export default function App() {
  const state = useTasks()
  const screen = useGame((s) => s.screen)
  const setTasks = useGame((s) => s.setTasks)

  useEffect(() => {
    if (state.status === 'ready') {
      setTasks(state.tasks)
      preloadScenes(state.tasks)
    }
  }, [state, setTasks])

  if (state.status === 'loading') return <Center>Загрузка заданий…</Center>
  if (state.status === 'error') return <Center>Не удалось загрузить задания (public/tasks.json): {state.message}</Center>

  if (screen === 'task') return <TaskScreen />
  if (screen === 'result') return <ResultScreen />
  return <StartScreen />
}

function Center({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-dvh items-center justify-center bg-navy p-6 text-center text-white">{children}</div>
}
