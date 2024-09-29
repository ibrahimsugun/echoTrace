import sys
import numpy as np
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QTextEdit, QLabel)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.optimize import minimize
from scipy import signal  # Sinyal işleme kütüphanesi

# Ses hızı
SOUND_SPEED = 343

class SoundSourceLocalization(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Ses Kaynağı Simülasyonu')
        self.setGeometry(100, 100, 1200, 800)

        # Mikrofonların başlangıç konumları
        self.default_mic_positions = np.array([
            [0, 0],    # Mikrofon 1
            [5, 0],    # Mikrofon 2
            [10, 0],   # Mikrofon 3
            [0, 5],    # Mikrofon 4
            [10, 5],   # Mikrofon 5
            [0, 10],   # Mikrofon 6
            [5, 10],   # Mikrofon 7
            [10, 10]   # Mikrofon 8
        ])
        self.mic_positions = np.copy(self.default_mic_positions)
        self.source_point = None
        self.estimated_point = None
        self.calculation_steps = ""
        self.picked_mic = None

        self.initUI()
        self.update_plot()

    def initUI(self):
        # Ana widget ve layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        layout = QHBoxLayout(self.main_widget)

        # Grafik alanı
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('pick_event', self.on_pick)

        # Sağ taraftaki kontrol paneli
        control_layout = QVBoxLayout()
        
        # "Sil" butonu
        self.clear_button = QPushButton('Sil')
        self.clear_button.clicked.connect(self.clear)
        control_layout.addWidget(self.clear_button)
        
        # "Sıfırla" butonu - Mikrofon konumlarını sıfırlar
        self.reset_button = QPushButton('Sıfırla')
        self.reset_button.clicked.connect(self.reset_mic_positions)
        control_layout.addWidget(self.reset_button)

        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        control_layout.addWidget(QLabel("Hesaplama Adımları:"))
        control_layout.addWidget(self.text_box)

        # Layoutları yerleştirme
        layout.addWidget(self.canvas, 70)
        layout.addLayout(control_layout, 30)

    def calculate_distance(self, mic_pos, source_pos):
        """Mikrofon ile ses kaynağı arasındaki mesafeyi hesaplar."""
        distance = np.sqrt((mic_pos[0] - source_pos[0]) ** 2 + (mic_pos[1] - source_pos[1]) ** 2)
        return max(distance, 1e-6)  # Sıfıra çok yakın değerlerde hata önleme

    def apply_low_pass_filter(self, signal_data):
        """Low-pass filter uygula ve yüksek frekanslı gürültüyü temizle."""
        nyquist = 0.5 * 44100  # Nyquist frekansı (Örnekleme frekansı)
        cutoff = 1000  # 1kHz altında gürültüyü filtrele
        normal_cutoff = cutoff / nyquist
        
        # Low-pass Butterworth filtre parametreleri
        b, a = signal.butter(5, normal_cutoff, btype='low', analog=False)
        filtered_signal = signal.filtfilt(b, a, signal_data)
        
        return filtered_signal

    def tdoa_loss(self, source_pos, mic_positions, time_stamps):
        """Tüm mikrofon çiftleri arasındaki zaman farklarını kullanan kayıp fonksiyonu."""
        total_loss = 0.0
        steps = []
        num_mics = len(mic_positions)
        for i in range(num_mics):
            for j in range(i + 1, num_mics):
                observed_delta_d = (time_stamps[i] - time_stamps[j]) * SOUND_SPEED
                dist_i = self.calculate_distance(mic_positions[i], source_pos)
                dist_j = self.calculate_distance(mic_positions[j], source_pos)
                predicted_delta_d = dist_i - dist_j
                residual = observed_delta_d - predicted_delta_d
                total_loss += residual ** 2

                step_info = (
                    f"Çift ({i+1}, {j+1}):\n"
                    f"  Zaman Farkı (t{i+1} - t{j+1}): {time_stamps[i] - time_stamps[j]:.6e} s\n"
                    f"  Gerçek Mesafe Farkı (d{i+1} - d{j+1}): {observed_delta_d:.6f} m\n"
                    f"  Tahmini Mesafe Farkı: {predicted_delta_d:.6f} m\n"
                    f"  Kalan (Residual): {residual:.6f}\n"
                )
                steps.append(step_info)

        self.calculation_steps = "\n".join(steps)
        return total_loss

    def find_sound_source(self, mic_positions, time_stamps):
        """Ses kaynağının konumunu optimize eder."""
        initial_guess = np.mean(mic_positions, axis=0)
        result = minimize(self.tdoa_loss, initial_guess, args=(mic_positions, time_stamps), method='Nelder-Mead')
        return result.x

    def on_click(self, event):
        if event.inaxes == self.ax:
            if event.button == 1:
                self.source_point = [event.xdata, event.ydata]
                
                # Mikrofonlardan gelen verileri simüle edelim (örneğin rastgele gürültü ekleyelim)
                raw_signals = np.array([self.calculate_distance(mic, self.source_point) / SOUND_SPEED for mic in self.mic_positions])
                
                # Gürültü içeren verilerden low-pass filter ile temizlenen sinyal
                filtered_signals = self.apply_low_pass_filter(raw_signals)
                
                # TDOA hesaplamalarını temizlenmiş sinyallerle yap
                self.estimated_point = self.find_sound_source(self.mic_positions, filtered_signals)
                
                self.update_plot()
                self.text_box.setPlainText(
                    f"Gerçek Ses Kaynağı: ({self.source_point[0]:.2f}, {self.source_point[1]:.2f})\n"
                    f"Tahmin Edilen Konum: ({self.estimated_point[0]:.2f}, {self.estimated_point[1]:.2f})\n\n"
                    f"Hesaplama Adımları:\n{self.calculation_steps}"
                )
        else:
            self.calculation_steps = ""
            self.text_box.setPlainText("")

    def on_pick(self, event):
        if event.mouseevent.button == 3 and event.ind is not None:
            self.picked_mic = event.ind[0]

    def on_motion(self, event):
        if self.picked_mic is not None and event.inaxes == self.ax:
            self.mic_positions[self.picked_mic] = [event.xdata, event.ydata]
            self.update_plot()

    def on_release(self, event):
        if self.picked_mic is not None and self.source_point is not None:
            time_stamps = np.array([self.calculate_distance(mic, self.source_point) / SOUND_SPEED for mic in self.mic_positions])
            self.estimated_point = self.find_sound_source(self.mic_positions, time_stamps)
            self.update_plot()
            self.text_box.setPlainText(
                f"Gerçek Ses Kaynağı: ({self.source_point[0]:.2f}, {self.source_point[1]:.2f})\n"
                f"Tahmin Edilen Konum: ({self.estimated_point[0]:.2f}, {self.estimated_point[1]:.2f})\n\n"
                f"Hesaplama Adımları:\n{self.calculation_steps}"
            )
        self.picked_mic = None

    def update_plot(self):
        self.ax.clear()
        self.ax.set_title('Ses Kaynağı Simülasyonu')
        self.ax.set_xlabel('X Koordinatı')
        self.ax.set_ylabel('Y Koordinatı')
        xlim = [-10, 20]
        ylim = [-10, 20]
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)
        self.ax.set_xticks(np.arange(-10, 21, 5))
        self.ax.set_yticks(np.arange(-10, 21, 5))
        self.ax.grid(True)

        scatter = self.ax.scatter(self.mic_positions[:, 0], self.mic_positions[:, 1], color='blue', label="Mikrofonlar", picker=True, s=100)
        for i, pos in enumerate(self.mic_positions):
            self.ax.text(pos[0], pos[1], f'M{i+1}', fontsize=12, ha='right', va='bottom')

        if self.source_point is not None:
            self.ax.scatter(*self.source_point, color='red', label="Gerçek Ses Kaynağı", s=200)
        if self.estimated_point is not None:
            self.ax.scatter(*self.estimated_point, color='green', label="Tahmin Edilen Ses Kaynağı", s=100)
        self.ax.legend()
        self.canvas.draw()

    def clear(self):
        """Ses kaynağı ve tahmin edilen noktaları siler."""
        self.source_point = None
        self.estimated_point = None
        self.calculation_steps = ""
        self.text_box.setPlainText("")
        self.update_plot()

    def reset_mic_positions(self):
        """Mikrofon konumlarını varsayılan pozisyonlarına sıfırlar."""
        self.mic_positions = np.copy(self.default_mic_positions)
        self.clear()  # Ses kaynağı ve tahminleri de sıfırlar

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SoundSourceLocalization()
    ex.show()
    sys.exit(app.exec_())
