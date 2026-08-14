import { Link } from 'react-router-dom';

import { useAuthenticatedSession } from '../lib/session';
import { TOOL_ROUTES } from './routes';
import styles from './Page.module.css';

/**
 * Readiness dashboard.
 *
 * The mockup's stat tiles (evidence complete, requirements met, blockers, days to
 * assessment) all read from the evidence graph, which arrives in M1. Rather than render
 * them with invented numbers, M0 shows what is genuinely known: the deployment is up and
 * empty.
 */
export function DashboardPage() {
  const session = useAuthenticatedSession();

  return (
    <div>
      <div className={styles.header}>
        <div className={styles.kicker}>Readiness</div>
        <h1 className={styles.title}>Nothing collected yet</h1>
        <p className={styles.lede}>
          {session.organization.name} is set up and no evidence has been attached. Evidence
          artifacts, the requirement catalog and the checklist arrive in M1; from then on this
          screen shows collection progress against your assessment date.
        </p>
      </div>

      <div className={styles.emptyState}>
        <div className={styles.emptyTitle}>What works today</div>
        <p className={styles.emptyBody}>
          Sign-in, roles and the hash-chained audit log are live. Every state change is
          already being recorded and can be verified from the audit screen — the chain
          starts from your first action, so it covers the whole life of this deployment.
        </p>
        <div style={{ marginTop: 14 }}>
          <Link to="/audit" className="btn btn-secondary">
            View the audit log
          </Link>
        </div>
      </div>

      <h2 className={styles.sectionTitle}>Tools</h2>
      <div className={styles.cardGrid}>
        {TOOL_ROUTES.map((route) => (
          <Link key={route.path} to={route.path} className={styles.toolCard}>
            <div className={styles.toolHead}>
              <span className={styles.toolName}>{route.label}</span>
              <span className="tag tag-neutral" style={{ marginLeft: 'auto' }}>
                {route.milestone}
              </span>
            </div>
            <p className={styles.toolBody}>{route.description}</p>
            <div className={styles.toolMeta}>
              {route.requirements.length > 0 ? (
                <span>
                  {route.requirements.includes('all')
                    ? 'All requirements'
                    : route.requirements.join(' · ')}
                </span>
              ) : (
                <span>Assessment delivery</span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
