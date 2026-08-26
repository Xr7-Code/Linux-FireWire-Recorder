#!/usr/bin/env python3

import os
import shutil
import signal
import subprocess
import threading
import tkinter as tk
import sys
import tempfile

from tkinter import messagebox, filedialog
from datetime import datetime


class MiniDVRecorder:

    def __init__(self, master):
        self.master = master
        self.process = None
        self.recording_start = None
        self.timer_running = False
        
        # Modus: "firewire" oder "usb"
        self.mode = "firewire"
        
        # Standard-Speicherort
        self.default_output_dir = os.path.expanduser("~/Videos/MiniDV")
        self.output_dir = self.default_output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        master.title("MiniDV / Webcam Überspielung")
        master.geometry("500x620")
        master.resizable(False, False)

        # ========== MODUS-AUSWAHL (ganz oben) ==========
        self.mode_frame = tk.Frame(master)
        self.mode_frame.pack(pady=(15, 5))

        tk.Label(
            self.mode_frame,
            text="Quelle wählen:",
            font=("Arial", 11, "bold")
        ).pack(side=tk.LEFT, padx=5)

        self.mode_var = tk.StringVar(value="firewire")

        self.firewire_radio = tk.Radiobutton(
            self.mode_frame,
            text="📹 Camcorder (FireWire)",
            variable=self.mode_var,
            value="firewire",
            font=("Arial", 10),
            command=self.on_mode_change
        )
        self.firewire_radio.pack(side=tk.LEFT, padx=5)

        self.usb_radio = tk.Radiobutton(
            self.mode_frame,
            text="🎥 Webcam (USB)",
            variable=self.mode_var,
            value="usb",
            font=("Arial", 10),
            command=self.on_mode_change
        )
        self.usb_radio.pack(side=tk.LEFT, padx=5)

        # Status der Kamera/Webcam
        self.camera_status = tk.Label(
            master,
            text="📹 Kamera bereit",
            font=("Arial", 10, "bold"),
            fg="gray"
        )
        self.camera_status.pack(pady=(5, 0))

        # Titel
        tk.Label(
            master,
            text="Digitalisierung von Videoquellen",
            font=("Arial", 14, "bold")
        ).pack(pady=(10, 5))

        # Hinweis (ändert sich je nach Modus)
        self.hint_label = tk.Label(
            master,
            text="",
            font=("Arial", 8),
            fg="gray",
            justify="center"
        )
        self.hint_label.pack(pady=(0, 5))
        self.update_hint()

        # ========== Speicherort ==========
        self.output_label = tk.Label(
            master,
            text=f"Speicherort:\n{self.output_dir}",
            font=("Arial", 10),
            justify="center"
        )
        self.output_label.pack()

        self.folder_btn = tk.Button(
            master,
            text="📁 Speicherort wählen",
            font=("Arial", 10),
            command=self.choose_folder
        )
        self.folder_btn.pack(pady=5)

        # ========== Dateiname ==========
        tk.Label(
            master,
            text="Dateiname:",
            font=("Arial", 10, "bold")
        ).pack(pady=(10, 2))

        self.filename_var = tk.StringVar()
        self.update_default_filename()

        self.filename_entry = tk.Entry(
            master,
            textvariable=self.filename_var,
            width=42,
            font=("Arial", 10),
            justify="center"
        )
        self.filename_entry.pack()

        tk.Label(
            master,
            text="(kann vor der Aufnahme geändert werden)",
            font=("Arial", 8),
            fg="gray"
        ).pack()

        # ========== Buttons ==========
        self.start_btn = tk.Button(
            master,
            text="▶ Aufnahme starten",
            font=("Arial", 13),
            width=24,
            command=self.start_recording,
            bg="#4CAF50",
            fg="white"
        )
        self.start_btn.pack(pady=12)

        self.stop_btn = tk.Button(
            master,
            text="■ Aufnahme beenden",
            font=("Arial", 13),
            width=24,
            command=self.stop_recording,
            state="disabled",
            bg="#C62828",
            fg="white"
        )
        self.stop_btn.pack()

        # ========== Status ==========
        self.status = tk.Label(
            master,
            text="Bereit",
            fg="green",
            font=("Arial", 12)
        )
        self.status.pack(pady=10)

        # ========== Timer ==========
        self.timer_label = tk.Label(
            master,
            text="Aufnahmedauer: 00:00:00",
            font=("Arial", 12)
        )
        self.timer_label.pack()

        master.protocol("WM_DELETE_WINDOW", self.close)

    def on_mode_change(self):
        """Wird aufgerufen, wenn der Modus umgeschaltet wird."""
        self.mode = self.mode_var.get()
        self.update_hint()
        # Status zurücksetzen
        self.camera_status.config(text="📹 Bereit", fg="gray")
        self.status.config(text="Bereit", fg="green")

    def update_hint(self):
        """Aktualisiert den Hinweistext je nach Modus."""
        if self.mode == "firewire":
            self.hint_label.config(
                text="MiniDV Camcorder über FireWire (IEEE 1394) anschließen.\n"
                     "Erfordert 'dvgrab'."
            )
        else:
            self.hint_label.config(
                text="Webcam über USB anschließen.\n"
                     "Erfordert 'ffmpeg' mit Video4Linux2 (V4L2) und ALSA.\n"
                     "Unterstützt Video + Audio."
            )

    def choose_folder(self):
        folder = filedialog.askdirectory(
            title="Speicherort auswählen",
            initialdir=self.output_dir
        )
        if folder:
            self.output_dir = folder
            os.makedirs(self.output_dir, exist_ok=True)
            self.output_label.config(text=f"Speicherort:\n{self.output_dir}")

    def update_default_filename(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        suffix = "Webcam" if self.mode == "usb" else "MiniDV"
        self.filename_var.set(f"{timestamp}_{suffix}")

    # -------------------------------------------------
    # Aufnahme starten
    # -------------------------------------------------
    def start_recording(self):
        if self.process:
            return

        filename = self.filename_var.get().strip()
        if not filename:
            messagebox.showerror("Fehler", "Bitte einen Dateinamen eingeben.")
            return

        # Sonderzeichen aus Dateiname entfernen
        filename = filename.replace("/", "_").replace("\\", "_")
        
        if self.mode == "firewire":
            self._start_firewire_recording(filename)
        else:
            self._start_usb_recording(filename)

    def _start_firewire_recording(self, filename):
        """Startet Aufnahme über FireWire mit dvgrab."""
        if shutil.which("dvgrab") is None:
            messagebox.showerror(
                "Fehler",
                "Das Programm 'dvgrab' wurde nicht gefunden.\n"
                "Installiere es mit: sudo apt install dvgrab"
            )
            return

        prefix = os.path.join(self.output_dir, filename + "_")

        try:
            self.process = subprocess.Popen(
                [
                    "dvgrab",
                    "-showstatus",
                    "-f", "raw",
                    "-autosplit",
                    "-timestamp",
                    prefix
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            threading.Thread(target=self._read_dvgrab_output, daemon=True).start()
            self._set_recording_state(True)
            self.status.config(text="● FireWire Aufnahme läuft", fg="red")

        except Exception as err:
            messagebox.showerror("Fehler", f"Aufnahme konnte nicht gestartet werden:\n\n{err}")
            self.process = None

    def _start_usb_recording(self, filename):
        """Startet Aufnahme über USB mit ffmpeg (Video + Audio)."""
        if shutil.which("ffmpeg") is None:
            messagebox.showerror(
                "Fehler",
                "Das Programm 'ffmpeg' wurde nicht gefunden.\n"
                "Installiere es mit: sudo apt install ffmpeg"
            )
            return

        # Dateiname mit .mkv (gutes Containerformat für Webcam)
        output_file = os.path.join(self.output_dir, filename + ".mkv")

        # Prüfe, ob Datei existiert
        if os.path.exists(output_file):
            if not messagebox.askyesno(
                "Datei existiert",
                f"Die Datei '{os.path.basename(output_file)}' existiert bereits.\n"
                "Überschreiben?"
            ):
                return

        try:
            # ffmpeg Befehl für Webcam (Video + Audio)
            # Video: V4L2 (Linux), Audio: ALSA
            # Hier wird /dev/video0 und /dev/snd/... verwendet
            # Anpassungen können nötig sein
            self.process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-f", "v4l2",
                    "-framerate", "30",
                    "-video_size", "640x480",
                    "-i", "/dev/video0",
                    "-f", "alsa",
                    "-i", "default",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-y",
                    output_file
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            threading.Thread(target=self._read_ffmpeg_output, daemon=True).start()
            self._set_recording_state(True)
            self.status.config(text="● USB Webcam Aufnahme läuft", fg="red")
            self.camera_status.config(text="🎥 Webcam aktiv", fg="green")

        except Exception as err:
            messagebox.showerror("Fehler", f"Aufnahme konnte nicht gestartet werden:\n\n{err}")
            self.process = None

    def _set_recording_state(self, is_recording):
        """Setzt die UI für Aufnahme-Status."""
        if is_recording:
            self.recording_start = datetime.now()
            self.timer_running = True
            self.update_timer()
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.filename_entry.config(state="disabled")
            self.folder_btn.config(state="disabled")
            self.firewire_radio.config(state="disabled")
            self.usb_radio.config(state="disabled")
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.filename_entry.config(state="normal")
            self.folder_btn.config(state="normal")
            self.firewire_radio.config(state="normal")
            self.usb_radio.config(state="normal")

    # -------------------------------------------------
    # Ausgabe lesen (dvgrab)
    # -------------------------------------------------
    def _read_dvgrab_output(self):
        try:
            for line in self.process.stdout:
                print(line.strip())
                if "Found AV/C device" in line:
                    self.master.after(0, lambda: self.camera_status.config(
                        text="📹 Kamera erkannt", fg="green"
                    ))
                elif "Waiting for DV" in line:
                    self.master.after(0, lambda: self.camera_status.config(
                        text="📹 Warte auf DV-Signal", fg="orange"
                    ))
                elif "Capture Started" in line:
                    self.master.after(0, lambda: self.camera_status.config(
                        text="📹 DV-Signal aktiv", fg="green"
                    ))
        except Exception:
            pass

    # -------------------------------------------------
    # Ausgabe lesen (ffmpeg)
    # -------------------------------------------------
    def _read_ffmpeg_output(self):
        try:
            for line in self.process.stdout:
                print(line.strip())
                # ffmpeg gibt viele Infos aus, wir filtern wichtige
                if "frame=" in line:
                    # Zeige Framerate/Status
                    pass
                elif "Input #0" in line:
                    self.master.after(0, lambda: self.camera_status.config(
                        text="🎥 Webcam erkannt", fg="green"
                    ))
        except Exception:
            pass

    # -------------------------------------------------
    # Timer
    # -------------------------------------------------
    def update_timer(self):
        if self.timer_running and self.recording_start:
            elapsed = datetime.now() - self.recording_start
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            self.timer_label.config(
                text=f"Aufnahmedauer: {hours:02d}:{minutes:02d}:{seconds:02d}"
            )
            self.master.after(1000, self.update_timer)

    def reset_timer(self):
        self.timer_running = False
        self.recording_start = None
        self.timer_label.config(text="Aufnahmedauer: 00:00:00")

    # -------------------------------------------------
    # Aufnahme stoppen
    # -------------------------------------------------
    def stop_recording(self):
        if not self.process:
            return

        try:
            self.process.send_signal(signal.SIGINT)
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
        except Exception as err:
            messagebox.showerror("Fehler", f"Fehler beim Beenden:\n\n{err}")

        self.process = None
        self.reset_timer()
        self._set_recording_state(False)
        self.status.config(text="Bereit", fg="green")
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
        self.update_default_filename()

    # -------------------------------------------------
    # Programm schließen
    # -------------------------------------------------
    def close(self):
        if self.process:
            antwort = messagebox.askyesno(
                "Aufnahme läuft",
                "Die Aufnahme läuft noch.\nSoll sie beendet werden?"
            )
            if antwort:
                self.stop_recording()
            else:
                return
        self.master.destroy()


# -------------------------------------------------
# Programmstart
# -------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = MiniDVRecorder(root)
    root.mainloop()
