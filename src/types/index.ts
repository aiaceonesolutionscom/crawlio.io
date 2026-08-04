export type PlanId = 'free' | 'pro' | 'enterprise';

export interface PlanFeature {
  label: string;
  included: boolean;
}

export interface Plan {
  id: PlanId;
  name: string;
  price: string;
  priceNote: string;
  tagline: string;
  bestFor: string;
  leadQuota: string;
  seats: string;
  features: PlanFeature[];
  cta: string;
  highlighted?: boolean;
}

export interface Workspace {
  name: string;
  plan: PlanId;
  leadsUsed: number;
  leadQuota: number;
  seatsUsed: number;
  seatQuota: number;
  createdAt: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'Owner' | 'Admin' | 'Member';
  workspace: Workspace;
}

export type LeadStatus = 'New' | 'Qualified' | 'Contacted' | 'Nurturing' | 'Won' | 'Lost';

export interface Lead {
  id: string;
  name: string;
  company: string;
  email: string;
  phone: string;
  score: number;
  status: LeadStatus;
  source: string;
  updatedAt: string;
}

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: 'Owner' | 'Admin' | 'Member';
  status: 'Active' | 'Invited';
}