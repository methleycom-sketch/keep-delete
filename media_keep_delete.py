#!/usr/bin/env python3
"""Interactive media triage tool.

Features:
1. Lets you choose a folder.
2. Finds images/videos and shuffles them.
3. Prioritizes videos before images.
4. Shows one item at a time:
   - Left click = keep
   - Right click = move to delete/ folder
5. Displays sorted/remaining counters.

Dependencies:
- Pillow
- python-vlc
- opencv-python
"""

from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import cv2
import vlc
from PIL import Image, ImageTk

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".wmv", ".flv"}
MIN_VIDEO_FPS = 30.0


class MediaSorterApp:
    def __init__(self, root: tk.Tk, media_paths: list[Path], source_folder: Path) -> None:
        self.root = root
        self.media_paths = media_paths
        self.source_folder = source_folder
        self.delete_folder = source_folder / "delete"

        self.total_items = len(media_paths)
        self.current_index = 0
        self.current_media: Path | None = None
        self.current_photo: ImageTk.PhotoImage | None = None

        self.instance = vlc.Instance("--quiet")
        self.player = self.instance.media_player_new()

        self.root.title("Keep/Delete Media Sorter")
        self.root.geometry("1200x800")
        self.root.configure(bg="#111")

        self.counter_label = tk.Label(
            root,
            text="",
            fg="white",
            bg="#111",
            font=("Arial", 14, "bold"),
            anchor="w",
            padx=10,
            pady=6,
        )
        self.counter_label.pack(fill="x")

        self.media_frame = tk.Frame(root, bg="black")
        self.media_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.media_frame, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.instructions = tk.Label(
            root,
            text="Left click: KEEP    |    Right click: MOVE TO delete/",
            fg="#ddd",
            bg="#111",
            font=("Arial", 12),
            pady=8,
        )
        self.instructions.pack(fill="x")

        self.canvas.bind("<Button-1>", self.keep_current)
        self.canvas.bind("<Button-3>", self.delete_current)
        self.root.bind("<Left>", self.keep_current)
        self.root.bind("<Right>", self.delete_current)
        self.root.bind("<Escape>", lambda _event: self.quit())

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(50, self.show_next)

    def quit(self) -> None:
        self.stop_video()
        self.root.destroy()

    def update_counter(self) -> None:
        sorted_count = self.current_index
        remaining = self.total_items - self.current_index
        self.counter_label.config(
            text=f"Sorted: {sorted_count}/{self.total_items}   Remaining: {remaining}"
        )

    def show_next(self) -> None:
        self.stop_video()
        self.canvas.delete("all")
        self.current_photo = None

        if self.current_index >= self.total_items:
            self.update_counter()
            messagebox.showinfo("Done", "No more media left to sort.")
            self.quit()
            return

        self.current_media = self.media_paths[self.current_index]
        self.update_counter()

        ext = self.current_media.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            self.display_video(self.current_media)
        else:
            self.display_image(self.current_media)

    def display_image(self, path: Path) -> None:
        try:
            image = Image.open(path)
            canvas_w = max(self.canvas.winfo_width(), 1)
            canvas_h = max(self.canvas.winfo_height(), 1)
            image.thumbnail((canvas_w, canvas_h), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(image)
            self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.current_photo)
            self.canvas.create_text(
                10,
                10,
                anchor="nw",
                fill="white",
                font=("Arial", 11, "bold"),
                text=path.name,
            )
        except Exception as exc:
            self.canvas.create_text(
                20,
                20,
                anchor="nw",
                fill="red",
                font=("Arial", 12, "bold"),
                text=f"Failed to load image: {path.name}\n{exc}",
            )

    def display_video(self, path: Path) -> None:
        self.canvas.update_idletasks()
        handle = self.canvas.winfo_id()

        if sys.platform.startswith("linux"):
            self.player.set_xwindow(handle)
        elif sys.platform == "win32":
            self.player.set_hwnd(handle)
        elif sys.platform == "darwin":
            self.player.set_nsobject(handle)

        media = self.instance.media_new(str(path))
        self.player.set_media(media)
        self.player.audio_set_mute(False)
        self.player.audio_set_volume(100)
        self.player.play()

        fps = self.get_video_fps(path)
        if fps and fps < MIN_VIDEO_FPS:
            target_rate = MIN_VIDEO_FPS / fps
            self.root.after(200, lambda: self.player.set_rate(target_rate))

        self.canvas.create_text(
            10,
            10,
            anchor="nw",
            fill="white",
            font=("Arial", 11, "bold"),
            text=path.name,
        )

    @staticmethod
    def get_video_fps(path: Path) -> float:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return 0.0
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        return fps or 0.0

    def stop_video(self) -> None:
        try:
            if self.player.is_playing():
                self.player.stop()
        except Exception:
            pass

    def keep_current(self, _event=None) -> None:
        self.current_index += 1
        self.show_next()

    def delete_current(self, _event=None) -> None:
        if self.current_media is None:
            return

        self.delete_folder.mkdir(parents=True, exist_ok=True)
        destination = self.unique_destination(self.delete_folder, self.current_media.name)
        shutil.move(str(self.current_media), str(destination))

        self.current_index += 1
        self.show_next()

    @staticmethod
    def unique_destination(folder: Path, filename: str) -> Path:
        target = folder / filename
        if not target.exists():
            return target

        stem = target.stem
        suffix = target.suffix
        counter = 1
        while True:
            candidate = folder / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1


def collect_media(folder: Path) -> list[Path]:
    videos: list[Path] = []
    images: list[Path] = []

    for path in folder.iterdir():
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            videos.append(path)
        elif ext in IMAGE_EXTENSIONS:
            images.append(path)

    random.shuffle(videos)
    random.shuffle(images)
    return videos + images


def main() -> None:
    chooser = tk.Tk()
    chooser.withdraw()
    selected = filedialog.askdirectory(title="Choose a folder containing media")
    chooser.destroy()

    if not selected:
        return

    folder = Path(selected)
    media_paths = collect_media(folder)
    if not media_paths:
        messagebox.showinfo("No media", "No images or videos were found in that folder.")
        return

    root = tk.Tk()
    app = MediaSorterApp(root, media_paths, folder)
    root.mainloop()


if __name__ == "__main__":
    main()
