import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useConfig, useHealth } from '../hooks/useConfig';
import { triggerSync, type SyncEvent } from '../api/sync';
import type { AppConfigUpdate } from '../api/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SyncProgress {
  stage: string;
  current: number;
  total: number;
}

interface SyncResult {
  cards_added: number;
  cards_updated: number;
  printings_added: number;
  prices_added: number;
  combos_synced: number;
  duration_seconds: number;
  success: boolean;
  summary?: string;
}

// ---------------------------------------------------------------------------
// SettingsPage
// ---------------------------------------------------------------------------

/**
 * Settings, health monitoring, and sync management page.
 *
 * Sections:
 *   1. Health Status   — API + DB status with card count
 *   2. Configuration   — Editable fields saved via PUT /api/config
 *   3. API Key Status  — Derived from current LLM provider config
 *   4. Sync            — SSE-streaming full or incremental sync
 */
export default function SettingsPage() {
  useEffect(() => {
    document.title = 'Settings | MTG Deck Maker';
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6 pb-12">
      <header>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Settings</h1>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
          Manage configuration, monitor system health, and sync card data.
        </p>
      </header>

      <HealthSection />
      <ConfigSection />
      <ApiKeyStatusSection />
      <SyncSection />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Health Status
// ---------------------------------------------------------------------------

function HealthSection() {
  const { health, isLoading } = useHealth();

  const apiStatus = health ? 'online' : isLoading ? 'checking' : 'offline';
  const statusColor =
    apiStatus === 'online'
      ? 'text-[var(--color-budget-ok)]'
      : apiStatus === 'checking'
      ? 'text-[var(--color-text-secondary)]'
      : 'text-[var(--color-budget-over)]';

  return (
    <section
      aria-labelledby="health-heading"
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-5 space-y-4"
    >
      <h2
        id="health-heading"
        className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]"
      >
        System Status
      </h2>

      {isLoading && !health ? (
        <div className="animate-pulse space-y-2">
          <div className="h-5 w-2/3 rounded bg-[var(--color-surface-raised)]" />
          <div className="h-5 w-1/2 rounded bg-[var(--color-surface-raised)]" />
          <div className="h-5 w-3/4 rounded bg-[var(--color-surface-raised)]" />
        </div>
      ) : (
        <dl className="space-y-3 text-sm">
          {/* API connection */}
          <div className="flex items-center justify-between">
            <dt className="text-[var(--color-text-secondary)]">API Connection</dt>
            <dd className={['flex items-center gap-1.5 font-medium', statusColor].join(' ')}>
              <StatusDot status={apiStatus === 'online' ? 'ok' : apiStatus === 'checking' ? 'pending' : 'error'} />
              {apiStatus === 'online' ? 'Connected' : apiStatus === 'checking' ? 'Checking...' : 'Offline'}
            </dd>
          </div>

          {/* Database */}
          <div className="flex items-center justify-between">
            <dt className="text-[var(--color-text-secondary)]">Database</dt>
            <dd
              className={[
                'flex items-center gap-1.5 font-medium',
                health?.db_exists
                  ? 'text-[var(--color-budget-ok)]'
                  : 'text-[var(--color-budget-over)]',
              ].join(' ')}
            >
              <StatusDot status={health?.db_exists ? 'ok' : 'error'} />
              {health ? (health.db_exists ? 'Found' : 'Not found') : '--'}
            </dd>
          </div>

          {/* Card count */}
          <div className="flex items-center justify-between">
            <dt className="text-[var(--color-text-secondary)]">Cards in Database</dt>
            <dd className="font-mono text-sm text-[var(--color-text-primary)]">
              {health ? health.card_count.toLocaleString() : '--'}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: Configuration Editor
// ---------------------------------------------------------------------------

function ConfigSection() {
  const { config, isLoading, saveConfig, isSaving, saveError, isSaveSuccess, reset } = useConfig();
  const [formValues, setFormValues] = useState<AppConfigUpdate>({});
  const [showSuccess, setShowSuccess] = useState(false);
  const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Show success banner briefly after save
  useEffect(() => {
    if (isSaveSuccess) {
      setShowSuccess(true);
      setFormValues({});
      reset();
      if (successTimerRef.current) clearTimeout(successTimerRef.current);
      successTimerRef.current = setTimeout(() => setShowSuccess(false), 3000);
    }
    return () => {
      if (successTimerRef.current) clearTimeout(successTimerRef.current);
    };
  }, [isSaveSuccess, reset]);

  const hasChanges =
    (formValues.constraints && Object.keys(formValues.constraints).length > 0) ||
    (formValues.llm && Object.keys(formValues.llm).length > 0) ||
    (formValues.pricing && Object.keys(formValues.pricing).length > 0) ||
    (formValues.general && Object.keys(formValues.general).length > 0);

  const currentMaxPrice =
    formValues.constraints?.max_price_per_card ?? config?.constraints.max_price_per_card ?? 50;
  const currentProvider = formValues.llm?.provider ?? config?.llm.provider ?? 'auto';
  const currentOpenAIModel = formValues.llm?.openai_model ?? config?.llm.openai_model ?? '';
  const currentAnthropicModel = formValues.llm?.anthropic_model ?? config?.llm.anthropic_model ?? '';
  const currentResearchEnabled = formValues.llm?.research_enabled ?? config?.llm.research_enabled ?? true;

  const handleSave = () => {
    if (!hasChanges) return;
    saveConfig(formValues);
  };

  const inputClass = [
    'rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
    'px-3 py-2 text-sm text-[var(--color-text-primary)]',
    'placeholder:text-[var(--color-text-secondary)]',
    'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
    'transition-colors',
  ].join(' ');

  return (
    <section
      aria-labelledby="config-heading"
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-5 space-y-5"
    >
      <h2
        id="config-heading"
        className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]"
      >
        Configuration
      </h2>

      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 w-1/3 rounded bg-[var(--color-surface-raised)]" />
              <div className="h-9 rounded bg-[var(--color-surface-raised)]" />
            </div>
          ))}
        </div>
      ) : (
        <>
          {/* Budget constraints */}
          <fieldset className="space-y-4">
            <legend className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)] pb-1 border-b border-[var(--color-border)] w-full">
              Budget Constraints
            </legend>

            <div>
              <label
                htmlFor="max-price-per-card"
                className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]"
              >
                Max Price Per Card (USD)
              </label>
              <div className="relative w-40">
                <span
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[var(--color-text-secondary)]"
                  aria-hidden="true"
                >
                  $
                </span>
                <input
                  id="max-price-per-card"
                  type="number"
                  min={1}
                  max={10000}
                  step={5}
                  value={currentMaxPrice}
                  onChange={(e) =>
                    setFormValues((v) => ({
                      ...v,
                      constraints: {
                        ...v.constraints,
                        max_price_per_card: Number(e.target.value),
                      },
                    }))
                  }
                  className={['w-full pl-7', inputClass].join(' ')}
                  aria-describedby="max-price-hint"
                />
              </div>
              <p id="max-price-hint" className="mt-1 text-xs text-[var(--color-text-secondary)]">
                Cards above this price will be excluded from deck building.
              </p>
            </div>
          </fieldset>

          {/* LLM settings */}
          <fieldset className="space-y-4">
            <legend className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)] pb-1 border-b border-[var(--color-border)] w-full">
              AI Provider
            </legend>

            <div>
              <label
                htmlFor="llm-provider"
                className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]"
              >
                Default AI Provider
              </label>
              <select
                id="llm-provider"
                value={currentProvider}
                onChange={(e) =>
                  setFormValues((v) => ({
                    ...v,
                    llm: { ...v.llm, provider: e.target.value },
                  }))
                }
                className={inputClass}
              >
                <option value="auto">Auto (use available key)</option>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="openai">OpenAI (GPT)</option>
              </select>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="openai-model"
                  className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]"
                >
                  OpenAI Model
                </label>
                <input
                  id="openai-model"
                  type="text"
                  value={currentOpenAIModel}
                  placeholder="e.g. gpt-4o"
                  onChange={(e) =>
                    setFormValues((v) => ({
                      ...v,
                      llm: { ...v.llm, openai_model: e.target.value },
                    }))
                  }
                  className={['w-full', inputClass].join(' ')}
                />
              </div>

              <div>
                <label
                  htmlFor="anthropic-model"
                  className="mb-1.5 block text-sm font-medium text-[var(--color-text-secondary)]"
                >
                  Anthropic Model
                </label>
                <input
                  id="anthropic-model"
                  type="text"
                  value={currentAnthropicModel}
                  placeholder="e.g. claude-3-5-sonnet-20241022"
                  onChange={(e) =>
                    setFormValues((v) => ({
                      ...v,
                      llm: { ...v.llm, anthropic_model: e.target.value },
                    }))
                  }
                  className={['w-full', inputClass].join(' ')}
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                id="research-enabled-toggle"
                type="button"
                role="switch"
                aria-checked={currentResearchEnabled}
                aria-label="Enable AI research feature"
                onClick={() =>
                  setFormValues((v) => ({
                    ...v,
                    llm: { ...v.llm, research_enabled: !currentResearchEnabled },
                  }))
                }
                className={[
                  'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
                  'transition-colors duration-200 ease-in-out',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
                  currentResearchEnabled
                    ? 'bg-[var(--color-accent)]'
                    : 'bg-[var(--color-surface-raised)]',
                ].join(' ')}
              >
                <span
                  aria-hidden="true"
                  className={[
                    'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg',
                    'transform transition duration-200 ease-in-out',
                    currentResearchEnabled ? 'translate-x-5' : 'translate-x-0',
                  ].join(' ')}
                />
              </button>
              <label
                htmlFor="research-enabled-toggle"
                className="text-sm font-medium text-[var(--color-text-primary)] cursor-pointer select-none"
                onClick={() =>
                  setFormValues((v) => ({
                    ...v,
                    llm: { ...v.llm, research_enabled: !currentResearchEnabled },
                  }))
                }
              >
                Research feature enabled
              </label>
            </div>
          </fieldset>

          {/* Feedback */}
          {showSuccess && (
            <div
              role="status"
              aria-live="polite"
              className="flex items-center gap-2 rounded-md bg-green-950/60 border border-[var(--color-budget-ok)]/40 px-4 py-2 text-sm text-[var(--color-budget-ok)]"
            >
              <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Settings saved successfully.
            </div>
          )}

          {saveError && (
            <p role="alert" className="text-sm text-[var(--color-budget-over)]">
              Save failed: {saveError.message}
            </p>
          )}

          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving || !hasChanges}
            aria-busy={isSaving}
            className={[
              'rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors',
              'bg-[var(--color-accent)] text-white',
              'hover:bg-[var(--color-accent-hover)]',
              'disabled:opacity-40 disabled:cursor-not-allowed',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
            ].join(' ')}
          >
            {isSaving ? (
              <span className="flex items-center gap-2">
                <SpinnerIcon className="h-4 w-4" />
                Saving...
              </span>
            ) : (
              'Save Settings'
            )}
          </button>
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section: API Key Status
// ---------------------------------------------------------------------------

function ApiKeyStatusSection() {
  const { config, isLoading } = useConfig();

  // The backend never exposes actual keys. We infer "configured" status
  // from whether the provider is set to a specific value (not "auto"),
  // and inform the user to set keys via environment variables.
  const provider = config?.llm.provider ?? 'auto';
  const openAIModel = config?.llm.openai_model ?? '';
  const anthropicModel = config?.llm.anthropic_model ?? '';

  const openAIConfigured = provider === 'openai' || provider === 'auto';
  const anthropicConfigured = provider === 'anthropic' || provider === 'auto';

  return (
    <section
      aria-labelledby="apikey-heading"
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-5 space-y-4"
    >
      <h2
        id="apikey-heading"
        className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]"
      >
        API Key Status
      </h2>

      <p className="text-xs text-[var(--color-text-secondary)]">
        API keys are configured via environment variables and are never exposed here.
        Status reflects whether each provider is available based on your current settings.
      </p>

      {isLoading ? (
        <div className="animate-pulse space-y-3">
          <div className="h-10 rounded bg-[var(--color-surface-raised)]" />
          <div className="h-10 rounded bg-[var(--color-surface-raised)]" />
        </div>
      ) : (
        <dl className="space-y-3">
          <ApiKeyRow
            provider="OpenAI"
            envVar="OPENAI_API_KEY"
            model={openAIModel}
            isActive={openAIConfigured}
          />
          <ApiKeyRow
            provider="Anthropic"
            envVar="ANTHROPIC_API_KEY"
            model={anthropicModel}
            isActive={anthropicConfigured}
          />
        </dl>
      )}

      <p className="text-xs text-[var(--color-text-secondary)]">
        Set the <code className="rounded bg-[var(--color-surface-raised)] px-1 py-0.5 font-mono text-[10px]">OPENAI_API_KEY</code> or{' '}
        <code className="rounded bg-[var(--color-surface-raised)] px-1 py-0.5 font-mono text-[10px]">ANTHROPIC_API_KEY</code> environment
        variables when launching the backend server.
      </p>
    </section>
  );
}

interface ApiKeyRowProps {
  provider: string;
  envVar: string;
  model: string;
  isActive: boolean;
}

function ApiKeyRow({ provider, envVar, model, isActive }: ApiKeyRowProps) {
  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
      <div>
        <dt className="text-sm font-medium text-[var(--color-text-primary)]">{provider}</dt>
        <dd className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
          <code className="font-mono">{envVar}</code>
          {model && (
            <span className="ml-2 text-[var(--color-text-secondary)]">
              &bull; {model}
            </span>
          )}
        </dd>
      </div>
      <div
        className={[
          'flex items-center gap-1.5 text-xs font-medium',
          isActive ? 'text-[var(--color-budget-ok)]' : 'text-[var(--color-text-secondary)]',
        ].join(' ')}
        aria-label={`${provider} ${isActive ? 'available' : 'not selected'}`}
      >
        {isActive ? (
          <>
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Available
          </>
        ) : (
          <>
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            Not selected
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Sync
// ---------------------------------------------------------------------------

function SyncSection() {
  const queryClient = useQueryClient();
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const abortRef = useRef<(() => void) | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  const startTimer = () => {
    startTimeRef.current = Date.now();
    setElapsedSeconds(0);
    timerRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const handleSync = (full: boolean) => {
    if (isSyncing) return;

    setIsSyncing(true);
    setSyncProgress(null);
    setSyncResult(null);
    setSyncError(null);
    startTimer();

    const abort = triggerSync(
      (event: SyncEvent) => {
        if (event.type === 'progress') {
          setSyncProgress({
            stage: event.stage ?? '',
            current: event.current ?? 0,
            total: event.total ?? 0,
          });
        } else if (event.type === 'result') {
          setSyncResult({
            cards_added: event.cards_added ?? 0,
            cards_updated: event.cards_updated ?? 0,
            printings_added: event.printings_added ?? 0,
            prices_added: event.prices_added ?? 0,
            combos_synced: event.combos_synced ?? 0,
            duration_seconds: event.duration_seconds ?? 0,
            success: event.success ?? true,
            summary: event.summary,
          });
        } else if (event.type === 'error') {
          setSyncError(event.detail ?? 'An unknown error occurred.');
        }
      },
      () => {
        stopTimer();
        setIsSyncing(false);
        setSyncProgress(null);
        queryClient.invalidateQueries({ queryKey: ['health'] });
        abortRef.current = null;
      },
      (err: Error) => {
        stopTimer();
        setIsSyncing(false);
        setSyncProgress(null);
        setSyncError(err.message);
        abortRef.current = null;
      },
      full,
    );

    abortRef.current = abort;
  };

  const handleCancel = () => {
    abortRef.current?.();
    stopTimer();
    setIsSyncing(false);
    setSyncProgress(null);
    setSyncError('Sync cancelled.');
  };

  const progressPercent =
    syncProgress && syncProgress.total > 0
      ? Math.round((syncProgress.current / syncProgress.total) * 100)
      : null;

  return (
    <section
      aria-labelledby="sync-heading"
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)] p-5 space-y-5"
    >
      <div>
        <h2
          id="sync-heading"
          className="text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]"
        >
          Scryfall Data Sync
        </h2>
        <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
          Download and index card data from Scryfall. A full sync downloads all bulk data
          and may take several minutes. Quick Sync fetches only incremental price updates.
        </p>
      </div>

      {/* Sync buttons */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => handleSync(true)}
          disabled={isSyncing}
          aria-busy={isSyncing}
          className={[
            'rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors',
            'bg-[var(--color-accent)] text-white',
            'hover:bg-[var(--color-accent-hover)]',
            'disabled:opacity-40 disabled:cursor-not-allowed',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
          ].join(' ')}
        >
          {isSyncing ? (
            <span className="flex items-center gap-2">
              <SpinnerIcon className="h-4 w-4" />
              Syncing...
            </span>
          ) : (
            'Sync Database'
          )}
        </button>

        <button
          type="button"
          onClick={() => handleSync(false)}
          disabled={isSyncing}
          aria-busy={isSyncing}
          className={[
            'rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors',
            'border border-[var(--color-border)] bg-[var(--color-surface)]',
            'text-[var(--color-text-primary)]',
            'hover:bg-[var(--color-surface-raised)]',
            'disabled:opacity-40 disabled:cursor-not-allowed',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface)]',
          ].join(' ')}
        >
          Quick Sync
        </button>

        {isSyncing && (
          <button
            type="button"
            onClick={handleCancel}
            className={[
              'rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
              'text-[var(--color-budget-over)] hover:text-[var(--color-budget-over)]/80',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-budget-over)]',
            ].join(' ')}
          >
            Cancel
          </button>
        )}
      </div>

      {/* Progress display */}
      {isSyncing && (
        <div
          className="space-y-3"
          aria-live="polite"
          aria-label="Sync progress"
        >
          {/* Elapsed time */}
          <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
            <span>
              {syncProgress ? (
                <>
                  Stage: <span className="text-[var(--color-text-primary)] font-medium">{syncProgress.stage}</span>
                </>
              ) : (
                'Starting sync...'
              )}
            </span>
            <span aria-label={`${elapsedSeconds} seconds elapsed`}>
              {formatDuration(elapsedSeconds)}
            </span>
          </div>

          {/* Progress bar */}
          {syncProgress && (
            <div className="space-y-1">
              <div
                className="h-2 w-full rounded-full bg-[var(--color-surface-raised)] overflow-hidden"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={syncProgress.total || 100}
                aria-valuenow={syncProgress.current}
                aria-label={`Sync progress: ${progressPercent ?? 0}%`}
              >
                <div
                  className="h-full rounded-full bg-[var(--color-accent)] transition-[width] duration-300 ease-out"
                  style={{
                    width: progressPercent != null ? `${progressPercent}%` : '100%',
                    animation: progressPercent == null ? 'pulse 1.5s ease-in-out infinite' : 'none',
                  }}
                />
              </div>
              {syncProgress.total > 0 && (
                <p className="text-right text-xs text-[var(--color-text-secondary)]">
                  {syncProgress.current.toLocaleString()} / {syncProgress.total.toLocaleString()}
                  {progressPercent != null && ` (${progressPercent}%)`}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Completion summary */}
      {syncResult && !isSyncing && (
        <div
          role="status"
          aria-live="polite"
          className={[
            'rounded-md border px-4 py-4 space-y-3',
            syncResult.success
              ? 'border-[var(--color-budget-ok)]/40 bg-green-950/40'
              : 'border-[var(--color-budget-over)]/40 bg-red-950/40',
          ].join(' ')}
        >
          <div className="flex items-center gap-2">
            {syncResult.success ? (
              <svg className="h-4 w-4 shrink-0 text-[var(--color-budget-ok)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg className="h-4 w-4 shrink-0 text-[var(--color-budget-over)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            )}
            <p className={['text-sm font-semibold', syncResult.success ? 'text-[var(--color-budget-ok)]' : 'text-[var(--color-budget-over)]'].join(' ')}>
              {syncResult.success ? 'Sync completed' : 'Sync completed with issues'}
            </p>
          </div>

          {syncResult.summary && (
            <p className="text-xs text-[var(--color-text-secondary)]">{syncResult.summary}</p>
          )}

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
            <SyncStat label="Cards Added" value={syncResult.cards_added.toLocaleString()} />
            <SyncStat label="Cards Updated" value={syncResult.cards_updated.toLocaleString()} />
            <SyncStat label="Printings Added" value={syncResult.printings_added.toLocaleString()} />
            <SyncStat label="Prices Added" value={syncResult.prices_added.toLocaleString()} />
            <SyncStat label="Combos Synced" value={syncResult.combos_synced.toLocaleString()} />
            <SyncStat label="Duration" value={formatDuration(syncResult.duration_seconds)} />
          </dl>
        </div>
      )}

      {/* Error display */}
      {syncError && !isSyncing && (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-md border border-[var(--color-budget-over)]/40 bg-red-950/40 px-4 py-3"
        >
          <p className="text-sm font-semibold text-[var(--color-budget-over)]">Sync failed</p>
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{syncError}</p>
          <button
            type="button"
            onClick={() => setSyncError(null)}
            className="mt-2 text-xs text-[var(--color-accent)] hover:underline focus:outline-none"
          >
            Dismiss
          </button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

interface StatusDotProps {
  status: 'ok' | 'error' | 'pending';
}

function StatusDot({ status }: StatusDotProps) {
  const color =
    status === 'ok'
      ? 'bg-[var(--color-budget-ok)]'
      : status === 'error'
      ? 'bg-[var(--color-budget-over)]'
      : 'bg-[var(--color-text-secondary)] animate-pulse';

  return (
    <span
      className={['inline-block h-2 w-2 rounded-full shrink-0', color].join(' ')}
      aria-hidden="true"
    />
  );
}

interface SyncStatProps {
  label: string;
  value: string;
}

function SyncStat({ label, value }: SyncStatProps) {
  return (
    <div>
      <dt className="text-[var(--color-text-secondary)]">{label}</dt>
      <dd className="font-mono font-medium text-[var(--color-text-primary)]">{value}</dd>
    </div>
  );
}

function SpinnerIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg
      className={['animate-spin', className].join(' ')}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}
