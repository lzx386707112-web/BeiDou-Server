var status = -1;
var selectedBase = 0;
var colorOptions = [];

var MALE_BASES = [
    40070, 40080, 42100, 46540, 46550, 47140, 42200,
    42210, 42220, 42230, 42240, 42250, 42260, 42270
];
var FEMALE_BASES = [
    43270, 44440, 44450, 48670, 48680, 48690, 48700,
    48710, 48720, 48730, 48740, 48750, 48760, 48770
];

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode < 1) {
        cm.dispose();
        return;
    }

    status++;

    if (status == 0) {
        var bases = getGenderBases();
        if (bases.length == 0) {
            cm.sendOk("当前性别没有可预览的发型。");
            cm.dispose();
            return;
        }
        cm.sendStyle("请选择想预览的发型款式。", bases);
    } else if (status == 1) {
        var bases = getGenderBases();
        if (selection < 0 || selection >= bases.length) {
            cm.sendOk("该发型不可用，请重新选择。");
            cm.dispose();
            return;
        }

        selectedBase = bases[selection];
        colorOptions = buildColorOptions(selectedBase);
        cm.sendStyle("请选择想预览的发色。", colorOptions);
    } else if (status == 2) {
        if (selection < 0 || selection >= colorOptions.length) {
            cm.sendOk("该颜色不可用，请重新选择。");
            cm.dispose();
            return;
        }

        cm.setHair(colorOptions[selection]);
        cm.sendOk("发型已更换。");
        cm.dispose();
    } else {
        cm.dispose();
    }
}

function buildColorOptions(base) {
    var result = [];
    for (var color = 0; color <= 7; color++) {
        result.push(base + color);
    }
    return result;
}

function getGenderBases() {
    return cm.getPlayer().getGender() == 0 ? MALE_BASES : FEMALE_BASES;
}
