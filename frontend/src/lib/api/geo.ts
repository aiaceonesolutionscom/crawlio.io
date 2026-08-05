import { apiFetch } from './client';

export interface CountryDTO {
  code: string;
  name: string;
}

export interface CityDTO {
  name: string;
  lat: number;
  lon: number;
}

export function searchCountries(token: string | null, q?: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : '';
  return apiFetch<{ items: CountryDTO[] }>(`/api/v1/geo/countries${query}`, token);
}

export function searchCities(token: string | null, country: string, q: string) {
  const query = `?country=${encodeURIComponent(country)}&q=${encodeURIComponent(q)}`;
  return apiFetch<{ items: CityDTO[] }>(`/api/v1/geo/cities${query}`, token);
}
