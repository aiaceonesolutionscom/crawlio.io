import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { MailIcon, PlusIcon, SplitIcon, Trash2Icon, ZapIcon } from 'lucide-react';
import { Button } from '../../ui/Button';
import { cn } from '../../utils/cn';
import {
  deleteSequence,
  listSequences,
  updateSequenceStatus,
  type SequenceDTO,
  type SequenceStatus
} from '../../../lib/api/automation';
import { AddSequenceModal } from './AddSequenceModal';

const STATUS_STYLES: Record<SequenceStatus, string> = {
  draft: 'border-ink-600 text-chalk-dim',
  active: 'border-signal/50 text-signal',
  paused: 'border-ember/40 text-ember'
};

export function AutomationFlow() {
  const { getToken } = useAuth();
  const [sequences, setSequences] = useState<SequenceDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    const token = await getToken();
    const res = await listSequences(token);
    setSequences(res.items);
    setIsLoading(false);
  }, [getToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const toggleStatus = async (sequence: SequenceDTO) => {
    setBusyId(sequence.id);
    const next: SequenceStatus = sequence.status === 'active' ? 'paused' : 'active';
    const token = await getToken();
    await updateSequenceStatus(token, sequence.id, next);
    await refresh();
    setBusyId(null);
  };

  const remove = async (sequence: SequenceDTO) => {
    setBusyId(sequence.id);
    const token = await getToken();
    await deleteSequence(token, sequence.id);
    await refresh();
    setBusyId(null);
  };

  return (
    <div className="rounded-2xl border border-ink-800 bg-ink-900 p-6">
      <div className="flex items-center justify-between gap-3">
        <p className="font-display text-[16px] font-semibold tracking-tight text-chalk">Email sequences</p>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <PlusIcon className="h-3.5 w-3.5" />
          New sequence
        </Button>
      </div>

      {isLoading &&
      <p className="mt-7 text-[14px] text-chalk-dim">Loading…</p>
      }

      {!isLoading && sequences.length === 0 &&
      <div className="mt-7 rounded-xl border border-dashed border-ink-800 p-8 text-center">
          <ZapIcon className="mx-auto h-6 w-6 text-chalk-faint" aria-hidden="true" />
          <p className="mt-3 text-[14px] text-chalk-dim">
            No sequences yet. Create one to email leads automatically as they come in.
          </p>
        </div>
      }

      {!isLoading && sequences.length > 0 &&
      <ol className="mt-7 space-y-3">
          {sequences.map((sequence) =>
        <li key={sequence.id} className="rounded-xl border border-ink-800 bg-ink-950 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-ink-700 bg-ink-850 text-signal">
                    <SplitIcon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[14.5px] font-medium text-chalk">{sequence.name}</span>
                    <span className="block font-mono text-[11.5px] text-chalk-faint">
                      Trigger: {sequence.trigger.replace('_', ' ')} · {sequence.steps.length} step
                      {sequence.steps.length === 1 ? '' : 's'}
                    </span>
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span
                  className={cn(
                    'rounded-full border px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider',
                    STATUS_STYLES[sequence.status]
                  )}>

                    {sequence.status}
                  </span>
                  <Button
                  size="sm"
                  variant="outline"
                  disabled={busyId === sequence.id}
                  onClick={() => toggleStatus(sequence)}>

                    {sequence.status === 'active' ? 'Pause' : 'Activate'}
                  </Button>
                  <button
                  type="button"
                  onClick={() => remove(sequence)}
                  disabled={busyId === sequence.id}
                  aria-label={`Delete ${sequence.name}`}
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-ember/50 hover:text-ember disabled:opacity-50">

                    <Trash2Icon className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              {sequence.steps.length > 0 &&
          <ol className="mt-3 space-y-1.5 border-t border-ink-850 pt-3">
                  {sequence.steps.map((step) =>
            <li key={step.id} className="flex items-center gap-2 text-[12.5px] text-chalk-dim">
                      <MailIcon className="h-3 w-3 shrink-0 text-chalk-faint" aria-hidden="true" />
                      <span className="truncate">{step.subject}</span>
                      <span className="shrink-0 text-chalk-faint">
                        {step.delay_hours === 0 ? 'immediately' : `after ${step.delay_hours}h`}
                      </span>
                    </li>
            )}
                </ol>
          }
            </li>
        )}
        </ol>
      }

      <AddSequenceModal open={addOpen} onClose={() => setAddOpen(false)} onCreated={refresh} />
    </div>);

}