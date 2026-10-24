import type {
  AnalysisResponse,
  ExplainResponse,
  FilePayload,
  HealthResponse,
} from './types'

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')

export class ApiError extends Error {
  status: number

  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ErrorBody {
  detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>
}

async function errorMessage(response: Response): Promise<string> {
  let body: ErrorBody | null = null
  try {
    body = (await response.json()) as ErrorBody
  } catch {
    body = null
  }

  if (typeof body?.detail === 'string') {
    return body.detail
  }
  if (Array.isArray(body?.detail)) {
    const messages = body.detail
      .map((item) => {
        const field = item.loc?.filter((part) => part !== 'body').join('.')
        return `${field ? `${field}: ` : ''}${item.msg ?? 'invalid value'}`
      })
      .filter(Boolean)
    if (messages.length > 0) return messages.join('; ')
  }
  if (response.status === 429) {
    return 'Too many requests. Wait a moment and try again.'
  }
  return `Request failed with status ${response.status}.`
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers ?? {}),
      },
    })

    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status)
    }
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('The request timed out. The analyzer may still be running; try again.')
    }
    throw new ApiError(
      'Could not reach the CredPilot API. Start the backend with `uvicorn app.main:app --reload` or check the deployment.',
    )
  } finally {
    window.clearTimeout(timer)
  }
}

function payload(files: FilePayload[], projectName: string) {
  return JSON.stringify({ files, project_name: projectName })
}

export function analyzeFiles(
  files: FilePayload[],
  projectName: string,
): Promise<AnalysisResponse> {
  return requestJson<AnalysisResponse>(
    '/api/analyze',
    { method: 'POST', body: payload(files, projectName) },
    45_000,
  )
}

export function explainFiles(
  files: FilePayload[],
  projectName: string,
): Promise<ExplainResponse> {
  return requestJson<ExplainResponse>(
    '/api/explain',
    { method: 'POST', body: payload(files, projectName) },
    75_000,
  )
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/api/health', { method: 'GET' }, 8_000)
}
