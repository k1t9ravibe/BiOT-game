import { StrictMode, lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter'
import './index.css'
import App from './App'

// Скрытая страница разметки сцен: /editor (или #editor — если хостинг не умеет SPA-маршруты)
const EditorScreen = lazy(() => import('./screens/EditorScreen'))
const isEditor = /^\/editor\/?$/.test(location.pathname) || location.hash === '#editor'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isEditor ? (
      <Suspense fallback={null}>
        <EditorScreen />
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
)
