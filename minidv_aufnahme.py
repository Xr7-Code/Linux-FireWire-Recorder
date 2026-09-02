#!/usr/bin/env python3
"""
MiniDV Recorder - All-in-One mit Auto-Installer
Einfach ausführen, das Programm installiert alle Abhängigkeiten selbst!
"""

import os
import sys
import subprocess
import platform
import shutil
import signal
import threading
import time
import glob
from datetime import datetime

# ============================================================
# AUTO-INSTALLER
# ============================================================

class AutoInstaller:
    """Automatische Installation aller Abhängigkeiten."""
    
    @staticmethod
    def get_system():
        """Ermittelt das Betriebssystem."""
        system = platform.system().lower()
        if system == "linux":
            try:
                with open("/etc/os-release") as f:
                    content = f.read()
                    if "ubuntu" in content.lower() or "debian" in content.lower():
                        return "debian"
                    elif "zorin" in content.lower():
                        return "debian"
                    elif "fedora" in content.lower():
                        return "fedora"
                    elif "arch" in content.lower():
                        return "arch"
            except:
                pass
        elif system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"
        return "unknown"
    
    @staticmethod
    def run_command(cmd, capture_output=False, timeout=300):
        """Führt einen Befehl aus."""
        try:
            if capture_output:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=timeout
                )
                return result.returncode == 0, result.stdout, result.stderr
            else:
                result = subprocess.run(cmd, shell=True, timeout=timeout)
                return result.returncode == 0, "", ""
        except subprocess.TimeoutExpired:
            return False, "", "Zeitüberschreitung"
        except Exception as e:
            return False, "", str(e)
    
    @staticmethod
    def check_dependencies():
        """Prüft ob alle Abhängigkeiten installiert sind."""
        checks = {
            "dvgrab": shutil.which("dvgrab") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "tkinter": False,
            "cv2": False,
            "PIL": False,
        }
        
        try:
            import tkinter
            checks["tkinter"] = True
        except:
            pass
        
        try:
            import cv2
            checks["cv2"] = True
        except:
            pass
        
        try:
            from PIL import Image
            checks["PIL"] = True
        except:
            pass
        
        return checks
    
    @staticmethod
    def install_all(progress_callback=None):
        """Installiert alle Abhängigkeiten."""
        system = AutoInstaller.get_system()
        
        if progress_callback:
            progress_callback("🔍 Prüfe System...", 0)
        
        # 1. Systempakete installieren
        if progress_callback:
            progress_callback("📦 Installiere Systempakete...", 20)
        
        if system == "debian":
            success, _, _ = AutoInstaller.run_command(
                "sudo apt update && sudo apt install -y dvgrab ffmpeg python3-tk python3-dev python3-opencv python3-pil"
            )
            if not success:
                # Versuche ohne opencv-pil (manchmal gibt es das nicht)
                success, _, _ = AutoInstaller.run_command(
                    "sudo apt update && sudo apt install -y dvgrab ffmpeg python3-tk python3-dev"
                )
        
        elif system == "fedora":
            success, _, _ = AutoInstaller.run_command(
                "sudo dnf install -y dvgrab ffmpeg python3-tkinter python3-devel python3-opencv python3-pillow"
            )
        
        elif system == "arch":
            success, _, _ = AutoInstaller.run_command(
                "sudo pacman -S --noconfirm dvgrab ffmpeg python-tk python-opencv python-pillow"
            )
        
        elif system == "macos":
            if not shutil.which("brew"):
                AutoInstaller.run_command(
                    '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
                )
            success, _, _ = AutoInstaller.run_command("brew install dvgrab ffmpeg")
        
        elif system == "windows":
            success = True  # Windows: manuelle Installation
        else:
            success = False
        
        if not success and system != "windows":
            return False, "Systempakete konnten nicht installiert werden"
        
        # 2. Python-Pakete installieren
        if progress_callback:
            progress_callback("📦 Installiere Python-Pakete...", 50)
        
        pip_cmd = "pip3" if shutil.which("pip3") else "pip"
        packages = ["opencv-python", "Pillow", "numpy"]
        
        for pkg in packages:
            methods = [
                f"{pip_cmd} install {pkg} --break-system-packages",
                f"{pip_cmd} install {pkg} --user",
                f"python3 -m pip install {pkg} --break-system-packages",
                f"sudo {pip_cmd} install {pkg}",
            ]
            
            installed = False
            for method in methods:
                success, _, _ = AutoInstaller.run_command(method)
                if success:
                    installed = True
                    break
            
            if not installed:
                return False, f"Konnte {pkg} nicht installieren"
        
        # 3. Benutzer zur video-Gruppe hinzufügen
        if progress_callback:
            progress_callback("👤 Konfiguriere Berechtigungen...", 80)
        
        if system in ["debian", "fedora", "arch"]:
            user = os.getenv("USER")
            AutoInstaller.run_command(f"sudo usermod -a -G video {user}")
            
            # Setze Berechtigungen für /dev/video*
            for dev in glob.glob("/dev/video*"):
                AutoInstaller.run_command(f"sudo chmod 666 {dev}")
        
        if progress_callback:
            progress_callback("✅ Installation abgeschlossen!", 100)
        
        return True, "Installation erfolgreich"


# ============================================================
# HAUPTANWENDUNG
# ============================================================

# Versuche Module zu importieren (nach erfolgreicher Installation)
try:
    import tkinter as tk
    from tkinter import messagebox, filedialog, ttk
    TKINTER_AVAILABLE = True
except:
    TKINTER_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except:
    CV2_AVAILABLE = False


class MiniDVRecorder:
    """Hauptanwendung für MiniDV und Webcam Aufnahme."""
    
    def __init__(self, master):
        self.master = master
        self.process = None
        self.recording_start = None
        self.timer_running = False
        self.mode = "firewire"
        self.preview_running = False
        self.preview_thread = None
        self.cap = None
        self.preview_fps = 15
        self.preview_available = PIL_AVAILABLE and CV2_AVAILABLE
        
        # Standard-Speicherort
        self.default_output_dir = os.path.expanduser("~/Videos/MiniDV")
        self.output_dir = self.default_output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Prüfe ob alle Abhängigkeiten da sind
        if not self.check_all_dependencies():
            return
        
        self.init_ui()
    
    def check_all_dependencies(self):
        """Prüft alle Abhängigkeiten und installiert sie bei Bedarf."""
        checks = AutoInstaller.check_dependencies()
        
        missing = []
        if not checks["dvgrab"]:
            missing.append("dvgrab")
        if not checks["ffmpeg"]:
            missing.append("ffmpeg")
        if not checks["tkinter"]:
            missing.append("python3-tk")
        if not checks["cv2"]:
            missing.append("opencv-python")
        if not checks["PIL"]:
            missing.append("Pillow")
        
        if not missing:
            return True
        
        # Frage ob installiert werden soll
        msg = f"Folgende Abhängigkeiten fehlen:\n\n" + "\n".join(f"• {pkg}" for pkg in missing)
        msg += "\n\nSoll ich sie automatisch installieren?"
        
        if not messagebox.askyesno("Abhängigkeiten fehlen", msg):
            messagebox.showwarning(
                "Abbruch",
                "Das Programm kann ohne die fehlenden Abhängigkeiten nicht starten."
            )
            return False
        
        # Installiere
        progress_window = self.create_progress_window()
        
        def install_thread():
            success, msg = AutoInstaller.install_all(
                lambda text, progress: self.update_progress(progress_window, text, progress)
            )
            
            progress_window.after(0, progress_window.destroy)
            
            if success:
                messagebox.showinfo(
                    "Erfolg",
                    "✅ Alle Abhängigkeiten wurden installiert!\n\n"
                    "Bitte starte das Programm neu."
                )
                self.master.after(100, self.master.destroy)
            else:
                messagebox.showerror(
                    "Fehler",
                    f"❌ Installation fehlgeschlagen:\n\n{msg}\n\n"
                    "Bitte installiere die Abhängigkeiten manuell:\n"
                    "sudo apt install dvgrab ffmpeg python3-tk\n"
                    "pip install opencv-python Pillow"
                )
                self.master.after(100, self.master.destroy)
        
        threading.Thread(target=install_thread, daemon=True).start()
        return False
    
    def create_progress_window(self):
        """Erstellt ein Fortschrittsfenster."""
        progress = tk.Toplevel(self.master)
        progress.title("Installation")
        progress.geometry("500x250")
        progress.resizable(False, False)
        progress.transient(self.master)
        progress.grab_set()
        
        # Zentrieren
        progress.update_idletasks()
        x = (progress.winfo_screenwidth() // 2) - (500 // 2)
        y = (progress.winfo_screenheight() // 2) - (250 // 2)
        progress.geometry(f"500x250+{x}+{y}")
        
        tk.Label(
            progress,
            text="🔧 Installation der Abhängigkeiten",
            font=("Arial", 14, "bold")
        ).pack(pady=15)
        
        self.progress_label = tk.Label(
            progress,
            text="Starte Installation...",
            font=("Arial", 11)
        )
        self.progress_label.pack(pady=10)
        
        self.progress_bar = ttk.Progressbar(
            progress,
            length=400,
            mode='determinate'
        )
        self.progress_bar.pack(pady=10)
        
        self.progress_status = tk.Label(
            progress,
            text="",
            font=("Arial", 9),
            fg="gray"
        )
        self.progress_status.pack(pady=5)
        
        # Speichere Referenz
        progress.progress_label = self.progress_label
        progress.progress_bar = self.progress_bar
        progress.progress_status = self.progress_status
        
        return progress
    
    def update_progress(self, window, text, progress):
        """Aktualisiert das Fortschrittsfenster."""
        window.after(0, lambda: window.progress_label.config(text=text))
        window.after(0, lambda: window.progress_bar.config(value=progress))
        window.after(0, lambda: window.progress_status.config(text=f"Fortschritt: {progress}%"))
        window.after(0, window.update)
    
    def init_ui(self):
        """Erstellt die Benutzeroberfläche."""
        self.master.title("MiniDV / Webcam Recorder mit Auto-Installer")
        self.master.geometry("620x900")
        self.master.resizable(False, False)
        
        # ========== MODUS ==========
        mode_frame = tk.Frame(self.master)
        mode_frame.pack(pady=(15, 5))
        
        tk.Label(mode_frame, text="Quelle wählen:", font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.mode_var = tk.StringVar(value="firewire")
        
        self.firewire_radio = tk.Radiobutton(
            mode_frame, text="📹 Camcorder (FireWire)",
            variable=self.mode_var, value="firewire",
            font=("Arial", 10), command=self.on_mode_change
        )
        self.firewire_radio.pack(side=tk.LEFT, padx=5)
        
        self.usb_radio = tk.Radiobutton(
            mode_frame, text="🎥 Webcam (USB)",
            variable=self.mode_var, value="usb",
            font=("Arial", 10), command=self.on_mode_change
        )
        self.usb_radio.pack(side=tk.LEFT, padx=5)
        
        # ========== STATUS ==========
        self.dep_status = tk.Label(
            self.master,
            text="✅ Alle Abhängigkeiten: OK" if self.preview_available else "⚠️ Vorschau nicht verfügbar",
            font=("Arial", 9),
            fg="green" if self.preview_available else "orange"
        )
        self.dep_status.pack(pady=(2, 0))
        
        self.camera_status = tk.Label(
            self.master,
            text="📹 Kamera bereit",
            font=("Arial", 10, "bold"),
            fg="gray"
        )
        self.camera_status.pack(pady=(5, 0))
        
        tk.Label(
            self.master,
            text="Digitalisierung von Videoquellen",
            font=("Arial", 14, "bold")
        ).pack(pady=(10, 5))
        
        # ========== HINWEIS ==========
        self.hint_label = tk.Label(
            self.master,
            text="",
            font=("Arial", 8),
            fg="gray",
            justify="center"
        )
        self.hint_label.pack(pady=(0, 5))
        self.update_hint()
        
        # ========== VORSCHAU ==========
        preview_frame = tk.Frame(self.master, bd=2, relief="groove")
        preview_frame.pack(pady=10, padx=10, fill="x")
        
        tk.Label(preview_frame, text="📺 Live-Vorschau", font=("Arial", 11, "bold")).pack(pady=(5, 0))
        
        self.preview_canvas = tk.Canvas(preview_frame, width=480, height=270, bg="black")
        self.preview_canvas.pack(padx=10, pady=(5, 10))
        
        if self.preview_available:
            self.preview_canvas.create_text(
                240, 135,
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white", font=("Arial", 12), justify="center"
            )
        else:
            self.preview_canvas.create_text(
                240, 135,
                text="⚠️ Vorschau nicht verfügbar\n\n"
                     "Pillow und/oder OpenCV fehlen\n\n"
                     "Installiere mit:\n"
                     "pip install opencv-python Pillow",
                fill="yellow", font=("Arial", 10), justify="center"
            )
        
        preview_btn_frame = tk.Frame(preview_frame)
        preview_btn_frame.pack(pady=(0, 10))
        
        self.preview_start_btn = tk.Button(
            preview_btn_frame, text="▶ Vorschau starten",
            font=("Arial", 10), command=self.start_preview,
            bg="#4CAF50" if self.preview_available else "gray",
            fg="white",
            state="normal" if self.preview_available else "disabled"
        )
        self.preview_start_btn.pack(side=tk.LEFT, padx=5)
        
        self.preview_stop_btn = tk.Button(
            preview_btn_frame, text="■ Vorschau stoppen",
            font=("Arial", 10), command=self.stop_preview,
            state="disabled", bg="#C62828", fg="white"
        )
        self.preview_stop_btn.pack(side=tk.LEFT, padx=5)
        
        # ========== SPEICHERORT ==========
        self.output_label = tk.Label(
            self.master,
            text=f"Speicherort:\n{self.output_dir}",
            font=("Arial", 10), justify="center"
        )
        self.output_label.pack()
        
        self.folder_btn = tk.Button(
            self.master, text="📁 Speicherort wählen",
            font=("Arial", 10), command=self.choose_folder
        )
        self.folder_btn.pack(pady=5)
        
        # ========== DATEINAME ==========
        tk.Label(self.master, text="Dateiname:", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        
        self.filename_var = tk.StringVar()
        self.update_default_filename()
        
        self.filename_entry = tk.Entry(
            self.master,
            textvariable=self.filename_var,
            width=42, font=("Arial", 10), justify="center"
        )
        self.filename_entry.pack()
        
        tk.Label(
            self.master,
            text="(kann vor der Aufnahme geändert werden)",
            font=("Arial", 8), fg="gray"
        ).pack()
        
        # ========== CODEC INFO ==========
        codec_frame = tk.Frame(self.master)
        codec_frame.pack(pady=5)
        
        tk.Label(codec_frame, text="Codec: ", font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Label(
            codec_frame,
            text="H.264 (MP4) - universell kompatibel",
            font=("Arial", 9, "bold"), fg="#1565C0"
        ).pack(side=tk.LEFT)
        
        # ========== BUTTONS ==========
        self.start_btn = tk.Button(
            self.master, text="▶ Aufnahme starten",
            font=("Arial", 13), width=24,
            command=self.start_recording,
            bg="#4CAF50", fg="white"
        )
        self.start_btn.pack(pady=12)
        
        self.stop_btn = tk.Button(
            self.master, text="■ Aufnahme beenden",
            font=("Arial", 13), width=24,
            command=self.stop_recording,
            state="disabled", bg="#C62828", fg="white"
        )
        self.stop_btn.pack()
        
        # ========== STATUS ==========
        self.status = tk.Label(
            self.master,
            text="Bereit",
            fg="green", font=("Arial", 12)
        )
        self.status.pack(pady=10)
        
        # ========== TIMER ==========
        self.timer_label = tk.Label(
            self.master,
            text="Aufnahmedauer: 00:00:00",
            font=("Arial", 12)
        )
        self.timer_label.pack()
        
        self.master.protocol("WM_DELETE_WINDOW", self.close)
    
    # ============================================================
    # VORSCHAU
    # ============================================================
    
    def start_preview(self):
        """Startet die Live-Vorschau."""
        if self.preview_running:
            return
        
        if not self.preview_available:
            messagebox.showerror(
                "Fehler",
                "Vorschau nicht verfügbar!\n\n"
                "Installiere die fehlenden Pakete:\n"
                "pip install opencv-python Pillow"
            )
            return
        
        if self.mode != "usb":
            messagebox.showinfo("Info", "Live-Vorschau ist nur im USB-Modus verfügbar.")
            return
        
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
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width = frame_rgb.shape[:2]
                target_width, target_height = 480, 270
                
                scale = min(target_width / width, target_height / height)
                new_width, new_height = int(width * scale), int(height * scale)
                resized = cv2.resize(frame_rgb, (new_width, new_height))
                
                canvas_img = np.zeros((target_height, target_width, 3), dtype=np.uint8)
                x_offset = (target_width - new_width) // 2
                y_offset = (target_height - new_height) // 2
                canvas_img[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized
                
                img = Image.fromarray(canvas_img)
                img_tk = ImageTk.PhotoImage(img)
                
                self.master.after(0, self._update_preview, img_tk)
                
            except Exception as e:
                print(f"Vorschau Fehler: {e}")
                break
            
            time.sleep(1.0 / self.preview_fps)
    
    def _update_preview(self, img_tk):
        """Aktualisiert das Vorschau-Canvas."""
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
        
        self.preview_canvas.delete("all")
        if self.preview_available:
            self.preview_canvas.create_text(
                240, 135,
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white", font=("Arial", 12), justify="center"
            )
        
        self.status.config(text="Bereit", fg="green")
        self.camera_status.config(text="🎥 Bereit" if self.mode == "firewire" else "📹 Bereit", fg="gray")
    
    # ============================================================
    # UI FUNKTIONEN
    # ============================================================
    
    def on_mode_change(self):
        """Wird bei Moduswechsel aufgerufen."""
        if self.preview_running:
            self.stop_preview()
        
        self.mode = self.mode_var.get()
        self.update_hint()
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
        self.status.config(text="Bereit", fg="green")
        self.update_default_filename()
        
        if self.mode != "usb" and self.preview_available:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                240, 135,
                text="ℹ️ Vorschau nur im USB-Modus verfügbar",
                fill="white", font=("Arial", 12), justify="center"
            )
    
    def update_hint(self):
        """Aktualisiert den Hinweistext."""
        if self.mode == "firewire":
            self.hint_label.config(
                text="MiniDV Camcorder über FireWire (IEEE 1394) anschließen.\n"
                     "Codec: DV (uncompressed) - wird als .dv-Datei gespeichert"
            )
        else:
            self.hint_label.config(
                text="Webcam über USB anschließen.\n"
                     "Codec: H.264 (MP4) - universell kompatibel"
            )
    
    def choose_folder(self):
        """Wählt den Speicherordner."""
        folder = filedialog.askdirectory(
            title="Speicherort auswählen",
            initialdir=self.output_dir
        )
        if folder:
            self.output_dir = folder
            os.makedirs(self.output_dir, exist_ok=True)
            self.output_label.config(text=f"Speicherort:\n{self.output_dir}")
    
    def update_default_filename(self):
        """Setzt den Standard-Dateinamen."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        suffix = "Webcam" if self.mode == "usb" else "MiniDV"
        self.filename_var.set(f"{timestamp}_{suffix}")
    
    # ============================================================
    # AUFNAHME
    # ============================================================
    
    def start_recording(self):
        """Startet die Aufnahme."""
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
        """Startet FireWire-Aufnahme."""
        if not shutil.which("dvgrab"):
            messagebox.showerror(
                "Fehler",
                "dvgrab nicht gefunden!\nInstalliere: sudo apt install dvgrab"
            )
            return
        
        prefix = os.path.join(self.output_dir, filename + "_")
        
        try:
            self.process = subprocess.Popen(
                ["dvgrab", "-showstatus", "-f", "raw", "-autosplit", "-timestamp", prefix],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            
            threading.Thread(target=self._read_dvgrab_output, daemon=True).start()
            self._set_recording_state(True)
            self.status.config(text="● FireWire Aufnahme läuft", fg="red")
            
        except Exception as err:
            messagebox.showerror("Fehler", f"Aufnahme konnte nicht gestartet werden:\n\n{err}")
            self.process = None
    
    def _start_usb_recording(self, filename):
        """Startet USB-Webcam-Aufnahme."""
        if not shutil.which("ffmpeg"):
            messagebox.showerror(
                "Fehler",
                "ffmpeg nicht gefunden!\nInstalliere: sudo apt install ffmpeg"
            )
            return
        
        output_file = os.path.join(self.output_dir, filename + ".mp4")
        
        if os.path.exists(output_file):
            if not messagebox.askyesno("Datei existiert", f"Die Datei '{os.path.basename(output_file)}' existiert bereits.\nÜberschreiben?"):
                return
        
        try:
            self.process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-f", "v4l2", "-framerate", "30", "-video_size", "640x480", "-i", "/dev/video0",
                    "-f", "alsa", "-i", "default",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-profile:v", "baseline", "-level", "3.0",
                    "-c:a", "aac", "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-y", output_file
                ],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            
            threading.Thread(target=self._read_ffmpeg_output, daemon=True).start()
            self._set_recording_state(True)
            self.status.config(text="● USB Webcam Aufnahme läuft", fg="red")
            self.camera_status.config(text="🎥 Webcam aktiv", fg="green")
            
        except Exception as err:
            messagebox.showerror("Fehler", f"Aufnahme konnte nicht gestartet werden:\n\n{err}")
            self.process = None
    
    def _set_recording_state(self, is_recording):
        """Setzt den UI-Status für Aufnahme."""
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
    
    # ============================================================
    # AUSGABE LESEN
    # ============================================================
    
    def _read_dvgrab_output(self):
        """Liest dvgrab Ausgabe."""
        try:
            for line in self.process.stdout:
                print(line.strip())
                if "Found AV/C device" in line:
                    self.master.after(0, lambda: self.camera_status.config(text="📹 Kamera erkannt", fg="green"))
                elif "Waiting for DV" in line:
                    self.master.after(0, lambda: self.camera_status.config(text="📹 Warte auf DV-Signal", fg="orange"))
                elif "Capture Started" in line:
                    self.master.after(0, lambda: self.camera_status.config(text="📹 DV-Signal aktiv", fg="green"))
        except:
            pass
    
    def _read_ffmpeg_output(self):
        """Liest ffmpeg Ausgabe."""
        try:
            for line in self.process.stdout:
                print(line.strip())
                if "Input #0" in line:
                    self.master.after(0, lambda: self.camera_status.config(text="🎥 Webcam erkannt", fg="green"))
        except:
            pass
    
    # ============================================================
    # TIMER
    # ============================================================
    
    def update_timer(self):
        """Aktualisiert den Timer."""
        if self.timer_running and self.recording_start:
            elapsed = datetime.now() - self.recording_start
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            self.timer_label.config(text=f"Aufnahmedauer: {hours:02d}:{minutes:02d}:{seconds:02d}")
            self.master.after(1000, self.update_timer)
    
    def reset_timer(self):
        """Setzt den Timer zurück."""
        self.timer_running = False
        self.recording_start = None
        self.timer_label.config(text="Aufnahmedauer: 00:00:00")
    
    # ============================================================
    # AUFNAHME STOPPEN
    # ============================================================
    
    def stop_recording(self):
        """Stoppt die Aufnahme."""
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
    
    # ============================================================
    # PROGRAMM SCHLIESSEN
    # ============================================================
    
    def close(self):
        """Schließt das Programm."""
        if self.preview_running:
            self.stop_preview()
        
        if self.process:
            if messagebox.askyesno("Aufnahme läuft", "Die Aufnahme läuft noch.\nSoll sie beendet werden?"):
                self.stop_recording()
            else:
                return
        
        self.master.destroy()


# ============================================================
# PROGRAMMSTART
# ============================================================

if __name__ == "__main__":
    # Prüfe ob Tkinter verfügbar ist (für GUI)
    if not TKINTER_AVAILABLE:
        print("❌ Tkinter nicht installiert!")
        print("\n📌 Installation:")
        print("   sudo apt install python3-tk")
        print("\n   Oder für andere Distributionen:")
        print("   Fedora: sudo dnf install python3-tkinter")
        print("   Arch:   sudo pacman -S python-tk")
        sys.exit(1)
    
    try:
        root = tk.Tk()
        app = MiniDVRecorder(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\n👋 Programm beendet")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        sys.exit(1)
