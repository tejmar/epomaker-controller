import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
import os
import queue
import threading
import time
from pathlib import Path
from PIL import Image, ImageTk
from .fonts import F
from . import theme as T
from .bitmap_text import detect_git_repo_name, render_text_animation
from .recent_paths import load_recent, remember
from .screen_slots import (
    NUM_SLOTS,
    ensure_factory_slots,
    load_slot,
    reset_slot_to_factory,
    save_slot,
    slot_photoimage,
)

from ..epomakercontroller import EpomakerController
from ..configs.configs import load_main_config
from ..commands.data.constants import CAPABILITY_DYNATAB_SCREEN

WIDTH = 60
HEIGHT = 9
CELL_SIZE = 18  # pixels per grid cell in GUI
MAX_FRAMES = 15  # hardware-safe maximum animation frame count


def _frame_to_row_major(frame):
    """Convert a column-major frame list to PIL's row-major pixel order."""
    return [frame[x * HEIGHT + y] for y in range(HEIGHT) for x in range(WIDTH)]


class CropDialog(tk.Toplevel):
    def __init__(self, parent, image_path, callback):
        super().__init__(parent)
        T.style_root(self, "Crop Image to 60×9")
        self.transient(parent)
        self.grab_set()

        self.callback = callback
        self.original_img = Image.open(image_path)
        self.first_frame = self.original_img.copy().convert("RGB")

        # Fit inside max dimensions 800x600
        max_w, max_h = 800, 600
        w, h = self.first_frame.size
        scale = min(max_w / w, max_h / h, 1.0)
        self.scale = scale

        self.disp_w = int(w * scale)
        self.disp_h = int(h * scale)
        self.disp_img = self.first_frame.resize(
            (self.disp_w, self.disp_h), Image.Resampling.LANCZOS
        )
        self.tk_img = ImageTk.PhotoImage(self.disp_img)

        # Crop parameters: aspect ratio 60:9
        self.crop_w = int(max(60, min(w, h * (60 / 9))))
        self.crop_h = int(self.crop_w * (9 / 60))

        T.body_label(
            self,
            "Position mouse · scroll or buttons to resize · left-click to crop",
            bg=T.BG,
            pady=12,
            padx=12,
        ).pack()

        control_frame = tk.Frame(self, bg=T.BG)
        control_frame.pack(pady=5)
        T.button_secondary(
            control_frame, "Zoom in (smaller box)", command=self.zoom_in
        ).pack(side=tk.LEFT, padx=5)
        T.button_secondary(
            control_frame, "Zoom out (larger box)", command=self.zoom_out
        ).pack(side=tk.LEFT, padx=5)

        canvas_wrap = tk.Frame(
            self, bg=T.BORDER, highlightthickness=0, padx=1, pady=1
        )
        canvas_wrap.pack(padx=12, pady=10)
        self.canvas = tk.Canvas(
            canvas_wrap,
            width=self.disp_w,
            height=self.disp_h,
            bg=T.CANVAS_BG,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)

        # Crop box outline
        self.rect_id = self.canvas.create_rectangle(
            0, 0, 0, 0, outline=T.ACCENT, width=2
        )
        
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_in()) # Linux Scroll Up
        self.canvas.bind("<Button-5>", lambda e: self.zoom_out()) # Linux Scroll Down
        
        self.mouse_x = self.disp_w // 2
        self.mouse_y = self.disp_h // 2
        self.update_crop_box()
        
    def update_crop_box(self):
        w = int(self.crop_w * self.scale)
        h = int(self.crop_h * self.scale)
        
        x1 = self.mouse_x - w // 2
        y1 = self.mouse_y - h // 2
        x2 = x1 + w
        y2 = y1 + h
        
        # Keep box in bounds
        if x1 < 0:
            x1, x2 = 0, w
        if y1 < 0:
            y1, y2 = 0, h
        if x2 > self.disp_w:
            x1, x2 = self.disp_w - w, self.disp_w
        if y2 > self.disp_h:
            y1, y2 = self.disp_h - h, self.disp_h
            
        self.canvas.coords(self.rect_id, x1, y1, x2, y2)
        
    def on_mouse_move(self, event):
        self.mouse_x = event.x
        self.mouse_y = event.y
        self.update_crop_box()
        
    def on_mouse_wheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
            
    def zoom_in(self):
        self.crop_w = max(60, int(self.crop_w / 1.1))
        self.crop_h = int(self.crop_w * (9/60))
        self.update_crop_box()
        
    def zoom_out(self):
        max_w, max_h = self.original_img.size
        self.crop_w = min(max_w, int(self.crop_w * 1.1))
        self.crop_h = int(self.crop_w * (9/60))
        self.update_crop_box()
        
    def on_click(self, event):
        w = self.crop_w
        h = self.crop_h
        
        x_center_orig = event.x / self.scale
        y_center_orig = event.y / self.scale
        
        x1 = int(max(0, x_center_orig - w / 2))
        y1 = int(max(0, y_center_orig - h / 2))
        x2 = int(min(self.original_img.width, x1 + w))
        y2 = int(min(self.original_img.height, y1 + h))
        
        if x2 == self.original_img.width:
            x1 = max(0, x2 - w)
        if y2 == self.original_img.height:
            y1 = max(0, y2 - h)
            
        crop_box = (x1, y1, x1 + w, y1 + h)
        self.destroy()
        self.callback(self.original_img, crop_box)


class TextOnScreenDialog(tk.Toplevel):
    """Pick free text, a folder (git name), or a recent entry to paint on the 60×9."""

    def __init__(self, parent: tk.Tk, on_apply):
        super().__init__(parent)
        T.style_root(self, "Text on screen")
        self.transient(parent)
        self.grab_set()
        self.on_apply = on_apply
        self._recent = load_recent()

        body = tk.Frame(self, bg=T.BG, padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        T.body_label(
            body,
            "Type anything, pick a project folder, or choose a recent entry.",
            bg=T.BG,
            wraplength=420,
        ).pack(anchor="w", pady=(0, 8))

        T.muted_label(body, "Text to show", bg=T.BG).pack(anchor="w")
        self.text_var = tk.StringVar()
        # Prefill from cwd git if available
        name, _ = detect_git_repo_name()
        if name:
            self.text_var.set(name)
        entry = T.entry(body, textvariable=self.text_var, width=48)
        entry.pack(fill=tk.X, pady=(2, 8))
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._apply())

        row = tk.Frame(body, bg=T.BG)
        row.pack(fill=tk.X, pady=(0, 10))
        T.button_secondary(
            row, "Pick folder…", command=self._pick_folder
        ).pack(side=tk.LEFT)
        T.button_secondary(
            row, "Use cwd git", command=self._use_cwd_git
        ).pack(side=tk.LEFT, padx=6)

        T.muted_label(body, "Recent", bg=T.BG).pack(anchor="w", pady=(4, 2))
        list_wrap = tk.Frame(
            body, bg=T.BORDER, highlightthickness=0, padx=1, pady=1
        )
        list_wrap.pack(fill=tk.BOTH, expand=True)
        self.listbox = tk.Listbox(
            list_wrap,
            height=8,
            bg=T.SURFACE_2,
            fg=T.TEXT,
            selectbackground=T.ACCENT,
            selectforeground="#ffffff",
            activestyle="none",
            relief=tk.FLAT,
            bd=0,
            font=F(9),
            highlightthickness=0,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self._use_selected_recent())
        self.listbox.bind("<<ListboxSelect>>", self._on_recent_select)
        self._reload_list()

        btns = tk.Frame(body, bg=T.BG)
        btns.pack(fill=tk.X, pady=(12, 0))
        T.button_secondary(btns, "Cancel", command=self.destroy).pack(
            side=tk.RIGHT
        )
        T.button_success(btns, "Apply to editor", command=self._apply).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        self.geometry("480x420")
        self.minsize(400, 360)

    def _reload_list(self) -> None:
        self.listbox.delete(0, tk.END)
        self._recent = load_recent()
        for it in self._recent:
            kind = it.get("kind", "text")
            label = it.get("label") or it.get("value")
            prefix = "📁 " if kind == "folder" else "✏️ "
            self.listbox.insert(tk.END, f"{prefix}{label}")

    def _on_recent_select(self, _event=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        it = self._recent[sel[0]]
        # For folders, show repo/folder name in the entry (value is path)
        if it.get("kind") == "folder":
            name, _ = detect_git_repo_name(Path(it["value"]))
            self.text_var.set(name or Path(it["value"]).name)
        else:
            self.text_var.set(it.get("value") or "")

    def _use_selected_recent(self) -> None:
        self._on_recent_select()
        self._apply()

    def _pick_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self,
            title="Select project folder",
            initialdir=os.path.expanduser("~"),
        )
        if not path:
            return
        p = Path(path)
        name, top = detect_git_repo_name(p)
        display = name or p.name
        folder = str(top or p.resolve())
        self.text_var.set(display)
        remember("folder", folder, label=f"{display}  —  {folder}")
        self._reload_list()

    def _use_cwd_git(self) -> None:
        name, top = detect_git_repo_name()
        if not name:
            messagebox.showwarning(
                "No git repository",
                "No git repo found for the app’s current working directory.",
                parent=self,
            )
            return
        self.text_var.set(name)
        if top:
            remember("folder", str(top), label=f"{name}  —  {top}")
            self._reload_list()

    def _apply(self) -> None:
        text = self.text_var.get().strip()
        if not text:
            messagebox.showwarning(
                "Empty text", "Enter some text to show on the screen.", parent=self
            )
            return
        remember("text", text, label=text)
        self.on_apply(text)
        self.destroy()


class ScreenDesignerApp:
    def __init__(self, root: tk.Tk, switch_callback=None):
        self.root = root
        self.switch_callback = switch_callback
        T.style_root(root, "LED Screen Designer")
        self.root.resizable(False, False)

        # Main config & controller
        self.config_main = load_main_config()
        self.controller = EpomakerController(self.config_main)

        # Editor State
        # base_frames stores the unadjusted high-fidelity RGB tuples.
        # frames stores the active displayable RGB tuples.
        self.base_frames = [[(0, 0, 0) for _ in range(WIDTH * HEIGHT)]]
        self.frames = [[(0, 0, 0) for _ in range(WIDTH * HEIGHT)]]
        
        self.brightness_val = 1.0
        self.contrast_val = 1.0
        self.saturation_val = 1.0

        self.current_frame_idx = 0
        self.selected_color = (255, 0, 0)  # Default: Red
        self.delay_ms = 150
        self.is_playing = False
        self.play_job = None
        self._uploading = False
        self.draw_mode = "draw"  # draw, erase, eyedropper

        # Swatch palette colors
        self.palette = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (0, 255, 255),  # Cyan
            (255, 0, 255),  # Magenta
            (255, 255, 255),# White
            (255, 128, 0),  # Orange
            (255, 0, 128),  # Pink
            (128, 128, 128),# Grey
            (128, 0, 0),    # Dark Red
            (0, 128, 0),    # Dark Green
            (0, 0, 128),    # Dark Blue
            (0, 0, 0)       # Black/Eraser
        ]

        # Local preset slot thumbnails (PhotoImage refs must be kept alive)
        self._slot_photos: list = [None] * NUM_SLOTS
        self._slot_buttons: list = []
        self._slot_labels: list = []

        # Setup GUI layout
        self.setup_ui()
        self.update_canvas()
        self.update_frame_indicators()
        self.refresh_slot_thumbnails()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg=T.SURFACE)
        header.pack(fill=tk.X)
        T.title_label(
            header,
            "LED Screen Designer",
            bg=T.SURFACE,
            font=F(14, "bold"),
            pady=10,
            padx=16,
            anchor="w",
        ).pack(side=tk.LEFT)
        T.muted_label(
            header,
            "60×9 · up to 15 frames",
            bg=T.SURFACE,
            padx=16,
        ).pack(side=tk.RIGHT)

        main_frame = tk.Frame(self.root, bg=T.BG, padx=12, pady=12)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self._main_frame = main_frame

        # Left: tools + color
        left_outer, left_frame = T.card(main_frame)
        left_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.configure(width=128)

        T.section_label(left_frame, "Tools", bg=T.SURFACE).pack(
            anchor="w", pady=(2, 6)
        )

        self.draw_btn = T.button_tool(
            left_frame,
            "Draw",
            command=lambda: self.set_draw_mode("draw"),
            active=True,
            width=12,
        )
        self.draw_btn.pack(pady=3, fill=tk.X)

        self.erase_btn = T.button_tool(
            left_frame,
            "Erase",
            command=lambda: self.set_draw_mode("erase"),
            width=12,
        )
        self.erase_btn.pack(pady=3, fill=tk.X)

        self.dropper_btn = T.button_tool(
            left_frame,
            "Picker",
            command=lambda: self.set_draw_mode("eyedropper"),
            width=12,
        )
        self.dropper_btn.pack(pady=3, fill=tk.X)

        T.section_label(left_frame, "Color", bg=T.SURFACE).pack(
            anchor="w", pady=(14, 6)
        )
        preview_border = tk.Frame(left_frame, bg=T.BORDER, padx=2, pady=2)
        preview_border.pack(pady=4)
        self.color_preview = tk.Frame(
            preview_border, width=44, height=44, bg="#ff0000", bd=0
        )
        self.color_preview.pack()
        self.color_preview.pack_propagate(False)

        T.button_secondary(
            left_frame, "Custom…", command=self.choose_custom_color, width=12
        ).pack(pady=6, fill=tk.X)

        swatch_frame = tk.Frame(left_frame, bg=T.SURFACE)
        swatch_frame.pack(pady=(6, 4))
        for idx, col in enumerate(self.palette):
            r = idx // 2
            c = idx % 2
            btn = T.color_swatch_button(
                swatch_frame,
                col,
                command=lambda col_val=col: self.set_selected_color(col_val),
                width=5,
                height=1,
            )
            btn.grid(row=r, column=c, padx=3, pady=3)

        # Center: canvas + playback + adjustments
        center_frame = tk.Frame(main_frame, bg=T.BG)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_width = WIDTH * CELL_SIZE
        canvas_height = HEIGHT * CELL_SIZE
        canvas_card = tk.Frame(
            center_frame,
            bg=T.BORDER,
            padx=2,
            pady=2,
            highlightthickness=0,
        )
        canvas_card.pack(pady=(4, 10))
        self.canvas = tk.Canvas(
            canvas_card,
            width=canvas_width,
            height=canvas_height,
            bg=T.CANVAS_BG,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<B3-Motion>", self.on_canvas_right_drag)

        # Pre-create cell rectangles
        self.rects = []
        for c in range(WIDTH):
            col_rects = []
            for r in range(HEIGHT):
                x1 = c * CELL_SIZE
                y1 = r * CELL_SIZE
                x2 = x1 + CELL_SIZE - 1
                y2 = y1 + CELL_SIZE - 1
                rect_id = self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=T.CANVAS_BG,
                    outline=T.GRID_LINE,
                    width=1,
                )
                col_rects.append(rect_id)
            self.rects.append(col_rects)

        # Preset slots (8 local favorites with thumbnails)
        slots_outer, slots_frame = T.card(center_frame, "Presets — click to load · right-click to save / manage")
        slots_outer.pack(fill=tk.X, pady=(0, 8))
        self._build_slots_ui(slots_frame)

        controls_outer, controls_frame = T.card(center_frame)
        controls_outer.pack(fill=tk.X, pady=(0, 8))

        playback_sub = tk.Frame(controls_frame, bg=T.SURFACE)
        playback_sub.pack(fill=tk.X)

        self.play_btn = T.button_success(
            playback_sub, "Play preview", command=self.toggle_preview
        )
        self.play_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.prev_btn = T.button_secondary(
            playback_sub, "◀ Prev", command=self.prev_frame
        )
        self.prev_btn.pack(side=tk.LEFT, padx=3)

        self.frame_lbl = tk.Label(
            playback_sub,
            text="Frame 1 of 1",
            font=F(10, "bold"),
            bg=T.SURFACE,
            fg=T.TEXT,
            width=14,
        )
        self.frame_lbl.pack(side=tk.LEFT, padx=8)

        self.next_btn = T.button_secondary(
            playback_sub, "Next ▶", command=self.next_frame
        )
        self.next_btn.pack(side=tk.LEFT, padx=3)

        delay_sub = tk.Frame(controls_frame, bg=T.SURFACE)
        delay_sub.pack(fill=tk.X, pady=(10, 0))
        T.muted_label(delay_sub, "Frame delay (ms)", bg=T.SURFACE).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self.delay_entry = T.entry(delay_sub, width=6, justify=tk.CENTER)
        self.delay_entry.insert(0, str(self.delay_ms))
        self.delay_entry.pack(side=tk.LEFT)
        self.delay_entry.bind("<FocusOut>", self.update_delay)
        self.delay_entry.bind("<Return>", self.update_delay)

        adj_outer, adj_frame = T.card(center_frame, "Image adjustments")
        adj_outer.pack(fill=tk.X)

        self.bright_scale = T.scale(
            adj_frame,
            from_=0.0,
            to=2.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            label="Brightness",
            command=self.reapply_adjustments,
        )
        self.bright_scale.set(1.0)
        self.bright_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.contrast_scale = T.scale(
            adj_frame,
            from_=0.0,
            to=2.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            label="Contrast",
            command=self.reapply_adjustments,
        )
        self.contrast_scale.set(1.0)
        self.contrast_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.sat_scale = T.scale(
            adj_frame,
            from_=0.0,
            to=2.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            label="Saturation",
            command=self.reapply_adjustments,
        )
        self.sat_scale.set(1.0)
        self.sat_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        T.button_danger(adj_frame, "Reset", command=self.reset_sliders).pack(
            side=tk.RIGHT, padx=4, pady=(12, 0)
        )

        # Right sidebar
        right_outer, right_frame = T.card(main_frame)
        right_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        T.section_label(right_frame, "Frame edits", bg=T.SURFACE).pack(
            anchor="w", pady=(2, 6)
        )
        for label, cmd in (
            ("Add blank", self.add_frame),
            ("Duplicate", self.duplicate_frame),
            ("Delete", self.delete_frame),
            ("Clear grid", self.clear_frame),
        ):
            T.button_secondary(right_frame, label, command=cmd, width=14).pack(
                pady=3, fill=tk.X
            )

        T.section_label(right_frame, "Shift pattern", bg=T.SURFACE).pack(
            anchor="w", pady=(14, 6)
        )
        shift_pad = tk.Frame(right_frame, bg=T.SURFACE)
        shift_pad.pack(pady=4)
        T.button_secondary(
            shift_pad, "▲", command=lambda: self.shift_frame("up"), width=3
        ).grid(row=0, column=1, pady=2)
        T.button_secondary(
            shift_pad, "◀", command=lambda: self.shift_frame("left"), width=3
        ).grid(row=1, column=0, padx=2)
        T.button_secondary(
            shift_pad, "▶", command=lambda: self.shift_frame("right"), width=3
        ).grid(row=1, column=2, padx=2)
        T.button_secondary(
            shift_pad, "▼", command=lambda: self.shift_frame("down"), width=3
        ).grid(row=2, column=1, pady=2)

        T.section_label(right_frame, "File", bg=T.SURFACE).pack(
            anchor="w", pady=(14, 6)
        )
        T.button_primary(
            right_frame, "Import GIF / image", command=self.import_file, width=14
        ).pack(pady=3, fill=tk.X)
        T.button_secondary(
            right_frame, "Export as GIF", command=self.export_gif, width=14
        ).pack(pady=3, fill=tk.X)
        T.button_success(
            right_frame,
            "Text / git…",
            command=self.open_text_on_screen_dialog,
            width=14,
        ).pack(pady=3, fill=tk.X)
        T.muted_label(
            right_frame,
            "Folder, recent, or\nany custom text",
            bg=T.SURFACE,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 4))

        T.section_label(right_frame, "Hardware", bg=T.SURFACE).pack(
            anchor="w", pady=(14, 6)
        )
        self.upload_btn = T.button_danger(
            right_frame,
            "Send to screen",
            command=self.upload_to_device,
            width=14,
            font=F(10, "bold"),
        )
        self.upload_btn.pack(pady=4, fill=tk.X)

        if self.switch_callback is not None:
            T.button_primary(
                right_frame,
                "← Key backlight",
                command=lambda: self.switch_callback(self.root),
                width=14,
            ).pack(pady=6, fill=tk.X)

    # Frame and Coordinate helpers (Column-major layout)
    def get_pixel(self, col, row):
        frame = self.frames[self.current_frame_idx]
        return frame[col * HEIGHT + row]

    def set_pixel(self, col, row, color):
        idx = col * HEIGHT + row
        # Store unadjusted color in base_frames
        self.base_frames[self.current_frame_idx][idx] = color
        # Compute adjusted color for active frames
        b = self.brightness_val
        c = self.contrast_val
        s = self.saturation_val
        self.frames[self.current_frame_idx][idx] = self.adjust_pixel(color, b, c, s)

    @staticmethod
    def adjust_pixel(rgb, brightness, contrast, saturation):
        r, g, b = rgb
        
        # 1. Apply Brightness (0.0 to 2.0)
        if brightness != 1.0:
            r = r * brightness
            g = g * brightness
            b = b * brightness
            
        # 2. Apply Contrast (0.0 to 2.0)
        if contrast != 1.0:
            r = 127.5 + (r - 127.5) * contrast
            g = 127.5 + (g - 127.5) * contrast
            b = 127.5 + (b - 127.5) * contrast
            
        # 3. Apply Saturation (0.0 to 2.0)
        if saturation != 1.0:
            gray = 0.299 * r + 0.587 * g + 0.114 * b
            r = gray + (r - gray) * saturation
            g = gray + (g - gray) * saturation
            b = gray + (b - gray) * saturation
            
        # Clamp to bounds
        rc = max(0, min(255, int(r)))
        gc = max(0, min(255, int(g)))
        bc = max(0, min(255, int(b)))
        return (rc, gc, bc)

    def reapply_adjustments(self, *args):
        try:
            self.brightness_val = self.bright_scale.get()
            self.contrast_val = self.contrast_scale.get()
            self.saturation_val = self.sat_scale.get()
        except Exception:
            pass # Widgets destroyed
            
        b = self.brightness_val
        c = self.contrast_val
        s = self.saturation_val
        
        for f_idx, base_frame in enumerate(self.base_frames):
            for p_idx, rgb in enumerate(base_frame):
                self.frames[f_idx][p_idx] = self.adjust_pixel(rgb, b, c, s)
                
        self.update_canvas()

    def reset_sliders(self):
        self.brightness_val = 1.0
        self.contrast_val = 1.0
        self.saturation_val = 1.0
        try:
            self.bright_scale.set(1.0)
            self.contrast_scale.set(1.0)
            self.sat_scale.set(1.0)
        except Exception:
            pass
        self.reapply_adjustments()

    # Painting and Mouse Events
    def set_selected_color(self, rgb_tuple):
        self.selected_color = rgb_tuple
        self.color_preview.configure(bg=T.hex_rgb(rgb_tuple))
        self.set_draw_mode("draw")

    def choose_custom_color(self):
        _, hex_color = colorchooser.askcolor(
            initialcolor=T.hex_rgb(self.selected_color)
        )
        if hex_color:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            self.set_selected_color((r, g, b))

    def set_draw_mode(self, mode):
        self.draw_mode = mode
        T.set_tool_active(self.draw_btn, mode == "draw")
        T.set_tool_active(self.erase_btn, mode == "erase")
        T.set_tool_active(self.dropper_btn, mode == "eyedropper")

    # --- Preset slots ---------------------------------------------------------

    def _build_slots_ui(self, parent: tk.Frame) -> None:
        ensure_factory_slots()
        grid = tk.Frame(parent, bg=T.SURFACE)
        grid.pack(fill=tk.X)
        self._slot_buttons = []
        self._slot_labels = []
        for i in range(NUM_SLOTS):
            cell = tk.Frame(grid, bg=T.SURFACE)
            cell.grid(row=0, column=i, padx=4, pady=2, sticky="n")
            btn = tk.Button(
                cell,
                text="",
                bg=T.SURFACE_2,
                activebackground=T.SURFACE_3,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=1,
                highlightbackground=T.BORDER,
                cursor="hand2",
                command=lambda idx=i: self.load_slot_into_editor(idx),
            )
            btn.pack()
            btn.bind(
                "<Button-3>",
                lambda e, idx=i: self._slot_context_menu(e, idx),
            )
            # Linux sometimes uses Button-2 for right-click alternatives; keep 3
            lbl = tk.Label(
                cell,
                text=f"{i + 1}",
                font=F(7),
                bg=T.SURFACE,
                fg=T.TEXT_DIM,
            )
            lbl.pack()
            self._slot_buttons.append(btn)
            self._slot_labels.append(lbl)

        hint = T.muted_label(
            parent,
            "Tip: right-click a slot to save the current animation, clear, or restore factory art.",
            bg=T.SURFACE,
            wraplength=900,
            justify=tk.LEFT,
        )
        hint.pack(anchor="w", pady=(6, 0))

    def refresh_slot_thumbnails(self) -> None:
        ensure_factory_slots()
        for i in range(NUM_SLOTS):
            photo, name = slot_photoimage(i, scale=2)
            self._slot_photos[i] = photo  # prevent GC
            if photo is not None:
                self._slot_buttons[i].configure(image=photo, text="")
            self._slot_labels[i].configure(text=f"{i + 1} · {name[:10]}")

    def load_slot_into_editor(self, index: int) -> None:
        data = load_slot(index)
        if not data:
            messagebox.showinfo(
                "Empty slot",
                f"Slot {index + 1} is empty. Right-click to save the current design here.",
                parent=self.root,
            )
            return
        if self.is_playing:
            self.toggle_preview()
        self.base_frames = [list(f) for f in data["frames"]]
        self.frames = [list(f) for f in data["frames"]]
        self.current_frame_idx = 0
        self.delay_ms = data["delay_ms"]
        self.delay_entry.delete(0, tk.END)
        self.delay_entry.insert(0, str(self.delay_ms))
        self.bright_scale.set(1.0)
        self.contrast_scale.set(1.0)
        self.sat_scale.set(1.0)
        self.brightness_val = self.contrast_val = self.saturation_val = 1.0
        self.reapply_adjustments()
        self.update_frame_indicators()

    def save_current_to_slot(self, index: int) -> None:
        name = f"Custom {index + 1}"
        save_slot(
            index,
            [list(f) for f in self.base_frames],
            self.delay_ms,
            name=name,
            factory=False,
        )
        self.refresh_slot_thumbnails()
        messagebox.showinfo(
            "Saved",
            f"Current animation saved to slot {index + 1}.",
            parent=self.root,
        )

    def _slot_context_menu(self, event, index: int) -> None:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=T.SURFACE_2,
            fg=T.TEXT,
            activebackground=T.ACCENT,
            activeforeground="#ffffff",
        )
        menu.add_command(
            label=f"Load slot {index + 1}",
            command=lambda: self.load_slot_into_editor(index),
        )
        menu.add_command(
            label="Save current design here",
            command=lambda: self.save_current_to_slot(index),
        )
        menu.add_separator()
        menu.add_command(
            label="Restore factory preset",
            command=lambda: self._restore_factory_slot(index),
        )
        menu.add_command(
            label="Clear slot",
            command=lambda: self._clear_slot(index),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _restore_factory_slot(self, index: int) -> None:
        reset_slot_to_factory(index)
        self.refresh_slot_thumbnails()

    def _clear_slot(self, index: int) -> None:
        # Overwrite with a blank design (do not delete the file, or factory re-seed
        # would repopulate the slot on next ensure_factory_slots call).
        save_slot(
            index,
            [[(0, 0, 0) for _ in range(WIDTH * HEIGHT)]],
            100,
            name="Empty",
            factory=False,
        )
        self.refresh_slot_thumbnails()

    def open_text_on_screen_dialog(self) -> None:
        """Dialog: free text, pick folder (git name), or recent entries."""
        TextOnScreenDialog(self.root, on_apply=self.apply_text_to_editor)

    def apply_text_to_editor(self, text: str) -> None:
        """Paint arbitrary text (repo name, branch, note, …) onto the 60×9 grid."""
        text = (text or "").strip()
        if not text:
            return
        if self.is_playing:
            self.toggle_preview()
        frames = render_text_animation(
            text,
            color=(0, 220, 140),
            max_frames=MAX_FRAMES,
            scroll=True,
        )
        self.base_frames = [list(f) for f in frames]
        self.frames = [list(f) for f in frames]
        self.current_frame_idx = 0
        self.delay_ms = 100 if len(frames) > 1 else 250
        self.delay_entry.delete(0, tk.END)
        self.delay_entry.insert(0, str(self.delay_ms))
        self.bright_scale.set(1.0)
        self.contrast_scale.set(1.0)
        self.sat_scale.set(1.0)
        self.brightness_val = self.contrast_val = self.saturation_val = 1.0
        self.reapply_adjustments()
        self.update_frame_indicators()

    def paint_cell(self, event, erase=False):
        c = event.x // CELL_SIZE
        r = event.y // CELL_SIZE
        if 0 <= c < WIDTH and 0 <= r < HEIGHT:
            if self.draw_mode == "eyedropper" and not erase:
                # Pick any pixel colour, including black (black is a valid swatch).
                self.set_selected_color(self.get_pixel(c, r))
                return
            
            color = (0, 0, 0) if (erase or self.draw_mode == "erase") else self.selected_color
            self.set_pixel(c, r, color)
            
            # Fetch the actual adjusted color from self.frames to render on the GUI canvas
            adjusted_col = self.get_pixel(c, r)
            hex_color = f"#{adjusted_col[0]:02x}{adjusted_col[1]:02x}{adjusted_col[2]:02x}"
            self.canvas.itemconfig(self.rects[c][r], fill=hex_color)

    def on_canvas_click(self, event):
        self.paint_cell(event)

    def on_canvas_drag(self, event):
        self.paint_cell(event)

    def on_canvas_right_click(self, event):
        self.paint_cell(event, erase=True)

    def on_canvas_right_drag(self, event):
        self.paint_cell(event, erase=True)

    # Frame Navigation and Operations
    def add_frame(self):
        if len(self.frames) >= MAX_FRAMES:
            messagebox.showwarning("Frame Limit", f"Maximum of {MAX_FRAMES} frames allowed to prevent keyboard memory issues.", parent=self.root)
            return
        new_frame = [(0, 0, 0) for _ in range(WIDTH * HEIGHT)]
        self.base_frames.insert(self.current_frame_idx + 1, new_frame)
        self.frames.insert(self.current_frame_idx + 1, list(new_frame))
        self.current_frame_idx += 1
        self.update_canvas()
        self.update_frame_indicators()

    def duplicate_frame(self):
        if len(self.frames) >= MAX_FRAMES:
            messagebox.showwarning("Frame Limit", f"Maximum of {MAX_FRAMES} frames allowed to prevent keyboard memory issues.", parent=self.root)
            return
        current_base = self.base_frames[self.current_frame_idx]
        new_base = list(current_base)
        self.base_frames.insert(self.current_frame_idx + 1, new_base)
        
        # Insert a copy and reapply adjustments to populate self.frames properly
        self.frames.insert(self.current_frame_idx + 1, list(new_base))
        self.current_frame_idx += 1
        self.reapply_adjustments()
        self.update_frame_indicators()

    def delete_frame(self):
        if len(self.frames) <= 1:
            messagebox.showwarning("Warning", "Cannot delete the only frame.", parent=self.root)
            return
        self.base_frames.pop(self.current_frame_idx)
        self.frames.pop(self.current_frame_idx)
        if self.current_frame_idx >= len(self.frames):
            self.current_frame_idx = len(self.frames) - 1
        self.update_canvas()
        self.update_frame_indicators()

    def clear_frame(self):
        self.base_frames[self.current_frame_idx] = [(0, 0, 0) for _ in range(WIDTH * HEIGHT)]
        self.reapply_adjustments()

    def prev_frame(self):
        if self.current_frame_idx > 0:
            self.current_frame_idx -= 1
            self.update_canvas()
            self.update_frame_indicators()

    def next_frame(self):
        if self.current_frame_idx < len(self.frames) - 1:
            self.current_frame_idx += 1
            self.update_canvas()
            self.update_frame_indicators()

    def shift_frame(self, direction):
        if direction not in ("left", "right", "up", "down"):
            raise ValueError(f"Unknown shift direction: {direction!r}")
        frame = self.base_frames[self.current_frame_idx]
        new_frame = list(frame)
        
        for c in range(WIDTH):
            for r in range(HEIGHT):
                if direction == "left":
                    src_c, src_r = (c + 1) % WIDTH, r
                elif direction == "right":
                    src_c, src_r = (c - 1) % WIDTH, r
                elif direction == "up":
                    src_c, src_r = c, (r + 1) % HEIGHT
                elif direction == "down":
                    src_c, src_r = c, (r - 1) % HEIGHT
                
                # Copy src pixel to dest
                new_frame[c * HEIGHT + r] = frame[src_c * HEIGHT + src_r]
                
        self.base_frames[self.current_frame_idx] = new_frame
        self.reapply_adjustments()

    # GUI Canvas Updates
    def update_canvas(self):
        frame = self.frames[self.current_frame_idx]
        for c in range(WIDTH):
            for r in range(HEIGHT):
                color = frame[c * HEIGHT + r]
                hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                self.canvas.itemconfig(self.rects[c][r], fill=hex_color)

    def update_frame_indicators(self):
        self.frame_lbl.configure(text=f"Frame {self.current_frame_idx + 1} of {len(self.frames)}")

    def update_delay(self, event=None):
        try:
            val = int(self.delay_entry.get())
            if 1 <= val <= 1000:
                self.delay_ms = val
            else:
                self.delay_entry.delete(0, tk.END)
                self.delay_entry.insert(0, str(self.delay_ms))
        except ValueError:
            self.delay_entry.delete(0, tk.END)
            self.delay_entry.insert(0, str(self.delay_ms))

    # Playback Preview
    def toggle_preview(self):
        if self.is_playing:
            self.is_playing = False
            self.play_btn.configure(
                text="▶ Play preview",
                bg=T.SUCCESS,
                activebackground=T.SUCCESS_HOVER,
                fg="#0b1a12",
            )
            if self.play_job:
                self.root.after_cancel(self.play_job)
                self.play_job = None
        else:
            self.is_playing = True
            self.play_btn.configure(
                text="⏸ Pause",
                bg=T.WARN,
                activebackground=T.WARN,
                fg="#111318",
            )
            self.run_preview()

    def run_preview(self):
        if not self.is_playing:
            return
        
        self.current_frame_idx = (self.current_frame_idx + 1) % len(self.frames)
        self.update_canvas()
        self.update_frame_indicators()
        
        self.play_job = self.root.after(self.delay_ms, self.run_preview)

    # Import / Export
    def import_file(self):
        file_path = filedialog.askopenfilename(
            title="Import GIF or Image",
            initialdir=os.path.expanduser("~/Pictures"),
            filetypes=[("All Image Files", "*.gif *.png *.jpg *.jpeg *.bmp *.webp"),
                       ("Animated GIF", "*.gif"),
                       ("Static Images", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if not file_path:
            return

        try:
            img = Image.open(file_path)
            if img.width > WIDTH or img.height > HEIGHT:
                CropDialog(self.root, file_path, self.process_import)
            else:
                crop_box = (0, 0, img.width, img.height)
                self.process_import(img, crop_box)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}", parent=self.root)

    def process_import(self, img, crop_box):
        try:
            file_path = img.filename if hasattr(img, "filename") else ""
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            imported_frames = []
            gif_img = Image.open(file_path) if file_path else img
            
            try:
                while True:
                    frame_img = gif_img.copy().convert("RGB").crop(crop_box).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                    # Convert to column-major tuple list
                    col_major_pixels = []
                    for x in range(WIDTH):
                        for y in range(HEIGHT):
                            col_major_pixels.append(frame_img.getpixel((x, y)))
                    imported_frames.append(col_major_pixels)
                    
                    if ext == ".gif":
                        gif_img.seek(gif_img.tell() + 1)
                    else:
                        break
            except EOFError:
                pass
            
            if imported_frames:
                if len(imported_frames) > MAX_FRAMES:
                    imported_frames = imported_frames[:MAX_FRAMES]
                    messagebox.showwarning(
                        "Animation Truncated",
                        "The imported animation had more than 15 frames and was truncated to the first 15 frames.",
                        parent=self.root
                    )
                self.base_frames = imported_frames
                self.frames = [list(f) for f in imported_frames]
                self.current_frame_idx = 0
                
                # Reset sliders so that they start fresh with the new import
                self.bright_scale.set(1.0)
                self.contrast_scale.set(1.0)
                self.sat_scale.set(1.0)
                self.reapply_adjustments()
                
                self.update_frame_indicators()
                messagebox.showinfo("Success", f"Successfully imported {len(self.frames)} frame(s)!", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import crop: {e}", parent=self.root)

    def export_gif(self):
        file_path = filedialog.asksaveasfilename(
            title="Export Animation as GIF",
            initialdir=os.path.expanduser("~/Pictures"),
            defaultextension=".gif",
            filetypes=[("Animated GIF", "*.gif")]
        )
        if not file_path:
            return

        try:
            pil_frames = []
            for frame in self.frames:
                row_major = _frame_to_row_major(frame)
                        
                img = Image.new("RGB", (WIDTH, HEIGHT))
                img.putdata(row_major)
                # Scale up to make it easy to view/share
                scaled_img = img.resize((WIDTH * 10, HEIGHT * 10), Image.Resampling.NEAREST)
                pil_frames.append(scaled_img)

            pil_frames[0].save(
                file_path,
                save_all=True,
                append_images=pil_frames[1:],
                duration=self.delay_ms,
                loop=0
            )
            messagebox.showinfo("Success", f"Animation saved to {file_path}", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export GIF: {e}", parent=self.root)

    # Device Upload
    def upload_to_device(self):
        if self._uploading:
            return  # an upload is already in progress
        if not self.controller.has_capability(CAPABILITY_DYNATAB_SCREEN):
            messagebox.showerror(
                "Error",
                "This keyboard model does not support DynaTab screen upload.\n"
                "Set CAPABILITIES to include \"dynatab_screen\" in "
                "~/.epomaker-controller/config.json.",
                parent=self.root,
            )
            return
        if self.is_playing:
            self.toggle_preview()  # Pause preview before upload

        # Snapshot frames on the UI thread so the worker gets a stable copy.
        frames_snapshot = [list(frame) for frame in self.frames]
        delay_ms = self.delay_ms

        # Enter "uploading" state: the slow device write runs in a worker thread
        # so the window stays responsive (it no longer freezes for ~12s).
        self._uploading = True
        self.upload_btn.config(state=tk.DISABLED)
        status_frame = tk.Frame(self.root, bg=T.DANGER)
        status_frame.pack(fill=tk.X, before=self._main_frame)
        tk.Label(
            status_frame,
            text="Uploading — keyboard will reboot. Do not unplug.",
            font=F(10, "bold"),
            bg=T.DANGER,
            fg="#ffffff",
            pady=8,
        ).pack(side=tk.LEFT, padx=12)
        progress = ttk.Progressbar(status_frame, mode="indeterminate", length=220)
        progress.pack(side=tk.LEFT, pady=6)
        progress.start(12)

        def _finish(error):
            try:
                progress.stop()
                status_frame.destroy()
            except tk.TclError:
                pass  # window was closed while uploading
            self._uploading = False
            try:
                self.upload_btn.config(state=tk.NORMAL)
                if error:
                    messagebox.showerror("Error", f"Upload failed: {error}", parent=self.root)
                else:
                    messagebox.showinfo("Success", "Animation uploaded successfully!", parent=self.root)
            except tk.TclError:
                pass

        def _worker():
            error = None
            try:
                # Close the main handle so iface 2/0 opens do not conflict.
                self.controller.close_device()
                self.controller.send_dynatab_frames(
                    frames_snapshot, delay_ms=delay_ms
                )
            except Exception as e:
                error = str(e)
            finally:
                try:
                    self.controller.close_device()
                except Exception:
                    pass
            # Signal completion via a thread-safe queue; the main thread polls it.
            # (Never call into Tk from this worker thread — it is not thread-safe.)
            self._upload_queue.put(error)

        def _poll():
            try:
                error = self._upload_queue.get_nowait()
            except queue.Empty:
                self.root.after(100, _poll)
                return
            _finish(error)

        self._upload_queue = queue.Queue()
        threading.Thread(target=_worker, daemon=True).start()
        self.root.after(100, _poll)

def main():
    root = tk.Tk()
    app = ScreenDesignerApp(root)
    
    # Clean exit helper
    def on_close():
        if app.is_playing:
            app.is_playing = False
        app.controller.close_device()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
