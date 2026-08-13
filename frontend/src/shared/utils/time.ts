export function khiTime(iso?: string | null, withDate = false): string {
  if (!iso) return '';
  const normalized = /Z|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z';
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return '';
  const time = d.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Karachi',
    hour: '2-digit',
    minute: '2-digit',
  });
  if (!withDate) return time;
  const date = d.toLocaleDateString('en-GB', {
    timeZone: 'Asia/Karachi',
    day: '2-digit',
    month: 'short',
    year: '2-digit',
  });
  return `${time}, ${date}`;
}