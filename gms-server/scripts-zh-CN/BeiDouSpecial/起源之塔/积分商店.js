/**
 * @description 起源之塔 · 积分商店
 *
 * 货币 = 「起源积分」，存在 extend_value 表（角色扩展值），键名见 起源积分键。
 * 该键名必须与 event/SeedTower20.js、抽奖.js 完全一致。
 *
 * 价格表（与 玩法说明.js 一致，改价要一起改）：
 *   1抽 40 / 5抽 160 / 10抽 360 / 20抽 760 / 50抽 1200
 *   法弗纳系列武器 统一 1299
 *
 * 法弗纳清单由 tool/scripts/migration/seed_tower_rewards.py 生成，
 * 数据源 gms-server/src/main/resources/equipment-catalog/catalog.json（后台装备预览）。
 *
 * 发放规则：背包放得下的进背包，放不下的部分掉在玩家脚下，由玩家自己拾取。
 * 积分按整笔扣除（买多少扣多少），掉落实现见下方「掉落兜底」标记块
 * （与 抽奖.js 共用同一份代码，两份必须逐字节相同）。
 *
 * 装备属性的读取与排版见「装备属性」标记块（与 奖池预览.js 共用，两份必须逐字节相同）。
 * 菜单里的图标一律放在 #L 链接【外面】——链接会生成可点击区域抢走鼠标，
 * 图标放里面就收不到悬停事件了，那样装备说明就弹不出来。
 */

var 起源积分键 = "起源积分";

// 抽奖卷：[道具ID, 抽取次数, 售价]
var 抽奖卷 = [
    [4009930, 1, 40],
    [4009931, 5, 160],
    [4009932, 10, 360],
    [4009933, 20, 760],
    [4009934, 50, 1200]
];

// BEGIN 法弗纳
var 法弗纳清单 = [1302275,1312153,1322203,1332225,1372177,1382208,1402196,1412135,1422140,1432167,1442223,1452205,1462193,1472214,1482168,1492179];
// END 法弗纳

var 法弗纳单价 = 1299;

// BEGIN 掉落兜底
// 发放口径：背包放得下的进背包，放不下的部分直接掉在玩家脚下，由玩家自己拾取。
// 掉落之后的命运（15 秒的归属保护、之后任何人都能捡、到期自然消失）全部走
// 服务端 MapItem 的既有逻辑，脚本不干预、也不额外统计。
//
// 两个必须守住的服务端契约：
//   1. 掉落件的构造口径要和 cm.gainItem() 一致，否则「地上的」和「包里的」品质不同。
//      gainItem 对装备走 getEquipById()，并给升级次数为 0 的饰品补 3 次；
//      是否 randomizeStats 取决于调用方传进来的 随机潜能（必须与进背包那条路相同）。
//   2. fieldLimit 带 DROP_LIMIT 的地图会静默吞掉掉落（内部降级成
//      disappearingItemDrop，连返回值都没有），所以落地前先自查一次。
var 掉落_装备栏编号 = 1;
var 掉落_道具类 = Java.type("org.gms.client.inventory.Item");
var 掉落_常量类 = Java.type("org.gms.constants.inventory.ItemConstants");
var 掉落_限制类 = Java.type("org.gms.server.maps.FieldLimit");

function 掉落_信息() {
    return Java.type("org.gms.server.ItemInformationProvider").getInstance();
}

// 造一件用于掉落的道具：装备恒为 1 件，其它按堆叠件。
function 掉落_造件(道具ID, 数量, 随机潜能) {
    if (Math.floor(道具ID / 1000000) === 掉落_装备栏编号) {
        var 件 = 掉落_信息().getEquipById(道具ID);
        if (件 === null || 件 === undefined) {
            return null;
        }
        try {
            if (掉落_常量类.isAccessory(道具ID) && 件.getUpgradeSlots() <= 0) {
                件.setUpgradeSlots(3);
            }
        } catch (e) { }
        if (随机潜能) {
            try {
                件 = 掉落_信息().randomizeStats(件);
            } catch (e) { }
        }
        return 件;
    }
    return new 掉落_道具类(道具ID, 0, 数量);
}

// 把 数量 个 道具ID 掉在玩家脚下；返回 true 表示确实掉出去了。
// ffa=false = 常规掉落：15 秒内归自己（同队队员可立即拾取），之后任何人都能捡。
function 掉落_地面(chr, 道具ID, 数量, 随机潜能) {
    try {
        var 地图 = chr.getMap();
        if (掉落_限制类.DROP_LIMIT.check(地图.getFieldLimit())) {
            return false;
        }
        var 件 = 掉落_造件(道具ID, 数量, 随机潜能);
        if (件 === null || 件 === undefined) {
            return false;
        }
        地图.spawnItemDrop(chr, chr, 件, chr.getPosition(), false, false);
        return true;
    } catch (e) {
        return false;
    }
}

// 发一个：放得下就进背包，放不下就掉地上。返回 '包' / '地' / ''（发不出去）。
// cm.canHold() 是只读预检（Inventory.checkSpots），所以可以逐件先问一次，
// 不会触发 gainItem 内部那句「您的背包已满…」（50 连抽会刷 50 条）。
function 掉落_发一个(chr, 道具ID, 随机潜能) {
    if (cm.canHold(道具ID, 1)) {
        var 结果 = cm.gainItem(道具ID, 1, 随机潜能, true);
        if (结果 !== null && 结果 !== undefined) {
            return '包';
        }
    }
    return 掉落_地面(chr, 道具ID, 1, 随机潜能) ? '地' : '';
}
// END 掉落兜底

// BEGIN 装备属性
// 装备属性的读取与排版。奖池预览与积分商店共用同一份实现
// （由 tool/scripts/migration/seed_tower_rewards.py 注入，契约测试核对两份逐字节相同）。
//
// ★ 键名注意：服务端 ItemInformationProvider.getEquipStats() 会把 info 里以 "inc"
// 开头的字段**去掉前缀**再放进 Map（见 ItemInformationProvider.java:575-577）：
//   incPAD -> PAD, incSTR -> STR, incPDD -> PDD, incSpeed -> Speed, incJump -> Jump ...
// 所以下面必须写去掉前缀后的名字；写 incPAD 会永远查不到值、属性整段空白且不报错。
// reqLevel/reqJob/reqSTR/reqDEX/reqINT/reqLUK/reqPOP/cash/tuc/only 是原样入表的。
var 装备_需求项 = [
    ["reqLevel", "等级要求"],
    ["reqSTR", "力量要求"],
    ["reqDEX", "敏捷要求"],
    ["reqINT", "智力要求"],
    ["reqLUK", "运气要求"],
    ["reqPOP", "人气要求"]
];
// 加成项的名字 = WZ 里的 incXXX 去掉 "inc"。这份清单是按奖池 1153 件
// （脸饰/耳环/项环/腰带）实际出现过的字段统计的，覆盖全部 20 个。
var 装备_加成项 = [
    ["PAD", "物理攻击力"],
    ["MAD", "魔法攻击力"],
    ["STR", "力量"],
    ["DEX", "敏捷"],
    ["INT", "智力"],
    ["LUK", "运气"],
    ["PDD", "物理防御力"],
    ["MDD", "魔法防御力"],
    ["ACC", "命中率"],
    ["EVA", "回避率"],
    ["MHP", "最大HP"],
    ["MMP", "最大MP"],
    ["MHPr", "最大HP%"],
    ["MMPr", "最大MP%"],
    ["Speed", "移动速度"],
    ["MSpeed", "移动速度%"],
    ["Jump", "跳跃力"],
    ["PVPDamage", "PVP伤害"],
    ["Craft", "制作技能"],
    ["CriticalMAXDamage", "暴击最大伤害"]
];

var 装备_部位名 = { "101": "脸饰", "103": "耳环", "112": "项环", "113": "腰带" };

function 装备_部位文本(道具ID) {
    var 段 = String(Math.floor(道具ID / 10000));
    return 装备_部位名[段] || ("道具 " + 段 + " 段");
}

// 读一件装备的全部 info 数值（键名已按上面的规则去过 inc 前缀）。
// 读失败时返回 {读取失败:true}，让调用方显式提示，而不是静默显示成"无附加属性"。
function 装备_取属性(道具ID) {
    var 结果 = {};
    try {
        var II = Java.type("org.gms.server.ItemInformationProvider").getInstance();
        var 映射 = II.getEquipStats(道具ID);
        if (映射 === null || 映射 === undefined) {
            return 结果;
        }
        var 迭代 = 映射.entrySet().iterator();
        while (迭代.hasNext()) {
            var 键值 = 迭代.next();
            var 值 = 键值.getValue();
            结果[String(键值.getKey())] = (值 === null || 值 === undefined) ? 0 : Number(值);
        }
    } catch (e) {
        结果.读取失败 = true;
    }
    return 结果;
}

function 装备_职业文本(掩码) {
    var 表 = [[1, "战士"], [2, "法师"], [4, "弓箭手"], [8, "飞侠"], [16, "海盗"]];
    var 名 = [];
    for (var i = 0; i < 表.length; i++) {
        if ((掩码 & 表[i][0]) !== 0) {
            名.push(表[i][1]);
        }
    }
    return 名.length > 0 ? 名.join("/") : "全职业";
}

// 需求行 [[标签, 值], ...]：职业位掩码排最前，其余按 装备_需求项 的顺序。
function 装备_需求行(属性) {
    var 行 = [];
    if (属性.reqJob && 属性.reqJob > 0) {
        行.push(["职业要求", 装备_职业文本(属性.reqJob)]);
    }
    for (var i = 0; i < 装备_需求项.length; i++) {
        var 值 = 属性[装备_需求项[i][0]];
        if (值 && 值 > 0) {
            行.push([装备_需求项[i][1], String(值)]);
        }
    }
    return 行;
}

// 加成行：已经是带好颜色标记的成品字符串，调用方直接逐行输出即可。
function 装备_加成行(属性) {
    var 行 = [];
    for (var i = 0; i < 装备_加成项.length; i++) {
        var 值 = 属性[装备_加成项[i][0]];
        if (值 && 值 !== 0) {
            行.push(装备_加成项[i][1] + " +#r" + 值 + "#k");
        }
    }
    if (属性.tuc && 属性.tuc > 0) {
        行.push("可升级次数 +#r" + 属性.tuc + "#k");
    }
    return 行;
}

// 半角宽度：中文按 2 格、ASCII 按 1 格。客户端点阵字体里全角正好是半角的两倍宽，
// 用这个单位补空格就能让两段文字左右对齐。对话框没有制表位，别用 	 去对齐。
function 文本_宽度(文本) {
    var 宽 = 0;
    for (var i = 0; i < 文本.length; i++) {
        宽 += (文本.charCodeAt(i) > 0x7F) ? 2 : 1;
    }
    return 宽;
}

function 文本_补右(文本, 目标宽) {
    var 缺 = 目标宽 - 文本_宽度(文本);
    return 缺 > 0 ? 文本 + new Array(缺 + 1).join(" ") : 文本;
}

function 文本_补左(文本, 目标宽) {
    var 缺 = 目标宽 - 文本_宽度(文本);
    return 缺 > 0 ? new Array(缺 + 1).join(" ") + 文本 : 文本;
}
// END 装备属性

var status = -1;
var 商品 = null;   // {id, price, maxQty}

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode === -1 || mode === 0) {
        cm.dispose();
        return;
    }
    status++;
    if (status === 0) {
        cm.sendSimple(商店菜单());
    } else if (status === 1) {
        选择商品(selection);
    } else if (status === 2) {
        输入数量(selection);
    } else if (status === 3) {
        结算();
    } else {
        cm.dispose();
    }
}

// ============================================================
// 界面
// ============================================================
function 商店菜单() {
    var 文本 = "#e#d【起源之塔 · 积分商店】#k#n\r\n";
    文本 += "当前起源积分：#r" + 取积分() + "#k 分\r\n";
    文本 += "#d----------------------------------------#k\r\n";

    文本 += "#e#b── 起源抽奖卷 ──#k#n\r\n";
    for (var i = 0; i < 抽奖卷.length; i++) {
        var 卷 = 抽奖卷[i];
        文本 += 商品行(i, 卷[0], 卷[2]);
    }

    文本 += "\r\n#e#b── 法弗纳系列武器 #d(统一 " + 法弗纳单价 + " 分)#k#n\r\n";
    for (var n = 0; n < 法弗纳清单.length; n++) {
        文本 += 商品行(抽奖卷.length + n, 法弗纳清单[n], 法弗纳单价);
    }
    文本 += "\r\n#d点击名称选商品；鼠标移到图标上可看装备说明。#k";
    文本 += "\r\n#d背包放不下的部分会直接掉在你脚下，需要自己拾取。#k";
    return 文本;
}

// 一行商品：图标放在链接【外】——#L...#l 会生成可点击区域抢走鼠标，图标放里面
// 就收不到悬停了；价格与名称放在链接内，点一下选中该商品。
// 价格排在名称之前并用半角宽度左补空格，这样不同位数的价格能对齐成一列
// （对话框没有制表位，原来的 \t 是错位的元凶）。
function 商品行(选择值, 道具ID, 价格) {
    return "#v" + 道具ID + "# #L" + 选择值 + "#"
        + 文本_补左(价格 + " 分", 8) + "  #t" + 道具ID + "##l\r\n";
}

function 选择商品(selection) {
    if (selection < 抽奖卷.length) {
        var 卷 = 抽奖卷[selection];
        商品 = {id: 卷[0], price: 卷[2], maxQty: 100};
    } else {
        var idx = selection - 抽奖卷.length;
        if (idx < 0 || idx >= 法弗纳清单.length) {
            cm.sendOk("商品不存在。");
            cm.dispose();
            return;
        }
        商品 = {id: 法弗纳清单[idx], price: 法弗纳单价, maxQty: 1};
    }

    var 文本 = "你想要兑换：\r\n";
    文本 += "#v" + 商品.id + "# #t" + 商品.id + "#\r\n";

    var 概览 = 装备概览文本(商品.id);
    if (概览 !== "") {
        文本 += "#d----------------------------------------#k\r\n";
        文本 += 概览;
    }

    文本 += "#d----------------------------------------#k\r\n";
    文本 += "单价：#r" + 商品.price + "#k 起源积分\r\n";
    文本 += "当前积分：#b" + 取积分() + "#k，最多可买 #b" + 可买数量() + "#k 个\r\n\r\n";
    文本 += "请输入兑换个数（上限 " + 商品.maxQty + "）";
    cm.sendGetNumber(文本, 1, 1, 商品.maxQty);
}

// 装备简况。商店只挑关键项（需求 + 加成各压成一行）；完整属性走大厅 NPC 的
// 「奖池预览」。非装备（抽奖卷）返回空串，调用方就不会多画一条分割线。
function 装备概览文本(道具ID) {
    if (Math.floor(道具ID / 1000000) !== 1) {
        return "";
    }
    var 属性 = 装备_取属性(道具ID);
    if (属性.读取失败) {
        return "#d（属性读取失败，请反馈管理员）#k\r\n";
    }
    var 文本 = "";
    var 需求 = 装备_需求行(属性);
    if (需求.length > 0) {
        文本 += "#e需求#n  ";
        for (var i = 0; i < 需求.length; i++) {
            文本 += 需求[i][0] + "：#r" + 需求[i][1] + "#k  ";
        }
        文本 += "\r\n";
    }
    var 加成 = 装备_加成行(属性);
    if (加成.length > 0) {
        文本 += "#e属性#n  ";
        for (var n = 0; n < 加成.length; n++) {
            文本 += 加成[n] + "  ";
        }
        文本 += "\r\n";
    }
    return 文本 === "" ? "#d（该装备没有额外属性）#k\r\n" : 文本;
}

function 输入数量(数量) {
    var 个 = 数量 > 0 ? 数量 : 1;
    if (个 > 商品.maxQty) {
        个 = 商品.maxQty;
    }
    商品.qty = 个;
    var 文本 = "确定花费 #r" + (商品.price * 个) + "#k 起源积分兑换 " + 个 + " 个 #b#t" + 商品.id + "##k 吗？\r\n";
    if (!cm.canHold(商品.id, 个)) {
        文本 += "\r\n#r#e注意：背包空间不足#k#n\r\n放不下的部分会 #b直接掉在你脚下#k，"
            + "需要#r自己拾取#k，长时间不捡会消失。\r\n";
    }
    cm.sendYesNo(文本);
}

function 结算() {
    var 花费 = 商品.price * 商品.qty;
    var 持有 = 取积分();
    if (持有 < 花费) {
        cm.sendOk("起源积分不足，还差 #r" + (花费 - 持有) + "#k 分。\r\n\r\n去起源之塔挑战就能赚积分。");
        cm.dispose();
        return;
    }
    写积分(持有 - 花费);

    // 放得下的进背包，放不下的直接掉在脚下（积分按整笔扣除，掉落由玩家自己捡）
    var chr = cm.getPlayer();
    var 进包 = 0, 落地 = 0, 未发 = 0;
    for (var i = 0; i < 商品.qty; i++) {
        var 落点 = 掉落_发一个(chr, 商品.id, false);   // 商店按基础属性发放，与 gainItem(id, qty) 同口径
        if (落点 === '包') {
            进包++;
        } else if (落点 === '地') {
            落地++;
        } else {
            未发++;
        }
    }

    var 文本 = "兑换成功！\r\n";
    if (进包 > 0) {
        文本 += "获得 #i" + 商品.id + "# #b#t" + 商品.id + "##k ×" + 进包 + "。\r\n";
    }
    if (落地 > 0) {
        文本 += "背包放不下 #r" + 落地 + "#k 个，#b已掉在你脚下#k，请#r自己拾取#k。\r\n";
    }
    if (未发 > 0) {
        文本 += "#d有 " + 未发 + " 个未能发放（当前地图不允许掉落，背包也放不下）。#k\r\n";
    }
    文本 += "消耗 " + 花费 + " 起源积分，剩余 #r" + 取积分() + "#k 分。";
    cm.sendOk(文本);
    cm.dispose();
}

function 可买数量() {
    var 个 = Math.floor(取积分() / 商品.price);
    return Math.min(个, 商品.maxQty);
}

// ============================================================
// 起源积分读写（唯一真源 = extend_value 表的「起源积分」字段）
// ============================================================
function 取积分() {
    return parseInt(cm.getCharacterExtendValue(起源积分键)) || 0;
}

function 写积分(值) {
    cm.saveOrUpdateCharacterExtendValue(起源积分键, String(值));
}
