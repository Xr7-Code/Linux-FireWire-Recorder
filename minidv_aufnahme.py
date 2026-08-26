#!/usr/bin/env python3

import os
import shutil
import signal
import subprocess
import threading
import tkinter as tk

from tkinter import messagebox, filedialog
from datetime import datetime



class MiniDVRecorder:


    def __init__(self, master):

        self.master = master

        self.process = None


        # Timer

        self.recording_start = None
        self.timer_running = False



        # Speicherort

        self.default_output_dir = os.path.expanduser(
            "~/Videos/MiniDV"
        )

        self.output_dir = self.default_output_dir


        os.makedirs(
            self.output_dir,
            exist_ok=True
        )



        master.title(
            "MiniDV Überspielung"
        )


        master.geometry(
            "450x560"
        )


        master.resizable(
            False,
            False
        )



        # Kamera Status

        self.camera_status = tk.Label(
            master,
            text="📹 Kamera bereit",
            font=("Arial",10,"bold"),
            fg="gray"
        )

        self.camera_status.place(
            x=250,
            y=10
        )



        tk.Label(
            master,
            text="Medion MD 9021\nMiniDV Archivierung",
            font=("Arial",16,"bold")
        ).pack(
            pady=35
        )



        # Speicherort Anzeige

        self.output_label = tk.Label(
            master,
            text=f"Speicherort:\n{self.output_dir}",
            font=("Arial",10),
            justify="center"
        )

        self.output_label.pack()



        self.folder_btn = tk.Button(
            master,
            text="📁 Speicherort wählen",
            font=("Arial",10),
            command=self.choose_folder
        )

        self.folder_btn.pack(
            pady=8
        )



        tk.Label(
            master,
            text="Hinweis:\nMiniDV Kamera über FireWire anschließen.",
            font=("Arial",8),
            fg="gray",
            justify="center"
        ).pack(
            pady=(0,10)
        )



        # Dateiname

        tk.Label(
            master,
            text="Dateiname:",
            font=("Arial",10,"bold")
        ).pack(
            pady=(10,2)
        )



        self.filename_var = tk.StringVar()


        self.update_default_filename()



        self.filename_entry = tk.Entry(
            master,
            textvariable=self.filename_var,
            width=42,
            font=("Arial",10),
            justify="center"
        )

        self.filename_entry.pack()



        tk.Label(
            master,
            text="(kann vor der Aufnahme geändert werden)",
            font=("Arial",8),
            fg="gray"
        ).pack()



        # Start Button

        self.start_btn = tk.Button(
            master,
            text="▶ Aufnahme starten",
            font=("Arial",13),
            width=24,
            command=self.start_recording,
            bg="#4CAF50",
            fg="white"
        )

        self.start_btn.pack(
            pady=12
        )



        # Stop Button

        self.stop_btn = tk.Button(
            master,
            text="■ Aufnahme beenden",
            font=("Arial",13),
            width=24,
            command=self.stop_recording,
            state="disabled",
            bg="#C62828",
            fg="white"
        )

        self.stop_btn.pack()



        # Status

        self.status = tk.Label(
            master,
            text="Bereit",
            fg="green",
            font=("Arial",12)
        )

        self.status.pack(
            pady=15
        )



        # Timer Anzeige

        self.timer_label = tk.Label(
            master,
            text="Aufnahmedauer: 00:00:00",
            font=("Arial",12)
        )

        self.timer_label.pack()



        master.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )



    def choose_folder(self):

        folder = filedialog.askdirectory(
            title="Speicherort auswählen",
            initialdir=self.output_dir
        )


        if folder:

            self.output_dir = folder


            os.makedirs(
                self.output_dir,
                exist_ok=True
            )


            self.output_label.config(
                text=f"Speicherort:\n{self.output_dir}"
            )



    def update_default_filename(self):

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )


        self.filename_var.set(
            f"{timestamp}_MiniDV"
        )
        
    # -------------------------------------------------
    # Aufnahme starten
    # -------------------------------------------------

    def start_recording(self):

        if self.process:
            return



        if shutil.which("dvgrab") is None:

            messagebox.showerror(
                "Fehler",
                "Das Programm 'dvgrab' wurde nicht gefunden."
            )

            return



        filename = self.filename_var.get().strip()


        if not filename:

            messagebox.showerror(
                "Fehler",
                "Bitte einen Dateinamen eingeben."
            )

            return



        filename = filename.replace(
            "/",
            "_"
        )

        filename = filename.replace(
            "\\",
            "_"
        )



        prefix = os.path.join(
            self.output_dir,
            filename + "_"
        )



        try:

            # Nur EIN dvgrab Prozess!
            self.process = subprocess.Popen(
                [
                    "dvgrab",
                    "-showstatus",
                    "-f",
                    "raw",
                    "-autosplit",
                    "-timestamp",
                    prefix
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )



            threading.Thread(
                target=self.read_dvgrab_status,
                daemon=True
            ).start()



            self.status.config(
                text="● Aufnahme läuft",
                fg="red"
            )


            self.recording_start = datetime.now()

            self.timer_running = True

            self.update_timer()



            self.start_btn.config(
                state="disabled"
            )


            self.stop_btn.config(
                state="normal"
            )


            self.filename_entry.config(
                state="disabled"
            )


            self.folder_btn.config(
                state="disabled"
            )



        except Exception as err:


            messagebox.showerror(
                "Fehler",
                f"Aufnahme konnte nicht gestartet werden:\n\n{err}"
            )


            self.process = None




    # -------------------------------------------------
    # dvgrab Ausgabe lesen
    # -------------------------------------------------

    def read_dvgrab_status(self):

        try:

            for line in self.process.stdout:


                print(
                    line.strip()
                )


                if "Found AV/C device" in line:


                    self.master.after(
                        0,
                        lambda:
                        self.camera_status.config(
                            text="📹 Kamera erkannt",
                            fg="green"
                        )
                    )



                elif "Waiting for DV" in line:


                    self.master.after(
                        0,
                        lambda:
                        self.camera_status.config(
                            text="📹 Warte auf DV-Signal",
                            fg="orange"
                        )
                    )



                elif "Capture Started" in line:


                    self.master.after(
                        0,
                        lambda:
                        self.camera_status.config(
                            text="📹 DV-Signal aktiv",
                            fg="green"
                        )
                    )



        except Exception:

            pass




    # -------------------------------------------------
    # Timer
    # -------------------------------------------------

    def update_timer(self):

        if self.timer_running and self.recording_start:


            elapsed = datetime.now() - self.recording_start


            total_seconds = int(
                elapsed.total_seconds()
            )


            hours = total_seconds // 3600

            minutes = (
                total_seconds % 3600
            ) // 60

            seconds = (
                total_seconds % 60
            )


            self.timer_label.config(
                text=f"Aufnahmedauer: {hours:02d}:{minutes:02d}:{seconds:02d}"
            )


            self.master.after(
                1000,
                self.update_timer
            )



    def reset_timer(self):

        self.timer_running = False

        self.recording_start = None


        self.timer_label.config(
            text="Aufnahmedauer: 00:00:00"
        )
        
    # -------------------------------------------------
    # Aufnahme stoppen
    # -------------------------------------------------

    def stop_recording(self):

        if not self.process:

            return



        try:

            self.process.send_signal(
                signal.SIGINT
            )


            self.process.wait(
                timeout=10
            )



        except subprocess.TimeoutExpired:

            self.process.kill()



        except Exception as err:


            messagebox.showerror(
                "Fehler",
                f"Fehler beim Beenden der Aufnahme:\n\n{err}"
            )



        self.process = None



        self.reset_timer()



        self.status.config(
            text="Bereit",
            fg="green"
        )



        self.camera_status.config(
            text="📹 Kamera bereit",
            fg="gray"
        )



        self.start_btn.config(
            state="normal"
        )


        self.stop_btn.config(
            state="disabled"
        )


        self.filename_entry.config(
            state="normal"
        )


        self.folder_btn.config(
            state="normal"
        )


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


    app = MiniDVRecorder(
        root
    )


    root.mainloop()
