import type {
  AssessmentHistoryItem,
  AssessmentRecord,
  AssessmentStreamEvent,
  AssessmentSubmitInput,
  AssessmentSubmitResult,
} from '../types'

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await parseErrorMessage(response)
    throw new Error(message || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

async function parseErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === 'string') return payload.detail
  }
  return response.text()
}

export async function fetchHistory(): Promise<AssessmentHistoryItem[]> {
  const response = await fetch('/api/assessments')
  return parseResponse<AssessmentHistoryItem[]>(response)
}

export async function fetchHistoryDetail(assessmentId: string): Promise<AssessmentRecord> {
  const response = await fetch(`/api/assessments/${assessmentId}`)
  return parseResponse<AssessmentRecord>(response)
}

export async function submitAssessment(payload: AssessmentSubmitInput): Promise<AssessmentSubmitResult> {
  const response = await fetch('/api/assessments', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return parseResponse<AssessmentSubmitResult>(response)
}

export async function streamAssessment(
  payload: AssessmentSubmitInput,
  onEvent: (event: AssessmentStreamEvent) => void,
): Promise<void> {
  const response = await fetch('/api/assessments/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const message = await parseErrorMessage(response)
    throw new Error(message || `Request failed with status ${response.status}`)
  }
  if (!response.body) {
    throw new Error('浏览器未返回可读取的分析流')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n\r?\n/)
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const parsed = parseSseBlock(part)
      if (parsed) onEvent(parsed)
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseBlock(buffer)
    if (parsed) onEvent(parsed)
  }
}

function parseSseBlock(block: string): AssessmentStreamEvent | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice('event:'.length).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice('data:'.length).trim())
  }
  if (!dataLines.length) return null
  return {
    event,
    data: JSON.parse(dataLines.join('\n')),
  } as AssessmentStreamEvent
}
