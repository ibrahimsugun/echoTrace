import sys
import numpy as np
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QTextEdit, QLabel)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.optimize import minimize
import math
import random

# Ses hızı (m/s)
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
        self.average_db = None  # Ortalama desibel değeri

        # Ambient Gürültü Kaynağı
        self.noise_source = self.generate_random_noise_source()

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

        # Ambient Gürültü Bilgisi
        self.noise_info_label = QLabel("")
        control_layout.addWidget(QLabel("Ambient Gürültü Bilgisi:"))
        control_layout.addWidget(self.noise_info_label)

        # Layoutları yerleştirme
        layout.addWidget(self.canvas, 70)
        layout.addLayout(control_layout, 30)

    def generate_random_noise_source(self):
        """Rastgele bir konum ve desibel değeri ile ambient gürültü kaynağı oluşturur."""
        x = random.uniform(-10, 20)
        y = random.uniform(-10, 20)
        # Desibel değeri 60 dB ile 90 dB arasında rastgele seçilir
        db = random.uniform(60, 90)
        return {'position': np.array([x, y]), 'db': db}

    def calculate_distance(self, mic_pos, source_pos):
        """Mikrofon ile ses kaynağı arasındaki mesafeyi hesaplar."""
        distance = np.sqrt((mic_pos[0] - source_pos[0]) ** 2 + (mic_pos[1] - source_pos[1]) ** 2)
        return max(distance, 1e-6)  # Sıfıra çok yakın değerlerde hata önleme

    def calculate_db(self, distance, source_db):
        """Verilen mesafeye ve kaynak desibeline göre desibel değerini hesaplar."""
        if distance <= 0:
            return source_db  # Maksimum desibel
        # Desibel azalması: dB = kaynak_dB - 20 * log10(r)
        db = source_db - 20 * math.log10(distance)
        return db

    def compute_total_db_per_mic(self, source_points):
        """
        Her mikrofon için tüm kaynaklardan gelen desibel değerlerini logaritmik olarak birleştirir.
        source_points: List of dictionaries with 'position' and 'db' keys.
        """
        total_db_per_mic = []
        for mic in self.mic_positions:
            total_power = 0
            for source in source_points:
                distance = self.calculate_distance(mic, source['position'])
                db = self.calculate_db(distance, source['db'])
                power = 10 ** (db / 10)
                total_power += power
            total_db = 10 * math.log10(total_power) if total_power > 0 else 0
            total_db_per_mic.append(total_db)
        average_db = np.mean(total_db_per_mic) if total_db_per_mic else 0
        return average_db

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
                self.source_point = np.array([event.xdata, event.ydata])
                
                # Tüm kaynaklar: Ana kaynak ve ambient gürültü
                sources = [{'position': self.source_point, 'db': 100}]  # Ana kaynakın varsayılan dB değeri
                sources.append(self.noise_source)  # Ambient gürültü kaynağı

                # Her mikrofon için zaman damgalarını hesapla
                time_stamps = []
                for mic in self.mic_positions:
                    # Ana kaynağın zaman damgası
                    dist_main = self.calculate_distance(mic, self.source_point)
                    t_main = dist_main / SOUND_SPEED
                    # Gürültü kaynağının zaman damgası
                    dist_noise = self.calculate_distance(mic, self.noise_source['position'])
                    t_noise = dist_noise / SOUND_SPEED
                    # Toplam zaman damgası (basitçe ortalama alınmıştır; gerçek uygulamalarda daha karmaşık olabilir)
                    t_total = (t_main + t_noise) / 2
                    time_stamps.append(t_total)
                time_stamps = np.array(time_stamps)

                self.estimated_point = self.find_sound_source(self.mic_positions, time_stamps)
                
                # Ortalama desibel hesaplama
                self.average_db = self.compute_total_db_per_mic([{'position': self.source_point, 'db': 100}, self.noise_source])
                
                self.update_plot()
                self.text_box.setPlainText(
                    f"Gerçek Ses Kaynağı: ({self.source_point[0]:.2f}, {self.source_point[1]:.2f})\n"
                    f"Tahmin Edilen Konum: ({self.estimated_point[0]:.2f}, {self.estimated_point[1]:.2f})\n"
                    f"Ortalama Desibel: {self.average_db:.2f} dB\n\n"
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
            # Tüm kaynaklar: Ana kaynak ve ambient gürültü
            sources = [{'position': self.source_point, 'db': 100}]  # Ana kaynakın varsayılan dB değeri
            sources.append(self.noise_source)  # Ambient gürültü kaynağı

            # Her mikrofon için zaman damgalarını hesapla
            time_stamps = []
            for mic in self.mic_positions:
                # Ana kaynağın zaman damgası
                dist_main = self.calculate_distance(mic, self.source_point)
                t_main = dist_main / SOUND_SPEED
                # Gürültü kaynağının zaman damgası
                dist_noise = self.calculate_distance(mic, self.noise_source['position'])
                t_noise = dist_noise / SOUND_SPEED
                # Toplam zaman damgası (basitçe ortalama alınmıştır; gerçek uygulamalarda daha karmaşık olabilir)
                t_total = (t_main + t_noise) / 2
                time_stamps.append(t_total)
            time_stamps = np.array(time_stamps)

            self.estimated_point = self.find_sound_source(self.mic_positions, time_stamps)
            
            # Ortalama desibel yeniden hesaplama (mikrofon konumları değiştiği için)
            self.average_db = self.compute_total_db_per_mic([{'position': self.source_point, 'db': 100}, self.noise_source])
            
            self.update_plot()
            self.text_box.setPlainText(
                f"Gerçek Ses Kaynağı: ({self.source_point[0]:.2f}, {self.source_point[1]:.2f})\n"
                f"Tahmin Edilen Konum: ({self.estimated_point[0]:.2f}, {self.estimated_point[1]:.2f})\n"
                f"Ortalama Desibel: {self.average_db:.2f} dB\n\n"
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

        # Mikrofonlar ve ses kaynağı arasındaki mesafeleri görselleştirme
        scatter = self.ax.scatter(self.mic_positions[:, 0], self.mic_positions[:, 1], color='blue', label="Mikrofonlar", picker=True, s=100)
        for i, pos in enumerate(self.mic_positions):
            self.ax.text(pos[0], pos[1], f'M{i+1}', fontsize=12, ha='right', va='bottom')

        # Gerçek Ses Kaynağı
        if self.source_point is not None:
            self.ax.scatter(*self.source_point, color='red', label="Gerçek Ses Kaynağı", s=200)
            # Ortalama desibel bilgisini ses kaynağı noktasının yanında gösterme
            self.ax.text(self.source_point[0], self.source_point[1], f'  {100:.2f} dB', color='red', fontsize=12, ha='left', va='center')
            # Mikrofonlar ile ses kaynağı arasındaki çizgileri çiz
            for mic_pos in self.mic_positions:
                self.ax.plot([mic_pos[0], self.source_point[0]], [mic_pos[1], self.source_point[1]], 'r--', alpha=0.5)

        # Ambient Gürültü Kaynağı
        if self.noise_source is not None:
            self.ax.scatter(*self.noise_source['position'], color='orange', label="Ambient Gürültü", s=150, marker='x')
            # Ambient gürültü bilgisi
            self.noise_info_label.setText(
                f"Pozisyon: ({self.noise_source['position'][0]:.2f}, {self.noise_source['position'][1]:.2f})\n"
                f"Desibel: {self.noise_source['db']:.2f} dB"
            )
            # Mikrofonlar ile ambient gürültü arasındaki çizgileri çiz
            for mic_pos in self.mic_positions:
                self.ax.plot([mic_pos[0], self.noise_source['position'][0]], [mic_pos[1], self.noise_source['position'][1]], 'orange', linestyle='--', alpha=0.3)

        # Tahmin Edilen Ses Kaynağı
        if self.estimated_point is not None:
            self.ax.scatter(*self.estimated_point, color='green', label="Tahmin Edilen Ses Kaynağı", s=100)
            # Mikrofonlar ile tahmin edilen ses kaynağı arasındaki çizgileri çiz
            for mic_pos in self.mic_positions:
                self.ax.plot([mic_pos[0], self.estimated_point[0]], [mic_pos[1], self.estimated_point[1]], 'g--', alpha=0.5)

        self.ax.legend()
        self.canvas.draw()

    def clear(self):
        """Ses kaynağı ve tahmin edilen noktaları siler."""
        self.source_point = None
        self.estimated_point = None
        self.calculation_steps = ""
        self.average_db = None
        self.text_box.setPlainText("")
        self.update_plot()

    def reset_mic_positions(self):
        """Mikrofon konumlarını varsayılan pozisyonlarına sıfırlar ve ambient gürültüyü yeniler."""
        self.mic_positions = np.copy(self.default_mic_positions)
        self.noise_source = self.generate_random_noise_source()
        self.noise_info_label.setText(
            f"Pozisyon: ({self.noise_source['position'][0]:.2f}, {self.noise_source['position'][1]:.2f})\n"
            f"Desibel: {self.noise_source['db']:.2f} dB"
        )
        self.clear()  # Ses kaynağı ve tahminleri de sıfırlar

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SoundSourceLocalization()
    ex.show()
    sys.exit(app.exec_())
