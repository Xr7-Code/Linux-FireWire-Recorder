#!/usr/bin/env python3
"""
MiniDV Recorder - PRODUKTIONSREIFE VERSION MIT KORREKTER SEGMENTIERUNG
Unterstützt FireWire und USB Webcam Aufnahmen mit stabiler, langer Laufzeit
Optimiert: MKV-Container, native FFmpeg-Segmentierung, Querformat-Layout
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
import json
import tempfile

from tkinter import messagebox, filedialog, ttk
from datetime import datetime
from pathlib import Path

# ============================================================
# PIL IMPORTS - KOMPATIBEL MIT ALLEN SYSTEMEN
# ============================================================

PIL_AVAILABLE = False
Image = None
ImageTk = None

try:
    from PIL import Image
    from PIL import ImageTk
    PIL_AVAILABLE = True
    print("✅ PIL/ImageTk importiert (normal)")
except ImportError:
    try:
        from PIL import Image
        import PIL.ImageTk as ImageTk
        PIL_AVAILABLE = True
        print("✅ PIL/ImageTk importiert (separat)")
    except ImportError:
        try:
            import Image
            import ImageTk
            PIL_AVAILABLE = True
            print("✅ PIL/ImageTk importiert (alt)")
        except ImportError:
            print("❌ PIL/ImageTk nicht gefunden!")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
    print(f"✅ OpenCV: {cv2.__version__}")
except ImportError:
    CV2_AVAILABLE = False
    print("❌ OpenCV nicht gefunden")

PREVIEW_AVAILABLE = PIL_AVAILABLE and CV2_AVAILABLE
print(f"📺 Vorschau verfügbar: {PREVIEW_AVAILABLE}")

# ============================================================
# KONFIGURATION
# ============================================================

CONFIG_FILE = os.path.expanduser("~/.minidv_recorder_config.json")

class Config:
    @staticmethod
    def load():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"output_dir": os.path.expanduser("~/Videos/MiniDV")}
    
    @staticmethod
    def save(config):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass

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
    def install_pip_package(pkg):
        pip_cmd = "pip3" if shutil.which("pip3") else "pip"
        methods = [
            f"{pip_cmd} install {pkg} --break-system-packages",
            f"{pip_cmd} install {pkg} --user",
            f"python3 -m pip install {pkg} --break-system-packages",
            f"python3 -m pip install {pkg} --user",
            f"sudo {pip_cmd} install {pkg}",
        ]
        for method in methods:
            success, _, _ = AutoInstaller.run_command(method)
            if success:
                return True
        return False
    
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
                "sudo apt update && sudo apt install -y dvgrab ffmpeg python3-tk python3-dev python3-pil.imagetk v4l-utils"
            )
        elif system == "fedora":
            success, _, _ = AutoInstaller.run_command(
                "sudo dnf install -y dvgrab ffmpeg python3-tkinter python3-devel python3-pillow v4l-utils"
            )
        elif system == "arch":
            success, _, _ = AutoInstaller.run_command(
                "sudo pacman -S --noconfirm dvgrab ffmpeg python-tk python-pillow v4l-utils"
            )
        elif system == "macos":
            if not shutil.which("brew"):
                AutoInstaller.run_command('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
            success, _, _ = AutoInstaller.run_command("brew install dvgrab ffmpeg")
        else:
            success = True
        
        if progress_callback:
            progress_callback("📦 Installiere Python-Pakete...", 60)
        
        for pkg in ["opencv-python", "Pillow", "numpy"]:
            if not AutoInstaller.install_pip_package(pkg):
                return False, f"Konnte {pkg} nicht installieren"
        
        if progress_callback:
            progress_callback("👤 Konfiguriere Berechtigungen...", 80)
        
        if system in ["debian", "fedora", "arch"]:
            user = os.getenv("USER")
            AutoInstaller.run_command(f"sudo usermod -a -G video {user}")
            for dev in glob.glob("/dev/video*"):
                AutoInstaller.run_command(f"sudo chmod 666 {dev}")
            
            AutoInstaller.run_command(
                'sudo bash -c \'cat > /etc/udev/rules.d/99-video.rules << EOF\nSUBSYSTEM=="video4linux", GROUP="video", MODE="0666"\nEOF\''
            )
            AutoInstaller.run_command("sudo udevadm control --reload-rules")
            AutoInstaller.run_command("sudo udevadm trigger")
        
        if progress_callback:
            progress_callback("✅ Fertig!", 100)
        
        return True, "Installation erfolgreich"


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
        
        # Konfiguration laden
        self.config = Config.load()
        self.output_dir = self.config.get("output_dir", os.path.expanduser("~/Videos/MiniDV"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Aufnahme-Status
        self.preview_running = False
        self.preview_thread = None
        self.cap = None
        self.preview_fps = 15
        self.recording_active = False
        self.current_output_file = None
        self.segment_thread_running = False
        
        # Segmentierung (wird jetzt von FFmpeg nativ übernommen)
        self.segment_duration = 600  # 10 Minuten pro Segment
        self.segment_count = 0
        self.segment_base_name = ""
        self.segment_files = []
        self.segment_lock = threading.Lock()
        
        # Robustheit
        self.recording_monitor_thread = None
        self.last_frame_time = 0
        self.write_error_count = 0
        
        self.preview_available = PREVIEW_AVAILABLE
        print(f"📺 Vorschau im Programm: {self.preview_available}")

        os.environ['TERM'] = 'xterm-256color'

        self.master.title("MiniDV Recorder - Produktionsversion")
        # Kompakteres Querformat (780x520) für kleine Bildschirme
        self.master.geometry("780x520")
        self.master.resizable(False, False)
        
        self._fix_webcam_permissions()
        self.setup_ui()
        self.master.after(100, self._check_dependencies_at_start)
        self.master.protocol("WM_DELETE_WINDOW", self.close)
    
    def _fix_webcam_permissions(self):
        for dev in glob.glob("/dev/video*"):
            try:
                os.system(f"sudo chmod 666 {dev} 2>/dev/null")
            except:
                pass
    
    def setup_ui(self):
        # ===== HAUPT-CONTAINER (zweispaltig) =====
        main_container = tk.Frame(self.master)
        main_container.pack(fill="both", expand=True, padx=8, pady=6)
        
        # ----- LINKE SPALTE (Vorschau + Quelle) -----
        left_col = tk.Frame(main_container)
        left_col.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 6))
        
        # Quelle
        top = tk.Frame(left_col)
        top.pack(pady=(0, 3))
        
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
        
        # Status
        self.dep_status = tk.Label(left_col, text="⏳ Prüfe Abhängigkeiten...", 
            font=("Arial", 8), fg="orange")
        self.dep_status.pack()
        
        self.camera_status = tk.Label(left_col, text="📹 Kamera bereit", 
            font=("Arial", 9, "bold"), fg="gray")
        self.camera_status.pack(pady=(2, 3))
        
        # Hinweis
        self.hint_label = tk.Label(left_col, text="", font=("Arial", 8), fg="gray")
        self.hint_label.pack()
        self.update_hint()
        
        # Vorschau
        preview_frame = tk.Frame(left_col, bd=2, relief="groove")
        preview_frame.pack(pady=4, fill="x")
        
        tk.Label(preview_frame, text="📺 Live-Vorschau", font=("Arial", 9, "bold")).pack(pady=(2, 0))
        
        self.preview_canvas = tk.Canvas(preview_frame, width=420, height=236, bg="black")
        self.preview_canvas.pack(pady=3, padx=3)
        
        if self.preview_available:
            self.preview_canvas.create_text(210, 118, 
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white", font=("Arial", 10), justify="center")
        else:
            self.preview_canvas.create_text(210, 118,
                text="⚠️ Vorschau nicht verfügbar\n\nInstalliere:\nsudo apt install python3-pil.imagetk",
                fill="yellow", font=("Arial", 9), justify="center")
        
        pbtn_frame = tk.Frame(preview_frame)
        pbtn_frame.pack(pady=(0, 3))
        
        self.preview_start_btn = tk.Button(pbtn_frame, text="▶ Vorschau starten", width=14,
            font=("Arial", 9), command=self.start_preview,
            bg="#4CAF50" if self.preview_available else "gray", fg="white",
            state="normal" if self.preview_available else "disabled")
        self.preview_start_btn.pack(side=tk.LEFT, padx=3)
        
        self.preview_stop_btn = tk.Button(pbtn_frame, text="■ Vorschau stoppen", width=14,
            font=("Arial", 9), command=self.stop_preview,
            state="disabled", bg="#C62828", fg="white")
        self.preview_stop_btn.pack(side=tk.LEFT, padx=3)
        
        # ----- RECHTE SPALTE (Einstellungen + Aufnahme) -----
        right_col = tk.Frame(main_container)
        right_col.pack(side=tk.RIGHT, fill="both", padx=(6, 0))
        
        # Titel
        tk.Label(right_col, text="Digitalisierung", 
            font=("Arial", 12, "bold")).pack(pady=(0, 2))
        
        # Segmentierung
        seg_frame = tk.Frame(right_col)
        seg_frame.pack(pady=2, fill="x")
        
        tk.Label(seg_frame, text="⏱ Segment:", font=("Arial", 9)).pack(side=tk.LEFT)
        
        self.seg_var = tk.StringVar(value="600")
        seg_options = ["300", "600", "900", "1200", "1800", "3600"]
        self.seg_combo = ttk.Combobox(seg_frame, textvariable=self.seg_var, 
                                       values=seg_options, width=6, state="readonly")
        self.seg_combo.pack(side=tk.LEFT, padx=4)
        self.seg_combo.bind("<<ComboboxSelected>>", self.on_seg_change)
        
        tk.Label(seg_frame, text="s", font=("Arial", 9)).pack(side=tk.LEFT)
        
        tk.Button(seg_frame, text="ℹ️", width=2, font=("Arial", 8),
                 command=self.show_seg_info).pack(side=tk.RIGHT, padx=2)
        
        # Speicherort
        loc_frame = tk.Frame(right_col)
        loc_frame.pack(pady=2, fill="x")
        
        self.output_label = tk.Label(loc_frame, text=f"📁 {self.output_dir}", 
            font=("Arial", 8), anchor="w", wraplength=280)
        self.output_label.pack(side=tk.LEFT, fill="x", expand=True)
        
        tk.Button(loc_frame, text="📁", width=3, command=self.choose_folder).pack(side=tk.RIGHT)
        
        # Dateiname
        name_frame = tk.Frame(right_col)
        name_frame.pack(pady=2, fill="x")
        
        tk.Label(name_frame, text="Datei:", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        
        self.filename_var = tk.StringVar()
        self.update_default_filename()
        self.filename_entry = tk.Entry(name_frame, textvariable=self.filename_var, 
            width=24, font=("Arial", 9))
        self.filename_entry.pack(side=tk.LEFT, padx=4)
        
        tk.Label(name_frame, text=".mkv", font=("Arial", 9), fg="gray").pack(side=tk.LEFT)
        
        # Codec Info
        codec_frame = tk.Frame(right_col)
        codec_frame.pack(pady=1)
        tk.Label(codec_frame, text="Codec: H.264 (MKV) - robust & crashsicher", 
            font=("Arial", 8), fg="#1565C0").pack()
        
        # Aufnahme Buttons
        btn_frame = tk.Frame(right_col)
        btn_frame.pack(pady=6)
        
        self.start_btn = tk.Button(btn_frame, text="▶ AUFNAHME STARTEN", 
            font=("Arial", 11, "bold"), width=22,
            command=self.start_recording, bg="#4CAF50", fg="white")
        self.start_btn.pack(pady=2)
        
        self.stop_btn = tk.Button(btn_frame, text="■ AUFNAHME STOPPEN",
            font=("Arial", 11, "bold"), width=22,
            command=self.stop_recording, state="disabled", 
            bg="#C62828", fg="white")
        self.stop_btn.pack(pady=2)
        
        # Status & Timer
        self.status = tk.Label(right_col, text="Bereit", fg="green", font=("Arial", 10))
        self.status.pack(pady=2)
        
        self.timer_label = tk.Label(right_col, text="⏱ 00:00:00", 
            font=("Arial", 12, "bold"))
        self.timer_label.pack(pady=1)
        
        # Fortschritt
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(right_col, variable=self.progress_var, 
                                            maximum=100, length=280, mode='determinate')
        self.progress_bar.pack(pady=4)
        
        self.status_detail = tk.Label(right_col, text="", font=("Arial", 8), fg="gray")
        self.status_detail.pack()
    
    def show_seg_info(self):
        messagebox.showinfo("Segmentierung",
            "Die Segmentierung teilt die Aufnahme automatisch in kleinere Dateien.\n\n"
            "Vorteile:\n"
            "• Keine Beschädigung bei Abbruch\n"
            "• Einfacheres Handling großer Aufnahmen\n"
            "• Keine verlorenen Daten bei Fehlern\n\n"
            "Empfehlung: 600 Sekunden (10 Minuten)")
    
    def on_seg_change(self, event=None):
        try:
            self.segment_duration = int(self.seg_var.get())
        except:
            self.segment_duration = 600
    
    def start_preview(self):
        if self.preview_running:
            return
        
        if not self.preview_available:
            messagebox.showerror("Fehler", 
                "Vorschau nicht verfügbar!\n\nInstalliere:\nsudo apt install python3-pil.imagetk")
            return
        
        if self.mode != "usb":
            messagebox.showinfo("Info", "Vorschau nur im USB-Modus verfügbar")
            return
        
        try:
            self._fix_webcam_permissions()
            self.cap = cv2.VideoCapture(0)
            
            if not self.cap.isOpened():
                messagebox.showerror("Fehler", "Webcam konnte nicht geöffnet werden")
                return
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            for _ in range(5):
                self.cap.read()
            
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.cap.release()
                messagebox.showerror("Fehler", "Webcam liefert kein Bild")
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
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    continue
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame_rgb.shape[:2]
                tw, th = 420, 236
                
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
            self.preview_canvas.create_text(210, 118,
                text="🖥️ Vorschau bereit\n\nKlicke auf 'Vorschau starten'",
                fill="white", font=("Arial", 10), justify="center")
        self.status.config(text="Bereit", fg="green")
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
    
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
        
        devices = glob.glob("/dev/video*")
        if devices:
            self.camera_status.config(text=f"📷 Webcam gefunden: {', '.join(devices)}", fg="green")
        else:
            self.camera_status.config(text="⚠️ Keine Webcam gefunden", fg="orange")
    
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
            self.preview_canvas.create_text(210, 118,
                text="ℹ️ Vorschau nur im USB-Modus",
                fill="white", font=("Arial", 11))
    
    def update_hint(self):
        if self.mode == "firewire":
            if DependencyManager.check_dependency("dvgrab"):
                self.hint_label.config(text="📹 FireWire: MiniDV Camcorder | Codec: DV → .dv")
            else:
                self.hint_label.config(text="⚠️ dvgrab fehlt! Installiere: sudo apt install dvgrab")
        else:
            if DependencyManager.check_dependency("ffmpeg"):
                self.hint_label.config(text="🎥 USB: Webcam | Codec: H.264 (MKV) | Segmentierung aktiv")
            else:
                self.hint_label.config(text="⚠️ ffmpeg fehlt! Installiere: sudo apt install ffmpeg")
    
    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            os.makedirs(self.output_dir, exist_ok=True)
            self.config["output_dir"] = self.output_dir
            Config.save(self.config)
            self.output_label.config(text=f"📁 {self.output_dir}")
    
    def update_default_filename(self):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        suffix = "Webcam" if self.mode == "usb" else "MiniDV"
        self.filename_var.set(f"{ts}_{suffix}")
    
    def start_recording(self):
        if self.process or self.recording_active:
            return
        
        filename = self.filename_var.get().strip()
        if not filename:
            messagebox.showerror("Fehler", "Bitte Dateinamen eingeben")
            return
        
        filename = filename.replace("/", "_").replace("\\", "_")
        
        if self.preview_running:
            self.stop_preview()
        
        self.segment_count = 0
        self.segment_base_name = filename
        self.segment_files = []
        self.recording_active = True
        self.segment_thread_running = True
        
        if self.mode == "firewire":
            self._start_firewire(filename)
        else:
            self._start_usb_segmented(filename)
        
        # Starte Überwachungsthread
        if self.recording_active:
            self.recording_monitor_thread = threading.Thread(target=self._monitor_recording, daemon=True)
            self.recording_monitor_thread.start()
    
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
            self.recording_active = False
    
    def _start_usb_segmented(self, filename):
        """Startet FFmpeg mit nativer Segmentierung in MKV-Container"""
        if not DependencyManager.check_dependency("ffmpeg"):
            messagebox.showerror("Fehler", "ffmpeg nicht installiert!\nsudo apt install ffmpeg")
            return
        
        output_pattern = os.path.join(self.output_dir, f"{filename}_seg%03d.mkv")
        
        try:
            print(f"📹 Starte native FFmpeg-Segmentierung: {filename}_seg%03d.mkv")
            
            # Prüfe Audio-Gerät
            has_alsa = os.path.exists("/dev/snd") or shutil.which("arecord") is not None
            
            cmd = [
                "ffmpeg",
                "-f", "v4l2",
                "-input_format", "mjpeg",
                "-framerate", "25",
                "-video_size", "640x480",
                "-i", "/dev/video0",
            ]
            
            # Audio nur hinzufügen wenn verfügbar
            if has_alsa:
                cmd += ["-f", "alsa", "-i", "default"]
            
            cmd += [
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-tune", "zerolatency",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-profile:v", "baseline",
                "-level", "3.0",
                "-pix_fmt", "yuv420p",
            ]
            
            if has_alsa:
                cmd += ["-c:a", "aac", "-b:a", "128k"]
            
            cmd += [
                "-f", "segment",
                "-segment_time", str(self.segment_duration),
                "-reset_timestamps", "1",
                "-segment_format", "matroska",
                "-y",
                output_pattern
            ]
            
            print(f"🔧 FFmpeg Befehl: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                bufsize=1
            )
            
            # Starte Thread zum Lesen der Ausgabe
            threading.Thread(target=self._read_ffmpeg_output, daemon=True).start()
            
            self._set_recording_state(True)
            self.status.config(text="● USB Aufnahme (FFmpeg-Segmentierung)", fg="red")
            self.camera_status.config(text="🎥 Webcam aktiv - Segmentierung läuft", fg="green")
            self.status_detail.config(text=f"📹 Aufnahme: {filename}_segXXX.mkv")
            
        except Exception as e:
            print(f"❌ Fehler beim Starten der Aufnahme: {e}")
            self.process = None
            self.recording_active = False
            self.master.after(0, lambda: messagebox.showerror("Fehler", 
                f"Aufnahme konnte nicht gestartet werden:\n\n{str(e)}"))
    
    def _monitor_recording(self):
        """Überwacht die Aufnahme auf Probleme und sammelt Segmentdateien"""
        last_scan = time.time()
        
        while self.recording_active:
            time.sleep(3)
            
            # Prüfe auf freien Speicherplatz
            try:
                stat = os.statvfs(self.output_dir)
                free_space = stat.f_frsize * stat.f_bavail
                if free_space < 100 * 1024 * 1024:  # Weniger als 100MB
                    self.master.after(0, lambda: self._handle_low_space())
                    break
            except:
                pass
            
            # Sammle Segmentdateien
            if time.time() - last_scan > 5:
                last_scan = time.time()
                pattern = os.path.join(self.output_dir, f"{self.segment_base_name}_seg*.mkv")
                found = sorted(glob.glob(pattern))
                for f in found:
                    if f not in self.segment_files:
                        self.segment_files.append(f)
                        self.segment_count = len(self.segment_files)
                        self.master.after(0, lambda c=self.segment_count: self._update_segment_info(c))
    
    def _update_segment_info(self, count):
        self.status_detail.config(text=f"📹 {count} Segment(e) aufgezeichnet")
    
    def _handle_low_space(self):
        messagebox.showwarning("Warnung", 
            "Niedriger Speicherplatz!\n\n"
            "Weniger als 100MB verfügbar.\n"
            "Die Aufnahme wird beendet.")
        self.stop_recording()
    
    def _set_recording_state(self, is_recording):
        if is_recording:
            if not self.recording_start:
                self.recording_start = datetime.now()
                self.timer_running = True
                self.update_timer()
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.filename_entry.config(state="disabled")
            self.preview_start_btn.config(state="disabled")
            self.preview_stop_btn.config(state="disabled")
            self.mode_var.set(self.mode)
            self.firewire_radio.config(state="disabled")
            self.usb_radio.config(state="disabled")
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.filename_entry.config(state="normal")
            self.preview_start_btn.config(state="normal" if self.preview_available else "disabled")
            self.preview_stop_btn.config(state="disabled")
            self.firewire_radio.config(state="normal")
            self.usb_radio.config(state="normal")
            self.status_detail.config(text="")
            self.progress_var.set(0)
    
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
                if "frame=" in line:
                    # Aktualisiere Fortschritt (grob)
                    try:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p.startswith("frame="):
                                frame_num = int(p.split("=")[1])
                                if frame_num % 50 == 0:
                                    fps = 25
                                    max_frames = self.segment_duration * fps
                                    progress = min(100, (frame_num % max_frames) / max_frames * 100)
                                    self.master.after(0, lambda p=progress: self.progress_var.set(p))
                                break
                    except:
                        pass
        except:
            pass
    
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
    
    def stop_recording(self):
        if not self.process and not self.recording_active:
            return
        
        self.recording_active = False
        self.segment_thread_running = False
        
        if self.process:
            try:
                print("⏹️ Beende Aufnahme...")
                # Sanft beenden (SIGINT), damit FFmpeg das MKV finalisieren kann
                self.process.send_signal(signal.SIGINT)
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print("⚠️ Prozess reagiert nicht, erzwinge Beenden")
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                print(f"Fehler beim Beenden: {e}")
            
            self.process = None
        
        self.reset_timer()
        self._set_recording_state(False)
        self.status.config(text="✅ Aufnahme beendet", fg="green")
        self.camera_status.config(text="📹 Bereit" if self.mode == "firewire" else "🎥 Bereit", fg="gray")
        self.update_default_filename()
        
        # Sammle finale Segmentdateien
        if self.mode == "usb":
            pattern = os.path.join(self.output_dir, f"{self.segment_base_name}_seg*.mkv")
            found = sorted(glob.glob(pattern))
            self.segment_files = found
        
        messagebox.showinfo("Aufnahme beendet", 
            f"Die Aufnahme wurde erfolgreich beendet.\n\n"
            f"Erstellte Dateien: {len(self.segment_files)}\n"
            f"Speicherort: {self.output_dir}")
    
    def close(self):
        if self.preview_running:
            self.stop_preview()
        if self.process or self.recording_active:
            if messagebox.askyesno("Aufnahme läuft", 
                "Die Aufnahme läuft noch.\nSoll sie beendet werden?"):
                self.stop_recording()
            else:
                return
        self.master.destroy()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    try:
        os.environ['TERM'] = 'xterm-256color'
        root = tk.Tk()
        app = MiniDVRecorder(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\n👋 Programm beendet")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        sys.exit(1)
