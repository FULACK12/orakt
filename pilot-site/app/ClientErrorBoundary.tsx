"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { failed: boolean };

export default class ClientErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("NEWS Map client render failed", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="client-recovery" role="alert">
        <div>
          <span>NEWS MAP</span>
          <h1>页面组件未能完成加载</h1>
          <p>
            已阻止整个页面继续闪退。请重新加载；报告和地图会继续采用按需加载。
          </p>
          <small>
            A page component failed to load. Reload to start again with staged
            data loading.
          </small>
          <button type="button" onClick={() => window.location.reload()}>
            重新加载 / Reload
          </button>
        </div>
      </main>
    );
  }
}
