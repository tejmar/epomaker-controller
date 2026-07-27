# src/epomakercontroller/cli.py
"""Simple CLI for the EpomakerController package."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import click
import tkinter as tk

from .commands.data.constants import Profile
from .configs.configs import load_main_config
from .epomakercontroller import EpomakerController
from .exceptions import DeviceNotOpenError, EpomakerError
from .utils.sensors import print_temp_devices
from .utils.keyboard_gui import RGBKeyboardGUI

CONFIG_MAIN = load_main_config()


@contextmanager
def open_controller(
    *,
    dry_run: bool = False,
    only_info: bool = False,
    install_signal_handlers: bool = False,
) -> Iterator[EpomakerController]:
    """Open a controller and always close it on exit.

    Yields an open :class:`EpomakerController`. On failure to open, raises
    :class:`DeviceNotOpenError` (or other controller errors).
    """
    controller = EpomakerController(
        CONFIG_MAIN,
        dry_run=dry_run,
        install_signal_handlers=install_signal_handlers,
    )
    with controller:
        if not controller.open_device(only_info=only_info):
            raise DeviceNotOpenError("Failed to open device.")
        yield controller


def _run_with_device(
    action: Callable[[EpomakerController], None],
    *,
    success: str | None = None,
    error_prefix: str = "Command failed",
    only_info: bool = False,
    install_signal_handlers: bool = False,
    dry_run: bool = False,
) -> None:
    """Run *action* against an opened device; print success or error."""
    try:
        with open_controller(
            dry_run=dry_run,
            only_info=only_info,
            install_signal_handlers=install_signal_handlers,
        ) as controller:
            action(controller)
            if success:
                click.echo(success)
    except (EpomakerError, OSError, ValueError) as e:
        click.echo(f"{error_prefix}: {e}")
    except Exception as e:  # unexpected — still report cleanly for CLI users
        click.echo(f"{error_prefix}: {e}")


@click.group()
def cli() -> None:
    """A simple CLI for the EpomakerController."""
    pass


@cli.command()
@click.argument("image_path", type=click.Path(exists=True))
@click.option(
    "--delay",
    default=100,
    type=int,
    help="Frame delay in milliseconds (for animations/GIFs).",
)
def upload_image(image_path: str, delay: int) -> None:
    """Upload an image or GIF to the Epomaker device."""

    def _action(controller: EpomakerController) -> None:
        print(
            "Uploading, you should see the status on the keyboard screen.\n"
            "The keyboard will be unresponsive during this process."
        )
        controller.send_image(image_path, delay_ms=delay)

    _run_with_device(
        _action,
        success="Image uploaded successfully.",
        error_prefix="Failed to upload image",
    )


@cli.command()
@click.argument("r", type=int)
@click.argument("g", type=int)
@click.argument("b", type=int)
def set_rgb_all_keys(r: int, g: int, b: int) -> None:
    """Set RGB colour for all keys."""
    _run_with_device(
        lambda c: c.set_rgb_all_keys(r, g, b),
        success=f"All keys set to RGB({r}, {g}, {b}) successfully.",
        error_prefix="Failed to set RGB for all keys",
    )


@cli.command()
@click.argument("r", type=int)
@click.argument("g", type=int)
@click.argument("b", type=int)
@click.option(
    "--mode",
    default="ALWAYS_ON",
    type=click.Choice([m.name for m in Profile.Mode]),
)
def set_profile(r: int, g: int, b: int, mode: str) -> None:
    """Set the permanent keyboard lighting profile and color."""

    def _action(controller: EpomakerController) -> None:
        profile = Profile(
            mode=Profile.Mode[mode],
            speed=Profile.Speed.DEFAULT,
            brightness=Profile.Brightness.DEFAULT,
            dazzle=Profile.Dazzle.OFF,
            option=Profile.Option.OFF,
            rgb=(r, g, b),
        )
        controller.set_profile(profile)

    _run_with_device(
        _action,
        success=f"Profile set to {mode} with RGB({r}, {g}, {b}) successfully.",
        error_prefix="Failed to set profile",
    )


@cli.command()
def cycle_light_modes() -> None:
    """Cycle through the light modes."""

    def _action(controller: EpomakerController) -> None:
        print(
            f"Cycling through {len(Profile.Mode)} modes, waiting 5 seconds on each"
        )
        controller.cycle_light_modes()

    _run_with_device(
        _action,
        success="Cycled through all light modes successfully.",
        error_prefix="Failed to cycle light modes",
    )


@cli.command()
def send_time() -> None:
    """Send the current time to the Epomaker device."""
    _run_with_device(
        lambda c: c.send_time(),
        success="Time sent successfully.",
        error_prefix="Failed to send time",
    )


@cli.command()
@click.argument("temperature", type=int)
def send_temperature(temperature: int) -> None:
    """Send temperature to the Epomaker screen."""
    _run_with_device(
        lambda c: c.send_temperature(temperature),
        success="Temperature sent successfully.",
        error_prefix="Failed to send temperature",
    )


@cli.command()
@click.argument("cpu", type=int)
def send_cpu(cpu: int) -> None:
    """Send CPU usage percentage to the Epomaker screen."""
    _run_with_device(
        lambda c: c.send_cpu(cpu),
        success="CPU usage sent successfully.",
        error_prefix="Failed to send CPU usage",
    )


@cli.command()
@click.option(
    "--test",
    "test_mode",
    is_flag=True,
    help="Start daemon in test mode, sending random data.",
)
@click.argument("temp_key", type=str, required=False)
def start_daemon(temp_key: str | None, test_mode: bool) -> None:
    """Start a daemon to update the CPU usage and optionally a temperature."""
    try:
        with open_controller(install_signal_handlers=True) as controller:
            controller.start_daemon(temp_key, test_mode)
    except KeyboardInterrupt:
        click.echo("Daemon interrupted by user.")
    except Exception as e:
        click.echo(f"Error in start-daemon: {e}")


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
    """Various dev tools."""
    if not print_info and not generate_udev:
        click.echo("No dev tool specified.")
        return

    try:
        with open_controller(only_info=True) as controller:
            if print_info:
                click.echo(
                    "Printing all available information about the connected keyboard."
                )
                # open_device(only_info=True) already printed via controller path
            if generate_udev:
                click.echo("Generating udev rule for the connected keyboard.")
                controller.generate_udev_rule()
    except Exception as e:
        click.echo(f"Dev tool failed: {e}")


def run_set_keys_flow(saved_colours: dict | None = None) -> tuple[str | None, dict]:
    import threading
    import time

    controller = EpomakerController(CONFIG_MAIN)
    with controller:
        if not controller.open_device():
            print("Failed to open device.")
            return None, saved_colours or {}

        root = tk.Tk()
        next_action = None
        running = True

        def on_switch(window: tk.Tk) -> None:
            nonlocal next_action, running
            next_action = "screen"
            running = False
            if thread.is_alive():
                thread.join(timeout=0.5)
            controller.close_device()
            window.destroy()

        gui = RGBKeyboardGUI(
            root,
            lambda x: None,
            controller.config_layout,
            controller.config_keymap,
            switch_callback=on_switch,
            controller=controller,
            initial_colours=saved_colours,
        )

        def rgb_send_loop() -> None:
            last_colors = None

            while running:
                if not running or controller.device is None:
                    break

                # Keep keyboard lighting presets active unless customizing
                if not gui.custom_mode_active:
                    last_colors = None
                    time.sleep(0.1)
                    continue

                try:
                    snap_frame = gui.snapshot_frame()
                    current_colors = tuple(snap_frame.key_map.key_map.values())
                except Exception:
                    current_colors = None
                    snap_frame = None

                if not running or controller.device is None:
                    break

                if current_colors is not None and current_colors != last_colors:
                    try:
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

        current_colours_dict = {
            k.name: v for k, v in gui.key_colours.items() if v is not None
        }
        return next_action, current_colours_dict


def run_screen_designer_flow(
    saved_state: dict | None = None,
) -> tuple[str | None, dict]:
    from .utils import screen_designer_gui

    root = tk.Tk()
    next_action = None

    def on_switch(window: tk.Tk) -> None:
        nonlocal next_action
        next_action = "keys"
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

    def on_close() -> None:
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
    current_mode: str | None = initial_mode
    saved_colours: dict = {}
    saved_screen_state: dict = {}

    while current_mode is not None:
        if current_mode == "keys":
            next_mode, saved_colours = run_set_keys_flow(saved_colours)
            current_mode = next_mode
        elif current_mode == "screen":
            next_mode, saved_screen_state = run_screen_designer_flow(
                saved_screen_state
            )
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
    """Remap key functionality using a KeyboardKey index (from) and a USB HID index (to)."""
    _run_with_device(
        lambda c: c.remap_keys(key_index, key_combo),
        error_prefix="Failed to remap keys",
    )


@cli.command()
@click.option("--filter", default=None, help="Filter the keymap by key name")
def show_keymap(filter: str | None) -> None:
    from .exceptions import ConfigError

    with open_controller(dry_run=True) as controller:
        data = controller.config_keymap.data
        if data is None:
            raise ConfigError("Config has no data")

        to_show = list(data)
        if filter:
            to_show = [
                item
                for item in data
                if filter.lower() in item["name"].lower()
            ]

        for item in to_show:
            print(f"{item['name']}: {item['value']}")


@cli.command()
def screen_designer() -> None:
    """Launch the interactive 60x9 screen designer and animator."""
    start_gui_flow("screen")


@cli.group()
def models() -> None:
    """List and select packaged keyboard models."""
    pass


@models.command("list")
def models_list() -> None:
    """List built-in keyboard models (* marks the current config match)."""
    from .configs.models import format_models_table, list_models, match_model

    config = load_main_config()
    current = match_model(config)
    click.echo(format_models_table(list_models(), current))
    if current is None:
        click.echo(
            "Current config does not match a built-in model "
            f"(layout={config['CONF_LAYOUT_PATH']!r}, "
            f"keymap={config['CONF_KEYMAP_PATH']!r})."
        )


@models.command("show")
def models_show() -> None:
    """Show the model currently selected in the main config."""
    from .configs.models import match_model

    config = load_main_config()
    current = match_model(config)
    click.echo(f"Layout:       {config['CONF_LAYOUT_PATH']}")
    click.echo(f"Keymap:       {config['CONF_KEYMAP_PATH']}")
    click.echo(f"Capabilities: {', '.join(config['CAPABILITIES'])}")
    if current:
        click.echo(f"Model:        {current.id} ({current.name})")
        if current.description:
            click.echo(f"Description:  {current.description}")
    else:
        click.echo("Model:        (custom — not a built-in registry entry)")


@models.command("set")
@click.argument("model_id")
def models_set(model_id: str) -> None:
    """Select a built-in model and write it to the main config.

    MODEL_ID is one of: rt100, dynatab75x, ep64, gamakay-tk68-he
    (see ``epomakercontroller models list``).
    """
    global CONFIG_MAIN
    from .configs.models import apply_model, get_model
    from .exceptions import ConfigError

    try:
        model = get_model(model_id)
        config = load_main_config()
        CONFIG_MAIN = apply_model(config, model.id, save=True)
    except ConfigError as e:
        click.echo(f"Failed to set model: {e}", err=True)
        raise SystemExit(1) from e

    click.echo(f"Model set to {model.id} ({model.name})")
    click.echo(f"  layout:       {model.layout}")
    click.echo(f"  keymap:       {model.keymap}")
    click.echo(f"  capabilities: {', '.join(model.capabilities)}")
    click.echo("Restart any open GUIs to pick up the new model.")


if __name__ == "__main__":
    cli()
