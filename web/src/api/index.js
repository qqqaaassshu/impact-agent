async function parseResponse(response) {
    if (!response.ok) {
        const message = await parseErrorMessage(response);
        throw new Error(message || `Request failed with status ${response.status}`);
    }
    return response.json();
}
async function parseErrorMessage(response) {
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
        const payload = (await response.json());
        if (typeof payload.detail === 'string')
            return payload.detail;
    }
    return response.text();
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
export async function streamAssessment(payload, onEvent) {
    const response = await fetch('/api/assessments/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
        },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const message = await parseErrorMessage(response);
        throw new Error(message || `Request failed with status ${response.status}`);
    }
    if (!response.body) {
        throw new Error('浏览器未返回可读取的分析流');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { value, done } = await reader.read();
        if (done)
            break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(/\r?\n\r?\n/);
        buffer = parts.pop() ?? '';
        for (const part of parts) {
            const parsed = parseSseBlock(part);
            if (parsed)
                onEvent(parsed);
        }
    }
    if (buffer.trim()) {
        const parsed = parseSseBlock(buffer);
        if (parsed)
            onEvent(parsed);
    }
}
function parseSseBlock(block) {
    let event = 'message';
    const dataLines = [];
    for (const line of block.split(/\r?\n/)) {
        if (line.startsWith('event:'))
            event = line.slice('event:'.length).trim();
        if (line.startsWith('data:'))
            dataLines.push(line.slice('data:'.length).trim());
    }
    if (!dataLines.length)
        return null;
    return {
        event,
        data: JSON.parse(dataLines.join('\n')),
    };
}
