import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ProgressBar } from "../components/common/ProgressBar";

describe("ProgressBar", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  describe("progress text and percentage", () => {
    it("shows 0/0 versions (0%) when both current and total are zero", () => {
      render(<ProgressBar current={0} total={0} />);
      expect(screen.getByTestId("progress-text").textContent).toBe("0/0 versions (0%)");
    });

    it("shows 0% when current=1: first item in-flight, none completed yet", () => {
      render(<ProgressBar current={1} total={5} />);
      expect(screen.getByTestId("progress-text").textContent).toBe("0/5 versions (0%)");
    });

    it("shows 20% when current=2 of 5 (1 completed)", () => {
      render(<ProgressBar current={2} total={5} />);
      expect(screen.getByTestId("progress-text").textContent).toBe("1/5 versions (20%)");
    });

    it("shows 100% when current equals total", () => {
      render(<ProgressBar current={5} total={5} />);
      expect(screen.getByTestId("progress-text").textContent).toBe("5/5 versions (100%)");
    });

    it("clamps to 100% when current exceeds total", () => {
      render(<ProgressBar current={7} total={5} />);
      expect(screen.getByTestId("progress-text").textContent).toBe("5/5 versions (100%)");
    });

    it("shows 50% when current=4 of 6 (3 completed)", () => {
      render(<ProgressBar current={4} total={6} />);
      expect(screen.getByTestId("progress-text").textContent).toBe("3/6 versions (50%)");
    });

    it("shows 100% for single-item job when complete", () => {
      render(<ProgressBar current={1} total={1} />);
      expect(screen.getByTestId("progress-text").textContent).toBe("1/1 versions (100%)");
    });
  });

  describe("formatDuration via elapsed on completed jobs", () => {
    it("formats sub-60s as seconds only", () => {
      const startTime = Date.now() - 45000;
      render(<ProgressBar current={5} total={5} startTime={startTime} />);
      expect(screen.getByTestId("progress-elapsed").textContent).toBe("45s elapsed");
    });

    it("formats exactly 60s as '1m 0s'", () => {
      const startTime = Date.now() - 60000;
      render(<ProgressBar current={5} total={5} startTime={startTime} />);
      expect(screen.getByTestId("progress-elapsed").textContent).toBe("1m 0s elapsed");
    });

    it("formats 90s as '1m 30s'", () => {
      const startTime = Date.now() - 90000;
      render(<ProgressBar current={5} total={5} startTime={startTime} />);
      expect(screen.getByTestId("progress-elapsed").textContent).toBe("1m 30s elapsed");
    });

    it("formats 125s as '2m 5s'", () => {
      const startTime = Date.now() - 125000;
      render(<ProgressBar current={5} total={5} startTime={startTime} />);
      expect(screen.getByTestId("progress-elapsed").textContent).toBe("2m 5s elapsed");
    });
  });

  describe("elapsed display", () => {
    it("does not render elapsed when startTime is omitted", () => {
      render(<ProgressBar current={2} total={5} />);
      expect(screen.queryByTestId("progress-elapsed")).not.toBeInTheDocument();
    });

    it("does not render elapsed when current=0 (job not started)", () => {
      render(<ProgressBar current={0} total={5} startTime={Date.now() - 5000} />);
      expect(screen.queryByTestId("progress-elapsed")).not.toBeInTheDocument();
    });

    it("shows elapsed for a completed job with startTime set", () => {
      render(<ProgressBar current={5} total={5} startTime={Date.now() - 10000} />);
      expect(screen.getByTestId("progress-elapsed")).toBeTruthy();
    });

    it("shows elapsed during in-progress job after the 1-second interval fires", async () => {
      vi.useFakeTimers();
      const startTime = Date.now();
      render(<ProgressBar current={2} total={5} startTime={startTime} />);
      await act(async () => {
        vi.advanceTimersByTime(3000);
      });
      expect(screen.getByTestId("progress-elapsed")).toBeTruthy();
    });
  });

  describe("ETA display", () => {
    it("does not render ETA without startTime", () => {
      render(<ProgressBar current={2} total={5} />);
      expect(screen.queryByTestId("progress-eta")).not.toBeInTheDocument();
    });

    it("does not render ETA when current=1 (completedItems=0, nothing done yet)", async () => {
      vi.useFakeTimers();
      const startTime = Date.now();
      render(<ProgressBar current={1} total={5} startTime={startTime} />);
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });
      expect(screen.queryByTestId("progress-eta")).not.toBeInTheDocument();
    });

    it("does not render ETA when job is complete (completedItems equals total)", () => {
      render(<ProgressBar current={5} total={5} startTime={Date.now() - 30000} />);
      expect(screen.queryByTestId("progress-eta")).not.toBeInTheDocument();
    });

    it("shows ~40s ETA: current=2 of 5, 10s elapsed, 1 item at 10s each gives 4 remaining", async () => {
      vi.useFakeTimers();
      const startTime = Date.now();
      render(<ProgressBar current={2} total={5} startTime={startTime} />);
      await act(async () => {
        vi.advanceTimersByTime(10000);
      });
      expect(screen.getByTestId("progress-eta").textContent).toBe("~40s remaining");
    });

    it("shows ~1m 20s ETA: current=3 of 10, 20s elapsed, 2 items at 10s each gives 8 remaining", async () => {
      vi.useFakeTimers();
      const startTime = Date.now();
      render(<ProgressBar current={3} total={10} startTime={startTime} />);
      await act(async () => {
        vi.advanceTimersByTime(20000);
      });
      expect(screen.getByTestId("progress-eta").textContent).toBe("~1m 20s remaining");
    });
  });
});
