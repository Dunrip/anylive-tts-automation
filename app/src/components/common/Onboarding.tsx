import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CheckCircle, Circle, Loader2, AlertCircle } from "lucide-react";

interface OnboardingProps {
  sidecarUrl: string;
  chromiumInstalled: boolean;
  sessionValid: boolean;
  onComplete: (opts: { sessionValid: boolean; displayName: string | null; email: string | null }) => void;
}

type Step = "check" | "chromium" | "login";
type StepStatus = "idle" | "loading" | "done" | "error";

const STEPS: { id: Step; label: string }[] = [
  { id: "check",    label: "Environment" },
  { id: "chromium", label: "Browser"     },
  { id: "login",    label: "Login"       },
];

export function Onboarding({ sidecarUrl, chromiumInstalled, sessionValid, onComplete }: OnboardingProps): React.ReactElement {
  const [step, setStep] = useState<Step>("check");
  const [chromiumStatus, setChromiumStatus] = useState<StepStatus>(chromiumInstalled ? "done" : "idle");
  const [chromiumMessage, setChromiumMessage] = useState("");
  const [loginStatus, setLoginStatus] = useState<StepStatus>(sessionValid ? "done" : "idle");
  const [loginMessage, setLoginMessage] = useState("");

  // Auto-complete if session is already valid when reaching login step
  useEffect(() => {
    if (step === "login" && sessionValid && loginStatus !== "loading") {
      setLoginStatus("done");
      setLoginMessage("Session already active.");
      const timer = setTimeout(() => {
        onComplete({ sessionValid: true, displayName: null, email: null });
      }, 900);
      return () => clearTimeout(timer);
    }
  }, [step, sessionValid, loginStatus, onComplete]);

  // Step 1: auto-advance from check → chromium (or login if chromium already done)
  useEffect(() => {
    if (step !== "check") return;
    const timer = setTimeout(() => {
      if (chromiumInstalled) {
        // Skip chromium step
        if (sessionValid) {
          onComplete({ sessionValid: true, displayName: null, email: null });
        } else {
          setStep("login");
        }
      } else {
        setStep("chromium");
      }
    }, 1200);
    return () => clearTimeout(timer);
  }, [step, chromiumInstalled, sessionValid, onComplete]);

  const chromiumTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const chromiumTimerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const [chromiumElapsed, setChromiumElapsed] = useState(0);

  const handleInstallChromium = async (): Promise<void> => {
    setChromiumStatus("loading");
    setChromiumElapsed(0);
    setChromiumMessage("Downloading Chromium browser (~150 MB). This may take a minute...");
    chromiumTimerRef.current = setInterval(() => setChromiumElapsed((s) => s + 1), 1000);
    try {
      const resp = await fetch(`${sidecarUrl}/api/setup/install-chromium`, { method: "POST" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.status === "installed" || data.status === "already_installed") {
        if (chromiumTimerRef.current) clearInterval(chromiumTimerRef.current);
        setChromiumStatus("done");
        setChromiumMessage("Chromium installed successfully.");
        chromiumTimeoutRef.current = setTimeout(() => setStep("login"), 800);
      } else {
        if (chromiumTimerRef.current) clearInterval(chromiumTimerRef.current);
        setChromiumStatus("error");
        setChromiumMessage(data.error || "Installation failed. Try again.");
      }
    } catch {
      if (chromiumTimerRef.current) clearInterval(chromiumTimerRef.current);
      setChromiumStatus("error");
      setChromiumMessage("Could not connect to sidecar.");
    }
  };

  const loginTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const handleLogin = async (): Promise<void> => {
    setLoginStatus("loading");
    setLoginMessage("Opening browser for login...");
    try {
      const resp = await fetch(`${sidecarUrl}/api/session/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform: "tts" }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.status === "ok") {
        setLoginStatus("done");
        setLoginMessage(`Welcome${data.display_name ? `, ${data.display_name}` : ""}!`);
        loginTimeoutRef.current = setTimeout(() => {
          onComplete({ sessionValid: true, displayName: data.display_name ?? null, email: data.email ?? null });
        }, 900);
      } else if (data.status === "timeout") {
        setLoginStatus("error");
        setLoginMessage("Login timed out. Please try again.");
      } else {
        setLoginStatus("error");
        setLoginMessage(data.error || "Login failed. Please try again.");
      }
    } catch {
      setLoginStatus("error");
      setLoginMessage("Could not connect to sidecar.");
    }
  };

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (chromiumTimeoutRef.current) clearTimeout(chromiumTimeoutRef.current);
      if (chromiumTimerRef.current) clearInterval(chromiumTimerRef.current);
      if (loginTimeoutRef.current) clearTimeout(loginTimeoutRef.current);
    };
  }, []);

  return (
    <div
      data-testid="onboarding"
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70"
    >
      <div className="w-[90%] max-w-[460px] rounded-2xl border border-[var(--border-default)] bg-[var(--bg-elevated)] shadow-xl overflow-hidden animate-panel-enter">

        {/* Header */}
        <div className="px-8 pt-8 pb-6 border-b border-[var(--border-default)]">
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
            Welcome to AnyLive TTS
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            Let&apos;s get you set up in a few steps.
          </p>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-0 px-8 py-4 border-b border-[var(--border-default)]">
          {STEPS.map((s, i) => {
            const isCurrent = s.id === step;
            const isDone = STEPS.findIndex((x) => x.id === step) > i || (s.id === "chromium" && chromiumStatus === "done" && step === "login") || (s.id === "check" && step !== "check");
            return (
              <React.Fragment key={s.id}>
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "size-6 rounded-full flex items-center justify-center text-xs font-semibold transition-colors",
                    isDone ? "bg-[var(--success)] text-white" :
                    isCurrent ? "bg-[var(--primary)] text-white" :
                    "bg-[var(--bg-hover)] text-[var(--text-muted)]"
                  )}>
                    {isDone ? "✓" : i + 1}
                  </div>
                  <span className={cn(
                    "text-sm transition-colors",
                    isCurrent ? "text-[var(--text-primary)] font-medium" :
                    isDone ? "text-[var(--text-secondary)]" :
                    "text-[var(--text-muted)]"
                  )}>
                    {s.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={cn(
                    "flex-1 h-px mx-3 transition-colors",
                    STEPS.findIndex((x) => x.id === step) > i ? "bg-[var(--success)]" : "bg-[var(--border-default)]"
                  )} />
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Step content */}
        <div className="px-8 py-7 min-h-[180px]">

          {/* Step 1: Environment check */}
          {step === "check" && (
            <div className="flex flex-col gap-4">
              <CheckRow
                label="Sidecar connected"
                status="done"
              />
              <CheckRow
                label={chromiumInstalled ? "Chromium browser ready" : "Checking Chromium..."}
                status={chromiumInstalled ? "done" : "loading"}
              />
              <CheckRow
                label={sessionValid ? "Session active" : "Login required"}
                status={sessionValid ? "done" : "idle"}
              />
            </div>
          )}

          {/* Step 2: Chromium install */}
          {step === "chromium" && (
            <div className="flex flex-col gap-5">
              <div>
                <p className="text-sm font-medium text-[var(--text-primary)] mb-1">
                  Chromium browser not found
                </p>
                <p className="text-sm text-[var(--text-secondary)]">
                  Chromium is required for browser automation. This is a one-time setup.
                </p>
              </div>

              {chromiumMessage && (
                <p className={cn(
                  "text-sm",
                  chromiumStatus === "error" ? "text-[var(--error)]" :
                  chromiumStatus === "done" ? "text-[var(--success)]" :
                  "text-[var(--text-secondary)]"
                )}>
                  {chromiumMessage}
                  {chromiumStatus === "loading" && chromiumElapsed > 0 && (
                    <span className="text-[var(--text-muted)] ml-1">({chromiumElapsed}s)</span>
                  )}
                </p>
              )}

              {chromiumStatus !== "done" && (
                <Button
                  data-testid="install-chromium-button"
                  variant="success"
                  onClick={handleInstallChromium}
                  disabled={chromiumStatus === "loading"}
                  className="w-fit"
                >
                  {chromiumStatus === "loading" ? (
                    <><Loader2 className="size-4 animate-spin" /> Installing...</>
                  ) : chromiumStatus === "error" ? "Retry Install" : "Install Chromium"}
                </Button>
              )}
            </div>
          )}

          {/* Step 3: Login */}
          {step === "login" && (
            <div className="flex flex-col gap-5">
              <div>
                <p className="text-sm font-medium text-[var(--text-primary)] mb-1">
                  Login to AnyLive
                </p>
                <p className="text-sm text-[var(--text-secondary)]">
                  A browser window will open. Log in to your AnyLive account to continue.
                </p>
              </div>

              {loginMessage && (
                <p className={cn(
                  "text-sm",
                  loginStatus === "error" ? "text-[var(--error)]" :
                  loginStatus === "done" ? "text-[var(--success)]" :
                  "text-[var(--text-secondary)]"
                )}>
                  {loginMessage}
                </p>
              )}

              {loginStatus !== "done" && (
                <Button
                  data-testid="login-button"
                  variant="success"
                  onClick={handleLogin}
                  disabled={loginStatus === "loading"}
                  className="w-fit"
                >
                  {loginStatus === "loading" ? (
                    <><Loader2 className="size-4 animate-spin" /> Waiting for login...</>
                  ) : loginStatus === "error" ? "Try Again" : "Login with Browser"}
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CheckRow({ label, status }: { label: string; status: "done" | "loading" | "error" | "idle" }): React.ReactElement {
  return (
    <div className="flex items-center gap-3">
      {status === "done" && <CheckCircle className="size-4 text-[var(--success)] shrink-0" />}
      {status === "loading" && <Loader2 className="size-4 text-[var(--running)] shrink-0 animate-spin" />}
      {status === "error" && <AlertCircle className="size-4 text-[var(--error)] shrink-0" />}
      {status === "idle" && <Circle className="size-4 text-[var(--text-muted)] shrink-0" />}
      <span className={cn(
        "text-sm",
        status === "done" ? "text-[var(--text-primary)]" :
        status === "loading" ? "text-[var(--text-secondary)]" :
        "text-[var(--text-muted)]"
      )}>
        {label}
      </span>
    </div>
  );
}
