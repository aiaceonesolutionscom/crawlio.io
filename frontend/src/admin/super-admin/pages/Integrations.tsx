import React, { useCallback, useState } from 'react';
import { getAdminToken } from '../../../contexts/AdminSessionContext';
import { CheckCircle2Icon, KeyRoundIcon, PlayIcon, RefreshCcwIcon, XCircleIcon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Button } from '../../../shared/ui/Button';
import { useAdminResource } from '../../lib/useAdminResource';
import { useAdminSession } from '../../../contexts/AdminSessionContext';
import {
  clearIntegrationOverride,
  listIntegrations,
  setIntegrationOverride,
  testIntegration,
  type IntegrationDTO,
  type IntegrationTestResultDTO
} from '../../../lib/api/admin/integrations';
import { cn } from '../../../shared/utils/cn';

const SOURCE_BADGE: Record<string, { label: string; className: string }> = {
  override: { label: 'Panel override', className: 'border-signal/50 bg-signal/10 text-signal' },
  env: { label: 'From .env', className: 'border-ink-600 bg-ink-800 text-chalk-dim' },
  unset: { label: 'Not configured', className: 'border-ember/50 bg-ember/10 text-ember' }
};

export function Integrations() {

  const { admin } = useAdminSession();
  const canWrite = admin?.permissions.includes('integrations.write') ?? false;

  const fetchList = useCallback(() => Promise.resolve(listIntegrations(getAdminToken())), []);
  const { items, isLoading, refresh } = useAdminResource(fetchList);

  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [newValue, setNewValue] = useState('');
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, IntegrationTestResultDTO>>({});
  const [error, setError] = useState<string | null>(null);

  const handleSaveOverride = async (item: IntegrationDTO) => {
    if (!newValue.trim()) return;
    setError(null);
    setBusyKey(item.key);
    try {
      const token = getAdminToken();
      await setIntegrationOverride(token, item.key, newValue.trim());
      setEditingKey(null);
      setNewValue('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save API key');
    } finally {
      setBusyKey(null);
    }
  };

  const handleClearOverride = async (item: IntegrationDTO) => {
    if (!confirm(`Clear the panel override for ${item.label}? It will fall back to the .env value.`)) return;
    setError(null);
    setBusyKey(item.key);
    try {
      const token = getAdminToken();
      await clearIntegrationOverride(token, item.key);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear API key');
    } finally {
      setBusyKey(null);
    }
  };

  const handleTest = async (item: IntegrationDTO) => {
    setBusyKey(item.key);
    setError(null);
    try {
      const token = getAdminToken();
      const result = await testIntegration(token, item.key);
      setTestResults((prev) => ({ ...prev, [item.key]: result }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [item.key]: { ok: false, message: err instanceof Error ? err.message : 'Test failed' }
      }));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="API keys & integrations"
        description="Every external service Crawlio talks to. Set a key here to override .env at runtime — no code change or restart needed. Changes apply immediately across the API and background workers."
      />

      {error && <p className="mb-4 text-[13px] text-ember">{error}</p>}

      {isLoading && <p className="py-14 text-center text-[14px] text-chalk-dim">Loading…</p>}

      {!isLoading && (
        <div className="grid gap-4 sm:grid-cols-2">
          {items.map((item) => {
            const source = SOURCE_BADGE[item.source];
            const testResult = testResults[item.key];
            const editing = editingKey === item.key;
            return (
              <div
                key={item.key}
                className="flex flex-col rounded-2xl border border-ink-800 bg-ink-900 p-5"
              >
                <div className="mb-1 flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <KeyRoundIcon className="h-4 w-4 shrink-0 text-chalk-faint" aria-hidden="true" />
                    <h3 className="text-[14px] font-medium text-chalk">{item.label}</h3>
                  </div>
                  <span
                    className={cn(
                      'shrink-0 rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em]',
                      source.className
                    )}
                  >
                    {source.label}
                  </span>
                </div>

                <p className="mb-3 text-[12.5px] leading-relaxed text-chalk-dim">{item.description}</p>

                <div className="mb-4 rounded-lg border border-ink-800 bg-ink-950 px-3 py-2">
                  <p className="font-mono text-[12.5px] text-chalk">{item.masked_value || 'Not set'}</p>
                  <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-chalk-faint">
                    env: {item.env_name}
                  </p>
                </div>

                {editing && (
                  <div className="mb-3 space-y-2">
                    <input
                      autoFocus
                      type="password"
                      value={newValue}
                      onChange={(e) => setNewValue(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSaveOverride(item)}
                      placeholder={`Paste new ${item.label} key…`}
                      className="h-10 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 font-mono text-[13px] text-chalk outline-none focus:border-signal/60"
                    />
                    <div className="flex gap-2">
                      <Button size="sm" disabled={busyKey === item.key || !newValue.trim()} onClick={() => handleSaveOverride(item)}>
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busyKey === item.key}
                        onClick={() => {
                          setEditingKey(null);
                          setNewValue('');
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {testResult && (
                  <div
                    className={cn(
                      'mb-3 flex items-start gap-2 rounded-lg border px-3 py-2 text-[12.5px]',
                      testResult.ok
                        ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                        : 'border-ember/50 bg-ember/10 text-ember'
                    )}
                  >
                    {testResult.ok ? (
                      <CheckCircle2Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <XCircleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>{testResult.message}</span>
                  </div>
                )}

                <div className="mt-auto flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busyKey === item.key}
                    onClick={() => handleTest(item)}
                  >
                    {busyKey === item.key ? (
                      <RefreshCcwIcon className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <PlayIcon className="h-3.5 w-3.5" />
                    )}
                    Test
                  </Button>

                  {canWrite && (
                    <>
                      <Button size="sm" variant="ghost" disabled={busyKey === item.key} onClick={() => { setEditingKey(item.key); setNewValue(''); setTestResults((prev) => { const next = { ...prev }; delete next[item.key]; return next; }); }}>
                        Change key
                      </Button>
                      {item.source === 'override' && (
                        <Button size="sm" variant="ghost" disabled={busyKey === item.key} onClick={() => handleClearOverride(item)}>
                          Clear override
                        </Button>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}