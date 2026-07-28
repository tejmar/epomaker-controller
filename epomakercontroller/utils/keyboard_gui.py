from pathlib import Path
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Literal

from .fonts import F
from . import theme as T
from .keyboard_keys import KeyboardKey, KeyboardKeys
from ..commands.EpomakerKeyRGBCommand import KeyMap, KeyboardRGBFrame
from ..configs.configs import Config
from ..commands.data.constants import Profile

DEFAULT_KEY_WIDTH = 8
DEFAULT_KEY_HEIGHT = 4


class RGBKeyboardGUI:
    def __init__(
        self,
        root: tk.Tk,
        callback: Callable[[list[KeyboardRGBFrame]], None],
        config_layout: Config,
        config_keymap: Config,
        switch_callback: Callable[[tk.Tk], None] | None = None,
        controller=None,
        initial_colours: dict | None = None,
    ):
        self.config_layout = config_layout.data
        self.keyboard_keys = KeyboardKeys(config_keymap)
        self.frame = KeyboardRGBFrame(KeyMap(self.keyboard_keys))
        # Guards the live frame against concurrent reads by the background send
        # loop (see cli.run_set_keys_flow). Mutate via apply_overlay().
        self._lock = threading.Lock()
        # Thread-safe channel for the background send loop to report device
        # status/errors without touching Tk from a worker thread.
        self._status_queue: "queue.Queue[str]" = queue.Queue()

        self.root = root
        T.style_root(root, f"Key Backlight — {Path(config_layout.filename).stem}")
        self.key_btn_dict: dict[KeyboardKey, tk.Button] = {}

        self.selected_key: set[KeyboardKey] = set()
        self.key_colours: dict[KeyboardKey, str | None] = {}
        self.selected_color = (255, 0, 0)  # Default: Red
        self.custom_mode_active = False

        self.col_offset = 0
        self.row_offset = 0
        self.key_width = DEFAULT_KEY_WIDTH
        self.key_height = DEFAULT_KEY_HEIGHT

        self.switch_callback = switch_callback
        self.controller = controller

        self.status_var = tk.StringVar(value="Device: ready")
        self.setup_ui()
        self.root.after(500, self._poll_status)

        # Apply initial colours if provided
        if initial_colours:
            self.custom_mode_active = True
            for name, color in initial_colours.items():
                key = self.keyboard_keys.get_key_by_name(name)
                if key and color:
                    self.key_colours[key] = color
                    self._refresh_key_btn(key)
                    r, g, b = (
                        int(color[1:3], 16),
                        int(color[3:5], 16),
                        int(color[5:7], 16),
                    )
                    self.apply_overlay({key}, (r, g, b))

        self.root.bind("<Return>", self.apply_colour_to_selected_keys)
        self.callback = callback

    def apply_overlay(self, keys, rgb) -> None:
        """Thread-safe wrapper around frame.overlay for use from the GUI thread."""
        with self._lock:
            self.frame.overlay(keys, rgb)

    def snapshot_frame(self) -> KeyboardRGBFrame:
        """Return a thread-safe copy of the current key-colour frame."""
        with self._lock:
            km = KeyMap(self.keyboard_keys)
            km.key_map = dict(self.frame.key_map.key_map)
            return KeyboardRGBFrame(key_map=km)

    def report_status(self, text: str) -> None:
        """Thread-safe: queue a status update for the UI thread to display."""
        self._status_queue.put(text)

    def _poll_status(self) -> None:
        """Apply the latest queued status to the status bar (runs on UI thread)."""
        latest = None
        try:
            while True:
                latest = self._status_queue.get_nowait()
        except queue.Empty:
            pass
        if latest is not None:
            self.status_var.set(latest)
            # Soft color cue for errors vs ok
            if "error" in latest.lower():
                self.status_lbl.configure(fg=T.DANGER)
            else:
                self.status_lbl.configure(fg=T.SUCCESS)
        if self.root.winfo_exists():
            self.root.after(500, self._poll_status)

    def _handle_customization(self, item: tuple[str, int]) -> bool:
        identifier, value = item
        if identifier == "w":
            self.key_width = int(DEFAULT_KEY_WIDTH * value)
            return True
        elif identifier == "h":
            self.key_height = int(DEFAULT_KEY_HEIGHT * value)
            return True
        elif identifier == "x":
            self.col_offset += int(DEFAULT_KEY_WIDTH * value)
        elif identifier == "y":
            self.row_offset += int(DEFAULT_KEY_HEIGHT * value)
        else:
            print(f"Warning: Unknown customization identifier: {item}")
        return False

    def _create_key_callback(self, key: KeyboardKey) -> Callable[[], None]:
        def on_key_selected() -> None:
            self.select_key(key)

        return on_key_selected

    def _key_face_color(self, key: KeyboardKey) -> str:
        return self.key_colours.get(key) or T.KEY_IDLE

    def _refresh_key_btn(self, key: KeyboardKey) -> None:
        btn = self.key_btn_dict[key]
        face = self._key_face_color(key)
        selected = key in self.selected_key
        fg = T.contrast_fg(face) if face != T.KEY_IDLE else T.KEY_TEXT
        if selected:
            btn.configure(
                bg=face,
                fg=fg,
                activebackground=face,
                activeforeground=fg,
                highlightthickness=3,
                highlightbackground=T.ACCENT,
                highlightcolor=T.ACCENT,
                relief=tk.FLAT,
            )
        else:
            btn.configure(
                bg=face,
                fg=fg,
                activebackground=face,
                activeforeground=fg,
                highlightthickness=1,
                highlightbackground=T.KEY_BORDER,
                highlightcolor=T.KEY_BORDER,
                relief=tk.FLAT,
            )

    def setup_ui(self) -> None:
        # Header
        header = tk.Frame(self.root, bg=T.SURFACE)
        header.pack(side=tk.TOP, fill=tk.X)
        T.title_label(
            header,
            "Key Backlight",
            bg=T.SURFACE,
            font=F(14, "bold"),
            pady=10,
            padx=16,
            anchor="w",
        ).pack(side=tk.LEFT)
        self.status_lbl = T.status_bar(header, self.status_var)
        self.status_lbl.pack(side=tk.RIGHT, padx=8, pady=8)

        # Keyboard deck (slightly elevated card)
        deck_outer = tk.Frame(self.root, bg=T.BG)
        deck_outer.pack(padx=16, pady=(12, 8), fill=tk.BOTH, expand=True)

        keyboard_card = tk.Frame(
            deck_outer,
            bg=T.SURFACE,
            highlightbackground=T.BORDER,
            highlightthickness=1,
            bd=0,
            padx=14,
            pady=14,
        )
        keyboard_card.pack()

        keyboard_frame = tk.Frame(keyboard_card, bg=T.SURFACE)
        keyboard_frame.pack()

        customized = False
        for row in self.config_layout:  # type: ignore
            for col in row:
                if isinstance(col, dict):
                    for item in col.items():
                        customized = customized or self._handle_customization(item)
                else:
                    display_str = col
                    state: Literal["normal", "active", "disabled"] = "disabled"

                    def noop() -> None:
                        pass

                    command = noop
                    key = self.keyboard_keys.get_key_by_name(col)
                    if key:
                        display_str = key.display_str
                        state = "normal"
                        command = self._create_key_callback(key)

                    if state == "normal":
                        btn = tk.Button(
                            keyboard_frame,
                            text=display_str,
                            width=self.key_width,
                            height=self.key_height,
                            command=command,
                            state=state,
                            bg=T.KEY_IDLE,
                            fg=T.KEY_TEXT,
                            activebackground=T.KEY_IDLE,
                            activeforeground=T.KEY_TEXT,
                            font=F(8, "bold"),
                            relief=tk.FLAT,
                            bd=0,
                            highlightthickness=1,
                            highlightbackground=T.KEY_BORDER,
                            highlightcolor=T.KEY_BORDER,
                            cursor="hand2",
                        )
                    else:
                        btn = tk.Button(
                            keyboard_frame,
                            text=display_str,
                            width=self.key_width,
                            height=self.key_height,
                            command=command,
                            state=state,
                            bg=T.KEY_DISABLED,
                            fg=T.KEY_TEXT_DIM,
                            disabledforeground=T.KEY_TEXT_DIM,
                            font=F(8, "bold"),
                            relief=tk.FLAT,
                            bd=0,
                            highlightthickness=1,
                            highlightbackground=T.KEY_DISABLED,
                        )

                    btn.grid(
                        row=self.row_offset,
                        column=self.col_offset,
                        columnspan=self.key_width,
                        rowspan=self.key_height,
                        padx=1,
                        pady=1,
                    )

                    if key:
                        self.key_btn_dict[key] = btn
                        self.key_colours[key] = None
                    self.col_offset += self.key_width

                    if customized:
                        customized = False
                        self.key_width = DEFAULT_KEY_WIDTH
                        self.key_height = DEFAULT_KEY_HEIGHT
            self.row_offset += DEFAULT_KEY_HEIGHT
            self.col_offset = 0

        # Controls
        controls_wrap = tk.Frame(self.root, bg=T.BG)
        controls_wrap.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=(0, 16))

        cp_outer, cp_inner = T.card(controls_wrap, "Color")
        cp_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.create_color_picker(cp_inner)

        pr_outer, pr_inner = T.card(controls_wrap, "Presets")
        pr_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self.create_preset_panel(pr_inner)

        act_outer, act_inner = T.card(controls_wrap, "Actions")
        act_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        self.create_actions_panel(act_inner)

    def create_color_picker(self, parent):
        swatch_frame = tk.Frame(parent, bg=T.SURFACE)
        swatch_frame.pack(side=tk.LEFT, padx=4)

        swatches_colors = [
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)),
            ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)),
            ("Cyan", (0, 255, 255)),
            ("Magenta", (255, 0, 255)),
            ("White", (255, 255, 255)),
            ("Orange", (255, 128, 0)),
            ("Pink", (255, 0, 128)),
            ("Purple", (128, 0, 255)),
            ("Teal", (0, 128, 128)),
            ("Off", (0, 0, 0)),
        ]

        for idx, (name, rgb) in enumerate(swatches_colors):
            r_idx = idx // 4
            c_idx = idx % 4
            btn = T.color_swatch_button(
                swatch_frame,
                rgb,
                command=lambda color=rgb: self.update_active_color(color),
                text=name[:3],
                width=4,
                height=1,
            )
            btn.grid(row=r_idx, column=c_idx, padx=2, pady=2)

        sliders_frame = tk.Frame(parent, bg=T.SURFACE)
        sliders_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y)

        preview_wrap = tk.Frame(
            sliders_frame,
            bg=T.BORDER,
            padx=2,
            pady=2,
            highlightthickness=0,
        )
        preview_wrap.pack(side=tk.LEFT, padx=6)
        self.color_preview = tk.Frame(
            preview_wrap, width=40, height=40, bg="#ff0000", bd=0
        )
        self.color_preview.pack()
        self.color_preview.pack_propagate(False)

        scale_sub = tk.Frame(sliders_frame, bg=T.SURFACE)
        scale_sub.pack(side=tk.LEFT, padx=4)

        self.r_scale = T.scale(
            scale_sub,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            label="R",
            length=120,
            command=self.on_slider_move,
        )
        self.r_scale.set(255)
        self.r_scale.pack(pady=1)

        self.g_scale = T.scale(
            scale_sub,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            label="G",
            length=120,
            command=self.on_slider_move,
        )
        self.g_scale.set(0)
        self.g_scale.pack(pady=1)

        self.b_scale = T.scale(
            scale_sub,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            label="B",
            length=120,
            command=self.on_slider_move,
        )
        self.b_scale.set(0)
        self.b_scale.pack(pady=1)

    def create_preset_panel(self, parent):
        T.muted_label(parent, "Effect mode", bg=T.SURFACE).grid(
            row=0, column=0, sticky="w", pady=2
        )

        self.preset_modes = [m.name for m in Profile.Mode]
        self.selected_preset_mode = tk.StringVar(value="ALWAYS_ON")

        mode_menu = T.option_menu(
            parent, self.selected_preset_mode, *self.preset_modes
        )
        mode_menu.config(width=18)
        mode_menu.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        T.muted_label(parent, "Speed", bg=T.SURFACE).grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.speed_scale = T.scale(
            parent, from_=0, to=5, orient=tk.HORIZONTAL, length=140
        )
        self.speed_scale.set(4)
        self.speed_scale.grid(row=1, column=1, sticky="we", pady=2, padx=5)

        T.muted_label(parent, "Brightness", bg=T.SURFACE).grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.brightness_scale = T.scale(
            parent, from_=0, to=4, orient=tk.HORIZONTAL, length=140
        )
        self.brightness_scale.set(4)
        self.brightness_scale.grid(row=2, column=1, sticky="we", pady=2, padx=5)

        self.dazzle_var = tk.BooleanVar(value=False)
        T.checkbox(parent, "Dazzle effect", self.dazzle_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=4
        )

        T.button_success(
            parent, "Apply preset", command=self.apply_preset_effect
        ).grid(row=4, column=0, columnspan=2, sticky="we", pady=6)

    def create_actions_panel(self, parent):
        self.paint_brush_var = tk.BooleanVar(value=False)
        T.checkbox(
            parent, "Paint brush (instant)", self.paint_brush_var
        ).pack(anchor="w", pady=2)

        T.button_secondary(
            parent, "Select all keys", command=self.select_all_keys
        ).pack(fill="x", pady=2)

        T.button_secondary(
            parent, "Save layout", command=self.save_layout
        ).pack(fill="x", pady=2)

        T.button_secondary(
            parent, "Load layout", command=self.load_layout
        ).pack(fill="x", pady=2)

        T.button_danger(
            parent, "Clear all keys", command=self.clear_all_keys
        ).pack(fill="x", pady=2)

        if self.switch_callback is not None:
            T.button_primary(
                parent,
                "Screen designer →",
                command=lambda: self.switch_callback(self.root),
            ).pack(fill="x", pady=(8, 2))

    def on_slider_move(self, _):
        r = self.r_scale.get()
        g = self.g_scale.get()
        b = self.b_scale.get()
        self.selected_color = (r, g, b)
        self.color_preview.config(bg=T.hex_rgb((r, g, b)))
        if self.selected_key:
            self.paint_selected_keys((r, g, b))

    def update_active_color(self, rgb):
        self.selected_color = rgb
        self.r_scale.set(rgb[0])
        self.g_scale.set(rgb[1])
        self.b_scale.set(rgb[2])
        self.color_preview.config(bg=T.hex_rgb(rgb))
        if self.selected_key:
            self.paint_selected_keys(rgb)

    def select_key(self, key: KeyboardKey) -> None:
        if self.paint_brush_var.get():
            self.custom_mode_active = True
            hex_color = T.hex_rgb(self.selected_color)
            self.key_colours[key] = hex_color
            self.apply_overlay({key}, self.selected_color)
            self._refresh_key_btn(key)
            return

        if key in self.selected_key:
            self.selected_key.remove(key)
        else:
            self.selected_key.add(key)
        self._refresh_key_btn(key)

    def select_all_keys(self):
        for key in self.key_btn_dict:
            self.selected_key.add(key)
            self._refresh_key_btn(key)

    def paint_selected_keys(self, rgb):
        self.custom_mode_active = True
        hex_color = T.hex_rgb(rgb)
        for key in list(self.selected_key):
            self.key_colours[key] = hex_color
            self._refresh_key_btn(key)
        self.apply_overlay(self.selected_key, rgb)
        # clear selection after paint but refresh borders
        selected = list(self.selected_key)
        self.selected_key.clear()
        for key in selected:
            self._refresh_key_btn(key)

    def apply_colour_to_selected_keys(self, _: object) -> None:
        if self.selected_key:
            self.paint_selected_keys(self.selected_color)

    def apply_preset_effect(self):
        if not self.controller:
            messagebox.showerror(
                "Error", "Controller not initialized.", parent=self.root
            )
            return

        try:
            mode_name = self.selected_preset_mode.get()
            mode_enum = Profile.Mode[mode_name]
            speed_val = self.speed_scale.get()
            brightness_val = self.brightness_scale.get()
            dazzle_val = (
                Profile.Dazzle.ON if self.dazzle_var.get() else Profile.Dazzle.OFF
            )

            profile = Profile(
                mode=mode_enum,
                speed=Profile.Speed(speed_val),
                brightness=Profile.Brightness(brightness_val),
                dazzle=dazzle_val,
                option=Profile.Option.OFF,
                rgb=self.selected_color,
            )
            self.controller.set_profile(profile)
            self.custom_mode_active = False
            messagebox.showinfo(
                "Success",
                f"Preset '{mode_name}' applied successfully!",
                parent=self.root,
            )
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to apply preset: {e}", parent=self.root
            )

    def save_layout(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Key Layout JSON",
            initialdir=os.path.expanduser("~/Pictures"),
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if not file_path:
            return

        try:
            layout_data = {}
            for key, val in self.key_colours.items():
                if val:
                    layout_data[key.name] = val

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(layout_data, f, indent=4)

            messagebox.showinfo(
                "Success",
                f"Layout saved successfully to {Path(file_path).name}",
                parent=self.root,
            )
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to save layout: {e}", parent=self.root
            )

    def load_layout(self):
        file_path = filedialog.askopenfilename(
            title="Load Key Layout JSON",
            initialdir=os.path.expanduser("~/Pictures"),
            filetypes=[("JSON Files", "*.json")],
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                layout_data = json.load(f)

            self.clear_all_keys()
            self.custom_mode_active = True

            for key_name, hex_color in layout_data.items():
                key = self.keyboard_keys.get_key_by_name(key_name)
                if key:
                    self.key_colours[key] = hex_color
                    self._refresh_key_btn(key)
                    r, g, b = (
                        int(hex_color[1:3], 16),
                        int(hex_color[3:5], 16),
                        int(hex_color[5:7], 16),
                    )
                    self.apply_overlay({key}, (r, g, b))

            messagebox.showinfo(
                "Success", "Layout loaded successfully!", parent=self.root
            )
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to load layout: {e}", parent=self.root
            )

    def clear_all_keys(self):
        for key in self.key_btn_dict:
            self.key_colours[key] = None
            self._refresh_key_btn(key)
        self.apply_overlay(self.key_btn_dict.keys(), (0, 0, 0))
        self.selected_key.clear()
        for key in self.key_btn_dict:
            self._refresh_key_btn(key)
