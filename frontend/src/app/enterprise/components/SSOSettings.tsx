import React from 'react';
import { KeyRoundIcon } from 'lucide-react';

export function SSOSettings() {
  return (
    <div className="rounded-xl border border-ink-800 bg-ink-950 p-4">
      <KeyRoundIcon className="h-4 w-4 text-signal" aria-hidden="true" />
      <p className="mt-3 text-[14px] font-medium text-chalk">SSO / SAML</p>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-chalk-dim">
        Connect Okta, Entra ID or any SAML 2.0 provider. (Setup pending)
      </p>
    </div>);

}
