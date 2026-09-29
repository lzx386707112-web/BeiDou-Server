/**
 * @description 拍卖行中心脚本（主菜单）
 *
 * 布局：
 *   顶部 MAPLE 字母图标 → 个人信息栏 → 四个分区
 *   （日常功能 / 每日日常 / 角色提升 / 其他功能），每行四格。
 *
 * 顶部字母：用道具图标拼写，与 BeiDouSpecial/战力系统.js 写法一致。
 *   M=3994071  A=3994059  P=3994074  L=3994070  E=3994063
 *
 * 咖位：读名牌称号档位，称号表与阈值必须与客户端 BeiDouSetItemCompat.dll
 *   的 .titles 节严格一致，数据源（唯一真源）：
 *   tool/client-debug/BeiDouSetItemCompat/patch_nameplate_series.py
 *   改客户端称号表时，这里要同步改，否则菜单显示的称号会和名片对不上。
 *
 * 当前破功：角色伤害上限（DamageCapService，初始 19999999，上限 int 最大值）。
 */
var status = -1;
var i = 0;

// ============================================================
// 图标常量：全部取自本仓库脚本已实际使用过的 UI 路径，不要换成没验证过的路径。
// 注意：UIWindow.img/QuestIcon/3/0、4/0、6/0、7/0、8/0、9/0 这类是"文字条"
// （渲染成 经验值/获取Meso/金币 等宽图，一个就占 50px+），会把信息栏挤爆，
// 严禁当小图标用。小图标只用下面这些已核过尺寸的：
// ============================================================
var ICON_ARROW = "#fUI/CashShop.img/CSDiscount/arrow#";              // 分区标题两侧箭头 (9x9)
var ICON_NAME = "#fUI/UIWindow.img/Quest/icon8/0#";                  // 玩家名称 (15x12)
var ICON_POWER = "#fUI/CashShop.img/CSDiscount/arrow#";              // 角色战力 (9x9)
var ICON_CROWN = "#fUI/UIWindow.img/UserInfo/bossPetCrown#";         // 咖位 (18x12)
var ICON_COIN = "#fUI/Basic.img/BtCoin/normal/0#";                   // 游戏金币 (14x14)
var ICON_CASH = "#fUI/CashShop.img/CashItem/0#";                     // 游戏点券 (13x13)
var ICON_CAP = "#fUI/Basic.img/CheckBox/1#";                         // 当前破功 (12x12)
var ICON_POINT = "#fUI/GuildBBS.img/GuildBBS/Emoticon/Basic/2#";     // 副本积分 (18x18)

// 标题 MAPLE（字母道具图标）
var TITLE_MAPLE = "#i03994071# #i03994059# #i03994074# #i03994070# #i03994063#";

// ============================================================
// 称号（咖位）数据 —— 与 patch_nameplate_series.py 的 SERIES / THRESHOLDS 一一对应
// ============================================================
var 称号系列名 = ["玄幻", "斗罗", "龙珠", "火影", "海贼", "死神", "鬼灭", "咒术", "英雄学院"];

var 称号表 = [
    ["乾元玄阶", "坤极天域", "天元墟境", "玄枢天宿", "星墟玄阙",
     "太白星河", "苍元帝宿", "昊天玄宿", "九曜神王", "无敌大帝"],
    ["魂师", "大魂师", "魂尊", "魂王", "魂圣",
     "封号斗罗", "极限斗罗", "三级神祇", "神帝", "神帝"],
    ["赛亚人", "超级赛亚", "赛亚二阶", "赛亚三阶", "超赛神境",
     "超赛蓝境", "蓝级进化", "破坏神位", "自在极意", "自在极意"],
    ["学院生徒", "下忍", "中忍", "上忍", "影级强者",
     "仙人模式", "尾兽化身", "六道之力", "大筒木境", "大筒木境"],
    ["海贼新秀", "超新星", "七武海", "中将", "四皇候补",
     "四皇", "大将", "觉醒者", "海贼王", "海贼王"],
    ["席官", "副队长", "队长", "破面十刃", "归刃解放",
     "完现术者", "零番队级", "灵王断片", "灵王", "灵王"],
    ["鬼杀队员", "十人众级", "柱级", "下弦之鬼", "上弦之鬼",
     "上弦首座", "鬼舞辻无", "赫刀觉醒", "缘壹之境", "缘壹之境"],
    ["四级术师", "三级术师", "二级术师", "一级术师", "准特级位",
     "特别一级", "特级术师", "领域展开", "最强之境", "最强之境"],
    ["无个性者", "普通学生", "雄英生徒", "实习英雄", "职业英雄",
     "前十强者", "前五英雄", "第一英雄", "超觉醒者", "超觉醒者"]
];

var 称号阈值 = [10000, 100000, 1000000, 10000000,
    50000000, 200000000, 500000000, 2000000000];

// 伤害上限初始值（DamageCapService.INITIAL_CAP）
var 伤害上限初始值 = 19999999;

// 信息栏第二列的起始宽度（半角单位，1 个汉字=2、1 个字母数字=1），调大即整体右移。
// 27 是实测不折行的上限（咖位一行最长，右列称号 18 单位），再大会把称号挤到第二行
var 第二列宽度 = 27;

// 对话框内容宽度（半角单位，实测约 54），分区标题按它自动居中；标题偏了就微调这个
var 对话框宽度 = 54;

// 分区之间的空行数：太密会出现标题和上一行菜单叠在一起
var 分区间空行 = 1;

// 菜单每格的定宽（半角单位）："[四字名]"=10，留 3 格间隔；航海/拍卖行等短名自动补齐
var 菜单格宽 = 13;

// ============================================================
// 入口流程
// ============================================================
function start() {
    // 显式重置：脚本引擎实例可能被复用，不能依赖 var status 的初值
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else if (mode === -1) {
        status--;
    } else {
        cm.dispose();
        return;
    }
    if (status === 0) {
        cm.sendSimple(构建主菜单());
    } else if (status === 1) {
        doSelect(selection);
    } else {
        cm.dispose();
    }
}

// ============================================================
// 界面构建
// ============================================================
function 构建主菜单() {
    var 文本 = "\r\n\r\n\t\t\t\t" + TITLE_MAPLE + "\r\n\r\n";
    文本 += 构建信息栏();
    文本 += "\r\n";

    // ---- 日常功能 ----
    文本 += 空行() + 分区标题("日常功能") + "\r\n";
    文本 += 菜单行([[0, "自由市场"], [1, "传送系统"], [2, "快捷商店"], [3, "一键出售"]]);
    文本 += 菜单行([[4, "随身仓库"], [5, "各种兑换"], [6, "任务大厅"], [7, "新人福利"]]);

    // ---- 每日日常 ----
    文本 += 空行() + 分区标题("每日日常") + "\r\n";
    文本 += 菜单行([[8, "每日签到"], [9, "在线奖励"], [10, "怪物公园"], [11, "航海"]]);
    文本 += 菜单行([[25, "跑环"], [26, "狩猎"], [30, "起源之塔"]]);

    // ---- 角色提升 ----
    文本 += 空行() + 分区标题("角色提升") + "\r\n";
    文本 += 菜单行([[12, "装备中心"], [13, "战力系统"], [14, "究极进化"], [15, "技能中心"]]);
    文本 += 菜单行([[27, "血衣合成"], [28, "怪物卡戒"], [29, "Boss成长"]]);

    // ---- 其他功能 ----
    文本 += 空行() + 分区标题("其他功能") + "\r\n";
    文本 += 菜单行([[16, "额外仓库"], [17, "删除道具"], [18, "掉落查询"], [19, "卷轴分解"]]);
    文本 += 菜单行([[20, "各种兑换"], [21, "抽奖保底"], [22, "拍卖行"], [23, "共同富裕"]]);
    文本 += 菜单行([[24, "投资理财"]]);

    // ---- GM 区（保持原有外观，标题同样居中）----
    if (cm.getPlayer().isGM()) {
        var gm标题 = "#r=====以下内容仅GM可见=====";
        文本 += "\r\n" + " ".repeat(Math.max(1, Math.floor((对话框宽度 - 取显示宽(纯文本(gm标题))) / 2))) + gm标题 + "\r\n";
        文本 += "#L100#巡逻#l\t\r\n\r\n";
        文本 += "#L107#设置血蓝#l\t\r\n\r\n";
        文本 += "#L101#UI查询#l\t#L102#GM商店集合#l\r\n";
        文本 += "#L103#一键删除道具#l\t#L104#一键刷道具#l\r\n";
        文本 += "#L105#有状态脚本示例#l\t #L106#NextLevel脚本示例#l";
        文本 += "#L108#加1000积分#l\t\r\n\r\n";
    }
    return 文本;
}

function 空行() {
    return "\r\n".repeat(分区间空行);
}

function 构建信息栏() {
    var p = cm.getPlayer();
    var 战力 = 取战力(p);
    var 咖位 = 取称号(战力);
    var 金币 = cm.getMeso();
    var 点券 = p.getCashShop().getCash(1);
    var 破功 = 取伤害上限(p);
    var 积分 = cm.getPqPoints();

    var 文本 = "";
    文本 += ICON_NAME + " #d玩家名称#k：#r" + p.getName() + "#k #d(ID:" + p.getId() + ")#k\r\n";

    文本 += 双列(
        ICON_POWER + " #d角色战力#k：#r" + 格式化数值(战力) + "#k",
        ICON_CROWN + " #d咖位#k：#r" + 咖位 + "#k"
    );

    文本 += 双列(
        ICON_COIN + " #d游戏金币#k：#r" + 格式化数值(金币) + "#k",
        ICON_CASH + " #d游戏点券#k：#r" + 格式化数值(点券) + "#k"
    );

    文本 += 双列(
        ICON_CAP + " #d当前破功#k：#r" + 格式化数值(破功) + "#k",
        ICON_POINT + " #d副本积分#k：#r" + 格式化数值(积分) + "#k"
    );

    return 文本;
}

// 两列信息行：把左列补到固定宽度后再接右列
function 双列(左, 右) {
    return 补位到(左, 第二列宽度) + 右 + "\r\n";
}

// 分区标题：按对话框宽度自动居中（对齐靠空格，制表符宽度不可控）
function 分区标题(名称) {
    var 内容 = "#d---------#k " + ICON_ARROW + " #e#r【" + 名称 + "】#k#n " + ICON_ARROW + " #d---------#k";
    var 缩进 = Math.floor((对话框宽度 - 取显示宽(纯文本(内容))) / 2);
    return " ".repeat(缩进 > 0 ? 缩进 : 1) + 内容;
}

// 一行菜单：半角 [] 括号 + 空格定宽对齐（全角【】+制表符实测会撑爆换行，不要改回去）
function 菜单行(条目列表) {
    var 行 = "";
    for (var n = 0; n < 条目列表.length; n++) {
        行 += "#L" + 条目列表[n][0] + "##b[" + 条目列表[n][1] + "]#k#l";
        if (n < 条目列表.length - 1) {
            var 补 = 菜单格宽 - 取显示宽("[" + 条目列表[n][1] + "]");
            行 += " ".repeat(补 > 0 ? 补 : 1);
        }
    }
    return 行 + "\r\n";
}

// ============================================================
// 数据取值
// ============================================================

// 角色战力：与 PacketCreator.calculateNameplatePower 完全一致
//   战力 = (STR+DEX+INT+LUK) * max(1, max(物攻, 魔攻)) + MaxHP/10 + MaxMP/20
function 取战力(p) {
    try {
        var 属性 = p.getTotalStr() + p.getTotalDex() + p.getTotalInt() + p.getTotalLuk();
        var 攻击 = Math.max(1, Math.max(p.getTotalWatk(), p.getTotalMagic()));
        var 血蓝 = Math.floor(p.getMaxHp() / 10) + Math.floor(p.getMaxMp() / 20);
        return Math.max(0, 属性 * 攻击 + 血蓝);
    } catch (e) {
        return 0;
    }
}

// 当前破功 = 伤害上限，取不到时按初始值算
function 取伤害上限(p) {
    try {
        var 上限 = p.getDamageCap();
        return (上限 === null || 上限 === undefined || 上限 < 伤害上限初始值) ? 伤害上限初始值 : 上限;
    } catch (e) {
        return 伤害上限初始值;
    }
}

// 咖位：按战力取当前系列的称号（系列由玩家自选，档位由战力决定）
function 取称号(战力) {
    var 系列 = cm.getNameplateSeries();
    if (系列 < 0 || 系列 >= 称号系列名.length) {
        系列 = 0;
    }
    var 表 = 称号表[系列];
    return "【" + 称号系列名[系列] + "】" + 表[取档位(战力)];
}

// 档位阶梯，逻辑与 patch_nameplate_series.py / 契约测试 tier_for() 一致：
// 战力 >= 阈值[i] 就升一档，8 个阈值封顶；超过 32 位后按高位单独判定。
function 取档位(战力) {
    var 低位 = 战力 % 4294967296;
    var 高位 = Math.floor(战力 / 4294967296) % 16777216;
    if (高位 !== 0) {
        if (高位 !== 2) {
            return 高位 > 2 ? 9 : 8;
        }
        return 低位 >= 0x540BE400 ? 9 : 8;
    }
    var 档 = 0;
    while (档 < 8 && 低位 >= 称号阈值[档]) {
        档++;
    }
    return 档;
}

// ============================================================
// 文本排版工具
// ============================================================

// 去掉 maple 控制符，只留肉眼可见的文字（图标统一折算成 2 个单位）
function 纯文本(文本) {
    return String(文本)
        .replace(/#[fit][^#]*#/g, "--")
        .replace(/#L\d+#/g, "")
        .replace(/#[a-zA-Z]/g, "");
}

// 半角宽度：中日韩全角字符按 2 计，其余按 1 计
function 取显示宽(文本) {
    var 宽 = 0;
    for (var n = 0; n < 文本.length; n++) {
        宽 += 文本.charCodeAt(n) > 0x2E80 ? 2 : 1;
    }
    return 宽;
}

// 用半角空格把内容补到目标宽度（制表符会跳到固定制表位、宽度不可控，不要用）
function 补位到(文本, 目标宽) {
    var 差 = 目标宽 - 取显示宽(纯文本(文本));
    return 文本 + " ".repeat(差 > 0 ? 差 : 1);
}

// 数值：过万显示"万"，过亿显示"亿"，末尾多余的 0 去掉
function 格式化数值(值) {
    var 数 = Number(值);
    if (!isFinite(数)) {
        return "0";
    }
    var 负 = 数 < 0;
    数 = Math.abs(数);
    var 结果;
    if (数 >= 100000000) {
        结果 = 去尾零((数 / 100000000).toFixed(2)) + "亿";
    } else if (数 >= 10000) {
        结果 = 去尾零((数 / 10000).toFixed(1)) + "万";
    } else {
        结果 = String(数);
    }
    return (负 ? "-" : "") + 结果;
}

function 去尾零(文本) {
    if (文本.indexOf(".") < 0) {
        return 文本;
    }
    return 文本.replace(/0+$/, "").replace(/\.$/, "");
}

// ============================================================
// 选择处理
// ============================================================
function doSelect(selection) {
    switch (selection) {
        // ---------- 日常功能 ----------
        case 0:// 自由市场
            cm.getPlayer().saveLocationOnWarp();
            cm.warp(910000000);
            cm.dispose();
            break;
        case 1:// 传送系统
            openNpc("万能传送");
            break;
        case 2:// 快捷商店
            cm.openShopNPC(9201099); // 便利商店
            cm.dispose();
            break;
        case 3:// 一键出售
            openNpc("一键出售");
            break;
        case 4:// 随身仓库
            openNpc("随身仓库");
            break;
        case 5:// 各种兑换
            openNpc("各种兑换");
            break;
        case 6:// 任务大厅
            openNpc("任务大厅");
            break;
        case 7:// 新人福利
            openNpc("新人福利");
            break;

        // ---------- 每日日常 ----------
        case 8:// 每日签到
            openNpc("每日签到");
            break;
        case 9:// 在线奖励
            openNpc("在线奖励");
            break;
        case 10:// 怪物公园（大厅地图，与万能传送一致）
            cm.warp(951000000);
            cm.dispose();
            break;
        case 11:// 航海（凯梅尔兹交易所，与万能传送一致）
            cm.warp(865000001);
            cm.dispose();
            break;
        case 25:// 跑环（原在任务大厅）
            openNpc("任务/跑环");
            break;
        case 26:// 狩猎（原在任务大厅）
            openNpc("任务/狩猎");
            break;
        case 30:// 起源之塔
            cm.warp(992000000);
            cm.dispose();
            break;

        // ---------- 角色提升 ----------
        case 12:// 装备中心
            openNpc("装备中心");
            break;
        case 13:// 战力系统
            openNpc("战力系统");
            break;
        case 14:// 究极进化（涅槃脚本）
            openNpc("一键转生");
            break;
        case 15:// 技能中心
            openNpc("技能中心");
            break;
        case 27:// 血衣合成（原在任务大厅，明珠港怪物卡戒指NPC）
            openNpc("任务/血衣合成");
            break;
        case 28:// 怪物卡戒（NPC 2006）
            openNpc("2006");
            break;
        case 29:// Boss成长（原在任务大厅）
            openNpc("Boss成长系统");
            break;

        // ---------- 其他功能 ----------
        case 16:// 额外仓库
            openNpc("物品仓库系统");
            break;
        case 17:// 删除道具
            openNpc("删除道具");
            break;
        case 18:// 掉落查询
            openNpc("查询掉落");
            break;
        case 19:// 卷轴分解
            openNpc("卷轴碎片");
            break;
        case 20:// 各种兑换
            openNpc("各种兑换");
            break;
        case 21:// 抽奖保底
            openNpc("抽奖保底");
            break;
        case 22:// 拍卖行
            拍卖系统();
            break;
        case 23:// 共同富裕
            openNpc("共同富裕");
            break;
        case 24:// 投资理财
            openNpc("金融/冒险炒股");
            break;

        // ---------- GM ----------
        case 100:// 巡逻
            openNpc("巡逻");
            break;
        case 101:
            openNpc("UI查询");
            break;
        case 102:
            openNpc("GM商店");
            break;
        case 103:
            openNpc("一键删除道具");
            break;
        case 104:
            openNpc("一键刷道具");
            break;
        case 105:
            openNpc("Example1");
            break;
        case 106:
            openNpc("Example2");
            break;
        case 107:
            openNpc("设置血蓝");
            break;
        case 108:
            cm.addPqPoints(1000);
            cm.sendOk("添加成功");
            cm.dispose();
            break;
        default:
            cm.sendOk("该功能暂不支持，敬请期待！");
            cm.dispose();
    }
}

function openNpc(scriptName) {
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}

function 拍卖系统() {
    if (cm.getLevel() < 50) {
        cm.sendOk("该功能50级以后开放");
        cm.dispose();
        return;
    }
    const EnterMTSHandler = Java.type(
        "org.gms.net.server.channel.handlers.EnterMTSHandler"
    );
    const client = cm.getPlayer().getClient();
    EnterMTSHandler.enterMTS(client);
}

// 核心：通过Java.type导入所需的Java类（需替换为实际包路径）
// 注意：请将包名替换为你项目中这些类的真实全限定名
const SkillFactory = Java.type("org.gms.client.SkillFactory");

/**
 * 核心方法：与原Java逻辑完全一致，适配JS语法+Java类调用
 * 前提：当前JS上下文已绑定getPlayer()方法（或可直接访问player对象）
 */
function maxMastery() {
    // 2. 遍历Java集合（JS中适配Java的Iterator）
    const iterator = cm.getTest().iterator();
    while (iterator.hasNext()) {
        const skill_ = iterator.next();

        // 转换技能ID（JS中调用Java的Integer.parseInt）
        const skillId = Java.type("java.lang.Integer").parseInt(skill_.getName());
        // 获取Java的Skill对象
        const skill = SkillFactory.getSkill(skillId);
        if (skill != null) {
            if (skillId === 14100005) {
                console.error("主菜单脚本错误===》:" + skillId);
                cm.getPlayer().changeSkillLevel(skill, 1, 1, -1);
            }
        }
    }
    cm.sendOk("11111！");
    cm.dispose();

}

function maxMastery9() {
    // 2. 遍历Java集合（JS中适配Java的Iterator）a
    const iterator = cm.getTest().iterator();
    while (iterator.hasNext()) {
        const skill_ = iterator.next();

        // 转换技能ID（JS中调用Java的Integer.parseInt）
        const skillId = Java.type("java.lang.Integer").parseInt(skill_.getName());
        // 获取Java的Skill对象
        const skill = SkillFactory.getSkill(skillId);
        if (skill != null) {
            console.error("主菜单脚本错误===》:" + skillId);
            cm.getPlayer().changeSkillLevel(skill, skill.getMaxLevel(), skill.getMaxLevel(), -1);
        }
    }
    cm.sendOk("11111！");
    cm.dispose();

}


// 导入所需的Java类
const ItemInformationProvider = Java.type('org.gms.server.ItemInformationProvider');
const I18nUtil = Java.type('org.gms.util.I18nUtil');
const Server = Java.type('org.gms.net.server.Server');
const PacketCreator = Java.type('org.gms.util.PacketCreator');

function makeItemWordNotice(player, itemId) {
    // 获取物品名称
    const itemName = ItemInformationProvider.getInstance().getName(itemId);
    // 获取国际化消息（参数依次为玩家名称、物品名称、物品ID）
    const msg = I18nUtil.getMessage("Player.make.things.tip", player.getName(), itemName, itemId);
    // 广播服务器通知（世界、频道、消息）
    Server.getInstance().broadcastMessage(
        player.getWorld(),
        PacketCreator.serverNotice(2, player.getClient().getChannel(), msg)
    );
}
