import type { TeamMember } from '../types';

export const LEADS_OVER_TIME = [
{ week: 'W1', leads: 182, qualified: 61 },
{ week: 'W2', leads: 246, qualified: 88 },
{ week: 'W3', leads: 213, qualified: 79 },
{ week: 'W4', leads: 298, qualified: 124 },
{ week: 'W5', leads: 341, qualified: 152 },
{ week: 'W6', leads: 312, qualified: 141 },
{ week: 'W7', leads: 404, qualified: 189 },
{ week: 'W8', leads: 448, qualified: 217 }];


export const CHANNEL_PERFORMANCE = [
{ channel: 'Email', replies: 312 },
{ channel: 'WhatsApp', replies: 481 },
{ channel: 'Inbound', replies: 174 },
{ channel: 'Referral', replies: 96 }];


export const SOURCE_SPLIT = [
{ name: 'Inbound form', value: 38 },
{ name: 'Paid social', value: 27 },
{ name: 'Cold list', value: 21 },
{ name: 'Referral', value: 14 }];


export const TEAM: TeamMember[] = [
{ id: 'tm_1', name: 'You', email: 'you@crawlio.io', role: 'Owner', status: 'Active' },
{ id: 'tm_2', name: 'Ines Cardoso', email: 'ines@crawlio.io', role: 'Admin', status: 'Active' },
{ id: 'tm_3', name: 'Marcus Hale', email: 'marcus@crawlio.io', role: 'Member', status: 'Active' },
{ id: 'tm_4', name: 'Ruth Adeyemi', email: 'ruth@crawlio.io', role: 'Member', status: 'Invited' }];


export const ACTIVITY = [
{ id: 'a1', text: 'AI scored 128 new leads from Paid social', time: '4 min ago' },
{ id: 'a2', text: 'Sequence “Q3 Manufacturing” sent 46 emails', time: '32 min ago' },
{ id: 'a3', text: 'Priya Raman replied on WhatsApp — routed to Marcus', time: '1 hr ago' },
{ id: 'a4', text: 'Workspace quota check passed (214 / 500 leads)', time: '3 hr ago' }];