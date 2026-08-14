import { useQuery } from '@tanstack/react-query';

import { endpoints } from '../lib/api';
import styles from './Page.module.css';

const ACTION_LABELS: Record<string, string> = {
  'auth.login_succeeded': 'Signed in',
  'auth.login_failed': 'Sign-in failed',
  'auth.logout': 'Signed out',
  'auth.session_expired': 'Session expired',
  'deployment.bootstrapped': 'Deployment initialized',
  'org.created': 'Organization created',
  'org.updated': 'Organization updated',
  'user.created': 'User created',
  'membership.granted': 'Member added',
  'membership.revoked': 'Member removed',
  'membership.role_changed': 'Role changed',
};

export function AuditPage() {
  const entries = useQuery({ queryKey: ['audit', 'entries'], queryFn: () => endpoints.auditEntries(50) });
  const chain = useQuery({ queryKey: ['audit', 'chain'], queryFn: endpoints.auditChain });

  return (
    <div>
      <div className={styles.header}>
        <div className={styles.kicker}>Assurance</div>
        <h1 className={styles.title}>Audit log</h1>
        <p className={styles.lede}>
          Every state change, hash-chained. Each entry commits to its predecessor, so altering
          one breaks every hash after it. The log is append-only in the database itself — the
          application's database role holds no UPDATE or DELETE grant on this table.
        </p>
      </div>

      <div className={styles.statGrid}>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Chain integrity</div>
          <div className={styles.statValue}>
            {chain.isLoading ? (
              <span style={{ fontSize: 15 }}>Checking…</span>
            ) : chain.data ? (
              <span
                className={chain.data.ok ? styles.chainOk : styles.chainBad}
                style={{ fontSize: 20 }}
              >
                {chain.data.ok ? 'Intact' : 'Broken'}
              </span>
            ) : (
              <span style={{ fontSize: 15 }}>Unavailable</span>
            )}
          </div>
          <div className={styles.statNote}>{chain.data?.summary ?? 'Verifying every hash…'}</div>
        </div>

        <div className={styles.stat}>
          <div className={styles.statLabel}>Entries</div>
          <div className={styles.statValue}>{chain.data?.entries_checked ?? '—'}</div>
          <div className={styles.statNote}>Since this deployment was initialized</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">Recent activity</h2>
          <span style={{ fontSize: 11, color: 'var(--app-text-muted)' }}>Newest first</span>
        </div>

        <div className={styles.tableWrap}>
          <table className="table">
            <thead>
              <tr>
                <th>Seq</th>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Target</th>
                <th>Hash</th>
              </tr>
            </thead>
            <tbody>
              {entries.isLoading ? (
                <tr>
                  <td colSpan={6} style={{ color: 'var(--app-text-muted)' }}>
                    Loading…
                  </td>
                </tr>
              ) : entries.data && entries.data.length > 0 ? (
                entries.data.map((entry) => (
                  <tr key={entry.id}>
                    <td className="mono">{entry.seq}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {new Date(entry.at).toLocaleString(undefined, {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                      })}
                    </td>
                    <td>{entry.actor_label}</td>
                    <td>{ACTION_LABELS[entry.action] ?? entry.action}</td>
                    <td style={{ color: 'var(--app-text-muted)' }}>{entry.target_type ?? '—'}</td>
                    <td className={styles.hashCell} title={entry.hash}>
                      {entry.hash.slice(0, 12)}…
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} style={{ color: 'var(--app-text-muted)' }}>
                    No entries yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
