/**
 * SSE event parsed from the sync stream.
 */
export interface SyncEvent {
  type: 'progress' | 'result' | 'error';
  stage?: string;
  current?: number;
  total?: number;
  cards_added?: number;
  cards_updated?: number;
  printings_added?: number;
  prices_added?: number;
  combos_synced?: number;
  duration_seconds?: number;
  errors?: string[];
  success?: boolean;
  summary?: string;
  detail?: string;
}

/**
 * Trigger a Scryfall data sync via POST with SSE streaming.
 *
 * The backend only accepts POST /api/sync with body {full: bool},
 * so we use fetch() with a ReadableStream to parse SSE events.
 *
 * Usage:
 *   const abort = triggerSync(
 *     (event) => console.log(event),
 *     () => console.log('done'),
 *     (err) => console.error(err),
 *     true // full sync
 *   );
 *   // later: abort();
 */
export function triggerSync(
  onMessage: (event: SyncEvent) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void,
  full = false,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch('/api/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Sync request failed: ${response.status} ${text}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body is not readable');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from the buffer.
        // SSE format: "data: <json>\n\n"
        const parts = buffer.split('\n\n');
        // The last part may be incomplete, so keep it in the buffer.
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          const trimmed = part.trim();
          if (!trimmed) continue;

          // Each SSE event line starts with "data: "
          const dataLine = trimmed
            .split('\n')
            .find((line) => line.startsWith('data: '));

          if (dataLine) {
            const jsonStr = dataLine.slice(6); // Remove "data: " prefix
            try {
              const event = JSON.parse(jsonStr) as SyncEvent;
              onMessage(event);
            } catch {
              // Skip malformed JSON lines
            }
          }
        }
      }

      onComplete?.();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Intentional abort, not an error
        return;
      }
      onError?.(err instanceof Error ? err : new Error(String(err)));
    }
  })();

  return () => {
    controller.abort();
  };
}
