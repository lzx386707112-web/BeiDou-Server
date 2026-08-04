var status = -1;
var maxSkills = false;//转职后全满技能
var needItemId = 4039020;
var needItemCount = 1;
var Job_list_Map = {
    //职业列表
    0: [//新手 - 一转
        [
            {job_id: 100, name: "战士", level: 10, js: ""},
            {id: 1000000, max_Level: 16},
            {id: 1000001, max_Level: 10},
            {id: 1000002, max_Level: 8},
            {id: 1001003, max_Level: 20},
            {id: 1001004, max_Level: 20},
            {id: 1001005, max_Level: 20}
        ], [
            {job_id: 200, name: "魔法师", level: 8, js: ""},
            {id: 2000000, max_Level: 16},
            {id: 2000001, max_Level: 10},
            {id: 2001002, max_Level: 20},
            {id: 2001003, max_Level: 20},
            {id: 2001004, max_Level: 20},
            {id: 2001005, max_Level: 20}
        ], [
            {job_id: 300, name: "弓箭手", level: 10, js: ""},
            {id: 3000000, max_Level: 16},
            {id: 3000001, max_Level: 20},
            {id: 3000002, max_Level: 8},
            {id: 3001003, max_Level: 20},
            {id: 3001004, max_Level: 20},
            {id: 3001005, max_Level: 20}
        ], [
            {job_id: 400, name: "飞侠", level: 10, js: ""},
            {id: 4000000, max_Level: 20},
            {id: 4000001, max_Level: 8},
            {id: 4001002, max_Level: 20},
            {id: 4001003, max_Level: 20},
            {id: 4001334, max_Level: 20},
            {id: 4001344, max_Level: 20}
        ], [
            {job_id: 500, name: "海盗", level: 10, js: ""},
            {id: 5000000, max_Level: 20},
            {id: 5001001, max_Level: 20},
            {id: 5001002, max_Level: 20},
            {id: 5001003, max_Level: 20},
            {id: 5001005, max_Level: 10}
        ]
    ],
    100: [//战士 - 二转
        [
            {job_id: 110, name: "剑客", level: 30, js: ""},
            {id: 1100000, max_Level: 20},
            {id: 1100001, max_Level: 20},
            {id: 1100002, max_Level: 30},
            {id: 1100003, max_Level: 30},
            {id: 1101004, max_Level: 20},
            {id: 1101005, max_Level: 20},
            {id: 1101006, max_Level: 20},
            {id: 1101007, max_Level: 30}
        ], [
            {job_id: 120, name: "准骑士", level: 30, js: ""},
            {id: 1200000, max_Level: 20},
            {id: 1200001, max_Level: 20},
            {id: 1200002, max_Level: 30},
            {id: 1200003, max_Level: 30},
            {id: 1201004, max_Level: 20},
            {id: 1201005, max_Level: 20},
            {id: 1201006, max_Level: 20},
            {id: 1201007, max_Level: 30}
        ], [
            {job_id: 130, name: "枪战", level: 30, js: ""},
            {id: 1300000, max_Level: 20},
            {id: 1300001, max_Level: 20},
            {id: 1300002, max_Level: 30},
            {id: 1300003, max_Level: 30},
            {id: 1301004, max_Level: 20},
            {id: 1301005, max_Level: 20},
            {id: 1301006, max_Level: 20},
            {id: 1301007, max_Level: 30}
        ]
    ],
    110: [//剑客 - 三转
        [
            {job_id: 111, name: "勇士", level: 70, js: ""},
            {id: 1110000, max_Level: 20},
            {id: 1110001, max_Level: 20},
            {id: 1111002, max_Level: 30},
            {id: 1111003, max_Level: 30},
            {id: 1111004, max_Level: 30},
            {id: 1111005, max_Level: 30},
            {id: 1111006, max_Level: 30},
            {id: 1111007, max_Level: 20},
            {id: 1111008, max_Level: 30}
        ]
    ],
    111: [//勇士 - 四转
        [
            {job_id: 112, name: "英雄", level: 120, js: ""},
            {id: 1120003, max_Level: 30},
            {id: 1120004, max_Level: 30},
            {id: 1120005, max_Level: 30},
            {id: 1121000, max_Level: 30},
            {id: 1121001, max_Level: 30},
            {id: 1121002, max_Level: 30},
            {id: 1121006, max_Level: 30},
            {id: 1121008, max_Level: 30},
            //{ id: 1121009, max_Level: 30 },
            {id: 1121010, max_Level: 30},
            {id: 1121011, max_Level: 5}
        ]
    ],
    120: [//准骑士 - 三转
        [
            {job_id: 121, name: "骑士", level: 70, js: ""},
            {id: 1210000, max_Level: 20},
            {id: 1210001, max_Level: 20},
            {id: 1211002, max_Level: 30},
            {id: 1211003, max_Level: 30},
            {id: 1211004, max_Level: 30},
            {id: 1211005, max_Level: 30},
            {id: 1211006, max_Level: 30},
            {id: 1211007, max_Level: 30},
            {id: 1211008, max_Level: 30},
            {id: 1211009, max_Level: 20}
        ]
    ],
    121: [//骑士 - 四转
        [
            {job_id: 122, name: "圣骑士", level: 120, js: ""},
            {id: 1220005, max_Level: 30},
            {id: 1220006, max_Level: 30},
            {id: 1220010, max_Level: 10},
            {id: 1221000, max_Level: 30},
            {id: 1221001, max_Level: 30},
            {id: 1221002, max_Level: 30},
            {id: 1221003, max_Level: 20},
            {id: 1221004, max_Level: 20},
            {id: 1221007, max_Level: 30},
            {id: 1221009, max_Level: 30},
            {id: 1221011, max_Level: 30},
            {id: 1221012, max_Level: 5}
        ]
    ],
    130: [//枪战 - 三转
        [
            {job_id: 131, name: "龙骑", level: 70, js: ""},
            {id: 1310000, max_Level: 20},
            {id: 1311001, max_Level: 30},
            {id: 1311002, max_Level: 30},
            {id: 1311003, max_Level: 30},
            {id: 1311004, max_Level: 30},
            {id: 1311005, max_Level: 30},
            {id: 1311006, max_Level: 30},
            {id: 1311007, max_Level: 20},
            {id: 1311008, max_Level: 20}
        ]
    ],
    131: [//龙骑 - 四转
        [
            {job_id: 132, name: "黑骑", level: 120, js: ""},
            {id: 1320005, max_Level: 30},
            {id: 1320006, max_Level: 30},
            {id: 1320008, max_Level: 25},
            {id: 1320009, max_Level: 25},
            {id: 1321000, max_Level: 30},
            {id: 1321001, max_Level: 30},
            {id: 1321002, max_Level: 30},
            {id: 1321003, max_Level: 30},
            {id: 1321007, max_Level: 10},
            {id: 1321010, max_Level: 5}
        ]
    ],
    200: [//魔法师 - 二转
        [
            {job_id: 210, name: "法师（火，毒）", level: 30, js: ""},
            {id: 2100000, max_Level: 20},
            {id: 2101001, max_Level: 20},
            {id: 2101002, max_Level: 20},
            {id: 2101003, max_Level: 20},
            {id: 2101004, max_Level: 30},
            {id: 2101005, max_Level: 30}
        ], [
            {job_id: 220, name: "法师（雷，冰）", level: 30, js: ""},
            {id: 2200000, max_Level: 20},
            {id: 2201001, max_Level: 20},
            {id: 2201002, max_Level: 20},
            {id: 2201003, max_Level: 20},
            {id: 2201004, max_Level: 30},
            {id: 2201005, max_Level: 30}
        ], [
            {job_id: 230, name: "牧师", level: 30, js: ""},
            {id: 2300000, max_Level: 20},
            {id: 2301001, max_Level: 20},
            {id: 2301002, max_Level: 30},
            {id: 2301003, max_Level: 20},
            {id: 2301004, max_Level: 20},
            {id: 2301005, max_Level: 30}
        ]
    ],
    210: [//法师（火，毒） - 三转
        [
            {job_id: 211, name: "巫师（火，毒）", level: 70, js: ""},
            {id: 2110000, max_Level: 20},
            {id: 2110001, max_Level: 30},
            {id: 2111002, max_Level: 30},
            {id: 2111003, max_Level: 30},
            {id: 2111004, max_Level: 20},
            {id: 2111005, max_Level: 20},
            {id: 2111006, max_Level: 30}
        ]
    ],
    220: [//法师（雷，冰） - 三转
        [
            {job_id: 221, name: "巫师（雷，冰）", level: 70, js: ""},
            {id: 2210000, max_Level: 20},
            {id: 2210001, max_Level: 30},
            {id: 2211002, max_Level: 30},
            {id: 2211003, max_Level: 30},
            {id: 2211004, max_Level: 20},
            {id: 2211005, max_Level: 20},
            {id: 2211006, max_Level: 30}
        ]
    ],
    230: [//牧师 - 三转
        [
            {job_id: 231, name: "祭司", level: 70, js: ""},
            {id: 2310000, max_Level: 20},
            {id: 2311001, max_Level: 20},
            {id: 2311002, max_Level: 20},
            {id: 2311003, max_Level: 30},
            {id: 2311004, max_Level: 30},
            {id: 2311005, max_Level: 30},
            {id: 2311006, max_Level: 30}
        ]
    ],
    211: [//巫师（火，毒） - 四转
        [
            {job_id: 212, name: "魔导师（火，毒）", level: 120, js: ""},
            {id: 2121000, max_Level: 30},
            {id: 2121001, max_Level: 30},
            {id: 2121002, max_Level: 30},
            {id: 2121003, max_Level: 30},
            {id: 2121004, max_Level: 30},
            {id: 2121005, max_Level: 30},
            {id: 2121006, max_Level: 30},
            {id: 2121007, max_Level: 30},
            {id: 2121008, max_Level: 5}
        ]
    ],
    221: [//巫师（雷，冰） - 四转
        [
            {job_id: 222, name: "魔导师（雷，冰）", level: 120, js: ""},
            {id: 2221000, max_Level: 30},
            {id: 2221001, max_Level: 30},
            {id: 2221002, max_Level: 30},
            {id: 2221003, max_Level: 30},
            {id: 2221004, max_Level: 30},
            {id: 2221005, max_Level: 30},
            {id: 2221006, max_Level: 30},
            {id: 2221007, max_Level: 30},
            {id: 2221008, max_Level: 5}
        ]
    ],
    231: [//祭司 - 四转
        [
            {job_id: 232, name: "主教", level: 120, js: ""},
            {id: 2321000, max_Level: 30},
            {id: 2321001, max_Level: 30},
            {id: 2321002, max_Level: 30},
            {id: 2321003, max_Level: 30},
            {id: 2321004, max_Level: 30},
            {id: 2321005, max_Level: 30},
            {id: 2321006, max_Level: 10},
            {id: 2321007, max_Level: 30},
            {id: 2321008, max_Level: 30},
            {id: 2321009, max_Level: 5}
        ]
    ],
    300: [//弓箭手 - 二转
        [
            {job_id: 310, name: "猎人", level: 30, js: ""},
            {id: 3100000, max_Level: 20},
            {id: 3100001, max_Level: 30},
            {id: 3101002, max_Level: 20},
            {id: 3101003, max_Level: 20},
            {id: 3101004, max_Level: 20},
            {id: 3101005, max_Level: 30}
        ], [
            {job_id: 320, name: "弩弓手", level: 30, js: ""},
            {id: 3200000, max_Level: 20},
            {id: 3200001, max_Level: 30},
            {id: 3201002, max_Level: 20},
            {id: 3201003, max_Level: 20},
            {id: 3201004, max_Level: 20},
            {id: 3201005, max_Level: 30}
        ]
    ],
    310: [//猎人 - 三转
        [
            {job_id: 311, name: "射手", level: 70, js: ""},
            {id: 3110000, max_Level: 20},
            {id: 3110001, max_Level: 20},
            {id: 3111002, max_Level: 20},
            {id: 3111003, max_Level: 30},
            {id: 3111004, max_Level: 30},
            {id: 3111005, max_Level: 30},
            {id: 3111006, max_Level: 30}
        ]
    ],
    311: [//射手 - 四转
        [
            {job_id: 312, name: "神射手", level: 120, js: ""},
            {id: 3120005, max_Level: 30},
            {id: 3121000, max_Level: 30},
            {id: 3121002, max_Level: 30},
            {id: 3121003, max_Level: 30},
            {id: 3121004, max_Level: 30},
            {id: 3221003, max_Level: 30},
            {id: 3121006, max_Level: 30},
            {id: 3121007, max_Level: 30},
            {id: 3121008, max_Level: 30},
            {id: 3121009, max_Level: 5}
        ]
    ],
    320: [//弩弓手 - 三转
        [
            {job_id: 321, name: "游侠", level: 70, js: ""},
            {id: 3210000, max_Level: 20},
            {id: 3210001, max_Level: 20},
            {id: 3211002, max_Level: 20},
            {id: 3211003, max_Level: 30},
            {id: 3211004, max_Level: 30},
            {id: 3211005, max_Level: 30},
            {id: 3211006, max_Level: 30}
        ]
    ],
    321: [//游侠 - 四转
        [
            {job_id: 322, name: "箭神", level: 120, js: ""},
            {id: 3220004, max_Level: 30},
            {id: 3221000, max_Level: 30},
            {id: 3221001, max_Level: 30},
            {id: 3221002, max_Level: 30},
            {id: 3221005, max_Level: 30},
            {id: 3221006, max_Level: 30},
            {id: 3221007, max_Level: 30},
            {id: 3221008, max_Level: 5}
        ]
    ],
    400: [//飞侠 - 二转
        [
            {job_id: 410, name: "刺客", level: 30, js: ""},
            {id: 4100000, max_Level: 20},
            {id: 4100001, max_Level: 30},
            {id: 4100002, max_Level: 20},
            {id: 4101003, max_Level: 20},
            {id: 4101004, max_Level: 20},
            {id: 4101005, max_Level: 30}
        ], [
            {job_id: 420, name: "侠客", level: 30, js: ""},
            {id: 4200000, max_Level: 20},
            {id: 4200001, max_Level: 20},
            {id: 4201002, max_Level: 20},
            {id: 4201003, max_Level: 20},
            {id: 4201004, max_Level: 30},
            {id: 4201005, max_Level: 30},
        ]
    ],
    410: [//刺客 - 三转
        [
            {job_id: 411, name: "无影人", level: 70, js: ""},
            {id: 4110000, max_Level: 20},
            {id: 4111001, max_Level: 20},
            {id: 4111002, max_Level: 30},
            {id: 4111003, max_Level: 20},
            {id: 4111004, max_Level: 30},
            {id: 4111005, max_Level: 30},
            {id: 4111006, max_Level: 20}
        ]
    ],
    411: [//无影人 - 四转
        [
            {job_id: 412, name: "隐士", level: 120, js: ""},
            {id: 4120002, max_Level: 30},
            {id: 4120005, max_Level: 30},
            {id: 4121000, max_Level: 30},
            {id: 4121003, max_Level: 30},
            {id: 4121004, max_Level: 30},
            {id: 4121006, max_Level: 30},
            {id: 4121007, max_Level: 30},
            {id: 4121008, max_Level: 30},
            {id: 4121009, max_Level: 5}
        ]
    ],
    420: [//侠客 - 三转
        [
            {job_id: 421, name: "独行客", level: 70, js: ""},
            {id: 4210000, max_Level: 20},
            {id: 4211001, max_Level: 30},
            {id: 4211002, max_Level: 30},
            {id: 4211003, max_Level: 20},
            {id: 4211004, max_Level: 30},
            {id: 4211005, max_Level: 20},
            {id: 4211006, max_Level: 30}
        ]
    ],
    421: [//独行客 - 四转
        [
            {job_id: 422, name: "侠盗", level: 120, js: ""},
            {id: 4220002, max_Level: 30},
            {id: 4220005, max_Level: 30},
            {id: 4221000, max_Level: 30},
            {id: 4221001, max_Level: 30},
            {id: 4221003, max_Level: 30},
            {id: 4221004, max_Level: 30},
            {id: 4221006, max_Level: 30},
            {id: 4221007, max_Level: 30},
            {id: 4221008, max_Level: 5}
        ]
    ],
    430: [//见习刀客 - 三转
        [
            {job_id: 431, name: "双刀客", level: 30, js: ""},
            {id: 4310000, max_Level: 20},
            {id: 4311001, max_Level: 20},
            {id: 4311002, max_Level: 20},
            {id: 4311003, max_Level: 20}
        ]
    ],
    431: [//双刀客 - 四转
        [
            {job_id: 432, name: "双刀侠", level: 55, js: ""},
            {id: 4321000, max_Level: 20},
            {id: 4321001, max_Level: 20},
            {id: 4321002, max_Level: 20},
            {id: 4321003, max_Level: 20}
        ]
    ],
    432: [//双刀侠 - 五转
        [
            {job_id: 433, name: "血刀", level: 70, js: ""},
            {id: 4331000, max_Level: 10},
            {id: 4330001, max_Level: 20},
            {id: 4331002, max_Level: 30},
            {id: 4331003, max_Level: 20},
            {id: 4331004, max_Level: 20},
            {id: 4331005, max_Level: 20}
        ]
    ],
    433: [//血刀 - 六转
        [
            {job_id: 434, name: "暗隐双刀", level: 120, js: ""},
            {id: 4341000, max_Level: 30},
            {id: 4340001, max_Level: 30},
            {id: 4341002, max_Level: 30},
            {id: 4341003, max_Level: 30},
            {id: 4341004, max_Level: 30},
            {id: 4341005, max_Level: 30},
            {id: 4341006, max_Level: 30},
            {id: 4341007, max_Level: 30},
            {id: 4341008, max_Level: 5}
        ]
    ],
    500: [//海盗 - 二转
        [
            {job_id: 510, name: "拳手", level: 30, js: ""},
            {id: 5100000, max_Level: 10},
            {id: 5100001, max_Level: 20},
            {id: 5101002, max_Level: 20},
            {id: 5101003, max_Level: 20},
            {id: 5101004, max_Level: 20},
            {id: 5101005, max_Level: 10},
            {id: 5101006, max_Level: 20},
            {id: 5101007, max_Level: 10}
        ], [
            {job_id: 520, name: "火枪手", level: 30, js: ""},
            {id: 5200000, max_Level: 20},
            {id: 5201001, max_Level: 20},
            {id: 5201002, max_Level: 20},
            {id: 5201003, max_Level: 20},
            {id: 5201004, max_Level: 20},
            {id: 5201005, max_Level: 10},
            {id: 5201006, max_Level: 20}
        ]
    ],
    510: [//拳手 - 三转
        [
            {job_id: 511, name: "斗士", level: 70, js: ""},
            {id: 5110000, max_Level: 20},
            {id: 5110001, max_Level: 40},
            {id: 5111002, max_Level: 30},
            {id: 5111004, max_Level: 20},
            {id: 5111005, max_Level: 20},
            {id: 5111006, max_Level: 30}
        ]
    ],
    511: [//斗士 - 四转
        [
            {job_id: 512, name: "冲锋队长", level: 120, js: ""},
            {id: 5121000, max_Level: 30},
            {id: 5121001, max_Level: 30},
            {id: 5121002, max_Level: 30},
            {id: 5121003, max_Level: 20},
            {id: 5121004, max_Level: 30},
            {id: 5121005, max_Level: 30},
            {id: 5121007, max_Level: 30},
            {id: 5121008, max_Level: 5},
            {id: 5121009, max_Level: 20},
            {id: 5121010, max_Level: 30}
        ]
    ],
    520: [//火枪手 - 三转
        [
            {job_id: 521, name: "大副", level: 70, js: ""},
            {id: 5210000, max_Level: 20},
            {id: 5211001, max_Level: 30},
            {id: 5211002, max_Level: 30},
            {id: 5211004, max_Level: 30},
            {id: 5211005, max_Level: 30},
            {id: 5211006, max_Level: 30}
        ]
    ],
    521: [//大副 - 四转
        [
            {job_id: 522, name: "船长", level: 120, js: ""},
            {id: 5221000, max_Level: 30},
            {id: 5220001, max_Level: 30},
            {id: 5220002, max_Level: 20},
            {id: 5221003, max_Level: 30},
            {id: 5221004, max_Level: 30},
            {id: 5221006, max_Level: 10},
            {id: 5221007, max_Level: 30},
            {id: 5221008, max_Level: 30},
            {id: 5221009, max_Level: 20},
            {id: 5221010, max_Level: 5},
            {id: 5220011, max_Level: 20}
        ]
    ],
    1000: [//初心者 - 一转
        [
            {job_id: 1100, name: "魂骑士 - 一转", level: 10, js: ""},
            {id: 11000000, max_Level: 10},
            {id: 11001001, max_Level: 10},
            {id: 11001002, max_Level: 20},
            {id: 11001003, max_Level: 20},
            {id: 11001004, max_Level: 20}
        ], [
            {job_id: 1200, name: "炎术士 - 一转", level: 10, js: ""},
            {id: 12000000, max_Level: 10},
            {id: 12001001, max_Level: 10},
            {id: 12001002, max_Level: 10},
            {id: 12001003, max_Level: 20},
            {id: 12001004, max_Level: 20}
        ], [
            {job_id: 1300, name: "风灵使者 - 一转", level: 10, js: ""},
            {id: 13000000, max_Level: 20},
            {id: 13000001, max_Level: 8},
            {id: 13001002, max_Level: 10},
            {id: 13001003, max_Level: 20},
            {id: 13001004, max_Level: 20}
        ], [
            {job_id: 1400, name: "夜行者 - 一转", level: 10, js: ""},
            {id: 14000000, max_Level: 10},
            {id: 14000001, max_Level: 8},
            {id: 14001002, max_Level: 10},
            {id: 14001003, max_Level: 10},
            {id: 14001004, max_Level: 20},
            {id: 14001005, max_Level: 20}
        ], [
            {job_id: 1500, name: "奇袭者 - 一转", level: 10, js: ""},
            {id: 15000000, max_Level: 10},
            {id: 15001001, max_Level: 20},
            {id: 15001002, max_Level: 20},
            {id: 15001003, max_Level: 10},
            {id: 15001004, max_Level: 20}
        ]
    ],
    1100: [//魂骑士 - 二转
        [
            {job_id: 1110, name: "魂骑士 - 二转", level: 30, js: ""},
            {id: 11100000, max_Level: 20},
            {id: 11101001, max_Level: 20},
            {id: 11101002, max_Level: 30},
            {id: 11101003, max_Level: 20},
            {id: 11101004, max_Level: 30},
            {id: 11101005, max_Level: 10}
        ]
    ],
    1110: [//魂骑士 - 三转
        [
            {job_id: 1111, name: "魂骑士 - 三转", level: 70, js: ""},
            {id: 11110000, max_Level: 20},
            {id: 11111001, max_Level: 20},
            {id: 11111002, max_Level: 20},
            {id: 11111003, max_Level: 20},
            {id: 11111004, max_Level: 30},
            {id: 11110005, max_Level: 20},
            {id: 11111006, max_Level: 30},
            {id: 11111007, max_Level: 20}
        ]
    ],
    1200: [//炎术士 - 二转
        [
            {job_id: 1210, name: "炎术士 - 二转", level: 30, js: ""},
            {id: 12101000, max_Level: 20},
            {id: 12101001, max_Level: 20},
            {id: 12101002, max_Level: 20},
            {id: 12101003, max_Level: 20},
            {id: 12101004, max_Level: 20},
            {id: 12101005, max_Level: 20},
            {id: 12101006, max_Level: 20}
        ]
    ],
    1210: [//炎术士 - 三转
        [
            {job_id: 1211, name: "炎术士 - 三转", level: 70, js: ""},
            {id: 12110000, max_Level: 20},
            {id: 12110001, max_Level: 20},
            {id: 12111002, max_Level: 20},
            {id: 12111003, max_Level: 20},
            {id: 12111004, max_Level: 20},
            {id: 12111005, max_Level: 30},
            {id: 12111006, max_Level: 30}
        ]
    ],
    1300: [//风灵使者 - 二转
        [
            {job_id: 1310, name: "风灵使者 - 二转", level: 30, js: ""},
            {id: 13100000, max_Level: 20},
            {id: 13101001, max_Level: 20},
            {id: 13101002, max_Level: 30},
            {id: 13101003, max_Level: 20},
            {id: 13100004, max_Level: 20},
            {id: 13101005, max_Level: 20},
            {id: 13101006, max_Level: 10}
        ]
    ],
    1310: [//风灵使者 - 三转
        [
            {job_id: 1311, name: "风灵使者 - 三转", level: 70, js: ""},
            {id: 13111000, max_Level: 20},
            {id: 13111001, max_Level: 30},
            {id: 13111002, max_Level: 20},
            {id: 13110003, max_Level: 20},
            {id: 13111004, max_Level: 20},
            {id: 13111005, max_Level: 10},
            {id: 13111006, max_Level: 20},
            {id: 13111007, max_Level: 20}
        ]
    ],
    1400: [//夜行者 - 二转
        [
            {job_id: 1410, name: "夜行者 - 二转", level: 30, js: ""},
            {id: 14100000, max_Level: 20},
            {id: 14100001, max_Level: 30},
            {id: 14101002, max_Level: 20},
            {id: 14101003, max_Level: 20},
            {id: 14101004, max_Level: 20},
            {id: 14100005, max_Level: 10},
            {id: 14101006, max_Level: 20}
        ]
    ],
    1410: [//夜行者 - 三转
        [
            {job_id: 1411, name: "夜行者 - 三转", level: 70, js: ""},
            {id: 14111000, max_Level: 30},
            {id: 14111001, max_Level: 20},
            {id: 14111002, max_Level: 30},
            {id: 14110003, max_Level: 20},
            {id: 14110004, max_Level: 20},
            {id: 14111005, max_Level: 20},
            {id: 14111006, max_Level: 30}
        ]
    ],
    1500: [//奇袭者 - 二转
        [
            {job_id: 1510, name: "奇袭者 - 二转", level: 30, js: ""},
            {id: 15100000, max_Level: 10},
            {id: 15100001, max_Level: 20},
            {id: 15101002, max_Level: 20},
            {id: 15101003, max_Level: 20},
            {id: 15100004, max_Level: 20},
            {id: 15101005, max_Level: 20},
            {id: 15101006, max_Level: 20}
        ]
    ],
    1510: [//奇袭者 - 三转
        [
            {job_id: 1511, name: "奇袭者 - 三转", level: 70, js: ""},
            {id: 15110000, max_Level: 20},
            {id: 15111001, max_Level: 20},
            {id: 15111002, max_Level: 10},
            {id: 15111003, max_Level: 20},
            {id: 15111004, max_Level: 20},
            {id: 15111005, max_Level: 20},
            {id: 15111006, max_Level: 20},
            {id: 15111007, max_Level: 30}
        ]
    ],
    2000: [//战神 - 一转
        [
            {job_id: 2100, name: "战神 - 一转", level: 10, js: ""},
            {id: 21000000, max_Level: 10},
            {id: 21001001, max_Level: 15},
            {id: 21000002, max_Level: 20},
            {id: 21001003, max_Level: 20}
        ]
    ],
    2100: [//战神 - 二转
        [
            {job_id: 2110, name: "战神 - 二转", level: 30, js: ""},
            {id: 21100000, max_Level: 20},
            {id: 21100001, max_Level: 20},
            {id: 21100002, max_Level: 30},
            {id: 21101003, max_Level: 20},
            {id: 21100004, max_Level: 20},
            {id: 21100005, max_Level: 20}
        ]
    ],
    2110: [//战神 - 三转
        [
            {job_id: 2111, name: "战神 - 三转", level: 70, js: ""},
            {id: 21110000, max_Level: 20},
            {id: 21111001, max_Level: 20},
            {id: 21110002, max_Level: 20},
            {id: 21110003, max_Level: 30},
            {id: 21110004, max_Level: 30},
            {id: 21111005, max_Level: 20},
            {id: 21110006, max_Level: 20},
            {id: 21110007, max_Level: 20},
            {id: 21110008, max_Level: 20}
        ]
    ],
    2111: [//战神 - 四转
        [
            {job_id: 2112, name: "战神 - 四转", level: 120, js: ""},
            {id: 21121000, max_Level: 30},
            {id: 21120001, max_Level: 30},
            {id: 21120002, max_Level: 30},
            {id: 21121003, max_Level: 30},
            {id: 21120004, max_Level: 30},
            {id: 21120005, max_Level: 30},
            {id: 21120006, max_Level: 30},
            {id: 21120007, max_Level: 30},
            {id: 21121008, max_Level: 5},
            {id: 21120009, max_Level: 30},
            {id: 21120010, max_Level: 30}
        ]
    ],

    2001: [//龙神 - 一转
        [
            {job_id: 2200, name: "龙神 - 一转", level: 10, js: ""},
            {id: 22000000, max_Level: 20},
            {id: 22001001, max_Level: 20}
        ]
    ],
    2200: [//龙神 - 二转
        [
            {job_id: 2210, name: "龙神 - 二转", level: 20, js: ""},
            {id: 22101000, max_Level: 20},
            {id: 22101001, max_Level: 20}
        ]
    ],
    2210: [//龙神 - 三转
        [
            {job_id: 2211, name: "龙神 - 三转", level: 30, js: ""},
            {id: 22111000, max_Level: 20},
            {id: 22111001, max_Level: 20}
        ]
    ],
    2211: [//龙神 - 四转
        [
            {job_id: 2212, name: "龙神 - 四转", level: 40, js: ""},
            {id: 22121000, max_Level: 20},
            {id: 22121001, max_Level: 20}
        ]
    ],
    2212: [//龙神 - 五转
        [
            {job_id: 2213, name: "龙神 - 五转", level: 50, js: ""},
            {id: 22131000, max_Level: 20},
            {id: 22131001, max_Level: 20}
        ]
    ],
    2213: [//龙神 - 六转
        [
            {job_id: 2214, name: "龙神 - 六转", level: 60, js: ""},
            {id: 22140000, max_Level: 15},
            {id: 22141001, max_Level: 20},
            {id: 22141002, max_Level: 15},
            {id: 22141003, max_Level: 15}
        ]
    ],
    2214: [//龙神 - 七转
        [
            {job_id: 2215, name: "龙神 - 七转", level: 80, js: ""},
            {id: 22150000, max_Level: 15},
            {id: 22151001, max_Level: 20},
            {id: 22151002, max_Level: 20},
            {id: 22151003, max_Level: 10}
        ]
    ],
    2215: [//龙神 - 八转
        [
            {job_id: 2216, name: "龙神 - 八转", level: 100, js: ""},
            {id: 22160000, max_Level: 10},
            {id: 22161001, max_Level: 20},
            {id: 22161002, max_Level: 20},
            {id: 22161003, max_Level: 15}
        ]
    ],
    2216: [//龙神 - 九转
        [
            {job_id: 2217, name: "龙神 - 九转", level: 120, js: ""},
            {id: 22171000, max_Level: 30},
            {id: 22170001, max_Level: 30},
            {id: 22171002, max_Level: 30},
            {id: 22171003, max_Level: 30},
            {id: 22171004, max_Level: 5},
        ]
    ],
    2217: [//龙神 - 九转
        [
            {job_id: 2218, name: "龙神 - 十转", level: 160, js: ""},
            {id: 22181000, max_Level: 30},
            {id: 22181001, max_Level: 30},
            {id: 22181002, max_Level: 30},
            {id: 22181003, max_Level: 20}
        ]
    ]
};
var Job_list = [];
var job_list_sel;

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode == -1) {
        cm.dispose();
    } else {
        if (status == 0 && mode == 0) {
            cm.dispose();
            return;
        }
        if (mode == 1) {
            status++;
        } else {
            status--;
        }
    }
    if (status == 0) {
        Job_list = Job_list_Map[cm.getJobId()];
        let qty = needItemCount * 获取更换职业次数();
        if (Job_list != null) {
            var text = "嗨，我是 #b管理员#k 我可以帮助你快速转职哦~~！\r\n#b";
            text+=`#r每次需要消耗#v${needItemId}# x${qty}个（更换职业次数越多需要的越多）#b\r\n\r\n`;
            for (var i = 0; i < Job_list.length; i++) {
                var s_text = "";
                for (var j = 1; j < Job_list[i].length; j++) {
                    s_text += "#s" + Job_list[i][j].id + "# ";
                }
                text += "#b#L" + i + "#" + Job_list[i][0].name + " #d最低等级要求：#r#e" + Job_list[i][0].level + "#b#n#l\r\n\r\n\t" + Job_list[i][0].js + "\r\n\t#d技能：" + s_text + "#k\r\n";
            }
            cm.sendSimple(text);
        } else {
            cm.sendOk("#d啊哈... 伟大的 #r[#h #]#k ,您的等级不够或已4转!");
            cm.dispose();
        }
    } else if (status == 1) {
        job_list_sel = selection;
        var s_text = "";
        for (var i = 1; i < Job_list[job_list_sel].length; i++) {
            s_text += "#s" + Job_list[job_list_sel][i].id + "# ";
        }
        let jonId = Job_list[job_list_sel][0].job_id
        if (is4Zhuan(Job_list[job_list_sel][0].job_id)) {
            maxSkills = false
        }
        var text = "#d你选择的职业是：#b" + Job_list[job_list_sel][0].name + " #d最低等级要求：#r#e" + Job_list[job_list_sel][0].level + "#d#n\r\n\t" + Job_list[job_list_sel][0].js + "\r\n\t技能：" + s_text + "#k\r\n" + (maxSkills ? "\t#b#e转职之后将为你全满技能#n\r\n\r\n" : "#b\t4转再提供满技能服务\r\n\r\n") + "#r\t是否要继续完成转职？";
        cm.sendYesNo(text);
    } else if (status == 2) {
        if (cm.getPlayer().getLevel() >= Job_list[job_list_sel][0].level) {
            jobChange(Job_list[job_list_sel][0].job_id);
        } else {
            cm.sendOk("怎么样？冒险还算顺利吧。有努力就有回报。当然这一切都不是容易的。当你到达 #r[" + Job_list[job_list_sel][0].level + "级]#k 的时候就可以进行#b[" + Job_list[job_list_sel][0].name + " 转职]#k到时别忘记来找我哦！");
            cm.dispose();
        }
    } else {
        cm.sendOk("脚本错误请联系技术处理QQ:790615512\r\nstatus:" + status + "\r\nselection:" + selection + "\r\nmode:" + mode);
        cm.dispose();
    }

}

function is4Zhuan(id) {
    return id === 112 || id === 122 || id === 132 || id === 212 || id === 222 || id === 232 || id === 312 || id === 322 || id === 412 || id === 422 || id === 512 || id === 522 || id === 2112
}

function jobChange(jobId) {
    let qty = needItemCount * 获取更换职业次数();
    if (!cm.haveItem(needItemId, qty)) {
        cm.sendOk(`快速转职需要：#v${needItemId}# x${qty}个，您的数量不足，无法转职！\r\n`);
        cm.dispose();
        return;
    }
    cm.gainItem(needItemId, -qty); // 扣减材料
    //一转需要给东西,并重置状态,不然不给技能点
    if (jobId === 100) {
        if (cm.isNotCanHold(2)) {
            return
        }
        cm.changeJobById(100);
        cm.gainItem(1302077, 1);
        cm.resetStats();
    } else if (jobId === 200) {
        if (cm.isNotCanHold(1)) {
            return
        }
        cm.changeJobById(200);
        cm.gainItem(1372043, 1);
        cm.resetStats();
    } else if (jobId === 300) {
        if (cm.isNotCanHold(1)) {
            return
        }
        if (cm.isNotCanHold(2)) {
            return
        }
        cm.changeJobById(300);
        cm.gainItem(1452051, 1);
        cm.gainItem(2060000, 1000);
        cm.resetStats();
    } else if (jobId === 400) {
        if (cm.isNotCanHold(1)) {
            return
        }
        if (cm.isNotCanHold(2, 3)) {
            return
        }
        cm.changeJobById(400);
        cm.gainItem(2070015, 500);
        cm.gainItem(1472061, 1);
        cm.gainItem(1332063, 1);
        cm.resetStats();
    } else if (jobId === 500) {
        if (cm.isNotCanHold(1)) {
            return
        }
        if (cm.isNotCanHold(2, 3)) {
            return
        }
        cm.changeJobById(500);
        cm.gainItem(1492000, 1);
        cm.gainItem(1482000, 1);
        cm.gainItem(2330000, 1000);
        cm.resetStats();
    } else {
        cm.changeJobById(jobId);
    }
    // cm.resetStats();
    for (var i = 1; i < Job_list[job_list_sel].length; i++) {
        cm.teachSkill(Job_list[job_list_sel][i].id, maxSkills ? Job_list[job_list_sel][i].max_Level : 0, Job_list[job_list_sel][i].max_Level, -1);
    }
    sendSuperMegaphone(cm.getPlayer(), 3, "转职系统", `恭喜玩家【${cm.getPlayer().getName()}】转职成为【${Job_list[job_list_sel][0].name}】!`);
    cm.sendOk("转职成功！加油锻炼，当你变的强大的时候记的来找我哦！");
    cm.dispose();
}

/**
 * 背包是否满了
 * type 背包类型:1 装备 2 消耗 3 设置 4 其他 5 特殊
 * count 查询的格子数量,最少1格
 */
function isCanHold(type) {
    if (cm.getPlayer().isFull(type, 3)) {
        cm.sendOk("#r背包空间不足，请确保空间大于等于3格子！");
        cm.dispose();
        return false
    }
    return true
}

function 获取更换职业次数() {
    let count = cm.getAccountExtendValue("更换职业次数");
    return Number(count) || 0; // 处理未签到过的情况
}

function 保存更换职业次数() {
    cm.saveOrUpdateAccountExtendValue("更换职业次数", String(获取更换职业次数() + 1));
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
