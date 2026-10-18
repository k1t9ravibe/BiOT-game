import { StrictMode, lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter'
import './index.css'
import App from './App'

// Скрытая страница разметки сцен: /editor (или #editor — если хостинг не умеет SPA-маршруты)
const EditorScreen = lazy(() => import('./screens/EditorScreen'))
const isEditor = /^\/editor\/?$/.test(location.pathname) || location.hash === '#editor'
// Прототип 3D-режима ходьбы: /walk (или #walk)
const Walk3DScreen = lazy(() => import('./screens/Walk3DScreen'))
const isWalk = /^\/walk\/?$/.test(location.pathname) || location.hash === '#walk'
// Локация 2 «Город»: /city (или #city) — тот же режим ходьбы со сценой city; открывается после локации 1
const isCity = /^\/city\/?$/.test(location.pathname) || location.hash === '#city'
// Локация 3 «Вечерний город»: /evening (или #evening)
const isEvening = /^\/evening\/?$/.test(location.pathname) || location.hash === '#evening'
// Локация 4 «Серверная»: /server (или #server)
const isServer = /^\/server\/?$/.test(location.pathname) || location.hash === '#server'
// Локация 5 «Трасса»: /highway (или #highway)
const isHighway = /^\/highway\/?$/.test(location.pathname) || location.hash === '#highway'
// Экзамен: вход → теория → сцены симулятора по очереди → сводка: /exam (или #exam)
const ExamScreen = lazy(() => import('./screens/ExamScreen'))
const isExam = /^\/exam\/?$/.test(location.pathname) || location.hash === '#exam'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isExam ? (
      <Suspense fallback={null}>
        <ExamScreen />
      </Suspense>
    ) : isEditor || isWalk || isCity || isEvening || isServer || isHighway ? (
      <Suspense fallback={null}>{isEditor ? <EditorScreen /> : <Walk3DScreen />}</Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
)
