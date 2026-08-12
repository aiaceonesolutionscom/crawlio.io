export interface SenderInfo {
  name: string;
  email: string;
}

const EMAIL_RE = /[^\s<>()[\]\\,;:"@]+@[^\s<>()[\]\\,;:"@]+/;

function parseEmailAddress(value: string): string {
  const match = value.match(EMAIL_RE);
  return match ? match[0] : '';
}

export function parseSender(input: unknown): SenderInfo | null {
  if (input == null) return null;

  let raw: unknown = input;

  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed && typeof parsed === 'object') raw = parsed;
      } catch {
        // Not JSON — fall through to string parsing below.
      }
    }
  }

  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    const nameVal = obj.name ?? obj.display_name ?? obj.displayName ?? obj.full_name ?? obj.sender_name ?? obj.senderName;
    const emailVal =
      obj.email ?? obj.address ?? obj.mail ?? obj.email_address ?? obj.emailAddress ?? obj.sender_email ?? obj.senderEmail;
    const name = typeof nameVal === 'string' ? nameVal.trim() : '';
    const email = typeof emailVal === 'string' ? emailVal.trim() : '';
    if (name || email) return { name, email };
  }

  if (typeof raw === 'string') {
    const s = raw.trim();
    if (!s) return null;

    // "Name <email@example.com>" or "Name<email>" or '"Name" <email>'
    const angleMatch = s.match(/^"?([^"<]*)"?\s*<\s*([^>]+)\s*>$/);
    if (angleMatch) {
      const name = angleMatch[1].trim().replace(/^["']+|["']+$/g, '');
      const email = angleMatch[2].trim();
      return { name, email };
    }

    const email = parseEmailAddress(s);
    if (email) {
      if (email === s) return { name: '', email };
      const name = s.replace(email, '').replace(/[<>"']/g, '').replace(/[,\s]+$/g, '').trim();
      return { name, email };
    }

    return { name: s, email: '' };
  }

  return null;
}

export function getSenderFromEmail(email: unknown): SenderInfo | null {
  if (!email || typeof email !== 'object') return null;
  const obj = email as Record<string, unknown>;

  for (const key of ['from', 'sender', 'from_email', 'from_address', 'sender_email', 'sender_name']) {
    const value = obj[key];
    if (value == null) continue;
    const parsed = parseSender(value);
    if (parsed && (parsed.name || parsed.email)) return parsed;
  }

  // Gmail API style payload.headers
  const payload = obj.payload as Record<string, unknown> | undefined;
  if (payload && Array.isArray(payload.headers)) {
    const fromHeader = (payload.headers as Array<{ name?: string; value?: string }>).find(
      (h) => h && typeof h.name === 'string' && h.name.toLowerCase() === 'from'
    );
    if (fromHeader && typeof fromHeader.value === 'string') {
      const parsed = parseSender(fromHeader.value);
      if (parsed && (parsed.name || parsed.email)) return parsed;
    }
  }

  return null;
}

export function formatSender(sender: SenderInfo | null): string {
  if (!sender) return '';
  const name = (sender.name || '').trim();
  const email = (sender.email || '').trim();
  if (!name && !email) return '';
  if (name && email) {
    return name.toLowerCase() === email.toLowerCase() ? email : `${name} <${email}>`;
  }
  return name || email;
}
