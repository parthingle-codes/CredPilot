import { useRef } from 'react'
import type { ConfigFileState, Demo } from '../types'
import { demos, fileTemplates } from '../data/demos'
import {
  basename,
  byteLength,
  detectFormat,
  formatBytes,
  formatLabel,
} from '../lib/format'
import { CodeEditor } from './CodeEditor'
import { Icon } from './Icons'

export type TemplateFormat = keyof typeof fileTemplates

interface ConfigPanelProps {
  files: ConfigFileState[]
  activeId: string
  projectName: string
  demoId: string | null
  analyzing: boolean
  canRun: boolean
  onProjectName: (value: string) => void
  onSelectFile: (id: string) => void
  onFileContent: (id: string, value: string) => void
  onFilePath: (id: string, value: string) => void
  onAddFile: (format: TemplateFormat) => void
  onRemoveFile: (id: string) => void
  onImportFiles: (files: FileList | null) => void
  onLoadDemo: (demo: Demo) => void
  onRun: () => void
}

const templateLabels: Record<TemplateFormat, string> = {
  render: 'Render',
  compose: 'Compose',
  dotenv: '.env',
}

const editorPlaceholders: Record<string, string> = {
  render: 'Paste a Render Blueprint (render.yaml)…',
  compose: 'Paste a Docker Compose file…',
  dotenv: 'Paste .env key/value pairs. Never use live production credentials…',
  unknown: 'Paste a supported configuration file…',
}

export function ConfigPanel({
  files,
  activeId,
  projectName,
  demoId,
  analyzing,
  canRun,
  onProjectName,
  onSelectFile,
  onFileContent,
  onFilePath,
  onAddFile,
  onRemoveFile,
  onImportFiles,
  onLoadDemo,
  onRun,
}: ConfigPanelProps) {
  const importRef = useRef<HTMLInputElement>(null)
  const activeFile = files.find((file) => file.id === activeId) ?? files[0]
  const format = activeFile
    ? detectFormat(activeFile.path, activeFile.content)
    : 'unknown'
  const lineCount = activeFile ? activeFile.content.split('\n').length : 0
  const bytes = activeFile ? byteLength(activeFile.content) : 0

  return (
    <section className="panel config-panel" aria-labelledby="config-heading">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">
            <span className="step-number">01</span> Configuration deck
          </p>
          <h2 id="config-heading">Feed it a deployment config</h2>
        </div>
        <span className="panel-badge">
          <Icon name="lock" size={13} /> Read-only
        </span>
      </div>

      <div className="demo-strip" aria-label="Synthetic demos">
        <div className="demo-strip-head">
          <span>Synthetic demos</span>
          {demoId && <span className="synthetic-tag">synthetic data loaded</span>}
        </div>
        <div className="demo-grid">
          {demos.map((demo) => (
            <button
              key={demo.id}
              type="button"
              className={`demo-card ${demoId === demo.id ? 'is-active' : ''}`}
              onClick={() => onLoadDemo(demo)}
              aria-pressed={demoId === demo.id}
            >
              <span className="demo-name">{demo.name}</span>
              <span className="demo-tagline">{demo.tagline}</span>
            </button>
          ))}
        </div>
      </div>

      <label className="field">
        <span className="field-label">Project label</span>
        <input
          className="text-input"
          value={projectName}
          maxLength={80}
          onChange={(event) => onProjectName(event.target.value)}
          placeholder="My hackathon project"
        />
      </label>

      <div className="file-tabs" role="tablist" aria-label="Configuration files">
        {files.map((file) => {
          const fileFormat = detectFormat(file.path, file.content)
          const active = file.id === activeFile?.id
          return (
            <div key={file.id} className={`file-tab ${active ? 'is-active' : ''}`}>
              <button
                type="button"
                role="tab"
                aria-selected={active}
                className="file-tab-select"
                onClick={() => onSelectFile(file.id)}
                title={file.path}
              >
                <span className={`format-dot format-${fileFormat}`} aria-hidden="true" />
                <span className="file-tab-name">{basename(file.path) || 'untitled'}</span>
              </button>
              <button
                type="button"
                className="file-tab-close"
                onClick={() => onRemoveFile(file.id)}
                disabled={files.length === 1}
                aria-label={`Remove ${file.path}`}
                title={files.length === 1 ? 'Keep at least one file' : 'Remove file'}
              >
                <Icon name="x" size={12} />
              </button>
            </div>
          )
        })}
      </div>

      {activeFile && (
        <div className="editor-block">
          <div className="editor-toolbar">
            <label className="path-field">
              <Icon name="file" size={14} />
              <span className="sr-only">File path</span>
              <input
                value={activeFile.path}
                onChange={(event) => onFilePath(activeFile.id, event.target.value)}
                spellCheck={false}
                aria-label="File path"
                placeholder="render.yaml"
              />
            </label>
            <span className={`format-pill format-${format}`}>
              {formatLabel(format)}
            </span>
            <button
              type="button"
              className="icon-button"
              onClick={() => onRemoveFile(activeFile.id)}
              disabled={files.length === 1}
              title={files.length === 1 ? 'Keep at least one file' : 'Remove this file'}
              aria-label="Remove this file"
            >
              <Icon name="trash" size={15} />
            </button>
          </div>

          <CodeEditor
            value={activeFile.content}
            onChange={(value) => onFileContent(activeFile.id, value)}
            onRun={onRun}
            placeholder={editorPlaceholders[format] ?? editorPlaceholders.unknown}
            ariaLabel={`${activeFile.path || 'Configuration'} content`}
          />

          <div className="editor-meta">
            <span>
              {lineCount} {lineCount === 1 ? 'line' : 'lines'} · {formatBytes(bytes)}
            </span>
            <span className="key-hint">
              <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> to run
            </span>
          </div>
        </div>
      )}

      <div className="config-actions">
        <div className="add-file-row">
          <span className="add-label">Add file</span>
          {(Object.keys(fileTemplates) as TemplateFormat[]).map((key) => (
            <button
              key={key}
              type="button"
              className="chip-button"
              onClick={() => onAddFile(key)}
              disabled={files.length >= 8}
            >
              <Icon name="plus" size={12} /> {templateLabels[key]}
            </button>
          ))}
          <button
            type="button"
            className="chip-button"
            onClick={() => importRef.current?.click()}
            disabled={files.length >= 8}
          >
            <Icon name="download" size={12} /> Import
          </button>
          <input
            ref={importRef}
            type="file"
            className="sr-only"
            accept=".yaml,.yml,.env,.txt,text/plain"
            multiple
            onChange={(event) => {
              onImportFiles(event.target.files)
              event.target.value = ''
            }}
          />
        </div>

        <button
          type="button"
          className="btn btn-primary run-button"
          onClick={onRun}
          disabled={!canRun || analyzing}
        >
          {analyzing ? (
            <>
              <span className="spinner" aria-hidden="true" /> Checking…
            </>
          ) : (
            <>
              <Icon name="radar" size={17} /> Run pre-flight
            </>
          )}
        </button>
      </div>

      <p className="config-footnote">
        <Icon name="shield" size={14} />
        Config text is sent to this app's analyzer only. It is not deployed, executed, or
        stored. Evidence is redacted before it is displayed or exported.
      </p>
    </section>
  )
}
