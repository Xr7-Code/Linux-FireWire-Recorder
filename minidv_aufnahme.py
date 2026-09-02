#!/usr/bin/env python3
"""
MiniDV Recorder - Kompakte Version mit Auto-Installer
Alle Funktionen der Originalversion, aber platzsparendes Layout
"""

import os
import shutil
import signal
import subprocess
import threading
import tkinter as tk
import sys
import platform
import time
import glob

from tkinter import messagebox, filedialog
from datetime import datetime

# ============================================================
# AUTO-INSTALLER
# ============================================================

class AutoInstaller:
    @staticmethod
    def get_system():
        system = platform.system().lower()
        if system == "linux":
            try:
                with open("/etc/os-release") as f:
                    content = f.read()
                    if "ubuntu" in content.lower() or "debian" in content.lower() or "zorin" in content.lower():
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
    def run_command(cmd, timeout=300):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout, result.stderr
        except:
            return False, "", "Fehler"
    
    @staticmethod
    def check_dependencies():
        checks = {
            "dvgrab": shutil.which("dvgrab") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "tkinter": False, "cv2": False, "PIL": False
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
        system = AutoInstaller.get_system()
        
        if progress_callback:
            progress_callback("📦 Installiere Systempakete...", 30)
        
        if system == "debian":
            success, _, _ = AutoInstaller.run_command(
                "sudo apt update && sudo apt install -y dvgrab ffmpeg python3-tk python3-dev"
            )
        elif system == "fedora":
            success, _, _ = AutoInstaller.run_command(
                "sudo dnf install -y dvgrab ffmpeg python3-tkinter python3-devel"
            )
        elif system == "arch":
            success, _, _ = AutoInstaller.run_command(
                "sudo pacman -S --noconfirm dvgrab ffmpeg python-tk"
            )
        elif system == "macos":
            if not shutil.which("brew"):
                AutoInstaller.run_command('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
            success, _, _ = AutoInstaller.run_command("brew install dvgrab ffmpeg")
        else:
            success = True
        
        if progress_callback:
            progress_callback("📦 Installiere Python-Pakete...", 60)
        
        pip_cmd = "pip3" if shutil.which("pip3") else "pip"
        for pkg in ["opencv-python", "Pillow", "numpy"]:
            for method in [
                f"{pip_cmd} install {pkg} --break-system-packages",
                f"{pip_cmd} install {pkg} --user",
                f"sudo {pip_cmd} install {pkg}"
            ]:
                success, _, _ = AutoInstaller.run_command(method)
                if success:
                    break
        
        if progress_callback:
            progress_callback("👤 Konfiguriere Berechtigungen...", 80)
        
        if system in ["debian", "fedora", "arch"]:
            user = os.getenv("USER")
            AutoInstaller.run_command(f"sudo usermod -a -G video {user}")
            for dev in glob.glob("/dev/video*"):
                AutoInstaller.run_command(f"sudo chmod 666 {dev}")
        
        if progress_callback:
            progress_callback("✅ Fertig!", 100)
        
        return True, "Installation erfolgreich"


# ============================================================
# OPTIONALE IMPORTS
# ============================================================

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


# ============================================================
# HAUPTANWENDUNG
# ============================================================

class DependencyManager:
    @staticmethod
    def check_dependency(command):
        return shutil.which(command) is not None
    
    @staticmethod
    def get_package_manager():
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
        if not package_manager_cmd:
            return False, "Kein Paketmanager gefunden"
        try:
            cmd = package_manager_cmd.split() + [package_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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
        missing = []
        install_commands = []
        
        if not DependencyManager.check_dependency("dvgrab"):
            missing.append("dvgrab")
            install_commands.append("dvgrab")
        
        if not DependencyManager.check_dependency("ffmpeg"):
            missing.append("ffmpeg")
            install_commands.append("ffmpeg")
        
        if not missing:
            return True, "Alle Abhängigkeiten sind installiert"
        
        pm_name, pm_cmd = DependencyManager.get_package_manager()
        
        if pm_name == "windows":
            msg = ("Folgende Programme werden benötigt:\n\n" + 
                   f"{', '.join(missing)}\n\n" +
                   "Bitte installiere sie manuell:\n" +
                   "• dvgrab: https://sourceforge.net/projects/dvgrab/\n" +
                   "• ffmpeg: https://ffmpeg.org/download.html")
            messagebox.showwarning("Abhängigkeiten fehlen", msg)
            return False, "Manuelle Installation erforderlich"
        
        if not pm_cmd:
            msg = (f"Folgende Programme werden benötigt:\n\n" +
                   f"{', '.join(missing)}\n\n" +
                   "Bitte installiere sie manuell mit deinem Paketmanager.")
            messagebox.showwarning("Abhängigkeiten fehlen", msg)
            return False, "Manuelle Installation erforderlich"
        
        msg = (f"Folgende Programme werden benötigt:\n\n" +
               f"{', '.join(missing)}\n\n" +
               f"Soll {pm_name.upper()} die Installation durchführen?\n\n" +
               f"Befehl: {pm_cmd} {' '.join(install_commands)}")
        
        if not messagebox.askyesno("Abhängigkeiten installieren", msg):
            return False, "Installation abgebrochen"
        
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
            messagebox.showerror("Installationsfehler",
                f"Einige Pakete konnten nicht installiert werden:\n\n" + "\n".join(errors) +
                "\n\nBitte installiere sie manuell.")
            return False, "Installation fehlgeschlagen"


class MiniDVRecorder:
    def __init__(self, master):
        self.master = master
        self.process = None
        self.recording_start = None
        self.timer_running = False
        self.mode = "firewire"
        self.default_output_dir = os.path.expanduser("~/Videos/MiniDV")
        self.output_dir = self.default_output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.preview_running = False
        self.preview_thread = None
        self.cap = None
        self.preview_fps = 15
        self.preview_available = PIL_AVAILABLE and CV2_AVAILABLE

        self.master.title("MiniDV Recorder")
        self.master.geometry("500x620")
        self.master.resizable(False, False)
        
        self.setup_ui()
        self.master.after(100, self._check_dependencies_at_start)
    
    def setup_ui(self):
        # ===== OBERER BEREICH =====
        top = tk.Frame(self.master)
        top.pack(pady=(10, 3))
        
        tk.Label(top, text="Quelle:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=3)
        self.mode_var = tk.StringVar(value="firewire")
        
        self.firewire_radio = tk.Radiobutton(top, text="📹 FireWire", 
            variable=self.mode_var, value="firewire", font=("Arial", 9),
            command=self.on_mode_change)
        self.firewire_radio.pack(side=tk.LEFT, padx=3)
        
        self.usb_radio = tk.Radiobutton(top, text="🎥 USB", 
            variable=self.mode_var, value="usb", font=("Arial", 9),
            command=self.on_mode_change)
        self.usb_radio.pack(side=tk.LEFT, padx=3)
        
        # ===== STATUS =====
        self.dep_status = tk.Label(self.master, text="⏳ Prüfe Abhängigkeiten...", 
            font=("Arial", 8), fg="orange")
        self.dep_status.pack()
        
        self.camera_status = tk.Label(self.master, text="📹 Kamera bereit", 
            font=("Arial", 9, "bold"), fg="gray")
        self.camera_status.pack(pady=(2, 3))
        
        # ===== TITEL =====
        tk.Label(self.master, text="Digitalisierung von Videoquellen", 
            font=("Arial", 13, "bold")).pack(pady=(5, 2))
        
        self.hint_label = tk.Label(self.master, text="", font=("Arial", 8), fg="gray")
        self.hint_label.pack()
        self.update_hint()
        
        # ===== VORSCHAU =====
        preview_frame = tk.Frame(self.master, bd=2, relief="groove")
        preview_frame.pack(pady=5, padx=10, fill="x")
        
        tk.Label(preview_frame, text="📺 Live-Vorschau", font=("Arial", 9, "bold")).pack(pady=(3, 0))
        
        self.preview_canvas = tk.Canvas(preview_frame, width=460, height=240, bg="black")
        self.preview_canvas.pack(pady=5, padx=5)
        
        if self.preview_available:
            self.preview_canvas.create_text(230, 120, 
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white", font=("Arial", 11), justify="center")
        else:
            self.preview_canvas.create_text(230, 120,
                text="⚠️ Vorschau nicht verfügbar\n\nInstalliere:\npip install opencv-python Pillow",
                fill="yellow", font=("Arial", 9), justify="center")
        
        pbtn_frame = tk.Frame(preview_frame)
        pbtn_frame.pack(pady=(0, 5))
        
        self.preview_start_btn = tk.Button(pbtn_frame, text="▶ Vorschau starten", width=14,
            font=("Arial", 9), command=self.start_preview,
            bg="#4CAF50" if self.preview_available else "gray", fg="white",
            state="normal" if self.preview_available else "disabled")
        self.preview_start_btn.pack(side=tk.LEFT, padx=3)
        
        self.preview_stop_btn = tk.Button(pbtn_frame, text="■ Vorschau stoppen", width=14,
            font=("Arial", 9), command=self.stop_preview,
            state="disabled", bg="#C62828", fg="white")
        self.preview_stop_btn.pack(side=tk.LEFT, padx=3)
        
        # ===== SPEICHERORT =====
        loc_frame = tk.Frame(self.master)
        loc_frame.pack(pady=3, fill="x", padx=10)
        
        self.output_label = tk.Label(loc_frame, text=f"📁 {self.output_dir}", 
            font=("Arial", 9), anchor="w", wraplength=350)
        self.output_label.pack(side=tk.LEFT, fill="x", expand=True)
        
        tk.Button(loc_frame, text="📁", width=3, command=self.choose_folder).pack(side=tk.RIGHT)
        
        # ===== DATEINAME =====
        name_frame = tk.Frame(self.master)
        name_frame.pack(pady=3, fill="x", padx=10)
        
        tk.Label(name_frame, text="Datei:", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        
        self.filename_var = tk.StringVar()
        self.update_default_filename()
        self.filename_entry = tk.Entry(name_frame, textvariable=self.filename_var, 
            width=28, font=("Arial", 9))
        self.filename_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(name_frame, text=".mp4", font=("Arial", 9), fg="gray").pack(side=tk.LEFT)
        
        # ===== CODEC INFO =====
        codec_frame = tk.Frame(self.master)
        codec_frame.pack(pady=2)
        tk.Label(codec_frame, text="Codec: H.264 (MP4) - universell kompatibel", 
            font=("Arial", 8), fg="#1565C0").pack()
        
        # ===== AUFNAHME BUTTONS =====
        btn_frame = tk.Frame(self.master)
        btn_frame.pack(pady=8)
        
        self.start_btn = tk.Button(btn_frame, text="▶ AUFNAHME STARTEN", 
            font=("Arial", 12, "bold"), width=24,
            command=self.start_recording, bg="#4CAF50", fg="white")
        self.start_btn.pack(pady=3)
        
        self.stop_btn = tk.Button(btn_frame, text="■ AUFNAHME STOPPEN",
            font=("Arial", 12, "bold"), width=24,
            command=self.stop_recording, state="disabled", 
            bg="#C62828", fg="white")
        self.stop_btn.pack(pady=3)
        
        # ===== STATUS & TIMER =====
        self.status = tk.Label(self.master, text="Bereit", fg="green", font=("Arial", 11))
        self.status.pack(pady=3)
        
        self.timer_label = tk.Label(self.master, text="⏱ 00:00:00", 
            font=("Arial", 13, "bold"))
        self.timer_label.pack(pady=2)
        
        self.master.protocol("WM_DELETE_WINDOW", self.close)
    
    # -------------------------------------------------
    # VORSCHAU
    # -------------------------------------------------
    def start_preview(self):
        if self.preview_running:
            return
        
        if not self.preview_available:
            messagebox.showerror("Fehler", 
                "Vorschau nicht verfügbar!\n\nInstalliere:\npip install opencv-python Pillow")
            return
        
        if self.mode != "usb":
            messagebox.showinfo("Info", "Vorschau nur im USB-Modus verfügbar")
            return
        
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror("Fehler", "Webcam konnte nicht geöffnet werden")
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
        while self.preview_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame_rgb.shape[:2]
                tw, th = 460, 240
                scale = min(tw/w, th/h)
                nw, nh = int(w*scale), int(h*scale)
                resized = cv2.resize(frame_rgb, (nw, nh))
                canvas = np.zeros((th, tw, 3), dtype=np.uint8)
                xo, yo = (tw-nw)//2, (th-nh)//2
                canvas[yo:yo+nh, xo:xo+nw] = resized
                img = Image.fromarray(canvas)
                img_tk = ImageTk.PhotoImage(img)
                self.master.after(0, self._update_preview, img_tk)
            except Exception as e:
                print(f"Vorschau Fehler: {e}")
                break
            time.sleep(1.0 / self.preview_fps)
    
    def _update_preview(self, img_tk):
        if self.preview_running:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, anchor="nw", image=img_tk)
            self.preview_canvas.image = img_tk
    
    def stop_preview(self):
        self.preview_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.preview_start_btn.config(state="normal" if self.preview_available else "disabled")
        self.preview_stop_btn.config(state="disabled")
        self.preview_canvas.delete("all")
        if self.preview_available:
            self.preview_canvas.create_text(230, 120,
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white", font=("Arial", 11), justify="center")
        self.status.config(text="Bereit", fg="green")
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
    
    # -------------------------------------------------
    # ABHÄNGIGKEITEN
    # -------------------------------------------------
    def _check_dependencies_at_start(self):
        def show_progress(text):
            progress = tk.Toplevel(self.master)
            progress.title("Installation")
            progress.geometry("400x100")
            progress.resizable(False, False)
            progress.transient(self.master)
            progress.grab_set()
            tk.Label(progress, text=text, font=("Arial", 12)).pack(pady=20)
            tk.Label(progress, text="Bitte warten...", font=("Arial", 10), fg="gray").pack()
            progress.update()
            return progress
        
        dvgrab_ok = DependencyManager.check_dependency("dvgrab")
        ffmpeg_ok = DependencyManager.check_dependency("ffmpeg")
        
        if not dvgrab_ok or not ffmpeg_ok:
            self.dep_status.config(text="⚠️ Einige Abhängigkeiten fehlen", fg="orange")
            success, msg = DependencyManager.ensure_dependencies(self.master, show_progress)
            if success:
                self.dep_status.config(text="✅ System-Abhängigkeiten: OK", fg="green")
            else:
                self.dep_status.config(text="⚠️ Abhängigkeiten fehlen", fg="red")
        else:
            self.dep_status.config(text="✅ System-Abhängigkeiten: OK", fg="green")
        
        if not self.preview_available:
            self.dep_status.config(text="✅ System: OK | ⚠️ Vorschau: nicht verfügbar", fg="orange")
    
    # -------------------------------------------------
    # UI FUNKTIONEN
    # -------------------------------------------------
    def on_mode_change(self):
        if self.preview_running:
            self.stop_preview()
        self.mode = self.mode_var.get()
        self.update_hint()
        self.update_default_filename()
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
        self.status.config(text="Bereit", fg="green")
        if self.mode != "usb" and self.preview_available:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(230, 120,
                text="ℹ️ Vorschau nur im USB-Modus",
                fill="white", font=("Arial", 12))
    
    def update_hint(self):
        if self.mode == "firewire":
            if DependencyManager.check_dependency("dvgrab"):
                self.hint_label.config(text="📹 FireWire: MiniDV Camcorder | Codec: DV → .dv")
            else:
                self.hint_label.config(text="⚠️ dvgrab fehlt! Installiere: sudo apt install dvgrab")
        else:
            if DependencyManager.check_dependency("ffmpeg"):
                self.hint_label.config(text="🎥 USB: Webcam | Codec: H.264 (MP4)")
            else:
                self.hint_label.config(text="⚠️ ffmpeg fehlt! Installiere: sudo apt install ffmpeg")
    
    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            os.makedirs(self.output_dir, exist_ok=True)
            self.output_label.config(text=f"📁 {self.output_dir}")
    
    def update_default_filename(self):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        suffix = "Webcam" if self.mode == "usb" else "MiniDV"
        self.filename_var.set(f"{ts}_{suffix}")
    
    # -------------------------------------------------
    # AUFNAHME
    # -------------------------------------------------
    def start_recording(self):
        if self.process:
            return
        
        filename = self.filename_var.get().strip()
        if not filename:
            messagebox.showerror("Fehler", "Bitte Dateinamen eingeben")
            return
        
        filename = filename.replace("/", "_").replace("\\", "_")
        
        if self.preview_running:
            self.stop_preview()
        
        if self.mode == "firewire":
            self._start_firewire(filename)
        else:
            self._start_usb(filename)
    
    def _start_firewire(self, filename):
        if not DependencyManager.check_dependency("dvgrab"):
            messagebox.showerror("Fehler", "dvgrab nicht installiert!\nsudo apt install dvgrab")
            return
        
        prefix = os.path.join(self.output_dir, filename + "_")
        try:
            self.process = subprocess.Popen(
                ["dvgrab", "-showstatus", "-f", "raw", "-autosplit", "-timestamp", prefix],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            threading.Thread(target=self._read_dvgrab_output, daemon=True).start()
            self._set_recording_state(True)
            self.status.config(text="● FireWire Aufnahme läuft", fg="red")
        except Exception as e:
            messagebox.showerror("Fehler", f"Aufnahme konnte nicht gestartet werden:\n\n{str(e)}")
            self.process = None
    
    def _start_usb(self, filename):
        if not DependencyManager.check_dependency("ffmpeg"):
            messagebox.showerror("Fehler", "ffmpeg nicht installiert!\nsudo apt install ffmpeg")
            return
        
        output_file = os.path.join(self.output_dir, filename + ".mp4")
        if os.path.exists(output_file):
            if not messagebox.askyesno("Datei existiert", 
                f"Die Datei '{filename}.mp4' existiert bereits.\nÜberschreiben?"):
                return
        
        try:
            self.process = subprocess.Popen(
                [
                    "ffmpeg", "-f", "v4l2", "-framerate", "30", "-video_size", "640x480",
                    "-i", "/dev/video0", "-f", "alsa", "-i", "default",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-profile:v", "baseline", "-level", "3.0",
                    "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-y", output_file
                ],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            threading.Thread(target=self._read_ffmpeg_output, daemon=True).start()
            self._set_recording_state(True)
            self.status.config(text="● USB Webcam Aufnahme läuft", fg="red")
            self.camera_status.config(text="🎥 Webcam aktiv", fg="green")
        except Exception as e:
            messagebox.showerror("Fehler", f"Aufnahme konnte nicht gestartet werden:\n\n{str(e)}")
            self.process = None
    
    def _set_recording_state(self, is_recording):
        if is_recording:
            self.recording_start = datetime.now()
            self.timer_running = True
            self.update_timer()
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.filename_entry.config(state="disabled")
            self.preview_start_btn.config(state="disabled")
            self.preview_stop_btn.config(state="disabled")
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.filename_entry.config(state="normal")
            self.preview_start_btn.config(state="normal" if self.preview_available else "disabled")
            self.preview_stop_btn.config(state="disabled")
    
    # -------------------------------------------------
    # AUSGABE LESEN
    # -------------------------------------------------
    def _read_dvgrab_output(self):
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
        try:
            for line in self.process.stdout:
                print(line.strip())
                if "Input #0" in line:
                    self.master.after(0, lambda: self.camera_status.config(text="🎥 Webcam erkannt", fg="green"))
        except:
            pass
    
    # -------------------------------------------------
    # TIMER
    # -------------------------------------------------
    def update_timer(self):
        if self.timer_running and self.recording_start:
            elapsed = datetime.now() - self.recording_start
            total = int(elapsed.total_seconds())
            h, m, s = total//3600, (total%3600)//60, total%60
            self.timer_label.config(text=f"⏱ {h:02d}:{m:02d}:{s:02d}")
            self.master.after(1000, self.update_timer)
    
    def reset_timer(self):
        self.timer_running = False
        self.recording_start = None
        self.timer_label.config(text="⏱ 00:00:00")
    
    # -------------------------------------------------
    # STOP & CLOSE
    # -------------------------------------------------
    def stop_recording(self):
        if not self.process:
            return
        try:
            self.process.send_signal(signal.SIGINT)
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Beenden:\n\n{str(e)}")
        self.process = None
        self.reset_timer()
        self._set_recording_state(False)
        self.status.config(text="Bereit", fg="green")
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
        self.update_default_filename()
    
    def close(self):
        if self.preview_running:
            self.stop_preview()
        if self.process:
            if messagebox.askyesno("Aufnahme läuft", "Die Aufnahme läuft noch.\nSoll sie beendet werden?"):
                self.stop_recording()
            else:
                return
        self.master.destroy()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
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
