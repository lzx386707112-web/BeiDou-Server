/* Seed 1-20 solo compatibility event. Gameplay sources and projections: migration notes. */
var isPq = true;
var minPlayers = 1;
var maxPlayers = 1;
var minLevel = 1;
var maxLevel = 250;
var maxLobbies = 8;
var exitMap = 992000000;
var TOTAL_TIME = 50 * 60000;
var Point = Java.type("java.awt.Point");
var Life = Java.type("org.gms.server.life.LifeFactory");
var Item = Java.type("org.gms.client.inventory.Item");
var Compat = Java.type("org.gms.server.life.SeedTowerCompat");
var Packets = Java.type("org.gms.util.PacketCreator");

// BEGIN SEED DATA
var SEED_DATA = {"0":{"portals":{"sp":[-324,32,"",""],"ptDirectionOut":[723,59,"","ptDirectionOut"],"go1F":[1761,45,"goTo1F",""],"ptOut":[-377,47,"outAquaris",""]},"spawns":[]},"1":{"portals":{"sp":[899,-615,"",""],"in00":[1000,-53,"","in00"],"trap11":[1041,-547,"safeZoneTrap",""],"out00":[997,69,"stageOut",""],"trap0":[864,-545,"safeZoneTrap",""],"trap1":[952,-547,"safeZoneTrap",""],"trap2":[775,-547,"safeZoneTrap",""],"trap3":[776,-635,"safeZoneTrap",""],"trap4":[776,-723,"safeZoneTrap",""],"trap5":[774,-812,"safeZoneTrap",""],"trap6":[863,-812,"safeZoneTrap",""],"trap7":[952,-811,"safeZoneTrap",""],"trap8":[1043,-812,"safeZoneTrap",""],"trap9":[1040,-724,"safeZoneTrap",""],"trap10":[1041,-637,"safeZoneTrap",""]},"spawns":[[9309047,-1234,-235],[9309047,-987,-235],[9309047,-723,-235],[9309047,-438,-235],[9309046,-992,-865],[9309046,-1127,215],[9309046,-825,215],[9309046,-594,215],[9309047,15,-235],[9309047,-194,215],[9309046,95,215],[9309046,303,-235],[9309047,295,215],[9309046,812,65],[9309047,1162,65],[9309046,837,215],[9309047,1164,215],[9309046,1588,215],[9309047,1969,215],[9309046,1713,-55],[9309047,2255,215],[9309046,1438,-295],[9309047,1630,-295],[9309046,2005,-295],[9309047,1979,-55],[9309046,-593,-55],[9309046,-520,-565],[9309046,-96,-565],[9309046,49,-865],[9309046,-282,-865],[9309046,-574,-865],[9309046,-772,-565],[9309047,-751,-865],[9309047,-105,-865],[9309047,-432,-865],[9309047,-316,-565],[9309047,102,-565],[9309047,321,-565]]},"2":{"portals":{"sp":[1081,-1270,"",""],"in00":[788,-341,"","in00"],"out00":[767,-142,"stageOut",""],"redCard":[277,-636,"s23redCard",""],"yellowCard":[1900,-634,"s23yellowCard",""],"greenCard":[-894,38,"s23greenCard",""],"blueCard":[1977,-85,"s23blueCard",""]},"spawns":[[9309013,-742,34],[9309013,-522,34],[9309013,-270,-26],[9309013,-72,-26],[9309013,218,-86],[9309013,480,-86],[9309013,697,-146],[9309013,994,-146],[9309013,1188,-86],[9309013,1449,-86],[9309013,1698,-86],[9309012,1921,-86],[9309012,-572,-157],[9309012,-370,-157],[9309012,-195,-157],[9309012,-371,-457],[9309012,-165,-457],[9309012,43,-457],[9309012,477,-337],[9309012,716,-337],[9309012,934,-337]]},"3":{"portals":{"sp":[-825,-663,"",""],"ptAssemblePoint":[762,-1211,"","ptAssemblePoint"],"in00":[762,-1211,"","in00"],"out00":[871,-176,"stageOut",""]},"spawns":[[9309042,1894,-178],[9309042,1204,-178],[9309042,1611,-178],[9309042,817,-178],[9309043,1419,-178],[9309043,549,-178],[9309043,-633,-178],[9309043,-420,-178],[9309043,-152,-178],[9309042,1830,-1558],[9309042,159,-178],[9309042,1475,-1558],[9309042,1148,-1558],[9309042,712,-1558],[9309042,220,-1558],[9309042,-142,-1258],[9309042,-505,-1258],[9309042,-855,-1258],[9309043,-691,-1258],[9309043,-328,-1258],[9309043,452,-1558],[9309043,931,-1558],[9309043,1330,-1558],[9309043,1649,-1558],[9309043,1972,-1558],[9309042,-651,-1018],[9309043,-433,-917],[9309042,-216,-838],[9309042,116,-838],[9309042,867,-838],[9309042,1212,-838],[9309043,321,-838],[9309043,671,-838],[9309043,1446,-838]]},"4":{"portals":{"sp":[582,-959,"",""],"inRight":[1418,-595,"","inRight"],"inLeft":[-415,-598,"","inLeft"],"out00":[96,161,"stageOut",""],"trap34":[1868,406,"stage4trap",""],"trap1":[-1004,406,"stage4trap",""],"trap2":[-916,406,"stage4trap",""],"trap3":[-829,406,"stage4trap",""],"trap4":[-742,406,"stage4trap",""],"trap5":[-655,406,"stage4trap",""],"trap6":[-568,406,"stage4trap",""],"trap7":[-481,406,"stage4trap",""],"trap8":[-394,406,"stage4trap",""],"trap9":[-307,406,"stage4trap",""],"trap10":[-220,406,"stage4trap",""],"trap11":[-133,406,"stage4trap",""],"trap12":[-46,406,"stage4trap",""],"trap13":[41,406,"stage4trap",""],"trap14":[128,406,"stage4trap",""],"trap15":[215,406,"stage4trap",""],"trap16":[302,406,"stage4trap",""],"trap17":[389,406,"stage4trap",""],"trap18":[476,406,"stage4trap",""],"trap19":[563,406,"stage4trap",""],"trap20":[650,406,"stage4trap",""],"trap21":[737,406,"stage4trap",""],"trap22":[824,406,"stage4trap",""],"trap23":[911,406,"stage4trap",""],"trap24":[998,406,"stage4trap",""],"trap25":[1085,406,"stage4trap",""],"trap26":[1172,406,"stage4trap",""],"trap27":[1259,406,"stage4trap",""],"trap28":[1346,406,"stage4trap",""],"trap29":[1433,406,"stage4trap",""],"trap30":[1520,406,"stage4trap",""],"trap31":[1607,406,"stage4trap",""],"trap32":[1694,406,"stage4trap",""],"trap33":[1781,406,"stage4trap",""],"trap35":[1856,486,"stage4trap",""],"trap36":[1770,486,"stage4trap",""],"trap37":[1686,486,"stage4trap",""],"trap38":[1599,487,"stage4trap",""],"trap39":[1517,487,"stage4trap",""],"trap40":[1438,489,"stage4trap",""],"trap41":[1358,489,"stage4trap",""],"trap42":[1268,491,"stage4trap",""],"trap43":[1190,493,"stage4trap",""],"trap44":[1118,488,"stage4trap",""],"trap45":[1031,485,"stage4trap",""],"trap46":[955,484,"stage4trap",""],"trap47":[876,487,"stage4trap",""],"trap48":[798,484,"stage4trap",""],"trap49":[716,488,"stage4trap",""],"trap50":[633,487,"stage4trap",""],"trap51":[560,487,"stage4trap",""],"trap52":[476,487,"stage4trap",""],"trap53":[395,488,"stage4trap",""],"trap54":[319,487,"stage4trap",""],"trap55":[238,486,"stage4trap",""],"trap56":[157,485,"stage4trap",""],"trap57":[75,484,"stage4trap",""],"trap58":[-10,484,"stage4trap",""],"trap59":[-96,487,"stage4trap",""],"trap60":[-180,482,"stage4trap",""],"trap61":[-261,482,"stage4trap",""],"trap62":[-340,482,"stage4trap",""],"trap63":[-424,482,"stage4trap",""],"trap64":[-509,483,"stage4trap",""],"trap65":[-595,484,"stage4trap",""],"trap66":[-681,484,"stage4trap",""],"trap67":[-765,482,"stage4trap",""],"trap68":[-848,487,"stage4trap",""],"trap69":[-921,489,"stage4trap",""],"trap70":[-984,489,"stage4trap",""],"trap71":[33,523,"stage4trap",""],"trap72":[-876,523,"stage4trap",""],"trap73":[-780,522,"stage4trap",""],"trap74":[-685,522,"stage4trap",""],"trap75":[-595,522,"stage4trap",""],"trap76":[-508,523,"stage4trap",""],"trap77":[-421,522,"stage4trap",""],"trap78":[-336,523,"stage4trap",""],"trap79":[-245,519,"stage4trap",""],"trap80":[-156,522,"stage4trap",""],"trap81":[-65,521,"stage4trap",""],"trap82":[-974,520,"stage4trap",""],"trap83":[129,520,"stage4trap",""],"trap84":[222,522,"stage4trap",""],"trap85":[323,522,"stage4trap",""],"trap86":[422,521,"stage4trap",""],"trap87":[521,522,"stage4trap",""],"trap88":[613,522,"stage4trap",""],"trap89":[703,524,"stage4trap",""],"trap90":[802,525,"stage4trap",""],"trap91":[900,524,"stage4trap",""],"trap92":[998,526,"stage4trap",""],"trap93":[1091,521,"stage4trap",""],"trap94":[1186,521,"stage4trap",""],"trap95":[1284,522,"stage4trap",""],"trap96":[1377,523,"stage4trap",""],"trap97":[1475,524,"stage4trap",""],"trap98":[1570,524,"stage4trap",""],"trap99":[1667,524,"stage4trap",""],"trap100":[1762,519,"stage4trap",""],"trap101":[1861,523,"stage4trap",""]},"spawns":[[9309033,-590,-50],[9309033,-594,-260],[9309033,-353,160],[9309033,-685,-470],[9309033,-355,-260],[9309033,-196,-50],[9309033,-98,-260],[9309033,-86,-470],[9309033,43,160],[9309033,-145,160],[9309033,-794,-50],[9309033,100,-50],[9309033,218,160],[9309033,-677,160],[9309132,1155,-470],[9309132,1376,-470],[9309132,1624,-470],[9309132,1100,-260],[9309132,1468,-260],[9309132,1676,-260],[9309132,1049,-50],[9309132,1307,-50],[9309132,1512,-50],[9309132,1687,-50],[9309132,1006,160],[9309132,1233,160],[9309132,1422,160],[9309132,1733,160]]},"5":{"portals":{"sp":[-1090,185,"",""],"out00":[1010,158,"stageOut",""]},"spawns":[]},"6":{"portals":{"sp":[595,-2026,"",""],"st00":[746,-985,"",""],"out00":[841,-985,"stageOut",""],"t001":[35,-666,"stage6portal","t002"],"t002":[1045,-988,"stage6portal","t003"],"t003":[481,-1180,"stage6portal","t004"],"t004":[1038,-592,"stage6portal","t005"],"t005":[1027,-1530,"stage6portal","t006"],"t006":[-24,-1008,"stage6portal","t008"],"t008":[470,-584,"stage6portal","t009"],"t009":[546,-974,"stage6portal","t010"],"t010":[-54,-1520,"stage6portal","t011"],"t011":[1037,-1201,"stage6portal","t012"],"t012":[497,-1520,"stage6portal","t013"],"t013":[-40,-1221,"stage6portal","t001"]},"spawns":[[9309001,692,-562],[9309001,1322,-562],[9309001,796,-742],[9309001,298,-562],[9309001,360,-802],[9309001,1144,-562],[9309001,1153,-742],[9309001,369,-1402],[9309001,39,-1222],[9309001,953,-562],[9309001,541,-1402],[9309001,665,-742],[9309001,698,-1462],[9309001,1308,-742],[9309001,-98,-922],[9309001,780,-1162],[9309001,1164,-1462],[9309001,1124,-1162],[9309001,516,-802],[9309001,934,-1162],[9309001,338,-1162],[9309001,1079,-862],[9309001,-115,-1462],[9309001,-107,-1222],[9309001,56,-922],[9309001,134,-562],[9309001,-30,-622],[9309001,814,-562],[9309001,948,-862],[9309001,1296,-1162],[9309001,992,-1462],[9309001,514,-1162],[9309001,236,-1402],[9309001,31,-1462],[9309001,-203,-802],[9309001,-295,-1462],[9309001,-36,-802]]},"7":{"portals":{"sp":[-502,2294,"",""],"in00":[-789,2205,"","in00"],"out00":[-909,278,"stageOut",""]},"spawns":[]},"8":{"portals":{"sp":[1344,498,"",""],"in00":[1363,966,"","in00"],"out00":[2064,2023,"stageOut",""]},"spawns":[[9309044,546,1477],[9309044,724,1472],[9309044,916,1480],[9309044,1059,1480],[9309044,1471,1471],[9309044,1634,1466],[9309044,1839,1475],[9309044,2059,1475],[9309044,2242,2025],[9309044,2034,2025],[9309045,1865,2025],[9309045,1723,2025],[9309045,1515,1905],[9309045,1288,1785],[9309045,1052,1845],[9309045,702,2025],[9309045,574,2025],[9309045,427,2025],[9309045,266,2025]]},"9":{"portals":{"sp":[897,-1179,"",""],"in00":[808,-1100,"","in00"],"tempPt2_1":[1059,-1207,"","pt02_1"],"tempPt2_2":[1059,-1207,"","pt02_2"],"tempPt2_3":[1059,-1207,"","pt02_3"],"pt06_3":[990,524,"stage9ptPuzzle",""],"tempPt3_1":[1059,-1207,"","pt03_1"],"tempPt3_2":[1059,-1207,"","pt03_2"],"tempPt3_3":[1059,-1207,"","pt03_3"],"pt06_2":[898,524,"stage9ptPuzzle",""],"tempPt4_1":[1059,-1207,"","pt04_1"],"tempPt4_2":[1059,-1207,"","pt04_2"],"tempPt4_3":[1059,-1207,"","pt04_3"],"pt06_1":[808,524,"stage9ptPuzzle",""],"tempPt5_1":[1059,-1207,"","pt05_1"],"tempPt5_2":[1059,-1207,"","pt05_2"],"tempPt5_3":[1059,-1207,"","pt05_3"],"pt07_2":[898,824,"stage9ptPuzzle",""],"tempPt6_1":[1059,-1207,"","pt06_1"],"tempPt6_2":[1059,-1207,"","pt06_2"],"tempPt6_3":[1059,-1207,"","pt06_3"],"pt05_3":[990,225,"stage9ptPuzzle",""],"tempPt7_1":[1059,-1207,"","pt07_1"],"tempPt7_2":[1059,-1207,"","pt07_2"],"tempPt7_3":[1059,-1207,"","pt07_3"],"pt05_2":[898,225,"stage9ptPuzzle",""],"tempPt8_1":[1059,-1207,"","pt08_1"],"tempPt8_2":[1059,-1207,"","pt08_2"],"tempPt8_3":[1059,-1207,"","pt08_3"],"pt05_1":[808,225,"stage9ptPuzzle",""],"tempPt9_1":[1059,-1207,"","pt09_1"],"tempPt9_2":[1059,-1207,"","pt09_2"],"tempPt9_3":[1059,-1207,"","pt09_3"],"pt07_3":[990,824,"stage9ptPuzzle",""],"tempPt10_1":[1059,-1207,"","pt10_1"],"tempPt10_2":[1059,-1207,"","pt10_2"],"tempPt10_3":[1059,-1207,"","pt10_3"],"pt04_3":[991,-75,"stage9ptPuzzle",""],"tempPt11_1":[1059,-1207,"","pt11_1"],"tempPt11_2":[1059,-1207,"","pt11_2"],"tempPt11_3":[1059,-1207,"","pt11_3"],"pt07_1":[808,824,"stage9ptPuzzle",""],"ptOut":[896,1462,"","out00"],"out00":[849,1602,"stageOut",""],"pt01_1":[809,-971,"stage9ptPuzzle",""],"pt01_2":[898,-971,"stage9ptPuzzle",""],"pt01_3":[989,-972,"stage9ptPuzzle",""],"pt08_3":[990,1124,"stage9ptPuzzle",""],"pt02_1":[809,-670,"stage9ptPuzzle",""],"pt02_2":[897,-671,"stage9ptPuzzle",""],"pt02_3":[990,-671,"stage9ptPuzzle",""],"pt08_2":[898,1124,"stage9ptPuzzle",""],"pt03_1":[809,-372,"stage9ptPuzzle",""],"pt03_2":[899,-370,"stage9ptPuzzle",""],"pt03_3":[989,-372,"stage9ptPuzzle",""],"pt08_1":[808,1124,"stage9ptPuzzle",""],"pt04_1":[809,-74,"stage9ptPuzzle",""],"pt04_2":[899,-75,"stage9ptPuzzle",""]},"spawns":[]},"10":{"portals":{"sp":[276,120,"",""],"in00":[272,124,"","in00"],"out00":[-660,155,"stageOut",""]},"spawns":[]},"11":{"portals":{"sp":[994,-833,"",""],"out00":[-798,269,"stageOut",""]},"spawns":[[9309102,-1568,270],[9309103,-1897,270],[9309102,-1142,270],[9309102,-687,270],[9309102,-18,270],[9309102,172,270],[9309102,633,270],[9309102,1195,270],[9309102,353,-150],[9309102,136,-150],[9309102,1317,-390],[9309102,745,-150],[9309102,869,-510],[9309102,556,-570],[9309102,212,-510],[9309102,-334,-630],[9309102,-958,-450],[9309102,-1308,-510],[9309102,-1637,-570],[9309102,-1865,-210],[9309102,-1648,-210],[9309102,-1361,-210],[9309102,-817,-30],[9309102,-544,-30],[9309102,-34,-330],[9309102,-323,-330],[9309103,-1364,270],[9309103,-479,270],[9309103,-214,270],[9309103,-641,-30],[9309103,-172,-330],[9309103,372,-570],[9309103,738,-558],[9309103,964,-252],[9309103,1430,-390],[9309103,-640,-630],[9309103,-491,-630],[9309103,-1454,-570],[9309103,-1129,-450],[9309103,-1489,-210],[9309103,-1763,-210]]},"12":{"portals":{"sp":[-1827,213,"",""],"in00":[-1826,195,"","in00"],"in01":[-1081,150,"","in01"],"in02":[-154,223,"","in02"],"in03":[808,196,"","in03"],"in04":[2027,-404,"","in04"],"pt_op00":[3420,-411,"","pt_op00"],"out00":[3726,270,"stageOut",""],"trap03":[1123,42,"stage12trap03",""],"trap00":[-906,102,"stage12trap00",""],"impact00":[5,-200,"",""],"trap01":[-722,223,"stage12trap01",""],"trap02":[1124,-138,"stage12trap02",""],"trap04":[1121,223,"stage12trap04",""]},"spawns":[]},"13":{"portals":{"sp":[-1262,-478,"",""],"in00":[-1748,205,"","in00"],"out00":[4354,265,"stageOut",""]},"spawns":[]},"14":{"portals":{"sp":[-96,276,"",""]},"spawns":[]},"15":{"portals":{"sp":[-1090,185,"",""],"out00":[1010,158,"stageOut",""]},"spawns":[]},"16":{"portals":{"sp":[-218,-921,"",""],"in00":[1169,32,"","in00"],"out00":[-27,119,"stageOut",""]},"spawns":[[9309004,-1724,120],[9309004,-1380,120],[9309004,-1104,-360],[9309005,-642,-360],[9309004,-1507,-120],[9309004,-1075,120],[9309004,-650,120],[9309004,-393,120],[9309004,-62,120],[9309004,377,120],[9309004,704,120],[9309004,1071,-240],[9309004,1485,120],[9309004,1685,120],[9309004,819,-180],[9309004,1290,-360],[9309004,1490,-297],[9309004,576,-300],[9309004,36,-180],[9309004,-470,-284],[9309004,-1717,-300],[9309004,-1277,-120],[9309004,-1380,-600],[9309004,-1199,-600],[9309004,-873,-228],[9309004,-582,-540],[9309004,-712,-540],[9309004,222,-420],[9309004,508,-540],[9309005,-963,-180],[9309005,-1534,-360],[9309005,20,-480],[9309005,-257,-480],[9309005,-121,-480],[9309005,356,-507],[9309005,170,-180],[9309005,314,-180],[9309005,977,-240],[9309005,1602,-240],[9309005,-1243,120],[9309005,-215,120]]},"17":{"portals":{"sp":[-1714,42,"",""],"in00":[-1711,-71,"","in00"],"hid00":[-407,-442,"",""],"hid01":[444,-469,"",""],"out00":[1528,-242,"stageOut",""]},"spawns":[]},"18":{"portals":{"sp":[-442,-953,"",""],"in00":[-453,-142,"","in00"],"out00":[-455,-27,"stageOut",""]},"spawns":[]},"19":{"portals":{"sp":[-223,-1314,"",""],"in00":[-1236,31,"","in00"],"out00":[2193,-1110,"stageOut",""],"trap0":[-186,-1205,"safeZoneTrap",""],"trap1":[-277,-1206,"safeZoneTrap",""],"trap2":[-367,-1207,"safeZoneTrap",""],"trap3":[-95,-1294,"safeZoneTrap",""],"trap4":[-95,-1205,"safeZoneTrap",""],"trap5":[-367,-1295,"safeZoneTrap",""]},"spawns":[[9309008,1043,-145],[9309008,-222,-145],[9309008,823,-505],[9309008,1556,-205],[9309008,1049,-625],[9309008,1402,-565],[9309008,428,-205],[9309008,86,-145],[9309008,-421,-145],[9309007,1757,-1045],[9309007,2329,-805],[9309006,853,-205],[9309006,1876,-85],[9309006,2086,-505],[9309006,2256,-1105],[9309006,2036,-1105],[9309006,1844,-865],[9309006,1223,-745],[9309006,942,-805],[9309006,1388,-745],[9309007,1859,-505],[9309006,2575,-805],[9309007,-753,-145],[9309007,1682,-85]],"route":[[-1195,104,0],[-945,104,2],[-702,-32,1],[-669,-157,0],[-538,-157,0],[-392,-157,0],[-209,-157,0],[6,-157,0],[243,-157,0],[449,-217,0],[673,-277,2],[847,-217,0],[1056,-157,0],[1242,-217,0],[1368,-157,0],[1541,-217,0],[1637,-217,0],[1730,-97,0],[1813,-301,1],[1754,-517,0],[1589,-577,0],[1310,-577,0],[1158,-637,0],[988,-637,0],[905,-517,0],[832,-668,1],[899,-817,0],[1019,-817,0],[1187,-757,0],[1375,-757,0],[1530,-817,0],[1628,-877,0],[1714,-817,0],[1841,-877,0],[2049,-937,0],[1925,-997,0],[1751,-1057,0],[1912,-1117,0],[2130,-1117,0]]},"20":{"portals":{"sp":[581,125,"",""],"in00":[580,131,"","in00"],"out00":[-660,155,"stageOut",""]},"spawns":[]}};
// END SEED DATA

var goals = {1:100, 3:1000, 4:300, 6:300, 8:100, 11:300, 13:80, 16:200, 18:10};
var instructions = {
    1:"消灭 100 只古代水灵，或击败古代超级水灵。",
    2:"拾取数字卡，在同色石碑按上。卡牌数字必须更大；紫卡万能。",
    3:"拾取乌龟蛋累计 1000 分，金蛋每个 50 分。",
    4:"平衡分达到 300。正确一侧 +5，错误一侧 -1；先打左边。",
    5:"休息层，总时间暂停。准备好后从出口继续。",
    6:"消灭 300 只水灵。每 30 秒出现水灵王，10 秒内击败可计 30 只。",
    7:"避开猴子的香蕉，沿绳索爬到顶端出口。",
    8:"消灭 100 只火山虫，注意火柱预警。",
    9:"八段三选一。选错退回上一段，正确答案本局保存。",
    10:"击败巨大蜘蛛。蛛网反伤持续 6 秒，注意蜘蛛卵和幼蛛。",
    11:"消灭 300 只花石巨人。",
    12:"通过尖刺跳跃和随机陷阱。弹射点会送到下一个落脚点。",
    13:"保卫左侧石碑，五波共 80 只。第五只漏怪将击碎石碑。避开落石预警。",
    14:"3 分钟内普攻击落 10 黄、5 红蝙蝠菇。99 发；前三次空挥免费，之后每次扣总时间 30 秒。",
    15:"休息层，总时间暂停。准备好后从出口继续。",
    16:"消灭 200 条鳄鱼。",
    17:"沿黑暗沼泽的绳索和尖刺路线走到出口，掉落须从头再来。",
    18:"拾取 10 个椰子并清空螃蟹。箱子 3 击，树上椰子 4 击；可再生。",
    19:"跟随 Fleta 抵达终点。距离超过 500 持续 10 秒，或 Fleta 死亡，挑战失败。",
    20:"击败铁皮伐木工。补油预警时，在入口附近按上发出艾丽西亚的咆哮打断补油。"
};

function init() { em.setProperty("party", "起源之塔 1~20 层 / 单人 / 50 分钟"); }
function getMaxLobbies() { return maxLobbies; }
function num(eim, key) { return Number(eim.getProperty(key) || 0); }
function set(eim, key, value) { eim.setProperty(key, String(value)); }
function inc(eim, key, amount) { var n = num(eim, key) + amount; set(eim, key, n); return n; }
function player(eim) { return eim.getPlayerCount() ? eim.getPlayers().get(0) : null; }
function floor(eim) { return num(eim, "floor"); }
function map(eim) { return eim.getMapInstance(992000000 + floor(eim) * 1000); }
function say(eim, text) { eim.dropMessage(5, text); }
function now() { return Date.now(); }
function random(n) { return Math.floor(Math.random() * n); }

function setup(level, lobbyid) {
    var eim = em.newInstance("SeedTower20-" + lobbyid);
    set(eim, "seedTower", 1); set(eim, "floor", 0); set(eim, "ending", 0);
    set(eim, "remaining", TOTAL_TIME);
    return eim;
}
function afterSetup(eim) {}
function playerEntry(eim, chr) {
    cleanItems(chr);
    enterFloor(eim, chr, 1);
    eim.schedule("tick", 500);
}
function cleanItems(chr) {
    var api = chr.getAbstractPlayerInteraction();
    [4000968,4009237,4009238,4009497].forEach(function(id) { api.removeAll(id); });
    for (var id = 4009900; id <= 4009928; id++) api.removeAll(id);
}
function teleport(chr, destination, name) {
    chr.changeMap(destination, destination.getPortal(name) || destination.getPortal("sp"));
}
function spawn(eim, id, x, y, controlled, flying) {
    var mob = Life.getMonster(id);
    if (!mob) throw new Error("Seed mob missing " + id);
    var m = map(eim);
    if (flying) { mob.setPosition(new Point(x,y)); m.spawnMonster(mob); }
    else m.spawnMonsterOnGroundBelow(mob, new Point(x,y));
    if (controlled) set(eim, "seedControlled." + m.getId() + "." + mob.getObjectId(), 1);
    return mob;
}
function drop(eim, dropper, id, count) {
    var chr = player(eim);
    if (chr) map(eim).spawnItemDrop(dropper, chr, new Item(id, 0, count), dropper.getPosition(), false, false);
}
function markClear(eim) {
    if (num(eim,"completed")) return;
    set(eim,"completed",1);
    eim.showClearEffect(false);
    say(eim,"第 " + floor(eim) + " 层完成，请从出口继续。");
}
function enterFloor(eim, chr, next) {
    if (next < 1 || next > 20 || num(eim,"ending")) return;
    if (floor(eim) && floor(eim) != 5 && floor(eim) != 15) set(eim,"remaining",Math.max(0,eim.getTimeLeft()));
    if(num(eim,"remaining")<=0) {fail(eim,"总时间耗尽。");return;}
    eim.stopEventTimer();
    if (floor(eim)) map(eim).killAllMonsters();
    cleanItems(chr);
    set(eim,"floor",next);
    ["kills","score","completed","side","correct","leaks","wave","shots","misses","yellow","red","puzzle","far","route","roarAt","oilAt","webAt","warning","warningAt"].forEach(function(k){set(eim,k,0);});
    set(eim,"entered",now()); set(eim,"lastTick",now());
    var m = eim.getInstanceMap(992000000 + next * 1000);
    m.resetPQ(chr.getLevel());
    var portals = SEED_DATA[String(next)].portals;
    var entrance = next == 4 ? "inLeft" : (portals.in00 ? "in00" : "sp");
    teleport(chr,m,entrance);
    if (next != 5 && next != 15) eim.startEventTimer(num(eim,"remaining"));
    else markClear(eim);
    eim.spawnNpc(2540000, chr.getPosition(), m);
    say(eim,"第 " + next + " 层：" + instructions[next]);
    if (next == 1) spawn(eim,9309131,-1150,200,false,false);
    if (next == 2) {
        ["b","y","r","g"].forEach(function(color){
            var rank = random(7)+1;
            set(eim,"seal."+color,rank); set(eim,"sealDone."+color,0);
            var reactor = m.getReactorByName(color);
            if (reactor) reactor.resetReactorActions(rank-1);
        });
        sealStatus(eim);
    }
    if (next == 9) for (var i=1;i<=8;i++) {set(eim,"answer."+i,random(3)+1);set(eim,"solved."+i,0);}
    if (next == 10) spawn(eim,9309201,-250,150,false,false);
    if (next == 12) { set(eim,"trapPair",random(2)); set(eim,"trapTriple",random(3)); }
    if (next == 13) startWave(eim);
    if (next == 14) {
        for (var b=0;b<5;b++) {
            var bat = spawn(eim,b < 3 ? 9309116 : 9309117, -400+b*170,240,true,true);
            set(eim,"batPhase."+bat.getObjectId(),b);
        }
    }
    if (next == 19) {
        var route = SEED_DATA["19"].route;
        var escort = spawn(eim,9309123,route[0][0],route[0][1],true,false);
        set(eim,"escort",escort.getObjectId());
    }
    if (next == 20) spawn(eim,9309205,-250,150,false,false);
}
function sealStatus(eim) {
    var names = ["蓝","黄","红","绿"], keys = ["b","y","r","g"], text=[];
    for (var i=0;i<4;i++) text.push(names[i]+":"+(num(eim,"sealDone."+keys[i]) ? "完成" : num(eim,"seal."+keys[i])));
    say(eim,"石碑 " + text.join("  "));
}
function progress(eim) {
    var f=floor(eim), text="第 " + f + " 层：";
    if (f==2) { sealStatus(eim); return; }
    if (f==14) text += "黄 " + num(eim,"yellow")+"/10，红 "+num(eim,"red")+"/5，余弹 "+(99-num(eim,"shots"))+"，空挥 "+num(eim,"misses");
    else if(f==9) {
        var saved=[];
        for(var i=1;i<=8;i++) if(num(eim,"solved."+i)) saved.push(i+"="+num(eim,"answer."+i));
        text+="当前第 "+(num(eim,"puzzle")+1)+" 段，已标记 "+saved.join("，");
    }
    else if (goals[f]) text += num(eim,"score")+"/"+goals[f]+(f==4 ? "，当前打"+(num(eim,"side") ? "右" : "左")+"侧" : "")+(f==13 ? "，漏怪 "+num(eim,"leaks")+"/5" : "");
    else text += instructions[f];
    say(eim,text);
}
function monsterValue(eim,id) { return 1; }
function monsterKilled(mob,eim,hasKiller) {
    if (!hasKiller || num(eim,"ending") || mob.getMap().getId() != 992000000 + floor(eim)*1000) return;
    var f=floor(eim), id=mob.getId();
    if(id>=9309400 && id<=9309402) return;
    if (num(eim,"completed")) return;
    inc(eim,"kills",1);
    if (f==1) { if(id==9309131) markClear(eim); else inc(eim,"score",1); }
    if (f==2) {
        var card = random(10)==0 ? 4009928 : 4009900+random(28);
        drop(eim,mob,card,1);
    }
    if (f==3) {
        drop(eim,mob,id==9309042 ? 4009237 : 4009238,random(10)+1);
        if(random(10)==0) drop(eim,mob,4009497,1);
    }
    if(f==4) {
        var side=id==9309132 ? 1 : 0;
        set(eim,"score",Math.max(0,num(eim,"score")+(side==num(eim,"side") ? 5 : -1)));
        if(side==num(eim,"side") && inc(eim,"correct",1)>=50) {
            set(eim,"correct",0); set(eim,"side",1-num(eim,"side"));
            say(eim,"平衡方向改变，现在打"+(num(eim,"side") ? "右" : "左")+"侧。");
        }
    }
    if(f==6) inc(eim,"score",id==9309127 ? 30 : 1);
    if(f==8 || f==11 || f==16) inc(eim,"score",1);
    if(f==10 && id==9309201) markClear(eim);
    if(f==10 && id==9309209) for(var s=0;s<3;s++) spawn(eim,9309202,mob.getPosition().x+s*30,mob.getPosition().y,false,false);
    if(f==13) {
        inc(eim,"score",1);
        if (num(eim,"score")>=80) markClear(eim);
        // Replacements keep 80 actual kills attainable after an allowed leak.
        else if(map(eim).getAllMonsters().size()==0) startWave(eim);
    }
    if(f==20 && id==9309205) finish(eim);
    if(goals[f] && f!=3 && f!=13 && f!=18 && num(eim,"score")>=goals[f]) markClear(eim);
    if(num(eim,"kills")%10==0) progress(eim);
}
function allMonstersDead(eim,hasKiller) {}
function startWave(eim) {
    var wave=inc(eim,"wave",1);
    var count=Math.min(16,80-num(eim,"score"));
    for(var i=0;i<count;i++) spawn(eim,[9309000,9309001,9309002,9309003][(wave+i)%4],400+i*65,260,true,false);
    say(eim,"第 "+Math.min(wave,5)+" 波来袭。");
}
function collect(eim,chr,id,value) {
    var quantity=chr.getItemQuantity(id,false);
    if(quantity>0) {
        chr.getAbstractPlayerInteraction().gainItem(id,-quantity);
        inc(eim,"score",quantity*value);
    }
}
function seedAttack(eim,chr,skill,oid) {
    if(floor(eim)!=14 || num(eim,"ending") || num(eim,"completed") || chr.getMapId()!=992014000 || !chr.isAlive()) return;
    if(skill!=0) { chr.dropMessage(5,"本层只能使用普通攻击。"); return; }
    if(now()-num(eim,"lastShot")<200) return;
    set(eim,"lastShot",now());
    if(num(eim,"shots")>=99 || now()-num(eim,"entered")>=180000) { fail(eim,"第 14 层弹药或时间耗尽。"); return; }
    inc(eim,"shots",1);
    var mob=oid ? map(eim).getMonsterByOid(oid) : null;
    if(mob && (mob.getId()==9309116 || mob.getId()==9309117)) {
        inc(eim,mob.getId()==9309116 ? "yellow" : "red",1);
        var id=mob.getId(), phase=num(eim,"batPhase."+oid);
        map(eim).killMonster(mob,chr,false);
        if(num(eim,"yellow")>=10 && num(eim,"red")>=5) markClear(eim);
        else {
            var replacement=spawn(eim,id,-400+phase*170,240,true,true);
            set(eim,"batPhase."+replacement.getObjectId(),phase);
        }
    } else if(inc(eim,"misses",1)>3) {
        var remaining=eim.getTimeLeft()-30000;
        set(eim,"remaining",remaining);
        if(remaining<=0) { fail(eim,"空挥扣时后总时间耗尽。"); return; }
        eim.restartEventTimer(remaining);
    }
    progress(eim);
    if(!num(eim,"completed") && num(eim,"shots")>=99) fail(eim,"第 14 层弹药耗尽。");
}
function seedReactorHit(eim,chr,reactor) {
    if(floor(eim)!=18 || num(eim,"ending") || num(eim,"completed") || chr.getMapId()!=992018000) return false;
    var key="reactor."+reactor.getObjectId();
    if(now()-num(eim,key+".hit")<500 || now()<num(eim,key+".reset")) return false;
    set(eim,key+".hit",now()); return true;
}
function seedCoconut(eim,chr,reactor) {
    if(floor(eim)!=18 || num(eim,"ending") || num(eim,"completed") || chr.getMapId()!=992018000) return;
    var required=reactor.getId()==9922003 ? 4 : 3;
    var key="reactor."+reactor.getObjectId();
    if(reactor.getState()<required || num(eim,key+".reset")>now()) return;
    set(eim,key+".reset",now()+15000);
    if(required==4 || random(3)!=0) drop(eim,reactor,4000968,required==4 ? 1 : random(2)+1);
    else for(var i=0;i<3;i++) spawn(eim,9309006,reactor.getPosition().x+i*25,reactor.getPosition().y,false,false);
}
function seedPortal(eim,chr,name) {
    if(num(eim,"ending") || chr.getMapId()!=992000000+floor(eim)*1000) return false;
    var f=floor(eim), m=map(eim), data=SEED_DATA[String(f)].portals[name];
    if(name=="out00") {
        if(f==7 || f==12 || f==17) markClear(eim);
        if(!num(eim,"completed")) { progress(eim); return false; }
        if(f==20) { finish(eim); return true; }
        enterFloor(eim,chr,f+1); return true;
    }
    if(f==2 && /Card$/.test(name)) {
        var colors=["blueCard","yellowCard","redCard","greenCard"], keys=["b","y","r","g"];
        var index=colors.indexOf(name), color=keys[index];
        if(index<0 || num(eim,"sealDone."+color)) return false;
        var api=chr.getAbstractPlayerInteraction(), card=0;
        for(var rank=num(eim,"seal."+color)+1;rank<=7;rank++) {
            var id=4009900+index*7+rank-1;
            if(chr.getItemQuantity(id,false)>0) {card=id;break;}
        }
        if(!card && chr.getItemQuantity(4009928,false)>0) card=4009928;
        if(!card) { sealStatus(eim); chr.dropMessage(5,"没有更大的同色卡或紫卡。"); return false; }
        api.gainItem(card,-1); set(eim,"sealDone."+color,1);
        var reactor=m.getReactorByName(color); if(reactor) reactor.resetReactorActions(7);
        if(keys.every(function(k){return num(eim,"sealDone."+k);})) markClear(eim);
        else sealStatus(eim);
        return true;
    }
    if(f==9 && /^pt0[1-8]_[1-3]$/.test(name)) {
        var stage=Number(name.substr(2,2)), choice=Number(name.substr(5,1));
        if(stage!=num(eim,"puzzle")+1) {teleport(chr,m,"pt0"+(num(eim,"puzzle")+1)+"_1");return false;}
        if(choice==num(eim,"answer."+stage)) {
            set(eim,"puzzle",stage);set(eim,"solved."+stage,1);say(eim,"第 "+stage+" 段答案："+choice);
            if(stage==8) {markClear(eim);teleport(chr,m,"ptOut");}
            else teleport(chr,m,"pt0"+(stage+1)+"_1");
        } else {
            set(eim,"puzzle",Math.max(0,stage-2));
            teleport(chr,m,"pt0"+Math.max(1,stage-1)+"_1");
        }
        return true;
    }
    if(f==6 && /^t\d+$/.test(name) && data && data[3]) {teleport(chr,m,data[3]);return true;}
    if(data && data[2]=="safeZoneTrap") {teleport(chr,m,f==4 ? "inLeft" : "in00");return true;}
    if(f==4 && /^trap/.test(name)) {teleport(chr,m,num(eim,"side") ? "inRight" : "inLeft");return true;}
    if(f==12) {
        if(name=="impact00") {teleport(chr,m,"in03");return true;}
        var trap=Number(name.replace("trap",""));
        if(/^trap/.test(name)) {
            var wrong=trap<2 ? trap==num(eim,"trapPair") : trap-2==num(eim,"trapTriple");
            if(wrong) teleport(chr,m,trap<2 ? "in00" : "in03");
            return true;
        }
    }
    if(f==20 && name=="roar") {seedRoar(eim,chr);return true;}
    return false;
}
function seedRoar(eim,chr) {
    if(floor(eim)!=20 || now()-num(eim,"roarAt")<15000) return;
    set(eim,"roarAt",now());
    if(num(eim,"oilAt")>now()) {
        set(eim,"oilAt",0);
        say(eim,"艾丽西亚的咆哮打断了补油！");
    } else say(eim,"咆哮已发动，暂时没有补油可打断。");
}
function hazard(eim,chr,age) {
    var f=floor(eim);
    if(f!=8 && f!=13) return;
    var interval=f==8 ? 9000 : 12000;
    if(!num(eim,"warningAt") && age>interval && age%interval<600) {
        set(eim,"warningAt",now()+1800); set(eim,"warningX",chr.getPosition().x);
        set(eim,"warningY",chr.getPosition().y); set(eim,"warning",random(2));
        if(f==13) {
            var visual=spawn(eim,num(eim,"warning") ? 9309401 : 9309402,
                num(eim,"warningX"),num(eim,"warningY")-260,true,true);
            set(eim,"hazardVisual",visual.getObjectId());
        }
        say(eim,(f==8 ? "火柱" : num(eim,"warning") ? "蓝色落石" : "绿色落石")+"即将落在 X="+chr.getPosition().x+"，请移动！");
    }
    if(f==13 && num(eim,"warningAt")) {
        var rock=map(eim).getMonsterByOid(num(eim,"hazardVisual"));
        if(rock) Compat.move(rock,num(eim,"warningX"),
            Math.round(num(eim,"warningY")-260*Math.max(0,num(eim,"warningAt")-now())/1800),500,true);
    }
    if(num(eim,"warningAt") && now()>=num(eim,"warningAt")) {
        set(eim,"warningAt",0);
        if(f==8) {
            var fire=spawn(eim,9309400,num(eim,"warningX"),num(eim,"warningY"),true,true);
            set(eim,"hazardVisual",fire.getObjectId());set(eim,"visualUntil",now()+1000);
        } else {
            var rock=map(eim).getMonsterByOid(num(eim,"hazardVisual"));
            if(rock) map(eim).killMonster(rock,null,false);
            set(eim,"hazardVisual",0);
        }
        var pos=chr.getPosition();
        if(Math.abs(pos.x-num(eim,"warningX"))<100 && Math.abs(pos.y-num(eim,"warningY"))<180) {
            if(f==8) chr.updateHpMp(Math.max(1,Math.floor(chr.getCurrentMaxHp()*0.01)),Math.max(1,Math.floor(chr.getCurrentMaxMp()*0.01)));
            else if(num(eim,"warning")) chr.addHP(-chr.getHp());
            else chr.addHP(-Math.floor(chr.getCurrentMaxHp()*0.6));
        }
    }
    if(f==8 && num(eim,"visualUntil") && now()>=num(eim,"visualUntil")) {
        var fire=map(eim).getMonsterByOid(num(eim,"hazardVisual"));
        if(fire) map(eim).killMonster(fire,null,false);
        set(eim,"hazardVisual",0);set(eim,"visualUntil",0);
    }
}
function tick(eim) {
    if(num(eim,"ending")) return;
    var chr=player(eim); if(!chr) {end(eim);return;}
    var f=floor(eim), m=map(eim), age=now()-num(eim,"entered"), dt=Math.min(1000,now()-num(eim,"lastTick"));
    set(eim,"lastTick",now());
    if(!chr.isAlive()) {fail(eim,"角色死亡，挑战结束。");return;}
    if(f!=5 && f!=15 && eim.getTimeLeft()<=0) {fail(eim,"总时间耗尽。");return;}
    if(!num(eim,"completed")) {
        if(f==3) {
            collect(eim,chr,4009237,1);collect(eim,chr,4009238,1);collect(eim,chr,4009497,50);
            if(num(eim,"score")>=1000) markClear(eim);
        }
        if(f==6 && Math.floor(age/30000)>num(eim,"kingWave")) {
            set(eim,"kingWave",Math.floor(age/30000));
            var spawns=SEED_DATA["6"].spawns;
            for(var i=0;i<2;i++) {var p=spawns[random(spawns.length)];spawn(eim,9309127,p[1],p[2],false,false);}
        }
        if(f==9) {
            var next=SEED_DATA["9"].portals["pt0"+(num(eim,"puzzle")+1)+"_1"];
            if(next && chr.getPosition().y>next[1]+180) teleport(chr,m,"pt0"+(num(eim,"puzzle")+1)+"_1");
        }
        if(f==10) {
            var boss=null, mobs=m.getAllMonsters();
            for(var i=0;i<mobs.size();i++) if(mobs.get(i).getId()==9309201) boss=mobs.get(i);
            if(boss && age-num(eim,"webAt")>=25000) {
                set(eim,"webAt",age);Compat.spiderWeb(boss);
                spawn(eim,9309209,chr.getPosition().x,chr.getPosition().y,false,false);
                say(eim,"蜘蛛织网：停止攻击，反伤持续 6 秒。");
            }
        }
        if(f==13) {
            var mobs=m.getAllMonsters();
            for(var i=0;i<mobs.size();i++) {
                var mob=mobs.get(i), p=mob.getPosition();
                if(mob.getId()>=9309400 && mob.getId()<=9309402) continue;
                var x=p.x-Math.round(110*dt/1000);
                if(x<=-1650) {
                    inc(eim,"leaks",1);m.killMonster(mob,null,false);
                    if(num(eim,"leaks")>=5) {fail(eim,"石碑被击碎。");return;}
                    say(eim,"怪物冲击石碑："+num(eim,"leaks")+"/5");
                    spawn(eim,mob.getId(),400,260,true,false);
                } else Compat.move(mob,x,p.y,Math.max(1,dt),false);
            }
            if(num(eim,"score")>=80) markClear(eim);
            else if(m.getAllMonsters().size()==0) startWave(eim);
        }
        if(f==14) {
            if(age>=180000) {fail(eim,"第 14 层三分钟时限到。");return;}
            var bats=m.getAllMonsters();
            for(var i=0;i<bats.size();i++) {
                var mob=bats.get(i), phase=num(eim,"batPhase."+mob.getObjectId());
                Compat.move(mob,Math.round(Math.sin(age/1600+phase)*450),Math.round(255+Math.sin(age/900+phase)*35),Math.max(1,dt),true);
            }
        }
        if(f==17 && chr.getPosition().y>150) teleport(chr,m,"in00");
        if(f==18) {
            collect(eim,chr,4000968,1);
            var reactors=m.getReactors();
            for(var i=0;i<reactors.size();i++) {
                var r=reactors.get(i), key="reactor."+r.getObjectId()+".reset";
                if(num(eim,key) && now()>=num(eim,key)) {r.resetReactorActions(0);set(eim,key,0);}
            }
            if(num(eim,"score")>=10 && m.getAllMonsters().size()==0) markClear(eim);
        }
        if(f==19) {
            var escort=m.getMonsterByOid(num(eim,"escort"));
            if(!escort || !escort.isAlive()) {fail(eim,"Fleta 死亡，护送失败。");return;}
            var pos=escort.getPosition(), distance=pos.distance(chr.getPosition());
            if(distance>500) {
                inc(eim,"far",dt);
                if(num(eim,"far")>=10000) {fail(eim,"距离 Fleta 太远，护送失败。");return;}
            } else {
                set(eim,"far",0);
                var route=SEED_DATA["19"].route, index=num(eim,"route");
                if(index<route.length-1) {
                    var dest=route[index+1], dx=dest[0]-pos.x,dy=dest[1]-pos.y,len=Math.sqrt(dx*dx+dy*dy);
                    var step=70*dt/1000;
                    if(len<=step) {Compat.move(escort,dest[0],dest[1],Math.max(1,dt),false);inc(eim,"route",1);}
                    else Compat.move(escort,Math.round(pos.x+dx/len*step),Math.round(pos.y+dy/len*step),Math.max(1,dt),false);
                } else if(age>=80000 && distance<250) markClear(eim);
            }
        }
        if(f==20) {
            if(!num(eim,"oilAt") && Math.floor(age/30000)>num(eim,"oilWave")) {
                set(eim,"oilWave",Math.floor(age/30000));set(eim,"oilAt",now()+6000);
                say(eim,"伐木工正在补油！6 秒内到入口按上发动咆哮。");
            }
            if(num(eim,"oilAt") && now()>=num(eim,"oilAt")) {
                set(eim,"oilAt",0);
                var mobs=m.getAllMonsters();
                for(var i=0;i<mobs.size();i++) if(mobs.get(i).getId()==9309205) mobs.get(i).heal(Math.floor(mobs.get(i).getMaxHp()*0.1),0);
                say(eim,"补油完成，伐木工恢复了 10% 生命。");
            }
        }
        hazard(eim,chr,age);
    }
    eim.schedule("tick",500);
}
function finish(eim) {
    if(num(eim,"ending")) return;
    set(eim,"ending",1);set(eim,"completed",1);
    eim.stopEventTimer();eim.setEventCleared();eim.showClearEffect(false);
    say(eim,"起源之塔前 20 层通关！");
    eim.schedule("end",3000);
}
function fail(eim,reason) { if(num(eim,"ending")) return; say(eim,reason);end(eim); }
function end(eim) {
    if(num(eim,"disposed")) return;
    set(eim,"disposed",1);set(eim,"ending",1);eim.stopEventTimer();
    var players=eim.getPlayers();
    for(var i=0;i<players.size();i++) {
        var chr=players.get(i);cleanItems(chr);eim.unregisterPlayer(chr);chr.changeMap(exitMap,0);
    }
    eim.dispose();
}
function scheduledTimeout(eim) {fail(eim,"总时间耗尽。");}
function playerExit(eim,chr) {end(eim);}
function playerLeft(eim,chr) {end(eim);}
function playerDead(eim,chr) {fail(eim,"角色死亡，挑战结束。");}
function playerRevive(eim,chr) {end(eim);return true;}
function playerDisconnected(eim,chr) {cleanItems(chr);eim.unregisterPlayer(chr);end(eim);}
function changedMap(eim,chr,id) {if(id!=992000000+floor(eim)*1000 && !num(eim,"ending")) end(eim);}
function friendlyKilled(mob,eim,hasKiller) {if(mob.getId()==9309123 && floor(eim)==19 && !num(eim,"completed")) fail(eim,"Fleta 死亡，护送失败。");}
function friendlyDamaged(eim,mob) {}
function friendlyItemDrop(eim,mob) {}
function playerUnregistered(eim,chr) {}
function changedLeader(eim,chr) {}
function leftParty(eim,chr) {}
function disbandParty(eim) {}
function clearPQ(eim) {}
function cancelSchedule() {}
function dispose(eim) {}
