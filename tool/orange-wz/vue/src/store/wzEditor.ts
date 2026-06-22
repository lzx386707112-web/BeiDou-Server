export interface IWorkplace {
  id: number;
  ref: object;
}

export interface IWzNode {
  id: number;
  name: string;
  type: WzStateType;
  leaf: boolean;
  file: boolean;
  children: IWzNode[];
}

export type WzStateType =
  | 'FOLDER'
  | 'WZ'
  | 'WZ_DIRECTORY'
  | 'IMAGE'
  | 'IMAGE_CANVAS'
  | 'IMAGE_CONVEX'
  | 'IMAGE_DOUBLE'
  | 'IMAGE_FLOAT'
  | 'IMAGE_INT'
  | 'IMAGE_LIST'
  | 'IMAGE_LONG'
  | 'IMAGE_NULL'
  | 'IMAGE_SHORT'
  | 'IMAGE_SOUND'
  | 'IMAGE_STRING'
  | 'IMAGE_UOL'
  | 'IMAGE_VECTOR';

export interface IWzNodeValue {
  id?: number;
  type?: WzStateType;
  name?: string;
  value?: string;
  x?: number;
  y?: number;
  png?: string;
  pngFormat?: string;
  mp3?: string;
}

export const getDefaultWzNodeValue = (): IWzNodeValue => ({
  id: undefined,
  type: undefined,
  name: undefined,
  value: undefined,
  x: undefined,
  y: undefined,
  png: undefined,
  pngFormat: undefined,
  mp3: undefined,
});

export const getFormatOptions = () => [
  { label: '50%压缩', value: 'Format1', disabled: false },
  { label: '原图', value: 'Format2', disabled: false },
  { label: '压缩', value: 'Format3', disabled: false },
  { label: '压缩', value: 'Format257', disabled: false },
  { label: '暂不支持', value: 'Format513', disabled: true },
  { label: '暂不支持', value: 'Format517', disabled: true },
  { label: '压缩', value: 'Format1026', disabled: false },
  { label: '压缩', value: 'Format2050', disabled: false },
];
