# Epomaker DynaTab 75X Controller & Screen Designer

A complete, feature-rich Linux controller utility and interactive pixel art animation suite for the **Epomaker DynaTab 75X** mechanical keyboard.

This utility allows you to control key backlighting, customize the onboard 60x9 dot-matrix display, sync system time, and build custom animations without needing the official Windows driver.

---

## Features

* **🎨 Interactive LED Screen Designer (GUI):** A frame-by-frame pixel editor to draw custom graphics, manage frames, import images/GIFs, export animations, and upload designs directly to the keyboard.
* **⌨️ Visual Key Backlight Customizer (GUI):** Real-time interactive key-by-key backlighting editor.
* **💾 Solid Color Profile Customizer:** Save permanent solid backlight configurations directly to the keyboard's onboard profile memory.
* **🕒 Time Sync:** Instantly sync the keyboard's built-in digital clock with your system time.

---

## Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.10+ and the required development libraries installed. On Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv libusb-1.0-0-dev libudev-dev
```

### 2. Configure USB Permissions (Udev Rules)
By default, Linux restricts access to raw HID USB interfaces. Run the setup script to grant your user account access to the keyboard interfaces:
```bash
chmod +x setup_udev.sh
sudo ./setup_udev.sh
```
*Note: Unplug and plug the keyboard back in for the rules to apply!*

### 3. Install Python Dependencies
Set up the virtual environment and install the library:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pillow opencv-python-headless
```

---

## How to Use

Activate the virtual environment:
```bash
source .venv/bin/activate
```

### 1. Launch the Screen Designer & Animator (GUI)
Draw custom frames, adjust animation speed, import images/GIFs, and upload them to the keyboard:
```bash
python -m epomakercontroller screen-designer
```

### 2. Launch the Backlight Customizer (GUI)
Open the key-by-key visual editor to color your keys in real-time:
```bash
python -m epomakercontroller set-keys
```

### 3. Set a Permanent Backlight Color (Profile)
Saves a solid color configuration to the hardware profile. For example, to set the backlight to solid Blue:
```bash
python -m epomakercontroller set-profile 0 0 255
```

### 4. Sync Time
```bash
python -m epomakercontroller send-time
```

### 5. Quick Image / GIF Upload (CLI)
Upload any PNG/JPG/GIF directly from the command line (automatically handles resizing and centering):
```bash
# Upload a static image
python -m epomakercontroller upload-image path/to/image.png

# Upload an animated GIF with 150ms frame delay
python -m epomakercontroller upload-image path/to/animation.gif --delay 150
```

---

## Protocol Details (DynaTab 75X Specifics)
The keyboard handles communication across multiple HID interfaces:
* **Interface 0 (Input):** Normal keyboard functions and configuration activation/apply commands.
* **Interface 1 (System Control):** Lighting and onboard key profiles.
* **Interface 2 (Media/Screen):** Dot-matrix screen graphics and animation buffers.

When uploading screen animations:
1. Data reports (`0xa9` for init, `0x29` for frames) are sent in **column-major format** to **Interface 2** with a Report ID of `0x00`.
2. To avoid overflow-induced color channel shifts, the 29th report of each frame is dynamically sized to exactly **52 bytes** instead of the typical 56.
3. The keyboard disconnects and reboots itself to write the data from RAM to flash. The controller waits **12 seconds** for the reboot before sending final activation calls to **Interface 0**.

---

## License
MIT License. Feel free to copy, modify, and share!
