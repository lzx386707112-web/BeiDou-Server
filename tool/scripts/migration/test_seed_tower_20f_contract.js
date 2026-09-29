#!/usr/bin/env node
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ROOT = path.resolve(__dirname, "../../..");
const list = values => ({size:()=>values.length,get:i=>values[i]});
let checks=0;
function check(value) { assert.ok(value);checks++; }

function fixture(floor=1) {
    let clock=1000000, nextOid=1, callback;
    class Point {
        constructor(x,y) {this.x=x;this.y=y;}
        distance(p) {return Math.hypot(this.x-p.x,this.y-p.y);}
    }
    const inventory=new Map(), messages=[], maps=new Map(), schedules=[];
    const chr={
        mapId:992000000, pos:new Point(0,0), hp:1000, mp:1000,
        getMapId(){return this.mapId;},getPosition(){return this.pos;},getLevel:()=>150,
        isAlive(){return this.hp>0;},getHp(){return this.hp;},getCurrentMaxHp:()=>1000,getCurrentMaxMp:()=>1000,
        addHP(n){this.hp+=n;},updateHpMp(hp,mp){this.hp=hp;this.mp=mp;},
        getItemQuantity(id){return inventory.get(id)||0;},
        getAbstractPlayerInteraction(){return {removeAll:id=>inventory.delete(id),gainItem:(id,q)=>inventory.set(id,(inventory.get(id)||0)+q)};},
        changeMap(map,portal){this.mapId=typeof map==="number" ? map : map.id; if(portal && portal.pos) this.pos=portal.pos;},
        dropMessage(t,s){messages.push(s);}
    };
    function monster(id) {
        let mob={id,oid:nextOid++,pos:new Point(0,0),alive:true,hp:100000,
            getId(){return this.id;},getObjectId(){return this.oid;},getPosition(){return this.pos;},
            setPosition(p){this.pos=p;},getMap(){return this.map;},isAlive(){return this.alive;},
            getMaxHp:()=>100000,heal(n){this.hp=Math.min(100000,this.hp+n);}};
        return mob;
    }
    function getMap(id) {
        if(!maps.has(id)) {
            const mobs=[], reactors=new Map(), drops=[];
            const m={id,mobs,drops,reactors,nextOid:1000000001,
                getId(){return this.id;},resetPQ(){},
                getPortal(name){return {name,pos:new Point(0,0)};},
                spawnMonster(mob){mob.map=this;mob.oid=this.nextOid++;mobs.push(mob);},
                spawnMonsterOnGroundBelow(mob,p){mob.pos=p;this.spawnMonster(mob);},
                getAllMonsters(){return list([...mobs]);},getMonsterByOid(oid){return mobs.find(x=>x.oid===oid)||null;},
                killMonster(mob,who){mobs.splice(mobs.indexOf(mob),1);mob.alive=false;if(callback) callback(mob,eim,!!who);},
                killAllMonsters(){for(const mob of [...mobs]) this.killMonster(mob,null);},
                spawnItemDrop(dropper,owner,item){drops.push(item);},
                getReactorByName(name){return reactors.get(name)||null;},getReactors(){return list([...reactors.values()]);}
            };
            maps.set(id,m);
        }
        return maps.get(id);
    }
    const props=new Map();
    let players=[chr], deadline=null;
    const eim={
        getProperty:k=>props.get(k)||null,setProperty:(k,v)=>props.set(k,String(v)),
        getPlayerCount:()=>players.length,getPlayers:()=>list([...players]),
        getInstanceMap:getMap,getMapInstance:getMap,spawnNpc(){},
        getTimeLeft:()=>deadline===null ? -clock : deadline-clock,
        startEventTimer(n){deadline=clock+n;},stopEventTimer(){deadline=null;},restartEventTimer(n){deadline=clock+n;},
        schedule(name,delay){schedules.push([name,delay]);},
        showClearEffect(){},setEventCleared(){this.cleared=true;},dropMessage(t,s){messages.push(s);},
        unregisterPlayer(p){players=players.filter(x=>x!==p);},dispose(){this.disposed=true;},
    };
    const Compat={move(mob,x,y){mob.pos=new Point(x,y);},spiderWeb(mob){mob.web=true;}};
    const sandbox={Java:{type(name){
        if(name==="java.awt.Point") return Point;
        if(name.endsWith("LifeFactory")) return {getMonster:monster};
        if(name.endsWith(".Item")) return class Item {constructor(id,pos,count){this.id=id;this.count=count;}};
        if(name.endsWith("SeedTowerCompat")) return Compat;
        return {};
    }},Date:{now:()=>clock},Math,em:{newInstance:()=>eim,setProperty(){}}};
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(path.join(ROOT,"gms-server/scripts/event/SeedTower20.js"),"utf8"),sandbox);
    callback=sandbox.monsterKilled;
    if(!Object.keys(sandbox.SEED_DATA).length) {
        for(let f=1;f<=20;f++) sandbox.SEED_DATA[f]={portals:{in00:[0,0,"",""],sp:[0,0,"",""]},spawns:[[9309001,0,0]]};
        sandbox.SEED_DATA[19].route=[[0,0,0],[70,0,0]];
    }
    sandbox.setup(1,0); sandbox.enterFloor(eim,chr,floor);
    return {s:sandbox,eim,chr,inventory,messages,props,maps,Point,
        m:()=>getMap(chr.mapId),n:k=>Number(props.get(k)||0),set:(k,v)=>props.set(k,String(v)),
        advance(ms){clock+=ms;},tick(ms=500){clock+=ms;sandbox.tick(eim);},
        mob(id,x=0,y=0){return sandbox.spawn(eim,id,x,y,true,false);},
        kill(id){const mob=this.mob(id);this.m().killMonster(mob,chr);},
        reactor(id,state=0){return {id,oid:nextOid++,state,pos:new Point(0,0),getId(){return this.id;},getObjectId(){return this.oid;},getState(){return this.state;},getPosition(){return this.pos;},resetReactorActions(state){this.state=state;}};}
    };
}

function counts() {
    for(const [floor,id,goal] of [[1,9309046,100],[6,9309001,300],[8,9309044,100],[11,9309102,300],[16,9309004,200]]) {
        const t=fixture(floor);
        for(let i=0;i<goal-1;i++) t.kill(id);
        check(!t.n("completed"));t.kill(id);check(t.n("completed")===1);
    }
    const t=fixture(1);t.kill(9309131);check(t.n("completed")===1);
    const king=fixture(6);king.kill(9309127);check(king.n("score")===30);
    king.tick(30000);check(king.m().mobs.filter(m=>m.id===9309127).length===2);
    const gone=fixture(11), mob=gone.mob(9309102);gone.m().killMonster(mob,null);check(gone.n("score")===0);
}
function pickupsAndSeals() {
    const t=fixture(3);t.kill(9309042);check(t.n("score")===0);check(t.m().drops.some(d=>d.id===4009237));
    t.inventory.set(4009237,500);t.inventory.set(4009238,450);t.inventory.set(4009497,1);t.tick();
    check(t.n("score")===1000 && t.n("completed")===1);check(t.inventory.get(4009237)===0);
    const seal=fixture(2);seal.set("seal.b",4);seal.inventory.set(4009903,1);
    check(!seal.s.seedPortal(seal.eim,seal.chr,"blueCard"));check(seal.inventory.get(4009903)===1);
    seal.inventory.set(4009904,1);check(seal.s.seedPortal(seal.eim,seal.chr,"blueCard"));check(seal.inventory.get(4009904)===0);
    for(const [key,name] of [["y","yellowCard"],["r","redCard"],["g","greenCard"]]) {
        seal.set("seal."+key,7);seal.inventory.set(4009928,1);check(seal.s.seedPortal(seal.eim,seal.chr,name));
    }
    check(seal.n("completed")===1);
}
function balanceAndRest() {
    const t=fixture(4);for(let i=0;i<50;i++) t.kill(9309033);
    check(t.n("score")===250 && t.n("side")===1);t.kill(9309033);check(t.n("score")===249);
    for(let i=0;i<11;i++) t.kill(9309132);check(t.n("completed")===1);
    for(const floor of [5,15]) {
        const rest=fixture(floor), remaining=rest.n("remaining");rest.tick(600000);
        check(!rest.eim.disposed && rest.n("remaining")===remaining);
        rest.s.seedPortal(rest.eim,rest.chr,"out00");check(rest.eim.getTimeLeft()===remaining);
    }
}
function shots() {
    const t=fixture(14), remaining=t.eim.getTimeLeft();
    t.s.seedAttack(t.eim,t.chr,1001004,0);check(t.n("shots")===0);
    for(let i=0;i<4;i++) {t.advance(300);t.s.seedAttack(t.eim,t.chr,0,0);}
    check(t.n("shots")===4 && t.n("misses")===4);check(t.eim.getTimeLeft()===remaining-1200-30000);
    const success=fixture(14);
    for(const [id,count] of [[9309116,10],[9309117,5]]) for(let i=0;i<count;i++) {
        success.advance(300);const mob=success.mob(id);success.s.seedAttack(success.eim,success.chr,0,mob.oid);
    }
    check(success.n("completed")===1 && success.n("shots")===15);
    const ammo=fixture(14);ammo.set("shots",98);ammo.s.seedAttack(ammo.eim,ammo.chr,0,0);check(ammo.eim.disposed);
    const time=fixture(14);time.tick(180000);check(time.eim.disposed);
}
function defend() {
    const t=fixture(13);
    for(let i=0;i<80;i++) {const mob=t.m().mobs[0];check(!!mob);t.m().killMonster(mob,t.chr);}
    check(t.n("wave")===5 && t.n("completed")===1);
    const leak=fixture(13);
    for(let i=0;i<4;i++) {leak.m().mobs[0].pos=new leak.Point(-1700,260);leak.tick();}
    check(leak.n("leaks")===4 && !leak.eim.disposed);
    leak.m().mobs[0].pos=new leak.Point(-1700,260);leak.tick();check(leak.eim.disposed);
    const allowed=fixture(13);allowed.m().mobs[0].pos=new allowed.Point(-1700,260);allowed.tick();
    for(let i=0;i<80;i++) allowed.m().killMonster(allowed.m().mobs[0],allowed.chr);
    check(allowed.n("completed")===1 && allowed.n("wave")===5);
}
function coconut() {
    const t=fixture(18), r=t.reactor(9922003,3);t.m().reactors.set("tree",r);
    check(t.s.seedReactorHit(t.eim,t.chr,r));check(!t.s.seedReactorHit(t.eim,t.chr,r));
    t.s.seedCoconut(t.eim,t.chr,r);check(t.m().drops.length===0);
    r.state=4;t.s.seedCoconut(t.eim,t.chr,r);check(t.m().drops[0].id===4000968);
    t.s.seedCoconut(t.eim,t.chr,r);check(t.m().drops.length===1);
    t.tick(15000);check(r.state===0);check(t.s.seedReactorHit(t.eim,t.chr,r));
    const crab=t.mob(9309006);t.inventory.set(4000968,10);t.tick();check(!t.n("completed"));
    t.m().killMonster(crab,t.chr);t.tick();check(t.n("completed")===1);
}
function puzzlesAndEscort() {
    const t=fixture(9);
    for(let stage=1;stage<=8;stage++) {t.set("answer."+stage,2);t.s.seedPortal(t.eim,t.chr,"pt0"+stage+"_2");}
    check(t.n("completed")===1 && t.n("puzzle")===8);
    const wrong=fixture(9);wrong.set("answer.1",1);wrong.s.seedPortal(wrong.eim,wrong.chr,"pt01_1");
    wrong.set("answer.2",2);wrong.s.seedPortal(wrong.eim,wrong.chr,"pt02_1");
    check(wrong.n("puzzle")===0 && wrong.n("solved.1")===1);
    const escort=fixture(19), mob=escort.m().getMonsterByOid(escort.n("escort"));
    escort.chr.pos=new escort.Point(5000,5000);
    for(let i=0;i<20;i++) escort.tick();check(escort.eim.disposed);
    const finish=fixture(19);
    finish.s.SEED_DATA[19].route=[[0,0,0],[70,0,0]];
    const fleta=finish.m().getMonsterByOid(finish.n("escort"));fleta.pos=new finish.Point(0,0);finish.chr.pos=new finish.Point(0,0);
    finish.tick(1000);finish.tick(1000);check(!finish.n("completed"));finish.advance(78000);finish.tick();check(finish.n("completed")===1);
    finish.s.friendlyKilled(fleta,finish.eim,false);check(!finish.eim.disposed);
}
function bossesAndCleanup() {
    const spider=fixture(10);spider.kill(9309202);check(!spider.n("completed"));spider.kill(9309201);check(spider.n("completed")===1);
    const oil=fixture(20);oil.tick(30000);check(oil.n("oilAt")>0);oil.s.seedRoar(oil.eim,oil.chr);check(oil.n("oilAt")===0);
    const t=fixture(20);t.kill(9309205);check(t.n("ending")===1 && t.eim.cleared);
    t.s.finish(t.eim);t.s.end(t.eim);check(t.eim.disposed && t.chr.getMapId()===992000000);
    check(!t.maps.has(992021000));
    const leave=fixture(2);leave.inventory.set(4009900,5);leave.inventory.set(4000000,10);leave.s.end(leave.eim);
    check(!leave.inventory.has(4009900) && leave.inventory.get(4000000)===10);
    const other=fixture(2);check(other.n("sealDone.b")===0);
}
function hazardsAndBoundaries() {
    const fire=fixture(8);fire.tick(9500);check(fire.n("warningAt")>0);
    fire.tick(1800);check(fire.chr.hp===10 && fire.chr.mp===10);
    check(fire.m().mobs.some(m=>m.id===9309400));check(fire.n("score")===0);
    fire.tick(1000);check(!fire.m().mobs.some(m=>m.id===9309400));check(fire.n("score")===0);
    const avoid=fixture(8);avoid.tick(9500);avoid.chr.pos=new avoid.Point(300,0);avoid.tick(1800);
    check(avoid.chr.hp===1000 && avoid.chr.mp===1000);
    for(const [blue,hp] of [[1,0],[0,400]]) {
        const rock=fixture(13);rock.tick(12500);check(rock.n("warningAt")>0);
        check(rock.m().mobs.some(m=>m.id===9309401 || m.id===9309402));
        rock.set("warning",blue);rock.tick(1800);check(rock.chr.hp===hp);
        check(!rock.m().mobs.some(m=>m.id===9309401 || m.id===9309402));check(rock.n("score")===0);
    }
    const ids=fixture(13), oid=ids.m().mobs[0].oid;
    check(ids.n("seedControlled.992013000."+oid)===1);
    ids.s.enterFloor(ids.eim,ids.chr,20);
    check(ids.m().mobs[0].oid===oid);check(ids.n("seedControlled.992020000."+oid)===0);
    const expired=fixture(4);expired.set("completed",1);expired.advance(50*60000);
    expired.s.seedPortal(expired.eim,expired.chr,"out00");check(expired.eim.disposed);
    check(expired.n("floor")===4);
    const java=fs.readFileSync(path.join(ROOT,"gms-server/src/main/java/org/gms/server/life/SeedTowerCompat.java"),"utf8");
    check(java.includes('mob.getMap().getId() + "." + mob.getObjectId()'));
    check(java.includes("mob.getId() >= 9309400 && mob.getId() <= 9309402"));
    check(java.includes("player.getMapId() == 992014000 && (mob.getId() == 9309116"));
}
counts();pickupsAndSeals();balanceAndRest();shots();defend();coconut();puzzlesAndEscort();bossesAndCleanup();hazardsAndBoundaries();
console.log(`Seed gameplay: ${checks} assertions passed`);
