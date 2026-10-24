import { useState } from 'react'
import type { ChecklistActions } from '../hooks/useChecklist'
import type { Category, Priority } from '../types'
import {
  categoryLabels,
  priorityLabels,
  priorityOrder,
} from '../lib/format'
import { Icon, type IconName } from './Icons'

interface ChecklistProps {
  checklist: ChecklistActions
  fingerprint: string
}

const categoryIcons: Record<Category, IconName> = {
  billing: 'wallet',
  deployment: 'server',
  security: 'shield',
  cleanup: 'broom',
}

const priorityHints: Record<Priority, string> = {
  now: 'Do this before anything is shared.',
  'before-demo': 'Finish before judges see the link.',
  'after-demo': 'Do not leave this behind.',
}

export function Checklist({ checklist, fingerprint }: ChecklistProps) {
  const { items, done, total, toggle, edit, remove, add, reset } = checklist
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftDetail, setDraftDetail] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newDetail, setNewDetail] = useState('')
  const [newPriority, setNewPriority] = useState<Priority>('before-demo')

  const percent = total === 0 ? 0 : Math.round((done / total) * 100)

  function startEdit(id: string, title: string, detail: string) {
    setEditingId(id)
    setDraftTitle(title)
    setDraftDetail(detail)
  }

  function saveEdit() {
    if (!editingId) return
    edit(editingId, draftTitle, draftDetail)
    setEditingId(null)
  }

  function submitNew() {
    if (!newTitle.trim()) return
    add(newTitle, newDetail, newPriority)
    setNewTitle('')
    setNewDetail('')
    setNewPriority('before-demo')
    setAdding(false)
  }

  function confirmReset() {
    if (window.confirm('Reset the checklist to the generated tasks? Local edits will be lost.')) {
      reset()
      setEditingId(null)
      setAdding(false)
    }
  }

  return (
    <div className="checklist-panel">
      <div className="checklist-head">
        <div>
          <h3>Cleanup checklist</h3>
          <p>
            Editable and saved in this browser for config{' '}
            <code>{fingerprint.slice(0, 8)}</code>. Nothing is sent to a server.
          </p>
        </div>
        <div className="checklist-head-actions">
          <button
            type="button"
            className="chip-button"
            onClick={() => setAdding((value) => !value)}
          >
            <Icon name={adding ? 'x' : 'plus'} size={13} />
            {adding ? 'Cancel' : 'Add task'}
          </button>
          <button type="button" className="chip-button" onClick={confirmReset}>
            <Icon name="refresh" size={13} /> Reset
          </button>
        </div>
      </div>

      <div className="progress-block">
        <div className="progress-label">
          <span>
            {done} of {total} complete
          </span>
          <span>{percent}%</span>
        </div>
        <div
          className="progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={done}
          aria-label="Cleanup progress"
        >
          <span className="progress-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {adding && (
        <form
          className="task-form"
          onSubmit={(event) => {
            event.preventDefault()
            submitNew()
          }}
        >
          <label className="field">
            <span className="field-label">Task</span>
            <input
              className="text-input"
              value={newTitle}
              onChange={(event) => setNewTitle(event.target.value)}
              placeholder="e.g. Delete the demo Postgres database"
              maxLength={140}
              autoFocus
            />
          </label>
          <label className="field">
            <span className="field-label">Detail (optional)</span>
            <textarea
              className="text-area"
              value={newDetail}
              onChange={(event) => setNewDetail(event.target.value)}
              placeholder="What exactly needs to happen, and where?"
              rows={2}
              maxLength={500}
            />
          </label>
          <div className="task-form-row">
            <label className="field field-inline">
              <span className="field-label">Priority</span>
              <select
                className="select-input"
                value={newPriority}
                onChange={(event) => setNewPriority(event.target.value as Priority)}
              >
                {priorityOrder.map((priority) => (
                  <option key={priority} value={priority}>
                    {priorityLabels[priority]}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              className="btn btn-primary btn-small"
              disabled={!newTitle.trim()}
            >
              Add task
            </button>
          </div>
        </form>
      )}

      {total === 0 ? (
        <div className="tab-empty">
          <span className="tab-empty-icon">
            <Icon name="broom" size={22} />
          </span>
          <h3>The checklist is empty</h3>
          <p>Add a manual task, or re-run the pre-flight to regenerate cleanup tasks.</p>
        </div>
      ) : (
        <div className="task-groups">
          {priorityOrder.map((priority) => {
            const group = items.filter((item) => item.priority === priority)
            if (group.length === 0) return null
            return (
              <section key={priority} className={`task-group p-${priority}`}>
                <header className="task-group-head">
                  <span className={`priority-badge p-${priority}`}>
                    {priorityLabels[priority]}
                  </span>
                  <span className="task-group-hint">{priorityHints[priority]}</span>
                  <span className="task-group-count">
                    {group.filter((item) => item.done).length}/{group.length}
                  </span>
                </header>

                <ul className="task-list">
                  {group.map((item) => {
                    const editing = editingId === item.id
                    return (
                      <li
                        key={item.id}
                        className={`task ${item.done ? 'is-done' : ''} ${
                          editing ? 'is-editing' : ''
                        }`}
                      >
                        <label className="task-check">
                          <input
                            type="checkbox"
                            checked={item.done}
                            onChange={() => toggle(item.id)}
                          />
                          <span className="task-checkmark" aria-hidden="true">
                            <Icon name="check" size={12} strokeWidth={2.4} />
                          </span>
                          <span className="sr-only">
                            Mark “{item.title}” {item.done ? 'incomplete' : 'complete'}
                          </span>
                        </label>

                        <div className="task-main">
                          {editing ? (
                            <form
                              className="task-edit-form"
                              onSubmit={(event) => {
                                event.preventDefault()
                                saveEdit()
                              }}
                            >
                              <input
                                className="text-input"
                                value={draftTitle}
                                onChange={(event) => setDraftTitle(event.target.value)}
                                maxLength={140}
                                autoFocus
                                aria-label="Task title"
                              />
                              <textarea
                                className="text-area"
                                value={draftDetail}
                                onChange={(event) => setDraftDetail(event.target.value)}
                                rows={2}
                                maxLength={500}
                                aria-label="Task detail"
                              />
                              <div className="task-edit-actions">
                                <button
                                  type="submit"
                                  className="btn btn-primary btn-small"
                                  disabled={!draftTitle.trim()}
                                >
                                  Save
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-ghost btn-small"
                                  onClick={() => setEditingId(null)}
                                >
                                  Cancel
                                </button>
                              </div>
                            </form>
                          ) : (
                            <>
                              <div className="task-title-row">
                                <span className="task-title">{item.title}</span>
                                {item.source_finding_id && (
                                  <span className="task-source">
                                    {item.source_finding_id}
                                  </span>
                                )}
                              </div>
                              {item.detail && <p className="task-detail">{item.detail}</p>}
                              <div className="task-meta">
                                <span>
                                  <Icon name={categoryIcons[item.category]} size={12} />
                                  {categoryLabels[item.category]}
                                </span>
                                {item.evidence_file && (
                                  <code>
                                    {item.evidence_file}
                                    {item.evidence_line ? `:${item.evidence_line}` : ''}
                                  </code>
                                )}
                              </div>
                            </>
                          )}
                        </div>

                        {!editing && (
                          <div className="task-actions">
                            <button
                              type="button"
                              className="icon-button"
                              onClick={() =>
                                startEdit(item.id, item.title, item.detail)
                              }
                              title="Edit task"
                              aria-label={`Edit ${item.title}`}
                            >
                              <Icon name="edit" size={14} />
                            </button>
                            <button
                              type="button"
                              className="icon-button icon-button-danger"
                              onClick={() => remove(item.id)}
                              title="Delete task"
                              aria-label={`Delete ${item.title}`}
                            >
                              <Icon name="trash" size={14} />
                            </button>
                          </div>
                        )}
                      </li>
                    )
                  })}
                </ul>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
