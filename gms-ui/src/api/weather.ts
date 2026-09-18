import axios from 'axios';

export const WEATHER_PROFILES = [
  'clear',
  'rain',
  'snow',
  'overcast',
  'storm',
  'blizzard',
  'leaves',
  'blossom',
  'sandstorm',
] as const;

export const DAY_PHASES = [
  { id: 'dawn', minute: 360 },
  { id: 'noon', minute: 720 },
  { id: 'dusk', minute: 1080 },
  { id: 'night', minute: 1320 },
] as const;

export interface WeatherState {
  enabled: boolean;
  minuteOfDay: number;
  nightLevel: number;
  phase?: string;
  weatherOverridden: boolean;
  overrideProfile?: string;
  timeFrozen: boolean;
  overrideRemainingSec: number;
  nextRollInSec: number;
  onlinePlayers: number;
  msPerGameMinute?: number;
}

export interface WeatherConfig {
  enabled: boolean;
  dayLengthMs: number;
  changeIntervalMs: number;
  overrideHoldMs: number;
  rainbowDurationSec: number;
  injectSky: boolean;
  seasonDrift: boolean;
}

export interface WeatherRegion {
  region: string;
  label?: string;
  mapHint?: string;
  currentProfile: string;
  forcedProfile?: string;
  weights: number[];
  nightTint: number;
  paletteId: number;
}

export interface WeatherOverride {
  profile?: string;
  minuteOfDay?: number;
  durationMinutes?: number;
}

export const getWeatherState = () =>
  axios.get<WeatherState>('/weather/v1/state');
export const getWeatherConfig = () =>
  axios.get<WeatherConfig>('/weather/v1/config');
export const updateWeatherConfig = (data: WeatherConfig) =>
  axios.put<number>('/weather/v1/config', data);
export const getWeatherRegions = () =>
  axios.get<WeatherRegion[]>('/weather/v1/regions');
export const updateWeatherRegion = (
  region: string,
  data: Omit<WeatherRegion, 'region' | 'currentProfile' | 'label' | 'mapHint'>
) => axios.put<number>(`/weather/v1/regions/${region}`, data);
export const setWeatherOverride = (data: WeatherOverride) =>
  axios.post<number>('/weather/v1/override', data);
export const clearWeatherOverride = () =>
  axios.delete<number>('/weather/v1/override');
export const broadcastWeather = () =>
  axios.post<number>('/weather/v1/broadcast');
export const rerollWeatherWind = () => axios.post<number>('/weather/v1/wind');
