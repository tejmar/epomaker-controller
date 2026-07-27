#!/bin/bash
set -e

RULE_FILE="/etc/udev/rules.d/99-epomaker-dynatab.rules"
echo "Creating udev rule file at $RULE_FILE..."

sudo bash -c "cat > $RULE_FILE" <<EOF
# Epomaker DynaTab 75X udev rules
# For hidraw backend
KERNEL=="hidraw*", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4015", MODE="0666"
# For libusb backend
SUBSYSTEM=="usb", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4015", MODE="0666"
SUBSYSTEM=="usb-device", ATTRS{idVendor}=="3151", ATTRS{idProduct}=="4015", MODE="0666"
EOF

echo "Reloading and triggering udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "udev rules configured successfully! You can now control the keyboard without sudo."
