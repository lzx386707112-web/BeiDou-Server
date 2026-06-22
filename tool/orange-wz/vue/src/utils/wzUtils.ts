export function isNormalValue(type: string | undefined) {
  return (
    type != 'WZ' &&
    type != 'WZ_DIRECTORY' &&
    type != 'IMAGE' &&
    type != 'IMAGE_LIST' &&
    type != 'IMAGE_NULL' &&
    type != 'IMAGE_VECTOR' &&
    type != 'IMAGE_CANVAS' &&
    type != 'IMAGE_SOUND'
  );
}

export function getMiniType(type: string) {
  switch (type) {
    case 'FOLDER':
      return '目录';
    case 'WZ':
      return 'wz 文件';
    case 'WZ_DIRECTORY':
      return '文件夹';
    case 'IMAGE':
      return 'img';
    case 'IMAGE_CANVAS':
      return '图片';
    case 'IMAGE_CONVEX':
      return 'convex';
    case 'IMAGE_DOUBLE':
      return '双精度';
    case 'IMAGE_FLOAT':
      return '浮点型';
    case 'IMAGE_INT':
      return '整数';
    case 'IMAGE_LIST':
      return '列表';
    case 'IMAGE_LONG':
      return '长整数';
    case 'IMAGE_NULL':
      return 'NULL';
    case 'IMAGE_SHORT':
      return '短整数';
    case 'IMAGE_SOUND':
      return 'mp3';
    case 'IMAGE_STRING':
      return '字符串';
    case 'IMAGE_UOL':
      return '链接';
    case 'IMAGE_VECTOR':
      return '向量';
  }
}
