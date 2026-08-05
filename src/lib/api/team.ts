import { apiFetch } from './client';

export type TeamRole = 'Owner' | 'Admin' | 'Member';
export type TeamEntryStatus = 'Active' | 'Invited';

export interface TeamEntryDTO {
  id: string;
  name: string | null;
  email: string | null;
  role: TeamRole;
  status: TeamEntryStatus;
  created_at: string;
}

export interface TeamListResponseDTO {
  items: TeamEntryDTO[];
  seats_used: number;
  seat_quota: number;
}

export function listTeam(token: string | null) {
  return apiFetch<TeamListResponseDTO>('/api/v1/team/members', token);
}

export function inviteMember(token: string | null, email: string, role: TeamRole = 'Member') {
  return apiFetch<TeamEntryDTO>('/api/v1/team/invites', token, {
    method: 'POST',
    body: JSON.stringify({ email, role })
  });
}

export function removeTeamEntry(token: string | null, entryId: string) {
  return apiFetch<undefined>(`/api/v1/team/members/${entryId}`, token, {
    method: 'DELETE'
  });
}
