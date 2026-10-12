import { useEffect, useState } from 'react'
import { PLACEHOLDER_SIZE, placeholderScene } from '../lib/placeholder'
import type { Task } from '../types'

export interface SceneImage {
  src: string
  w: number
  h: number
  isPlaceholder: boolean
}

const cache = new Map<string, SceneImage>()

/** Загружает картинку сцены и узнаёт её размеры; если файла нет — подставляет SVG-заглушку */
export function useSceneImage(task: Task | undefined): SceneImage | null {
  const key = task ? `${task.id}|${task.image}` : ''
  const [img, setImg] = useState<SceneImage | null>(() => cache.get(key) ?? null)

  useEffect(() => {
    if (!task) return
    const cached = cache.get(key)
    if (cached) {
      setImg(cached)
      return
    }
    setImg(null)
    let alive = true
    const el = new Image()
    el.onload = () => {
      const res = { src: task.image, w: el.naturalWidth || 1600, h: el.naturalHeight || 900, isPlaceholder: false }
      cache.set(key, res)
      if (alive) setImg(res)
    }
    el.onerror = () => {
      const res = { src: placeholderScene(task), ...PLACEHOLDER_SIZE, isPlaceholder: true }
      cache.set(key, res)
      if (alive) setImg(res)
    }
    el.src = task.image
    return () => {
      alive = false
    }
  }, [key, task])

  return img
}

/** Заранее подгружает картинки всех сцен, чтобы переход между заданиями был без задержки */
export function preloadScenes(tasks: Task[]) {
  for (const t of tasks) new Image().src = t.image
}
