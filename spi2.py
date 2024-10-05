import tkinter as tk
from tkinter import messagebox, ttk
import sounddevice as sd
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time
from dtw import accelerated_dtw
from sklearn.preprocessing import normalize

class VoiceSimilarityApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Similarity Analyzer")
        self.root.geometry("1200x900")
        self.root.configure(bg='#e0f7fa')

        # Variables to hold recorded audio data
        self.recorded_audio_1 = None
        self.recorded_audio_2 = None
        self.sample_rate = 44100

        # GUI Elements
        self.create_widgets()

    def create_widgets(self):
        # Title label
        title_label = tk.Label(self.root, text="Voice Similarity Analyzer", font=("Helvetica", 20, "bold"), bg='#e0f7fa', fg="#00796b")
        title_label.pack(pady=10)

        # Frame for device selection and controls
        control_frame = tk.Frame(self.root, bg='#e0f7fa')
        control_frame.pack(side=tk.LEFT, padx=20, pady=20, fill=tk.Y)

        # Select audio input device
        tk.Label(control_frame, text="Select Audio Input Device", font=("Helvetica", 12), bg='#e0f7fa').pack(pady=5)
        self.device_listbox = tk.Listbox(control_frame, height=8, bg='#ffffff', selectbackground='#007acc', font=("Helvetica", 10))
        self.device_listbox.pack(pady=5, fill=tk.X)
        devices = sd.query_devices()
        for idx, device in enumerate(devices):
            self.device_listbox.insert(idx, device['name'])

        # Record first audio button
        self.record_button_1 = ttk.Button(control_frame, text="Record First Audio", command=self.record_audio_1)
        self.record_button_1.pack(pady=5, fill=tk.X)

        # Record second audio button
        self.record_button_2 = ttk.Button(control_frame, text="Record Second Audio", command=self.record_audio_2)
        self.record_button_2.pack(pady=5, fill=tk.X)

        # Analyze similarity button
        self.analyze_button = ttk.Button(control_frame, text="Analyze Similarity", command=self.analyze_similarity)
        self.analyze_button.pack(pady=5, fill=tk.X)

        # Clear results button
        self.clear_button = ttk.Button(control_frame, text="Clear Results", command=self.clear_results)
        self.clear_button.pack(pady=5, fill=tk.X)

        # Progress label
        self.progress_label = tk.Label(control_frame, text="", bg='#e0f7fa', font=("Helvetica", 10))
        self.progress_label.pack(pady=10)

        # Frame for plots
        self.plot_frame = tk.Frame(self.root, bg='#e0f7fa')
        self.plot_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

        # Frame for analysis steps
        self.steps_frame = tk.Frame(control_frame, bg='#e0f7fa', bd=2, relief=tk.RIDGE)
        self.steps_frame.pack(pady=10, fill=tk.X)
        tk.Label(self.steps_frame, text="Analysis Steps", font=("Helvetica", 12, "bold"), bg='#e0f7fa').pack()
        self.steps_listbox = tk.Listbox(self.steps_frame, height=10, bg='#ffffff', font=("Helvetica", 10))
        self.steps_listbox.pack(pady=5, fill=tk.BOTH)

    def record_audio_1(self):
        selected_device = self.device_listbox.curselection()
        if not selected_device:
            messagebox.showerror("Error", "Please select an audio input device.")
            return
        device_index = selected_device[0]
        
        def record():
            self.progress_label.config(text="Recording first audio started...", fg="green")
            self.root.update()
            time.sleep(0.5)
            self.recorded_audio_1 = sd.rec(int(7 * self.sample_rate), samplerate=self.sample_rate, channels=1, device=device_index)
            sd.wait()  # Wait until the recording is finished
            self.progress_label.config(text="First audio recording finished.", fg="blue")
            self.steps_listbox.insert(tk.END, "First audio recorded.")
            self.root.update()
        
        record_thread = threading.Thread(target=record)
        record_thread.start()
        

    def record_audio_2(self):
        selected_device = self.device_listbox.curselection()
        if not selected_device:
            messagebox.showerror("Error", "Please select an audio input device.")
            return
        device_index = selected_device[0]
        
        def record():
            self.progress_label.config(text="Recording second audio started...", fg="green")
            self.root.update()
            time.sleep(0.5)
            self.recorded_audio_2 = sd.rec(int(7 * self.sample_rate), samplerate=self.sample_rate, channels=1, device=device_index)
            sd.wait()  # Wait until the recording is finished
            self.progress_label.config(text="Second audio recording finished.", fg="blue")
            self.steps_listbox.insert(tk.END, "Second audio recorded.")
            self.root.update()
        
        threading.Thread(target=record).start()

    def analyze_similarity(self):
        if self.recorded_audio_1 is None or self.recorded_audio_2 is None:
            messagebox.showerror("Error", "Please record both audios first.")
            return

        self.progress_label.config(text="Analyzing similarity...", fg="orange")
        self.root.update()
        self.steps_listbox.insert(tk.END, "Starting similarity analysis...")

        # Convert recorded audios to 1D arrays (mono)
        recorded_audio_1_mono = np.squeeze(self.recorded_audio_1)
        recorded_audio_2_mono = np.squeeze(self.recorded_audio_2)
        self.steps_listbox.insert(tk.END, "Converted recordings to mono.")

        # Normalize the audio data to reduce volume-related differences
        recorded_audio_1_mono = normalize(recorded_audio_1_mono.reshape(1, -1)).flatten()
        recorded_audio_2_mono = normalize(recorded_audio_2_mono.reshape(1, -1)).flatten()
        self.steps_listbox.insert(tk.END, "Normalized audio data.")

        # Extract MFCC features
        mfcc_recorded_1 = librosa.feature.mfcc(y=recorded_audio_1_mono, sr=self.sample_rate, n_mfcc=13)
        mfcc_recorded_2 = librosa.feature.mfcc(y=recorded_audio_2_mono, sr=self.sample_rate, n_mfcc=13)
        self.steps_listbox.insert(tk.END, "Extracted MFCC features from both recordings.")

        # Calculate similarity using Dynamic Time Warping (DTW)
        dist, _, _, _ = accelerated_dtw(mfcc_recorded_1.T, mfcc_recorded_2.T, dist='euclidean')
        similarity_score = max(0, 100 - dist)  # Convert distance to similarity percentage
        self.steps_listbox.insert(tk.END, f"Calculated similarity using DTW: {similarity_score:.2f}%")
        messagebox.showinfo("Similarity Result", f"Similarity: {similarity_score:.2f}%")

        self.progress_label.config(text="Analysis complete.", fg="blue")
        self.root.update()

        # Plot MFCCs and similarity result
        self.plot_mfcc_and_similarity(mfcc_recorded_1, mfcc_recorded_2, similarity_score, recorded_audio_1_mono, recorded_audio_2_mono)

    def plot_mfcc_and_similarity(self, mfcc_recorded_1, mfcc_recorded_2, similarity_score, recorded_audio_1_mono, recorded_audio_2_mono):
        # Clear previous plots
        for widget in self.plot_frame.winfo_children():
            widget.pack_forget()

        fig, axs = plt.subplots(3, 1, figsize=(10, 12))

        axs[0].set_title("First Audio MFCC", fontsize=14)
        librosa.display.specshow(mfcc_recorded_1, sr=self.sample_rate, x_axis='time', cmap='viridis')
        axs[0].set_ylabel("MFCC Coefficients")
        axs[0].set_xlabel("Time [s]")

        axs[1].set_title("Second Audio MFCC", fontsize=14)
        librosa.display.specshow(mfcc_recorded_2, sr=self.sample_rate, x_axis='time', cmap='viridis')
        axs[1].set_ylabel("MFCC Coefficients")
        axs[1].set_xlabel("Time [s]")

        axs[2].set_title("Similarity Score", fontsize=14)
        time_axis = np.linspace(0, len(recorded_audio_1_mono) / self.sample_rate, len(recorded_audio_1_mono))
        axs[2].plot(time_axis, recorded_audio_1_mono, label='First Audio', color='blue', alpha=0.6)
        axs[2].plot(time_axis, recorded_audio_2_mono, label='Second Audio', color='green', alpha=0.6)
        axs[2].set_title('Similarity Analysis - Waveform Overlay', fontsize=14)
        axs[2].grid(True)
        axs[2].set_xlabel('Time [s]')
        axs[2].set_ylabel('Amplitude')
        axs[2].legend()
        axs[2].bar(['Similarity'], [similarity_score], color='green' if similarity_score >= 50 else 'orange')
        axs[2].set_ylabel("Percentage (%)")

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.steps_listbox.insert(tk.END, "MFCC graphs and similarity score plotted.")

    def clear_results(self):
        # Clear progress label
        self.progress_label.config(text="")
        # Clear plots
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        # Clear steps listbox
        self.steps_listbox.delete(0, tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceSimilarityApp(root)
    root.mainloop()