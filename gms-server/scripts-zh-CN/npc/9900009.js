var CHAIR_PRICE = 6000;
var FISHING_CHAIR = 3011000;
var PAGE_SIZE = 20;
var PREVIOUS_PAGE = 1000000;
var NEXT_PAGE = 1000001;
var BACK_TO_MAIN = 1000002;

var stage = "init";
var currentPage = 0;
var selectedChair = 0;
var chairIds = [
    3010000, 3010001, 3010002, 3010003, 3010004, 3010005, 3010006, 3010007, 3010008, 3010009,
    3010010, 3010011, 3010012, 3010013, 3010014, 3010015, 3010016, 3010017, 3010018, 3010019,
    3010020, 3010021, 3010022, 3010023, 3010024, 3010025, 3010026, 3010027, 3010028, 3010029,
    3010030, 3010031, 3010032, 3010033, 3010034, 3010035, 3010036, 3010037, 3010038, 3010039,
    3010040, 3010041, 3010043, 3010044, 3010045, 3010046, 3010047, 3010048, 3010049, 3010050,
    3010051, 3010052, 3010053, 3010055, 3010056, 3010057, 3010058, 3010059, 3010060, 3010061,
    3010062, 3010063, 3010064, 3010065, 3010066, 3010067, 3010068, 3010069, 3010072, 3010073,
    3010075, 3010077, 3010080, 3010081, 3010082, 3010083, 3010084, 3010085, 3010092, 3010093,
    3010094, 3010095, 3010096, 3010097, 3010098, 3010099, 3010100, 3010102, 3010103, 3010104,
    3010105, 3010106, 3010107, 3010108, 3010109, 3010110, 3010111, 3010112, 3010113, 3010114,
    3010115, 3010116, 3010117, 3010118, 3010119, 3010120, 3010123, 3010124, 3010125, 3010126,
    3010127, 3010128, 3010129, 3010130, 3010131, 3010132, 3010133, 3010134, 3010135, 3010136,
    3010137, 3010138, 3010139, 3010140, 3010141, 3010142, 3010144, 3010145, 3010146, 3010149,
    3010150, 3010151, 3010152, 3010154, 3010155, 3010156, 3010157, 3010161, 3010162, 3010166,
    3010168, 3010169, 3010170, 3010172, 3010173, 3010174, 3010175, 3010177, 3010179, 3010180,
    3010181, 3010183, 3010184, 3010188, 3010189, 3010191, 3010194, 3010196, 3010197, 3010200,
    3010201, 3010202, 3010203, 3010205, 3010206, 3010208, 3010211, 3010215, 3010216, 3010218,
    3010219, 3010222, 3010224, 3010225, 3010257, 3010279, 3010282, 3010283, 3010287, 3010288,
    3010290, 3010296, 3010297, 3010298, 3010307, 3010313, 3010314, 3010315, 3010316, 3010317,
    3010318, 3010319, 3010320, 3010321, 3010322, 3010354, 3010360, 3010364, 3010365, 3010368,
    3010369, 3010370, 3010371, 3010372, 3010373, 3010374, 3010375, 3010376, 3010377, 3010383,
    3010390, 3010397, 3010402, 3010403, 3010404, 3010405, 3010406, 3010408, 3010421, 3010423,
    3010424, 3010429, 3010430, 3010431, 3010432, 3010433, 3010434, 3010435, 3010436, 3010437,
    3010439, 3010440, 3010442, 3010443, 3010444, 3010445, 3010446, 3010447, 3010449, 3010450,
    3010451, 3010452, 3010455, 3010457, 3010458, 3010459, 3010464, 3010465, 3010493, 3010510,
    3010512, 3010513, 3010514, 3010515, 3010516, 3010517, 3010518, 3010519, 3010520, 3010521,
    3010522, 3010523, 3010524, 3010525, 3010526, 3010531, 3010532, 3010533, 3010534, 3010535,
    3010536, 3010537, 3010538, 3010539, 3010541, 3010543, 3010544, 3010545, 3010546, 3010547,
    3010548, 3010551, 3010552, 3010553, 3010554, 3010555, 3010556, 3010557, 3010558, 3010559,
    3010560, 3010561, 3010562, 3010563, 3010564, 3010565, 3010566, 3010567, 3010568, 3010569,
    3010570, 3010571, 3010572, 3010573, 3010574, 3010583, 3010584, 3010585, 3010587, 3010589,
    3010592, 3010596, 3010597, 3010600, 3010608, 3010643, 3010644, 3010651, 3010652, 3010653,
    3010654, 3010655, 3010656, 3010659, 3010663, 3010675, 3010682, 3010683, 3010698, 3010699,
    3010700, 3010703, 3010721, 3010742, 3010743, 3010744, 3010752, 3010754, 3010755, 3010756,
    3010766, 3010797, 3010798, 3010800, 3010801, 3010802, 3010803, 3010804, 3010806, 3010854,
    3010864, 3010867, 3010878, 3010947, 3010948, 3010965, 3012000, 3012001, 3012002, 3012006,
    3012007, 3012008, 3012009, 3012010, 3012011, 3013000, 3013002, 3013008, 3013009, 3015000,
    3015011, 3015012, 3015015, 3015016, 3015017, 3015018, 3015019, 3015020, 3015021, 3015022,
    3015023, 3015024, 3015025, 3015026, 3015027, 3015034, 3015035, 3015045, 3015174, 3015238,
    3015240, 3015241, 3015244, 3015279, 3015325, 3015330, 3015332, 3015340, 3015404, 3015405,
    3015416, 3015628, 3015639, 3015640, 3015641, 3015666, 3015759, 3015818, 3015848, 3015962,
    3015994, 3018003, 3018006, 3018008, 3018039, 3018042, 3018112, 3018138, 3018140, 3018222,
    3018224, 3018259, 3018361, 3018436, 3018614, 3019700
];

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }

    if (stage === "init") {
        stage = "main";
        showMainMenu();
        return;
    }

    if (stage === "main") {
        if (selection === 0) {
            cm.dispose();
            cm.openNpc(9900001, "时装暖暖");
            return;
        }
        if (selection === 1) {
            stage = "chairs";
            currentPage = 0;
            showChairPage();
            return;
        }
        rejectInvalidSelection();
        return;
    }

    if (stage === "chairs") {
        handleChairPageSelection(selection);
        return;
    }

    if (stage === "confirm") {
        purchaseChair();
        return;
    }

    cm.dispose();
}

function showMainMenu() {
    var text = "#e#b潮流前线#k#n\r\n\r\n";
    text += "#L0##b时装暖暖#k#l\r\n";
    text += "#L1##b椅子#k（每把 " + CHAIR_PRICE + " 点券）#l";
    cm.sendSimple(text);
}

function showChairPage() {
    if (chairIds.length === 0) {
        cm.sendOk("当前没有可购买的椅子。");
        cm.dispose();
        return;
    }

    var pageCount = Math.ceil(chairIds.length / PAGE_SIZE);
    if (currentPage < 0 || currentPage >= pageCount) {
        rejectInvalidSelection();
        return;
    }

    var startIndex = currentPage * PAGE_SIZE;
    var endIndex = Math.min(startIndex + PAGE_SIZE, chairIds.length);
    var balance = cm.getPlayer().getCashShop().getCash(1);
    var text = "#e椅子商店#n  #d第 " + (currentPage + 1) + "/" + pageCount + " 页#k\r\n";
    text += "每把 #r" + CHAIR_PRICE + "#k 点券，当前余额：#b" + balance + "#k\r\n\r\n";

    for (var i = startIndex; i < endIndex; i++) {
        var itemId = chairIds[i];
        text += "#L" + i + "##i" + itemId + "# #b#z" + itemId + "##k#l\r\n";
    }

    text += "\r\n";
    if (currentPage > 0) {
        text += "#L" + PREVIOUS_PAGE + "##b上一页#k#l  ";
    }
    if (currentPage + 1 < pageCount) {
        text += "#L" + NEXT_PAGE + "##b下一页#k#l  ";
    }
    text += "#L" + BACK_TO_MAIN + "##d返回主菜单#k#l";
    cm.sendSimple(text);
}

function handleChairPageSelection(selection) {
    var pageCount = Math.ceil(chairIds.length / PAGE_SIZE);
    if (selection === PREVIOUS_PAGE && currentPage > 0) {
        currentPage--;
        showChairPage();
        return;
    }
    if (selection === NEXT_PAGE && currentPage + 1 < pageCount) {
        currentPage++;
        showChairPage();
        return;
    }
    if (selection === BACK_TO_MAIN) {
        stage = "main";
        showMainMenu();
        return;
    }

    var startIndex = currentPage * PAGE_SIZE;
    var endIndex = Math.min(startIndex + PAGE_SIZE, chairIds.length);
    if (selection < startIndex || selection >= endIndex) {
        rejectInvalidSelection();
        return;
    }

    selectedChair = chairIds[selection];
    if (selectedChair === FISHING_CHAIR) {
        rejectInvalidSelection();
        return;
    }

    stage = "confirm";
    var text = "确定花费 #r" + CHAIR_PRICE + "#k 点券购买以下椅子吗？\r\n\r\n";
    text += "#i" + selectedChair + "# #b#z" + selectedChair + "##k";
    cm.sendYesNo(text);
}

function purchaseChair() {
    if (!containsChair(selectedChair)) {
        rejectInvalidSelection();
        return;
    }
    if (!cm.canHold(selectedChair, 1)) {
        cm.sendOk("设置栏背包空间不足，请整理后再来。");
        cm.dispose();
        return;
    }

    var cashShop = cm.getPlayer().getCashShop();
    if (cashShop.getCash(1) < CHAIR_PRICE) {
        cm.sendOk("点券不足，需要 #r" + CHAIR_PRICE + "#k 点券。");
        cm.dispose();
        return;
    }

    cashShop.gainCash(1, -CHAIR_PRICE);
    cm.gainItem(selectedChair, 1);
    cm.sendOk("购买成功，获得 #i" + selectedChair + "# #b#z" + selectedChair + "##k。\r\n已扣除 #r" + CHAIR_PRICE + "#k 点券。");
    cm.dispose();
}

function containsChair(itemId) {
    for (var i = 0; i < chairIds.length; i++) {
        if (chairIds[i] === itemId) {
            return true;
        }
    }
    return false;
}

function rejectInvalidSelection() {
    cm.sendOk("选择无效，请重新打开对话。");
    cm.dispose();
}
