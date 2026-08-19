import type { ReactNode } from 'react';

interface EmptyStateProps {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly children?: ReactNode;
}

export function EmptyState({ eyebrow, title, description, children }: EmptyStateProps) {
  return (
    <section className="empty-state">
      <div aria-hidden="true" className="empty-state-mark">
        <span />
        <span />
        <span />
      </div>
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{description}</p>
        {children}
      </div>
    </section>
  );
}
