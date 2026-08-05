import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Loader2Icon, PlusIcon, Trash2Icon, XIcon } from 'lucide-react';
import { Button } from '../../../shared/ui/Button';
import { createSequence, type CreateSequenceStepInput } from '../../../lib/api/automation';
import { ApiError } from '../../../lib/api/client';

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

function emptyStep(): CreateSequenceStepInput {
  return { subject: '', body: '', delay_hours: 0 };
}

export function AddSequenceModal({ open, onClose, onCreated }: Props) {
  const { getToken } = useAuth();
  const [name, setName] = useState('');
  const [steps, setSteps] = useState<CreateSequenceStepInput[]>([emptyStep()]);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName('');
    setSteps([emptyStep()]);
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const updateStep = (index: number, patch: Partial<CreateSequenceStepInput>) => {
    setSteps((prev) => prev.map((step, i) => i === index ? { ...step, ...patch } : step));
  };

  const removeStep = (index: number) => {
    setSteps((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsPending(true);
    setError(null);
    try {
      const token = await getToken();
      await createSequence(token, {
        name,
        trigger: 'lead_created',
        steps: steps.filter((s) => s.subject.trim() && s.body.trim())
      });
      reset();
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.');
    } finally {
      setIsPending(false);
    }
  };

  return (
    <AnimatePresence>
      {open &&
      <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.button
          type="button"
          aria-label="Close"
          onClick={handleClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm" />

          <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="add-sequence-title"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="relative max-h-[85vh] w-full max-w-[560px] overflow-y-auto rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">

            <div className="sticky top-0 flex items-start justify-between gap-4 border-b border-ink-850 bg-ink-900 px-6 py-5">
              <h2 id="add-sequence-title" className="font-display text-[18px] font-semibold tracking-tight text-chalk">
                New sequence
              </h2>
              <button
              type="button"
              onClick={handleClose}
              aria-label="Close dialog"
              className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">

                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5 px-6 py-5">
              <div>
                <label htmlFor="sequence-name" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Sequence name
                </label>
                <input
                  id="sequence-name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Q3 Manufacturing"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>

              <div className="space-y-3">
                <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-chalk-faint">Steps</p>
                {steps.map((step, i) =>
                <div key={i} className="rounded-xl border border-ink-800 bg-ink-950 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <span className="font-mono text-[11.5px] text-chalk-faint">Step {i + 1}</span>
                      {steps.length > 1 &&
                    <button
                      type="button"
                      onClick={() => removeStep(i)}
                      aria-label={`Remove step ${i + 1}`}
                      className="text-chalk-faint hover:text-ember">

                          <Trash2Icon className="h-3.5 w-3.5" />
                        </button>
                    }
                    </div>
                    <div className="space-y-3">
                      <input
                      required
                      value={step.subject}
                      onChange={(e) => updateStep(i, { subject: e.target.value })}
                      placeholder="Email subject"
                      className="h-10 w-full rounded-lg border border-ink-700 bg-ink-900 px-3 text-[13.5px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

                      <textarea
                      required
                      rows={3}
                      value={step.body}
                      onChange={(e) => updateStep(i, { body: e.target.value })}
                      placeholder="Email body"
                      className="w-full resize-none rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-[13.5px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

                      <div className="flex items-center gap-2">
                        <label htmlFor={`delay-${i}`} className="text-[12.5px] text-chalk-dim">
                          Send after
                        </label>
                        <input
                        id={`delay-${i}`}
                        type="number"
                        min={0}
                        value={step.delay_hours ?? 0}
                        onChange={(e) => updateStep(i, { delay_hours: Number(e.target.value) })}
                        className="h-9 w-20 rounded-lg border border-ink-700 bg-ink-900 px-2.5 text-[13px] text-chalk focus:border-signal focus:outline-none" />

                        <span className="text-[12.5px] text-chalk-dim">hours</span>
                      </div>
                    </div>
                  </div>
                )}
                <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSteps((prev) => [...prev, emptyStep()])}>

                  <PlusIcon className="h-3.5 w-3.5" />
                  Add step
                </Button>
              </div>

              {error &&
              <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                  {error}
                </p>
              }

              <div className="flex justify-end gap-2 border-t border-ink-850 pt-4">
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isPending}>
                  {isPending && <Loader2Icon className="h-4 w-4 animate-spin" />}
                  {isPending ? 'Creating…' : 'Create sequence'}
                </Button>
              </div>
            </form>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}
