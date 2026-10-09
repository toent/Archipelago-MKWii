import asyncio
import logging
import time
from dolphin_memory import DolphinMemoryManager

logger = logging.getLogger("MKWii")

DEATH_Y = -1000.0

POLL_INTERVAL = 0.1
# Poll faster while a received death is in flight so the first timer reading is not late.
FAST_POLL_INTERVAL = 0.01
# Vanilla pickup is 150 frames (2.5 s) and one tenth of a second is 6 frames.
VANILLA_RESPAWN_FRAMES = 150
FRAMES_PER_TENTH = 6
# Must be longer than the delay between the Y write and the pickup starting.
TRAP_WINDOW = 5.0
# A received death is dropped if it cannot be applied within this time.
RECEIVE_TTL = 120.0
# No new received death is applied this soon after any death.
DEATH_COOLDOWN = 5.0


class DeathLinkBridge:
    def __init__(self, send_death, get_mem, respawn_tenths=25):
        # send_death is an async callable taking no arguments.
        # get_mem returns the DolphinMemoryManager while it is hooked and no
        # savestate is loading, otherwise None.
        self.send_death = send_death
        self.get_mem = get_mem
        self.respawn_frames = VANILLA_RESPAWN_FRAMES
        self.set_respawn_time(respawn_tenths)
        self.pending_until = 0.0
        self.suppress_until = 0.0
        self.last_death = 0.0
        self.active = False
        self.last_t = 0

    def set_respawn_time(self, tenths):
        # Pickup length for received deaths, in tenths of a second.
        self.respawn_frames = max(1, min(32767, int(tenths) * FRAMES_PER_TENTH))

    def receive(self):
        # Call from the context's on_deathlink.
        self.pending_until = time.monotonic() + RECEIVE_TTL

    def reset(self):
        # Drop stale race state. A pending received death is kept so it can land in the next race.
        self.active = False
        self.last_t = 0

    def apply_death(self, mem: DolphinMemoryManager):
        # Arm the suppression before the write so the pickup it causes is not sent back.
        self.suppress_until = time.monotonic() + TRAP_WINDOW
        if mem.write_player_y(DEATH_Y):
            return True
        self.suppress_until = 0.0
        return False

    async def poll_once(self, mem: DolphinMemoryManager):
        now = time.monotonic()
        t = mem.read_pre_respawn_timer()
        if t is None:
            self.reset()
            return

        # The timer is 0 in normal driving and set to 150 when Lakitu starts the pickup.
        send = False
        if t > 0 and (not self.active or t > self.last_t):
            self.last_death = now
            if now < self.suppress_until:
                # Caused by a received death: do not echo it, and give it the configured length.
                self.suppress_until = 0.0
                if t != self.respawn_frames and mem.write_pre_respawn_timer(self.respawn_frames):
                    t = self.respawn_frames
            elif mem.race_has_started():
                # Falls outside the live race (intro, or the CPU driving after you finish) are not the player's deaths.
                send = True
        self.active = t > 0
        self.last_t = t
        if send:
            await self.send_death()

        if self.pending_until > now:
            if self.active:
                # Already being picked up, the received death adds nothing.
                self.pending_until = 0.0
            elif (
                now - self.last_death >= DEATH_COOLDOWN
                and mem.race_has_started()
                # Lap is 0 on the grid, so a death there waits until the start line is crossed.
                and mem.read_p1_lap() >= 1
                and mem.read_p1_lap() < 4
            ):
                if self.apply_death(mem):
                    self.last_death = now
                    self.pending_until = 0.0

    async def run(self):
        while True:
            try:
                mem = self.get_mem()
                if mem is not None:
                    await self.poll_once(mem)
                else:
                    self.reset()
            except Exception:
                # A read failed or sending failed, retry on the next tick.
                logger.exception("DeathLink poll failed")
            armed = time.monotonic() < self.suppress_until
            await asyncio.sleep(FAST_POLL_INTERVAL if armed else POLL_INTERVAL)