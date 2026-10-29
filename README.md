# 🎥 MiniDV Recorder

Eine produktionsreife Python-Anwendung zur Digitalisierung von MiniDV-Camcordern (FireWire) und USB-Webcams – mit Live-Vorschau, automatischer Segmentierung und robustem MKV-Container.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Produktionsreif-brightgreen)

---

## ✨ Features

- 📹 **FireWire-Unterstützung** – Digitalisierung von MiniDV-Camcordern via `dvgrab`
- 🎥 **USB-Webcam-Unterstützung** – Aufnahme via FFmpeg (V4L2)
- 📺 **Live-Vorschau** – Echtzeit-Vorschau der USB-Kamera (OpenCV + PIL)
- ⏱ **Automatische Segmentierung** – Aufteilung in konfigurierbare Segmente (5–60 Minuten)
- 🛡 **Crashsicher** – MKV-Container mit nativer FFmpeg-Segmentierung; kein Datenverlust bei Abbruch
- 💾 **Platzsparend** – H.264-Encoding mit hardware-schonenden Parametern für ältere Systeme
- 🔧 **Auto-Installer** – Fehlende Abhängigkeiten (`dvgrab`, `ffmpeg`) werden automatisch installiert
- 🎨 **Benutzerfreundliche GUI** – Tkinter-Oberfläche mit Timer, Fortschrittsbalken und Statusanzeige
- 📁 **Konfigurierbarer Speicherort** – Ausgabeverzeichnis wird gespeichert
- 🐧 **Multi-Plattform** – Linux (Debian/Ubuntu, Fedora, Arch), macOS, Windows (eingeschränkt)

---

## 📋 Voraussetzungen

### System
- **Python 3.10+**
- **FFmpeg** (für USB-Aufnahmen)
- **dvgrab** (für FireWire-Aufnahmen)
- **Tkinter** (Python-GUI)

### Python-Pakete
- `opencv-python`
- `Pillow`
- `numpy`

> 💡 **Hinweis:** Die Anwendung versucht, fehlende Abhängigkeiten automatisch zu installieren. Bei FireWire wird zusätzlich `dvgrab` benötigt.

---

## 🚀 Installation

### 1. Repository klonen

```bash
git clone https://github.com/DEIN-USER/minidv-recorder.git
cd minidv-recorder
