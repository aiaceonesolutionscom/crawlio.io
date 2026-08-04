export const FEATURES = [
{
  id: 'qualification',
  icon: 'brain',
  name: 'AI Qualification',
  description:
  'Every inbound and scraped lead is enriched, scored and ranked against your closed-won patterns — before a rep ever opens it.',
  detail: 'Scores refresh continuously as new signals arrive.'
},
{
  id: 'email',
  icon: 'mail',
  name: 'Email Outreach',
  description:
  'Multi-step sequences that write themselves from the lead context, with deliverability guardrails and reply detection built in.',
  detail: 'Warm-up, throttling and inbox rotation handled for you.'
},
{
  id: 'whatsapp',
  icon: 'message',
  name: 'WhatsApp Automation',
  description:
  'Reach buyers where they actually reply. Template approvals, opt-outs and handoff to a human are all part of the flow.',
  detail: 'Official Business API, no grey-market gateways.'
}] as
const;

export const PIPELINE_STEPS = [
{ step: '01', label: 'Capture', copy: 'Forms, ads, scrapes and CRM syncs land in one queue.' },
{ step: '02', label: 'Qualify', copy: 'AI enriches and scores against your ideal customer profile.' },
{ step: '03', label: 'Automate', copy: 'Sequences fire across email and WhatsApp on the right cadence.' },
{ step: '04', label: 'Close', copy: 'Hot replies route to a rep with full context attached.' }];


export const LOGOS = [
'Northwind',
'Vector Health',
'Loop Retail',
'Cascade Solar',
'Harbor & Co',
'Meridian',
'Kestrel',
'Fjord'];


export const TESTIMONIALS = [
{
  quote:
  'We cut our qualification time from three days to about forty minutes. The scoring is genuinely better than what our SDRs were doing by hand.',
  name: 'Amara Okafor',
  role: 'VP Revenue, Northwind Logistics'
},
{
  quote:
  'The WhatsApp sequences changed our numbers in LATAM. Reply rate went from 4% on email alone to 22% blended.',
  name: 'Sofia Almeida',
  role: 'Growth Lead, Brightline Studios'
},
{
  quote:
  'I started on the free plan to test one campaign and upgraded within two weeks. Onboarding took ten minutes, not a quarter.',
  name: 'Owen Marsh',
  role: 'Founder, Kestrel Manufacturing'
}];


export const FAQS = [
{
  q: 'What counts as a lead?',
  a: 'Any unique contact record processed by Crawlio in a billing month — captured, enriched or scored. Re-processing the same contact never double-counts.'
},
{
  q: 'Do I need a credit card to start?',
  a: 'No. The Free plan is available forever with a 500 lead per month cap and one seat. You only add billing when you upgrade.'
},
{
  q: 'Is my workspace isolated from other customers?',
  a: 'Yes. Each account is provisioned as its own tenant workspace with scoped data access, role-based permissions and per-plan quotas enforced server-side.'
},
{
  q: 'Can I bring my own AI models?',
  a: 'On Enterprise, yes — scoring can run against your own fine-tuned model and your own historical outcome data.'
},
{
  q: 'How does upgrading work mid-cycle?',
  a: 'Quotas lift immediately and we prorate the remainder of the cycle. Downgrades take effect at the end of the current period.'
}];