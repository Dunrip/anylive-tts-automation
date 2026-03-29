import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { fetchWithTimeout } from "../lib/fetchWithTimeout"

describe("fetchWithTimeout", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  it("returns response on successful fetch", async () => {
    const mockResponse = { ok: true, status: 200 } as Response
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(mockResponse)

    const result = await fetchWithTimeout("http://example.com")

    expect(result).toBe(mockResponse)
    expect(globalThis.fetch).toHaveBeenCalledOnce()
  })

  it("throws AbortError on timeout", async () => {
    const mockFetch = vi.fn(async (_url: string, options?: RequestInit) => {
      if (options?.signal) {
        return new Promise<Response>((_, reject) => {
          options.signal!.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"))
          })
        })
      }
      return new Promise<Response>(() => {})
    })
    globalThis.fetch = mockFetch as typeof fetch

    const promise = fetchWithTimeout("http://example.com", { timeout: 50 })

    try {
      await promise
      expect.fail("Should have thrown AbortError")
    } catch (error) {
      expect(error).toBeInstanceOf(DOMException)
      expect((error as DOMException).name).toBe("AbortError")
    }
  })

  it("caller-provided abort signal triggers abort rejection", async () => {
    const controller = new AbortController()
    const mockFetch = vi.fn(async (_url: string, options?: RequestInit) => {
      if (options?.signal) {
        return new Promise<Response>((_, reject) => {
          options.signal!.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"))
          })
        })
      }
      return new Promise<Response>(() => {})
    })
    globalThis.fetch = mockFetch as typeof fetch

    const promise = fetchWithTimeout("http://example.com", {
      signal: controller.signal,
    })

    controller.abort()

    try {
      await promise
      expect.fail("Should have thrown AbortError")
    } catch (error) {
      expect(error).toBeInstanceOf(DOMException)
      expect((error as DOMException).name).toBe("AbortError")
    }
  })

  it("clears timeout on success", async () => {
    vi.useFakeTimers()
    const clearTimeoutSpy = vi.spyOn(global, "clearTimeout")
    const mockResponse = { ok: true } as Response
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(mockResponse)

    await fetchWithTimeout("http://example.com", { timeout: 5000 })

    expect(clearTimeoutSpy).toHaveBeenCalled()
    vi.useRealTimers()
  })
})
