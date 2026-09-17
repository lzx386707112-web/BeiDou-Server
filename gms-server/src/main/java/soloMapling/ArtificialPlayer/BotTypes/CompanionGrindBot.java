package soloMapling.ArtificialPlayer.BotTypes;

import java.awt.Point;
import org.gms.client.Character;
import org.gms.net.server.world.Party;
import org.gms.server.life.Monster;
import soloMapling.ArtificialPlayer.BotCommandsPack.BotAttack;
import soloMapling.ArtificialPlayer.BotHelpers;
import soloMapling.ArtificialPlayer.BotPartySystem.BotDamageModel;
import soloMapling.ArtificialPlayer.BotPartySystem.PartyGrindService;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;
import soloMapling.server.BotTickService;

public class CompanionGrindBot extends BotSM {
    private static final long TICK_MS = 220;
    private static final long SWING_CD_MS = 800;
    private static final int LEASH_X = 280;
    private static final int ENGAGE_X = 120;
    private static final int ENGAGE_Y = 120;
    private static final int MOVE_EPS = 16;
    private volatile int leaderId = -1;
    private int lastMoveX = Integer.MIN_VALUE;
    private int lastMoveY = Integer.MIN_VALUE;
    private long nextSwingAtMs;

    public CompanionGrindBot(Character character) {
        super(character);
        this.botType = "CompanionGrindBot";
        this.dialoguePath = "";
        this.leaderId = PartyGrindService.leaderIdFor(character.getId());
    }

    @Override
    public void checkPrioritySpeed() {
        updateScheduleDelay(TICK_MS);
    }

    @Override
    public synchronized void startScheduledTask(long initialDelayMs) {
        super.startScheduledTask(Math.min(initialDelayMs, TICK_MS));
        int id = getChr().getId();
        BotTickService.reschedule(id, TICK_MS);
    }

    @Override
    public boolean isAvailableForAmbientActions() {
        return false;
    }

    @Override
    public void updateState() {
        Character chr;
        super.updateState();
        if (checkIfNotRunningOrPaused() || (chr = getChr()) == null || chr.getMap() == null) {
            return;
        }
        if (getState() == BotState.TRADING) {
            return;
        }
        Character leader = resolveLeader();
        if (leader == null || leader.getMap() == null) {
            PartyGrindService.dismiss(this.leaderId);
            stopScheduledTask();
            return;
        }
        Party party = leader.getParty();
        if (party == null || chr.getParty() == null || party.getId() != chr.getParty().getId()) {
            leader.stopPartyGrindCompanions("组队已解散，基友集合结束。");
            return;
        }
        if (chr.getMapId() != leader.getMapId()) {
            Point dest = PartyGrindService.stationFor(chr, leader);
            if (dest == null) {
                dest = leader.getPosition();
            }
            try {
                chr.changeMap(leader.getMap(), dest);
                lastMoveX = Integer.MIN_VALUE;
            } catch (Exception ignored) {
                return;
            }
            return;
        }
        GCMovement.setGrinding(chr, true);
        Point station = PartyGrindService.stationFor(chr, leader);
        Monster target = PartyGrindService.huntMobFor(chr, leader);
        if (target != null) {
            Point mobPos = target.getPosition();
            int dx = Math.abs(chr.getPosition().x - mobPos.x);
            int dy = Math.abs(chr.getPosition().y - mobPos.y);
            if (dx <= ENGAGE_X && dy <= ENGAGE_Y) {
                GCMovement.stop(chr);
                lastMoveX = Integer.MIN_VALUE;
                if (System.currentTimeMillis() >= nextSwingAtMs) {
                    swingAndHit(chr, target);
                }
                return;
            }
            approach(chr, mobPos);
            return;
        }
        if (station != null && !PartyGrindService.onAssignedFloor(chr)) {
            approach(chr, station);
            return;
        }
        if (station != null && Math.abs(chr.getPosition().x - leader.getPosition().x) > LEASH_X) {
            approach(chr, station);
        }
    }

    private void approach(Character chr, Point dest) {
        if (chr.getMap() == null || dest == null) {
            return;
        }
        if (Math.abs(dest.x - lastMoveX) < MOVE_EPS && Math.abs(dest.y - lastMoveY) < MOVE_EPS
                && GCMovement.isMoving(chr)) {
            return;
        }
        lastMoveX = dest.x;
        lastMoveY = dest.y;
        GCMovement.move(chr, dest.x, dest.y);
    }

    private void swingAndHit(Character chr, Monster target) {
        if (chr.getMap() == null || !target.isAlive()) {
            return;
        }
        int damage = BotDamageModel.lineDamage(
                chr.getJob().getJobTier(),
                chr.getLevel(),
                target.getMaxHp()
        );
        if (target.getPosition().x < chr.getPosition().x) {
            GCMovement.face(chr, true);
        } else {
            GCMovement.face(chr, false);
        }
        BotAttack.grindHit(chr, target, damage);
        chr.getMap().damageMonster(chr, target, damage);
        nextSwingAtMs = System.currentTimeMillis() + SWING_CD_MS;
    }

    private Character resolveLeader() {
        if (this.leaderId <= 0) {
            this.leaderId = PartyGrindService.leaderIdFor(getChr().getId());
        }
        if (this.leaderId <= 0 || getChr().getClient() == null) {
            return null;
        }
        Character lead = getChr().getClient().getChannelServer().getPlayerStorage().getCharacterById(this.leaderId);
        if (lead != null && !BotHelpers.isBot(lead)) {
            return lead;
        }
        return null;
    }
}
