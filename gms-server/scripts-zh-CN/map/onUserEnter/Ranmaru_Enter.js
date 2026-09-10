function start(ms) {
    var player = ms.getPlayer();
    if (player == null) {
        return;
    }
    player.dropMessage(5, "森兰丸的气息笼罩了祭坛。");
}
