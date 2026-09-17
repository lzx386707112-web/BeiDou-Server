import axios from 'axios';

export interface BotControlField {
  id: number;
  code: string;
  clazz: string;
  value: string;
  desc: string;
}

export interface BotControlState {
  activeBots: number;
  marketDirectorBots: number;
  marketEntranceBots: number;
  onlinePlayers: number;
  marketReady: boolean;
  marketStarting: boolean;
}

export interface BotControlConfig {
  market: BotControlField[];
  appearance: BotControlField[];
  environment: BotControlField[];
  party: BotControlField[];
}

export const getBotControlState = () =>
  axios.get<BotControlState>('/bot-control/v1/state');
export const getBotControlConfig = () =>
  axios.get<BotControlConfig>('/bot-control/v1/config');
export const updateBotControlConfig = (fields: BotControlField[]) =>
  axios.put<number>('/bot-control/v1/config', { fields });
export const startMarketBots = () =>
  axios.post<string>('/bot-control/v1/market/start');
