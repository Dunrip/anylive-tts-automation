export interface FetchWithTimeoutOptions extends RequestInit {
  timeout?: number
}

export async function fetchWithTimeout(
  url: string | URL,
  options: FetchWithTimeoutOptions = {}
): Promise<Response> {
  const { timeout = 30000, signal, ...fetchOptions } = options

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const mergedSignal = signal
      ? AbortSignal.any([signal, controller.signal])
      : controller.signal

    return await fetch(url, { ...fetchOptions, signal: mergedSignal })
  } finally {
    clearTimeout(timeoutId)
  }
}
