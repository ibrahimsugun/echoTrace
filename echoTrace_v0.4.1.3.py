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
from mpl_toolkits.mplot3d import Axes3D

# Ses hızı (m/s)
SOUND_SPEED = 343

class SoundSourceLocalization3D(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('3D Ses Kaynağı Simülasyonu')
        self.setGeometry(100, 100, 1500, 900)  # Daha geniş bir pencere boyutu

        # Mikrofonların başlangıç konumları (18 mikrofon, rastgele düzen)
        self.default_mic_positions = self.generate_random_mic_positions(num_mics=18)
        self.mic_positions = np.copy(self.default_mic_positions)
        self.source_point = None
        self.estimated_point = None
        self.calculation_steps = ""
        self.average_db = None  # Ortalama desibel değeri

        # Ambient Gürültü Kaynakları (3 Boyutlu)
        self.noise_sources = self.generate_multiple_noise_sources(count=2)

        # Grafik öğelerini saklamak için değişkenler
        self.mic_scatter = None
        self.mic_texts = []
        self.noise_scatter = []
        self.noise_texts = []
        self.source_scatter = None
        self.source_text = None
        self.estimated_scatter = None
        self.estimated_text = None

        # Ses kaynağından mikrofonlara çizilen çizgileri saklamak için liste
        self.source_to_mic_lines = []

        self.initUI()
        self.initial_plot()

    def initUI(self):
        # Ana widget ve layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        layout = QHBoxLayout(self.main_widget)

        # Grafik alanı
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, projection='3d')

        # Fare ile döndürme ayarları (sağ tık ile döndürme)
        self.ax.mouse_init(rotate_btn=3, zoom_btn=None)

        # Mouse event'leri
        self.canvas.mpl_connect('button_press_event', self.on_click)

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

        # "Rastgele Pozisyon" butonu - Mikrofon ve gürültü kaynaklarını rastgele pozisyonlar
        self.randomize_button = QPushButton('Rastgele Pozisyon')
        self.randomize_button.clicked.connect(self.randomize_positions)
        control_layout.addWidget(self.randomize_button)

        # "Rastgele Ses Kaynağı" butonu - Rastgele bir ses kaynağı ekler
        self.random_source_button = QPushButton('Rastgele Ses Kaynağı')
        self.random_source_button.clicked.connect(self.add_random_sound_source)
        control_layout.addWidget(self.random_source_button)

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

    def generate_random_mic_positions(self, num_mics=18):
        """
        Rastgele mikrofon konumları oluşturur (3D düzlem üzerinde).
        num_mics: Mikrofon sayısı
        """
        x_coords = np.random.uniform(-15, 25, num_mics)
        y_coords = np.random.uniform(-15, 25, num_mics)
        z_coords = np.random.uniform(-10, 10, num_mics)
        positions = np.column_stack((x_coords, y_coords, z_coords))
        return positions

    def generate_random_noise_source(self):
        """Rastgele bir konum ve desibel değeri ile ambient gürültü kaynağı oluşturur (3D)."""
        x = random.uniform(-15, 25)
        y = random.uniform(-15, 25)
        z = random.uniform(-10, 10)
        # Desibel değeri 60 dB ile 90 dB arasında rastgele seçilir
        db = random.uniform(60, 90)
        return {'position': np.array([x, y, z]), 'db': db}

    def generate_multiple_noise_sources(self, count=2):
        """Belirli sayıda rastgele ambient gürültü kaynağı oluşturur."""
        noise_sources = []
        for _ in range(count):
            noise_sources.append(self.generate_random_noise_source())
        return noise_sources

    def calculate_distance(self, mic_pos, source_pos):
        """Mikrofon ile ses kaynağı arasındaki mesafeyi hesaplar (3D)."""
        distance = np.sqrt((mic_pos[0] - source_pos[0]) ** 2 +
                           (mic_pos[1] - source_pos[1]) ** 2 +
                           (mic_pos[2] - source_pos[2]) ** 2)
        return max(distance, 1e-6)  # Sıfıra çok yakın değerlerde hata önleme

    def calculate_db(self, distance, source_db):
        """Verilen mesafeye ve kaynak desibeline göre desibel değerini hesaplar."""
        if distance <= 0:
            return source_db  # Maksimum desibel
        # Desibel azalması: dB = kaynak_dB - 20 * log10(r)
        db = source_db - 20 * math.log10(distance)
        return db

    def initial_plot(self):
        """Başlangıç grafiğini oluşturur ve öğelerin referanslarını saklar."""
        self.ax.set_title('3D Ses Kaynağı Simülasyonu')
        self.ax.set_xlabel('X Koordinatı')
        self.ax.set_ylabel('Y Koordinatı')
        self.ax.set_zlabel('Z Koordinatı')
        xlim = [-15, 25]
        ylim = [-15, 25]
        zlim = [-10, 10]
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)
        self.ax.set_zlim(zlim)

        # Grafiğin başlangıç görünümünü çaprazdan ayarla
        self.ax.view_init(elev=30, azim=-60)  # İstediğiniz açıları ayarlayabilirsiniz

        # Mikrofonlar ve etiketler
        self.mic_scatter = self.ax.scatter(
            self.mic_positions[:, 0], self.mic_positions[:, 1], self.mic_positions[:, 2],
            color='blue', label="Mikrofonlar", s=100
        )
        for i, pos in enumerate(self.mic_positions):
            text = self.ax.text(pos[0], pos[1], pos[2], f'M{i+1}', fontsize=8, ha='right', va='bottom')
            self.mic_texts.append(text)

        # Ambient Gürültü Kaynakları
        for idx, noise in enumerate(self.noise_sources, start=1):
            # Marker boyutunu dB seviyesine göre ayarla (60-90 dB arasında 50-150 büyüklük)
            marker_size = 50 + (noise['db'] - 60) * 2
            scatter = self.ax.scatter(
                noise['position'][0], noise['position'][1], noise['position'][2],
                color='orange',
                label=f"Ambient Gürültü {idx}" if idx == 1 else "",
                s=marker_size,
                marker='x'
            )
            self.noise_scatter.append(scatter)
            # Desibel seviyesini marker'ın yanında göster
            text = self.ax.text(
                noise['position'][0], noise['position'][1], noise['position'][2],
                f' {noise["db"]:.1f} dB', color='orange', fontsize=8,
                ha='left', va='center'
            )
            self.noise_texts.append(text)
            # Gürültü bilgilerini kontrol paneline ekle
            noise_info = QLabel(f"Gürültü {idx}: Konum=({noise['position'][0]:.2f}, {noise['position'][1]:.2f}, {noise['position'][2]:.2f}), dB={noise['db']:.2f}")
            self.noise_info_layout.addWidget(noise_info)

        # Gerçek Ses Kaynağı (Başlangıçta boş)
        self.source_scatter = self.ax.scatter([], [], [], color='red', label="Gerçek Ses Kaynağı", s=200)
        self.source_text = None  # Başlangıçta None

        # Tahmin Edilen Ses Kaynağı (Başlangıçta boş)
        self.estimated_scatter = self.ax.scatter([], [], [], color='green', label="Tahmin Edilen Ses Kaynağı", s=100)
        self.estimated_text = None  # Başlangıçta None

        self.ax.legend(loc='upper right', fontsize=8)
        self.canvas.draw()

    def on_click(self, event):
        """Sol tık ile herhangi bir işlem yapma."""
        if event.button == 1:  # Sol tık
            return  # Sol tıkta hiçbir işlem yapma

    def add_random_sound_source(self):
        """Rastgele bir ses kaynağı ekler."""
        x = random.uniform(-15, 25)
        y = random.uniform(-15, 25)
        z = random.uniform(-10, 10)  # Z koordinatı rastgele
        self.source_point = np.array([x, y, z])
        self.update_plot_elements()
        self.perform_localization()

    def perform_localization(self):
        """Ses kaynağının yerini tahmin eder."""
        if self.source_point is None:
            return

        # Gerçek kaynak ve gürültü kaynaklarından gelen toplam dB'yi hesapla
        source_points = [{'position': self.source_point, 'db': 100}]  # Kaynak dB değeri varsayılan 100 dB
        source_points.extend(self.noise_sources)
        measured_db = []
        self.calculation_steps = ""  # Hesaplama adımlarını sıfırla
        self.calculation_steps += "Mikrofonlarda Ölçülen dB Değerleri:\n"

        for idx_mic, mic in enumerate(self.mic_positions):
            total_power = 0
            self.calculation_steps += f"\nMikrofon {idx_mic + 1}:\n"
            for source in source_points:
                distance = self.calculate_distance(mic, source['position'])
                db = self.calculate_db(distance, source['db'])
                power = 10 ** (db / 10)
                total_power += power
                self.calculation_steps += f"  Kaynak ({source['position'][0]:.2f}, {source['position'][1]:.2f}, {source['position'][2]:.2f}), Mesafe: {distance:.2f} m, dB: {db:.2f}\n"
            total_db = 10 * math.log10(total_power) if total_power > 0 else 0
            measured_db.append(total_db)
            self.calculation_steps += f"  Toplam dB: {total_db:.2f}\n"
        self.average_db = np.mean(measured_db)
        self.calculation_steps += f"\nOrtalama dB: {self.average_db:.2f}\n"

        # Ses kaynağının yerini tahmin et
        def objective_function(pos):
            total_error = 0
            for i, mic in enumerate(self.mic_positions):
                distance = self.calculate_distance(mic, pos)
                db = self.calculate_db(distance, 100)  # Kaynak dB değeri varsayılan 100 dB
                power = 10 ** (db / 10)
                total_power = power
                for noise in self.noise_sources:
                    n_distance = self.calculate_distance(mic, noise['position'])
                    n_db = self.calculate_db(n_distance, noise['db'])
                    n_power = 10 ** (n_db / 10)
                    total_power += n_power
                total_db = 10 * math.log10(total_power) if total_power > 0 else 0
                error = (total_db - measured_db[i]) ** 2
                total_error += error
            return total_error

        x0 = np.array([0, 0, 0])
        res = minimize(objective_function, x0, method='BFGS')
        self.estimated_point = res.x
        self.calculation_steps += f"\nTahmin Edilen Konum: ({self.estimated_point[0]:.2f}, {self.estimated_point[1]:.2f}, {self.estimated_point[2]:.2f})\n"
        self.text_box.setPlainText(self.calculation_steps)
        self.update_plot_elements()

    def clear(self):
        """Ses kaynağı ve tahmin edilen noktaları siler."""
        self.source_point = None
        self.estimated_point = None
        self.calculation_steps = ""
        self.average_db = None
        self.text_box.setPlainText("")
        self.update_plot_elements()

    def reset_mic_positions(self):
        """Mikrofon konumlarını ve ambient gürültü kaynaklarını sıfırlar."""
        self.mic_positions = np.copy(self.default_mic_positions)
        self.noise_sources = self.generate_multiple_noise_sources(count=2)
        self.clear()
        self.update_plot_elements()

    def randomize_positions(self):
        """Mikrofon ve gürültü kaynaklarının pozisyonlarını rastgele olarak değiştirir."""
        self.mic_positions = self.generate_random_mic_positions(num_mics=18)
        self.noise_sources = self.generate_multiple_noise_sources(count=2)
        self.clear()
        self.update_plot_elements()

    def update_plot_elements(self):
        """Grafik öğelerini günceller (mikrofonlar, gürültü kaynakları, ses kaynakları)."""
        self.ax.clear()
        self.initial_plot()
        # Fare ile döndürme ayarları (sağ tık ile döndürme)
        self.ax.mouse_init(rotate_btn=3, zoom_btn=None)

        # Önceki ses kaynağı yazısını ve çizgileri kaldır
        if self.source_text is not None:
            self.source_text.remove()
            self.source_text = None

        # Ses kaynağından mikrofonlara çizilen çizgileri kaldır
        for line in self.source_to_mic_lines:
            line.remove()
        self.source_to_mic_lines = []

        # Gerçek Ses Kaynağı
        if self.source_point is not None:
            self.source_scatter._offsets3d = (self.source_point[0:1], self.source_point[1:2], self.source_point[2:3])
            x, y, z = self.source_point
            self.source_text = self.ax.text(x, y, z, f'({x:.2f}, {y:.2f}, {z:.2f})', color='red', fontsize=10, ha='left', va='center')

            # Ses kaynağından mikrofonlara çizgileri çiz
            for mic_pos in self.mic_positions:
                line, = self.ax.plot(
                    [self.source_point[0], mic_pos[0]],
                    [self.source_point[1], mic_pos[1]],
                    [self.source_point[2], mic_pos[2]],
                    color='orange',
                    linestyle='--',
                    linewidth=0.5
                )
                self.source_to_mic_lines.append(line)
        else:
            self.source_scatter._offsets3d = ([], [], [])

        # Önceki tahmin yazısını kaldır
        if self.estimated_text is not None:
            self.estimated_text.remove()
            self.estimated_text = None

        # Tahmin Edilen Ses Kaynağı
        if self.estimated_point is not None:
            self.estimated_scatter._offsets3d = (self.estimated_point[0:1], self.estimated_point[1:2], self.estimated_point[2:3])
            x, y, z = self.estimated_point
            self.estimated_text = self.ax.text(x, y, z, 'Tahmin', color='green', fontsize=8, ha='left', va='center')
        else:
            self.estimated_scatter._offsets3d = ([], [], [])

        self.canvas.draw_idle()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SoundSourceLocalization3D()
    ex.show()
    sys.exit(app.exec_())
