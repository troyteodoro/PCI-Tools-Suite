import styles from './Page.module.css';

/**
 * Shown for tools whose milestone has not landed.
 *
 * States plainly what the tool will do and when it arrives. The alternative — a screen
 * of invented numbers — is actively harmful in a compliance product, where a reader
 * cannot easily tell demo data from their own.
 */
export function PlaceholderPage({
  kicker,
  title,
  description,
  milestone,
  requirements,
}: {
  kicker: string;
  title: string;
  description: string;
  milestone: string;
  requirements: string[];
}) {
  const named = requirements.filter((requirement) => requirement !== 'all');

  return (
    <div>
      <div className={styles.header}>
        <div className={styles.kicker}>{kicker}</div>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.lede}>{description}</p>
      </div>

      <div className={styles.emptyState}>
        <div className={styles.emptyTitle}>Not built yet — scheduled for {milestone}</div>
        <p className={styles.emptyBody}>
          The application shell, tenant isolation and audit log are in place (M0). This tool
          is built in {milestone}; see <code>docs/tasks.md</code> for the sequence and what each
          milestone depends on.
        </p>
        <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span className={styles.milestoneBadge}>Milestone {milestone}</span>
          {named.map((requirement) => (
            <span key={requirement} className="tag tag-outline">
              {requirement}
            </span>
          ))}
          {requirements.includes('all') ? (
            <span className="tag tag-outline">all requirements</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
