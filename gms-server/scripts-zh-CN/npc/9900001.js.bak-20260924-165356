/**
 * @description 拍卖行中心脚本
 */
var DAILY_CHECK_IN_TOTAL = "累计签到次数"
var status = -1;
var i = 0;
// var icon="#fMap/MapHelper/minimap/arrowright#";
var icon = "#fUI/UIWindow.img/Quest/icon8/0#";
const I18nUtil = Java.type('org.gms.util.I18nUtil');
const LoggerFactory = Java.type('org.slf4j.LoggerFactory');

function start() {
    try {
        action(1, 0, 0)
    } catch (e) {
        cm.dispose();
        // 打印错误日志便于调试
        console.error("主菜单脚本错误===》:", e);
    }
}

function addTextInfo(text) {
    var id = cm.getPlayer().getId();
    text = `#b用户ID:#r${id}`;
    if (id < 10) {
        text += "\t\t\t\t";
    } else if (id < 1000) {
        text += "\t\t\t";
    } else {
        text += "\t\t";
    }
    text += "#k当前点券：#r" + cm.getPlayer().getCashShop().getCash(1) + "\t\t\t"
    text += "#k转生次数:#r" + cm.getChar().getReborns() + " \r\n";
    var day = Number(cm.getAccountExtendValue(DAILY_CHECK_IN_TOTAL));
    text += `#k签到天数:#r${day}`;
    if (day < 10) {
        text += "\t\t\t";
    } else if (id < 1000) {
        text += "\t\t";
    }
    text += "#k累计副本积分:#r" + cm.getPqTotalPoints() + "\t\t\t";
    text += "#k剩余副本积分:#r" + cm.getPqPoints() + " \r\n";
    return text;
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
        var log = LoggerFactory.getLogger("main_js");
        var OldTitle = "\t\t\t\t\t#e#k欢迎大佬 #r[" + cm.getPlayer().getName() + "] #k您的到来#n\t\t\t\t\r\n";
        let text = OldTitle;
        text += " \r\n";
        text += addTextInfo();
        var jobId = cm.getPlayer().getJob().getId();
        if ((jobId == 0 || jobId == 1000 || jobId == 2000) && !cm.getPlayer().isGM() && 获取更换职业次数() == 1) {
            text += "#L999#新人福利#n#l\r\n\r\n\r\n";
            text += "\t#b(一转后开启传送功能)\r\n";
            text += "#L1#" + icon + "#r万能传送#l\t#L2#随身仓库#l\t#L3#便利商店#l\t#L4#一键出售#l\r\n";
            text += " \r\n";
        } else {
            text += "\t\t\t\t\t#L0 ##b自由市场#n#l\t\t #L999#新人福利#n#l\r\n";
            text += " \r\n";
            text += "#L1#" + icon + "#r万能传送#l\t#L2#随身仓库#l\t#L3#便利商店#l\t#L4#一键出售#l\r\n";
            text += " \r\n";

        }
        text += "#b#L5#" + icon + "每日签到#l\t#L6#在线奖励#l\t#L7#任务大厅#l\t #L8#各种兑换#l\r\n";
        text += " \r\n";
        text += "#L9#" + icon + "职业中心#l\t#L10#技能中心#l\t#L11#装备中心#l\t#L12#时装暖暖#l\r\n";
        text += " \r\n";
        text += "#L13#" + icon + "额外仓库#l\t#L14#删除道具#l\t#L15#查询掉落#l\t#L16#其他功能#l\r\n";
        text += " \r\n";
        text += "#L19#" + icon + "卷轴分解#l\t#L21#副本兑换#l\t#L22#抽奖保底#l\t#L20#拍卖行#l\r\n";
        text += " \r\n";
        text += "#L23#" + icon + "战力排行#l\t#L24#怪物攻城#l\t#L25#共同富裕#l\t#L26#理财#l\r\n";
        text += " \r\n";
        if (cm.getPlayer().isGM()) {
            text += "\r\n";
            text += "\t\t\t\t#r=====以下内容仅GM可见=====\r\n";
            text += "#L100#巡逻#l\t\r\n\r\n";
            text += "#L107#设置血蓝#l\t\r\n\r\n";
            text += "#L101#UI查询#l\t#L102#GM商店集合#l\r\n";
            text += "#L103#一键删除道具#l\t#L104#一键刷道具#l\r\n";
            text += "#L105#有状态脚本示例#l\t #L106#NextLevel脚本示例#l";
            text += "#L108#加1000积分#l\t\r\n\r\n";
        }
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else {
        cm.dispose();
    }
}


function doSelect(selection) {
    switch (selection) {
        // 脚本移植注意编码改为UTF-8
        case 0://去自由
            cm.getPlayer().saveLocationOnWarp();
            cm.warp(910000000);
            cm.dispose();
            break;
        case 1://万能传送
            // openNpc("test/装备强化");
            openNpc("万能传送");
            break;
        case 2://随身仓库
            openNpc("随身仓库");
            break;
        case 3://便利商店
            cm.openShopNPC(9201099); //便利商店
            cm.dispose();
            break;
        case 4://一键出售
            openNpc("一键出售");
            break;
        case 5://每日签到
            openNpc("每日签到");
            break;
        case 6://在线奖励
            openNpc("在线奖励");
            break;
        case 7://任务大厅
            openNpc("任务大厅");
            break;
        case 8://各种兑换
            openNpc("各种兑换");
            break;
        case 9://职业中心
            openNpc("职业相关");
            break;
        case 10://技能中心
            openNpc("技能中心");
            break;
        case 11://装备中心
            openNpc("装备中心");
            break;
        case 12://时装暖暖#
            openNpc("时装暖暖");
            break;
        case 13://额外仓库
            openNpc("物品仓库系统");
            break;
        case 14://删除道具
            openNpc("删除道具");
            break;
        case 15://查询掉落
            openNpc("查询掉落");
            break;
        case 16://其他功能
            openNpc("其他功能");
            break;
            break;
        case 17://各种商店
            openNpc("各种商店");
            break;
        case 18://新人福利
            openNpc("卷轴商店");
            break;
        case 19://卷轴分解
            openNpc("卷轴碎片");
            break;
        case 20://拍卖行
            拍卖系统();
            break;
        case 21://副本兑换
            openNpc("副本相关/副本兑换");
            break;
        case 22://副本兑换
            openNpc("抽奖保底");
            break;
        case 23://战力系统
            openNpc("战力系统");
            break;
        case 24://怪物攻城
            cm.sendOk("该功能还未完成，敬请期待！");
            cm.dispose();
            // openNpc("怪物攻城");
            break;
        case 25://共同富裕
            openNpc("共同富裕");
            break;
        case 26://冒险炒股
            // openNpc("召唤怪物");
            openNpc("金融/冒险炒股");
            break;
        case 999://新人福利
            openNpc("新人福利");
            break;
        // GM功能
        case 100://巡逻
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
            openNpc("Example1")
            break;
        case 106:
            openNpc("Example2")
            break;
        case 107:
            openNpc("设置血蓝")
            break;
        case 108:
            cm.addPqPoints(1000);
            cm.sendOk("添加成功");
            cm.dispose();
            break;
        case 1000:
            // openNpc("砸卷次数");
            // openNpc("音乐点播");
            // openNpc("战力系统");
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

function 获取更换职业次数() {
    let count = cm.getAccountExtendValue("更换职业次数");
    return Number(count) || 0; // 处理未签到过的情况
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