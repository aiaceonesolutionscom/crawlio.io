import DOMPurify from 'dompurify';

// AI-generated/composed email bodies are rendered as HTML for preview, but
// that content is partly LLM output seeded from scraped lead/website data —
// untrusted input. Sanitize before it ever reaches dangerouslySetInnerHTML
// so a crafted lead name/website can't inject a script into the dashboard.
export function sanitizeEmailHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'p', 'br', 'b', 'strong', 'i', 'em', 'u', 'a', 'ul', 'ol', 'li',
      'blockquote', 'span', 'div', 'h1', 'h2', 'h3', 'hr'
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel']
  });
}
