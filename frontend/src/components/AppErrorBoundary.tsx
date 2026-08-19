import { Component, type ErrorInfo, type ReactNode } from 'react';

interface AppErrorBoundaryProps {
  readonly children: ReactNode;
}

interface AppErrorBoundaryState {
  readonly hasError: boolean;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  public state: AppErrorBoundaryState = { hasError: false };

  public static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      console.error('Meridian failed to render.', error, info);
    }
  }

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main className="fatal-state">
          <p className="eyebrow">Application error</p>
          <h1>Meridian could not load this view.</h1>
          <p>Refresh the page. If the problem continues, check the frontend logs.</p>
        </main>
      );
    }

    return this.props.children;
  }
}
