import axios from 'axios';

export function getServerStatus() {
  return axios.get<boolean>('/server/v1/online');
}

export function startServer() {
  return axios.get('/server/v1/startServer');
}

interface StopServerParams {
  minutes: number;
  shutdownMsg: string;
  showServerMsg: boolean;
  showCenterMsg: boolean;
  showChatMsg: boolean;
}

interface BroadcastParams {
  message: string;
}

interface MonsterSiegeParams {
  monsterIds: number[];
  count: number;
  message: string;
  broadcast: boolean;
}

export function stopServer(params: StopServerParams) {
  return axios.post('/server/v1/stopServerWithMsgAndInternal', params);
}

export function restartServer() {
  return axios.get('/server/v1/restartServer');
}

export function shutdown() {
  return axios.get('/server/v1/shutdown');
}

export function getVersion() {
  return axios.get('/server/v1/version');
}

export function sendServerBroadcast(params: BroadcastParams) {
  return axios.post('/server/v1/broadcast', params);
}

export function startMonsterSiege(params: MonsterSiegeParams) {
  return axios.post<number>('/server/v1/monsterSiege', params);
}
