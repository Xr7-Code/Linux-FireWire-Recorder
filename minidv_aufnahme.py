#!/usr/bin/env python3

import os
import shutil
import signal
import subprocess
import threading
import tkinter as tk
import sys
import platform
import tempfile
import time

from tkinter import messagebox, filedialog
from datetime import datetime

# PIL imports richtig machen
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL/Pillow nicht installiert. Vorschau deaktiviert.")

# OpenCV imports
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
            # Prüfe verschiedene Paketmanager
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
        elif system == "darwin":  # macOS
            if shutil.which("brew"):
                return "brew", "brew install"
        elif system == "windows":
            return "windows", None
        
        return None, None
    
    @staticmethod
    def get_python_package_name(system_package):
        """Mapped System-Paketnamen zu Python-Paketnamen für pip."""
        mapping = {
            "python3-opencv": "opencv-python",
            "python3-pil": "Pillow",
            "python3-pil.imagetk": "Pillow",
            "python3-numpy": "numpy"
        }
        return mapping.get(system_package, system_package)
    
    @staticmethod
    def install_with_pip(package_name):
        """Installiert ein Python-Paket mit pip."""
        try:
            # Versuche mit --user flag (keine Admin-Rechte benötigt)
            cmd = [sys.executable, "-m", "pip", "install", "--user", package_name]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return True, "Mit pip installiert"
            
            # Falls --user nicht klappt, versuche ohne
            cmd = [sys.executable, "-m", "pip", "install", package_name]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return True, "Mit pip installiert"
            else:
                return False, f"pip Fehler: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Zeitüberschreitung bei pip Installation"
        except Exception as e:
            return False, f"pip Fehler: {str(e)}"
    
    @staticmethod
    def install_dependency(package_name, package_manager_cmd, is_python_package=False):
        """Installiert eine Abhängigkeit."""
        if is_python_package:
            # Für Python-Pakete: erst pip versuchen
            success, msg = DependencyManager.install_with_pip(package_name)
            if success:
                return True, msg
            
            # Wenn pip fehlschlägt, zeige Hinweis für Systempaket
            system_pkg = None
            if package_name == "opencv-python":
                system_pkg = "python3-opencv"
            elif package_name == "Pillow":
                system_pkg = "python3-pil"
            
            if system_pkg:
                return False, f"pip Installation fehlgeschlagen. Versuche: sudo apt install {system_pkg}"
            else:
                return False, f"pip Installation fehlgeschlagen. Installiere manuell: pip install {package_name}"
        
        # Für Systempakete (dvgrab, ffmpeg)
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
        missing_system = []
        missing_python = []
        install_commands = []
        
        # Prüfe dvgrab für FireWire (Systempaket)
        if not DependencyManager.check_dependency("dvgrab"):
            missing_system.append("dvgrab")
            install_commands.append(("dvgrab", False))
        
        # Prüfe ffmpeg für USB (Systempaket)
        if not DependencyManager.check_dependency("ffmpeg"):
            missing_system.append("ffmpeg")
            install_commands.append(("ffmpeg", False))
        
        # Prüfe Python-Pakete für Vorschau
        if not PIL_AVAILABLE:
            missing_python.append("Pillow")
            install_commands.append(("Pillow", True))
        
        if not CV2_AVAILABLE:
            missing_python.append("opencv-python")
            install_commands.append(("opencv-python", True))
        
        if not missing_system and not missing_python:
            return True, "Alle Abhängigkeiten sind installiert"
        
        # Erstelle Nachricht
        msg = "Folgende Abhängigkeiten werden benötigt:\n\n"
        
        if missing_system:
            msg += "System-Pakete:\n"
            for pkg in missing_system:
                msg += f"  • {pkg}\n"
            msg += "\n"
        
        if missing_python:
            msg += "Python-Pakete (pip):\n"
            for pkg in missing_python:
                msg += f"  • {pkg}\n"
            msg += "\n"
        
        # Finde Paketmanager für Systempakete
        pm_name, pm_cmd = DependencyManager.get_package_manager()
        
        if pm_name == "windows":
            msg += (
                "Bitte installiere die fehlenden Pakete manuell:\n\n"
                "System-Pakete:\n"
                "• dvgrab: https://sourceforge.net/projects/dvgrab/\n"
                "• ffmpeg: https://ffmpeg.org/download.html\n\n"
                "Python-Pakete:\n"
                "• pip install opencv-python Pillow\n\n"
                "Alternativ mit Chocolatey:\n"
                "choco install ffmpeg dvgrab"
            )
            messagebox.showwarning("Abhängigkeiten fehlen", msg)
            return False, "Manuelle Installation erforderlich"
        
        # Füge Installationsanweisungen hinzu
        if missing_system and pm_cmd:
            msg += f"Für System-Pakete: {pm_cmd} {' '.join(missing_system)}\n\n"
        
        if missing_python:
            msg += f"Für Python-Pakete: pip install {' '.join(missing_python)}\n\n"
        
        msg += "Soll die Installation jetzt versucht werden?"
        
        if not messagebox.askyesno("Abhängigkeiten installieren", msg):
            return False, "Installation abgebrochen"
        
        # Installiere jede Abhängigkeit
        progress_window = None
        if callback:
            progress_window = callback("Installiere Abhängigkeiten...")
        
        all_success = True
        errors = []
        
        for pkg, is_python in install_commands:
            if is_python:
                success, msg = DependencyManager.install_dependency(
                    pkg, None, is_python_package=True
                )
            else:
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
            error_msg = "Einige Pakete konnten nicht installiert werden:\n\n"
            error_msg += "\n".join(errors)
            error_msg += "\n\nBitte installiere sie manuell:\n\n"
            
            if missing_system and pm_cmd:
                error_msg += f"System-Pakete: {pm_cmd} {' '.join(missing_system)}\n"
            
            if missing_python:
                error_msg += f"Python-Pakete: pip install {' '.join(missing_python)}"
            
            messagebox.showerror("Installationsfehler", error_msg)
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
        self.last_frame = None
        self.preview_label = None
        
        # FPS für Vorschau
        self.preview_fps = 15
        
        # Prüfe ob Vorschau verfügbar ist
        self.preview_available = PIL_AVAILABLE and CV2_AVAILABLE

        master.title("MiniDV / Webcam Überspielung mit Vorschau")
        master.geometry("620x900")
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

        # ========== VORSCHAU ==========
        preview_frame = tk.Frame(master, bd=2, relief="groove")
        preview_frame.pack(pady=10, padx=10)

        tk.Label(
            preview_frame,
            text="📺 Live-Vorschau",
            font=("Arial", 11, "bold")
        ).pack(pady=(5, 0))

        # Canvas für Vorschau
        self.preview_canvas = tk.Canvas(
            preview_frame,
            width=480,
            height=360,
            bg="black"
        )
        self.preview_canvas.pack(padx=10, pady=(5, 10))

        # Vorschau Buttons
        preview_btn_frame = tk.Frame(preview_frame)
        preview_btn_frame.pack(pady=(0, 10))

        self.preview_start_btn = tk.Button(
            preview_btn_frame,
            text="▶ Vorschau starten",
            font=("Arial", 10),
            command=self.start_preview,
            bg="#2196F3",
            fg="white"
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
        
        # Wenn keine Vorschau verfügbar, deaktiviere Buttons
        if not self.preview_available:
            self.preview_start_btn.config(state="disabled", bg="gray")
            self.preview_start_btn.config(text="⚠️ Vorschau nicht verfügbar")
            
            # Zeige Hinweis auf Canvas
            self.preview_canvas.create_text(
                240, 180,
                text="Pillow und/oder OpenCV nicht installiert\n\n"
                     "Installiere mit:\n"
                     "pip install opencv-python Pillow\n\n"
                     "oder (Debian/Ubuntu):\n"
                     "sudo apt install python3-opencv python3-pil",
                fill="white",
                font=("Arial", 10),
                justify="center"
            )

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
        
        # Prüfe ob Vorschau verfügbar ist
        if not self.preview_available:
            messagebox.showerror(
                "Fehler",
                "Vorschau nicht verfügbar.\n\n"
                "Installiere die fehlenden Pakete:\n"
                "pip install opencv-python Pillow\n\n"
                "oder (Debian/Ubuntu):\n"
                "sudo apt install python3-opencv python3-pil"
            )
            return
        
        # Prüfe ob Kamera verfügbar ist
        if self.mode == "usb":
            if not DependencyManager.check_dependency("ffmpeg"):
                messagebox.showerror(
                    "Fehler",
                    "ffmpeg nicht installiert. Bitte zuerst installieren."
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
        else:
            # FireWire - verwende dvgrab mit Vorschau
            messagebox.showinfo(
                "Info",
                "FireWire-Vorschau wird nur bei USB-Webcams unterstützt.\n"
                "Bitte wechsle zum USB-Modus für Live-Vorschau."
            )
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
            
            # Konvertiere für Tkinter
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Skaliere auf Canvas-Größe
            height, width = frame_rgb.shape[:2]
            target_width = 480
            target_height = 360
            
            # Skaliere unter Beibehaltung des Seitenverhältnisses
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
            
            # FPS begrenzen
            time.sleep(1.0 / self.preview_fps)
    
    def _update_preview(self, img_tk):
        """Aktualisiert das Vorschau-Canvas im Hauptthread."""
        if self.preview_running:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, anchor="nw", image=img_tk)
            self.preview_canvas.image = img_tk  # Referenz halten
    
    def stop_preview(self):
        """Stoppt die Live-Vorschau."""
        self.preview_running = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.preview_start_btn.config(state="normal" if self.preview_available else "disabled")
        self.preview_stop_btn.config(state="disabled")
        self.preview_canvas.delete("all")
        
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
            progress.geometry("450x120")
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
        
        # Prüfe Python-Pakete für Vorschau
        cv2_ok = CV2_AVAILABLE
        pil_ok = PIL_AVAILABLE
        
        if not dvgrab_ok or not ffmpeg_ok or not cv2_ok or not pil_ok:
            self.dep_status.config(
                text="⚠️ Einige Abhängigkeiten fehlen",
                fg="orange"
            )
            
            # Frage ob installiert werden soll
            success, msg = DependencyManager.ensure_dependencies(
                self.master,
                show_progress
            )
            
            if success:
                self.dep_status.config(
                    text="✅ Alle Abhängigkeiten: OK",
                    fg="green"
                )
                
                # Prüfe nochmal ob wirklich installiert
                if not DependencyManager.check_dependency("dvgrab"):
                    self.dep_status.config(
                        text="⚠️ dvgrab nicht gefunden - FireWire nicht verfügbar",
                        fg="orange"
                    )
                if not DependencyManager.check_dependency("ffmpeg"):
                    self.dep_status.config(
                        text="⚠️ ffmpeg nicht gefunden - USB nicht verfügbar",
                        fg="orange"
                    )
                if not CV2_AVAILABLE:
                    self.dep_status.config(
                        text="⚠️ opencv-python nicht installiert - Keine Vorschau",
                        fg="orange"
                    )
                    self.preview_canvas.delete("all")
                    self.preview_canvas.create_text(
                        240, 180,
                        text="OpenCV nicht installiert\n\n"
                             "Installiere mit:\n"
                             "pip install opencv-python\n\n"
                             "oder (Debian/Ubuntu):\n"
                             "sudo apt install python3-opencv",
                        fill="white",
                        font=("Arial", 10),
                        justify="center"
                    )
                if not PIL_AVAILABLE:
                    self.dep_status.config(
                        text="⚠️ Pillow nicht installiert - Keine Vorschau",
                        fg="orange"
                    )
            else:
                self.dep_status.config(
                    text="⚠️ Abhängigkeiten fehlen - einige Funktionen nicht verfügbar",
                    fg="red"
                )
        else:
            self.dep_status.config(
                text="✅ Alle Abhängigkeiten: OK",
                fg="green"
            )

    def on_mode_change(self):
        """Wird aufgerufen, wenn der Modus umgeschaltet wird."""
        # Stoppe Vorschau wenn läuft
        if self.preview_running:
            self.stop_preview()
        
        self.mode = self.mode_var.get()
        self.update_hint()
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
        self.status.config(text="Bereit", fg="green")
        self.update_default_filename()

    def update_hint(self):
        """Aktualisiert den Hinweistext je nach Modus."""
        if self.mode == "firewire":
            if DependencyManager.check_dependency("dvgrab"):
                self.hint_label.config(
                    text="MiniDV Camcorder über FireWire (IEEE 1394) anschließen.\n"
                         "Codec: DV (uncompressed) - wird als .dv-Datei gespeichert\n"
                         "⚠️ Live-Vorschau nur im USB-Modus verfügbar"
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
                         "Codec: H.264 (MP4) - universell kompatibel\n"
                         "✅ Live-Vorschau verfügbar"
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

        # Sonderzeichen aus Dateiname entfernen
        filename = filename.replace("/", "_").replace("\\", "_")
        
        # Stoppe Vorschau wenn läuft (um Ressourcen zu schonen)
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

        # Datei mit .mp4 - universell kompatibel
        output_file = os.path.join(self.output_dir, filename + ".mp4")

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
            self.process = subprocess.Popen(
                [
                    "ffmpeg",
                    # Video Input
                    "-f", "v4l2",
                    "-framerate", "30",
                    "-video_size", "640x480",
                    "-i", "/dev/video0",
                    # Audio Input
                    "-f", "alsa",
                    "-i", "default",
                    # Video Codec: H.264
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-profile:v", "baseline",
                    "-level", "3.0",
                    # Audio Codec: AAC
                    "-c:a", "aac",
                    "-b:a", "128k",
                    # Pixel Format
                    "-pix_fmt", "yuv420p",
                    # Overwrite
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
                if "frame=" in line:
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
        self.camera_status.config(
            text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit",
            fg="gray"
        )
        self.update_default_filename()

    # -------------------------------------------------
    # Programm schließen
    # -------------------------------------------------
    def close(self):
        # Stoppe Vorschau
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
