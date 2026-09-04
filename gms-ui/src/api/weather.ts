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

export interface WeatherState {
  enabled: boolean;
  minuteOfDay: number;
  nightLevel: number;
  weatherOverridden: boolean;
  overrideProfile?: string;
  timeFrozen: boolean;
  overrideRemainingSec: number;
  nextRollInSec: number;
  onlinePlayers: number;
}

export interface WeatherConfig {
  enabled: boolean;
  dayLengthMs: number;
  changeIntervalMs: number;
  overrideHoldMs: number;
  rainbowDurationSec: number;
}

export interface WeatherRegion {
  region: string;
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
  data: Omit<WeatherRegion, 'region' | 'currentProfile'>
) => axios.put<number>(`/weather/v1/regions/${region}`, data);
export const setWeatherOverride = (data: WeatherOverride) =>
  axios.post<number>('/weather/v1/override', data);
export const clearWeatherOverride = () =>
  axios.delete<number>('/weather/v1/override');
export const broadcastWeather = () =>
  axios.post<number>('/weather/v1/broadcast');
