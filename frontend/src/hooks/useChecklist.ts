import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ChecklistItem, CleanupTask, Priority } from '../types'

const STORAGE_PREFIX = 'credpilot.checklist.v1.'

interface ChecklistState {
  fingerprint: string
  items: ChecklistItem[]
}

function storageKey(fingerprint: string): string {
  return `${STORAGE_PREFIX}${fingerprint}`
}

function isValidItem(value: unknown): value is ChecklistItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    typeof item.id === 'string' &&
    typeof item.title === 'string' &&
    typeof item.detail === 'string' &&
    typeof item.done === 'boolean' &&
    ['now', 'before-demo', 'after-demo'].includes(String(item.priority)) &&
    ['billing', 'deployment', 'security', 'cleanup'].includes(String(item.category))
  )
}

function readSaved(fingerprint: string): ChecklistItem[] | null {
  try {
    const raw = window.localStorage.getItem(storageKey(fingerprint))
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    const items = parsed.filter(isValidItem)
    return items.length === parsed.length ? items : null
  } catch {
    return null
  }
}

function writeSaved(fingerprint: string, items: ChecklistItem[]): void {
  try {
    window.localStorage.setItem(storageKey(fingerprint), JSON.stringify(items))
  } catch {
    // A full or unavailable localStorage must not break the analyzer.
  }
}

function fromGenerated(tasks: CleanupTask[]): ChecklistItem[] {
  return tasks.map((task) => ({ ...task, done: false }))
}

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `user-${crypto.randomUUID()}`
  }
  return `user-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export interface ChecklistActions {
  items: ChecklistItem[]
  done: number
  total: number
  toggle: (id: string) => void
  edit: (id: string, title: string, detail: string) => void
  remove: (id: string) => void
  add: (title: string, detail: string, priority: Priority) => void
  reset: () => void
}

export function useChecklist(
  fingerprint: string | undefined,
  generated: CleanupTask[],
): ChecklistActions {
  const [state, setState] = useState<ChecklistState | null>(null)

  useEffect(() => {
    if (!fingerprint) {
      setState(null)
      return
    }
    setState((current) => {
      if (current?.fingerprint === fingerprint) return current
      const saved = readSaved(fingerprint)
      return {
        fingerprint,
        items: saved ?? fromGenerated(generated),
      }
    })
  }, [fingerprint, generated])

  useEffect(() => {
    if (state) writeSaved(state.fingerprint, state.items)
  }, [state])

  const update = useCallback(
    (updater: (items: ChecklistItem[]) => ChecklistItem[]) => {
      setState((current) => {
        if (!current) return current
        return { ...current, items: updater(current.items) }
      })
    },
    [],
  )

  const toggle = useCallback(
    (id: string) => {
      update((items) =>
        items.map((item) => (item.id === id ? { ...item, done: !item.done } : item)),
      )
    },
    [update],
  )

  const edit = useCallback(
    (id: string, title: string, detail: string) => {
      const cleanTitle = title.trim()
      if (!cleanTitle) return
      update((items) =>
        items.map((item) =>
          item.id === id
            ? { ...item, title: cleanTitle, detail: detail.trim() }
            : item,
        ),
      )
    },
    [update],
  )

  const remove = useCallback(
    (id: string) => {
      update((items) => items.filter((item) => item.id !== id))
    },
    [update],
  )

  const add = useCallback(
    (title: string, detail: string, priority: Priority) => {
      const cleanTitle = title.trim()
      if (!cleanTitle) return
      update((items) => [
        ...items,
        {
          id: newId(),
          title: cleanTitle,
          detail: detail.trim(),
          priority,
          category: 'cleanup',
          source_finding_id: null,
          evidence_file: null,
          evidence_line: null,
          done: false,
        },
      ])
    },
    [update],
  )

  const reset = useCallback(() => {
    setState((current) => {
      if (!current) return current
      return { ...current, items: fromGenerated(generated) }
    })
  }, [generated])

  const items = state?.items ?? []
  const done = useMemo(() => items.filter((item) => item.done).length, [items])

  return {
    items,
    done,
    total: items.length,
    toggle,
    edit,
    remove,
    add,
    reset,
  }
}
