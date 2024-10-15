import sys
import numpy as np
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QTextEdit, QLabel, QScrollArea
)
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

        # Ambient Gürültü Kaynakları (Çoklu)
        self.noise_sources = self.generate_multiple_noise_sources()

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
        
        # "Sıfırla" butonu - Mikrofon konumlarını ve ambient gürültü kaynaklarını sıfırlar
        self.reset_button = QPushButton('Sıfırla')
        self.reset_button.clicked.connect(self.reset_mic_positions)
        control_layout.addWidget(self.reset_button)

        # Hesaplama Adımları
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        control_layout.addWidget(QLabel("Hesaplama Adımları:"))
        control_layout.addWidget(self.text_box)

        # Ambient Gürültü Bilgisi (Scroll Area ile)
        control_layout.addWidget(QLabel("Ambient Gürültü Bilgisi:"))
        self.noise_info_scroll = QScrollArea()
        self.noise_info_widget = QWidget()
        self.noise_info_layout = QVBoxLayout(self.noise_info_widget)
        self.noise_info_scroll.setWidget(self.noise_info_widget)
        self.noise_info_scroll.setWidgetResizable(True)
        control_layout.addWidget(self.noise_info_scroll)

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

    def generate_multiple_noise_sources(self, count=None):
        """Belirli sayıda rastgele ambient gürültü kaynağı oluşturur. Sayı belirtilmezse 1-3 arasında rastgele seçilir."""
        if count is None:
            count = random.randint(1, 3)  # 1 ila 3 arasında rastgele sayıda gürültü kaynağı
        noise_sources = []
        for _ in range(count):
            noise_sources.append(self.generate_random_noise_source())
        return noise_sources

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

    def compute_noise_power_per_mic(self):
        """
        Her mikrofon için ambient gürültü kaynaklarından gelen toplam gürültü gücünü hesaplar.
        """
        noise_powers = []
        for mic in self.mic_positions:
            total_noise_power = 0
            for noise in self.noise_sources:
                distance = self.calculate_distance(mic, noise['position'])
                db = self.calculate_db(distance, noise['db'])
                power = 10 ** (db / 10)
                total_noise_power += power
            noise_powers.append(total_noise_power)
        return np.array(noise_powers)

    def compute_weights(self, noise_powers):
        """
        Gürültü gücüne bağlı olarak her mikrofon için ağırlıkları hesaplar.
        Daha az gürültüye sahip mikrofonlara daha yüksek ağırlık verilir.
        """
        # Önce tüm gürültü güçlerinin bir araya getirilmiş ortalamasını alın
        avg_noise_power = np.mean(noise_powers)
        # Ağırlıkları, ortalamadan ters oranda belirleyin
        weights = avg_noise_power / (noise_powers + 1e-6)  # 1e-6 ile sıfıra bölünmeyi önleyin
        return weights

    def tdoa_loss(self, source_pos, mic_positions, time_stamps, weights):
        """Ağırlıklı TDOA kayıp fonksiyonu."""
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
                weighted_residual = weights[i] * weights[j] * residual ** 2
                total_loss += weighted_residual

                step_info = (
                    f"Çift ({i+1}, {j+1}):\n"
                    f"  Zaman Farkı (t{i+1} - t{j+1}): {time_stamps[i] - time_stamps[j]:.6e} s\n"
                    f"  Gerçek Mesafe Farkı (d{i+1} - d{j+1}): {observed_delta_d:.6f} m\n"
                    f"  Tahmini Mesafe Farkı: {predicted_delta_d:.6f} m\n"
                    f"  Kalan (Residual): {residual:.6f}\n"
                    f"  Ağırlıklı Residual: {weighted_residual:.6f}\n"
                )
                steps.append(step_info)

        self.calculation_steps = "\n".join(steps)
        return total_loss

    def find_sound_source(self, mic_positions, time_stamps, weights):
        """Ses kaynağının konumunu optimize eder."""
        initial_guess = np.mean(mic_positions, axis=0)
        result = minimize(
            self.tdoa_loss,
            initial_guess,
            args=(mic_positions, time_stamps, weights),
            method='Nelder-Mead'
        )
        return result.x

    def on_click(self, event):
        if event.inaxes == self.ax:
            if event.button == 1:
                self.source_point = np.array([event.xdata, event.ydata])
                
                # Tüm kaynaklar: Ana kaynak ve ambient gürültü
                sources = [{'position': self.source_point, 'db': 100}]  # Ana kaynakın varsayılan dB değeri
                sources.extend(self.noise_sources)  # Tüm ambient gürültü kaynakları

                # Gürültü güçlerini hesapla
                noise_powers = self.compute_noise_power_per_mic()

                # Ağırlıkları hesapla
                weights = self.compute_weights(noise_powers)

                # Her mikrofon için zaman damgalarını hesapla (ölçüm gürültüsü ekleyerek)
                time_stamps = []
                for mic in self.mic_positions:
                    # Ana kaynağın zaman damgası
                    dist_main = self.calculate_distance(mic, self.source_point)
                    t_main = dist_main / SOUND_SPEED

                    # Gürültü kaynaklarının etkisiyle ölçüm gürültüsü
                    # Ölçüm gürültüsünü, toplam gürültü gücüne bağlı olarak belirleyin
                    # Daha yüksek gürültü gücüne sahip mikrofonlar için daha büyük standart sapma
                    noise_std = 1e-4 * math.log10(noise_powers[np.where(self.mic_positions == mic)[0][0]] + 1e-6)
                    t_noise = np.random.normal(0, noise_std)

                    # Gürültülü zaman damgası
                    t_total = t_main + t_noise
                    time_stamps.append(t_total)
                time_stamps = np.array(time_stamps)

                self.estimated_point = self.find_sound_source(self.mic_positions, time_stamps, weights)
                
                # Ortalama desibel hesaplama
                self.average_db = self.compute_total_db_per_mic(sources)
                
                self.update_plot()
                self.update_noise_info_labels()
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
            sources.extend(self.noise_sources)  # Tüm ambient gürültü kaynakları

            # Gürültü güçlerini hesapla
            noise_powers = self.compute_noise_power_per_mic()

            # Ağırlıkları hesapla
            weights = self.compute_weights(noise_powers)

            # Her mikrofon için zaman damgalarını hesapla (ölçüm gürültüsü ekleyerek)
            time_stamps = []
            for mic in self.mic_positions:
                # Ana kaynağın zaman damgası
                dist_main = self.calculate_distance(mic, self.source_point)
                t_main = dist_main / SOUND_SPEED

                # Gürültü kaynaklarının etkisiyle ölçüm gürültüsü
                # Ölçüm gürültüsünü, toplam gürültü gücüne bağlı olarak belirleyin
                # Daha yüksek gürültü gücüne sahip mikrofonlar için daha büyük standart sapma
                noise_std = 1e-4 * math.log10(noise_powers[np.where(self.mic_positions == mic)[0][0]] + 1e-6)
                t_noise = np.random.normal(0, noise_std)

                # Gürültülü zaman damgası
                t_total = t_main + t_noise
                time_stamps.append(t_total)
            time_stamps = np.array(time_stamps)

            self.estimated_point = self.find_sound_source(self.mic_positions, time_stamps, weights)
            
            # Ortalama desibel yeniden hesaplama (mikrofon konumları değiştiği için)
            self.average_db = self.compute_total_db_per_mic(sources)
            
            self.update_plot()
            self.update_noise_info_labels()
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
        scatter = self.ax.scatter(
            self.mic_positions[:, 0], self.mic_positions[:, 1],
            color='blue', label="Mikrofonlar", picker=True, s=100
        )
        for i, pos in enumerate(self.mic_positions):
            self.ax.text(pos[0], pos[1], f'M{i+1}', fontsize=12, ha='right', va='bottom')

        # Gerçek Ses Kaynağı
        if self.source_point is not None:
            self.ax.scatter(*self.source_point, color='red', label="Gerçek Ses Kaynağı", s=200)
            # Ortalama desibel bilgisini ses kaynağı noktasının yanında gösterme
            self.ax.text(
                self.source_point[0], self.source_point[1],
                f'  {100:.2f} dB', color='red', fontsize=12, ha='left', va='center'
            )
            # Mikrofonlar ile ses kaynağı arasındaki çizgileri çiz
            for mic_pos in self.mic_positions:
                self.ax.plot(
                    [mic_pos[0], self.source_point[0]],
                    [mic_pos[1], self.source_point[1]],
                    'r--', alpha=0.5
                )

        # Ambient Gürültü Kaynakları
        if self.noise_sources:
            for idx, noise in enumerate(self.noise_sources, start=1):
                # Marker boyutunu dB seviyesine göre ayarla (örneğin, 60-90 dB arasında 50-150 büyüklük)
                marker_size = 50 + (noise['db'] - 60) * 2
                self.ax.scatter(
                    *noise['position'],
                    color='orange',
                    label=f"Ambient Gürültü {idx}" if idx ==1 else "",
                    s=marker_size,
                    marker='x'
                )
                # Desibel seviyesini marker'ın yanında göster
                self.ax.text(
                    noise['position'][0], noise['position'][1],
                    f' {noise["db"]:.1f} dB', color='orange', fontsize=10,
                    ha='left', va='center'
                )
                # Mikrofonlar ile ambient gürültü arasındaki çizgileri çiz
                for mic_pos in self.mic_positions:
                    self.ax.plot(
                        [mic_pos[0], noise['position'][0]],
                        [mic_pos[1], noise['position'][1]],
                        color='orange', linestyle='--', alpha=0.3
                    )

        # Tahmin Edilen Ses Kaynağı
        if self.estimated_point is not None:
            self.ax.scatter(*self.estimated_point, color='green', label="Tahmin Edilen Ses Kaynağı", s=100)
            # Mikrofonlar ile tahmin edilen ses kaynağı arasındaki çizgileri çiz
            for mic_pos in self.mic_positions:
                self.ax.plot(
                    [mic_pos[0], self.estimated_point[0]],
                    [mic_pos[1], self.estimated_point[1]],
                    'g--', alpha=0.5
                )

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
        """Mikrofon konumlarını varsayılan pozisyonlarına sıfırlar ve ambient gürültü kaynaklarını yeniler."""
        self.mic_positions = np.copy(self.default_mic_positions)
        self.noise_sources = self.generate_multiple_noise_sources()
        self.update_noise_info_labels()
        self.clear()  # Ses kaynağı ve tahminleri de sıfırlar

    def update_noise_info_labels(self):
        """Kontrol panelindeki ambient gürültü bilgilerini günceller."""
        # Eski etiketleri temizle
        while self.noise_info_layout.count():
            child = self.noise_info_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Yeni etiketleri ekle
        for idx, noise in enumerate(self.noise_sources, start=1):
            label = QLabel(
                f"Ambient Gürültü {idx}:\n"
                f"  Pozisyon: ({noise['position'][0]:.2f}, {noise['position'][1]:.2f})\n"
                f"  Desibel: {noise['db']:.2f} dB"
            )
            self.noise_info_layout.addWidget(label)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SoundSourceLocalization()
    ex.show()
    sys.exit(app.exec_())
