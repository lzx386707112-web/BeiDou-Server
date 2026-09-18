/*
	This file is part of the OdinMS Maple Story Server
    Copyright (C) 2008 Patrick Huy <patrick.huy@frz.cc>
		       Matthias Butz <matze@odinms.de>
		       Jan Christian Meyer <vimes@odinms.de>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation version 3 as published by
    the Free Software Foundation. You may not use, modify or distribute
    this program under any other version of the GNU Affero General Public
    License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
package org.gms.provider;

import org.gms.provider.wz.OverlayXMLWZFile;
import org.gms.provider.wz.WZFiles;
import org.gms.provider.wz.XMLWZFile;

import java.nio.file.Files;
import java.nio.file.Path;

public class DataProviderFactory {
    public static DataProvider getDataProvider(WZFiles in) {
        return getDataProvider(in, in.getLanguageFile());
    }

    /**
     * 按指定语言构建数据提供者，不需要 ServerManager 的 ApplicationContext，
     * 避免在 Spring 启动早期（ApplicationContext 尚未注入静态字段时）触发 NPE。
     */
    public static DataProvider getDataProvider(WZFiles in, String language) {
        return getDataProvider(in, in.getLanguageFile(language));
    }

    private static DataProvider getDataProvider(WZFiles in, Path language) {
        Path base = in.getBaseFile();
        if (Files.exists(language) && Files.exists(base) && !language.equals(base)) {
            return new OverlayXMLWZFile(base, language);
        }
        Path chosen = Files.exists(language) ? language : base;
        return new XMLWZFile(chosen);
    }
}