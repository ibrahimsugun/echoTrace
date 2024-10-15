import sys
import numpy as np
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QTextEdit, QLabel, QScrollArea
)
from PyQt5.QtCore import Qt
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
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
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setAspectLocked(True)
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setXRange(-15, 25)
        self.plot_widget.setYRange(-15, 25)
        self.plot_widget.setLabel('left', 'Y Koordinatı')
        self.plot_widget.setLabel('bottom', 'X Koordinatı')
        self.plot_widget.setTitle('Ses Kaynağı Simülasyonu')

        # Mikrofon ve kaynak etkileşimleri
        self.plot_widget.scene().sigMouseClicked.connect(self.on_click)
        self.plot_widget.scene().sigMouseReleased.connect(self.on_release)
        self.plot_widget.scene().sigMouseMoved.connect(self.on_motion)

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
        layout.addWidget(self.plot_widget, 70)
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
        # Mikrofonlar ve etiketler
        self.mic_scatter = pg.ScatterPlotItem(
            self.mic_positions[:, 0], self.mic_positions[:, 1],
            pen=pg.mkPen('b'), brush=pg.mkBrush('b'), size=10, symbol='o'
        )
        self.plot_widget.addItem(self.mic_scatter)
        self.mic_scatter.sigClicked.connect(self.on_mic_clicked)

        for i, pos in enumerate(self.mic_positions):
            text = pg.TextItem(f'M{i+1}', anchor=(0.5, -1.0))
            text.setPos(pos[0], pos[1])
            self.plot_widget.addItem(text)
            self.mic_texts.append(text)

        # Ambient Gürültü Kaynakları
        for idx, noise in enumerate(self.noise_sources, start=1):
            marker_size = 10 + (noise['db'] - 60) * 0.5
            scatter = pg.ScatterPlotItem(
                [noise['position'][0]], [noise['position'][1]],
                pen=pg.mkPen('orange'), brush=pg.mkBrush('orange'), size=marker_size, symbol='x'
            )
            self.plot_widget.addItem(scatter)
            self.noise_scatter.append(scatter)

            text = pg.TextItem(f'{noise["db"]:.1f} dB', anchor=(0.5, -1.0), color='orange')
            text.setPos(noise['position'][0], noise['position'][1])
            self.plot_widget.addItem(text)
            self.noise_texts.append(text)

        # Gerçek Ses Kaynağı (Başlangıçta görünmez)
        self.source_scatter = pg.ScatterPlotItem(
            [], [], pen=pg.mkPen('r'), brush=pg.mkBrush('r'), size=15, symbol='o'
        )
        self.plot_widget.addItem(self.source_scatter)
        self.source_text = pg.TextItem('', anchor=(0.5, -1.0), color='r')
        self.plot_widget.addItem(self.source_text)

        # Tahmin Edilen Ses Kaynağı (Başlangıçta görünmez)
        self.estimated_scatter = pg.ScatterPlotItem(
            [], [], pen=pg.mkPen('g'), brush=pg.mkBrush('g'), size=12, symbol='o'
        )
        self.plot_widget.addItem(self.estimated_scatter)
        self.estimated_text = pg.TextItem('', anchor=(0.5, -1.0), color='g')
        self.plot_widget.addItem(self.estimated_text)

    def update_plot_elements(self):
        """Grafik öğelerini günceller (mikrofonlar, gürültü kaynakları, ses kaynakları)."""
        # Güncellenmiş mikrofon scatter
        self.mic_scatter.setData(self.mic_positions[:, 0], self.mic_positions[:, 1])

        # Mikrofon etiketlerini güncelle
        for i, pos in enumerate(self.mic_positions):
            self.mic_texts[i].setPos(pos[0], pos[1])

        # Ambient Gürültü Kaynakları
        for idx, noise in enumerate(self.noise_sources):
            self.noise_scatter[idx].setData([noise['position'][0]], [noise['position'][1]])
            marker_size = 10 + (noise['db'] - 60) * 0.5
            self.noise_scatter[idx].setSymbol('x')
            self.noise_scatter[idx].setSize(marker_size)
            self.noise_texts[idx].setPos(noise['position'][0], noise['position'][1])
            self.noise_texts[idx].setText(f'{noise["db"]:.1f} dB')

        # Gerçek Ses Kaynağı
        if self.source_point is not None:
            self.source_scatter.setData([self.source_point[0]], [self.source_point[1]])
            self.source_text.setPos(self.source_point[0], self.source_point[1])
            self.source_text.setText(f'  100.00 dB')  # Varsayılan dB değeri
        else:
            self.source_scatter.setData([], [])
            self.source_text.setText('')

        # Tahmin Edilen Ses Kaynağı
        if self.estimated_point is not None:
            self.estimated_scatter.setData([self.estimated_point[0]], [self.estimated_point[1]])
            self.estimated_text.setPos(self.estimated_point[0], self.estimated_point[1])
            self.estimated_text.setText('')
        else:
            self.estimated_scatter.setData([], [])
            self.estimated_text.setText('')

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
        if event.button() == Qt.LeftButton:
            pos = event.scenePos()
            vb = self.plot_widget.plotItem.vb
            mousePoint = vb.mapSceneToView(pos)
            x, y = mousePoint.x(), mousePoint.y()

            # Ses kaynağını belirle
            self.source_point = np.array([x, y])

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

    def on_release(self, event):
        pass  # PyQtGraph'de fare bırakma olayını burada yönetmek gerekmiyor

    def on_motion(self, event):
        if self.picked_mic is not None:
            pos = event
            vb = self.plot_widget.plotItem.vb
            mousePoint = vb.mapSceneToView(pos)
            x, y = mousePoint.x(), mousePoint.y()
            self.mic_positions[self.picked_mic] = [x, y]
            self.update_plot_elements()

    def on_mic_clicked(self, scatter, points):
        for point in points:
            if QtGui.QGuiApplication.mouseButtons() == Qt.RightButton:
                self.picked_mic = int(point.data())  # Mikrofon indexini al
                break

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SoundSourceLocalization()
    ex.show()
    sys.exit(app.exec_())
