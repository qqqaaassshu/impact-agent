async function parseResponse(response) {
    if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Request failed with status ${response.status}`);
    }
    return response.json();
}
export async function fetchHistory() {
    const response = await fetch('/api/assessments');
    return parseResponse(response);
}
export async function fetchHistoryDetail(assessmentId) {
    const response = await fetch(`/api/assessments/${assessmentId}`);
    return parseResponse(response);
}
export async function submitAssessment(payload) {
    const response = await fetch('/api/assessments', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}
