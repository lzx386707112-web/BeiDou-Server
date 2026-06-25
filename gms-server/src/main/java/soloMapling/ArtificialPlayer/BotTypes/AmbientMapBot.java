package soloMapling.ArtificialPlayer.BotTypes;

import org.gms.client.Character;
import soloMapling.ArtificialPlayer.BotSM;

import java.awt.Point;
import java.util.concurrent.ThreadLocalRandom;

import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotEmote;
import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotSpeak;
import static soloMapling.ArtificialPlayer.BotHelpers.sleepAmountSeconds;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.BotMoveSmallDistanceX;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botFaceTowardsPoint;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.microTurnAround;

public class AmbientMapBot extends BotSM {
    private static final String[] AMBIENT_LINES = {
            "有人一起打吗？",
            "这个图还挺舒服的。",
            "刚才卡了一下。",
            "我去旁边看看。",
            "今天爆率怎么样？",
            "有人做任务吗？",
            "先在这边练一会儿。",
            "路过路过。",
            "这里人还不少。",
            "等会儿去自由市场看看。"
    };

    private long nextActionAt = 0;

    public AmbientMapBot(Character chr) {
        super(chr);
        dialoguePath = "";
        botType = "AmbientMapBot";
        scheduleNextAction();
    }

    @Override
    public void updateState() {
        super.updateState();
        if (checkIfNotRunningOrPaused()) {
            return;
        }
        if (System.currentTimeMillis() < nextActionAt) {
            return;
        }

        runAmbientAction();
        scheduleNextAction();
    }

    @Override
    public void checkPrioritySpeed() {
        if (checkMainPlayersOnMap()) {
            updateScheduleDelay(1800 + ThreadLocalRandom.current().nextInt(2200));
            return;
        }
        updateScheduleDelay(8000);
    }

    private void runAmbientAction() {
        int roll = ThreadLocalRandom.current().nextInt(100);
        if (roll < 68) {
            stroll();
        } else if (roll < 82) {
            faceNearbyPlayerOrTurn();
        } else if (roll < 93) {
            BotEmote(getChr());
        } else {
            BotSpeak(getChr(), AMBIENT_LINES[ThreadLocalRandom.current().nextInt(AMBIENT_LINES.length)]);
        }
    }

    private void stroll() {
        int steps = ThreadLocalRandom.current().nextInt(1, 4);
        int direction = ThreadLocalRandom.current().nextBoolean() ? 1 : -1;
        for (int i = 0; i < steps; i++) {
            int distance = ThreadLocalRandom.current().nextInt(70, 181) * direction;
            Point pos = getChr().getPosition();
            BotMoveSmallDistanceX(getChr(), new Point(pos.x + distance, pos.y));
            if (i + 1 < steps && !sleepAmountSeconds(500 + ThreadLocalRandom.current().nextInt(900))) {
                return;
            }
        }
    }

    private void faceNearbyPlayerOrTurn() {
        Character target = null;
        int bestDistance = Integer.MAX_VALUE;
        for (Character other : getChr().getMap().getAllPlayers()) {
            if (other.getId() == getChr().getId() || other.getId() > 20000 || other.getId() == 999) {
                continue;
            }
            int distance = Math.abs(other.getPosition().x - getChr().getPosition().x);
            if (distance < bestDistance) {
                bestDistance = distance;
                target = other;
            }
        }
        if (target != null && bestDistance < 500) {
            botFaceTowardsPoint(getChr(), target.getPosition());
        } else {
            microTurnAround(getChr());
        }
    }

    private void scheduleNextAction() {
        nextActionAt = System.currentTimeMillis() + ThreadLocalRandom.current().nextLong(2000, 5001);
    }
}
