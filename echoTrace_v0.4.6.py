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
        self.setWindowTitle('3D Ses Kaynağı Lokalizasyon Simülasyonu')
        self.setGeometry(100, 100, 1500, 900)
        
        # Mikrofonların başlangıç konumları (18 mikrofon)
        self.default_mic_positions = self.generate_random_mic_positions(num_mics=18)
        self.mic_positions = np.copy(self.default_mic_positions)
        
        # Ses kaynağı değişkenleri
        self.source_point = None
        self.source_db = None
        self.estimated_point = None
        self.estimated_db = None
        
        # Ambient gürültü kaynakları
        self.noise_sources = self.generate_multiple_noise_sources(count=2)
        self.estimated_noise_sources = []
        
        # Binalar
        self.buildings = self.generate_buildings(random.randint(2, 3))
        
        # Hesaplama değişkenleri
        self.calculation_steps = ""
        self.average_db = None
        
        # Grafik elemanları için referanslar
        self.mic_scatter = None
        self.mic_texts = []
        self.noise_scatter = []
        self.noise_texts = []
        self.estimated_noise_scatter = []
        self.estimated_noise_texts = []
        self.source_scatter = None
        self.source_text = None
        self.estimated_scatter = None
        self.estimated_text = None
        self.source_to_mic_lines = []
        
        # UI başlatma
        self.initUI()
        self.initial_plot()
    
    def initUI(self):
        """Kullanıcı arayüzünü oluşturur."""
        # Ana widget ve layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        layout = QHBoxLayout(self.main_widget)
        
        # 3D grafik alanı
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, projection='3d')
        
        # Arka plan renkleri
        self.ax.xaxis.pane.set_facecolor((0.95, 0.95, 0.95, 1.0))
        self.ax.yaxis.pane.set_facecolor((0.90, 0.90, 0.90, 1.0))
        self.ax.zaxis.pane.set_facecolor((0.85, 0.85, 0.85, 1.0))
        
        # Grid renkleri
        self.ax.xaxis._axinfo["grid"]["color"] = "lightgrey"
        self.ax.yaxis._axinfo["grid"]["color"] = "lightgrey"
        self.ax.zaxis._axinfo["grid"]["color"] = "lightgrey"
        
        # Sağ tık ile döndürme
        self.ax.mouse_init(rotate_btn=3, zoom_btn=None)
        
        # Kontrol paneli
        control_layout = QVBoxLayout()
        
        # Butonlar
        self.clear_button = QPushButton('Temizle')
        self.clear_button.clicked.connect(self.clear)
        control_layout.addWidget(self.clear_button)
        
        self.reset_button = QPushButton('Sıfırla')
        self.reset_button.clicked.connect(self.reset_positions)
        control_layout.addWidget(self.reset_button)
        
        self.randomize_button = QPushButton('Rastgele Konumlar')
        self.randomize_button.clicked.connect(self.randomize_positions)
        control_layout.addWidget(self.randomize_button)
        
        self.add_source_button = QPushButton('Rastgele Ses Kaynağı Ekle')
        self.add_source_button.clicked.connect(self.add_random_sound_source)
        control_layout.addWidget(self.add_source_button)
        
        # Hesaplama detayları
        control_layout.addWidget(QLabel("Hesaplama Detayları:"))
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        control_layout.addWidget(self.text_box)
        
        # Ses kaynakları bilgi paneli
        control_layout.addWidget(QLabel("Ses Kaynakları Bilgisi:"))
        self.info_scroll = QScrollArea()
        self.info_widget = QWidget()
        self.info_layout = QVBoxLayout(self.info_widget)
        self.info_scroll.setWidget(self.info_widget)
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setFixedHeight(200)
        control_layout.addWidget(self.info_scroll)
        
        # Layout yerleşimi
        layout.addWidget(self.canvas, 70)
        layout.addLayout(control_layout, 30)
    
    def generate_random_mic_positions(self, num_mics=18):
        """Rastgele mikrofon konumları oluşturur."""
        positions = []
        for _ in range(num_mics):
            x = np.random.uniform(-15, 25)
            y = np.random.uniform(-15, 25)
            z = np.random.uniform(-5, 10)
            positions.append([x, y, z])
        return np.array(positions)
    
    def generate_random_noise_source(self):
        """Rastgele gürültü kaynağı oluşturur."""
        x = np.random.uniform(-15, 25)
        y = np.random.uniform(-15, 25)
        z = np.random.uniform(-5, 10)
        db = np.random.uniform(60, 85)
        return {'position': np.array([x, y, z]), 'db': db}
    
    def generate_multiple_noise_sources(self, count=2):
        """Birden fazla gürültü kaynağı oluşturur."""
        sources = []
        for _ in range(count):
            sources.append(self.generate_random_noise_source())
        return sources
    
    def generate_buildings(self, count):
        """Rastgele binalar oluşturur."""
        buildings = []
        for _ in range(count):
            width = np.random.uniform(4, 8)
            depth = np.random.uniform(4, 8)
            height = np.random.uniform(8, 15)
            x = np.random.uniform(-10, 20 - width)
            y = np.random.uniform(-10, 20 - depth)
            z = 0
            buildings.append({
                'position': (x, y, z),
                'size': (width, depth, height)
            })
        return buildings
    
    def calculate_distance(self, pos1, pos2):
        """İki nokta arasındaki 3D mesafeyi hesaplar."""
        pos1 = np.array(pos1)
        pos2 = np.array(pos2)
        distance = np.linalg.norm(pos1 - pos2)
        return max(distance, 1e-6)  # Sıfıra bölme hatası önleme
    
    def calculate_db(self, distance, source_db):
        """Mesafeye göre dB azalmasını hesaplar."""
        if distance <= 1e-6:
            return source_db
        # Ses şiddeti mesafenin karesiyle ters orantılı olarak azalır
        db = source_db - 20 * np.log10(distance)
        return db
    
    def is_path_blocked(self, start_point, end_point):
        """İki nokta arasındaki yolun bina tarafından engellenip engellenmediğini kontrol eder."""
        for building in self.buildings:
            if self.line_intersects_box(start_point, end_point, building):
                return True
        return False
    
    def line_intersects_box(self, p0, p1, box):
        """Çizgi-kutu kesişim kontrolü."""
        x_min, y_min, z_min = box['position']
        x_max = x_min + box['size'][0]
        y_max = y_min + box['size'][1]
        z_max = z_min + box['size'][2]
        
        box_min = np.array([x_min, y_min, z_min])
        box_max = np.array([x_max, y_max, z_max])
        p0 = np.array(p0)
        p1 = np.array(p1)
        
        direction = p1 - p0
        tmin = 0.0
        tmax = 1.0
        
        for i in range(3):
            if abs(direction[i]) < 1e-8:
                if p0[i] < box_min[i] or p0[i] > box_max[i]:
                    return False
            else:
                ood = 1.0 / direction[i]
                t1 = (box_min[i] - p0[i]) * ood
                t2 = (box_max[i] - p0[i]) * ood
                t_enter = min(t1, t2)
                t_exit = max(t1, t2)
                tmin = max(tmin, t_enter)
                tmax = min(tmax, t_exit)
                if tmin > tmax:
                    return False
        return True
    
    def initial_plot(self):
        """Başlangıç grafiğini oluşturur."""
        self.ax.clear()
        
        # Eksen ayarları
        self.ax.set_title('3D Ses Kaynağı Lokalizasyon Simülasyonu')
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.set_zlabel('Z (m)')
        self.ax.set_xlim([-15, 25])
        self.ax.set_ylim([-15, 25])
        self.ax.set_zlim([-5, 20])
        self.ax.view_init(elev=25, azim=-60)
        
        # Mikrofonları çiz
        self.mic_scatter = self.ax.scatter(
            self.mic_positions[:, 0],
            self.mic_positions[:, 1],
            self.mic_positions[:, 2],
            color='blue', s=80, label='Mikrofonlar'
        )
        
        # Mikrofon etiketleri
        self.mic_texts = []
        for i, pos in enumerate(self.mic_positions):
            text = self.ax.text(
                pos[0], pos[1], pos[2],
                f'M{i+1}', fontsize=7
            )
            self.mic_texts.append(text)
        
        # Gürültü kaynaklarını çiz
        self.noise_scatter = []
        self.noise_texts = []
        for idx, noise in enumerate(self.noise_sources):
            scatter = self.ax.scatter(
                noise['position'][0],
                noise['position'][1],
                noise['position'][2],
                color='orange', s=100, marker='x',
                label=f'Gürültü {idx+1}' if idx == 0 else ""
            )
            self.noise_scatter.append(scatter)
            
            text = self.ax.text(
                noise['position'][0],
                noise['position'][1],
                noise['position'][2],
                f" {noise['db']:.1f} dB",
                fontsize=8, color='orange'
            )
            self.noise_texts.append(text)
        
        # Binaları çiz
        for building in self.buildings:
            x, y, z = building['position']
            dx, dy, dz = building['size']
            self.ax.bar3d(x, y, z, dx, dy, dz,
                         color='gray', alpha=0.7, shade=True)
        
        # Boş ses kaynağı scatter'ları
        self.source_scatter = self.ax.scatter(
            [], [], [], color='red', s=200,
            marker='o', label='Gerçek Ses Kaynağı'
        )
        
        self.estimated_scatter = self.ax.scatter(
            [], [], [], color='green', s=150,
            marker='^', label='Tahmin Edilen'
        )
        
        self.ax.legend(loc='upper right', fontsize=8)
        self.canvas.draw()
    
    def add_random_sound_source(self):
        """Rastgele ses kaynağı ekler ve lokalizasyon yapar."""
        # Rastgele konum ve dB
        x = np.random.uniform(-10, 20)
        y = np.random.uniform(-10, 20)
        z = np.random.uniform(0, 10)
        self.source_point = np.array([x, y, z])
        self.source_db = np.random.uniform(75, 95)
        
        # Lokalizasyon işlemini başlat
        self.perform_localization()
        self.update_plot()
    
    def perform_localization(self):
        """Ses kaynağı lokalizasyonunu gerçekleştirir."""
        if self.source_point is None:
            return
        
        # Mikrofonlarda ölçülen dB değerlerini hesapla
        measured_db = []
        mic_blocked = []
        self.calculation_steps = "=== ÖLÇÜM SONUÇLARI ===\n\n"
        
        for i, mic_pos in enumerate(self.mic_positions):
            total_power = 0
            
            # Ana ses kaynağından gelen ses
            blocked = self.is_path_blocked(self.source_point, mic_pos)
            mic_blocked.append(blocked)
            
            if not blocked:
                dist = self.calculate_distance(mic_pos, self.source_point)
                db = self.calculate_db(dist, self.source_db)
                power = 10 ** (db / 10)
                total_power += power
                self.calculation_steps += f"M{i+1}: Kaynak mesafe={dist:.2f}m, dB={db:.1f}\n"
            else:
                self.calculation_steps += f"M{i+1}: Kaynak ENGELLENMİŞ\n"
            
            # Gürültü kaynaklarından gelen ses
            for noise in self.noise_sources:
                if not self.is_path_blocked(noise['position'], mic_pos):
                    dist = self.calculate_distance(mic_pos, noise['position'])
                    db = self.calculate_db(dist, noise['db'])
                    power = 10 ** (db / 10)
                    total_power += power
            
            # Toplam dB
            total_db = 10 * np.log10(total_power) if total_power > 0 else 0
            measured_db.append(total_db)
        
        # Engellenmemiş mikrofonları filtrele
        unblocked_indices = [i for i, blocked in enumerate(mic_blocked) if not blocked]
        
        if len(unblocked_indices) < 4:
            self.calculation_steps += "\n⚠️ Yetersiz engellenmemiş mikrofon!\n"
            self.text_box.setPlainText(self.calculation_steps)
            return
        
        filtered_mics = self.mic_positions[unblocked_indices]
        filtered_db = [measured_db[i] for i in unblocked_indices]
        
        # Optimizasyon
        def objective(params):
            """Hedef fonksiyon: ölçülen ve tahmin edilen dB farkını minimize et."""
            # Ana ses kaynağı parametreleri
            x, y, z, source_db = params[:4]
            
            # Gürültü kaynakları parametreleri
            noise_params = params[4:].reshape(-1, 4)
            
            total_error = 0
            for i, mic_pos in enumerate(filtered_mics):
                # Tahmin edilen toplam güç
                predicted_power = 0
                
                # Ana kaynak
                if not self.is_path_blocked([x, y, z], mic_pos):
                    dist = self.calculate_distance(mic_pos, [x, y, z])
                    db = self.calculate_db(dist, source_db)
                    predicted_power += 10 ** (db / 10)
                
                # Gürültü kaynakları
                for n_params in noise_params:
                    n_x, n_y, n_z, n_db = n_params
                    if not self.is_path_blocked([n_x, n_y, n_z], mic_pos):
                        dist = self.calculate_distance(mic_pos, [n_x, n_y, n_z])
                        db = self.calculate_db(dist, n_db)
                        predicted_power += 10 ** (db / 10)
                
                # Tahmin edilen toplam dB
                predicted_db = 10 * np.log10(predicted_power) if predicted_power > 0 else 0
                
                # Hata
                error = (predicted_db - filtered_db[i]) ** 2
                total_error += error
            
            return total_error
        
        # Başlangıç tahmini
        x0 = []
        # Ana kaynak için başlangıç tahmini (mikrofonların ortalaması)
        x0.extend(np.mean(filtered_mics, axis=0).tolist())
        x0.append(85)  # Başlangıç dB tahmini
        
        # Gürültü kaynakları için başlangıç tahmini
        for noise in self.noise_sources:
            x0.extend(noise['position'].tolist())
            x0.append(noise['db'])
        
        # Sınırlar
        bounds = [
            (-15, 25), (-15, 25), (-5, 15), (60, 100)  # Ana kaynak
        ]
        for _ in self.noise_sources:
            bounds.extend([
                (-15, 25), (-15, 25), (-5, 15), (50, 90)  # Gürültü kaynakları
            ])
        
        # Optimizasyon
        result = minimize(objective, x0, method='L-BFGS-B', bounds=bounds)
        
        # Sonuçları kaydet
        self.estimated_point = result.x[:3]
        self.estimated_db = result.x[3]
        
        # Gürültü kaynaklarının tahminleri
        self.estimated_noise_sources = []
        noise_params = result.x[4:].reshape(-1, 4)
        for n_params in noise_params:
            self.estimated_noise_sources.append({
                'position': n_params[:3],
                'db': n_params[3]
            })
        
        # Sonuçları rapora ekle
        self.calculation_steps += f"\n=== TAHMİN SONUÇLARI ===\n"
        self.calculation_steps += f"Gerçek Konum: ({self.source_point[0]:.1f}, {self.source_point[1]:.1f}, {self.source_point[2]:.1f})\n"
        self.calculation_steps += f"Gerçek dB: {self.source_db:.1f}\n\n"
        self.calculation_steps += f"Tahmin Konum: ({self.estimated_point[0]:.1f}, {self.estimated_point[1]:.1f}, {self.estimated_point[2]:.1f})\n"
        self.calculation_steps += f"Tahmin dB: {self.estimated_db:.1f}\n\n"
        
        # Hata hesaplama
        position_error = self.calculate_distance(self.source_point, self.estimated_point)
        db_error = abs(self.source_db - self.estimated_db)
        self.calculation_steps += f"Konum Hatası: {position_error:.2f} m\n"
        self.calculation_steps += f"dB Hatası: {db_error:.1f} dB\n"
        
        self.text_box.setPlainText(self.calculation_steps)
    
    def update_plot(self):
        """Grafiği günceller."""
        # Grafiği temizle ve yeniden çiz
        self.initial_plot()
        
        # Bilgi panelini güncelle
        for i in reversed(range(self.info_layout.count())):
            widget = self.info_layout.itemAt(i).widget()
            if widget:
                self.info_layout.removeWidget(widget)
                widget.deleteLater()
        
        # Gerçek ses kaynağı
        if self.source_point is not None:
            self.source_scatter._offsets3d = (
                [self.source_point[0]],
                [self.source_point[1]],
                [self.source_point[2]]
            )
            
            # Bilgi paneline ekle
            info = QLabel(f"🔴 Ses Kaynağı: ({self.source_point[0]:.1f}, {self.source_point[1]:.1f}, {self.source_point[2]:.1f}) - {self.source_db:.1f} dB")
            self.info_layout.addWidget(info)
            
            # Mikrofonlara çizgiler
            for mic_pos in self.mic_positions:
                blocked = self.is_path_blocked(self.source_point, mic_pos)
                color = 'red' if blocked else 'gray'
                alpha = 0.3 if blocked else 0.2
                self.ax.plot(
                    [self.source_point[0], mic_pos[0]],
                    [self.source_point[1], mic_pos[1]],
                    [self.source_point[2], mic_pos[2]],
                    color=color, alpha=alpha, linewidth=0.5
                )
        
        # Tahmin edilen ses kaynağı
        if self.estimated_point is not None:
            self.estimated_scatter._offsets3d = (
                [self.estimated_point[0]],
                [self.estimated_point[1]],
                [self.estimated_point[2]]
            )
            
            # Bilgi paneline ekle
            info = QLabel(f"🟢 Tahmin: ({self.estimated_point[0]:.1f}, {self.estimated_point[1]:.1f}, {self.estimated_point[2]:.1f}) - {self.estimated_db:.1f} dB")
            self.info_layout.addWidget(info)
        
        # Gürültü kaynakları bilgisi
        for i, noise in enumerate(self.noise_sources):
            info = QLabel(f"🟠 Gürültü {i+1}: ({noise['position'][0]:.1f}, {noise['position'][1]:.1f}, {noise['position'][2]:.1f}) - {noise['db']:.1f} dB")
            self.info_layout.addWidget(info)
        
        # Tahmin edilen gürültü kaynakları
        for i, est_noise in enumerate(self.estimated_noise_sources):
            scatter = self.ax.scatter(
                est_noise['position'][0],
                est_noise['position'][1],
                est_noise['position'][2],
                color='purple', s=80, marker='v', alpha=0.7
            )
            info = QLabel(f"🟣 Gürültü {i+1} Tahmini: ({est_noise['position'][0]:.1f}, {est_noise['position'][1]:.1f}, {est_noise['position'][2]:.1f}) - {est_noise['db']:.1f} dB")
            self.info_layout.addWidget(info)
        
        self.canvas.draw()
    
    def clear(self):
        """Ses kaynağını ve tahminleri temizler."""
        self.source_point = None
        self.source_db = None
        self.estimated_point = None
        self.estimated_db = None
        self.estimated_noise_sources = []
        self.calculation_steps = ""
        self.text_box.clear()
        self.update_plot()
    
    def reset_positions(self):
        """Tüm konumları varsayılana döndürür."""
        self.mic_positions = np.copy(self.default_mic_positions)
        self.noise_sources = self.generate_multiple_noise_sources(count=2)
        self.buildings = self.generate_buildings(random.randint(2, 3))
        self.clear()
    
    def randomize_positions(self):
        """Tüm konumları rastgele değiştirir."""
        self.mic_positions = self.generate_random_mic_positions(num_mics=18)
        self.noise_sources = self.generate_multiple_noise_sources(count=2)
        self.buildings = self.generate_buildings(random.randint(1, 3))
        self.clear()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SoundSourceLocalization3D()
    window.show()
    sys.exit(app.exec_())