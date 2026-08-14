import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ArrowRightIcon, CheckIcon, Loader2Icon, SparklesIcon } from 'lucide-react';
import { cn } from '../../utils/cn';
import { ApiError } from '../../../lib/api/client';
import { createBusinessProfile, updateBusinessProfile, type BusinessProfileDTO } from '../../../lib/api/agent';

interface Props {
  initial?: BusinessProfileDTO | null;
  onComplete: (profile: BusinessProfileDTO) => void;
}

const FIELDS: { key: string; label: string; placeholder: string; type?: string; hint?: string }[] = [
  { key: 'business_name', label: 'Business Name', placeholder: 'AceOne', hint: 'The name the AI sends emails as.' },
  { key: 'owner_name', label: 'Your Name', placeholder: 'Nauman Alvi', hint: 'Signed at the end of every email.' },
  { key: 'business_phone', label: 'Business Phone Number', placeholder: '+92 300 1234567', type: 'tel' },
  { key: 'business_address', label: 'Business Address', placeholder: 'Karachi, Pakistan' },
  { key: 'services', label: 'What Services Do You Provide?', placeholder: 'AI automation, lead generation, email outreach and CRM automation.', hint: 'One line the AI can pitch in outreach.' },
  { key: 'website', label: 'Website (optional)', placeholder: 'https://aceone.com', type: 'url' },
];

export function BusinessOnboarding({ initial, onComplete }: Props) {
  const { getToken } = useAuth();
  const [form, setForm] = useState<Record<string, string>>({
    business_name: initial?.business_name || '',
    owner_name: initial?.owner_name || '',
    business_phone: initial?.business_phone || '',
    business_address: initial?.business_address || '',
    services: initial?.services || '',
    website: initial?.website || '',
  });
  const [knowledge, setKnowledge] = useState(initial?.knowledge_base || '');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const required = ['business_name', 'owner_name', 'services'];

  const setValue = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleSubmit = async () => {
    const nextErrors: Record<string, string> = {};
    for (const key of required) {
      if (!form[key]?.trim()) nextErrors[key] = 'Required';
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      const payload = {
        business_name: form.business_name,
        owner_name: form.owner_name,
        business_phone: form.business_phone || null,
        business_address: form.business_address || null,
        services: form.services,
        website: form.website || null,
        timezone: initial?.timezone || 'Asia/Karachi',
        knowledge_base: knowledge,
      };
      const profile = initial
        ? await updateBusinessProfile(token, payload)
        : await createBusinessProfile(token, payload);
      onComplete(profile);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save business profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="rounded-2xl border border-ink-800 bg-ink-900/90 p-6 shadow-xl">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-signal/40 bg-signal/10">
            <SparklesIcon className="h-5 w-5 text-signal" />
          </span>
          <div>
            <h2 className="font-display text-[18px] font-semibold tracking-tight text-chalk">
              {initial ? 'Edit Business Profile' : "Let's set up your AI Agent"}
            </h2>
            <p className="mt-1 text-[13px] leading-relaxed text-chalk-dim">
              The agent uses this business info to write outreach, reply to inbox emails and book meetings.
              You&apos;ll only do this once — it&apos;s saved to your workspace.
            </p>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2 text-[12px] text-ember">{error}</div>
        )}

        <div className="mt-5 space-y-3">
          {FIELDS.map((field) => (
            <div key={field.key}>
              <label className="mb-1 block text-[11px] font-medium text-chalk-dim">
                {field.label} {required.includes(field.key) && <span className="text-signal">*</span>}
              </label>
              {field.key === 'services' ? (
                <textarea
                  value={form[field.key] || ''}
                  onChange={(e) => setValue(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  rows={2}
                  className={cn(
                    'w-full rounded-lg border bg-ink-950 px-3 py-2 text-[13px] text-chalk placeholder:text-chalk-faint focus:outline-none',
                    errors[field.key] ? 'border-ember/60' : 'border-ink-700 focus:border-signal'
                  )}
                />
              ) : (
                <input
                  type={field.type || 'text'}
                  value={form[field.key] || ''}
                  onChange={(e) => setValue(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  className={cn(
                    'h-10 w-full rounded-lg border bg-ink-950 px-3 text-[13px] text-chalk placeholder:text-chalk-faint focus:outline-none',
                    errors[field.key] ? 'border-ember/60' : 'border-ink-700 focus:border-signal'
                  )}
                />
              )}
              {errors[field.key] ? (
                <p className="mt-1 text-[11px] text-ember">{errors[field.key]}</p>
              ) : field.hint ? (
                <p className="mt-1 text-[11px] text-chalk-faint">{field.hint}</p>
              ) : null}
            </div>
          ))}

          <div>
            <label className="mb-1 block text-[11px] font-medium text-chalk-dim">Business knowledge base (optional)</label>
            <textarea
              value={knowledge}
              onChange={(e) => setKnowledge(e.target.value)}
              placeholder="Add FAQs, pricing, policies, USP, objections handling — anything the agent should know. Leave empty to skip."
              rows={3}
              className="w-full rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-[13px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
            />
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={handleSubmit}
            disabled={
              saving ||
              !form.business_name?.trim() ||
              !form.owner_name?.trim() ||
              !form.services?.trim()
            }
            className="flex h-10 items-center gap-2 rounded-lg border border-signal/50 bg-signal/10 px-5 text-[12px] font-medium text-signal hover:bg-signal/20 disabled:opacity-40"
          >
            {saving ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <CheckIcon className="h-4 w-4" />}
            {saving ? 'Saving...' : 'Save & Start Agent'}
            {!saving && <ArrowRightIcon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}