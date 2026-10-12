import type { SceneImage } from '../hooks/useSceneImage'
import type { Task } from '../types'
import { GridCard } from './Cards'

/** Режим grid: сетка 3×2, номер — порядок клика (для смены порядка снимите выбор и выберите заново) */
export function GridCards({ task, img, selected, onToggle }: { task: Task; img: SceneImage | null; selected: string[]; onToggle: (id: string) => void }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {task.items.map((it) => {
        const p = selected.indexOf(it.id)
        return <GridCard key={it.id} item={it} img={img} n={p >= 0 ? p + 1 : null} onToggle={() => onToggle(it.id)} />
      })}
    </div>
  )
}
