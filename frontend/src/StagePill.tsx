import type { Priority, Stage } from './api'
import { PRIORITY_CLASSES, PRIORITY_LABELS, STAGE_CLASSES, STAGE_LABELS } from './labels'

export function StagePill({ stage }: { stage: Stage | null }) {
  if (!stage) return null
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ${STAGE_CLASSES[stage]}`}>
      {STAGE_LABELS[stage]}
    </span>
  )
}

export function PriorityPill({ priority }: { priority: Priority | null }) {
  if (!priority) return null
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ${PRIORITY_CLASSES[priority]}`}>
      {PRIORITY_LABELS[priority]}
    </span>
  )
}
