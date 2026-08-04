/**
 * 名称：在线奖励(nextlevel版)
 * 功能：用于颁发在线奖励的脚本，采用JSON配置阶段奖励，NextLevel构造脚本，具有配置清晰便捷、代码逻辑清晰的特点。
 *      支持配置的奖励有 金币、经验、点券、抵用券、信用点 和 有效物品
 *      支持输入整数按份领取奖励列表
 *      新增功能：一键领取所有已满足条件的奖励
 * 作者：Magical-H (https://www.github.com/Magical-H)
 * 版本：1.1
 * 日期：2025-06-28
 */

/**
 * 奖励配置
 * - itemlist的id解释：
 * - 0：金币;
 * - 1：点券;
 * - 2：抵用券;
 * - 4、信用点;
 * - 5、经验值;
 * - id ≥ 1_000_000 的为有效物品ID，自动区分，你只需要操心客户端有没有填入的物品即可。
 */
var config = {
	reward:[
		{
			online:10,	//时长限制，单位：分钟
			itemlist:[
				// id解释：0：金币;  1：点券;  2：抵用券;  4、信用点; 5、经验值;  id ≥ 1_000_000 的为有效物品ID，自动区分，你只需要操心客户端有没有填入的物品即可。
				{id:0,qty:10000},	//金币，数量1万
				{id:2430033,qty:1}	//北斗指南书碎片，数量5
			]
		},{
			online:30,
			itemlist:[
				{id:0,qty:50000},	//金币
				{id:2430033,qty:1}	//北斗指南书碎片
			]
		},{
			online:60,
			itemlist:[
				{id:0,qty:100000},	//金币
				{id:2430033,qty:1},	//北斗指南书碎片
			]
		},{
			online:120,
			itemlist:[
				{id:0,qty:150000},	//金币
				{id:2430033,qty:2},	//北斗指南书碎片
			]
		},{
			online:240,
			itemlist:[
				{id:0,qty:200000},	//金币
				{id:2430033,qty:2},	//北斗指南书碎片
				{id:2340000,qty:1},	//祝福
				{id:2049100,qty:1},	//混沌
			]
		},{
			online:360,
			itemlist:[
				{id:0,qty:400000},	//金币
				{id:2430033,qty:2},	//北斗指南书碎片
				{id:2340000,qty:1},	//祝福
				{id:2049100,qty:1},	//混沌
				{id:4032133,qty:1}	//红色钻石
			]
		},{
			online:480,
			itemlist:[
				{id:0,qty:500000},	//金币
				{id:1,qty:1000},	//点券，数量1千
				{id:2430033,qty:3},	//北斗指南书碎片
				{id:4032133,qty:1},	//红色钻石
				{id:2340000,qty:1},	//祝福
				{id:2049100,qty:1},	//混沌
			]
		},
	]
}

var key="每日在线奖励领取状态";

/**
 * 全局变量
 * - 累计在线分钟数
 * @type {number}
 */
var g_OnlineMinutes = 0;
/**
 * 全局变量
 * - 奖励领取状态
 * @type {number}
 */
var g_ClaimStatus;
/**
 * 全局变量
 * - 待兑换的奖励索引
 * @type {number}
 */
var g_Select;
/**
 * 全局变量
 * - 待兑换的奖励份数
 * @type {number}
 */
var g_itemCount = 1;

// 定义物品显示模板的映射表（ES6对象字面量优化）
const ITEM_TEMPLATES = {
	0: '#fUI/Basic.img/BtCoin/normal/0#   #fUI/UIWindow.img/QuestIcon/7/0#',	//金币
	1: '#fUI/CashShop.img/CashItem/0#   #e#b点券#k#n',
	2: '#fUI/CashShop.img/CashItem/0#   #e#b抵用券#k#n',
	4: '#fUI/CashShop.img/CashItem/0#   #e#b信用点#k#n',
	5: '#fUI/UIWindow.img/AriantMatch/characterIcon/2#   #fUI/UIWindow.img/QuestIcon/8/0#'	//经验值
};

function start() {
	var limitDt = new Date();
	limitDt.setHours(0, 0, 5, 0);
	if (new Date() <= limitDt) {
		cm.sendOkLevel("","在线奖励正在初始化中，请稍后再试...");
	} else {
		g_OnlineMinutes = getOnlineMinute();
		g_ClaimStatus = getOnlineStatus() || 0;
		levelmain();
	}
}

function level() {
	cm.dispose();
}
function levelnull() {
	level();
}
function leveldispose() {
	level();
}

function levelmain() {
	text = "亲爱的玩家：#e#b#h ##k#n，感谢您持续在线支持！\r\n";
	text += `#e今日已累积在线：#n${formatMinutes(g_OnlineMinutes)}\r\n`;
	text += "我们为您准备了丰厚的在线时长奖励，点击领取下方的奖励：\r\n";
	// 新增：添加一键领取选项
	text += "#L999##r【一键领取所有可领奖励】#k#l\r\n\r\n";

	text += getOnlineRewardListText() + "\r\n\r\n";
	text += "\r\n【领取说明】\r\n · 可选择单个领取或一键领取所有已解锁的奖励\r\n · #b每日0点#e#r重置#b#n累计时长#k\r\n · 背包空间不足将不会发放奖励\r\n · 坚持在线时间越长，获得奖励越丰厚！";
	cm.sendNextSelectLevel("claimrewards",text);
}

function levelclaimrewards(Select) {
	// 检查是否是一键领取的选项
	if (Select == 999) {
		levelclaimallrewards(); // 调用一键领取的函数
		return; // 结束当前函数
	}

	const reward = config.reward[Select];
	// 注意：原代码在这里提前设置了 g_ClaimStatus，这是个逻辑错误。
	// 应该在确认领取后（在 levelgiveRewardItems 中）再设置。
	// 这里先注释掉，它会在 giveRewardItems 中被正确设置。
	// g_ClaimStatus |= (1 << Select);
	let text = "\r\n";
	text += getRewardList(Select);
	if (reward.isReceive) {	//已领取
		text += "\r\n\r\n#r#e以上奖励你已领取过了，无法再次领取。#k#n";
	} else if (!reward.isClaimed) {//未满足在线时长
		text += "\r\n\r\n#r#e你的在线时长尚不足以领取上方奖励。#k#n";
	} else {	//待领取
		text += "\r\n\r\n#b#e你已满足领取条件，是否领取奖励？#n#k";
		g_Select = Select;
		cm.sendYesNoLevel("","giveRewardItems",text);
		return;
	}
	cm.sendOkLevel("",text);
}

/**
 * 一键领取所有可领取的奖励 - 确认界面
 */
function levelclaimallrewards() {
	let claimableRewards = [];
	// 首先，找出所有可以领取的奖励
	for (let i = 0; i < config.reward.length; i++) {
		const isReceived = (g_ClaimStatus & (1 << i)) !== 0;
		const isClaimable = g_OnlineMinutes >= config.reward[i].online;
		if (isClaimable && !isReceived) {
			claimableRewards.push(i);
		}
	}

	if (claimableRewards.length === 0) {
		cm.sendOkLevel("", "当前没有可领取的奖励。");
		return;
	}

	let text = "你确定要一键领取以下所有奖励吗？\r\n";
	claimableRewards.forEach((index, idx) => {
		// 拼接每个奖励的文本，一行显示两个
		text += `#k#L${index}#【${formatMinutes(config.reward[index].online)}】在线奖励#l`;
		// 索引为奇数时换行（0和1为第一行，2和3为第二行，以此类推）
		if ((idx + 1) % 2 === 0) {
			text += "\r\n";
		} else {
			// 同一行的两个奖励之间用空格分隔
			text += "  ";
		}
	});
	// 如果奖励数量为奇数，最后一行可能缺少换行，手动补一个
	if (claimableRewards.length % 2 !== 0) {
		text += "\r\n";
	}
	// 使用一个特殊的选择ID，比如 -1，来标识确认一键领取
	cm.sendYesNoLevel("","doclaimall", text);
}

/**
 * 执行一键领取操作
 */
function leveldoclaimall() {
	let claimedCount = 0;
	let failedItems = []; // 用于收集所有背包不足的物品信息

	// 循环检查并发放所有可领取的奖励
	for (let i = 0; i < config.reward.length; i++) {
		const isReceived = (g_ClaimStatus & (1 << i)) !== 0;
		const isClaimable = g_OnlineMinutes >= config.reward[i].online;

		if (isClaimable && !isReceived) {
			const reward = config.reward[i];
			// 先检查背包空间
			const normalItems = reward.itemlist.filter(obj => obj.id >= 1_000_000);
			let canHoldAll = true;
			for (const {id, qty} of normalItems) {
				if (!cm.canHold(id, qty)) {
					canHoldAll = false;
					failedItems.push(`#i${id}#   #b#t${id}##k (来自【${formatMinutes(reward.online)}】奖励)`);
				}
			}

			if (!canHoldAll) {
				continue; // 如果某个奖励的物品背包不足，则跳过这个奖励
			}

			// 发放奖励
			for (const {id, qty} of reward.itemlist) {
				if (id >= 1_000_000) {
					cm.gainItem(id, qty);
				} else {
					switch(id) {
						case 0: cm.gainMeso(qty); break;
						case 1: case 2: case 4: cm.getPlayer().getCashShop().gainCash(id, qty); break;
						case 5: cm.gainExp(qty); break;
					}
				}
			}

			// 更新领取状态
			g_ClaimStatus |= (1 << i);
			claimedCount++;
		}
	}

	// 统一保存所有领取状态
	if (claimedCount > 0) {
		saveOnlineStatus(g_ClaimStatus);
	}

	let resultText = "";
	if (claimedCount > 0) {
		resultText += `成功领取了 #b${claimedCount}#k 个奖励！\r\n`;
	} else {
		resultText += "没有成功领取任何奖励。\r\n";
	}

	if (failedItems.length > 0) {
		resultText += "\r\n由于背包空间不足，以下物品无法发放：\r\n";
		failedItems.forEach(itemText => {
			resultText += itemText + "\r\n";
		});
	}
	if (claimedCount > 0) {
		sendSuperMegaphone(cm.getPlayer(), "在线奖励", `恭喜玩家${cm.getPlayer().getName()}一键领取了${claimedCount}个在线奖励!`);
	}
	cm.sendOkLevel("", resultText);
}

function levelgiveRewardItems() {
	cm.sendOkLevel("",giveRewardItems(g_Select,g_itemCount));
}

/**
 * 生成奖励物品的显示列表
 * @param {number} Select - 奖励索引
 * @param {Number} [count=1] - 包含奖励数据的配置对象
 * @returns {string} 格式化后的奖励列表字符串，每项用换行符分隔
 */
function getRewardList(Select,count = 1) {
	let reward = config.reward[Select];
	let text = reward.title + "\r\n\r\n";
	return text + reward.itemlist.map(obj => {
		let { id, qty } = obj;// 通过解构赋值获取当前物品属性
		let itemshow = ITEM_TEMPLATES[id] ?? '';// 根据物品ID获取基础显示模板（使用空值合并运算符??）
		if (count > 1) qty = `${qty}#k × ${count}份 = #b${qty * count}#k`;
		// 处理不同物品类型的显示逻辑
		if (id >= 1_000_000) {  // 有效的物品ID≥7位数，使用数字分隔符提高可读性
			itemshow = `#i${id}#   #e#b#t${id}##k#n × #r${qty}#k`;
		} else if (itemshow) {// 已知物品追加数量显示
			itemshow += ` × #r${qty}#k`;
		} else {// 未知物品显示错误提示
			itemshow = `#fUI/UIWindow.img/KeyConfig/BtHelp/mouseOver/0# #e#r未知物品ID：[#k ${id} #r]#k#n`;
		}
		return `#fUI/CashShop.img/CSDiscount/arrow# ${itemshow}`;// 为每项添加统一前缀并返回
	}).join('\r\n');  // 用回车换行符连接所有项
}

/**
 * 发放奖励道具（支持多份兑换）
 * @param {number} Select - 奖励索引
 * @param {number} [count=1] - 兑换份数（默认为1）
 * @returns {string} 发放结果信息（失败时返回无法兑换的物品列表）
 */
function giveRewardItems(Select,count = 1) {
	if (count <= 0 || count > g_itemCount) {
		return "输入的份数不能 ≤0 且 不能超过最大份数 " + g_itemCount;
	}
	const reward = config.reward[Select];
	// 验证普通物品
	const failedItems = [];
	const normalItems = reward.itemlist.filter(obj => obj.id >= 1_000_000);

	for (const {id, qty} of normalItems) {
		const totalQty = qty * count;
		if (!cm.canHold(id, totalQty)) {
			failedItems.push(`#fUI/UIWindow.img/FadeYesNo/BtCancel/mouseOver/0# #i${id}#   #b#t${id}##k × #r${totalQty}#k`);
		}
	}

	if (failedItems.length > 0) {
		return ` 背包空间不足，无法兑换以下物品：\r\n\r\n${failedItems.join('\r\n')}`;
	}

	// 实际发放所有物品
	const successItems = [];
	for (const {id, qty} of reward.itemlist) {
		const totalQty = qty * count;
		let succitemshow;

		if (id >= 1_000_000) {
			cm.gainItem(id, totalQty);
			succitemshow = `#i${id}#   #b#t${id}##k × #r${totalQty}#k`;
		} else {
			switch(id) {
				case 0:
					cm.gainMeso(totalQty);
					succitemshow = `${ITEM_TEMPLATES[id]} × #r${totalQty}#k`;
					break;
				case 1:
				case 2:
				case 4:
					cm.getPlayer().getCashShop().gainCash(id, totalQty);
					succitemshow =`${ITEM_TEMPLATES[id]} × #r${totalQty}#k`;
					break;
				case 5:
					cm.gainExp(totalQty);
					succitemshow =`${ITEM_TEMPLATES[id]} × #r${totalQty}#k`;
					break;
			}
		}
		if (succitemshow) {
			successItems.push(`#fUI/Basic.img/CheckBox/1# ${succitemshow}`);
		}
	}
	// 在这里设置领取状态
	g_ClaimStatus |= (1 << Select);
	saveOnlineStatus(g_ClaimStatus);//更新领取记录
	cm.dropMessage(0,`你已成功领取了 ${reward.title.toString().replace(/#[a-zA-Z]/g,"")}！`);
	sendSuperMegaphone(cm.getPlayer(), "在线奖励", `恭喜玩家${cm.getPlayer().getName()}领取了${reward.title.toString().replace(/#[a-zA-Z]/g, "")}!`);
	return `#fUI/UIWindow.img/QuestIcon/4/0#\r\n\r\n${successItems.join('\r\n')}`;
}

/**
 * 获取当前账号每日在线奖励领取状态
 * @returns {string}
 */
function getOnlineStatus() {
	return cm.getAccountExtendValue(key,true);
}

/**
 * 保存当前账号每日在线奖励领取状态
 * @returns {string}
 */
function saveOnlineStatus(status) {
	cm.saveOrUpdateAccountExtendValue(key, status.toString(), true);
}

/**
 * 将分钟格式化为d天h小时m分
 * @param minutes 分钟
 * @returns {string} 格式化字符串
 */
function formatMinutes(minutes) {
	const days = Math.floor(minutes / 1440);  // 1440 = 24*60
	minutes = minutes % 1440;
	const hours = Math.floor(minutes / 60);
	minutes = minutes % 60;

	let result = '';
	if (days > 0) result += `#r${days.toString().padStart(3," ")}#k天`;
	if (hours > 0) result += `#r${hours.toString().padStart(3," ")}#k小时`;
	if ((hours > 0 && minutes > 0) || (hours === 0 && minutes >= 0)) {
		result += `#r${minutes.toString().padStart(2," ")}#k分钟`;
	}
	return result;
}

/**
 * 获取玩家在线分钟数
 * @returns {number} 在线分钟数
 */
function getOnlineMinute() {
	return Math.floor(cm.getOnlineTime() / 60);
}

function getOnlineRewardListText() {
	let listtext = [];
	let CheckBox_0 = "#fUI/Basic.img/CheckBox/0#";
	let CheckBox_1 = "#fUI/Basic.img/CheckBox/1#";
	let CheckBox_2 = "#fUI/Basic.img/CheckBox/2#";

	return config.reward.map((obj, i) => {
		const isReceived = (g_ClaimStatus & (1 << i)) !== 0;  // 精确检查每一位
		const isClaimable = g_OnlineMinutes >= obj.online;
		let text = "";

		config.reward[i] = {
			...obj,
			isReceive: isReceived,
			isClaimed: isClaimable,
			title: `#b【${formatMinutes(obj.online)}#b】在线奖励列表`,
		};

		if (!isReceived) {
			listtext.push(1);
			if (isClaimable) {
				text += `\r\n#L${i}##b领取#k【${formatMinutes(obj.online)}#k】在线奖励 ${CheckBox_0}#k#l`;
			} else {
				text += `\r\n#L${i}##r查看#k【${formatMinutes(obj.online)}#k】在线奖励 ${CheckBox_2}#k#l`;
			}
		} else {
			if (i > 0 && listtext[i-1] === 1) text += "\r\n";
			text += `\r\n\t  #b已领#k【${formatMinutes(obj.online)}#k】在线奖励 ${CheckBox_1}`;
			listtext.push(0);
		}
		return text;
	}).join("");
}
function sendSuperMegaphone(player, typeOrTitle, titleOrContent, content) {
    if (player.checkoutBroadcast()) {
        return;
    }
    var title = content === undefined ? typeOrTitle : titleOrContent;
    var message = content === undefined ? titleOrContent : content;
    var fullMessage = "[" + title + "] : " + message;
    var Server = Java.type("org.gms.net.server.Server");
    var PacketCreator = Java.type("org.gms.util.PacketCreator");

    // 5072000（高质地喇叭）使用类型 3 的全服喇叭封包。
    Server.getInstance().broadcastMessage(
        player.getWorld(),
        PacketCreator.serverNotice(
            3,
            player.getClient().getChannel(),
            player.getName() + " : " + fullMessage,
            true
        )
    );
}
