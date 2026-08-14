/**
 * @description 拍卖行中心脚本
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[技能中心]#k系统#n\t\t\t\t\r\n";
var status = -1;
var i = 0;

function start() {
    action(1, 0, 0)
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
        let text = OldTitle;
        text += " \r\n";
        text += "#L1##b快捷技能(获取二段跳)#l\t\r\n\r\n";
        if (cm.getPlayer().isGM()) {
            text += "#L2#技能全满#l\t\r\n\r\n";
        }
        text += "#L3#三宠技能#l\t\r\n\r\n";
        text += "#L4#技能偷学#l\t\r\n\r\n";
        text += "#L5#风影漫步修复(仅限风灵使者使用)#l\t\r\n\r\n";
//        text += "#L6#龙神技能面板#l\t\r\n\r\n";
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else {
        cm.dispose();
    }
}

function doSelect(selection) {
    switch (selection) {
        case 1:
            openNpc("快捷技能");
            break;
        case 2:
            openNpc("技能全满");
            break;
        case 3:
            openNpc("三宠技能");
            break;
        case 4:
            openNpc("技能偷学");
            break;
        case 5:
            风影漫步修复();
            break;
        case 6:
            openNpc("龙神技能面板");
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
const SkillFactory = Java.type("org.gms.client.SkillFactory");

function 风影漫步修复() {
    var job = cm.getJob();
    if(job.getId() >= 1300 && job.getId() <= 1312){
        ///获取风影漫步技能
        var skill= SkillFactory.getSkill(13101006);
        var targetSkill= SkillFactory.getSkill(14100005);
        var player = cm.getPlayer();
        let curLevel=player.getSkillLevel(skill);
        //14100005需要同步驱逐这个技能等级才能使风影漫步生效
        player.changeSkillLevel(targetSkill, curLevel, 20, -1);
        //修复成功
        cm.sendOk("风影漫步修复成功,\r\n#b建议每次风影漫步升级都手动修复一下，满级后不用修复！");
        cm.dispose();
    }else {
        cm.sendOk("非风灵使者不用修复！");
        cm.dispose();
    }
}
