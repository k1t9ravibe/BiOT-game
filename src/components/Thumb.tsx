import { config } from '../config'
import { cropStyle } from '../lib/crop'
import { useElementSize } from '../hooks/useElementSize'
import type { SceneImage } from '../hooks/useSceneImage'
import type { Area } from '../types'

/** Миниатюра — фрагмент картинки сцены, вырезанный через background-position (отдельные файлы не нужны) */
/** img === undefined — миниатюра не нужна (режим ходьбы), ничего не рисуем */
export function Thumb({ img, area, className = '' }: { img: SceneImage | null | undefined; area: Area; className?: string }) {
  const [ref, box] = useElementSize<HTMLDivElement>()
  if (img === undefined) return null
  const style =
    img && box.w > 0 && box.h > 0
      ? { backgroundImage: `url("${img.src}")`, backgroundRepeat: 'no-repeat', ...cropStyle(box, img, area, config.thumbPadding) }
      : undefined
  return <div ref={ref} className={`shrink-0 overflow-hidden bg-[#d8e0ec] ${className}`} style={style} aria-hidden />
}
