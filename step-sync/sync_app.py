# sync_app.py — shared drawing + event logic for the step/status sync app.
# Both badges' __init__.py import this and just wire up a few parameters.
#
# Copy this to /lib on BOTH badges (via Thonny's Files panel, not disk mode),
# alongside steps.py and ble_sync.py.
#
# Note: screen/badge/color/shape/BUTTON_* are passed in explicitly rather
# than assumed as globals in this file, since this module is imported
# rather than being the app's own __init__.py.

import time
import steps
import ble_sync

STATUSES = ble_sync.STATUSES

_HEARTBEAT_MS = 60_000  # re-broadcast at least this often even with no new message
_ADV_BURST_MS = 1_500   # how long we advertise after each send, before going quiet


class SyncApp:
    def __init__(self, my_id, is_eink, badge, screen, color, shape,
                 button_a, button_b, button_c):
        self.my_id = my_id
        self.is_eink = is_eink
        self.badge = badge
        self.screen = screen
        self.color = color
        self.shape = shape
        self.BUTTON_A = button_a
        self.BUTTON_B = button_b
        self.BUTTON_C = button_c

        self.sync = ble_sync.BadgeSync(my_id)

        self.selected = 0          # index into STATUSES, currently highlighted
        self.last_sent_status = 0  # index actually broadcast last

        self.last_heartbeat = time.ticks_ms()
        self.advertising_until = None

        self._last_peer_seen = None  # used to notice new peer packets, for e-ink redraw gating
        self.needs_redraw = True     # always draw at least once

        # Raw pin state for our own press-edge detection — badge.pressed()
        # depends on internal polling that behaves differently on Badger,
        # so we read BUTTON_X.value() directly instead (0 = pressed).
        self._prev_a = 1
        self._prev_b = 1
        self._prev_c = 1

        if is_eink:
            self.COLOR_MINE = (0, 0, 0)          # solid black
            self.COLOR_THEIRS = (150, 150, 150)  # mid grey (auto-quantised by the firmware)
            self.COLOR_BG = (255, 255, 255)
            self.COLOR_TEXT = (0, 0, 0)
            self.TEXT_SCALE = 2                  # e-ink needs bigger text to read well
        else:
            self.COLOR_MINE = (90, 150, 230)     # blue
            self.COLOR_THEIRS = (235, 140, 60)   # orange
            self.COLOR_BG = (20, 20, 25)
            self.COLOR_TEXT = (255, 255, 255)
            self.TEXT_SCALE = 1

        self._line_h = 14 * self.TEXT_SCALE

    # --- lifecycle -------------------------------------------------

    def on_init(self):
        pass  # BadgeSync is already advertising/scanning from its own __init__

    def on_exit(self):
        self.sync.stop_broadcast()

    # --- per-frame update --------------------------------------------

    def on_update(self):
        now = time.ticks_ms()
        badge = self.badge

        a_raw = self.BUTTON_A.value()
        b_raw = self.BUTTON_B.value()
        c_raw = self.BUTTON_C.value()

        a_pressed = a_raw == 0 and self._prev_a == 1
        b_pressed = b_raw == 0 and self._prev_b == 1
        c_pressed = c_raw == 0 and self._prev_c == 1

        self._prev_a, self._prev_b, self._prev_c = a_raw, b_raw, c_raw

        if a_pressed:
            self.selected = (self.selected - 1) % len(STATUSES)
            self.needs_redraw = True
        if c_pressed:
            self.selected = (self.selected + 1) % len(STATUSES)
            self.needs_redraw = True
        if b_pressed:
            self._send(self.selected, now)

        # periodic heartbeat if nothing's been sent in a while
        if time.ticks_diff(now, self.last_heartbeat) >= _HEARTBEAT_MS:
            self._send(self.last_sent_status, now)

        # stop advertising once the burst window's up
        if self.advertising_until is not None and time.ticks_diff(now, self.advertising_until) >= 0:
            self.sync.stop_broadcast()
            self.advertising_until = None

        # notice new data from the peer
        if self.sync.peer_last_seen != self._last_peer_seen:
            self._last_peer_seen = self.sync.peer_last_seen
            self.needs_redraw = True

        if not self.is_eink:
            self._draw()               # Tufty redraws every frame regardless
        elif self.needs_redraw:
            self._draw()
            badge.update()             # Badger only pays the e-ink refresh cost here
            self.needs_redraw = False

    def _send(self, status_index, now):
        self.last_sent_status = status_index
        self.sync.broadcast(status_index, steps.get_steps())
        self.advertising_until = time.ticks_add(now, _ADV_BURST_MS)
        self.last_heartbeat = now
        self.needs_redraw = True

    # --- drawing -----------------------------------------------------

    def _draw(self):
        screen = self.screen
        w, h = screen.width, screen.height
        right_margin = int(w * 0.12)  # reserved for UP/DOWN, unassigned for now
        content_w = w - right_margin

        lh = self._line_h
        hint_h = 14  # button hints are always drawn small, regardless of TEXT_SCALE
        top_h = 4 + lh + 4 + 14           # header row + a plain bar strip
        bottom_h = 4 + lh + 4 + hint_h + 4  # selected message + hint row, sized to fit both
        mid_h = h - top_h - bottom_h

        screen.pen = self.color.rgb(*self.COLOR_BG)
        screen.clear()

        self._draw_bar(0, 0, content_w, top_h)
        self._draw_log(0, top_h, content_w, mid_h)
        self._draw_picker(0, h - bottom_h, content_w, bottom_h)

    def _draw_bar(self, x, y, w, h):
        screen = self.screen
        my_steps = steps.get_steps()
        peer_steps = self.sync.peer_steps or 0

        # Labels get their own row against the plain background — never
        # drawn on top of the coloured fill, so contrast is always safe.
        label_h = self._line_h + 4
        bar_y = y + label_h
        bar_h = max(h - label_h, 4)

        screen.pen = self.color.rgb(*self.COLOR_TEXT)
        left_label = "YOU {}".format(my_steps)
        screen.text(left_label, x + 4, y + 2, self.TEXT_SCALE)

        right_label = "THEM {}".format(peer_steps) if self.sync.peer_steps is not None else "THEM ?"
        rw = screen.measure_text(right_label)[0] * self.TEXT_SCALE
        screen.text(right_label, x + w - rw - 4, y + 2, self.TEXT_SCALE)

        total = my_steps + peer_steps
        my_w = (w // 2) if total <= 0 else int(w * my_steps / total)

        screen.pen = self.color.rgb(*self.COLOR_MINE)
        screen.shape(self.shape.rectangle(x, bar_y, my_w, bar_h))
        screen.pen = self.color.rgb(*self.COLOR_THEIRS)
        screen.shape(self.shape.rectangle(x + my_w, bar_y, w - my_w, bar_h))

    def _draw_log(self, x, y, w, h):
        screen = self.screen
        screen.pen = self.color.rgb(*self.COLOR_TEXT)
        lh = self._line_h

        screen.text("You: {}".format(STATUSES[self.last_sent_status]), x + 4, y + 2, self.TEXT_SCALE)

        if self.sync.peer_status is not None:
            them_text = "Them: {}".format(STATUSES[self.sync.peer_status])
        else:
            them_text = "Them: no signal"
        screen.text(them_text, x + 4, y + 2 + lh, self.TEXT_SCALE)

        secs = self.sync.seconds_since_peer_update()
        age_text = "Never heard" if secs is None else "{}s ago".format(secs)
        screen.text(age_text, x + 4, y + 2 + lh * 2, self.TEXT_SCALE)

    def _draw_picker(self, x, y, w, h):
        screen = self.screen
        lh = self._line_h
        hint_scale = 1  # hints stay small/fixed so they can't crowd the message above

        label = STATUSES[self.selected]
        tw = screen.measure_text(label)[0] * self.TEXT_SCALE
        screen.text(label, x + (w - tw) // 2, y + 4, self.TEXT_SCALE)

        hint_y = y + 4 + lh + 4  # placed right after the message row, not anchored to the bottom
        screen.text("<A", x + 4, hint_y, hint_scale)
        b_text = "B:SEND"
        bw = screen.measure_text(b_text)[0] * hint_scale
        screen.text(b_text, x + (w - bw) // 2, hint_y, hint_scale)
        c_text = "C>"
        cw = screen.measure_text(c_text)[0] * hint_scale
        screen.text(c_text, x + w - cw - 4, hint_y, hint_scale)
