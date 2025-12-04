import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="container">
          <div className="card" style={{ border: "1px solid var(--bad)" }}>
            <div className="title" style={{ color: "var(--bad)" }}>
              Something went wrong
            </div>
            <div className="sub">
              {this.state.error?.message || "An unexpected error occurred"}
            </div>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{ marginTop: "12px" }}
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.href = "/"}
              style={{ marginTop: "12px", marginLeft: "8px" }}
            >
              Go Home
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
