import type { Task } from '../types'

export const PLACEHOLDER_SIZE = { w: 1600, h: 900 }

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/**
 * SVG-заглушка, пока настоящая картинка сцены не загружена в public/scenes.
 * Рисует условный пейзаж и подписанные прямоугольники по координатам из tasks.json —
 * так игру можно проверить целиком и сразу видно, где лежат области.
 */
export function placeholderScene(task: Task): string {
  const { w, h } = PLACEHOLDER_SIZE
  const evening = /вечер|сумерк/i.test(task.title)
  const sky = evening ? ['#2b3a67', '#e58e5a'] : ['#8cc8f0', '#dff1fb']
  const rects = task.items
    .map((it, i) => {
      const x = (it.area.x / 100) * w
      const y = (it.area.y / 100) * h
      const rw = (it.area.w / 100) * w
      const rh = (it.area.h / 100) * h
      const hue = (i * 57) % 360
      return `<g><rect x="${x}" y="${y}" width="${rw}" height="${rh}" rx="14" fill="hsl(${hue} 70% 60% / .55)" stroke="hsl(${hue} 60% 35%)" stroke-width="4"/>
<foreignObject x="${x + 6}" y="${y + 6}" width="${Math.max(10, rw - 12)}" height="${Math.max(10, rh - 12)}"><div xmlns="http://www.w3.org/1999/xhtml" style="font:600 22px sans-serif;color:#0b2a5b;line-height:1.15;overflow:hidden;height:100%">${esc(it.text)}</div></foreignObject></g>`
    })
    .join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${sky[0]}"/><stop offset="1" stop-color="${sky[1]}"/></linearGradient></defs>
<rect width="${w}" height="${h}" fill="url(#s)"/>
<rect y="${h * 0.62}" width="${w}" height="${h * 0.38}" fill="${evening ? '#5d6b3f' : '#b9c77a'}"/>
<rect x="${w * 0.08}" y="${h * 0.34}" width="${w * 0.3}" height="${h * 0.3}" fill="#b5654a"/>
<rect x="${w * 0.06}" y="${h * 0.3}" width="${w * 0.34}" height="${h * 0.05}" fill="#7a3f2c"/>
<rect x="${w * 0.55}" y="${h * 0.08}" width="${w * 0.018}" height="${h * 0.58}" fill="#7b5a3a"/>
${rects}
<text x="${w / 2}" y="${h - 30}" text-anchor="middle" font-family="sans-serif" font-size="30" fill="#0b2a5b" opacity=".75">Заглушка: положите картинку ${esc(task.image)} в папку public</text>
</svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}
