import { useLocation } from 'react-router-dom';

import { TOOL_ROUTES } from '../routes/routes';
import styles from './AppShell.module.css';

/**
 * PCI Coach.
 *
 * A renderer, not a thinker. From M3 it displays findings produced by the deterministic
 * rules engine; every card will carry the rules-pack version that produced it, so any
 * statement can be re-derived months later (docs/spec.md §7).
 *
 * Until then it explains the milestone state of whatever screen you are on, rather than
 * showing invented advice — placeholder advice in a compliance tool is worse than none.
 */
export function CoachRail() {
  const { pathname } = useLocation();
  const route = TOOL_ROUTES.find((candidate) => candidate.path === pathname);

  return (
    <aside className={styles.rail} aria-label="PCI Coach">
      <div className={styles.railHeader}>
        <div className={styles.brandMark} aria-hidden="true" />
        <div style={{ flex: 1 }}>
          <div className={styles.railTitle}>PCI Coach</div>
          <div className={styles.railSubtitle}>Deterministic rules engine · arrives in M3</div>
        </div>
      </div>

      <div className={styles.railBody}>
        <div className={`${styles.railCard} ${styles.railCardAccent}`}>
          <div className={styles.railCardLabel}>Where you stand</div>
          <div className={styles.railCardBody}>
            No evidence has been attached yet, so there is nothing to advise on. The Coach
            reads the evidence graph built in M1 and reports findings from the rules pack
            added in M3.
          </div>
        </div>

        {route ? (
          <div className={styles.railCard}>
            <div className={styles.railCardLabel}>About this screen</div>
            <div className={styles.railCardBody}>
              {route.description}
              {route.requirements.length > 0 && route.requirements[0] !== 'all' ? (
                <>
                  {' '}
                  Serves requirement{route.requirements.length > 1 ? 's' : ''}{' '}
                  {route.requirements.join(', ')}.
                </>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className={styles.railCard}>
          <div className={styles.railCardLabel}>Worth knowing</div>
          <div className={styles.railCardBody}>
            Demarc reports what evidence exists and what a rule found. It never states that
            a control is compliant — that determination belongs to your assessor.
          </div>
        </div>
      </div>
    </aside>
  );
}
