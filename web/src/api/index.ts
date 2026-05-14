import type {
  AssessmentHistoryItem,
  AssessmentRecord,
  AssessmentSubmitInput,
  AssessmentSubmitResult,
} from '../types'

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
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
