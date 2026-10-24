import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { analyzeFiles, explainFiles, getHealth } from './api'
import type {
  AiState,
  AnalysisResponse,
  ConfigFileState,
  CleanupTask,
  Demo,
  FilePayload,
  HealthResponse,
} from './types'
import { demos, fileTemplates } from './data/demos'
import type { TemplateFormat } from './components/ConfigPanel'
import { ConfigPanel } from './components/ConfigPanel'
import { ResultsPanel } from './components/ResultsPanel'
import { Header } from './components/Header'
import { Hero } from './components/Hero'
import { HowItWorks } from './components/HowItWorks'
import { Footer } from './components/Footer'
import { Icon } from './components/Icons'
import { useChecklist } from './hooks/useChecklist'
import { scrollToResults, uniquePath } from './lib/format'

const EMPTY_TASKS: CleanupTask[] = []
const MAX_FILES = 8
const MAX_FILE_BYTES = 120_000

const emptyAi: AiState = {
  status: 'idle',
  available: false,
  explanation: null,
  reason: null,
  model: null,
  guardrail: null,
}

function newFileId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `file-${crypto.randomUUID()}`
  }
  return `file-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function filesFromDemo(demo: Demo): ConfigFileState[] {
  return demo.files.map((file) => ({ ...file, id: newFileId() }))
}

const initialDemo = demos[0]
const initialFiles = initialDemo ? filesFromDemo(initialDemo) : []

export default function App() {
  const [files, setFiles] = useState<ConfigFileState[]>(initialFiles)
  const [activeId, setActiveId] = useState<string>(initialFiles[0]?.id ?? '')
  const [projectName, setProjectName] = useState(
    initialDemo?.projectName ?? 'My hackathon project',
  )
  const [demoId, setDemoId] = useState<string | null>(initialDemo?.id ?? null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [analysisInput, setAnalysisInput] = useState<{
    files: FilePayload[]
    projectName: string
  } | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)
  const [ai, setAi] = useState<AiState>(emptyAi)

  const [healthStatus, setHealthStatus] = useState<'checking' | 'online' | 'offline'>(
    'checking',
  )
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const runToken = useRef(0)
  const editVersion = useRef(0)

  const checkHealth = useCallback(async () => {
    setHealthStatus('checking')
    try {
      const result = await getHealth()
      setHealth(result)
      setHealthStatus('online')
    } catch {
      setHealth(null)
      setHealthStatus('offline')
    }
  }, [])

  useEffect(() => {
    void checkHealth()
  }, [checkHealth])

  const checklist = useChecklist(
    analysis?.fingerprint,
    analysis?.cleanup_tasks ?? EMPTY_TASKS,
  )

  const canRun = useMemo(
    () =>
      files.length > 0 &&
      files.every((file) => file.path.trim().length > 0 && file.content.trim().length > 0),
    [files],
  )

  const aiConfigured =
    healthStatus === 'online' ? (health?.ai_configured ?? false) : null

  const markDirty = useCallback(() => {
    editVersion.current += 1
    setDirty(true)
    setDemoId(null)
    setAi(emptyAi)
  }, [])

  const runAnalysisWith = useCallback(
    async (nextFiles: ConfigFileState[], nextProjectName: string, demo: string | null) => {
      const missing = nextFiles.find(
        (file) => !file.path.trim() || !file.content.trim(),
      )
      if (missing) {
        setError('Every file needs a path and some content before it can be checked.')
        return
      }

      const token = ++runToken.current
      const version = editVersion.current
      setAnalyzing(true)
      setError(null)
      setAi(emptyAi)
      try {
        const result = await analyzeFiles(
          nextFiles.map((file) => ({
            path: file.path.trim(),
            content: file.content,
          })),
          nextProjectName.trim() || 'My hackathon project',
        )
        if (token !== runToken.current) return
        setAnalysis(result)
        setAnalysisInput({
          files: nextFiles.map((file) => ({
            path: file.path.trim(),
            content: file.content,
          })),
          projectName: nextProjectName.trim() || 'My hackathon project',
        })
        if (editVersion.current === version) {
          setDirty(false)
          setDemoId(demo)
        } else {
          setDirty(true)
          setDemoId(null)
        }
        scrollToResults()
      } catch (err) {
        if (token !== runToken.current) return
        setError(err instanceof Error ? err.message : 'The analyzer request failed.')
      } finally {
        if (token === runToken.current) setAnalyzing(false)
      }
    },
    [],
  )

  const runAnalysis = useCallback(() => {
    void runAnalysisWith(files, projectName, demoId)
  }, [files, projectName, demoId, runAnalysisWith])

  const loadDemo = useCallback(
    (demo: Demo) => {
      editVersion.current += 1
      const nextFiles = filesFromDemo(demo)
      setFiles(nextFiles)
      setActiveId(nextFiles[0]?.id ?? '')
      setProjectName(demo.projectName)
      setDemoId(demo.id)
      setAnalysis(null)
      setAnalysisInput(null)
      setDirty(false)
      setError(null)
      setAi(emptyAi)
      void runAnalysisWith(nextFiles, demo.projectName, demo.id)
    },
    [runAnalysisWith],
  )

  const updateContent = useCallback(
    (id: string, content: string) => {
      setFiles((current) =>
        current.map((file) => (file.id === id ? { ...file, content } : file)),
      )
      markDirty()
    },
    [markDirty],
  )

  const updatePath = useCallback(
    (id: string, path: string) => {
      setFiles((current) =>
        current.map((file) => (file.id === id ? { ...file, path } : file)),
      )
      markDirty()
    },
    [markDirty],
  )

  const updateProjectName = useCallback(
    (value: string) => {
      setProjectName(value)
      markDirty()
    },
    [markDirty],
  )

  const addFile = useCallback(
    (format: TemplateFormat) => {
      if (files.length >= MAX_FILES) {
        setError(`CredPilot accepts at most ${MAX_FILES} files per check.`)
        return
      }
      const desired =
        format === 'render'
          ? 'render.yaml'
          : format === 'compose'
            ? 'docker-compose.yml'
            : '.env'
      const path = uniquePath(
        desired,
        files.map((file) => file.path),
      )
      const file: ConfigFileState = {
        id: newFileId(),
        path,
        content: fileTemplates[format],
      }
      setFiles((current) => [...current, file])
      setActiveId(file.id)
      markDirty()
    },
    [files, markDirty],
  )

  const removeFile = useCallback(
    (id: string) => {
      if (files.length <= 1) return
      const index = files.findIndex((file) => file.id === id)
      const next = files.filter((file) => file.id !== id)
      setFiles(next)
      if (activeId === id) {
        setActiveId(next[Math.min(index, next.length - 1)]?.id ?? '')
      }
      markDirty()
    },
    [files, activeId, markDirty],
  )

  const importFiles = useCallback(
    async (incoming: FileList | null) => {
      if (!incoming || incoming.length === 0) return
      const remaining = MAX_FILES - files.length
      if (remaining <= 0) {
        setError(`CredPilot accepts at most ${MAX_FILES} files per check.`)
        return
      }

      const loaded: ConfigFileState[] = []
      const paths = files.map((file) => file.path)
      const failures: string[] = []

      for (const file of Array.from(incoming).slice(0, remaining)) {
        if (file.size > MAX_FILE_BYTES) {
          failures.push(`${file.name} is larger than 120 KB.`)
          continue
        }
        try {
          const text = await file.text()
          if (!text.trim()) {
            failures.push(`${file.name} is empty.`)
            continue
          }
          if (text.includes('\0')) {
            failures.push(`${file.name} looks binary, not a text config.`)
            continue
          }
          const path = uniquePath(file.name, paths)
          paths.push(path)
          loaded.push({ id: newFileId(), path, content: text })
        } catch {
          failures.push(`${file.name} could not be read.`)
        }
      }

      if (loaded.length > 0) {
        setFiles((current) => [...current, ...loaded])
        setActiveId(loaded[0].id)
        markDirty()
      }
      setError(
        failures.length > 0
          ? failures.join(' ')
          : loaded.length === 0
            ? 'No files were imported.'
            : null,
      )
    },
    [files, markDirty],
  )

  const explain = useCallback(async () => {
    if (!analysis || !analysisInput) return
    setAi({
      status: 'loading',
      available: false,
      explanation: null,
      reason: null,
      model: health?.gemma_model ?? null,
      guardrail: null,
    })
    try {
      const result = await explainFiles(
        analysisInput.files,
        analysisInput.projectName,
      )
      setAi({
        status: 'done',
        available: result.available,
        explanation: result.explanation,
        reason: result.reason,
        model: result.model,
        guardrail: result.guardrail,
      })
    } catch (err) {
      setAi({
        status: 'done',
        available: false,
        explanation: null,
        reason:
          err instanceof Error
            ? err.message
            : 'The optional explanation could not be generated.',
        model: health?.gemma_model ?? null,
        guardrail: null,
      })
    }
  }, [analysis, analysisInput, health])

  return (
    <div className="app-shell">
      <div className="backdrop-grid" aria-hidden="true" />
      <Header
        healthStatus={healthStatus}
        health={health}
        onRetry={() => void checkHealth()}
      />

      <main>
        <Hero />

        <section className="workspace" id="analyzer" aria-label="CredPilot analyzer">
          <div className="workspace-heading">
            <p className="eyebrow">
              <Icon name="radar" size={14} /> Pre-flight console
            </p>
            <p className="workspace-note">
              Three supported formats. Deterministic checks. Optional AI narration.
            </p>
          </div>

          <div className="workspace-grid">
            <ConfigPanel
              files={files}
              activeId={activeId}
              projectName={projectName}
              demoId={demoId}
              analyzing={analyzing}
              canRun={canRun}
              onProjectName={updateProjectName}
              onSelectFile={setActiveId}
              onFileContent={updateContent}
              onFilePath={updatePath}
              onAddFile={addFile}
              onRemoveFile={removeFile}
              onImportFiles={(list) => void importFiles(list)}
              onLoadDemo={loadDemo}
              onRun={runAnalysis}
            />

            <ResultsPanel
              analysis={analysis}
              analyzing={analyzing}
              error={error}
              stale={dirty && analysis !== null}
              canRun={canRun}
              checklist={checklist}
              ai={ai}
              aiConfigured={aiConfigured}
              onRun={runAnalysis}
              onExplain={() => void explain()}
            />
          </div>
        </section>

        <HowItWorks />
      </main>

      <Footer />
    </div>
  )
}
