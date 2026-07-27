## Contributing to Epomaker Controller

Thanks for taking the time to contribute! Here's how to get started.

### Reporting Bugs
Use the **Bug Report** issue template. Include your OS version, Python version, keyboard model, and a full traceback if available.

### Suggesting Features
Use the **Feature Request** issue template.

### Adding Support for a New Keyboard Model
Use the **Keyboard Model Support** issue template. USB packet captures from Wireshark are extremely valuable.

---

### Setting Up for Development

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/epomaker-controller.git
cd epomaker-controller
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Code Structure

```
epomakercontroller/
├── cli.py                  # CLI entrypoints and GUI orchestration flow
├── epomakercontroller.py   # Core HID device controller
├── commands/               # Protocol command implementations
│   ├── EpomakerKeyRGBCommand.py
│   ├── EpomakerDynaTabScreenCommand.py
│   └── ...
├── configs/
│   ├── keymaps/            # Per-model key index maps (JSON)
│   └── layouts/            # Per-model GUI key layouts (JSON)
└── utils/
    ├── keyboard_gui.py     # Key backlight customizer GUI
    └── screen_designer_gui.py  # Dot-matrix screen designer GUI
```

### Adding a New Keyboard Model

1. Capture USB traffic from the official driver using Wireshark.
2. Add a new keymap JSON file to `epomakercontroller/configs/keymaps/`.
3. Add a new layout JSON file to `epomakercontroller/configs/layouts/`.
4. Register the model VID/PID in `epomakercontroller/configs/configs.py`.
5. Set `CAPABILITIES` in `~/.epomaker-controller/config.json` (or `DEFAULT_MAIN_CONFIG`) to the features this model supports:
   - `per_key_rgb` — per-key RGB / key customizer
   - `rt100_screen` — RT100-style 162×173 image upload
   - `dynatab_screen` — DynaTab 60×9 animation / screen designer
   Example for DynaTab 75X:
   ```json
   "CONF_LAYOUT_PATH": "EpomakerDynaTab75X.json",
   "CONF_KEYMAP_PATH": "EpomakerDynaTab75X.json",
   "CAPABILITIES": ["per_key_rgb", "dynatab_screen"]
   ```
6. Test the protocol against the hardware and submit a PR.

### Pull Request Guidelines

- Keep PRs focused on one change.
- Test against real hardware if possible.
- Update the relevant section of the README if you add features.
- Keep code style consistent with the rest of the project (PEP8).
