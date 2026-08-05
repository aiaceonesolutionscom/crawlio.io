import { apiFetch } from './client';

export type SequenceStatus = 'draft' | 'active' | 'paused';

export interface SequenceStepDTO {
  id: string;
  step_order: number;
  delay_hours: number;
  subject: string;
  body: string;
}

export interface SequenceDTO {
  id: string;
  workspace_id: string;
  name: string;
  trigger: string;
  status: SequenceStatus;
  created_at: string;
  steps: SequenceStepDTO[];
}

export interface SequenceListResponseDTO {
  items: SequenceDTO[];
}

export function listSequences(token: string | null) {
  return apiFetch<SequenceListResponseDTO>('/api/v1/automation/sequences', token);
}

export interface CreateSequenceStepInput {
  subject: string;
  body: string;
  delay_hours?: number;
}

export interface CreateSequenceInput {
  name: string;
  trigger?: string;
  steps: CreateSequenceStepInput[];
}

export function createSequence(token: string | null, input: CreateSequenceInput) {
  return apiFetch<SequenceDTO>('/api/v1/automation/sequences', token, {
    method: 'POST',
    body: JSON.stringify(input)
  });
}

export function updateSequenceStatus(token: string | null, sequenceId: string, status: SequenceStatus) {
  return apiFetch<SequenceDTO>(`/api/v1/automation/sequences/${sequenceId}/status`, token, {
    method: 'PATCH',
    body: JSON.stringify({ status })
  });
}

export function deleteSequence(token: string | null, sequenceId: string) {
  return apiFetch<undefined>(`/api/v1/automation/sequences/${sequenceId}`, token, {
    method: 'DELETE'
  });
}
