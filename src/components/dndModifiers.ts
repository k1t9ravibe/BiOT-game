import type { Modifier } from '@dnd-kit/core'

/** Перетаскивание только по вертикали */
export const restrictToVerticalAxis: Modifier = ({ transform }) => ({ ...transform, x: 0 })

/** Не выходить за пределы списка */
export const restrictToParentElement: Modifier = ({ transform, draggingNodeRect, containerNodeRect }) => {
  if (!draggingNodeRect || !containerNodeRect) return transform
  const minY = containerNodeRect.top - draggingNodeRect.top
  const maxY = containerNodeRect.bottom - draggingNodeRect.bottom
  return { ...transform, y: Math.min(maxY, Math.max(minY, transform.y)) }
}
