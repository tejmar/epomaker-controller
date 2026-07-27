import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
import os
import queue
import threading
import time
from PIL import Image, ImageTk
from .fonts import F, get_ui_font

from ..epomakercontroller import EpomakerController
from ..configs.configs import load_main_config
from ..commands.data.constants import CAPABILITY_DYNATAB_SCREEN

WIDTH = 60
HEIGHT = 9
CELL_SIZE = 16  # pixels per grid cell in GUI
MAX_FRAMES = 15  # hardware-safe maximum animation frame count


def _frame_to_row_major(frame):
    """Convert a column-major frame list to PIL's row-major pixel order."""
    return [frame[x * HEIGHT + y] for y in range(HEIGHT) for x in range(WIDTH)]


class CropDialog(tk.Toplevel):
    def __init__(self, parent, image_path, callback):
        super().__init__(parent)
        self.title("Crop Image to 60x9")
        self.configure(bg="#1e1e1e")
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
        self.disp_img = self.first_frame.resize((self.disp_w, self.disp_h), Image.Resampling.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(self.disp_img)
        
        # Crop parameters: aspect ratio 60:9
        self.crop_w = int(max(60, min(w, h * (60/9))))
        self.crop_h = int(self.crop_w * (9/60))
        
        tk.Label(
            self,
            text="Position mouse. Scroll wheel or use buttons to resize. Left-click to crop.",
            font=F(10), bg="#1e1e1e", fg="#eeeeee", pady=10
        ).pack()
        
        # Zoom controls
        control_frame = tk.Frame(self, bg="#1e1e1e")
        control_frame.pack(pady=5)
        tk.Button(
            control_frame, text="Zoom In (Smaller Box)", bg="#3a3a3a", fg="#eeeeee",
            command=self.zoom_in, relief=tk.FLAT, bd=0, padx=10
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            control_frame, text="Zoom Out (Larger Box)", bg="#3a3a3a", fg="#eeeeee",
            command=self.zoom_out, relief=tk.FLAT, bd=0, padx=10
        ).pack(side=tk.LEFT, padx=5)
        
        self.canvas = tk.Canvas(self, width=self.disp_w, height=self.disp_h, bg="#000000", highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)
        
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        
        # Crop box outline
        self.rect_id = self.canvas.create_rectangle(0, 0, 0, 0, outline="#00adb5", width=2)
        
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


class ScreenDesignerApp:
    def __init__(self, root: tk.Tk, switch_callback=None):
        self.root = root
        self.switch_callback = switch_callback
        self.root.title("Epomaker LED Screen Designer")
        self.root.configure(bg="#1e1e1e")
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

        # Setup GUI layout
        self.setup_ui()
        self.update_canvas()
        self.update_frame_indicators()

    def setup_ui(self):
        # 1. Title bar
        title_lbl = tk.Label(
            self.root,
            text="Epomaker LED Screen Designer",
            font=F(16, "bold"),
            bg="#1e1e1e",
            fg="#eeeeee",
            pady=10
        )
        title_lbl.pack(fill=tk.X)

        # 2. Main content container
        main_frame = tk.Frame(self.root, bg="#1e1e1e", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left Column: Tool & Color Toolbar
        left_frame = tk.Frame(main_frame, bg="#2d2d2d", width=120, bd=1, relief=tk.FLAT)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Mode label
        tk.Label(left_frame, text="TOOLS", font=F(9, "bold"), bg="#2d2d2d", fg="#888888").pack(pady=(10, 5))

        # Tool buttons
        self.draw_btn = tk.Button(
            left_frame, text="Draw", bg="#00adb5", fg="#ffffff", font=F(9),
            activebackground="#00adb5", activeforeground="#ffffff", relief=tk.FLAT, bd=0, width=12,
            command=lambda: self.set_draw_mode("draw")
        )
        self.draw_btn.pack(pady=3, padx=10)

        self.erase_btn = tk.Button(
            left_frame, text="Erase", bg="#3a3a3a", fg="#eeeeee", font=F(9),
            relief=tk.FLAT, bd=0, width=12,
            command=lambda: self.set_draw_mode("erase")
        )
        self.erase_btn.pack(pady=3, padx=10)

        self.dropper_btn = tk.Button(
            left_frame, text="Picker", bg="#3a3a3a", fg="#eeeeee", font=F(9),
            relief=tk.FLAT, bd=0, width=12,
            command=lambda: self.set_draw_mode("eyedropper")
        )
        self.dropper_btn.pack(pady=3, padx=10)

        # Color Preview Indicator
        tk.Label(left_frame, text="COLOR", font=F(9, "bold"), bg="#2d2d2d", fg="#888888").pack(pady=(15, 5))
        self.color_preview = tk.Frame(left_frame, width=40, height=40, bg="#ff0000", bd=2, relief=tk.SOLID)
        self.color_preview.pack(pady=5)
        self.color_preview.pack_propagate(False)

        custom_color_btn = tk.Button(
            left_frame, text="Custom...", bg="#3a3a3a", fg="#eeeeee", font=F(8),
            relief=tk.FLAT, bd=0, width=12, command=self.choose_custom_color
        )
        custom_color_btn.pack(pady=5)

        # Palettes
        swatch_frame = tk.Frame(left_frame, bg="#2d2d2d")
        swatch_frame.pack(pady=(10, 10))
        for idx, col in enumerate(self.palette):
            r = idx // 2
            c = idx % 2
            hex_color = f"#{col[0]:02x}{col[1]:02x}{col[2]:02x}"
            btn = tk.Button(
                swatch_frame, bg=hex_color, activebackground=hex_color,
                relief=tk.FLAT, bd=1, highlightthickness=0, width=4, height=1,
                command=lambda col_val=col: self.set_selected_color(col_val)
            )
            btn.grid(row=r, column=c, padx=3, pady=3)

        # Center Column: Main editor canvas, playback controls, and sliders
        center_frame = tk.Frame(main_frame, bg="#1e1e1e")
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Screen grid canvas
        canvas_width = WIDTH * CELL_SIZE
        canvas_height = HEIGHT * CELL_SIZE
        self.canvas = tk.Canvas(
            center_frame, width=canvas_width, height=canvas_height,
            bg="#000000", highlightthickness=0, bd=0
        )
        self.canvas.pack(pady=10)

        # Mouse event binds for drawing
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<B3-Motion>", self.on_canvas_right_drag)

        # Pre-create all rectangle widgets on the canvas for maximum performance
        self.rects = []
        for c in range(WIDTH):
            col_rects = []
            for r in range(HEIGHT):
                x1 = c * CELL_SIZE
                y1 = r * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE
                rect_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill="#000000", outline="#222222", width=1
                )
                col_rects.append(rect_id)
            self.rects.append(col_rects)

        # Frame navigation & playback control frame
        controls_frame = tk.Frame(center_frame, bg="#2d2d2d", pady=10, padx=10)
        controls_frame.pack(fill=tk.X, pady=(10, 0))

        playback_sub = tk.Frame(controls_frame, bg="#2d2d2d")
        playback_sub.pack(fill=tk.X)

        self.play_btn = tk.Button(
            playback_sub, text="Play Preview", bg="#28a745", fg="#ffffff", font=F(9, "bold"),
            relief=tk.FLAT, bd=0, padx=12, command=self.toggle_preview
        )
        self.play_btn.pack(side=tk.LEFT, padx=10)

        self.prev_btn = tk.Button(
            playback_sub, text="Prev Frame", bg="#3a3a3a", fg="#eeeeee", font=F(9),
            relief=tk.FLAT, bd=0, command=self.prev_frame
        )
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.frame_lbl = tk.Label(
            playback_sub, text="Frame 1 of 1", font=F(10, "bold"),
            bg="#2d2d2d", fg="#eeeeee", width=15
        )
        self.frame_lbl.pack(side=tk.LEFT, padx=5)

        self.next_btn = tk.Button(
            playback_sub, text="Next Frame", bg="#3a3a3a", fg="#eeeeee", font=F(9),
            relief=tk.FLAT, bd=0, command=self.next_frame
        )
        self.next_btn.pack(side=tk.LEFT, padx=5)

        # Delay Control
        delay_sub = tk.Frame(controls_frame, bg="#2d2d2d", pady=10)
        delay_sub.pack(fill=tk.X)
        tk.Label(
            delay_sub, text="Frame Delay (ms):", font=F(9),
            bg="#2d2d2d", fg="#bbbbbb"
        ).pack(side=tk.LEFT, padx=(10, 5))
        
        self.delay_entry = tk.Entry(
            delay_sub, bg="#1e1e1e", fg="#eeeeee", insertbackground="#eeeeee",
            font=F(9), width=6, justify=tk.CENTER, bd=0
        )
        self.delay_entry.insert(0, str(self.delay_ms))
        self.delay_entry.pack(side=tk.LEFT, padx=5)
        self.delay_entry.bind("<FocusOut>", self.update_delay)
        self.delay_entry.bind("<Return>", self.update_delay)

        # 3. Image Adjustments Subframe (Sliders)
        adj_frame = tk.LabelFrame(
            center_frame, text="Image Adjustments", bg="#2d2d2d", fg="#888888",
            font=F(9, "bold"), padx=10, pady=5
        )
        adj_frame.pack(fill=tk.X, pady=(10, 0))

        # Pack sliders in a row
        self.bright_scale = tk.Scale(
            adj_frame, from_=0.0, to=2.0, resolution=0.05, orient=tk.HORIZONTAL,
            label="Brightness", bg="#2d2d2d", fg="#eeeeee", highlightthickness=0,
            command=self.reapply_adjustments
        )
        self.bright_scale.set(1.0)
        self.bright_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.contrast_scale = tk.Scale(
            adj_frame, from_=0.0, to=2.0, resolution=0.05, orient=tk.HORIZONTAL,
            label="Contrast", bg="#2d2d2d", fg="#eeeeee", highlightthickness=0,
            command=self.reapply_adjustments
        )
        self.contrast_scale.set(1.0)
        self.contrast_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.sat_scale = tk.Scale(
            adj_frame, from_=0.0, to=2.0, resolution=0.05, orient=tk.HORIZONTAL,
            label="Saturation", bg="#2d2d2d", fg="#eeeeee", highlightthickness=0,
            command=self.reapply_adjustments
        )
        self.sat_scale.set(1.0)
        self.sat_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        reset_adj_btn = tk.Button(
            adj_frame, text="Reset", bg="#e94560", fg="#ffffff", font=F(8, "bold"),
            relief=tk.FLAT, bd=0, padx=10, command=self.reset_sliders
        )
        reset_adj_btn.pack(side=tk.RIGHT, padx=5, pady=(15, 0))

        # Right Column: Frame manipulations and File/Device Actions
        right_frame = tk.Frame(main_frame, bg="#2d2d2d", width=150, bd=1, relief=tk.FLAT)
        right_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        # Frame operations section
        tk.Label(right_frame, text="FRAME EDITS", font=F(9, "bold"), bg="#2d2d2d", fg="#888888").pack(pady=(10, 5))

        tk.Button(right_frame, text="Add Blank", bg="#3a3a3a", fg="#eeeeee", font=F(9),
                  relief=tk.FLAT, bd=0, width=15, command=self.add_frame).pack(pady=3, padx=15)
        
        tk.Button(right_frame, text="Duplicate", bg="#3a3a3a", fg="#eeeeee", font=F(9),
                  relief=tk.FLAT, bd=0, width=15, command=self.duplicate_frame).pack(pady=3, padx=15)
        
        tk.Button(right_frame, text="Delete", bg="#3a3a3a", fg="#eeeeee", font=F(9),
                  relief=tk.FLAT, bd=0, width=15, command=self.delete_frame).pack(pady=3, padx=15)
        
        tk.Button(right_frame, text="Clear Grid", bg="#3a3a3a", fg="#eeeeee", font=F(9),
                  relief=tk.FLAT, bd=0, width=15, command=self.clear_frame).pack(pady=3, padx=15)

        # Shift operations
        tk.Label(right_frame, text="SHIFT PATTERN", font=F(9, "bold"), bg="#2d2d2d", fg="#888888").pack(pady=(15, 5))
        shift_pad = tk.Frame(right_frame, bg="#2d2d2d")
        shift_pad.pack(pady=5)
        
        tk.Button(shift_pad, text="▲", bg="#3a3a3a", fg="#eeeeee", font=F(8), relief=tk.FLAT, bd=0, width=3,
                  command=lambda: self.shift_frame("up")).grid(row=0, column=1, pady=2)
        tk.Button(shift_pad, text="◀", bg="#3a3a3a", fg="#eeeeee", font=F(8), relief=tk.FLAT, bd=0, width=3,
                  command=lambda: self.shift_frame("left")).grid(row=1, column=0, padx=2)
        tk.Button(shift_pad, text="▶", bg="#3a3a3a", fg="#eeeeee", font=F(8), relief=tk.FLAT, bd=0, width=3,
                  command=lambda: self.shift_frame("right")).grid(row=1, column=2, padx=2)
        tk.Button(shift_pad, text="▼", bg="#3a3a3a", fg="#eeeeee", font=F(8), relief=tk.FLAT, bd=0, width=3,
                  command=lambda: self.shift_frame("down")).grid(row=2, column=1, pady=2)

        # File Operations Section
        tk.Label(right_frame, text="FILE ACTIONS", font=F(9, "bold"), bg="#2d2d2d", fg="#888888").pack(pady=(15, 5))
        
        tk.Button(right_frame, text="Import GIF/Img", bg="#4f46e5", fg="#ffffff", font=F(9),
                  relief=tk.FLAT, bd=0, width=15, command=self.import_file).pack(pady=3, padx=15)
        
        tk.Button(right_frame, text="Export as GIF", bg="#3a3a3a", fg="#eeeeee", font=F(9),
                  relief=tk.FLAT, bd=0, width=15, command=self.export_gif).pack(pady=3, padx=15)

        # Device Operations Section
        tk.Label(right_frame, text="HARDWARE", font=F(9, "bold"), bg="#2d2d2d", fg="#888888").pack(pady=(15, 5))
        
        self.upload_btn = tk.Button(right_frame, text="Send to Screen", bg="#e94560", fg="#ffffff", font=F(10, "bold"),
                  relief=tk.FLAT, bd=0, width=15, pady=5, command=self.upload_to_device)
        self.upload_btn.pack(pady=5, padx=15)

        if self.switch_callback is not None:
            tk.Button(right_frame, text="Switch to Keys", bg="#4f46e5", fg="#ffffff", font=F(10, "bold"),
                      relief=tk.FLAT, bd=0, width=15, pady=5, command=lambda: self.switch_callback(self.root)).pack(pady=5, padx=15)

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
        hex_color = f"#{rgb_tuple[0]:02x}{rgb_tuple[1]:02x}{rgb_tuple[2]:02x}"
        self.color_preview.configure(bg=hex_color)
        self.set_draw_mode("draw")

    def choose_custom_color(self):
        _, hex_color = colorchooser.askcolor(
            initialcolor=f"#{self.selected_color[0]:02x}{self.selected_color[1]:02x}{self.selected_color[2]:02x}"
        )
        if hex_color:
            # Parse hex string to rgb
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            self.set_selected_color((r, g, b))

    def set_draw_mode(self, mode):
        self.draw_mode = mode
        self.draw_btn.configure(bg="#00adb5" if mode == "draw" else "#3a3a3a", fg="#ffffff" if mode == "draw" else "#eeeeee")
        self.erase_btn.configure(bg="#00adb5" if mode == "erase" else "#3a3a3a", fg="#ffffff" if mode == "erase" else "#eeeeee")
        self.dropper_btn.configure(bg="#00adb5" if mode == "eyedropper" else "#3a3a3a", fg="#ffffff" if mode == "eyedropper" else "#eeeeee")

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
            self.play_btn.configure(text="▶ Play Preview", bg="#28a745")
            if self.play_job:
                self.root.after_cancel(self.play_job)
                self.play_job = None
        else:
            self.is_playing = True
            self.play_btn.configure(text="⏸ Pause Preview", bg="#ffc107")
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
        status_frame = tk.Frame(self.root, bg="#e94560")
        status_frame.pack(fill=tk.X, before=self.canvas)
        tk.Label(status_frame, text="Uploading — keyboard will reboot. Do not unplug.",
                 font=F(10, "bold"), bg="#e94560", fg="#ffffff", pady=6).pack(side=tk.LEFT, padx=10)
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
