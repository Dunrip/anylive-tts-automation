import React, { ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          data-testid="error-boundary-fallback"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            padding: "20px",
            backgroundColor: "#f5f5f5",
            fontFamily: "system-ui, -apple-system, sans-serif",
          }}
        >
          <h1 style={{ color: "#333", marginBottom: "10px" }}>Something went wrong</h1>
          <p style={{ color: "#666", marginBottom: "20px", textAlign: "center" }}>
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
           <button
             type="button"
             onClick={this.handleReload}
             style={{
               padding: "10px 20px",
               backgroundColor: "#007bff",
               color: "white",
               border: "none",
               borderRadius: "4px",
               cursor: "pointer",
               fontSize: "16px",
             }}
           >
             Reload Page
           </button>
        </div>
      );
    }

    return this.props.children;
  }
}
