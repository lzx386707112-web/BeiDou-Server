/* ==================
 脚本类型: 万能传送   
 脚本作者：汉堡  
 联系方式：北斗项目组
 =====================
 */
//------------------------------------------------------------------------
var bossmaps2 = Array(
    Array(211042300, 380000, "扎昆                               #r（消耗38万金币）#b"),
    Array(240040700, 380000, "暗黑龙王                       #r（消耗38万金币）#b"),
    Array(270050000, 2000000, "时间的宠儿品克缤       #r（消耗200万金币）#b"),
    Array(271030000, 380000, "骑士团要塞入口            #r（消耗38万金币）#b"),
    Array(271040000, 380000, "希纳斯远征入口            #r（消耗38万金币）#b"),
//    Array(272020110, 500000, "阿卡伊勒祭坛入口        #r（消耗50万金币）#b"),
    Array(272030300, 500000, "阿卡伊勒远征入口        #r（消耗50万金币）#b"),
//    Array(262030300, 500000, "希拉                               #r（消耗50万金币）#b", 8870000, -1, 1092, 196),
//    Array(262031300, 500000, "白发希拉                       #r（消耗50万金币）#b", 8870200, -1, 1092, 196),
//    Array(450010100, 500000, "觉醒希拉                       #r（消耗50万金币）#b", 8880400, -1, 855, 266),
//    Array(221040001, 500000, "卡翁                               #r（消耗50万金币）#b", 8880200, -1, -1215, 866),
//    Array(450009400, 500000, "亲卫队长敦凯尔            #r（消耗50万金币）#b", 8645009, -1, -1, -157),
//    Array(900000207, 500000, "守护天使绿水灵            #r（消耗50万金币）#b", 8880700, -1, 703, -1394),
//    Array(410002060, 500000, "监视者卡洛斯                #r（消耗50万金币）#b", 8880803, -1, 900, 325),
    Array(105100100, 100000, "蝙蝠怪巴洛古                #r（消耗10万金币）#b"),
    Array(220080000, 280000, "闹钟                               #r（消耗28万金币）#b"),
    Array(541020700, 380000, "大树BOSS                     #r（消耗38万金币）#b"),
    Array(551030100, 380000, "心疤狮王和暴力熊        #r（消耗38万金币）#b"),
    Array(501030104, 380000, "泰国六手邪神                #r（消耗38万金币）#b"),
    Array(702070400, 380000, "藏经阁武陵妖僧            #r（消耗38万金币）#b"),
    Array(802000210, 380000, "贝尔加莫特                    #r（消耗38万金币）#b"),
    Array(802000500, 380000, "都纳斯                            #r（消耗38万金币）#b"),
    Array(802000602, 380000, "尼贝隆                            #r（消耗38万金币）#b"),
    Array(802000110, 380000, "努克斯                            #r（消耗38万金币）#b"),
    Array(802000700, 380000, "再生都纳斯                    #r（消耗38万金币）#b"),
    Array(802000800, 380000, "欧碧拉                            #r（消耗38万金币）#b"),
    Array(211070100, 500000, "班·雷昂                            #r（消耗50万金币，每日3次）#b"),
    Array(703011000, 500000, "钻机                  #r（消耗50万金币，每日3次）#b"),
);

var DAILY_BOSS_LIMIT = 300;
var DAILY_BOSS_BY_MAP = {
    211070100: { countKey: "BOSS每日_班雷昂", name: "班·雷昂" },
    703011000: { countKey: "BOSS每日_钻机", name: "钻机" }
};
var SHENSHUO_BOSS_ENTRY_ITEMS = Array(
    Array(4000019, 500),
    Array(2210006, 1)
);
var SHENSHUO_BOSS_MAPS = {
    262030300: true,
    262031300: true,
    450010100: true,
    221040001: true,
    450009400: true,
    900000207: true,
    410002060: true
};
//------------------------------------------------------------------------
var bossmaps1 = Array(
    Array(104000400, 100000, "红蜗牛王                        #r（消耗10万金币）#b"),
    Array(677000003, 100000, "黑暗独角兽                    #r（消耗10万金币）#b"),
    Array(677000005, 100000, "印第安老斑鸠                #r（消耗10万金币）#b"),
    Array(677000009, 100000, "沃勒福                            #r（消耗10万金币）#b"),
    Array(677000001, 100000, "牛魔王 I                         #r（消耗10万金币）#b"),
    Array(677000007, 100000, "雪之猫女                        #r（消耗10万金币）#b"),
    Array(677000012, 100000, "牛魔王 II                       #r（消耗10万金币）#b"),
    Array(101030404, 100000, "树妖王                            #r（消耗10万金币）#b"),
    Array(107000300, 100000, "鳄鱼多尔                        #r（消耗10万金币）#b"),
    Array(100040105, 100000, "浮士德 I                         #r（消耗10万金币）#b"),
    Array(100040106, 100000, "浮士德                            #r（消耗10万金币）#b"),
    Array(110040000, 100000, "巨居蟹                            #r（消耗10万金币）#b"),
    Array(103040400, 100000, "摇滚之魂                        #r（消耗10万金币）#b"),
    Array(105090310, 100000, "黑轮王                            #r（消耗10万金币）#b"),
    Array(100000005, 100000, "蘑菇王                            #r（消耗10万金币）#b"),
    Array(105070002, 100000, "僵尸蘑菇王                    #r（消耗10万金币）#b"),
    Array(800010100, 100000, "蓝蘑菇王                        #r（消耗10万金币）#b"),
    Array(230020100, 100000, "贝壳歇尔夫                    #r（消耗10万金币）#b"),
    Array(220050000, 100000, "闹钟提莫 I                     #r（消耗10万金币）#b"),
    Array(220050100, 100000, "闹钟提莫                        #r（消耗10万金币）#b"),
    Array(220050200, 100000, "闹钟提莫 III                  #r（消耗10万金币）#b"),
    Array(221020701, 100000, "战甲吹泡泡鱼                #r（消耗10万金币）#b"),
    Array(260010201, 100000, "仙人掌大宇                    #r（消耗10万金币）#b"),
    Array(250010304, 100000, "肯德熊                            #r（消耗10万金币）#b"),
    Array(250010504, 100000, "妖怪禅师                        #r（消耗10万金币）#b"),
    Array(222010310, 100000, "九尾狐                            #r（消耗10万金币）#b"),
    Array(200010300, 100000, "艾利杰                            #r（消耗10万金币）#b"),
    Array(211040101, 100000, "驼狼雪人                        #r（消耗10万金币）#b"),
    Array(261030000, 100000, "吉米拉                            #r（消耗10万金币）#b"),
    Array(251010102, 100000, "蜈蚣王2                          #r（消耗10万金币）#b"),
    Array(221040301, 100000, "外星人朱诺                    #r（消耗10万金币）#b"),
    Array(800020120, 100000, "青竹武士                        #r（消耗10万金币）#b"),
    Array(221030601, 100000, "外星章鱼闪电棒            #r（消耗10万金币）#b"),
    Array(801040004, 380000, "大头老板                        #r（消耗38万金币）#b"),
    Array(105090900, 100000, "蝙蝠怪                            #r（消耗10万金币）#b"),
    Array(240020401, 180000, "喷火龙                           #r（消耗18万金币）#b"),
    Array(240020101, 180000, "格瑞芬多                       #r（消耗18万金币）#b"),
    Array(240040401, 180000, "大海兽                           #r（消耗18万金币）#b"),
    Array(270010500, 380000, "时间神殿多多               #r（消耗38万金币）#b"),
    Array(270020500, 380000, "时间神殿玄冰独角兽   #r（消耗38万金币）#b"),
    Array(270030500, 380000, "时间神殿雷卡               #r（消耗38万金币）#b"),
    Array(610010013, 280000, "大脚和无头骑士           #r（消耗28万金币）#b"),  //580
    Array(801040003, 500000, "御姐BOSS                     #r（消耗50万金币）#b"), //780
    Array(230040420, 380000, "鱼王                               #r（消耗38万金币）#b"), //180 260=440
    Array(800020130, 380000, "天狗                                #r（消耗38万金币）#b"),//350万经验

    Array(800040208, 380000, "甲胄武士                        #r（消耗38万金币）#b"),
    Array(800040401, 1000000, "枫城天皇蟾蜍                #r（消耗100万金币）#b"),
);

//------------------------------------------------------------------------

var monstermaps = Array(
    Array(104040000, 5000, "射手训练场#r（5000金币）#b　　 　适合 1 ~ 15 级玩家"),
    Array(101010100, 5800, "大木林#r（5800金币）#b 　　　   　 适合 8 ~ 15 级玩家"),
    Array(682010201, 5800, "玩具工作室1#r（5800金币）#b　　   适合 15 ~ 25 级玩家"),
    Array(103000101, 6800, "地铁<第1地区>#r（6800金币）#b　  适合 20 ~ 25 级玩家"),
    Array(220010500, 7800, "露台大厅#r（7800金币）#b                 适合 25 ~ 30 级玩家"),
    Array(101030001, 8800, "野猪的领土Ⅱ#r（8800金币）#b　 　适合 25 ~ 35 级玩家"),
    Array(106000002, 8800, "危险的峡谷Ⅱ#r（8800金币）#b　 　适合 30 ~ 40 级玩家"),
    Array(106000130, 8800, "火焰之地4#r（8800金币）#b　  　     适合 35 ~ 40 级玩家"),
    Array(200050000, 9800, "云彩公园4#r（9800金币）#b　  　     适合 35 ~ 45 级玩家"),
    Array(103000103, 9800, "地铁<第2地区>#r（9800金币）#b　  适合 35 ~ 45 级玩家"),
    Array(100040103, 9800, "猴子森林Ⅱ#r（9800金币）#b 　　    适合 35 ~ 50 级玩家"),
    Array(103000105, 9800, "地铁<第4地区>#r（9800金币）#b　  适合 40 ~ 50 级玩家"),
    Array(682010202, 10800, "玩具工作室2#r（10800金币）#b　　适合 40 ~ 55 级玩家"),
    Array(550000200, 10800, "泥泞的河岸1#r（10800金币）#b　　适合 45 ~ 55 级玩家"),
    Array(220040000, 11800, "时间之路1#r（11800金币）#b　   　 适合 45 ~ 60 级玩家"),
    Array(105040306, 12800, "巨人之林#r（12800金币）#b　　 　 适合 50 ~ 65 级玩家"),
    Array(250020000, 12800, "初级修炼场#r（12800金币）#b　　  适合 45 ~ 55 级玩家"),
    Array(251010200, 12800, "百年草药地#r（12800金币）#b　　  适合 50 ~ 60 级玩家"),
    Array(211041400, 12800, "死亡之林4#r（12800金币）#b　　    适合 50 ~ 60 级玩家"),
    Array(101030110, 12800, "第1军营#r（12800金币）#b　　 　   适合 50 ~ 65 级玩家"),
    Array(105090300, 12800, "龙穴#r（12800金币）#b　　 　     　适合 50 ~ 65 级玩家"),
    Array(500020400, 12800, "深丛林#r（12800金币）#b 　　 　    适合 50 ~ 65 级玩家"),
    Array(250010301, 22800, "野生熊的地盘#r（22800金币）#b 　 适合 55 ~ 75 级玩家"),
    Array(250010501, 22800, "迷雾森林#r（22800金币）#b　　 　 适合 55 ~ 75 级玩家"),
    Array(261020500, 25800, "研究所C3#r（22800金币）#b　　　 适合 55 ~ 75 级玩家"),
    Array(541010010, 25800, "幽灵船2#r（25800金币）#b　　　    适合 55 ~ 75 级玩家"),
    Array(251010402, 23800, "海盗团老巢2#r（23800金币）#b　　适合 60 ~ 75 级玩家"),
    Array(682010203, 25800, "玩具工作室3#r（25800金币）#b　　适合 60 ~ 80 级玩家"),
    Array(600020300, 26800, "机械蜘蛛洞穴#r（26800金币）#b　   适合 80 ~ 90 级玩家"),
    Array(800040206, 26800, "枫城上忍#r（26800金币）#b　　　   适合 80 ~ 90 级玩家"),
    Array(240010500, 27800, "山羊峡谷#r（27800金币）#b　　  　 适合 85 ~ 100 级玩家"),
    Array(230040100, 28800, "深海峡谷2#r（28800金币）#b　　 　适合 90 ~ 100 级玩家"),
    Array(220060201, 28800, "怪异的时间#r（28800金币）#b　　   适合 80 ~ 100 级玩家"),
    Array(220070201, 28800, "消失的时间#r（28800金币）#b　　   适合 90 ~ 100 级玩家"),
    Array(551030100, 29800, "阴森世界入口#r（29800金币）#b　   适合 95 ~ 120 级玩家"),
    Array(800020130, 29800, "大佛的邂逅#r（29800金币）#b　　   适合 95 ~ 120 级玩家"),
    Array(800040207, 32800, "枫城忍者头头#r（32800金币）#b　   适合 100 ~ 130 级玩家"),
    Array(240040510, 32800, "死龙巢穴#r（32800金币）#b　  　 　适合 105 ~ 130 级玩家"),
    Array(240040520, 32800, "遭破坏的龙之巢穴#r（32800金币）#b 适合 105 ~ 130 级玩家"),
    Array(541020200, 35800, "乌鲁庄园2#r（35800金币）#b             适合 100 ~ 140 级玩家"),
    Array(541020500, 35800, "乌鲁城中心#r（35800金币）#b           适合 105 ~ 150 级玩家"),
    Array(541020610, 35800, "毁灭的公园2#r（35800金币）#b           适合 105 ~ 150 级玩家"),
    Array(541020620, 35800, "毁灭的公园3#r（35800金币）#b           适合 105 ~ 150 级玩家"),
    Array(270030400, 35800, "忘却之路4#r（35800金币）#b             适合 120 ~ 150 级玩家")
);

//------------------------------------------------------------------------		

//------------------------------------------------------------------------

var townmaps = Array(
    Array(910000000, 0, "自由市场#r              （消耗0金币）#b"),
    Array(680100000, 500, "冒险岛周末集市#r  （消耗5百金币）#b"),
    Array(271000000, 10000, "未来之门#r              （消耗1万金币）#b"),
    Array(271030000, 10000, "骑士团要塞入口#r  （消耗1万金币）#b"),
//    Array(1006000, 10000, "遗忘山谷#r              （消耗1万金币）#b"),
    Array(105200000, 10000, "鲁塔比斯入口#r      （消耗1万金币）#b"),
//    Array(105200100, 10000, "鲁塔比斯东部庭院#r（消耗1万金币）#b"),
//    Array(105200200, 10000, "鲁塔比斯西部庭院#r（消耗1万金币）#b"),
//    Array(105200300, 10000, "鲁塔比斯南部庭院#r（消耗1万金币）#b"),
//    Array(105200400, 10000, "鲁塔比斯北部庭院#r（消耗1万金币）#b"),
//    Array(105200500, 10000, "鲁塔比斯东部庭院<进阶>#r（消耗1万金币）#b"),
//    Array(105200600, 10000, "鲁塔比斯西部庭院<进阶>#r（消耗1万金币）#b"),
//    Array(105200700, 10000, "鲁塔比斯南部庭院<进阶>#r（消耗1万金币）#b"),
//    Array(105200800, 10000, "鲁塔比斯北部庭院<进阶>#r（消耗1万金币）#b"),
//    Array(105200110, 10000, "鲁塔比斯半半房间<普通>#r（消耗1万金币）#b"),
//    Array(105200120, 10000, "鲁塔比斯半半内在世界#r（消耗1万金币）#b"),
//    Array(105200210, 10000, "鲁塔比斯皮埃尔房间<普通>#r（消耗1万金币）#b"),
//    Array(105200310, 10000, "鲁塔比斯血腥女王房间<普通>#r（消耗1万金币）#b"),
//    Array(105200410, 10000, "鲁塔比斯贝伦房间<普通>#r（消耗1万金币）#b"),
//    Array(105200510, 10000, "鲁塔比斯半半房间<进阶>#r（消耗1万金币）#b"),
//    Array(105200520, 10000, "鲁塔比斯半半内在世界<进阶>#r（消耗1万金币）#b"),
//    Array(105200610, 10000, "鲁塔比斯皮埃尔房间<进阶>#r（消耗1万金币）#b"),
//    Array(105200710, 10000, "鲁塔比斯血腥女王房间<进阶>#r（消耗1万金币）#b"),
//    Array(105200810, 10000, "鲁塔比斯贝伦房间<进阶>#r（消耗1万金币）#b"),
//    Array(105200900, 10000, "鲁塔比斯全光洞#r（消耗1万金币）#b"),
//    Array(105200901, 10000, "鲁塔比斯贝伦洞穴通道1#r（消耗1万金币）#b"),
//    Array(105200902, 10000, "鲁塔比斯贝伦洞穴通道2#r（消耗1万金币）#b"),
//    Array(105200903, 10000, "鲁塔比斯贝伦洞穴通道3#r（消耗1万金币）#b"),
//    Array(105200904, 10000, "鲁塔比斯贝伦洞穴通道4#r（消耗1万金币）#b"),
//    Array(105200905, 10000, "鲁塔比斯贝伦洞穴通道5#r（消耗1万金币）#b"),
//    Array(105200906, 10000, "鲁塔比斯贝伦洞穴通道6#r（消耗1万金币）#b"),
//    Array(105200907, 10000, "鲁塔比斯贝伦洞穴通道7#r（消耗1万金币）#b"),
//    Array(105200908, 10000, "鲁塔比斯贝伦洞穴通道8#r（消耗1万金币）#b"),
//    Array(105200909, 10000, "鲁塔比斯贝伦洞穴通道9#r（消耗1万金币）#b"),
//    Array(105201000, 10000, "鲁塔比斯贝伦洞穴1#r（消耗1万金币）#b"),
//    Array(105201100, 10000, "鲁塔比斯贝伦洞穴2#r（消耗1万金币）#b"),
//    Array(105201200, 10000, "鲁塔比斯贝伦洞穴3#r（消耗1万金币）#b"),
//    Array(105201300, 10000, "鲁塔比斯贝伦洞穴4#r（消耗1万金币）#b"),
    Array(272000000, 10000, "时间裂缝#r              （消耗1万金币）#b"),
    Array(272020000, 10000, "扭曲时间神殿1#r    （消耗1万金币）#b"),
    Array(272020110, 10000, "阿卡伊勒祭坛前#r  （消耗1万金币）#b"),
    Array(272030000, 10000, "次元的缝隙#r          （消耗1万金币）#b"),
    Array(1000000, 0, "彩虹岛新手村#r      （消耗0金币）#b"),
    Array(104000000, 500, "明珠港#r                  （消耗5百金币）#b"),
    Array(100000000, 800, "射手村#r                  （消耗8百金币）#b"),
    Array(101000000, 800, "魔法密林#r              （消耗8百金币）#b"),
    Array(102000000, 800, "勇士部落#r              （消耗8百金币）#b"),
    Array(103000000, 800, "废弃都市#r              （消耗8百金币）#b"),
    Array(120000000, 800, "诺特勒斯码头#r      （消耗8百金币）#b"),
    Array(105040300, 1000, "林中之城#r              （消耗1千金币）#b"),
    Array(106020000, 1000, "蘑菇城#r                  （消耗1千金币）#b"),
    Array(103040000, 1000, "废都广场#r              （消耗1千金币）#b"),
    Array(209000000, 1000, "圣诞节幸福村#r      （消耗1千金币）#b"),
    Array(680000000, 1000, "婚礼村#r                  （消耗1千金币）#b"),
    Array(140000000, 1000, "里恩#r                      （消耗1千金币）#b"),
    Array(130000000, 1000, "圣地#r                      （消耗1千金币）#b"),
    Array(110000000, 1000, "黄金海岸#r              （消耗1千金币）#b"),
    Array(600000000, 2000, "新叶城#r                  （消耗2千金币）#b"),
    Array(682000000, 5000, "闹鬼宅邸外部#r      （消耗5千金币）#b"),
    Array(540010000, 5000, "新加坡机场#r          （消耗5千金币）#b"),
    Array(541000000, 5000, "新加坡码头#r          （消耗5千金币）#b"),
    Array(550000000, 5000, "吉隆大都市#r          （消耗5千金币）#b"),
    Array(551000000, 5000, "甘榜村#r                  （消耗5千金币）#b"),
    Array(200000000, 2000, "天空之城#r              （消耗2千金币）#b"),
    Array(200000301, 2000, "家族中心#r              （消耗2千金币）#b"),
    Array(211000000, 2000, "冰峰雪域#r              （消耗2千金币）#b"),
    Array(230000000, 2000, "水下世界#r              （消耗2千金币）#b"),
    Array(222000000, 2000, "童话村#r                  （消耗2千金币）#b"),
    Array(220000000, 2000, "玩具城#r                  （消耗2千金币）#b"),
    Array(300000000, 2000, "艾林森林#r              （消耗2千金币）#b"),
    Array(221000000, 2000, "地球防御本部#r      （消耗2千金币）#b"),
    Array(701000000, 5000, "上海东方神州#r      （消耗5千金币）#b"),
    Array(701000200, 5000, "上海豫园#r              （消耗5千金币）#b"),
    Array(250000000, 2000, "武陵#r                      （消耗2千金币）#b"),
    Array(251000000, 2000, "百草堂#r                  （消耗2千金币）#b"),
    Array(260000000, 2000, "阿里安特#r              （消耗2千金币）#b"),
    Array(261000000, 2000, "玛加提亚#r              （消耗2千金币）#b"),
    Array(240000000, 2000, "神木村#r                  （消耗2千金币）#b"),
    Array(702000000, 5000, "嵩山#r                      （消耗5千金币）#b"),
    Array(702100000, 5000, "大雄宝殿#r              （消耗5千金币）#b"),
    Array(500000000, 1000, "泰国#r                      （消耗1千金币）#b"),
    Array(501000000, 5000, "黄金寺庙#r              （消耗5千金币）#b"),
    Array(800000000, 5000, "日本神社#r              （消耗5千金币）#b"),
    Array(801000000, 5000, "昭和村#r                  （消耗5千金币）#b"),
    Array(800040000, 5000, "枫城#r                      （消耗5千金币）#b"),
    Array(240070000, 5000, "逆奥之城#r              （消耗5千金币）#b"),
    Array(802000100, 10000, "未来东京#r              （消耗1万金币）#b"),
    Array(270000100, 10000, "时间神殿#r              （消耗1万金币）#b"),
    Array(450001000, 10000, "无名村#r                  （消耗1万金币）#b"),
    Array(450015060, 10000, "真香村#r                  （消耗1万金币）#b"),
    Array(450002000, 10000, "啾啾村#r                  （消耗1万金币）#b"),
    Array(450003000, 10000, "梦都拉克兰#r          （消耗1万金币）#b"),
    Array(450005000, 10000, "神秘森林阿尔卡娜#r  （消耗1万金币）#b"),
    // Array(450006130, 10000, "记忆沼泽莫拉斯#r      （消耗1万金币）#b"),
    Array(450007040, 10000, "太初之海埃斯佩拉#r  （消耗1万金币）#b"),
    Array(450014050, 10000, "反转城市地下避难处#r      （消耗1万金币）#b"),
    Array(450007170, 10000, "埃斯佩拉她沉睡的大海#r（消耗1万金币）#b"),
    Array(450016000, 10000, "塞拉斯繁星沉睡之地#r  （消耗1万金币）#b"),
    Array(450009100, 10000, "泰涅布利斯月之桥#r      （消耗1万金币）#b"),
    Array(450011120, 10000, "泰涅布利斯苦痛迷宫#r  （消耗1万金币）#b"),
    Array(450012000, 10000, "泰涅布利斯利曼#r          （消耗1万金币）#b")
    //Array(749020000,0,"国庆蛋糕地图")
);

//------------------------------------------------------------------------

var fubenmaps = Array(
    Array(103000000, 100000, "废弃组队（#r每日强化和正向#b）", 32),
    Array(300030100, 100000, "毒雾森林（#r副本装备和材料#b）", -1),
    Array(221024500, 100000, "玩具城101（#r副本装备和材料#b）", -1),
    Array(251010404, 100000, "老海盗（#r副本装备和材料#b）", -1),
    Array(670010000, 100000, "婚礼村组队任务（#r大药+鞋子攻击卷#b）", -1),
    Array(100000200, 100000, "月妙的年糕（#r奖励：1000点卷#b）", 12),
    Array(925020000, 100000, "武陵道场", -1),
    Array(970030000, 100000, "BOSS 强化特训", -1),
    Array(610030010, 100000, "绯红组队任务（#r披风#b）", -1),
    Array(701010321, 100000, "蜈蚣王（#r奖励：红色钻石#b）", -1),
);

//------------------------------------------------------------------------	


var status;

//Start
function start() {
    levelStart();
}

/**
 * @description 如果是sendSelectLevel，那么会根据玩家的选项自动路由到对应的level+selection方法
 */
function levelStart() {
    let text = "尊贵的大人，您想去哪里呢？（100级后可使用高级BOSS传送）\r\n";
    text += "#b#L0#城镇地图#l\t\t\t\t\t\t\t\t\t";
    text += "#L1#副本组队#l\r\n";
    text += "#L2#练级地图#l\t\t\t\t\t\t\t\t\t";
    text += "#L3#野外boss#l\r\n";
    if (cm.getPlayer().getLevel() >= 100) {
        text += "#L4#高级BOSS地图#l\r\n";
    }

    cm.sendSelectLevel(text);
}

function level0() {
    let text = "#b";
    for (let i = 0; i < townmaps.length; i++) {
        text += "#L" + i + "#" + townmaps[i][2] + "#l\r\n";
    }
    cm.sendNextSelectLevel("Town", text);
}

function level1() {
    let text = "#r#L999#注意：副本传送费用10万！(点击查看副本产出)\r\n\r\n#b";
    for (let i = 0; i < fubenmaps.length; i++) {
        text += "#L" + i + "#" + fubenmaps[i][2] + "#l\r\n";
    }
    cm.sendNextSelectLevel("Fuben", text);
}


function level2() {
    let text = "#b";
    for (let i = 0; i < monstermaps.length; i++) {
        text += "#L" + i + "#" + monstermaps[i][2] + "#l\r\n";
    }
    cm.sendNextSelectLevel("LevelUp", text);
}

function level3() {
    let text = "#b";
    for (let i = 0; i < bossmaps1.length; i++) {
        text += "#L" + i + "#" + bossmaps1[i][2] + "#l\r\n";
    }
    cm.sendNextSelectLevel("Boss1", text);
}

function level4() {
    let text = "#b";
    for (let i = 0; i < bossmaps2.length; i++) {
        text += "#L" + i + "#" + bossmaps2[i][2] + "#l\r\n";
    }
    cm.sendNextSelectLevel("Boss2", text);
}


//----------------------------------------------------------------------------------
function getDailyBossAttempts(key) {
    var v = cm.getAccountExtendValue(key, true);
    if (v == null || v === "") {
        return 0;
    }
    return parseInt(v, 10) || 0;
}

function getDailyBossConfig(mapId) {
    return DAILY_BOSS_BY_MAP[mapId];
}

function isShenshuoBossMap(mapId) {
    return SHENSHUO_BOSS_MAPS[mapId] === true;
}

function hasShenshuoBossEntryItems() {
    for (var i = 0; i < SHENSHUO_BOSS_ENTRY_ITEMS.length; i++) {
        if (!cm.haveItem(SHENSHUO_BOSS_ENTRY_ITEMS[i][0], SHENSHUO_BOSS_ENTRY_ITEMS[i][1])) {
            return false;
        }
    }
    return true;
}

function changeShenshuoBossEntryItems(multiplier) {
    for (var i = 0; i < SHENSHUO_BOSS_ENTRY_ITEMS.length; i++) {
        cm.gainItem(SHENSHUO_BOSS_ENTRY_ITEMS[i][0], SHENSHUO_BOSS_ENTRY_ITEMS[i][1] * multiplier);
    }
}

function getShenshuoBossEntryItemText() {
    return "#v4000019##z4000019# ×500\r\n#v2210006##z2210006# ×1";
}

function getServerResourceStatus(relativePath) {
    const File = Java.type('java.io.File');
    var file = new File(relativePath);
    return file.getAbsolutePath() + "（" + (file.isFile() ? "存在" : "不存在") + "）";
}

function getMapResourceStatus(mapId) {
    var area = Math.floor(mapId / 100000000);
    var relative = "Map.wz/Map/Map" + area + "/" + mapId + ".img.xml";
    return "\r\n普通WZ：" + getServerResourceStatus("wz/" + relative)
        + "\r\n语言WZ：" + getServerResourceStatus("wz-zh-CN/" + relative);
}

function levelBoss2(selection) {
    var cost = bossmaps2[selection][1];
    var mapId = bossmaps2[selection][0];
    var bossId = bossmaps2[selection][3];
    var fallbackMapId = bossmaps2[selection][4];
    var bossX = bossmaps2[selection][5];
    var bossY = bossmaps2[selection][6];
    var requiresEntryItems = isShenshuoBossMap(mapId);
    
    // 检查金币是否足够
    if (cm.getPlayer().getMeso() < cost) {
        cm.sendOk("您的金币不足，无法传送！需要 " + cost + " 金币。");
        cm.dispose();
        return;
    }

    if (requiresEntryItems && !hasShenshuoBossEntryItems()) {
        cm.sendOk("进入该 Boss 地图除 " + cost + " 金币外，还需要：\r\n" + getShenshuoBossEntryItemText());
        cm.dispose();
        return;
    }

    if (mapId === 221040001) {
        var charged = false;
        var entryItemsCharged = false;
        try {
            cm.gainMeso(-cost);
            charged = true;
            changeShenshuoBossEntryItems(-1);
            entryItemsCharged = true;
            cm.getPlayer().saveLocationOnWarp();
            cm.warp(mapId, 0);

            if (cm.getPlayer().getMapId() !== mapId) {
                cm.gainMeso(cost);
                charged = false;
                changeShenshuoBossEntryItems(1);
                entryItemsCharged = false;
                cm.sendOk("卡翁地图 " + mapId + " 未安装或加载失败，传送费用已退还。"
                    + getMapResourceStatus(mapId)
                    + "\r\n客户端地图：clien/Data/Map/Map/Map2/" + mapId + ".img"
                    + "\r\n请同时覆盖客户端和服务端地图文件，并完全重启服务端后再试。");
                cm.dispose();
                return;
            }

            var enteredMap = cm.getPlayer().getMap();
            if (bossId != null && bossId > 0 && enteredMap.getMonsterById(bossId) == null) {
                const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
                const Point = Java.type('java.awt.Point');
                var directBoss = LifeFactory.getMonster(bossId);
                if (directBoss == null) {
                    throw new Error("Boss 数据 " + bossId + " 未被当前服务端加载");
                }
                directBoss.setPosition(new Point(bossX, bossY));
                directBoss.setFh(43);
                directBoss.setCy(bossY);
                directBoss.setRx0(bossX - 500);
                directBoss.setRx1(bossX + 500);
                enteredMap.spawnMonster(directBoss);
            }
            cm.dispose();
        } catch (error) {
            if (charged && cm.getPlayer().getMapId() !== mapId) {
                cm.gainMeso(cost);
            }
            if (entryItemsCharged && cm.getPlayer().getMapId() !== mapId) {
                changeShenshuoBossEntryItems(1);
            }
            var errorMessage = "卡翁传送失败：" + String(error);
            if (cm.getPlayer().getMapId() === mapId) {
                cm.getPlayer().dropMessage(5, errorMessage);
            } else {
                cm.sendOk(errorMessage + "\r\n请把这段提示反馈给管理员。");
            }
            cm.dispose();
        }
        return;
    }
    
    var targetMap = cm.getMap(mapId);
    if (targetMap == null && fallbackMapId != null && fallbackMapId > 0) {
        mapId = fallbackMapId;
        targetMap = cm.getMap(mapId);
    }
    if (targetMap == null) {
        cm.sendOk("目标地图 " + mapId + " 未被当前服务端加载。"
            + getMapResourceStatus(mapId)
            + "\r\n请按上面的绝对路径检查补丁覆盖层级，并完全重启服务端。");
        cm.dispose();
        return;
    }

    var boss = null;
    if (bossId != null && bossId > 0 && targetMap.getMonsterById(bossId) == null) {
        const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
        const Point = Java.type('java.awt.Point');
        boss = LifeFactory.getMonster(bossId);
        if (boss == null) {
            cm.sendOk("Boss 数据 " + bossId + " 未被当前服务端加载。"
                + "\r\n普通WZ：" + getServerResourceStatus("wz/Mob.wz/" + bossId + ".img.xml")
                + "\r\n语言WZ：" + getServerResourceStatus("wz-zh-CN/Mob.wz/" + bossId + ".img.xml")
                + "\r\n请按上面的绝对路径检查补丁覆盖层级，并完全重启服务端。");
            cm.dispose();
            return;
        }
        targetMap.spawnMonsterOnGroundBelow(boss, new Point(bossX, bossY));
    }

    var cfg = getDailyBossConfig(mapId);
    if (cfg != null) {
        var used = getDailyBossAttempts(cfg.countKey);
        if (used >= DAILY_BOSS_LIMIT) {
            cm.sendOk("#e" + cfg.name + "#n 今日挑战次数已用完（" + DAILY_BOSS_LIMIT + "/" + DAILY_BOSS_LIMIT + "），请明天再来。");
            cm.dispose();
            return;
        }
        cm.saveOrUpdateAccountExtendValue(cfg.countKey, String(used + 1), true);
    }

    cm.gainMeso(-cost);
    if (requiresEntryItems) {
        changeShenshuoBossEntryItems(-1);
    }
    cm.getPlayer().saveLocationOnWarp();
    var portal = getBoss2WarpPortal(mapId);
    if (typeof portal === "string") {
        var targetPortal = targetMap.getPortal(portal);
        if (targetPortal != null) {
            // Old mobile clients may ignore a warp packet that references an
            // invisible script portal. Use its server-side position instead.
            cm.getPlayer().changeMap(targetMap, targetPortal.getPosition());
        } else {
            cm.warp(mapId, 0);
        }
    } else if (portal >= 0) {
        cm.warp(mapId, portal);
    } else {
        cm.warp(mapId);
    }
    cm.dispose();
}

function getBoss2WarpPortal(mapId) {
    if (mapId === 262030300 || mapId === 262031300
        || mapId === 450010100 || mapId === 221040001
        || mapId === 450009400 || mapId === 900000207
        || mapId === 410002060) {
        return "bossRetry";
    }
    if (mapId === 703011000) {
        return 1;
    }
    if (mapId === 211070100) {
        return 0;
    }
    return -1;
}


function levelBoss1(selection) {
    var cost = bossmaps1[selection][1];
    if (cm.getPlayer().getMeso() < cost) {
        cm.sendOk("您的金币不足，无法传送！需要 " + cost + " 金币。");
        cm.dispose();
        return;
    }
    cm.gainMeso(-cost);
    cm.getPlayer().saveLocationOnWarp();
    cm.warp(bossmaps1[selection][0]);
    cm.dispose();
}

function levelLevelUp(selection) {
    var cost = monstermaps[selection][1];
    if (cm.getPlayer().getMeso() < cost) {
        cm.sendOk("您的金币不足，无法传送！需要 " + cost + " 金币。");
        cm.dispose();
        return;
    }
    cm.gainMeso(-cost);
    cm.getPlayer().saveLocationOnWarp();
    cm.warp(monstermaps[selection][0]);
    cm.dispose();
}

function levelTown(selection) {
    var cost = townmaps[selection][1];
    if (cm.getPlayer().getMeso() < cost) {
        cm.sendOk("您的金币不足，无法传送！需要 " + cost + " 金币。");
        cm.dispose();
        return;
    }
    cm.gainMeso(-cost);
    cm.getPlayer().saveLocationOnWarp();
    cm.warp(townmaps[selection][0]);
    cm.dispose();
}

function levelFuben(selection) {
    if (selection === 999) {
        副本产出说明();
    } else {
        let portal = fubenmaps[selection][3];
        var cost = fubenmaps[selection][1];
        if (cm.getPlayer().getMeso() < cost) {
            cm.sendOk("您的金币不足，无法传送！需要 " + cost + " 金币。");
            cm.dispose();
            return;
        }
        cm.gainMeso(-cost);
        cm.getPlayer().saveLocationOnWarp();
        if (portal > 0) {
            cm.warp(fubenmaps[selection][0], portal);
        } else {
            cm.warp(fubenmaps[selection][0]);
        }
        //传送到指定位置
        // cm.getPlayer().changeMap(instanceMap, targetPos);
        cm.dispose();
    }
}

function 副本产出说明() {
    let tip = "#r所有副本每天前5次均可获得1点副本积分#k\r\n\r\n";
    tip += "#b月妙#k\r\n" +
        "1.最高经验10万\r\n" +
        "2.金币50万\r\n" +
        "3.点卷1000\r\n" +
        "\r\n" +
        "#b蜈蚣王#k\r\n" +
        "1.每天进入一次99%爆红色钻石\r\n" +
        "\r\n" +
        "#b废弃#k\r\n" +
        "1.每天强化一次项链\r\n" +
        "2.经验最高1000万\r\n" +
        "3.金币300万\r\n" +
        "4.每次必获得2个祝福1个混沌\r\n" +
        "5.30%概率获取一个正向混沌\r\n" +
        "6.2-5每天只有前3次有\r\n" +
        "\r\n" +
        "#b玩具#k\r\n" +
        "1.每天能获得一次温暖的阳光\r\n" +
        "2.小于50级，一次升1级，50级后所需经验小于200万经验获得当前所需经验的80%，当前等级所需经验大于200万获得200万经验。\r\n" +
        "3.金币100万\r\n" +
        "4.50%概率获取祝福或混沌1个\r\n" +
        "5.2-5每天只有前30次有\r\n" +
        "6.必定获取随机3个60卷，2个10卷\r\n" +
        "\r\n" +
        "#b海盗#k\r\n" +
        "1.每天能获得一次耀眼的阳光\r\n" +
        "2.每次必定获取40-60个枫叶\r\n" +
        "3.小于50级，一次升1级，50级后所需经验小于200万经验获得当前所需经验的80%，当前等级所需经验大于200万获得200万经验。\r\n" +
        "4.金币200万\r\n" +
        "5.30%概率获取祝福或混沌1个\r\n" +
        "6.3-5每天只有前50次有\r\n" +
        "\r\n" +
        "#b毒物#k\r\n" +
        "1.每天能获得一次阿尔泰碎片\r\n" +
        "2.小于50级，一次升1级，50级后所需经验小于200万经验获得当前所需经验的80%，当前等级所需经验大于200万获得200万经验。\r\n" +
        "3.金币300万\r\n" +
        "4.70%概率获取祝福或混沌1个\r\n" +
        "5.2-5每天只有前20次有\r\n" +
        "6.必定获取随机3种母矿，30%机率获取一个成品矿石\r\n" +
        "\r\n" +
        "#b婚礼村#k\r\n" +
        "1.最后打箱子机率获取鞋子攻击卷\r\n" ;
    cm.sendOk(tip);
    cm.dispose();
}
