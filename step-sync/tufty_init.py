# Rename this file to __init__.py and place it in /apps/step_sync/ on Tufty.
# Requires sync_app.py, steps.py, and ble_sync.py to already be in /lib.

from sync_app import SyncApp

app = SyncApp(
    my_id=1,             # must be different from the Badger's my_id
    is_eink=False,
    badge=badge,
    screen=screen,
    color=color,
    shape=shape,
    button_a=BUTTON_A,
    button_b=BUTTON_B,
    button_c=BUTTON_C,
)


def init():
    app.on_init()


def update():
    app.on_update()


def on_exit():
    app.on_exit()


run(update)
