import React from 'react';
import { ArrowRightIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ButtonLink } from '../../shared/ui/Button';
import { Logo } from '../../shared/ui/Logo';
import { useSystemSettings } from '../../lib/api/systemSettings';

const COLUMNS = [
  {
    title: 'Product',
    links: [
      { label: 'AI Qualification', to: '/product/ai-qualification' },
      { label: 'Email Outreach', to: '/product/email-outreach' },
      { label: 'WhatsApp Automation', to: '/product/whatsapp-automation' },
      { label: 'Automation Builder', to: '/product/automation-builder' }
    ]
  },
  {
    title: 'Company',
    links: [
      { label: 'About', to: '/about' },
      { label: 'Careers', to: '/careers' },
      { label: 'Blog', to: '/blog' },
      { label: 'Contact sales', to: '/contact-sales' }
    ]
  },
  {
    title: 'Resources',
    links: [
      { label: 'Docs', to: '/docs' },
      { label: 'API reference', to: '/api-reference' },
      { label: 'Changelog', to: '/changelog' },
      { label: 'Status', to: '/status' }
    ]
  },
  {
    title: 'Legal',
    links: [
      { label: 'Privacy', to: '/privacy' },
      { label: 'Terms', to: '/terms' },
      { label: 'DPA', to: '/dpa' },
      { label: 'Security', to: '/security' }
    ]
  }
];

export function SiteFooter() {
  const { footer_text, website_name } = useSystemSettings();
  return (
    <footer className="bg-ink-950">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <div className="flex flex-col items-start justify-between gap-6 border-b border-ink-850 py-16 md:flex-row md:items-center">
          <div>
            <h2 className="font-display text-[28px] font-semibold tracking-tight text-chalk sm:text-[36px]">
              Put your pipeline on autopilot
            </h2>
            <p className="mt-3 text-[15px] text-chalk-dim">
              {footer_text}
            </p>
          </div>
          <ButtonLink to="/signup" size="lg">
            Get started
            <ArrowRightIcon className="h-4 w-4" />
          </ButtonLink>
        </div>

        <div className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-1">
            <Logo />
            <p className="mt-4 max-w-[220px] text-[13px] leading-relaxed text-chalk-faint">
              AI-powered lead automation for teams that would rather close than copy-paste.
            </p>
          </div>
          {COLUMNS.map((col) =>
            <nav key={col.title} aria-label={col.title}>
              <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-chalk-faint">{col.title}</h3>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((link) =>
                  <li key={link.label}>
                    <Link to={link.to} className="text-[14px] text-chalk-dim transition-colors hover:text-chalk">
                      {link.label}
                    </Link>
                  </li>
                )}
              </ul>
            </nav>
          )}
        </div>

        <div className="flex flex-col gap-2 border-t border-ink-850 py-7 text-[12.5px] text-chalk-faint sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} {website_name} — all rights reserved. Built by Aceone Solutions.</p>
          <p className="font-mono">Built for revenue teams, not for spreadsheets.</p>
        </div>
      </div>
    </footer>
  );
}