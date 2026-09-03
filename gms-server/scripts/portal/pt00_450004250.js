function enter(pi) {
    var player = pi.getPlayer();
    var map = player.getMap();
    var destination = map.getPortal(3);
    if (destination == null) {
        return false;
    }
    player.changeMap(map, destination);
    return true;
}
