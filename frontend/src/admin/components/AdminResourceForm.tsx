import React, { useState } from 'react';
import { cn } from '../../shared/utils/cn';

export type AdminFieldType = 'text' | 'number' | 'boolean' | 'select' | 'textarea' | 'json';

export interface AdminField {
  key: string;
  label: string;
  type: AdminFieldType;
  options?: { label: string; value: string }[];
  helpText?: string;
}

interface Props {
  fields: AdminField[];
  initialValues: Record<string, unknown>;
  onSubmit: (values: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}

const inputClass =
  'w-full rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-[13.5px] text-chalk outline-none focus:border-signal/60';

/** Generic add/edit form driven by field config — a `json` field type (textarea
 * + JSON.parse validation) covers list/object values like plan capabilities
 * without building a bespoke array/object editor per resource. */
export function AdminResourceForm({ fields, initialValues, onSubmit, onCancel, submitLabel = 'Save' }: Props) {
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const initial: Record<string, unknown> = { ...initialValues };
    for (const field of fields) {
      if (field.type === 'json' && initial[field.key] !== undefined) {
        initial[field.key] = JSON.stringify(initial[field.key], null, 2);
      }
    }
    return initial;
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const setValue = (key: string, value: unknown) => setValues((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const payload: Record<string, unknown> = { ...values };
    for (const field of fields) {
      if (field.type === 'json' && typeof payload[field.key] === 'string') {
        try {
          payload[field.key] = JSON.parse(payload[field.key] as string);
        } catch {
          setError(`"${field.label}" must be valid JSON`);
          return;
        }
      }
      if (field.type === 'number' && payload[field.key] !== '') {
        payload[field.key] = Number(payload[field.key]);
      }
    }
    setIsSubmitting(true);
    try {
      await onSubmit(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {fields.map((field) => (
        <div key={field.key} className="space-y-1.5">
          <label className="block text-[12.5px] font-medium text-chalk-dim" htmlFor={field.key}>
            {field.label}
          </label>
          {field.type === 'boolean' ? (
            <label className="flex items-center gap-2 text-[13.5px] text-chalk">
              <input
                type="checkbox"
                id={field.key}
                checked={Boolean(values[field.key])}
                onChange={(e) => setValue(field.key, e.target.checked)}
              />
              Enabled
            </label>
          ) : field.type === 'select' ? (
            <select
              id={field.key}
              className={inputClass}
              value={String(values[field.key] ?? '')}
              onChange={(e) => setValue(field.key, e.target.value)}
            >
              {(field.options ?? []).map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : field.type === 'textarea' || field.type === 'json' ? (
            <textarea
              id={field.key}
              rows={field.type === 'json' ? 5 : 3}
              className={cn(inputClass, 'font-mono')}
              value={String(values[field.key] ?? '')}
              onChange={(e) => setValue(field.key, e.target.value)}
            />
          ) : (
            <input
              id={field.key}
              type={field.type === 'number' ? 'number' : 'text'}
              className={inputClass}
              value={values[field.key] === undefined || values[field.key] === null ? '' : String(values[field.key])}
              onChange={(e) => setValue(field.key, e.target.value)}
            />
          )}
          {field.helpText && <p className="text-[11.5px] text-chalk-faint">{field.helpText}</p>}
        </div>
      ))}

      {error && <p className="text-[13px] text-ember">{error}</p>}

      <div className="flex justify-end gap-3 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-ink-700 px-4 py-2 text-[13.5px] text-chalk-dim hover:text-chalk"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-signal px-4 py-2 text-[13.5px] font-medium text-ink-950 disabled:opacity-50"
        >
          {isSubmitting ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
