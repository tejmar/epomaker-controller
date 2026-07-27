from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import queue
import threading
from .fonts import F, get_ui_font

from .keyboard_keys import KeyboardKey, KeyboardKeys
from ..commands.EpomakerKeyRGBCommand import KeyMap, KeyboardRGBFrame
from typing import Callable, Literal
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
        switch_callback: Callable[[tk.Tk], None] = None,
        controller = None,
        initial_colours: dict = None,
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
        self.root.title(f"RGB Keyboard ({Path(config_layout.filename).stem})")
        self.root.configure(bg="#1e1e1e")
        self.key_btn_dict: dict[KeyboardKey, tk.Button] = {}

        self.selected_key: set[KeyboardKey] = set()
        self.key_colours: dict[KeyboardKey, str | None] = {}
        self.selected_color = (255, 0, 0) # Default: Red
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
                    self.key_btn_dict[key].config(bg=color)
                    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                    self.apply_overlay({key}, (r, g, b))

        self.root.bind("<Return>", self.apply_colour_to_selected_keys)
        self.callback = callback

    def apply_overlay(self, keys, rgb) -> None:
        """Thread-safe wrapper around frame.overlay for use from the GUI thread."""
        with self._lock:
            self.frame.overlay(keys, rgb)

    def snapshot_frame(self) -> KeyboardRGBFrame:
        """Return a thread-safe copy of the current key-colour frame.

        The background send loop builds the device command from this snapshot so
        the GUI can keep mutating the live frame without producing an inconsistent
        partial update over the wire.
        """
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

    def setup_ui(self) -> None:
        # Device status bar (updated by the background send loop via report_status)
        tk.Label(self.root, textvariable=self.status_var, bg="#1e1e1e", fg="#9aa0a6",
                 font=F(8), anchor="w", pady=2).pack(side=tk.TOP, fill=tk.X)
        # Create container for keys to prevent layout shift
        keyboard_frame = tk.Frame(self.root, bg="#1e1e1e")
        keyboard_frame.pack(padx=15, pady=15)

        customized = False
        for row in self.config_layout:  # type: ignore
            keyboardkeys_row: list[KeyboardKey] = []
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
                        keyboardkeys_row.append(key)

                    btn = tk.Button(
                        keyboard_frame,
                        text=display_str,
                        width=self.key_width,
                        height=self.key_height,
                        command=command,
                        state=state,
                        bg="#2b2b2b" if state == "normal" else "#151515",
                        fg="#eeeeee" if state == "normal" else "#555555",
                        activebackground="#444444",
                        activeforeground="#ffffff",
                        font=F(8, "bold"),
                        relief=tk.RAISED,
                        bd=1,
                        highlightthickness=0
                    )
                    btn.grid(
                        row=self.row_offset,
                        column=self.col_offset,
                        columnspan=self.key_width,
                        rowspan=self.key_height,
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

        # Build controls section at the bottom
        controls_frame = tk.Frame(self.root, bg="#2d2d2d")
        controls_frame.pack(fill="x", side="bottom", padx=15, pady=(0, 15))

        # 1. Color Picker
        cp_frame = tk.LabelFrame(controls_frame, text="Color Picker", bg="#2d2d2d", fg="#888888", font=F(9, "bold"), padx=10, pady=5)
        cp_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.create_color_picker(cp_frame)

        # 2. Preset Panel
        pr_frame = tk.LabelFrame(controls_frame, text="Presets", bg="#2d2d2d", fg="#888888", font=F(9, "bold"), padx=10, pady=5)
        pr_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.create_preset_panel(pr_frame)

        # 3. Actions Panel
        act_frame = tk.LabelFrame(controls_frame, text="Actions", bg="#2d2d2d", fg="#888888", font=F(9, "bold"), padx=10, pady=5)
        act_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.create_actions_panel(act_frame)

    def create_color_picker(self, parent):
        swatch_frame = tk.Frame(parent, bg="#2d2d2d")
        swatch_frame.pack(side="left", padx=5)

        swatches_colors = [
            ("Red", (255, 0, 0)), ("Green", (0, 255, 0)), ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)), ("Cyan", (0, 255, 255)), ("Magenta", (255, 0, 255)),
            ("White", (255, 255, 255)), ("Orange", (255, 128, 0)), ("Pink", (255, 0, 128)),
            ("Purple", (128, 0, 255)), ("Teal", (0, 128, 128)), ("Off", (0, 0, 0))
        ]

        for idx, (name, rgb) in enumerate(swatches_colors):
            r_idx = idx // 4
            c_idx = idx % 4
            hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            btn = tk.Button(
                swatch_frame, text=name, bg=hex_color if name != "Off" else "#1e1e1e",
                fg="#ffffff" if name in ["Blue", "Purple", "Off"] else "#000000",
                font=F(8, "bold"), width=7, relief=tk.FLAT, bd=0,
                command=lambda color=rgb: self.update_active_color(color)
            )
            btn.grid(row=r_idx, column=c_idx, padx=2, pady=2)

        sliders_frame = tk.Frame(parent, bg="#2d2d2d")
        sliders_frame.pack(side="left", padx=10, fill="y")

        self.color_preview = tk.Frame(sliders_frame, width=35, height=35, bg="#ff0000", bd=1, relief=tk.SOLID)
        self.color_preview.pack(side="left", padx=5)

        scale_sub = tk.Frame(sliders_frame, bg="#2d2d2d")
        scale_sub.pack(side="left", padx=5)

        self.r_scale = tk.Scale(scale_sub, from_=0, to=255, orient=tk.HORIZONTAL, label="R", bg="#2d2d2d", fg="#eeeeee", highlightthickness=0, command=self.on_slider_move)
        self.r_scale.set(255)
        self.r_scale.pack(pady=1)

        self.g_scale = tk.Scale(scale_sub, from_=0, to=255, orient=tk.HORIZONTAL, label="G", bg="#2d2d2d", fg="#eeeeee", highlightthickness=0, command=self.on_slider_move)
        self.g_scale.set(0)
        self.g_scale.pack(pady=1)

        self.b_scale = tk.Scale(scale_sub, from_=0, to=255, orient=tk.HORIZONTAL, label="B", bg="#2d2d2d", fg="#eeeeee", highlightthickness=0, command=self.on_slider_move)
        self.b_scale.set(0)
        self.b_scale.pack(pady=1)

    def create_preset_panel(self, parent):
        tk.Label(parent, text="Effect Mode:", bg="#2d2d2d", fg="#eeeeee").grid(row=0, column=0, sticky="w", pady=2)

        self.preset_modes = [m.name for m in Profile.Mode]
        self.selected_preset_mode = tk.StringVar(value="ALWAYS_ON")
        
        mode_menu = tk.OptionMenu(parent, self.selected_preset_mode, *self.preset_modes)
        mode_menu.config(bg="#3a3a3a", fg="#eeeeee", highlightthickness=0, relief=tk.FLAT, width=20)
        mode_menu["menu"].config(bg="#3a3a3a", fg="#eeeeee")
        mode_menu.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        tk.Label(parent, text="Speed:", bg="#2d2d2d", fg="#eeeeee").grid(row=1, column=0, sticky="w", pady=2)
        self.speed_scale = tk.Scale(parent, from_=0, to=5, orient=tk.HORIZONTAL, bg="#2d2d2d", fg="#eeeeee", highlightthickness=0)
        self.speed_scale.set(4)
        self.speed_scale.grid(row=1, column=1, sticky="we", pady=2, padx=5)

        tk.Label(parent, text="Brightness:", bg="#2d2d2d", fg="#eeeeee").grid(row=2, column=0, sticky="w", pady=2)
        self.brightness_scale = tk.Scale(parent, from_=0, to=4, orient=tk.HORIZONTAL, bg="#2d2d2d", fg="#eeeeee", highlightthickness=0)
        self.brightness_scale.set(4)
        self.brightness_scale.grid(row=2, column=1, sticky="we", pady=2, padx=5)

        self.dazzle_var = tk.BooleanVar(value=False)
        dazzle_cb = tk.Checkbutton(parent, text="Dazzle Effect", variable=self.dazzle_var, bg="#2d2d2d", fg="#eeeeee", selectcolor="#1e1e1e", activebackground="#2d2d2d")
        dazzle_cb.grid(row=3, column=0, columnspan=2, sticky="w", pady=2)

        apply_btn = tk.Button(
            parent, text="Apply Preset Effect", bg="#28a745", fg="#ffffff", font=F(9, "bold"),
            relief=tk.FLAT, bd=0, command=self.apply_preset_effect
        )
        apply_btn.grid(row=4, column=0, columnspan=2, sticky="we", pady=5)

    def create_actions_panel(self, parent):
        self.paint_brush_var = tk.BooleanVar(value=False)
        paint_cb = tk.Checkbutton(parent, text="Paint Brush Mode (Instant)", variable=self.paint_brush_var, bg="#2d2d2d", fg="#eeeeee", selectcolor="#1e1e1e", activebackground="#2d2d2d")
        paint_cb.pack(anchor="w", pady=2)

        select_all_btn = tk.Button(
            parent, text="Select All Keys", bg="#3a3a3a", fg="#eeeeee", font=F(9, "bold"),
            relief=tk.FLAT, bd=0, command=self.select_all_keys
        )
        select_all_btn.pack(fill="x", pady=2)

        save_btn = tk.Button(
            parent, text="Save Layout", bg="#3a3a3a", fg="#eeeeee", font=F(9, "bold"),
            relief=tk.FLAT, bd=0, command=self.save_layout
        )
        save_btn.pack(fill="x", pady=2)

        load_btn = tk.Button(
            parent, text="Load Layout", bg="#3a3a3a", fg="#eeeeee", font=F(9, "bold"),
            relief=tk.FLAT, bd=0, command=self.load_layout
        )
        load_btn.pack(fill="x", pady=2)

        clear_btn = tk.Button(
            parent, text="Clear All Keys", bg="#e94560", fg="#ffffff", font=F(9, "bold"),
            relief=tk.FLAT, bd=0, command=self.clear_all_keys
        )
        clear_btn.pack(fill="x", pady=2)

        if self.switch_callback is not None:
            switch_btn = tk.Button(
                parent, text="Switch to Screen Designer", bg="#4f46e5", fg="#ffffff", font=F(9, "bold"),
                relief=tk.FLAT, bd=0, command=lambda: self.switch_callback(self.root)
            )
            switch_btn.pack(fill="x", pady=4)

    def on_slider_move(self, _):
        r = self.r_scale.get()
        g = self.g_scale.get()
        b = self.b_scale.get()
        self.selected_color = (r, g, b)
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.color_preview.config(bg=hex_color)
        if self.selected_key:
            self.paint_selected_keys((r, g, b))

    def update_active_color(self, rgb):
        self.selected_color = rgb
        self.r_scale.set(rgb[0])
        self.g_scale.set(rgb[1])
        self.b_scale.set(rgb[2])
        hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        self.color_preview.config(bg=hex_color)
        if self.selected_key:
            self.paint_selected_keys(rgb)

    def select_key(self, key: KeyboardKey) -> None:
        if self.paint_brush_var.get():
            self.custom_mode_active = True
            hex_color = f"#{self.selected_color[0]:02x}{self.selected_color[1]:02x}{self.selected_color[2]:02x}"
            self.key_colours[key] = hex_color
            self.key_btn_dict[key].config(bg=hex_color, relief=tk.RAISED)
            self.apply_overlay({key}, self.selected_color)
            return

        if key in self.selected_key:
            self.selected_key.remove(key)
            original_color = self.key_colours.get(key)
            self.key_btn_dict[key].config(
                bg=original_color if original_color else "#2b2b2b",
                relief=tk.RAISED
            )
        else:
            self.selected_key.add(key)
            self.key_btn_dict[key].config(
                bg="#e94560",
                relief=tk.SUNKEN
            )

    def select_all_keys(self):
        for key in self.key_btn_dict.keys():
            if key not in self.selected_key:
                self.selected_key.add(key)
                self.key_btn_dict[key].config(
                    bg="#e94560",
                    relief=tk.SUNKEN
                )

    def paint_selected_keys(self, rgb):
        self.custom_mode_active = True
        hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        for key in self.selected_key:
            self.key_colours[key] = hex_color
            self.key_btn_dict[key].config(bg=hex_color, relief=tk.RAISED)
        self.apply_overlay(self.selected_key, rgb)
        self.selected_key.clear()

    def apply_colour_to_selected_keys(self, _: object) -> None:
        if self.selected_key:
            self.paint_selected_keys(self.selected_color)

    def apply_preset_effect(self):
        if not self.controller:
            messagebox.showerror("Error", "Controller not initialized.", parent=self.root)
            return

        try:
            mode_name = self.selected_preset_mode.get()
            mode_enum = Profile.Mode[mode_name]
            speed_val = self.speed_scale.get()
            brightness_val = self.brightness_scale.get()
            dazzle_val = Profile.Dazzle.ON if self.dazzle_var.get() else Profile.Dazzle.OFF

            profile = Profile(
                mode=mode_enum,
                speed=Profile.Speed(speed_val),
                brightness=Profile.Brightness(brightness_val),
                dazzle=dazzle_val,
                option=Profile.Option.OFF,
                rgb=self.selected_color
            )
            self.controller.set_profile(profile)
            self.custom_mode_active = False
            messagebox.showinfo("Success", f"Preset '{mode_name}' applied successfully!", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply preset: {e}", parent=self.root)

    def save_layout(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Key Layout JSON",
            initialdir=os.path.expanduser("~/Pictures"),
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")]
        )
        if not file_path:
            return

        try:
            import json
            layout_data = {}
            for key, val in self.key_colours.items():
                if val:
                    layout_data[key.name] = val

            with open(file_path, "w") as f:
                json.dump(layout_data, f, indent=4)

            messagebox.showinfo("Success", f"Layout saved successfully to {Path(file_path).name}", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save layout: {e}", parent=self.root)

    def load_layout(self):
        file_path = filedialog.askopenfilename(
            title="Load Key Layout JSON",
            initialdir=os.path.expanduser("~/Pictures"),
            filetypes=[("JSON Files", "*.json")]
        )
        if not file_path:
            return

        try:
            import json
            with open(file_path, "r") as f:
                layout_data = json.load(f)

            self.clear_all_keys()
            self.custom_mode_active = True

            for key_name, hex_color in layout_data.items():
                key = self.keyboard_keys.get_key_by_name(key_name)
                if key:
                    self.key_colours[key] = hex_color
                    self.key_btn_dict[key].config(bg=hex_color)
                    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                    self.apply_overlay({key}, (r, g, b))

            messagebox.showinfo("Success", "Layout loaded successfully!", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load layout: {e}", parent=self.root)

    def clear_all_keys(self):
        for key in self.key_btn_dict.keys():
            self.key_colours[key] = None
            self.key_btn_dict[key].config(bg="#2b2b2b", relief=tk.RAISED)
        self.apply_overlay(self.key_btn_dict.keys(), (0, 0, 0))
        self.selected_key.clear()
