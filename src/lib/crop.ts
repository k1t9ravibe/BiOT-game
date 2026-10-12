import type { Area } from '../types'

export interface Size {
  w: number
  h: number
}

/**
 * Размер и смещение картинки, вписанной в контейнер (как object-fit: cover/contain).
 * Нужен, чтобы зоны нарушений в процентах точно совпадали с картинкой.
 */
export function fitRect(box: Size, img: Size, mode: 'cover' | 'contain') {
  const s = mode === 'cover' ? Math.max(box.w / img.w, box.h / img.h) : Math.min(box.w / img.w, box.h / img.h)
  const w = img.w * s
  const h = img.h * s
  return { w, h, left: (box.w - w) / 2, top: (box.h - h) / 2 }
}

/**
 * Параметры background-size / background-position, чтобы в блоке размером box
 * была видна область area картинки (с запасом pad), без искажения пропорций.
 */
export function cropStyle(box: Size, img: Size, area: Area, pad: number) {
  const aw = Math.max(1, (area.w * (1 + pad * 2) * img.w) / 100)
  const ah = Math.max(1, (area.h * (1 + pad * 2) * img.h) / 100)
  const s = Math.max(box.w / aw, box.h / ah)
  const sw = img.w * s
  const sh = img.h * s
  const cx = ((area.x + area.w / 2) / 100) * sw
  const cy = ((area.y + area.h / 2) / 100) * sh
  const clamp = (v: number, min: number) => Math.min(0, Math.max(min, v))
  return {
    backgroundSize: `${sw}px ${sh}px`,
    backgroundPosition: `${clamp(box.w / 2 - cx, box.w - sw)}px ${clamp(box.h / 2 - cy, box.h - sh)}px`,
  }
}
