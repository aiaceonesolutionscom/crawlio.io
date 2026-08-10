import { apiFetch } from '../client';

export interface AuditLogDTO {
  id: string;
  actor_email: string;
  action: string;
  target_type: string;
  target_id: string | null;
  workspace_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogFilters {
  actorEmail?: string;
  action?: string;
  targetType?: string;
  workspaceId?: string;
  limit?: number;
  offset?: number;
}

export function listAuditLog(token: string | null, filters: AuditLogFilters = {}) {
  const params = new URLSearchParams();
  if (filters.actorEmail) params.set('actor_email', filters.actorEmail);
  if (filters.action) params.set('action', filters.action);
  if (filters.targetType) params.set('target_type', filters.targetType);
  if (filters.workspaceId) params.set('workspace_id', filters.workspaceId);
  if (filters.limit) params.set('limit', String(filters.limit));
  if (filters.offset) params.set('offset', String(filters.offset));
  const qs = params.toString();
  return apiFetch<AuditLogDTO[]>(`/api/v1/admin/audit-log${qs ? `?${qs}` : ''}`, token);
}
