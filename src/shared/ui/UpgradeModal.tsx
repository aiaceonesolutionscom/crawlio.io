import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckIcon, Loader2Icon, XIcon } from 'lucide-react';
import { Button } from './Button';
import { useSession } from '../../contexts/SessionContext';
import { PLANS } from '../../data/plans';
import { cn } from '../utils/cn';
import type { PlanId } from '../../types';

interface Props {
  open: boolean;
  onClose: () => void;
}

/** Calls the real PATCH /workspaces/{id}/plan endpoint. Redirect to the new tier's route root only fires after changePlan's setWorkspace has resolved, so RequirePlan on the new route sees the updated plan immediately instead of bouncing back. */
export function UpgradeModal({ open, onClose }: Props) {
  const { user, changePlan } = useSession();
  const navigate = useNavigate();
  const currentPlan = user?.workspace.plan ?? 'free';
  const [selected, setSelected] = useState<PlanId>(currentPlan === 'free' ? 'pro' : currentPlan);
  const [status, setStatus] = useState<'idle' | 'saving' | 'done' | 'error'>('idle');

  useEffect(() => {
    if (open) {
      setSelected(currentPlan === 'free' ? 'pro' : currentPlan);
      setStatus('idle');
    }
  }, [open, currentPlan]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const confirm = async () => {
    setStatus('saving');
    try {
      await changePlan(selected);
      setStatus('done');
      window.setTimeout(() => {
        onClose();
        navigate(`/app/${selected}`, { replace: true });
      }, 500);
    } catch {
      setStatus('error');
    }
  };

  return (
    <AnimatePresence>
      {open &&
      <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.button
          type="button"
          aria-label="Close"
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm" />

          <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="upgrade-title"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="relative w-full max-w-[720px] overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">

            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <div>
                <h2 id="upgrade-title" className="font-display text-[19px] font-semibold tracking-tight text-chalk">
                  Change your plan
                </h2>
                <p className="mt-1 text-[13.5px] text-chalk-dim">
                  Quotas lift immediately. Downgrades apply at the end of the cycle.
                </p>
              </div>
              <button
              type="button"
              onClick={onClose}
              aria-label="Close dialog"
              className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">

                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[60vh] overflow-y-auto scrollbar-slim px-6 py-5">
              <div className="grid gap-3 sm:grid-cols-3">
                {PLANS.map((plan) => {
                const isCurrent = plan.id === currentPlan;
                const isSelected = plan.id === selected;
                return (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => setSelected(plan.id)}
                    className={cn(
                      'rounded-xl border p-4 text-left transition-colors',
                      isSelected ? 'border-signal bg-ink-850' : 'border-ink-700 bg-ink-950 hover:border-ink-600'
                    )}>

                      <span className="flex items-center justify-between">
                        <span className="font-display text-[16px] font-semibold text-chalk">{plan.name}</span>
                        {isCurrent &&
                      <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[10px] uppercase text-chalk-dim">
                            Current
                          </span>
                      }
                      </span>
                      <span className="mt-2 block font-display text-[24px] font-semibold text-chalk">{plan.price}</span>
                      <span className="mt-1 block text-[12px] text-chalk-faint">{plan.priceNote}</span>
                      <span className="mt-3 block text-[12.5px] text-chalk-dim">{plan.leadQuota}</span>
                      <span className="block text-[12.5px] text-chalk-dim">{plan.seats}</span>
                    </button>);

              })}
              </div>
            </div>

            <div className="flex flex-col gap-3 border-t border-ink-850 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[12.5px] text-chalk-faint">
                {status === 'error' ?
              'Something went wrong updating your plan — try again.' :
              selected === 'enterprise' ?
              'Enterprise is quoted — our team will reach out within one business day.' :
              'Quotas update immediately on this workspace.'}
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button onClick={confirm} disabled={status === 'saving' || status === 'done' || selected === currentPlan}>
                  {status === 'saving' && <Loader2Icon className="h-4 w-4 animate-spin" />}
                  {status === 'done' && <CheckIcon className="h-4 w-4" />}
                  {status === 'idle' || status === 'error' ?
                `Switch to ${selected === 'pro' ? 'Pro' : selected === 'enterprise' ? 'Enterprise' : 'Free'}` :
                status === 'saving' ?
                'Updating…' :
                'Plan updated'}
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}
