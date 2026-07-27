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
git clone https://github.com/tejmar/epomaker-controller.git
cd epomaker-controller
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running tests

Unit tests do not need a keyboard attached (controller paths use `dry_run` / pure command builders):

```bash
pytest
```

CI runs the same suite on Python 3.10–3.12 via `.github/workflows/ci.yml`.

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

### Switching keyboard models (users)

```bash
epomakercontroller models list          # * marks the current match
epomakercontroller models show          # layout / keymap / capabilities
epomakercontroller models set dynatab75x
```

Built-in ids: `rt100`, `dynatab75x`, `ep64`, `gamakay-tk68-he`.  
This writes layout, keymap, and `CAPABILITIES` into `~/.epomaker-controller/config.json`.

### Adding a New Keyboard Model

1. Capture USB traffic from the official driver using Wireshark.
2. Add a new keymap JSON file to `epomakercontroller/configs/keymaps/`.
3. Add a new layout JSON file to `epomakercontroller/configs/layouts/`.
4. Register the model in `epomakercontroller/configs/models.py` (`MODELS` dict): layout, keymap, and capabilities.
5. Capability flags:
   - `per_key_rgb` — per-key RGB / key customizer
   - `rt100_screen` — RT100-style 162×173 image upload
   - `dynatab_screen` — DynaTab 60×9 animation / screen designer
6. Users can then run `epomakercontroller models set <id>`.
7. Test the protocol against the hardware and submit a PR.

### Pull Request Guidelines

- Keep PRs focused on one change.
- Test against real hardware if possible.
- Update the relevant section of the README if you add features.
- Keep code style consistent with the rest of the project (PEP8).
