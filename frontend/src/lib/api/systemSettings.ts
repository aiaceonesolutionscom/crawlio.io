import { apiFetch } from "../../lib/api/client";

export interface SystemSettings {
  site_name: string;
  primary_color: string;
  secondary_color: string;
  hero_video_url: string;
  cta_text: string;
  feedback_text: string;
  website_name: string;
  header_text: string;
  footer_text: string;
  hero_background: string;
}

export function useSystemSettings(): SystemSettings {
  const { data, isLoading } = apiFetch<SystemSettings>('/api/v1/admin/system-settings', null);
  return data || {
    site_name: 'Crawlio',
    primary_color: '#CBFF4D',
    secondary_color: '#A9DE22',
    hero_video_url: '',
    cta_text: 'Get Started',
    feedback_text: 'Trusted by revenue teams worldwide',
    website_name: 'Crawlio',
    header_text: 'Lead generation CRM',
    footer_text: 'Free forever on 700 leads a month. No card, no call.',
    hero_background: '',
  };
}