const API_URL = import.meta.env.VITE_API_URL;

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data: any = null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export async function apiFetch<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {})
    }
  });

  if (!res.ok) {
    let data: any = null;
    try { data = await res.json(); } catch { /* body is not JSON */ }
    const message = (data && (data.error || data.detail || data.message)) || res.statusText;
    throw new ApiError(res.status, message, data);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
