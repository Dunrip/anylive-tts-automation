import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useHistory } from "../hooks/useHistory";

describe("useHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("starts in loading state and resolves to empty runs on null sidecarUrl", () => {
    const { result } = renderHook(() => useHistory(null));

    expect(result.current.loading).toBe(false);
    expect(result.current.runs).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });

  it("fetches and sets valid history run array", async () => {
    const validRuns = [
      {
        id: "run-1",
        automation_type: "tts",
        client: "default",
        status: "success",
        started_at: "2026-01-01T10:00:00Z",
        versions_total: 5,
        versions_success: 5,
        versions_failed: 0,
      },
    ];

    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(validRuns),
    });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.runs).toHaveLength(1);
    expect(result.current.runs[0].id).toBe("run-1");
    expect(result.current.error).toBeNull();
  });

  it("sets error when API returns non-array (isHistoryRunArray guard fails)", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ runs: [] }),
    });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Invalid history response shape");
    expect(result.current.runs).toHaveLength(0);
  });

  it("sets error when API returns array with malformed items (missing required fields)", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([{ id: 123, status: "success" }]),
    });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Invalid history response shape");
    expect(result.current.runs).toHaveLength(0);
  });

  it("sets error on HTTP failure", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("HTTP 500");
    expect(result.current.runs).toHaveLength(0);
  });

  it("refresh re-fetches history", async () => {
    const runs = [
      { id: "run-a", automation_type: "tts", client: "x", status: "success", started_at: "2026-01-01T00:00:00Z", versions_total: 1, versions_success: 1, versions_failed: 0 },
    ];

    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(runs) });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.runs).toHaveLength(0);

    result.current.refresh();

    await waitFor(() => expect(result.current.runs).toHaveLength(1));
    expect(result.current.runs[0].id).toBe("run-a");
  });

  it("sets error on network failure (fetch rejects with Error)", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Network error")
    );

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network error");
    expect(result.current.runs).toHaveLength(0);
  });

  it("uses fallback error message when fetch rejects with non-Error", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      "connection-refused"
    );

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Failed to load history");
    expect(result.current.runs).toHaveLength(0);
  });

  it("sets empty runs and no error when API returns empty array", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.runs).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });

  it("sets error when array contains a null item (isHistoryRunArray null check)", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([null]),
    });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Invalid history response shape");
    expect(result.current.runs).toHaveLength(0);
  });

  it("sets error when array item is missing started_at (isHistoryRunArray started_at check)", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([{ id: "run-1", status: "success" }]),
    });

    const { result } = renderHook(() => useHistory("http://127.0.0.1:8080"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Invalid history response shape");
    expect(result.current.runs).toHaveLength(0);
  });
});
