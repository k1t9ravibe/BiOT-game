import { useEffect } from 'react'

interface Props {
  open: boolean
  title: string
  text?: string
  okText?: string
  onOk: () => void
  onCancel: () => void
}

export function ConfirmDialog({ open, title, text, okText = 'Да', onOk, onCancel }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onCancel()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/60 p-4" onClick={onCancel}>
      <div role="dialog" aria-modal className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-navy">{title}</h2>
        {text && <p className="mt-2 text-sm text-muted">{text}</p>}
        <div className="mt-6 flex gap-3">
          <button onClick={onCancel} className="flex-1 rounded-[10px] border border-line py-2.5 font-semibold text-ink hover:bg-page">
            Отмена
          </button>
          <button onClick={onOk} autoFocus className="flex-1 rounded-[10px] bg-action py-2.5 font-semibold text-white hover:bg-action-dark">
            {okText}
          </button>
        </div>
      </div>
    </div>
  )
}
