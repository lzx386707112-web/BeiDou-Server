/**
 * 起源之塔 NPC / 积分商店 / 抽奖 / 奖池预览 的离线流程验证。
 * 用 mock cm 在 Node vm 里真跑一遍脚本，捕捉 API 名称写错、状态机跳错、
 * 对话框用法错误（例如 dispose 之后再 sendOk），以及**渲染出来的文本**里的
 * UI 约定（#v 图标必须在 #L 链接之外、价格靠半角宽度对齐、每行一件等）——
 * 这些用 Python 契约测试看不出来，只能把脚本跑起来才验得到。
 *
 * 用法： node tool/scripts/migration/test_seed_tower_rewards_flow.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '../../..');
const DIR = path.join(ROOT, 'gms-server/scripts-zh-CN/BeiDouSpecial/起源之塔');

const 失败 = [];
function 检查(ok, msg) {
    console.log((ok ? '  OK   ' : '  FAIL ') + msg);
    if (!ok) 失败.push(msg);
}

// 数一数 #v 图标有多少个落在 #L...#l 链接【里面】/【外面】。
// 这是本功能最容易踩的坑：图标一旦被链接包住，客户端就把鼠标交互交给链接，
// 悬停说明再也弹不出来 —— 而且不报错，只是"鼠标移上去没反应"。
// 参数 只要链接内=true 时返回链接内的个数（应当恒为 0）。
function 数图标(text, 只要链接内) {
    let 深度 = 0, 命中 = 0;
    for (let i = 0; i < text.length - 1; i++) {
        const 两字 = text.substr(i, 2);
        if (两字 === '#L') { 深度++; i++; continue; }
        if (两字 === '#l') { if (深度 > 0) 深度--; i++; continue; }
        if (两字 === '#v') { if ((深度 > 0) === 只要链接内) 命中++; i++; continue; }
    }
    return 命中;
}

// ---------------------------------------------------------------- mock cm
// 背包容量按「栏位」(itemId/1000000) 分开：1 = 装备栏、4 = 其他栏。
// 简化：不做堆叠合并，1 件 = 1 格。脚本是逐件判定（canHold(id,1)），
// 只用得到"这一件放不放得下"，所以这个简化不影响被测逻辑。
function 造环境(opts = {}) {
    const 状态 = {
        变量: Object.assign({}, opts.变量 || {}),
        物品: Object.assign({}, opts.物品 || {}),      // itemId -> 数量
        登录: [],           // sendSimple / sendOk / sendYesNo / sendGetNumber
        dispose次数: 0,
        买到: [],           // [id, qty]
        开NPC: [],
        warp: null,
        drop: [],
        掉落: [],           // 落地的地面掉落记录
        已用: { 1: 0, 4: 0 },   // 各栏已占格数
        可容纳件数: opts.canHold === false ? 0
            : (opts.可容纳件数 === undefined ? Infinity : opts.可容纳件数),
        其他栏可容: opts.其他栏可容 === undefined ? Infinity : opts.其他栏可容,
        fieldLimit: opts.fieldLimit === undefined ? 590316 : opts.fieldLimit,  // 大厅 992000000
        gainItem返回null: !!opts.gainItemNull,
    };
    状态.面板 = { 可容: (t) => (t === 1 ? 状态.可容纳件数 : (t === 4 ? 状态.其他栏可容 : Infinity)) };
    const 地图 = {
        getFieldLimit: () => 状态.fieldLimit,
        spawnItemDrop: (dropper, owner, item, pos, ffa, playerDrop) => {
            状态.掉落.push({ dropper, owner, item, pos, ffa, playerDrop });
        },
    };
    const 玩家 = {
        getItemQuantity: (id) => 状态.物品[id] || 0,
        getEventInstance: () => null,
        getMap: () => 地图,
        getPosition: () => ({ x: 10, y: 20 }),
        haveItemWithId: (id) => (opts.拥有 || []).indexOf(id) >= 0,
        dropMessage: (t, m) => 状态.drop.push(m),
        getLevel: () => 200,
        getName: () => '测试员',
    };
    const 栏位类型 = (id) => Math.floor(id / 1000000);
    const cm = {
        getPlayer: () => 玩家,
        getEventInstance: () => opts.eim || null,
        getCharacterExtendValue: (k) => (k in 状态.变量 ? 状态.变量[k] : null),
        saveOrUpdateCharacterExtendValue: (k, v) => { 状态.变量[k] = String(v); },
        sendSimple: (t) => 状态.登录.push({ type: 'simple', text: t }),
        sendOk: (t) => 状态.登录.push({ type: 'ok', text: t }),
        sendYesNo: (t) => 状态.登录.push({ type: 'yesno', text: t }),
        sendGetNumber: (t, d, mi, ma) => 状态.登录.push({ type: 'number', text: t, def: d, min: mi, max: ma }),
        dispose: () => { 状态.dispose次数++; },
        // 与真机一致：canHold 是只读预检（Inventory.checkSpots），不改动任何状态
        canHold: (id, qty) => {
            const t = 栏位类型(id);
            const n = 状态.已用[t] || 0;
            return n + (qty === undefined ? 1 : qty) <= 状态.面板.可容(t);
        },
        gainItem: (id, qty) => {
            状态.买到.push([id, qty]);
            const cur = 状态.物品[id] || 0;
            状态.物品[id] = Math.max(0, cur + qty);
            const t = 栏位类型(id);
            if (状态.已用[t] !== undefined) 状态.已用[t] = Math.max(0, 状态.已用[t] + qty);
            return 状态.gainItem返回null ? null : { id };
        },
        openNpc: (npc, script) => { 状态.开NPC.push(script); },
        warp: (m) => { 状态.warp = m; },
        getEventManager: () => null,
    };
    状态.登录.length = 0;
    return { cm, 状态, 玩家 };
}

// 服务端 getEquipStats() 的**真实**键集合（ItemInformationProvider.java:574-592）：
//   info 里 "inc*" 字段会被去掉前缀再入表（incSTR -> STR、incSpeed -> Speed）
//   其余 req*/cash/tuc/cursed/success/fs 原样入表。
// mock 必须照这个契约返回，否则会漏掉"脚本写 incPAD、真机永远查不到"这类错误。
const 服务端显式键 = ['reqJob', 'reqLevel', 'reqDEX', 'reqSTR', 'reqINT', 'reqLUK', 'reqPOP',
    'cash', 'tuc', 'cursed', 'success', 'fs'];
const 服务端去前缀键 = ['PAD', 'MAD', 'STR', 'DEX', 'INT', 'LUK', 'PDD', 'MDD', 'ACC', 'EVA',
    'MHP', 'MMP', 'MHPr', 'MMPr', 'Speed', 'MSpeed', 'Jump', 'PVPDamage', 'Craft', 'CriticalMAXDamage'];
const 服务端键集 = new Set([...服务端显式键, ...服务端去前缀键]);

const 属性表 = {
    1010000: { reqLevel: 10, reqJob: 1, STR: 2, tuc: 5, PDD: 10 },
    1032000: { reqLevel: 50, reqJob: 2, INT: 3, MAD: 2, tuc: 6 },
    1132000: { reqLevel: 120, reqJob: 1, STR: 4, tuc: 3, PVPDamage: 2, tradeBlock: 1 },
    1012076: { reqLevel: 30, only: 1 },          // info/only=1 的唯一件
};

// 商店的法弗纳要展示属性，所以按清单里实际上架的 id 补 mock 数值。
const 法弗纳IDs = JSON.parse(fs.readFileSync(
    path.join(ROOT, 'docs/migrations/seed-tower-rewards-manifest.json'), 'utf8')).fafnir;
法弗纳IDs.forEach((id) => {
    属性表[id] = { reqLevel: 160, reqJob: 1, PAD: 100, STR: 20, tuc: 8 };
});

function 造装备(id) {
    const 基础 = 属性表[id] || {};
    return {
        道具ID: id,
        数量: 1,
        升级次数: 基础.tuc || 0,
        随机化: false,                  // randomizeStats 是否被调用
        随机潜: [],
        getUpgradeSlots() { return this.升级次数; },
        setUpgradeSlots(v) { this.升级次数 = v; },
    };
}

const II = {
    getInstance: () => II,      // 脚本里是 Java.type(...).getInstance().getEquipStats(id)
    getEquipById: (id) => 造装备(id),
    // 真机里对 inc* 字段加了随机值；mock 只标记"被调用过"
    randomizeStats: (eq) => { eq.随机化 = true; return eq; },
    isPickupRestricted: (id) => !!(属性表[id] || {}).only,
    getEquipStats: (id) => {
        const m = 属性表[id] || {};
        const keys = Object.keys(m);
        return {
            entrySet: () => ({
                iterator: () => {
                    let i = 0;
                    return {
                        hasNext: () => i < keys.length,
                        next: () => {
                            const k = keys[i++];
                            return { getKey: () => k, getValue: () => m[k] };
                        },
                    };
                },
            }),
        };
    },
};

// Java.type 的分派表：脚本按类名取不同 mock
const ITEM_CONSTANTS = { isAccessory: (id) => id >= 1110000 && id < 1140000 };
const FIELD_LIMIT = {
    DROP_LIMIT: { check: (limit) => (limit & 0x400000) === 0x400000 },
};

// 服务端 org.gms.client.inventory.Item 的 3 参构造器（int, short, short）。
// 掉落非装备（抽奖卷之类）时脚本会 new 它，所以 mock 必须可被 new。
function 造Java() {
    function 道具类(id, 位置, 数量) {
        this.道具ID = id;
        this.位置 = 位置;
        this.数量 = 数量;
    }
    return {
        type: (名字) => {
            if (名字.indexOf('ItemConstants') >= 0) return ITEM_CONSTANTS;   // 必须先于 Item 判断
            if (名字.indexOf('ItemInformationProvider') >= 0) return II;
            if (名字.indexOf('FieldLimit') >= 0) return FIELD_LIMIT;
            if (名字 === 'org.gms.client.inventory.Item') return 道具类;
            return II;
        },
    };
}

function 加载(file, cm) {
    const src = fs.readFileSync(path.join(DIR, file), 'utf8');
    const sandbox = {
        cm,
        Java: 造Java(),
        Math, JSON, String, Number, Date, parseInt, isFinite, Array, Object, Boolean, Error,
        console,
    };
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(src, sandbox);
    return sandbox;
}

function 最后(s) { return s.登录[s.登录.length - 1]; }

// ================================================================ 大厅 NPC
console.log('=== 大厅 NPC 2540000.js ===');
const NPC_PATH = path.join(ROOT, 'gms-server/scripts/npc/2540000.js');
{
    const src = fs.readFileSync(NPC_PATH, 'utf8');
    const sandbox = {
        Java: { type: () => function () {} },
        Math, JSON, String, Number, Date, parseInt, isFinite, Array, Object, Boolean, Error, console,
    };
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(src, sandbox);
    检查(typeof sandbox.大厅菜单 === 'function', '脚本可加载并导出函数');

    // 大厅：菜单 + 5 个新选项各自的分支
    const 期望 = { 2: '起源之塔/玩法说明', 4: '起源之塔/积分商店', 5: '起源之塔/抽奖', 6: '起源之塔/奖池预览' };
    for (const sel of [2, 4, 5, 6]) {
        const { cm, 状态 } = 造环境({ 变量: { 起源积分: '1200', 起源累计积分: '2000' } });
        cm.getEventInstance = () => null;
        const s = { cm, ...(function () { return {}; })() };
        // 重新加载，把 mock cm 注入
        const src2 = fs.readFileSync(NPC_PATH, 'utf8');
        const box = {
            cm, Java: { type: () => function () {} },
            Math, JSON, String, Number, Date, parseInt, isFinite, Array, Object, Boolean, Error, console,
        };
        box.globalThis = box;
        vm.createContext(box);
        vm.runInContext(src2, box);
        box.start();
        检查(最后(状态).type === 'simple' && 最后(状态).text.indexOf('起源宝库') >= 0, `选 ${sel} 前先出大厅菜单`);
        检查(最后(状态).text.indexOf('起源积分：#r1200#k') >= 0, `菜单显示当前起源积分`);
        box.action(1, 0, sel);
        检查(状态.开NPC[0] === 期望[sel], `选 ${sel} → openNpc("${期望[sel]}")`);
        检查(状态.dispose次数 >= 1, `选 ${sel} 会结束本次对话`);
    }

    // 查看当前积分：必须先 sendOk 再 dispose，不能反过来
    {
        const { cm, 状态 } = 造环境({ 变量: { 起源积分: '88', 起源累计积分: '200' } });
        const box = {
            cm, Java: { type: () => function () {} },
            Math, JSON, String, Number, Date, parseInt, isFinite, Array, Object, Boolean, Error, console,
        };
        box.globalThis = box;
        vm.createContext(box);
        vm.runInContext(fs.readFileSync(NPC_PATH, 'utf8'), box);
        box.start();
        box.action(1, 0, 3);
        const 末 = 最后(状态);
        检查(末 && 末.type === 'ok' && 末.text.indexOf('88') >= 0 && 末.text.indexOf('200') >= 0,
            '选 3 → 弹出当前积分/累计积分');
        检查(状态.开NPC.length === 0, '选 3 不打开子脚本');
    }
}

// ================================================================ 玩法说明
console.log('=== 玩法说明.js ===');
{
    const { cm, 状态 } = 造环境();
    const box = 加载('玩法说明.js', cm);
    box.start();
    检查(最后(状态) && 最后(状态).type === 'ok', '说明用 sendOk 弹出');
    const t = 最后(状态).text;
    检查(t.indexOf('2 分') >= 0 && t.indexOf('40 分') >= 0, '说明里写了 2 分/层、40 分通关');
    检查(t.indexOf('累计') < 0, '说明文本无异常残留');
    检查(t.indexOf('主动退出') >= 0, '说明里写了主动退出不发积分');
    检查(t.indexOf('同一批连抽内') >= 0, '说明里写了同批不重复的抽奖规则');
    检查(状态.dispose次数 === 1, '说明后 dispose 一次');
}

// ================================================================ 积分商店
console.log('=== 积分商店.js ===');
{
    // 积分足够：1 抽 = 40 分
    const { cm, 状态 } = 造环境({ 变量: { 起源积分: '100' } });
    const box = 加载('积分商店.js', cm);
    box.start();
    let 菜单 = 最后(状态).text;
    检查(最后(状态).type === 'simple', '商店用 sendSimple');
    检查(菜单.indexOf('#L0#') >= 0 && 菜单.indexOf('4009930') >= 0, '菜单含 1 抽卷（图标+名称）');
    检查(菜单.indexOf('#L5#') >= 0, '法弗纳从第 6 项开始（5 个抽奖卷之后）');
    检查(菜单.indexOf('1299') >= 0, '菜单显示法弗纳 1299 分');
    检查(数图标(菜单, true) === 0, '商店菜单：图标全在 #L 之外（悬停说明才有效）');
    检查(数图标(菜单, false) === 21, `商店 5+16 个商品图标都在链接外（实际 ${数图标(菜单, false)}）`);
    检查(菜单.indexOf('\\t') < 0, '商店菜单不再用 \\t 对齐（对话框没有制表位）');

    box.action(1, 0, 0);                     // 选中 1 抽卷
    检查(最后(状态).type === 'number' && 最后(状态).max === 100, '1 抽卷可输入数量 1-100');
    检查(最后(状态).text.indexOf('等级要求') < 0, '抽奖卷不是装备，兑换页不加属性块');
    box.action(1, 0, 2);                     // 买 2 张
    检查(最后(状态).type === 'yesno' && 最后(状态).text.indexOf('80') >= 0, '确认框金额 = 40×2 = 80');
    box.action(1, 0, 0);                     // 确定
    检查(最后(状态).type === 'ok' && 最后(状态).text.indexOf('兑换成功') >= 0, '兑换成功提示');
    检查(状态.变量['起源积分'] === '20', '扣除 80 分，剩 20');
    const 卷明细 = 状态.买到.filter(([id]) => id === 4009930);
    检查(卷明细.length === 2 && 卷明细.every(([, q]) => q === 1),
        `发放 4009930 ×2（逐件发放，实得 ${卷明细.length} 件）`);
    检查(状态.掉落.length === 0, '背包有空间时全部进背包，不产生地面掉落');

    // 积分不足
    const b2 = 造环境({ 变量: { 起源积分: '10' } });
    const s2 = 加载('积分商店.js', b2.cm);
    s2.start(); s2.action(1, 0, 4);          // 20 连抽（760 分）
    s2.action(1, 0, 1);
    s2.action(1, 0, 0);
    检查(最后(b2.状态).text.indexOf('积分不足') >= 0, '积分不足时拒绝');
    检查(b2.状态.买到.length === 0, '积分不足不发放道具');
    检查(b2.状态.变量['起源积分'] === '10', '积分不足不扣分');

    // 背包满 → 不再拒绝整笔购买，放不下的部分掉在地上
    {
        const b3 = 造环境({ 变量: { 起源积分: '9999' }, 其他栏可容: 0 });
        const s3 = 加载('积分商店.js', b3.cm);
        s3.start();
        检查(最后(b3.状态).text.indexOf('放不下的部分会直接掉在你脚下') >= 0, '商店菜单写明放不下会掉地上');
        s3.action(1, 0, 1);                      // 5 连抽卷（160 分）
        s3.action(1, 0, 1);                      // 买 1 张
        const 确认 = 最后(b3.状态);
        检查(确认.type === 'yesno' && 确认.text.indexOf('背包空间不足') >= 0, '空间不足时确认框提前警告');
        s3.action(1, 0, 0);                      // 确定
        const r3 = 最后(b3.状态);
        检查(r3.text.indexOf('兑换成功') >= 0, '"背包满"也照常完成购买');
        检查(b3.状态.变量['起源积分'] === '9839', '积分照扣 160（整笔扣除）');
        检查(b3.状态.买到.length === 0, '放不下就不往背包里塞');
        检查(b3.状态.掉落.length === 1, `放不下的 1 张掉在地上（实际 ${b3.状态.掉落.length}）`);
        检查(r3.text.indexOf('背包放不下 #r1#k 个') >= 0, '结果框写明掉了几件');
        检查(r3.text.indexOf('未能发放') < 0, '大厅地图允许掉落，没有未发放');
    }

    // 背包只够 2 格 → 2 张进包、3 张掉地上（逐件判定）
    {
        const b = 造环境({ 变量: { 起源积分: '9999' }, 其他栏可容: 2 });
        const s = 加载('积分商店.js', b.cm);
        s.start(); s.action(1, 0, 1); s.action(1, 0, 5); s.action(1, 0, 0);
        const r = 最后(b.状态);
        const 进包 = b.状态.买到.filter(([id, q]) => id === 4009931 && q > 0);
        检查(进包.length === 2, `2 张进背包（实际 ${进包.length}）`);
        检查(b.状态.掉落.length === 3, `3 张掉地上（实际 ${b.状态.掉落.length}）`);
        检查(b.状态.掉落.every((d) => d.item.道具ID === 4009931 && d.item.数量 === 1),
            '掉落的是同一张抽奖卷，每件 1 张');
        检查(b.状态.掉落.every((d) => d.owner === b.玩家 && d.pos.x === 10), '掉落的归属与坐标正确');
        检查(b.状态.变量['起源积分'] === '9199', '5 张共扣 800 分（160×5）');
        检查(r.text.indexOf('获得 #i4009931#') >= 0, '结果框同时列出进包与落地');
    }

    // 买法弗纳（装备，装备栏 0 格）→ 掉在地上
    {
        const b = 造环境({ 变量: { 起源积分: '5000' }, 可容纳件数: 0, canHold: undefined });
        const s = 加载('积分商店.js', b.cm);
        s.start(); s.action(1, 0, 5);
        s.action(1, 0, 1); s.action(1, 0, 0);
        const r = 最后(b.状态);
        检查(b.状态.变量['起源积分'] === '3701', '法弗纳照扣 1299 分');
        检查(b.状态.买到.length === 0, '装备栏满时不往背包里塞');
        检查(b.状态.掉落.length === 1, '法弗纳掉在地上');
        检查(b.状态.掉落[0].item.道具ID > 1300000 && b.状态.掉落[0].item.道具ID < 1500000,
            '掉的是法弗纳武器');
        检查(b.状态.掉落[0].item.随机化 === false,
            '地上那件与 gainItem(id,qty) 同口径（商店不发随机潜能）');
        检查(b.状态.掉落[0].ffa === false, '常规掉落（15 秒内归自己）');
        检查(r.text.indexOf('兑换成功') >= 0, '交易照常完成');
    }

    // 地图禁止掉落（fieldLimit 带 DROP_LIMIT）→ 记为未发放
    {
        const b = 造环境({ 变量: { 起源积分: '9999' }, 其他栏可容: 0, fieldLimit: 0x400000 });
        const s = 加载('积分商店.js', b.cm);
        s.start(); s.action(1, 0, 1); s.action(1, 0, 1); s.action(1, 0, 0);
        检查(b.状态.掉落.length === 0, '禁止掉落的地图上不产生地面掉落');
        检查(最后(b.状态).text.indexOf('未能发放') >= 0, '禁掉落地图如实记为未发放');
        检查(b.状态.变量['起源积分'] === '9839', '仍然扣分（不做退款，积分按整笔算）');
    }

    // 买法弗纳（装备栏有空间，正常进背包，只买 1 件）
    const b4 = 造环境({ 变量: { 起源积分: '5000' } });
    const s4 = 加载('积分商店.js', b4.cm);
    s4.start(); s4.action(1, 0, 5);
    检查(最后(b4.状态).type === 'number' && 最后(b4.状态).max === 1, '法弗纳一次只能买 1 件');
    检查(最后(b4.状态).text.indexOf('等级要求：#r160#k') >= 0, '商店兑换页显示等级要求（共用装备属性块）');
    检查(最后(b4.状态).text.indexOf('物理攻击力 +#r100#k') >= 0, '商店兑换页显示装备加成（去 inc 前缀键）');
    s4.action(1, 0, 1); s4.action(1, 0, 0);
    检查(最后(b4.状态).text.indexOf('兑换成功') >= 0, '法弗纳兑换成功');
    检查(b4.状态.变量['起源积分'] === '3701', '法弗纳扣 1299 分');
    检查(b4.状态.买到[0][0] > 1300000 && b4.状态.买到[0][0] < 1500000, '发放的是法弗纳武器');
    检查(b4.状态.掉落.length === 0, '装备栏有空间时不产生地面掉落');
}

// ================================================================ 抽奖
console.log('=== 抽奖.js ===');
{
    const { cm, 状态 } = 造环境({ 物品: { 4009931: 1 }, 变量: {} });
    const box = 加载('抽奖.js', cm);
    box.start();
    检查(最后(状态).type === 'simple' && 最后(状态).text.indexOf('1153') >= 0, '抽奖菜单显示奖池 1153 件');
    检查(最后(状态).text.indexOf('4009931') >= 0 && 最后(状态).text.indexOf('持有 #r1#k') >= 0, '显示每张卷的持有数');
    检查(最后(状态).text.indexOf('同一批连抽内不会抽到重复的装备') >= 0, '菜单写明同批不重复');

    box.action(1, 0, 1);                       // 用 5 连抽卷
    检查(最后(状态).type === 'yesno' && 最后(状态).text.indexOf('5') >= 0, '确认框写明抽 5 次');
    检查(最后(状态).text.indexOf('本次 #r5#k 件互不重复') >= 0, '确认框写明本批互不重复');
    box.action(1, 0, 0);                       // 确定
    const 结果 = 最后(状态);
    检查(结果.type === 'ok' && 结果.text.indexOf('抽奖结果') >= 0, '弹出抽奖结果');
    检查(状态.物品[4009931] === 0, '消耗 1 张 5 连抽卷');
    const 抽到 = 状态.买到.filter(([id]) => id !== 4009931);
    检查(抽到.length === 5, `实际发放 5 件（实得 ${抽到.length}）`);
    const 合法 = 抽到.every(([id, q]) => q === 1 && id >= 1010000 && id <= 1139999);
    检查(合法, '抽到的都是 101/103/112/113 段的装备');

    // 没有卷
    const b2 = 造环境({ 物品: { 4009933: 0 } });
    const s2 = 加载('抽奖.js', b2.cm);
    s2.start(); s2.action(1, 0, 3); s2.action(1, 0, 0);
    检查(最后(b2.状态).text.indexOf('没有这张抽奖卷') >= 0, '没卷时拒绝并提示去商店');
    检查(b2.状态.买到.length === 0, '没卷时不做任何发放');

    // 背包满 → 奖品掉在地上（不再拒绝），抽奖卷照常消耗
    {
        const b = 造环境({ 物品: { 4009934: 1 }, 可容纳件数: 0 });
        const s = 加载('抽奖.js', b.cm);
        s.start(); s.action(1, 0, 4);            // 选 50 连抽
        检查(最后(b.状态).type === 'yesno' && 最后(b.状态).text.indexOf('直接掉在你脚下') >= 0,
            '装备栏满时确认框提前警告会掉地上');
        s.action(1, 0, 0);                      // 确定
        const r = 最后(b.状态);
        检查(b.状态.物品[4009934] === 0, '即使背包满是，抽奖卷照样消耗');
        检查(b.状态.买到.filter(([id]) => id !== 4009934).length === 0, '背包满时不往背包里塞');
        检查(b.状态.掉落.length === 50, `50 件全部掉在地上（实际 ${b.状态.掉落.length}）`);
        检查(b.状态.掉落.every((d) => d.ffa === false), '按常规掉落参数 ffa=false（15 秒后谁都能捡）');
        检查(b.状态.掉落.every((d) => d.owner === b.玩家), '掉落 owner 是玩家本人');
        检查(b.状态.掉落.every((d) => d.pos && d.pos.x === 10 && d.pos.y === 20),
            '掉落位置 = 玩家当前位置');
        检查(b.状态.掉落.every((d) => d.item && d.item.道具ID >= 1010000 && d.item.道具ID <= 1139999),
            '掉落的都是奖池里的装备');
        检查(b.状态.掉落.every((d) => d.item.随机化 === true), '掉地上的装备同样做了随机潜能');
        检查(r.type === 'ok' && r.text.indexOf('已掉在你脚下') >= 0, '结果框说明奖品掉在地上');
        检查(r.text.indexOf('共获得 #r50#k 件装备') >= 0, `结果框件数正确（${r.text.match(/共获得[^。]*/)}）`);
        检查(r.text.indexOf('未发放') < 0, '这一轮没有未发放');
    }

    // 只够 2 格 → 2 件进背包、3 件掉地上（逐件判定，不是一刀切）
    {
        const b = 造环境({ 物品: { 4009931: 1 }, 可容纳件数: 2 });
        const s = 加载('抽奖.js', b.cm);
        s.start(); s.action(1, 0, 1); s.action(1, 0, 0);
        const r = 最后(b.状态);
        检查(b.状态.买到.filter(([id]) => id !== 4009931).length === 2,
            `2 件进背包（实际 ${b.状态.买到.filter(([id]) => id !== 4009931).length}）`);
        检查(b.状态.掉落.length === 3, `3 件掉地上（实际 ${b.状态.掉落.length}）`);
        检查(r.text.indexOf('共获得 #r5#k 件装备') >= 0, '进包 + 落地都计入"共获得"');
        检查(r.text.indexOf('其中 #r3#k 件') >= 0, '结果框写明 3 件掉在脚下');
    }

    // 地图禁止掉落（fieldLimit 带 DROP_LIMIT）→ 只能记为未发放，不能凭空消失
    {
        const b = 造环境({ 物品: { 4009930: 1 }, 可容纳件数: 0, fieldLimit: 0x400000 });
        const s = 加载('抽奖.js', b.cm);
        s.start(); s.action(1, 0, 0); s.action(1, 0, 0);
        检查(b.状态.掉落.length === 0, '禁止掉落的地图上不产生地面掉落');
        检查(最后(b.状态).text.indexOf('未能发放') >= 0, '禁掉落地图把奖品记为未发放');
        检查(b.状态.物品[4009930] === 0, '禁掉落地图仍然消耗抽奖卷（已抽出但发不出）');
    }

    // 唯一件（info/only=1）已拥有 → 建候选池时就剔掉，不占本批名额
    {
        const b = 造环境({ 拥有: [1012076] });
        const s = 加载('抽奖.js', b.cm);
        const 池1 = s.候选池(b.玩家);
        检查(池1.indexOf(1012076) < 0, '已拥有的唯一件不进候选池');
        检查(池1.length === 1152, `候选池剔掉那 1 件后剩 1152（实际 ${池1.length}）`);

        const b2 = 造环境({});
        const s2 = 加载('抽奖.js', b2.cm);
        const 池2 = s2.候选池(b2.玩家);
        检查(池2.length === 1153 && 池2.indexOf(1012076) >= 0, '未拥有时唯一件正常留在候选池');
        检查(s2.抽一件([1012076]) === 1012076, '未拥有时同一件正常抽到');
    }

    // 抽一件 的语义：取走一件、候选池少一件，取完返回 null
    {
        const s = 加载('抽奖.js', 造环境({}).cm);
        const 小池 = [11, 22, 33];
        const 出 = [s.抽一件(小池), s.抽一件(小池), s.抽一件(小池)];
        检查(小池.length === 0, '抽一件 会把取走的元素移出候选池');
        检查(new Set(出).size === 3, `3 次抽完 3 件互不相同（${出.join(',')}）`);
        检查(s.抽一件(小池) === null, '候选池抽干后返回 null（唯一会返回 null 的情况）');
    }

    // ★ 核心口径：同一批连抽内不重复
    {
        const b = 造环境({ 物品: { 4009934: 1 } });
        const s = 加载('抽奖.js', b.cm);
        s.start(); s.action(1, 0, 4); s.action(1, 0, 0);        // 50 连抽
        const 抽到 = b.状态.买到.filter(([id]) => id !== 4009934).map(([id]) => id);
        检查(抽到.length === 50, `50 连抽发放 50 件（实际 ${抽到.length}）`);
        检查(new Set(抽到).size === 50, `50 件互不重复（去重后 ${new Set(抽到).size} 件）`);
        检查(最后(b.状态).text.indexOf('×') < 0, '结果面板不再出现「×N」这种重复标记');
        检查(最后(b.状态).text.indexOf('共获得 #r50#k 件装备') >= 0, '结果框件数正确');
    }

    // 背包满 → 全部掉地上，那 50 件同样不重复
    {
        const b = 造环境({ 物品: { 4009934: 1 }, 可容纳件数: 0 });
        const s = 加载('抽奖.js', b.cm);
        s.start(); s.action(1, 0, 4); s.action(1, 0, 0);
        const 落地 = b.状态.掉落.map((d) => d.item.道具ID);
        检查(落地.length === 50, `50 件全落地（实际 ${落地.length}）`);
        检查(new Set(落地).size === 50, `掉在地上的 50 件也互不重复（去重后 ${new Set(落地).size}）`);
    }

    // 候选池必须是副本：连抽两批，第二批的池子不能被第一批掏空
    {
        const b = 造环境({ 物品: { 4009933: 2 } });
        const s = 加载('抽奖.js', b.cm);
        s.start(); s.action(1, 0, 3); s.action(1, 0, 0);        // 第一批 20 连
        s.start(); s.action(1, 0, 3); s.action(1, 0, 0);        // 第二批 20 连
        const 抽到 = b.状态.买到.filter(([id]) => id !== 4009933).map(([id]) => id);
        检查(抽到.length === 40, `两批合计 40 件（实际 ${抽到.length}）`);
        const 一批 = 抽到.slice(0, 20), 二批 = 抽到.slice(20);
        检查(new Set(一批).size === 20, '第一批内部不重复');
        检查(new Set(二批).size === 20, '第二批内部不重复（池子没被第一批抽空）');
        检查(s.奖池().length === 1153, `抽过两批后奖池源仍是 1153 件（实际 ${s.奖池().length}）`);
    }

    // 单抽也能出结果
    const b4 = 造环境({ 物品: { 4009930: 1 } });
    const s4 = 加载('抽奖.js', b4.cm);
    s4.start(); s4.action(1, 0, 0); s4.action(1, 0, 0);
    const 唯一 = new Set(b4.状态.买到.filter(([id]) => id !== 4009930).map(([id]) => id));
    检查(唯一.size === 1, `单抽能出结果（${[...唯一][0]}）`);
}

// ================================================================ 掉落实现共用
console.log('=== 抽奖.js / 积分商店.js 共用同一份掉落实现 ===');
{
    const 取块 = (f) => {
        const t = fs.readFileSync(path.join(DIR, f), 'utf8');
        const B = '// BEGIN 掉落兜底', E = '// END 掉落兜底';
        if (t.split(B).length !== 2 || t.split(E).length !== 2) throw new Error(`${f}: 标记块必须各一次`);
        return t.split(B)[1].split(E)[0];
    };
    const 抽奖块 = 取块('抽奖.js');
    const 商店块 = 取块('积分商店.js');
    检查(抽奖块 === 商店块, '两份「掉落兜底」块逐字节相同（防止口径漂移）');
    检查(抽奖块.indexOf('掉落_发一个') >= 0 && 抽奖块.indexOf('spawnItemDrop') >= 0,
        '掉落块提供统一的 掉落_发一个()');
    检查(抽奖块.indexOf('DROP_LIMIT') >= 0, '掉落块自带"该地图禁止掉落"自查');
    检查(抽奖块.indexOf('getEquipById') >= 0 && 抽奖块.indexOf('randomizeStats') >= 0,
        '掉落块的装备构造口径与 gainItem 一致');
    检查(抽奖块.indexOf('isAccessory') >= 0 && 抽奖块.indexOf('setUpgradeSlots(3)') >= 0,
        '掉落块给饰品补 3 次升级（对齐 AbstractPlayerInteraction:648）');
}

// ================================================================ 奖池预览
console.log('=== 奖池预览.js ===');
{
    const { cm, 状态 } = 造环境();
    const box = 加载('奖池预览.js', cm);
    box.start();
    let 菜单 = 最后(状态).text;
    检查(最后(状态).type === 'simple', '分类菜单用 sendSimple');
    检查(['脸饰', '耳环', '项环', '腰带'].every((c) => 菜单.indexOf(c) >= 0), '四个分类都在');
    检查(菜单.indexOf('1153') >= 0, '显示奖池总数 1153');
    检查(数图标(菜单, true) === 0, '分类菜单：没有图标被写进链接内');

    box.action(1, 0, 0);                       // 进「脸饰」
    let 列表 = 最后(状态).text;
    检查(列表.indexOf('第 1/29 页') >= 0,
        `脸饰 566 件、每页 20 件 → 29 页（实际 "${(列表.match(/第 \d+\/\d+ 页/) || [''])[0]}"）`);
    检查(列表.indexOf('#v1010000# #L0#') >= 0, '第 1 行是「图标(链接外) + 名称(链接内)」');
    检查(数图标(列表, true) === 0, '本页没有任何图标落在链接内部（悬停说明才弹得出来）');
    检查(数图标(列表, false) === 20, `本页 20 个图标全在链接之外（实际 ${数图标(列表, false)}）`);
    检查((列表.match(/#t\d+#/g) || []).length === 20, '每件都带上了装备名称 #t');
    检查(列表.split('\r\n').filter((l) => l.indexOf('#v') >= 0).length === 20, '一行一件，不再挤成网格');
    检查(列表.indexOf('#L900002#') >= 0 && 列表.indexOf('【下一页】') >= 0, '有下一页按钮');
    检查(列表.indexOf('#L900001#') < 0, '第一页没有上一页按钮');

    box.action(1, 0, 900002);                  // 下一页
    检查(最后(状态).text.indexOf('第 2/29 页') >= 0, '翻到第 2 页');
    box.action(1, 0, 900001);                  // 上一页
    检查(最后(状态).text.indexOf('第 1/29 页') >= 0, '退回第 1 页');
    box.action(1, 0, 900003);                  // 返回分类
    检查(最后(状态).text.indexOf('请选择要查看的分类') >= 0, '返回分类菜单');

    box.action(1, 0, 3);                       // 进「腰带」（160 件 → 8 页）
    检查(最后(状态).text.indexOf('第 1/8 页') >= 0, '腰带 160 件共 8 页');

    box.action(1, 0, 0);                       // 点第 1 件看详情
    const 详情 = 最后(状态);
    检查(详情.type === 'ok', '点名称弹出装备详情');
    检查(详情.text.indexOf('#t1132000#') >= 0, '详情标题是装备名');
    检查(详情.text.indexOf('部位：#b腰带#k') >= 0, '详情显示部位');
    检查(详情.text.indexOf('#e需求#n') >= 0 && 详情.text.indexOf('#e基础属性#n') >= 0, '详情有需求/基础属性两段');
    检查(详情.text.indexOf('等级要求：#r120#k') >= 0, '详情渲染出等级要求');
    检查(详情.text.indexOf('职业要求：#r战士#k') >= 0, 'reqJob 位掩码解析成职业名');
    检查(详情.text.indexOf('力量 +#r4#k') >= 0, '详情渲染出加成属性（去 inc 前缀键）');
    检查(详情.text.indexOf('可升级次数 +#r3#k') >= 0, '详情渲染出可升级次数');
    检查(详情.text.indexOf('PVP伤害 +#r2#k') >= 0, '详情渲染出 PVP伤害（新增字段）');
    检查(详情.text.indexOf('（不可交易）') >= 0, '详情渲染出不可交易标记');
    检查(详情.text.indexOf('读取失败') < 0, '属性读取正常（没有走读取失败兜底）');

    // 属性键名契约：服务端把 incXXX 去前缀后入表，脚本里绝不能写 inc 开头
    {
        const 脚本键 = [...box.装备_需求项, ...box.装备_加成项].map(([k]) => k);
        const 带inc = 脚本键.filter((k) => k.indexOf('inc') === 0);
        检查(带inc.length === 0, `脚本没有误用 inc 前缀键（越界 ${JSON.stringify(带inc)}）`);
        const 未知 = 脚本键.filter((k) => !服务端键集.has(k));
        检查(未知.length === 0, `奖池预览用的属性键都在服务端契约内（未知 ${JSON.stringify(未知)}）`);
        检查(box.文本_宽度('物理攻击力') === 10, '宽度工具：中文按 2 格算（5 字 = 10）');
        检查(box.文本_补左('40 分', 8) === '   40 分', '宽度工具：短价格左补空格');
        检查(box.文本_补左('1299 分', 8) === ' 1299 分', '宽度工具：长价格左补空格');
    }

    // 详情页里再点一下 = 确认，回到原页列表（页面=详情 时任意 action 都回列表）
    box.action(1, 0, 0);
    检查(最后(状态).type === 'simple' && 最后(状态).text.indexOf('第 1/8 页') >= 0, '详情确认后回到原页');

    // 无属性装备不能出现空页面（腰带第 2 件，mock 里没给数据）
    box.action(1, 0, 1);
    检查(最后(状态).type === 'ok' && 最后(状态).text.indexOf('无等级/属性要求') >= 0, '无需求时给兜底文案');
    检查(最后(状态).text.indexOf('无附加属性') >= 0, '无加成时给兜底文案');
}

console.log();
if (失败.length) {
    console.log(`存在 ${失败.length} 项失败：`);
    失败.forEach((f) => console.log('  -', f));
    process.exit(1);
}
console.log('全部流程验证通过');
