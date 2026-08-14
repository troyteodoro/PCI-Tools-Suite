import type { ReactNode } from 'react';

import { ThemeIcon } from '../components/icons';
import { useTheme } from '../theme/ThemeProvider';
import styles from './AuthLayout.module.css';

export function AuthLayout({
  title,
  subtitle,
  error,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  error?: string | null;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.themeToggle}
        onClick={toggleTheme}
        aria-label={`Switch to ${theme === 'modernist' ? 'Nocturne' : 'Modernist'} theme`}
      >
        <ThemeIcon dark={theme === 'nocturne'} />
        {theme === 'modernist' ? 'Nocturne' : 'Modernist'}
      </button>

      <div className={styles.card}>
        <div className={styles.brand}>
          <div className={styles.brandMark} aria-hidden="true" />
          <div>
            <div className={styles.brandName}>Demarc</div>
            <div className={styles.brandStandard}>PCI DSS v4.0.1</div>
          </div>
        </div>

        <h1 className={styles.title}>{title}</h1>
        <p className={styles.subtitle}>{subtitle}</p>

        {error ? (
          <div className={styles.error} role="alert">
            {error}
          </div>
        ) : null}

        {children}

        {footer ? <div className={styles.footer}>{footer}</div> : null}
      </div>
    </div>
  );
}
