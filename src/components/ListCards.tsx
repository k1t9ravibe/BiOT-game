import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { restrictToParentElement, restrictToVerticalAxis } from './dndModifiers'
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'
import type { SceneImage } from '../hooks/useSceneImage'
import type { Task, TaskItem } from '../types'
import { ListCard } from './Cards'

interface Props {
  task: Task
  img: SceneImage | null | undefined
  selected: string[]
  onToggle: (id: string) => void
  onMove: (fromId: string, toId: string) => void
}

/**
 * Режим list: сверху выбранные карточки в порядке игрока (их можно перетаскивать за «ручку»),
 * ниже — остальные варианты. Номера пересчитываются автоматически.
 */
export function ListCards({ task, img, selected, onToggle, onMove }: Props) {
  // Тач: небольшая задержка, чтобы прокрутка страницы пальцем не превращалась в перетаскивание
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const byId = new Map(task.items.map((i) => [i.id, i]))
  const chosen = selected.map((id) => byId.get(id)).filter((i) => i !== undefined)
  const rest = task.items.filter((i) => !selected.includes(i.id))

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (over && active.id !== over.id) onMove(String(active.id), String(over.id))
  }

  return (
    <div className="flex flex-col gap-2.5">
      {chosen.length > 0 && (
        <>
          <SectionLabel>Ваш порядок — перетащите, чтобы изменить</SectionLabel>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd} modifiers={[restrictToVerticalAxis, restrictToParentElement]}>
            <SortableContext items={selected} strategy={verticalListSortingStrategy}>
              <div className="flex flex-col gap-2.5">
                {chosen.map((it, i) => (
                  <SortableCard key={it.id} item={it} img={img} n={i + 1} onToggle={() => onToggle(it.id)} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
          {rest.length > 0 && <SectionLabel>Остальные варианты</SectionLabel>}
        </>
      )}
      {rest.map((it) => (
        <ListCard key={it.id} item={it} img={img} n={null} onToggle={() => onToggle(it.id)} />
      ))}
    </div>
  )
}

function SortableCard({ item, img, n, onToggle }: { item: TaskItem; img: SceneImage | null | undefined; n: number; onToggle: () => void }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={`relative ${isDragging ? 'z-10 opacity-90 drop-shadow-xl' : ''}`}
    >
      <ListCard
        item={item}
        img={img}
        n={n}
        onToggle={onToggle}
        handle={
          <button
            type="button"
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
            aria-label="Перетащить"
            className="flex h-10 w-8 shrink-0 cursor-grab touch-none items-center justify-center rounded-md text-[#8a99b3] hover:bg-page active:cursor-grabbing"
          >
            <GripVertical className="h-5 w-5" />
          </button>
        }
      />
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="px-1 pt-1 text-xs font-semibold uppercase tracking-wide text-muted">{children}</div>
}
