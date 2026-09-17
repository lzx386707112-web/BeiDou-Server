package soloMapling.ArtificialPlayer.BotFlavorSystem;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotFlavorSystem/FlavorAction.class */
public enum FlavorAction {
    EMOTE(5),
    BUFF_FLEX(3),
    SKILL_SWING(3);

    public final int weight;

    FlavorAction(int weight) {
        this.weight = weight;
    }
}
