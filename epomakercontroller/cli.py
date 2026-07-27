# src/epomakercontroller/cli.py
"""Simple CLI for the EpomakerController package."""

import click
import tkinter as tk

from .commands.data.constants import Profile
from .configs.configs import load_main_config
from .epomakercontroller import EpomakerController
from .utils.sensors import print_temp_devices
from .utils.keyboard_gui import RGBKeyboardGUI

CONFIG_MAIN = load_main_config()


@click.group()
def cli() -> None:
    """A simple CLI for the EpomakerController."""
    pass


@cli.command()
@click.argument("image_path", type=click.Path(exists=True))
@click.option("--delay", default=100, type=int, help="Frame delay in milliseconds (for animations/GIFs).")
def upload_image(image_path: str, delay: int) -> None:
    """Upload an image or GIF to the Epomaker device.

    Args:
        image_path (str): The path to the image file to upload.
        delay (int): Frame delay in milliseconds for animations.
    """
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if controller.open_device():
            print(
                "Uploading, you should see the status on the keyboard screen.\n"
                "The keyboard will be unresponsive during this process."
            )
            controller.send_image(image_path, delay_ms=delay)
            click.echo("Image uploaded successfully.")
    except Exception as e:
        click.echo(f"Failed to upload image: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
@click.argument("r", type=int)
@click.argument("g", type=int)
@click.argument("b", type=int)
def set_rgb_all_keys(r: int, g: int, b: int) -> None:
    """Set RGB colour for all keys.

    Args:
        r (int): The red value (0-255).
        g (int): The green value (0-255).
        b (int): The blue value (0-255).
    """
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if controller.open_device():
            controller.set_rgb_all_keys(r, g, b)
            click.echo(f"All keys set to RGB({r}, {g}, {b}) successfully.")
    except Exception as e:
        click.echo(f"Failed to set RGB for all keys: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
@click.argument("r", type=int)
@click.argument("g", type=int)
@click.argument("b", type=int)
@click.option("--mode", default="ALWAYS_ON", type=click.Choice([m.name for m in Profile.Mode]))
def set_profile(r: int, g: int, b: int, mode: str) -> None:
    """Set the permanent keyboard lighting profile and color.

    Args:
        r (int): Red value (0-255).
        g (int): Green value (0-255).
        b (int): Blue value (0-255).
        mode (str): Backlight profile mode name.
    """
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if controller.open_device():
            profile_mode = Profile.Mode[mode]
            profile = Profile(
                mode=profile_mode,
                speed=Profile.Speed.DEFAULT,
                brightness=Profile.Brightness.DEFAULT,
                dazzle=Profile.Dazzle.OFF,
                option=Profile.Option.OFF,
                rgb=(r, g, b),
            )
            controller.set_profile(profile)
            click.echo(f"Profile set to {mode} with RGB({r}, {g}, {b}) successfully.")
    except Exception as e:
        click.echo(f"Failed to set profile: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
def cycle_light_modes() -> None:
    """Cycle through the light modes."""
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if not controller.open_device():
            click.echo("Failed to open device.")
            return

        print(f"Cycling through {len(Profile.Mode)} modes, waiting 5 seconds on each")
        controller.cycle_light_modes()

        click.echo("Cycled through all light modes successfully.")
    except Exception as e:
        click.echo(f"Failed to cycle light modes: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
def send_time() -> None:
    """Send the current time to the Epomaker device."""
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if controller.open_device():
            controller.send_time()
            click.echo("Time sent successfully.")
    except Exception as e:
        click.echo(f"Failed to send time: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
@click.argument("temperature", type=int)
def send_temperature(temperature: int) -> None:
    """Send temperature to the Epomaker screen.

    Args:
        temperature (int): The temperature value in C (0-100).
    """
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if controller.open_device():
            controller.send_temperature(temperature)
            click.echo("Temperature sent successfully.")
    except Exception as e:
        click.echo(f"Failed to send temperature: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
@click.argument("cpu", type=int)
def send_cpu(cpu: int) -> None:
    """Send CPU usage percentage to the Epomaker screen.

    Args:
        cpu (int): The CPU usage percentage (0-100).
    """
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if controller.open_device():
            controller.send_cpu(cpu)
            click.echo("CPU usage sent successfully.")
    except Exception as e:
        click.echo(f"Failed to send CPU usage: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
@click.option(
    "--test",
    "test_mode",
    is_flag=True,
    help="Start daemon in test mode, sending random data.",
)
@click.argument("temp_key", type=str, required=False)
def start_daemon(temp_key: str | None, test_mode: bool) -> None:
    """Start a daemon to update the CPU usage and optionally a temperature.

    Args:
        temp_key (str): A label corresponding to the device to monitor.
        test_mode (bool): Send random ints instead of real values.
    """
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if not controller.open_device():
            click.echo("Failed to open device.")
            return
        controller.start_daemon(temp_key, test_mode)

    except KeyboardInterrupt:
        click.echo("Daemon interrupted by user.")
    except Exception as e:
        click.echo(f"Error in start-daemon: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
def list_temp_devices() -> None:
    """List available temperature devices."""
    print_temp_devices()


@cli.command()
@click.option(
    "--print",
    "print_info",
    is_flag=True,
    help="Print all available information about the connected keyboard.",
)
@click.option(
    "--udev",
    "generate_udev",
    is_flag=True,
    help="Generate a udev rule for the connected keyboard.",
)
def dev(print_info: bool, generate_udev: bool) -> None:
    """Various dev tools.

    Args:
        print_info (bool): Print information about the connected keyboard.
        generate_udev (bool): Generate a udev rule for the connected keyboard.
    """
    try:
        if print_info:
            click.echo("Printing all available information about the connected keyboard.")
            controller = EpomakerController(CONFIG_MAIN)
            if not controller.open_device(only_info=True):
                click.echo("Failed to open device.")
                return
        elif generate_udev:
            click.echo("Generating udev rule for the connected keyboard.")
            # Init controller to get the PID
            controller = EpomakerController(CONFIG_MAIN)
            if not controller.open_device(only_info=True):
                click.echo("Failed to open device.")
                return
            controller.generate_udev_rule()
        else:
            click.echo("No dev tool specified.")
    except Exception as e:
        click.echo(f"Dev tool failed: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


def run_set_keys_flow(saved_colours: dict = None) -> tuple[str | None, dict]:
    import threading
    import time

    controller = EpomakerController(CONFIG_MAIN)
    if not controller.open_device():
        print("Failed to open device.")
        return None, saved_colours or {}

    root = tk.Tk()
    next_action = None
    running = True

    def on_switch(window):
        nonlocal next_action, running
        next_action = "screen"
        running = False
        if thread.is_alive():
            thread.join(timeout=0.5)
        controller.close_device()
        window.destroy()

    gui = RGBKeyboardGUI(
        root, lambda x: None, controller.config_layout, controller.config_keymap,
        switch_callback=on_switch, controller=controller, initial_colours=saved_colours
    )

    def rgb_send_loop() -> None:
        last_colors = None

        while running:
            if not running or controller.device is None:
                break

            # Keep keyboard lighting presets active unless the user is actively customizing
            if not gui.custom_mode_active:
                last_colors = None  # Reset so it re-applies if custom mode is reactivated
                time.sleep(0.1)
                continue

            try:
                # Snapshot the live frame under its lock so the GUI thread can
                # keep mutating it while we build + send without a torn update.
                snap_frame = gui.snapshot_frame()
                current_colors = tuple(snap_frame.key_map.key_map.values())
            except Exception:
                current_colors = None
                snap_frame = None

            if not running or controller.device is None:
                break

            if current_colors is not None and current_colors != last_colors:
                try:
                    # Paced multi-packet send (erase delay + 10 ms packet pace)
                    controller.send_keys([snap_frame])
                except Exception as e:
                    gui.report_status(f"Device: error - {e}")
                else:
                    gui.report_status("Device: connected")
                last_colors = current_colors

            time.sleep(0.1)

    thread = threading.Thread(target=rgb_send_loop, daemon=True)
    thread.start()

    def on_close() -> None:
        nonlocal running
        running = False
        if thread.is_alive():
            thread.join(timeout=0.5)
        controller.close_device()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

    current_colours_dict = {k.name: v for k, v in gui.key_colours.items() if v is not None}
    return next_action, current_colours_dict


def run_screen_designer_flow(saved_state: dict = None) -> tuple[str | None, dict]:
    from .utils import screen_designer_gui
    root = tk.Tk()
    next_action = None

    def on_switch(window):
        nonlocal next_action
        next_action = "keys"
        # Match on_close: stop preview playback and release the device so the
        # keys flow can reopen it cleanly.
        if app.is_playing:
            app.is_playing = False
        app.controller.close_device()
        window.destroy()

    app = screen_designer_gui.ScreenDesignerApp(root, switch_callback=on_switch)
    if saved_state and saved_state.get("frames"):
        app.base_frames = saved_state["base_frames"]
        app.frames = saved_state["frames"]
        app.delay_ms = saved_state["delay_ms"]
        app.bright_scale.set(saved_state["brightness"])
        app.contrast_scale.set(saved_state["contrast"])
        app.sat_scale.set(saved_state["saturation"])
        app.update_canvas()
        app.update_frame_indicators()

    def on_close():
        if app.is_playing:
            app.is_playing = False
        app.controller.close_device()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

    current_state = {
        "base_frames": app.base_frames,
        "frames": app.frames,
        "delay_ms": app.delay_ms,
        "brightness": app.brightness_val,
        "contrast": app.contrast_val,
        "saturation": app.saturation_val,
    }
    return next_action, current_state


def start_gui_flow(initial_mode: str) -> None:
    current_mode = initial_mode
    saved_colours = {}
    saved_screen_state = {}

    while current_mode is not None:
        if current_mode == "keys":
            next_mode, saved_colours = run_set_keys_flow(saved_colours)
            current_mode = next_mode
        elif current_mode == "screen":
            next_mode, saved_screen_state = run_screen_designer_flow(saved_screen_state)
            current_mode = next_mode
        else:
            current_mode = None


@cli.command()
def set_keys() -> None:
    """Open a simple GUI to set individual key colours."""
    start_gui_flow("keys")


@cli.command()
@click.argument("key_index", type=int)
@click.argument("key_combo", type=int)
def remap_keys(key_index: int, key_combo: int) -> None:
    """Remap key functionality using a KeyboardKey index (from) and a USB HID index (to)"""
    try:
        controller = EpomakerController(CONFIG_MAIN)
        if controller.open_device():
            controller.remap_keys(key_index, key_combo)
    except Exception as e:
        click.echo(f"Failed to remap keys: {e}")
    finally:
        if "controller" in locals():
            controller.close_device()


@cli.command()
@click.option("--filter", default=None, help="Filter the keymap by key name")
def show_keymap(filter: str | None) -> None:
    from .exceptions import ConfigError

    controller = EpomakerController(CONFIG_MAIN, dry_run=True)
    data = controller.config_keymap.data
    if data is None:
        raise ConfigError("Config has no data")

    to_show = list(data)
    if filter:
        to_show = [item for item in data if filter.lower() in item["name"].lower()]

    for item in to_show:
        print(f"{item['name']}: {item['value']}")


@cli.command()
def screen_designer() -> None:
    """Launch the interactive 60x9 screen designer and animator."""
    start_gui_flow("screen")


if __name__ == "__main__":
    cli()
