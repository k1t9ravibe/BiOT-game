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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isEditor || isWalk ? (
      <Suspense fallback={null}>{isEditor ? <EditorScreen /> : <Walk3DScreen />}</Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
)
