import type { WzKeyDto } from '@/api/wzKey.ts';

export class WzKeyHexConverter {
  /**
   * 将 WzKeyDto 转换为十六进制数组格式
   */
  static convertToHexArrays(wzKey: WzKeyDto): WzKeyHexDto {
    return {
      id: wzKey.id,
      name: wzKey.name,
      iv: this.processStringArray(wzKey.iv),
      userKey: this.processStringArray(wzKey.userKey),
    };
  }

  static convertToBase64(wzKey: WzKeyDto): WzKeyHexDto {
    return {
      id: wzKey.id,
      name: wzKey.name,
      iv: this.hexArrayToBase64(wzKey.iv),
      userKey: this.hexArrayToBase64(wzKey.userKey),
    };
  }

  /**
   * 处理字符串数组，自动检测格式并转换为十六进制数组
   */
  private static processStringArray(stringArray: string): [] {
    if (stringArray.includes('=') || stringArray.length % 4 === 0) {
      return this.base64ToHexArray(stringArray);
    } else {
      // 否则当作十六进制字符串处理
      return this.hexStringToHexArray(stringArray);
    }
  }

  /**
   * Base64 转十六进制数组
   */
  private static base64ToHexArray(base64: string): string[] {
    try {
      const binaryString = atob(base64);
      const hexArray: string[] = [];

      for (let i = 0; i < binaryString.length; i++) {
        const hex = binaryString.charCodeAt(i).toString(16).toUpperCase().padStart(2, '0');
        hexArray.push(hex);
      }

      return hexArray;
    } catch (error) {
      console.warn(`Base64 解码失败: ${base64}`, error);
      return [];
    }
  }

  /**
   * 十六进制字符串转十六进制数组
   */
  private static hexStringToHexArray(hexString: string): string[] {
    const result: string[] = [];
    const cleanHex = hexString.replace(/[^0-9A-Fa-f]/g, '').toUpperCase();

    for (let i = 0; i < cleanHex.length; i += 2) {
      const hex = cleanHex.substr(i, 2);
      if (hex.length === 2) {
        result.push(hex);
      }
    }

    return result;
  }

  /**
   * 十六进制数组转回 Base64（如果需要）
   */
  private static hexArrayToBase64(hexArray: string[]): string {
    const bytes = hexArray.map((hex) => parseInt(hex, 16));
    const binaryString = String.fromCharCode(...bytes);
    return btoa(binaryString);
  }
}
