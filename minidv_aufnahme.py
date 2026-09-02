#!/usr/bin/env python3

import os
import shutil
import signal
import subprocess
import threading
import tkinter as tk
import sys
import platform
import time

from tkinter import messagebox, filedialog
from datetime import datetime

# Versuche PIL zu importieren, aber mach es optional
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL/Pillow nicht installiert. Vorschau deaktiviert.")

# Versuche OpenCV zu importieren, aber mach es optional
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("OpenCV nicht installiert. Vorschau deaktiviert.")


class DependencyManager:
    """Verwaltet die Prüfung und Installation von Abhängigkeiten."""
    
    @staticmethod
    def check_dependency(command):
        """Prüft ob ein Befehl verfügbar ist."""
        return shutil.which(command) is not None
    
    @staticmethod
    def get_package_manager():
        """Ermittelt den Paketmanager des Systems."""
        system = platform.system().lower()
        
        if system == "linux":
            if shutil.which("apt"):
                return "apt", "sudo apt install -y"
            elif shutil.which("dnf"):
                return "dnf", "sudo dnf install -y"
            elif shutil.which("yum"):
                return "yum", "sudo yum install -y"
            elif shutil.which("pacman"):
                return "pacman", "sudo pacman -S --noconfirm"
            elif shutil.which("zypper"):
                return "zypper", "sudo zypper install -y"
        elif system == "darwin":
            if shutil.which("brew"):
                return "brew", "brew install"
        elif system == "windows":
            return "windows", None
        
        return None, None
    
    @staticmethod
    def install_dependency(package_name, package_manager_cmd):
        """Installiert eine Abhängigkeit."""
        if not package_manager_cmd:
            return False, "Kein Paketmanager gefunden"
        
        try:
            cmd = package_manager_cmd.split() + [package_name]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return True, "Installation erfolgreich"
            else:
                return False, f"Fehler: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Zeitüberschreitung bei Installation"
        except Exception as e:
            return False, f"Fehler: {str(e)}"
    
    @staticmethod
    def ensure_dependencies(master, callback=None):
        """Prüft und installiert alle benötigten Abhängigkeiten."""
        missing = []
        install_commands = []
        
        # Prüfe dvgrab für FireWire
        if not DependencyManager.check_dependency("dvgrab"):
            missing.append("dvgrab")
            install_commands.append("dvgrab")
        
        # Prüfe ffmpeg für USB
        if not DependencyManager.check_dependency("ffmpeg"):
            missing.append("ffmpeg")
            install_commands.append("ffmpeg")
        
        if not missing:
            return True, "Alle Abhängigkeiten sind installiert"
        
        # Finde Paketmanager
        pm_name, pm_cmd = DependencyManager.get_package_manager()
        
        if pm_name == "windows":
            msg = (
                "Folgende Programme werden benötigt:\n\n"
                f"{', '.join(missing)}\n\n"
                "Bitte installiere sie manuell:\n"
                "• dvgrab: https://sourceforge.net/projects/dvgrab/\n"
                "• ffmpeg: https://ffmpeg.org/download.html\n\n"
                "Alternativ mit Chocolatey:\n"
                "choco install ffmpeg\n"
                "choco install dvgrab"
            )
            messagebox.showwarning("Abhängigkeiten fehlen", msg)
            return False, "Manuelle Installation erforderlich"
        
        if not pm_cmd:
            msg = (
                f"Folgende Programme werden benötigt:\n\n"
                f"{', '.join(missing)}\n\n"
                "Bitte installiere sie manuell mit deinem Paketmanager."
            )
            messagebox.showwarning("Abhängigkeiten fehlen", msg)
            return False, "Manuelle Installation erforderlich"
        
        # Frage ob installiert werden soll
        pm_display = pm_name.upper()
        msg = (
            f"Folgende Programme werden benötigt:\n\n"
            f"{', '.join(missing)}\n\n"
            f"Soll {pm_display} die Installation durchführen?\n\n"
            f"Befehl: {pm_cmd} {' '.join(install_commands)}"
        )
        
        if not messagebox.askyesno("Abhängigkeiten installieren", msg):
            return False, "Installation abgebrochen"
        
        # Installiere jede Abhängigkeit
        progress_window = None
        if callback:
            progress_window = callback("Installiere Abhängigkeiten...")
        
        all_success = True
        errors = []
        
        for pkg in install_commands:
            success, msg = DependencyManager.install_dependency(pkg, pm_cmd)
            if not success:
                all_success = False
                errors.append(f"{pkg}: {msg}")
        
        if progress_window:
            progress_window.destroy()
        
        if all_success:
            messagebox.showinfo("Erfolg", "Alle Abhängigkeiten wurden installiert!")
            return True, "Installation abgeschlossen"
        else:
            messagebox.showerror(
                "Installationsfehler",
                f"Einige Pakete konnten nicht installiert werden:\n\n" + "\n".join(errors) +
                "\n\nBitte installiere sie manuell."
            )
            return False, "Installation fehlgeschlagen"


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
        
        # Vorschau
        self.preview_running = False
        self.preview_thread = None
        self.cap = None
        self.preview_fps = 15
        
        # Prüfe ob Vorschau verfügbar ist
        self.preview_available = PIL_AVAILABLE and CV2_AVAILABLE

        master.title("MiniDV / Webcam Überspielung")
        master.geometry("520x700")
        master.resizable(False, False)

        # ========== MODUS-AUSWAHL ==========
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

        # ========== Statusleiste für Abhängigkeiten ==========
        self.dep_status = tk.Label(
            master,
            text="⏳ Prüfe Abhängigkeiten...",
            font=("Arial", 9),
            fg="orange"
        )
        self.dep_status.pack(pady=(2, 0))

        # ========== Kamera/Webcam Status ==========
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

        # Hinweis
        self.hint_label = tk.Label(
            master,
            text="",
            font=("Arial", 8),
            fg="gray",
            justify="center"
        )
        self.hint_label.pack(pady=(0, 5))
        self.update_hint()

        # ========== VORSCHAU (OPTIONAL) ==========
        preview_frame = tk.Frame(master, bd=2, relief="groove")
        preview_frame.pack(pady=10, padx=10, fill="x")

        preview_header = tk.Label(
            preview_frame,
            text="📺 Live-Vorschau (optional)",
            font=("Arial", 10, "bold")
        )
        preview_header.pack(pady=(5, 0))

        # Canvas für Vorschau - immer sichtbar, aber nur aktiv wenn verfügbar
        self.preview_canvas = tk.Canvas(
            preview_frame,
            width=480,
            height=270,
            bg="black"
        )
        self.preview_canvas.pack(padx=10, pady=(5, 10))

        # Zeige Standardtext im Canvas
        if self.preview_available:
            self.preview_canvas.create_text(
                240, 135,
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white",
                font=("Arial", 12),
                justify="center"
            )
        else:
            self.preview_canvas.create_text(
                240, 135,
                text="⚠️ Vorschau nicht verfügbar\n\n"
                     "Pillow und/oder OpenCV fehlen\n\n"
                     "Installiere mit:\n"
                     "pip install opencv-python Pillow",
                fill="yellow",
                font=("Arial", 10),
                justify="center"
            )

        # Vorschau Buttons
        preview_btn_frame = tk.Frame(preview_frame)
        preview_btn_frame.pack(pady=(0, 10))

        self.preview_start_btn = tk.Button(
            preview_btn_frame,
            text="▶ Vorschau starten",
            font=("Arial", 10),
            command=self.start_preview,
            bg="#4CAF50" if self.preview_available else "gray",
            fg="white",
            state="normal" if self.preview_available else "disabled"
        )
        self.preview_start_btn.pack(side=tk.LEFT, padx=5)

        self.preview_stop_btn = tk.Button(
            preview_btn_frame,
            text="■ Vorschau stoppen",
            font=("Arial", 10),
            command=self.stop_preview,
            state="disabled",
            bg="#C62828",
            fg="white"
        )
        self.preview_stop_btn.pack(side=tk.LEFT, padx=5)

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

        # ========== Codec Info ==========
        codec_frame = tk.Frame(master)
        codec_frame.pack(pady=5)
        
        tk.Label(
            codec_frame,
            text="Codec: ",
            font=("Arial", 9)
        ).pack(side=tk.LEFT)
        
        tk.Label(
            codec_frame,
            text="H.264 (MP4) - universell kompatibel",
            font=("Arial", 9, "bold"),
            fg="#1565C0"
        ).pack(side=tk.LEFT)

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
        
        # ========== JETZT Abhängigkeiten prüfen ==========
        self.master.after(100, self._check_dependencies_at_start)

    # -------------------------------------------------
    # VORSCHAU FUNKTIONEN
    # -------------------------------------------------
    def start_preview(self):
        """Startet die Live-Vorschau."""
        if self.preview_running:
            return
        
        if not self.preview_available:
            messagebox.showerror(
                "Fehler",
                "Vorschau nicht verfügbar!\n\n"
                "Installiere die fehlenden Pakete:\n\n"
                "pip install opencv-python Pillow\n\n"
                "oder (Debian/Ubuntu):\n"
                "sudo apt install python3-opencv python3-pil\n\n"
                "oder (Fedora):\n"
                "sudo dnf install python3-opencv python3-pillow"
            )
            return
        
        if self.mode != "usb":
            messagebox.showinfo(
                "Info",
                "Live-Vorschau ist nur im USB-Modus verfügbar.\n"
                "Bitte wechsle zum USB-Modus."
            )
            return
        
        if not DependencyManager.check_dependency("ffmpeg"):
            messagebox.showerror(
                "Fehler",
                "ffmpeg nicht installiert!\n"
                "Installiere es mit:\n"
                "sudo apt install ffmpeg"
            )
            return
        
        # Versuche Webcam zu öffnen
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror("Fehler", "Webcam konnte nicht geöffnet werden.")
                return
        except Exception as e:
            messagebox.showerror("Fehler", f"Webcam Fehler: {str(e)}")
            return
        
        self.preview_running = True
        self.preview_start_btn.config(state="disabled")
        self.preview_stop_btn.config(state="normal")
        
        # Starte Vorschau-Thread
        self.preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
        self.preview_thread.start()
        
        self.status.config(text="📺 Live-Vorschau aktiv", fg="blue")
        self.camera_status.config(text="🎥 Webcam aktiv", fg="green")
    
    def _preview_loop(self):
        """Hauptschleife für die Vorschau."""
        while self.preview_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            try:
                # Konvertiere für Tkinter
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Skaliere auf Canvas-Größe
                height, width = frame_rgb.shape[:2]
                target_width = 480
                target_height = 270
                
                scale = min(target_width / width, target_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                resized = cv2.resize(frame_rgb, (new_width, new_height))
                
                # Füge schwarze Ränder hinzu
                canvas_img = np.zeros((target_height, target_width, 3), dtype=np.uint8)
                x_offset = (target_width - new_width) // 2
                y_offset = (target_height - new_height) // 2
                canvas_img[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized
                
                # Konvertiere zu PIL Image und dann zu Tkinter PhotoImage
                img = Image.fromarray(canvas_img)
                img_tk = ImageTk.PhotoImage(img)
                
                # Aktualisiere Canvas im Hauptthread
                self.master.after(0, self._update_preview, img_tk)
                
            except Exception as e:
                print(f"Vorschau Fehler: {e}")
                break
            
            # FPS begrenzen
            time.sleep(1.0 / self.preview_fps)
    
    def _update_preview(self, img_tk):
        """Aktualisiert das Vorschau-Canvas im Hauptthread."""
        if self.preview_running:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, anchor="nw", image=img_tk)
            self.preview_canvas.image = img_tk
    
    def stop_preview(self):
        """Stoppt die Live-Vorschau."""
        self.preview_running = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.preview_start_btn.config(state="normal" if self.preview_available else "disabled")
        self.preview_stop_btn.config(state="disabled")
        
        # Zeige Standardtext
        self.preview_canvas.delete("all")
        if self.preview_available:
            self.preview_canvas.create_text(
                240, 135,
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white",
                font=("Arial", 12),
                justify="center"
            )
        
        self.status.config(text="Bereit", fg="green")
        self.camera_status.config(
            text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit",
            fg="gray"
        )

    # -------------------------------------------------
    # Abhängigkeiten prüfen
    # -------------------------------------------------
    def _check_dependencies_at_start(self):
        """Prüft beim Start alle Abhängigkeiten."""
        def show_progress(text):
            progress = tk.Toplevel(self.master)
            progress.title("Installation")
            progress.geometry("400x100")
            progress.resizable(False, False)
            progress.transient(self.master)
            progress.grab_set()
            
            tk.Label(
                progress,
                text=text,
                font=("Arial", 12)
            ).pack(pady=20)
            
            tk.Label(
                progress,
                text="Bitte warten...",
                font=("Arial", 10),
                fg="gray"
            ).pack()
            
            progress.update()
            return progress
        
        # Prüfe auf dvgrab und ffmpeg
        dvgrab_ok = DependencyManager.check_dependency("dvgrab")
        ffmpeg_ok = DependencyManager.check_dependency("ffmpeg")
        
        if not dvgrab_ok or not ffmpeg_ok:
            self.dep_status.config(
                text="⚠️ Einige Abhängigkeiten fehlen",
                fg="orange"
            )
            
            success, msg = DependencyManager.ensure_dependencies(
                self.master,
                show_progress
            )
            
            if success:
                self.dep_status.config(
                    text="✅ System-Abhängigkeiten: OK",
                    fg="green"
                )
            else:
                self.dep_status.config(
                    text="⚠️ Abhängigkeiten fehlen - einige Funktionen nicht verfügbar",
                    fg="red"
                )
        else:
            self.dep_status.config(
                text="✅ System-Abhängigkeiten: OK",
                fg="green"
            )
        
        # Zeige Vorschau-Status separat
        if not self.preview_available:
            self.dep_status.config(
                text="✅ System: OK | ⚠️ Vorschau: nicht verfügbar",
                fg="orange"
            )

    def on_mode_change(self):
        """Wird aufgerufen, wenn der Modus umgeschaltet wird."""
        if self.preview_running:
            self.stop_preview()
        
        self.mode = self.mode_var.get()
        self.update_hint()
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
        self.status.config(text="Bereit", fg="green")
        self.update_default_filename()
        
        # Aktualisiere Vorschau-Hinweis
        if self.mode != "usb" and self.preview_available:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                240, 135,
                text="ℹ️ Vorschau nur im USB-Modus verfügbar",
                fill="white",
                font=("Arial", 12),
                justify="center"
            )

    def update_hint(self):
        """Aktualisiert den Hinweistext je nach Modus."""
        if self.mode == "firewire":
            if DependencyManager.check_dependency("dvgrab"):
                self.hint_label.config(
                    text="MiniDV Camcorder über FireWire (IEEE 1394) anschließen.\n"
                         "Codec: DV (uncompressed) - wird als .dv-Datei gespeichert"
                )
            else:
                self.hint_label.config(
                    text="⚠️ dvgrab nicht installiert! FireWire nicht verfügbar.\n"
                         "Bitte installiere: sudo apt install dvgrab"
                )
        else:
            if DependencyManager.check_dependency("ffmpeg"):
                self.hint_label.config(
                    text="Webcam über USB anschließen.\n"
                         "Codec: H.264 (MP4) - universell kompatibel"
                )
            else:
                self.hint_label.config(
                    text="⚠️ ffmpeg nicht installiert! USB nicht verfügbar.\n"
                         "Bitte installiere: sudo apt install ffmpeg"
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

        filename = filename.replace("/", "_").replace("\\", "_")
        
        if self.preview_running:
            self.stop_preview()
        
        if self.mode == "firewire":
            self._start_firewire_recording(filename)
        else:
            self._start_usb_recording(filename)

    def _start_firewire_recording(self, filename):
        """Startet Aufnahme über FireWire mit dvgrab."""
        if not DependencyManager.check_dependency("dvgrab"):
            messagebox.showerror(
                "Fehler",
                "Das Programm 'dvgrab' wurde nicht gefunden.\n"
                "Installiere es mit:\n"
                "sudo apt install dvgrab\n\n"
                "Oder verwende den USB-Modus."
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
        if not DependencyManager.check_dependency("ffmpeg"):
            messagebox.showerror(
                "Fehler",
                "Das Programm 'ffmpeg' wurde nicht gefunden.\n"
                "Installiere es mit:\n"
                "sudo apt install ffmpeg\n\n"
                "Oder verwende den FireWire-Modus."
            )
            return

        output_file = os.path.join(self.output_dir, filename + ".mp4")

        if os.path.exists(output_file):
            if not messagebox.askyesno(
                "Datei existiert",
                f"Die Datei '{os.path.basename(output_file)}' existiert bereits.\n"
                "Überschreiben?"
            ):
                return

        try:
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
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-profile:v", "baseline",
                    "-level", "3.0",
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
            self.preview_start_btn.config(state="disabled")
            self.preview_stop_btn.config(state="disabled")
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.filename_entry.config(state="normal")
            self.folder_btn.config(state="normal")
            self.firewire_radio.config(state="normal")
            self.usb_radio.config(state="normal")
            self.preview_start_btn.config(state="normal" if self.preview_available else "disabled")
            self.preview_stop_btn.config(state="disabled")

    # -------------------------------------------------
    # Ausgabe lesen
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

    def _read_ffmpeg_output(self):
        try:
            for line in self.process.stdout:
                print(line.strip())
                if "Input #0" in line:
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
        self.camera_status.config(
            text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit",
            fg="gray"
        )
        self.update_default_filename()

    # -------------------------------------------------
    # Programm schließen
    # -------------------------------------------------
    def close(self):
        if self.preview_running:
            self.stop_preview()
        
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
