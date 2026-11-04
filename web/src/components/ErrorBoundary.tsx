import { Component, type ErrorInfo, type ReactNode } from "react";

import { ToneGlyph } from "./icons";

/** Last line of defence: a render error shows a message instead of a blank page. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="state state--error" role="alert">
        <p className="state__title">
          <ToneGlyph tone="alert" size={14} />
          Something went wrong in the interface
        </p>
        <p className="state__detail">{this.state.error.message}</p>
        <a className="state__link" href="/">
          Reload the fleet
        </a>
      </div>
    );
  }
}
