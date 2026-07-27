"""EpomakerController module.

This module contains the EpomakerController class, which represents a controller
for an Epomaker USB HID device.
"""

import dataclasses
from datetime import datetime
from json import dumps
import os
import time
from typing import Any, Callable, Optional
import hid  # type: ignore[import-not-found]
import signal
import subprocess
from types import FrameType
import re
import threading

from .utils.sensors import get_cpu_usage, get_device_temp
from .utils.time_helper import TimeHelper
from .utils.keyboard_keys import KeyboardKeys

from .commands import (
    EpomakerCommand,
    EpomakerImageCommand,
    EpomakerRemapKeysCommand,
    EpomakerTimeCommand,
    EpomakerTempCommand,
    EpomakerCpuCommand,
    EpomakerKeyRGBCommand,
    EpomakerProfileCommand,
)
from .commands.data.constants import BUFF_LENGTH, Profile
from .configs.configs import Config, ConfigType


class EpomakerController:
    """EpomakerController class represents a controller for an Epomaker USB HID device.

    Attributes:
        vendor_id (int): The vendor ID of the USB HID device.
        product_id (int): The product ID of the USB HID device.
        device (hid.device): The HID device object.
        dry_run (bool): Whether to run in dry run mode.

    Methods:
        open_device: Opens the USB HID device and prints device information.
        send_basic_command: Sends a command to the HID device.
        close_device: Closes the USB HID device.
        format_current_time: Gets the current time and formats it into the required
            byte string format.
    """

    def __init__(
        self,
        config_main: Config,
        dry_run: bool = False,
    ) -> None:
        """Initializes the EpomakerController object.

        Args:
            vendor_id (int): The vendor ID of the USB HID device.
            dry_run (bool): Whether to run in dry run mode (default: False).
        """

        self.config_layout = Config(
            ConfigType.CONF_LAYOUT, config_main.data["CONF_LAYOUT_PATH"]  # type: ignore
        )
        self.config_keymap = Config(
            ConfigType.CONF_KEYMAP, config_main.data["CONF_KEYMAP_PATH"]  # type: ignore
        )

        self.vendor_id = config_main["VENDOR_ID"]
        self.use_wireless = config_main["USE_WIRELESS"]
        self.product_ids: list[int] = (
            config_main["PRODUCT_IDS_WIRED"]
            if not self.use_wireless
            else config_main["PRODUCT_IDS_24G"]
        )
        self.device_description = config_main["DEVICE_DESCRIPTION_REGEX"]
        self.device = hid.device()
        self.lock = threading.Lock()
        self.dry_run = dry_run
        self.device_list: list[dict[str, Any]] = []
        print(
            """WARNING: If this program errors out or you cancel early, the keyboard
              may become unresponsive. It should work fine again if you unplug and plug
               it back in!"""
        )

        # Set up signal handling
        self._setup_signal_handling()

    def _setup_signal_handling(self) -> None:
        """Sets up signal handling to close the HID device on termination."""
        signal.signal(signal.SIGINT, self._signal_handler)  # Handle Ctrl+C
        signal.signal(signal.SIGTERM, self._signal_handler)  # Handle termination

    def _signal_handler(self, sig: int, frame: Optional[FrameType]) -> None:
        """Handles signals to ensure the HID device is closed."""
        self.close_device()
        os._exit(0)  # Exit immediately after closing the device

    def __del__(self) -> None:
        """Destructor to ensure the device is closed."""
        self.close_device()

    def open_device(self, only_info: bool = False) -> bool:
        """Opens the USB HID device and prints device information.

        Args:
            only_info (bool): Print device information and exit (default: False).

        Raises:
            ValueError: If no device is found with the specified interface number.

        Returns:
            bool: True if the device is opened successfully, False otherwise.
        """
        if self.dry_run:
            print("Dry run: skipping device open")
            return True

        product_id = self._find_product_id()
        if not product_id:
            raise ValueError("No Epomaker RT100 devices found")

        if only_info:
            self._print_device_info()
            return True

        # Find the device with the specified interface number so we can open by path
        # This way we don't block usage of the keyboard whilst the device is open
        device_path = self._find_device_path()
        if device_path is None:
            raise ValueError("No device found")
        self._open_device(device_path)

        return self.device is not None

    def _find_product_id(self) -> int | None:
        """Finds the product ID of the device using a list of possible product IDs.

        Returns:
            int | None: The product ID if found, None otherwise.
        """
        for pid in self.product_ids:
            self.device_list = hid.enumerate(self.vendor_id, pid)
            if self.device_list:
                return pid
        return None

    def _open_device(self, device_path: bytes) -> None:
        """Opens the USB HID device.

        Args:
            device_path (bytes): The path to the device.
        """
        try:
            self.device = hid.device()
            self.device.open_path(device_path)
        except IOError as e:
            print(
                f"Failed to open device: {e}\n"
                "Please make sure the device is connected\n"
                "and you have the necessary permissions.\n\n"
                "You may need to run this program as root or with sudo, or\n"
                "set up a udev rule to allow access to the device.\n\n"
            )
            self.device = None

        assert self.device is not None

    def generate_udev_rule(self) -> None:
        """Generates a udev rule for the connected keyboard."""
        rule_content = (
            f"# Epomaker RT100 keyboard\n"
            f'SUBSYSTEM=="usb", ATTRS{{idVendor}}=="{self.vendor_id:04x}", '
            f'ATTRS{{idProduct}}=="{self._find_product_id():04x}", MODE="0666", '
            'GROUP="plugdev"\n\n'
        )

        rule_file_path = "/etc/udev/rules.d/99-epomaker-rt100.rules"

        print("Generating udev rule for Epomaker RT100 keyboard")
        print(f"Rule content:\n{rule_content}")
        print(f"Rule file path: {rule_file_path}")
        print("Please enter your password if prompted")

        # Write the rule to a temporary file
        temp_file_path = "/tmp/99-epomaker-rt100.rules"
        with open(temp_file_path, "w", encoding="utf-8") as temp_file:
            temp_file.write(rule_content)

        # Move the file to the correct location, reload rules

        move_command = ["mv", temp_file_path, rule_file_path]
        reload_command = ["udevadm", "control", "--reload-rules"]
        trigger_command = ["udevadm", "trigger"]

        if os.geteuid() != 0:
            # Use sudo if not root
            move_command = ["sudo"] + move_command
            reload_command = ["sudo"] + reload_command
            trigger_command = ["sudo"] + trigger_command

        subprocess.run(move_command, check=True)
        subprocess.run(reload_command, check=True)
        subprocess.run(trigger_command, check=True)

        print("Rule generated successfully")

    def _print_device_info(self) -> None:
        """Prints device information."""
        devices = self.device_list.copy()
        for device in devices:
            device["path"] = device["path"].decode("utf-8")
            device["vendor_id"] = f"0x{device['vendor_id']:04x}"
            device["product_id"] = f"0x{device['product_id']:04x}"
        print(
            dumps(
                devices,
                indent="  ",
            )
        )

    @dataclasses.dataclass
    class HIDInfo:
        device_name: str
        event_path: str
        hid_path: Optional[str] = None

    def _find_device_path(self) -> Optional[bytes]:
        """Finds the device path with the specified interface number.

        Returns:
            Optional[bytes]: The device path if found, None otherwise.
        """
        input_dir = "/sys/class/input"
        hid_infos = []
        try:
            hid_infos = EpomakerController._get_hid_infos(
                input_dir, self.device_description
            )
        except Exception as e:
            print(f"Error reading input directory: {e}")

        if not hid_infos:
            print(f"No events found with description: '{self.device_description}' in sysfs, falling back to direct HID enumeration")
            product_id = self._find_product_id()
            if product_id:
                for dev in hid.enumerate(self.vendor_id, product_id):
                    if dev.get('interface_number') == 1:
                        return dev['path']
                devs = hid.enumerate(self.vendor_id, product_id)
                if devs:
                    return devs[0]['path']
            return None

        EpomakerController._populate_hid_paths(hid_infos)

        return self._select_device_path(hid_infos)

    @staticmethod
    def _get_hid_infos(input_dir: str, description: str) -> list[HIDInfo]:
        """Retrieve HID information based on the given description."""
        hid_infos = []
        for event in os.listdir(input_dir):
            if event.startswith("event"):
                device_name_path = os.path.join(input_dir, event, "device", "name")
                try:
                    with open(device_name_path, "r", encoding="utf-8") as f:
                        device_name = f.read().strip()
                        if re.search(description, device_name):
                            event_path = os.path.join(input_dir, event)
                            hid_infos.append(
                                EpomakerController.HIDInfo(device_name, event_path)
                            )
                except FileNotFoundError:
                    continue
        return hid_infos

    @staticmethod
    def _populate_hid_paths(hid_infos: list[HIDInfo]) -> None:
        """Populate the HID paths for each HIDInfo object in the list."""
        for hi in hid_infos:
            device_symlink = os.path.join(hi.event_path, "device")
            if not os.path.islink(device_symlink):
                print(f"No 'device' symlink found in {hi.event_path}")
                continue

            hid_device_path = os.path.realpath(device_symlink)
            match = re.search(r"\b\d+-[\d.]+:\d+\.\d+\b", hid_device_path)
            hi.hid_path = match.group(0) if match else None

    def _select_device_path(self, hid_infos: list[HIDInfo]) -> Optional[bytes]:
        """Select the appropriate device path based on interface preference."""
        device_name_filter = "Wireless" if self.use_wireless else "Wired"
        filtered_devices = [h for h in hid_infos if device_name_filter in h.device_name]

        if not filtered_devices:
            print(f"Could not find {device_name_filter} interface, falling back to any matching interface")
            filtered_devices = hid_infos

        if not filtered_devices:
            return None

        selected_device = filtered_devices[0]
        return (
            selected_device.hid_path.encode("utf-8")
            if selected_device.hid_path
            else None
        )

    def _send_command(self, command: EpomakerCommand.EpomakerCommand) -> None:
        """Sends a command to the HID device.

        Args:
            command (EpomakerCommand): The command to send.
        """
        # Make sure device is opened and connected
        assert self.device, "Device is not set!"
        try:
            self.device.get_product_string()
        except:  # noqa: E722
            raise IOError("Could not communicate with device")

        assert command.report_data_prepared, "Report data not prepared"
        with self.lock:
            for packet in command:
                assert len(packet) == BUFF_LENGTH
                if self.dry_run:
                    print(f"Dry run: skipping command send: {packet!r}")
                else:
                    self.device.send_feature_report(packet.get_all_bytes())

    def send_raw_report(self, data: bytes) -> None:
        """Sends a raw feature report to the HID device in a thread-safe manner."""
        with self.lock:
            if self.device:
                self.device.send_feature_report(data)

    @staticmethod
    def _assert_range(value: int, r: range | None = None) -> bool:
        """Asserts that a value is within a specified range.

        Args:
            value (int): The value to check.
            r (range): The range to check against (default: None).

        Returns:
            bool: True if the value is within the range, False otherwise.
        """
        if not r:
            r = range(0, 100)  # 0 to 99
        return value in r

    def send_dynatab_screen(self, image_path: str, delay_ms: int = 100) -> None:
        """Sends an image or GIF to the DynaTab 75X screen.

        Args:
            image_path (str): The path to the image/GIF file.
            delay_ms (int): The animation frame delay in milliseconds (default: 100).
        """
        from .commands.EpomakerDynaTabScreenCommand import EpomakerDynaTabScreenCommand
        screen_command = EpomakerDynaTabScreenCommand.from_image(image_path, delay_ms)

        import hid
        import time

        # 1. Open Interface 2 and send the screen command packets
        dev2_path = None
        for device_info in hid.enumerate(self.vendor_id):
            if device_info["product_id"] in self.product_ids:
                if device_info["interface_number"] == 2:
                    dev2_path = device_info["path"]
                    break
        if dev2_path:
            try:
                dev2 = hid.device()
                dev2.open_path(dev2_path)
                reports_list = list(screen_command)
                if reports_list:
                    # Send initialization report (0xa9) and wait for flash memory erase/init
                    dev2.send_feature_report(b'\x00' + reports_list[0].get_all_bytes())
                    time.sleep(0.25)
                    
                    # Send data reports (0x29) with a 10ms delay between reports to avoid buffer overflows
                    for packet in reports_list[1:]:
                        dev2.send_feature_report(b'\x00' + packet.get_all_bytes())
                        time.sleep(0.010)
                dev2.close()
                print("Animation uploaded on Interface 2. Waiting 12 seconds for the keyboard to write to flash and reboot...")
                time.sleep(12)
            except Exception as e:
                print(f"Warning: Failed to upload screen design on Interface 2: {e}")
        else:
            print("Warning: Interface 2 not found.")

        # 2. Open Interface 0 to apply/activate the uploaded screen design
        # Re-enumerate hid devices because the keyboard has disconnected and reconnected
        dev0_path = None
        for device_info in hid.enumerate(self.vendor_id):
            if device_info["product_id"] in self.product_ids:
                if device_info["interface_number"] == 0:
                    dev0_path = device_info["path"]
                    break
        if dev0_path:
            try:
                dev0 = hid.device()
                dev0.open_path(dev0_path)
                dev0.write(b'\x00\x00')
                time.sleep(0.3)
                dev0.write(b'\x00\x01')
                dev0.close()
            except Exception as e:
                print(f"Warning: Failed to apply screen design on Interface 0: {e}")

    def send_image(self, image_path: str, delay_ms: int = 100) -> None:
        """Sends an image or GIF to the HID device.

        Args:
            image_path (str): The path to the image file.
            delay_ms (int): The animation frame delay in milliseconds (default: 100).
        """
        if "DynaTab" in self.config_layout.filename:
            was_open = self.device is not None
            if was_open:
                self.close_device()

            self.send_dynatab_screen(image_path, delay_ms)

            if was_open:
                self.open_device()
            return

        image_command = EpomakerImageCommand.EpomakerImageCommand()
        image_command.encode_image(image_path)
        self._send_command(image_command)

    def send_time(self, time: datetime | None = None) -> None:
        """Sends `time` to the HID device.

        Args:
            time (datetime): The time to send (default: None).
        """
        if not time:
            time = datetime.now()
        time_command = EpomakerTimeCommand.EpomakerTimeCommand(time)
        self._send_command(time_command)

    def send_temperature(self, temperature: int | None) -> None:
        """Sends the temperature to the HID device.

        Args:
            temperature (int): The temperature value in C (0-99).
            delay_seconds (int): Time waited after command is sent.

        Raises:
            ValueError: If the temperature is not in the range 0-99.
        """
        if not temperature:
            # Don't do anything if temperature is None
            return
        if not self._assert_range(temperature):
            raise ValueError("Temperature must be in range 0-99: ", temperature)
        temperature_command = EpomakerTempCommand.EpomakerTempCommand(temperature)
        print(f"Sending temperature {temperature}C")
        self._send_command(temperature_command)

    def send_cpu(self, cpu: int) -> None:
        """Sends the CPU percentage to the HID device.

        Args:
            cpu (int): The CPU percentage to send.
            delay_seconds (int): Time waited after command is sent.

        Raises:
            ValueError: If the CPU percentage is not in the range 0-100 and
                from_daemon is False.
        """
        if not self._assert_range(cpu):
            raise ValueError("CPU percentage must be in range 0-100")
        cpu_command = EpomakerCpuCommand.EpomakerCpuCommand(cpu)
        print(f"Sending CPU {cpu}%")
        self._send_command(cpu_command)

    def set_rgb_all_keys(self, r: int, g: int, b: int) -> None:
        # Make sure values are within range
        for value in [r, g, b]:
            self._assert_range(value, range(0, 256))

        # Get all the keyboard keys
        keyboard_keys = KeyboardKeys(self.config_keymap)

        # Construct a KeyMap object
        mapping = EpomakerKeyRGBCommand.KeyMap(keyboard_keys)

        # Set all keys to r, g, b
        for key in keyboard_keys:
            mapping[key] = (r, g, b)

        frames = [EpomakerKeyRGBCommand.KeyboardRGBFrame(key_map=mapping)]
        self.send_keys(frames)

    def send_keys(self, frames: list[EpomakerKeyRGBCommand.KeyboardRGBFrame]) -> None:
        """Sends key RGB frames to the HID device.

        Args:
            frames (list): The list of KeyboardRGBFrame to send.
        """
        rgb_command = EpomakerKeyRGBCommand.EpomakerKeyRGBCommand(frames)
        self._send_command(rgb_command)

    def remap_keys(self, key_index: int, key_combo: int) -> None:
        key_map_command = EpomakerRemapKeysCommand.EpomakerRemapKeysCommand(
            key_index, key_combo
        )
        self._send_command(key_map_command)

    def cycle_light_modes(self, sleep_seconds: int = 5) -> None:
        for counter, mode in enumerate(Profile.Mode):
            profile = Profile(
                mode=mode,
                speed=Profile.Speed.DEFAULT,
                brightness=Profile.Brightness.DEFAULT,
                dazzle=Profile.Dazzle.OFF,
                option=Profile.Option.OFF,
                rgb=(180, 180, 180),
            )
            self.set_profile(profile)
            print(
                f"[{counter + 1}/{len(Profile.Mode)}] Cycled to light mode: {mode.name}"
            )
            time.sleep(sleep_seconds)
            counter += 1

    def set_profile(self, profile: Profile) -> None:
        """Set the keyboard profile."""
        profile_command = EpomakerProfileCommand.EpomakerProfileCommand(profile)
        self._send_command(profile_command)

    def start_daemon(self, temp_key: str | None, test_mode: bool) -> None:
        """Start a daemon to update the CPU usage and optionally a temperature.

        Args:
            temp_key (str): A label corresponding to the device to monitor.
            test_mode (bool): Send random ints instead of real values.
        """
        # Set current time and date
        self.send_time()

        while True:
            # Send CPU usage
            th_cpu = TimeHelper(min_duration=1.6)
            self.send_cpu(get_cpu_usage(test_mode))
            del th_cpu

            # Get device temperature using the provided key
            if temp_key:
                th_temp = TimeHelper(min_duration=1.6)
                self.send_temperature(get_device_temp(temp_key, test_mode))
                del th_temp
            elif test_mode:
                self.send_temperature(get_device_temp("dummy_device", test_mode))
                time.sleep(1.6)

    def close_device(self) -> None:
        """Closes the USB HID device."""
        if self.device:
            self.device.close()
            self.device = None
