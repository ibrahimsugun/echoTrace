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
        self.setGeometry(100, 100, 1500, 910)  # Pencere boyutunu belirler

        # Mikrofonların başlangıç konumları (18 mikrofon, rastgele dağılım)
        self.default_mic_positions = self.generate_random_mic_positions(num_mics=18)
        self.mic_positions = np.copy(self.default_mic_positions)  # Aktif mikrofon konumları
        self.source_point = None  # Gerçek ses kaynağı konumu
        self.source_db = None  # Gerçek ses kaynağı desibel değeri
        self.estimated_point = None  # Tahmin edilen ses kaynağı konumu
        self.estimated_D = None  # Tahmin edilen ses kaynağı desibel değeri
        self.calculation_steps = ""  # Hesaplama adımlarını tutar
        self.average_db = None  # Ortalama desibel değeri

        # Ambient (ortam) gürültü kaynakları (3 Boyutlu)
        self.noise_sources = self.generate_multiple_noise_sources(count=2)

        # Binalar
        self.buildings = []  # Bina verilerini saklamak için liste

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

        # Gerçek ses kaynağı bilgisi için QLabel referansı
        self.source_info_label = None

        # Tahmin edilen ses kaynağı bilgisi için QLabel referansı
        self.estimated_info_label = None

        # Kullanıcı arayüzünü başlat
        self.initUI()
        # Başlangıç grafiğini oluştur
        self.initial_plot()

    def initUI(self):
        """Ana kullanıcı arayüzünü oluşturur ve düzenler."""
        # Ana widget ve layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        layout = QHBoxLayout(self.main_widget)

        # Grafik alanı oluşturma
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, projection='3d')

        # Arka plan panellerinin renklerini ayarla
        self.ax.xaxis.pane.set_facecolor((0.95, 0.95, 0.95, 1.0))  # Çok açık gri
        self.ax.yaxis.pane.set_facecolor((0.88, 0.88, 0.88, 1.0))  # Daha açık gri
        self.ax.zaxis.pane.set_facecolor((0.75, 0.75, 0.75, 1.0))  # Açık gri

        # Grid çizgilerinin renklerini ayarla
        self.ax.xaxis._axinfo["grid"]["color"] = "lightgrey"
        self.ax.yaxis._axinfo["grid"]["color"] = "lightgrey"
        self.ax.zaxis._axinfo["grid"]["color"] = "lightgrey"

        # Fare ile döndürme ayarları (sağ tık ile döndürme)
        self.ax.mouse_init(rotate_btn=3, zoom_btn=None)

        # Mouse event'lerini bağla (sol tık ile işlem yapılmaz)
        self.canvas.mpl_connect('button_press_event', self.on_click)

        # Sağ taraftaki kontrol paneli için layout oluştur
        control_layout = QVBoxLayout()

        # "Sil" butonu: Ses kaynağını ve tahmini noktaları temizler
        self.clear_button = QPushButton('Sil')
        self.clear_button.clicked.connect(self.clear)
        control_layout.addWidget(self.clear_button)

        # "Sıfırla" butonu: Mikrofon konumlarını ve ambient gürültü kaynaklarını sıfırlar
        self.reset_button = QPushButton('Sıfırla')
        self.reset_button.clicked.connect(self.reset_mic_positions)
        control_layout.addWidget(self.reset_button)

        # "Rastgele Pozisyon" butonu: Mikrofon ve gürültü kaynaklarını rastgele pozisyonlara yerleştirir
        self.randomize_button = QPushButton('Rastgele Pozisyon')
        self.randomize_button.clicked.connect(self.randomize_positions)
        control_layout.addWidget(self.randomize_button)

        # "Rastgele Ses Kaynağı" butonu: Rastgele bir ses kaynağı ekler
        self.random_source_button = QPushButton('Rastgele Ses Kaynağı')
        self.random_source_button.clicked.connect(self.add_random_sound_source)
        control_layout.addWidget(self.random_source_button)

        # Hesaplama Adımları metin kutusu: Hesaplama süreçlerini gösterir
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        control_layout.addWidget(QLabel("Hesaplama Adımları:"))
        control_layout.addWidget(self.text_box)

        # Ambient Gürültü Bilgisi bölümü (Scroll Area ile)
        control_layout.addWidget(QLabel("Ambient Gürültü Bilgisi:"))
        self.noise_info_scroll = QScrollArea()
        self.noise_info_widget = QWidget()
        self.noise_info_layout = QVBoxLayout(self.noise_info_widget)
        self.noise_info_scroll.setWidget(self.noise_info_widget)
        self.noise_info_scroll.setWidgetResizable(True)
        self.noise_info_scroll.setFixedHeight(200)  # Yüksekliği artırdık
        self.noise_info_scroll.setStyleSheet("padding: 5px; margin: 0px;")  # Stili küçültmek için
        control_layout.addWidget(self.noise_info_scroll)

        # Layoutları yerleştirme: Grafik alanı %70, kontrol paneli %30 genişlikte
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
        """
        Rastgele bir konum ve desibel değeri ile ambient gürültü kaynağı oluşturur (3D).
        Desibel değeri 60 dB ile 90 dB arasında rastgele seçilir.
        """
        x = random.uniform(-15, 25)
        y = random.uniform(-15, 25)
        z = random.uniform(-10, 10)
        db = random.uniform(60, 90)
        return {'position': np.array([x, y, z]), 'db': db}

    def generate_multiple_noise_sources(self, count=2):
        """
        Belirli sayıda rastgele ambient gürültü kaynağı oluşturur.
        count: Gürültü kaynağı sayısı
        """
        noise_sources = []
        for _ in range(count):
            noise_sources.append(self.generate_random_noise_source())
        return noise_sources

    def generate_buildings(self, count):
        """
        Belirli sayıda rastgele bina oluşturur.
        count: Bina sayısı
        """
        buildings = []
        for _ in range(count):
            width = random.uniform(5, 10)
            depth = random.uniform(5, 10)
            height = random.uniform(5, 10)
            x = random.uniform(-15, 25 - width)
            y = random.uniform(-15, 25 - depth)
            z = 0  # Binalar zeminde başlar
            buildings.append({'position': (x, y, z), 'size': (width, depth, height)})
        return buildings

    def calculate_distance(self, mic_pos, source_pos):
        """
        Mikrofon ile ses kaynağı arasındaki mesafeyi hesaplar (3D).
        mic_pos: Mikrofonun (x, y, z) koordinatları
        source_pos: Ses kaynağının (x, y, z) koordinatları
        """
        distance = np.sqrt((mic_pos[0] - source_pos[0]) ** 2 +
                           (mic_pos[1] - source_pos[1]) ** 2 +
                           (mic_pos[2] - source_pos[2]) ** 2)
        return max(distance, 1e-6)  # Sıfıra çok yakın değerlerde hata önleme

    def calculate_db(self, distance, source_db):
        """
        Verilen mesafeye ve kaynak desibeline göre desibel değerini hesaplar.
        distance: Mikrofon ile ses kaynağı arasındaki mesafe (m)
        source_db: Ses kaynağının desibel değeri (dB)
        """
        if distance <= 0:
            return source_db  # Maksimum desibel
        # Desibel azalması: dB = kaynak_dB - 20 * log10(r)
        db = source_db - 20 * math.log10(distance)
        return db

    def initial_plot(self):
        """
        Başlangıç grafiğini oluşturur ve öğelerin referanslarını saklar.
        Mikrofonlar, ambient gürültü kaynakları ve binalar çizilir.
        """
        self.ax.set_title('3D Ses Kaynağı Simülasyonu')
        self.ax.set_xlabel('X Koordinatı')
        self.ax.set_ylabel('Y Koordinatı')
        self.ax.set_zlabel('Z Koordinatı')

        # Eksen limitlerini belirle
        xlim = [-15, 25]
        ylim = [-15, 25]
        zlim = [-10, 20]  # Yükseklik artırıldı
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)
        self.ax.set_zlim(zlim)

        # Grafiğin başlangıç görünümünü ayarla
        self.ax.view_init(elev=30, azim=-60)  # İstediğiniz açıları ayarlayabilirsiniz

        # Mikrofonları çiz
        self.mic_scatter = self.ax.scatter(
            self.mic_positions[:, 0], self.mic_positions[:, 1], self.mic_positions[:, 2],
            color='blue', label="Mikrofonlar", s=100
        )
        # Mikrofon etiketlerini ekle
        for i, pos in enumerate(self.mic_positions):
            text = self.ax.text(pos[0], pos[1], pos[2], f'M{i+1}', fontsize=8, ha='right', va='bottom')
            self.mic_texts.append(text)

        # Ambient Gürültü Bilgisi bölümünü temizle
        for i in reversed(range(self.noise_info_layout.count())):
            widget_to_remove = self.noise_info_layout.itemAt(i).widget()
            self.noise_info_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

        # Ambient Gürültü Kaynaklarını çiz ve bilgilerini ekle
        for idx, noise in enumerate(self.noise_sources, start=1):
            # Marker boyutunu dB seviyesine göre ayarla (60-90 dB arasında 50-150 büyüklük)
            marker_size = 50 + (noise['db'] - 60) * 2
            scatter = self.ax.scatter(
                noise['position'][0], noise['position'][1], noise['position'][2],
                color='orange',  # Turuncu renkte yuvarlak işaretçi
                label=f"Ambient Gürültü {idx}" if idx == 1 else "",
                s=marker_size,
                marker='x'  # Yuvarlak işaretçi
            )
            self.noise_scatter.append(scatter)
            # Desibel seviyesini marker'ın yanında göster
            text = self.ax.text(
                noise['position'][0], noise['position'][1], noise['position'][2],
                f' {noise["db"]:.1f} dB', fontsize=8,
                ha='left', va='bottom'
            )
            self.noise_texts.append(text)
            # Gürültü bilgilerini kontrol paneline ekle
            noise_info = QLabel(f"Gürültü {idx}: Konum=({noise['position'][0]:.2f}, {noise['position'][1]:.2f}, {noise['position'][2]:.2f}), dB={noise['db']:.2f}")
            self.noise_info_layout.addWidget(noise_info)

        # Binaları çiz
        for building in self.buildings:
            x, y, z = building['position']
            dx, dy, dz = building['size']
            self.ax.bar3d(x, y, z, dx, dy, dz, color='brown', alpha=0.8, shade=True, edgecolor='black')

        # Gerçek Ses Kaynağı (Başlangıçta boş)
        self.source_scatter = self.ax.scatter([], [], [], color='red', label="Gerçek Ses Kaynağı", s=300, marker='o', edgecolors='black', linewidths=1)
        self.source_text = None  # Başlangıçta None

        # Tahmin Edilen Ses Kaynağı (Başlangıçta boş)
        self.estimated_scatter = self.ax.scatter([], [], [], color='green', label="Tahmin Edilen Ses Kaynağı", s=200, marker='o', edgecolors='black', linewidths=1)
        self.estimated_text = None  # Başlangıçta None

        # Legend ekle
        self.ax.legend(loc='upper right', fontsize=8)
        # Grafiği çiz
        self.canvas.draw()

    def on_click(self, event):
        """
        Mouse tıklama event handler.
        Sol tık ile herhangi bir işlem yapmaz.
        """
        if event.button == 1:  # Sol tık
            return  # Sol tıkta hiçbir işlem yapma

    def add_random_sound_source(self):
        """
        Rastgele bir ses kaynağı ekler ve desibel değerini rastgele belirler.
        Ses kaynağı grafiğe eklenir ve lokalizasyon işlemi başlatılır.
        Ayrıca, ses kaynağının bilgisi Ambient Gürültü Bilgisi alanına eklenir.
        """
        x = random.uniform(-15, 25)
        y = random.uniform(-15, 25)
        z = random.uniform(-10, 10)  # Z koordinatı rastgele belirlenir
        self.source_point = np.array([x, y, z])  # Ses kaynağı konumu
        self.source_db = random.uniform(60, 100)  # Ses kaynağı desibel değeri 60-100 dB arasında rastgele seçilir
        self.update_plot_elements()  # Grafiği güncelle
        self.perform_localization()  # Lokalizasyon işlemini gerçekleştir

        # Ambient Gürültü Bilgisi alanına gerçek ses kaynağı bilgisi ekle
        if self.source_info_label:
            # Eğer daha önce bir ses kaynağı eklenmişse, eski etiketi kaldır
            self.noise_info_layout.removeWidget(self.source_info_label)
            self.source_info_label.deleteLater()
            self.source_info_label = None

        # Yeni ses kaynağı bilgisi ekle
        self.source_info_label = QLabel(f"Ses Kaynağı: Konum=({x:.2f}, {y:.2f}, {z:.2f}), dB={self.source_db:.2f}")
        self.noise_info_layout.insertWidget(0, self.source_info_label)  # En üstte göster

    def is_path_blocked(self, start_point, end_point):
        """
        Ses kaynağı ile mikrofon arasındaki yolun bir bina tarafından engellenip engellenmediğini kontrol eder.
        start_point: Başlangıç noktası (ses kaynağı)
        end_point: Bitiş noktası (mikrofon)
        """
        for building in self.buildings:
            if self.line_intersects_box(start_point, end_point, building):
                return True  # Yol engellenmiş
        return False  # Yol engellenmemiş

    def line_intersects_box(self, p0, p1, box):
        """
        Bir çizginin (p0, p1) bir kutu (box) ile kesişip kesişmediğini kontrol eder.
        p0: Çizginin başlangıç noktası (x, y, z)
        p1: Çizginin bitiş noktası (x, y, z)
        box: Kutu verileri {'position': (x, y, z), 'size': (dx, dy, dz)}
        """
        x_min = box['position'][0]
        y_min = box['position'][1]
        z_min = box['position'][2]
        x_max = x_min + box['size'][0]
        y_max = y_min + box['size'][1]
        z_max = z_min + box['size'][2]

        box_min = np.array([x_min, y_min, z_min])
        box_max = np.array([x_max, y_max, z_max])
        p0 = np.array(p0)
        p1 = np.array(p1)

        # Çizgi segmentinin parametreleri
        direction = p1 - p0
        tmin = 0.0
        tmax = 1.0

        for i in range(3):  # x, y, z için
            if abs(direction[i]) < 1e-8:
                # Çizgi bu eksene paralel
                if p0[i] < box_min[i] or p0[i] > box_max[i]:
                    return False  # Çizgi kutunun dışında
            else:
                ood = 1.0 / direction[i]
                t1 = (box_min[i] - p0[i]) * ood
                t2 = (box_max[i] - p0[i]) * ood
                t_enter = min(t1, t2)
                t_exit = max(t1, t2)
                tmin = max(tmin, t_enter)
                tmax = min(tmax, t_exit)
                if tmin > tmax:
                    return False  # Kesişim yok
        return True  # Kesişim var

    def perform_localization(self):
        """
        Ses kaynağının yerini ve desibel değerini tahmin eder.
        Ölçülen dB değerleri kullanılarak optimizasyon yapılır.
        """
        if self.source_point is None:
            return  # Ses kaynağı belirlenmemişse işlemi durdur

        # Gerçek kaynak ve gürültü kaynaklarından gelen toplam dB'yi hesapla
        # Gerçek ses kaynağının desibel değeri artık değişken
        source_points = [{'position': self.source_point, 'db': self.source_db}]
        # Ambient gürültü kaynakları zaten self.noise_sources içinde mevcut

        # Ölçülen dB değerlerini hesapla
        measured_db = []
        self.calculation_steps = ""  # Hesaplama adımlarını sıfırla
        self.calculation_steps += "Mikrofonlarda Ölçülen dB Değerleri:\n"

        mic_blocked_status = []  # Mikrofonun engellenip engellenmediğini tutar

        for idx_mic, mic in enumerate(self.mic_positions):
            total_power = 0  # Mikrofon için toplam ses gücü
            self.calculation_steps += f"\nMikrofon {idx_mic + 1}:\n"
            blocked = self.is_path_blocked(self.source_point, mic)
            mic_blocked_status.append(blocked)
            for source in source_points:
                # Ses kaynağı ile mikrofon arasındaki yol engellenmiş mi kontrol et
                source_blocked = self.is_path_blocked(source['position'], mic)
                if source_blocked:
                    self.calculation_steps += f"  Kaynak ({source['position'][0]:.2f}, {source['position'][1]:.2f}, {source['position'][2]:.2f}) engellenmiş.\n"
                    continue  # Engellenmişse bu kaynağı hesaba katma
                distance = self.calculate_distance(mic, source['position'])
                db = self.calculate_db(distance, source['db'])
                power = 10 ** (db / 10)
                total_power += power
                self.calculation_steps += f"  Kaynak ({source['position'][0]:.2f}, {source['position'][1]:.2f}, {source['position'][2]:.2f}), Mesafe: {distance:.2f} m, dB: {db:.2f}, Engellenmiş: Hayır\n"
            # Ambient gürültü ekle
            for noise in self.noise_sources:
                n_distance = self.calculate_distance(mic, noise['position'])
                n_db = self.calculate_db(n_distance, noise['db'])
                n_power = 10 ** (n_db / 10)
                total_power += n_power
                self.calculation_steps += f"  Gürültü Kaynağı ({noise['position'][0]:.2f}, {noise['position'][1]:.2f}, {noise['position'][2]:.2f}), Mesafe: {n_distance:.2f} m, dB: {n_db:.2f}\n"
            # Toplam dB değerini hesapla
            total_db = 10 * math.log10(total_power) if total_power > 0 else 0
            measured_db.append(total_db)
            self.calculation_steps += f"  Toplam dB: {total_db:.2f}\n"

        # Ortalama dB değerini hesapla
        self.average_db = np.mean(measured_db)
        self.calculation_steps += f"\nOrtalama dB: {self.average_db:.2f}\n"

        # Bloklanmamış mikrofonların indekslerini al
        unblocked_mic_indices = [i for i, blocked in enumerate(mic_blocked_status) if not blocked]

        # Eğer bloklanmamış mikrofon yoksa, işlemi durdur
        if not unblocked_mic_indices:
            self.calculation_steps += "\nBloklanmamış mikrofon bulunamadı. Tahmin yapılamıyor.\n"
            self.text_box.setPlainText(self.calculation_steps)
            return

        # Bloklanmamış mikrofonlar için measured_db ve pozisyonları filtrele
        filtered_measured_db = [measured_db[i] for i in unblocked_mic_indices]
        filtered_mic_positions = [self.mic_positions[i] for i in unblocked_mic_indices]

        # Ses kaynağının yerini ve D (desibel) değerini tahmin et
        def objective_function(pos_dB):
            """
            Optimizasyon fonksiyonu.
            pos_dB: [x, y, z, D] tahmin edilen pozisyon ve desibel değeri
            Hedef, tahmin edilen dB değerleri ile ölçülen dB değerleri arasındaki toplam kare hatayı minimize etmektir.
            """
            x, y, z, D = pos_dB
            total_error = 0
            for i, mic in enumerate(filtered_mic_positions):
                # Tahmin edilen pozisyondan mikrofon konumuna mesafe
                distance = self.calculate_distance(mic, pos_dB[:3])
                if distance <= 0:
                    predicted_db = D  # Maksimum dB
                else:
                    predicted_db = self.calculate_db(distance, D)
                # Ambient gürültüyü ekle
                total_power = 10 ** (predicted_db / 10)
                for noise in self.noise_sources:
                    n_distance = self.calculate_distance(mic, noise['position'])
                    n_db = self.calculate_db(n_distance, noise['db'])
                    n_power = 10 ** (n_db / 10)
                    total_power += n_power
                # Tahmin edilen toplam dB değeri
                total_db = 10 * math.log10(total_power) if total_power > 0 else 0
                # Hata hesapla
                error = (total_db - filtered_measured_db[i]) ** 2
                total_error += error
            return total_error

        # Optimizasyon için başlangıç tahminini belirle (mikrofonların ortalaması ve ortalama dB)
        x0 = list(np.mean(filtered_mic_positions, axis=0)) + [self.average_db]
        # Optimizasyon işlemini gerçekleştir (BFGS yöntemi ile)
        res = minimize(objective_function, x0, method='BFGS')
        estimated_pos = res.x[:3]  # Tahmin edilen pozisyon
        estimated_D = res.x[3]  # Tahmin edilen desibel değeri

        # Tahmin sonuçlarını sakla
        self.estimated_point = estimated_pos
        self.estimated_D = estimated_D  # Tahmin edilen dB değeri

        # Hesaplama adımlarına tahmin sonuçlarını ekle
        self.calculation_steps += f"\nTahmin Edilen Konum: ({estimated_pos[0]:.2f}, {estimated_pos[1]:.2f}, {estimated_pos[2]:.2f}), Tahmin Edilen dB: {estimated_D:.2f}\n"
        # Metin kutusunu güncelle
        self.text_box.setPlainText(self.calculation_steps)
        # Grafiği güncelle
        self.update_plot_elements()

    def clear(self):
        """
        Ses kaynağı ve tahmin edilen noktaları siler.
        Grafiği ve hesaplama adımlarını temizler.
        Ayrıca Ambient Gürültü Bilgisi alanındaki ses kaynağı ve tahmin etiketlerini kaldırır.
        """
        self.source_point = None
        self.source_db = None
        self.estimated_point = None
        self.estimated_D = None
        self.calculation_steps = ""
        self.average_db = None
        self.text_box.setPlainText("")

        # Ambient Gürültü Bilgisi alanındaki ses kaynağı etiketini kaldır
        if self.source_info_label:
            self.noise_info_layout.removeWidget(self.source_info_label)
            self.source_info_label.deleteLater()
            self.source_info_label = None

        # Ambient Gürültü Bilgisi alanındaki tahmin etiketini kaldır
        if self.estimated_info_label:
            self.noise_info_layout.removeWidget(self.estimated_info_label)
            self.estimated_info_label.deleteLater()
            self.estimated_info_label = None

        self.update_plot_elements()

    def reset_mic_positions(self):
        """
        Mikrofon konumlarını, ambient gürültü kaynaklarını ve binaları sıfırlar.
        Ayrıca ses kaynağı ve tahmin edilen noktaları temizler.
        """
        self.mic_positions = np.copy(self.default_mic_positions)  # Mikrofon konumlarını varsayılan değerlere döndür
        self.noise_sources = self.generate_multiple_noise_sources(count=2)  # Gürültü kaynaklarını yenile
        # Binaları oluştur
        building_count = random.randint(1, 3)
        self.buildings = self.generate_buildings(building_count)
        self.clear()  # Ses kaynağı ve tahminleri temizle
        self.update_plot_elements()  # Grafiği güncelle

    def randomize_positions(self):
        """
        Mikrofon, gürültü kaynakları ve binaların pozisyonlarını rastgele olarak değiştirir.
        Ses kaynağı ve tahmin edilen noktaları temizler.
        """
        self.mic_positions = self.generate_random_mic_positions(num_mics=18)  # Mikrofonları rastgele konumlandır
        self.noise_sources = self.generate_multiple_noise_sources(count=2)  # Gürültü kaynaklarını rastgele konumlandır
        # Binaları oluştur
        building_count = random.randint(1, 3)
        self.buildings = self.generate_buildings(building_count)
        self.clear()  # Ses kaynağı ve tahminleri temizle
        self.update_plot_elements()  # Grafiği güncelle

    def update_plot_elements(self):
        """
        Grafik öğelerini günceller (mikrofonlar, gürültü kaynakları, ses kaynakları).
        Gerçek ses kaynağı ve tahmin edilen ses kaynağı grafiğe eklenir.
        Ambient Gürültü Bilgisi alanındaki bilgileri günceller.
        """
        self.ax.clear()  # Grafiği temizle
        self.initial_plot()  # Başlangıç grafiğini yeniden oluştur

        # Silinen çizgi referanslarını temizle
        self.source_to_mic_lines = []

        # Fare ile döndürme ayarlarını tekrar uygula
        self.ax.mouse_init(rotate_btn=3, zoom_btn=None)

        # Arka plan panellerinin renklerini tekrar ayarla
        self.ax.xaxis.pane.set_facecolor((0.95, 0.95, 0.95, 1.0))  # Çok açık gri
        self.ax.yaxis.pane.set_facecolor((0.88, 0.88, 0.88, 1.0))  # Daha açık gri
        self.ax.zaxis.pane.set_facecolor((0.75, 0.75, 0.75, 1.0))  # Açık gri

        # Grid çizgilerinin renklerini ayarla
        self.ax.xaxis._axinfo["grid"]["color"] = "grey"
        self.ax.yaxis._axinfo["grid"]["color"] = "grey"
        self.ax.zaxis._axinfo["grid"]["color"] = "grey"

        # Gerçek Ses Kaynağı
        if self.source_point is not None:
            # Ses kaynağını grafiğe ekle
            self.source_scatter._offsets3d = (self.source_point[0:1], self.source_point[1:2], self.source_point[2:3])
            x, y, z = self.source_point
            # Z koordinatına offset ekle
            offset = 0.9
            self.source_text = self.ax.text(
                x, y, z - offset,
                f'({x:.2f}, {y:.2f}, {z:.2f})', color='red', fontsize=10, fontweight='bold',
                ha='center', va='top'
            )

            # Ses kaynağından mikrofonlara çizgileri çiz
            for idx, mic_pos in enumerate(self.mic_positions):
                blocked = self.is_path_blocked(self.source_point, mic_pos)
                if blocked:
                    color = 'red'
                    linestyle = 'dashdot'
                else:
                    color = 'gray'
                    linestyle = '--'
                line, = self.ax.plot(
                    [self.source_point[0], mic_pos[0]],
                    [self.source_point[1], mic_pos[1]],
                    [self.source_point[2], mic_pos[2]],
                    color=color,
                    linestyle=linestyle,
                    linewidth=0.7
                )
                self.source_to_mic_lines.append(line)

        else:
            # Ses kaynağı yoksa scatter noktalarını temizle
            self.source_scatter._offsets3d = ([], [], [])

        # Tahmin Edilen Ses Kaynağı
        if self.estimated_point is not None:
            # Tahmin edilen ses kaynağını grafiğe ekle
            self.estimated_scatter._offsets3d = (self.estimated_point[0:1], self.estimated_point[1:2], self.estimated_point[2:3])
            x, y, z = self.estimated_point
            # Z koordinatına offset ekle
            offset = 0.9
            self.estimated_text = self.ax.text(
                x, y, z + offset,
                f'Tahmin (dB: {self.estimated_D:.2f})', color='green', fontsize=9, fontweight='bold', 
                ha='left', va='bottom'
            )

            # Tahmin edilen ses kaynağından mikrofonlara çizgileri çiz
            for idx, mic_pos in enumerate(self.mic_positions):
                blocked = self.is_path_blocked(self.estimated_point, mic_pos)
                if blocked:
                    color = 'red'
                    linestyle = 'dashdot'
                else:
                    color = 'gray'
                    linestyle = '--'
                line, = self.ax.plot(
                    [self.estimated_point[0], mic_pos[0]],
                    [self.estimated_point[1], mic_pos[1]],
                    [self.estimated_point[2], mic_pos[2]],
                    color=color,
                    linestyle=linestyle,
                    linewidth=0.7
                )
                self.source_to_mic_lines.append(line)

            # Tahmin edilen ses kaynağı bilgisi Ambient Gürültü Bilgisi alanına ekle
            if self.estimated_info_label:
                # Eğer daha önce bir tahmin eklenmişse, eski etiketi kaldır
                self.noise_info_layout.removeWidget(self.estimated_info_label)
                self.estimated_info_label.deleteLater()
                self.estimated_info_label = None

            # Yeni tahmin bilgisi ekle
            self.estimated_info_label = QLabel(f"Tahmin Edilen Ses Kaynağı: Konum=({x:.2f}, {y:.2f}, {z:.2f}), dB={self.estimated_D:.2f}")
            self.noise_info_layout.addWidget(self.estimated_info_label)
        else:
            # Tahmin edilen ses kaynağı yoksa scatter noktalarını temizle
            self.estimated_scatter._offsets3d = ([], [], [])

        # Güncellenmiş çizimleri ekrana yansıt
        self.canvas.draw_idle()

if __name__ == '__main__':
    # Uygulamayı başlat
    app = QApplication(sys.argv)
    ex = SoundSourceLocalization3D()
    ex.show()
    sys.exit(app.exec_()) 