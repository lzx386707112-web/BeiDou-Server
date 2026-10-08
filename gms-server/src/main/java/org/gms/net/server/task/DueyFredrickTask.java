/*
    This file is part of the HeavenMS MapleStory Server
    Copyleft (L) 2016 - 2019 RonanLana

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation version 3 as published by
    the Free Software Foundation. You may not use, modify or distribute
    this program under any other version of the GNU Affero General Public
    License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
package org.gms.net.server.task;

import org.gms.client.processor.npc.DueyProcessor;
import org.gms.client.processor.npc.FredrickProcessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * @author Ronan
 */
public class DueyFredrickTask implements Runnable {
    private static final Logger log = LoggerFactory.getLogger(DueyFredrickTask.class);

    private final FredrickProcessor fredrickProcessor;

    public DueyFredrickTask(FredrickProcessor fredrickProcessor) {
        this.fredrickProcessor = fredrickProcessor;
    }

    @Override
    public void run() {
        // Keep the two schedules independent: a failure in the Fredrick pass used to abort
        // the Duey expiration pass as well, silently stalling duey parcel cleanup.
        try {
            fredrickProcessor.runFredrickSchedule();
        } catch (Throwable t) {
            log.error("Error running Fredrick schedule", t);
        }

        DueyProcessor.runDueyExpireSchedule();
    }
}
