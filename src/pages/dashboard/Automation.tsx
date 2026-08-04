import React from 'react';
import { ArrowRightIcon, MailIcon, MessageSquareIcon, SplitIcon, ZapIcon } from 'lucide-react';
import { PageHeader } from '../../components/dashboard/PageHeader';
import { PlanGate } from '../../components/dashboard/PlanGate';
import { useAuth } from '../../contexts/AuthContext';
import { useDashboardChrome } from '../../hooks/useDashboardChrome';
import { can } from '../../utils/plan';

const NODES = [
{ icon: ZapIcon, title: 'New lead captured', meta: 'Trigger · any source' },
{ icon: SplitIcon, title: 'Score ≥ 70?', meta: 'Condition · AI qualification' },
{ icon: MailIcon, title: 'Send intro email', meta: 'Action · sequence “Q3 Manufacturing”' },
{ icon: MessageSquareIcon, title: 'WhatsApp follow-up after 48h', meta: 'Action · if no reply' }];


export function Automation() {
  const { user } = useAuth();
  const { openUpgrade } = useDashboardChrome();
  if (!user) return null;

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Automation Builder"
        description="Chain triggers, conditions and channel actions into a flow that works leads without a rep touching them." />
      

      <PlanGate
        allowed={can(user.workspace.plan, 'automationBuilder')}
        title="Automation Builder is a Pro feature"
        description="Build multi-channel flows with conditions, delays and human handoff on Pro and above."
        onUpgrade={openUpgrade}>
        
        <div className="rounded-2xl border border-ink-800 bg-ink-900 p-6">
          <div className="flex items-center justify-between gap-3">
            <p className="font-display text-[16px] font-semibold tracking-tight text-chalk">
              Flow: Inbound → Qualified → Multi-channel
            </p>
            <span className="rounded-full border border-signal/50 px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider text-signal">
              Live
            </span>
          </div>

          <ol className="mt-7 space-y-3">
            {NODES.map((node, i) =>
            <li key={node.title}>
                <div className="flex items-center gap-4 rounded-xl border border-ink-800 bg-ink-950 p-4">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-ink-700 bg-ink-850 text-signal">
                    <node.icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[14.5px] font-medium text-chalk">{node.title}</span>
                    <span className="block font-mono text-[11.5px] text-chalk-faint">{node.meta}</span>
                  </span>
                </div>
                {i < NODES.length - 1 &&
              <div className="ml-[34px] h-5 w-px bg-ink-700" aria-hidden="true" />
              }
              </li>
            )}
          </ol>

          <p className="mt-7 flex items-center gap-2 border-t border-ink-850 pt-5 text-[13px] text-chalk-faint">
            Visual drag-and-drop editing
            <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="text-chalk-dim">(Coming soon)</span>
          </p>
        </div>
      </PlanGate>
    </div>);

}