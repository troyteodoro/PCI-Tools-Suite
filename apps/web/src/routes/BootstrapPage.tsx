import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError, endpoints } from '../lib/api';
import { AuthLayout } from './AuthLayout';

const MIN_PASSWORD_LENGTH = 12;

/**
 * First-run setup.
 *
 * There is no default credential and no bootstrap token: the window is open only while
 * the deployment has zero users, and closes permanently once this form succeeds. That
 * removes both "forgot to change the default password" and "the setup token leaked".
 */
export function BootstrapPage() {
  const queryClient = useQueryClient();
  const [orgName, setOrgName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');

  const mismatch = confirm.length > 0 && password !== confirm;
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD_LENGTH;

  const bootstrap = useMutation({
    mutationFn: () => endpoints.bootstrap({ org_name: orgName, full_name: fullName, email, password }),
    onSuccess: (session) => {
      queryClient.setQueryData(['session'], session);
      void queryClient.invalidateQueries({ queryKey: ['deployment'] });
    },
  });

  const errorMessage =
    bootstrap.error instanceof ApiError
      ? bootstrap.error.message
      : bootstrap.error
        ? 'Could not reach the server.'
        : null;

  const canSubmit =
    orgName.trim() !== '' &&
    fullName.trim() !== '' &&
    email.trim() !== '' &&
    password.length >= MIN_PASSWORD_LENGTH &&
    password === confirm &&
    !bootstrap.isPending;

  return (
    <AuthLayout
      title="Set up Demarc"
      subtitle="Name the organization being assessed and create its owner account. This runs once."
      error={errorMessage}
      footer="The owner can add engineers, and auditors who can read evidence but never alter it."
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) bootstrap.mutate();
        }}
      >
        <div className="field">
          <label htmlFor="orgName">Organization</label>
          <input
            id="orgName"
            className="input"
            required
            value={orgName}
            placeholder="Northgate Retail"
            onChange={(event) => setOrgName(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="fullName">Your name</label>
          <input
            id="fullName"
            className="input"
            required
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            className="input"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {tooShort ? (
            <div className="field-error">At least {MIN_PASSWORD_LENGTH} characters.</div>
          ) : (
            <div className="field-hint">
              Minimum {MIN_PASSWORD_LENGTH} characters — the floor requirement 8.3.6 sets.
            </div>
          )}
        </div>

        <div className="field">
          <label htmlFor="confirm">Confirm password</label>
          <input
            id="confirm"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
          {mismatch ? <div className="field-error">Passwords do not match.</div> : null}
        </div>

        <button type="submit" className="btn btn-primary btn-block" disabled={!canSubmit}>
          {bootstrap.isPending ? 'Creating…' : 'Create organization'}
        </button>
      </form>
    </AuthLayout>
  );
}
