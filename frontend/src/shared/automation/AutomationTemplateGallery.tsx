import React from 'react';
import { Link } from 'react-router-dom';
import { FacebookIcon, InstagramIcon, MailIcon, MessageSquareIcon, RepeatIcon, SendIcon } from 'lucide-react';
import { cn } from '../utils/cn';

interface Template {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  available: boolean;
  to?: string;
}

interface Props {
  emailAgentPath: string;
  whatsappAgentPath: string;
}

export function AutomationTemplateGallery({ emailAgentPath, whatsappAgentPath }: Props) {
  const TEMPLATES: Template[] = [
    {
      icon: MailIcon,
      title: 'Email automation',
      description: 'Send a sequence of emails automatically as leads come in — build one below.',
      available: true,
      to: emailAgentPath
    },
    {
      icon: InstagramIcon,
      title: 'Instagram automation',
      description: 'Auto-DM new leads and reply to comments on Instagram.',
      available: false
    },
    {
      icon: FacebookIcon,
      title: 'Facebook automation',
      description: 'Auto-respond to Facebook Page messages and lead-form submissions.',
      available: false
    },
    {
      icon: SendIcon,
      title: 'Telegram automation',
      description: 'Send updates and follow-ups to leads over Telegram.',
      available: false
    },
    {
      icon: MessageSquareIcon,
      title: 'WhatsApp automation',
      description: 'Auto-respond and follow up with leads over WhatsApp.',
      available: true,
      to: whatsappAgentPath
    },
    {
      icon: RepeatIcon,
      title: 'Follow-ups automation',
      description: 'Auto-remind your team to follow up on leads that have gone quiet.',
      available: false
    }
  ];

  return (
    <div className="mb-6">
      <p className="mb-3 font-display text-[16px] font-semibold tracking-tight text-chalk">Automation templates</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TEMPLATES.map((t) => {
          const cardClassName = cn(
            'rounded-2xl border border-ink-800 bg-ink-900 p-5 text-left',
            !t.available && 'opacity-60',
            t.available && t.to && 'transition-colors hover:border-ink-700 hover:bg-ink-850/60'
          );
          const cardContent = (
            <>
              <div className="flex items-start justify-between gap-2">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-ink-700 bg-ink-850 text-signal">
                  <t.icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <span
                  className={cn(
                    'rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider',
                    t.available ? 'border-signal/50 text-signal' : 'border-ink-700 text-chalk-faint'
                  )}
                >
                  {t.available ? 'Available' : 'Coming soon'}
                </span>
              </div>
              <p className="mt-3 text-[14.5px] font-medium text-chalk">{t.title}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-chalk-dim">{t.description}</p>
            </>
          );

          if (t.available && t.to) {
            return (
              <Link key={t.title} to={t.to} className={cardClassName}>
                {cardContent}
              </Link>
            );
          }

          return (
            <div key={t.title} className={cardClassName}>
              {cardContent}
            </div>
          );
        })}
      </div>
    </div>
  );
}
