'use client';

import type { TaskEvent } from '@/lib/api';

type TimelineProps = {
  events: TaskEvent[];
  loading?: boolean;
};

function formatTimestamp(ts: string): string {
  const parsed = new Date(ts);
  if (Number.isNaN(parsed.getTime())) {
    return ts;
  }
  return parsed.toLocaleString();
}

function parseTimestamp(ts: string): number | null {
  const parsed = Date.parse(ts);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
}

function formatDelta(ms: number | null): string {
  if (ms === null || ms < 0) {
    return '—';
  }
  const seconds = Math.floor(ms / 1000);
  if (seconds < 1) {
    return '<1s';
  }
  const minutes = Math.floor(seconds / 60);
  const remSeconds = seconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${remSeconds}s`;
  }
  return `${seconds}s`;
}

function hasDetails(event: TaskEvent): boolean {
  return Object.keys(event.details || {}).length > 0;
}

export default function Timeline({ events, loading = false }: TimelineProps) {
  if (loading) {
    return <div className="callout">Loading timeline...</div>;
  }

  if (events.length === 0) {
    return <div className="callout">No events yet.</div>;
  }

  return (
    <ol className="timeline-list">
      {events.map((event, index) => {
        const prev = events[index - 1];
        const currentTs = parseTimestamp(event.ts);
        const prevTs = prev ? parseTimestamp(prev.ts) : null;
        const delta = currentTs !== null && prevTs !== null ? currentTs - prevTs : null;
        return (
        <li key={event.id} className="timeline-item">
          <div className={`timeline-dot timeline-dot-${event.status}`} aria-hidden="true" />
          <article className="timeline-card">
            <header className="timeline-head">
              <p className="timeline-time">{formatTimestamp(event.ts)}</p>
              <h3 className="timeline-title">{event.title}</h3>
            </header>
            <p className="timeline-elapsed">
              {index === 0 ? 'Start event' : `+${formatDelta(delta)} from previous step`}
            </p>
            <p className={`timeline-type timeline-type-${event.status}`}>{event.type}</p>
            {hasDetails(event) && (
              <details className="timeline-details">
                <summary>View details</summary>
                <pre>{JSON.stringify(event.details, null, 2)}</pre>
              </details>
            )}
          </article>
        </li>
        );
      })}
    </ol>
  );
}
