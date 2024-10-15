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
        self.setGeometry(100, 100, 1500, 900)  # Daha geniş bir pencere boyutu

        # Mikrofonların başlangıç konumları (18 mikrofon, dairesel düzen)
        self.default_mic_positions = self.generate_circular_mic_positions(num_mics=18, radius=10)
        self.mic_positions = np.copy(self.default_mic_positions)
        self.source_point = None
        self.estimated_point = None
        self.calculation_steps = ""
        self.picked_mic = None
        self.average_db = None  # Ortalama desibel değeri

        # Ambient Gürültü Kaynakları (Çoklu)
        self.noise_sources = self.generate_multiple_noise_sources()

        # Grafik öğelerini saklamak için değişkenler
        self.mic_scatter = None
        self.mic_texts = []
        self.noise_scatter = []
        self.noise_texts = []
        self.source_scatter = None
        self.source_text = None
        self.estimated_scatter = None
        self.estimated_text = None
        self.lines_main = []
        self.lines_noise = []
        self.lines_estimated = []

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

    def generate_circular_mic_positions(self, num_mics=18, radius=10):
        """
        Dairesel düzenle mikrofon konumları oluşturur.
        num_mics: Mikrofon sayısı
        radius: Dairenin yarıçapı
        """
        angles = np.linspace(0, 2 * np.pi, num=num_mics, endpoint=False)
        positions = np.array([[radius * np.cos(angle), radius * np.sin(angle)] for angle in angles])
        return positions

    def generate_random_noise_source(self):
        """Rastgele bir konum ve desibel değeri ile ambient gürültü kaynağı oluşturur."""
        x = random.uniform(-15, 25)
        y = random.uniform(-15, 25)
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

    def initial_plot(self):
        """Başlangıç grafiğini oluşturur ve öğelerin referanslarını saklar."""
        self.ax.set_title('Ses Kaynağı Simülasyonu')
        self.ax.set_xlabel('X Koordinatı')
        self.ax.set_ylabel('Y Koordinatı')
        xlim = [-15, 25]
        ylim = [-15, 25]
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)
        self.ax.set_xticks(np.arange(-15, 26, 5))
        self.ax.set_yticks(np.arange(-15, 26, 5))
        self.ax.grid(True)

        # Mikrofonlar ve etiketler
        self.mic_scatter = self.ax.scatter(
            self.mic_positions[:, 0], self.mic_positions[:, 1],
            color='blue', label="Mikrofonlar", picker=True, s=100
        )
        for i, pos in enumerate(self.mic_positions):
            text = self.ax.text(pos[0], pos[1], f'M{i+1}', fontsize=8, ha='right', va='bottom')
            self.mic_texts.append(text)

        # Ambient Gürültü Kaynakları
        for idx, noise in enumerate(self.noise_sources, start=1):
            # Marker boyutunu dB seviyesine göre ayarla (örneğin, 60-90 dB arasında 50-150 büyüklük)
            marker_size = 50 + (noise['db'] - 60) * 2
            scatter = self.ax.scatter(
                noise['position'][0], noise['position'][1],
                color='orange',
                label=f"Ambient Gürültü {idx}" if idx ==1 else "",
                s=marker_size,
                marker='x'
            )
            self.noise_scatter.append(scatter)
            # Desibel seviyesini marker'ın yanında göster
            text = self.ax.text(
                noise['position'][0], noise['position'][1],
                f' {noise["db"]:.1f} dB', color='orange', fontsize=8,
                ha='left', va='center'
            )
            self.noise_texts.append(text)

        # Gerçek Ses Kaynağı (Başlangıçta boş)
        self.source_scatter = self.ax.scatter([], [], color='red', label="Gerçek Ses Kaynağı", s=200)
        self.source_text = self.ax.text(0, 0, '', color='red', fontsize=10, ha='left', va='center')

        # Tahmin Edilen Ses Kaynağı (Başlangıçta boş)
        self.estimated_scatter = self.ax.scatter([], [], color='green', label="Tahmin Edilen Ses Kaynağı", s=100)
        self.estimated_text = self.ax.text(0, 0, '', color='green', fontsize=8, ha='left', va='center')

        self.ax.legend(loc='upper right', fontsize=8)
        self.canvas.draw()

    def update_plot_elements(self):
        """Grafik öğelerini günceller (mikrofonlar, gürültü kaynakları, ses kaynakları)."""
        # Güncellenmiş mikrofon scatter
        self.mic_scatter.set_offsets(self.mic_positions)

        # Mikrofon etiketlerini güncelle
        for i, pos in enumerate(self.mic_positions):
            self.mic_texts[i].set_position((pos[0], pos[1]))

        # Ambient Gürültü Kaynakları
        for idx, noise in enumerate(self.noise_sources):
            # Güncellenmiş pozisyon
            self.noise_scatter[idx].set_offsets(noise['position'])
            # Marker boyutunu dB seviyesine göre ayarla
            marker_size = 50 + (noise['db'] - 60) * 2
            self.noise_scatter[idx].set_sizes([marker_size])
            # Desibel etiketi
            self.noise_texts[idx].set_position((noise['position'][0], noise['position'][1]))
            self.noise_texts[idx].set_text(f' {noise["db"]:.1f} dB')

        # Gerçek Ses Kaynağı
        if self.source_point is not None:
            self.source_scatter.set_offsets(self.source_point)
            self.source_text.set_position((self.source_point[0], self.source_point[1]))
            self.source_text.set_text(f'  {100:.2f} dB')  # Varsayılan dB değeri, gerekirse güncellenebilir
        else:
            self.source_scatter.set_offsets(np.empty((0, 2)))  # Düzeltme yapıldı
            self.source_text.set_text('')

        # Tahmin Edilen Ses Kaynağı
        if self.estimated_point is not None:
            self.estimated_scatter.set_offsets(self.estimated_point)
            self.estimated_text.set_position((self.estimated_point[0], self.estimated_point[1]))
            self.estimated_text.set_text('')
        else:
            self.estimated_scatter.set_offsets(np.empty((0, 2)))  # Düzeltme yapıldı
            self.estimated_text.set_text('')

        # Çizgileri güncelle
        # Önce eski çizgileri temizle
        for line in self.lines_main + self.lines_noise + self.lines_estimated:
            line.remove()
        self.lines_main = []
        self.lines_noise = []
        self.lines_estimated = []

        # Gerçek Ses Kaynağı Çizgileri
        if self.source_point is not None:
            for mic_pos in self.mic_positions:
                line, = self.ax.plot(
                    [mic_pos[0], self.source_point[0]],
                    [mic_pos[1], self.source_point[1]],
                    'r--', alpha=0.3
                )
                self.lines_main.append(line)

        # Ambient Gürültü Kaynakları Çizgileri
        for noise in self.noise_sources:
            for mic_pos in self.mic_positions:
                line, = self.ax.plot(
                    [mic_pos[0], noise['position'][0]],
                    [mic_pos[1], noise['position'][1]],
                    color='orange', linestyle='--', alpha=0.2
                )
                self.lines_noise.append(line)

        # Tahmin Edilen Ses Kaynağı Çizgileri
        if self.estimated_point is not None:
            for mic_pos in self.mic_positions:
                line, = self.ax.plot(
                    [mic_pos[0], self.estimated_point[0]],
                    [mic_pos[1], self.estimated_point[1]],
                    'g--', alpha=0.3
                )
                self.lines_estimated.append(line)

        self.canvas.draw_idle()

    def clear(self):
        """Ses kaynağı ve tahmin edilen noktaları siler."""
        self.source_point = None
        self.estimated_point = None
        self.calculation_steps = ""
        self.average_db = None
        self.text_box.setPlainText("")
        self.update_plot_elements()

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
                for idx, mic in enumerate(self.mic_positions):
                    # Ana kaynağın zaman damgası
                    dist_main = self.calculate_distance(mic, self.source_point)
                    t_main = dist_main / SOUND_SPEED

                    # Gürültü kaynaklarının etkisiyle ölçüm gürültüsü
                    # Ölçüm gürültüsünü, toplam gürültü gücüne bağlı olarak belirleyin
                    # Daha yüksek gürültü gücüne sahip mikrofonlar için daha büyük standart sapma
                    noise_std = 1e-4 * math.log10(noise_powers[idx] + 1e-6)
                    t_noise = np.random.normal(0, noise_std)

                    # Gürültülü zaman damgası
                    t_total = t_main + t_noise
                    time_stamps.append(t_total)
                time_stamps = np.array(time_stamps)

                self.estimated_point = self.find_sound_source(self.mic_positions, time_stamps, weights)
                
                # Ortalama desibel hesaplama
                self.average_db = self.compute_total_db_per_mic(sources)
                
                # Ses kaynağı öğelerini güncelle
                self.update_plot_elements()

                # Gürültü bilgilerini güncelle
                self.update_noise_info_labels()

                # Metin kutusunu güncelle
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
            self.update_plot_elements()

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
            for idx, mic in enumerate(self.mic_positions):
                # Ana kaynağın zaman damgası
                dist_main = self.calculate_distance(mic, self.source_point)
                t_main = dist_main / SOUND_SPEED

                # Gürültü kaynaklarının etkisiyle ölçüm gürültüsü
                # Ölçüm gürültüsünü, toplam gürültü gücüne bağlı olarak belirleyin
                # Daha yüksek gürültü gücüne sahip mikrofonlar için daha büyük standart sapma
                noise_std = 1e-4 * math.log10(noise_powers[idx] + 1e-6)
                t_noise = np.random.normal(0, noise_std)

                # Gürültülü zaman damgası
                t_total = t_main + t_noise
                time_stamps.append(t_total)
            time_stamps = np.array(time_stamps)

            self.estimated_point = self.find_sound_source(self.mic_positions, time_stamps, weights)
            
            # Ortalama desibel yeniden hesaplama (mikrofon konumları değiştiği için)
            self.average_db = self.compute_total_db_per_mic(sources)
            
            # Ses kaynağı öğelerini güncelle
            self.update_plot_elements()

            # Gürültü bilgilerini güncelle
            self.update_noise_info_labels()

            # Metin kutusunu güncelle
            self.text_box.setPlainText(
                f"Gerçek Ses Kaynağı: ({self.source_point[0]:.2f}, {self.source_point[1]:.2f})\n"
                f"Tahmin Edilen Konum: ({self.estimated_point[0]:.2f}, {self.estimated_point[1]:.2f})\n"
                f"Ortalama Desibel: {self.average_db:.2f} dB\n\n"
                f"Hesaplama Adımları:\n{self.calculation_steps}"
            )
        self.picked_mic = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SoundSourceLocalization()
    ex.show()
    sys.exit(app.exec_())
