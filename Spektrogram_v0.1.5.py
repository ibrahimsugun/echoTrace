import sys
import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from scipy.signal import spectrogram  # fftpack kaldırıldı
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QTextEdit,
    QMessageBox, QInputDialog, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class SingleMicrophoneApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Tek Mikrofonla Ses Kaydı ve Spektrogram')
        self.setGeometry(100, 100, 1600, 900)  # Başlangıç boyutunu artırdık

        # Ses kayıt parametreleri
        self.fs = 44100  # Örnekleme frekansı (Hz)
        self.duration = 1.0  # Kayıt süresi (saniye)

        # Zaman serisi verileri
        self.time_data = []        # Saniye cinsinden zaman verisi
        self.dominant_freqs = []   # Dominant frekanslar

        # Timer
        self.timer = QTimer()
        self.timer.setInterval(int(self.duration * 1000))  # milisaniye cinsinden
        self.timer.timeout.connect(self.record_and_plot)

        # UI'yi oluştur
        self.initUI()
        self.list_audio_devices()

    def initUI(self):
        # Ana widget ve layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)

        main_layout = QHBoxLayout(self.main_widget)

        # Sol tarafta grafik alanı (spektrogram, frekans spektrumu ve zaman serisi)
        plot_layout = QVBoxLayout()

        # Spektrogram için Figure ve Canvas
        self.figure_spectrogram = Figure(constrained_layout=True)
        self.ax_spectrogram = self.figure_spectrogram.add_subplot(111)
        self.canvas_spectrogram = FigureCanvas(self.figure_spectrogram)
        self.canvas_spectrogram.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_layout.addWidget(QLabel("Spektrogram"))
        plot_layout.addWidget(self.canvas_spectrogram)

        # Frekans Spektrumu için Figure ve Canvas
        self.figure_spectrum = Figure(constrained_layout=True)
        self.ax_spectrum = self.figure_spectrum.add_subplot(111)
        self.canvas_spectrum = FigureCanvas(self.figure_spectrum)
        self.canvas_spectrum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_layout.addWidget(QLabel("Frekans Spektrumu"))
        plot_layout.addWidget(self.canvas_spectrum)

        # Zaman Serisi (Dominant Frekanslar) için Figure ve Canvas
        self.figure_time_series = Figure(constrained_layout=True)
        self.ax_time_series = self.figure_time_series.add_subplot(111)
        self.canvas_time_series = FigureCanvas(self.figure_time_series)
        self.canvas_time_series.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_layout.addWidget(QLabel("Dominant Frekans Zaman Serisi"))
        plot_layout.addWidget(self.canvas_time_series)

        # Sağ tarafta kontrol paneli
        control_layout = QVBoxLayout()

        # Ses aygıtlarını listeleyen widget
        control_layout.addWidget(QLabel("Mevcut Ses Giriş Aygıtları:"))
        self.device_list_widget = QListWidget()
        self.device_list_widget.setSelectionMode(QListWidget.SingleSelection)
        control_layout.addWidget(self.device_list_widget)

        # Mikrofon sayısı seçimi (Tek mikrofon için zorunlu)
        control_layout.addWidget(QLabel("Kullanılacak Mikrofon Sayısı:"))
        self.mic_count_label = QLabel("1")
        control_layout.addWidget(self.mic_count_label)

        # "Kalibrasyon Yap" butonu (Opsiyonel)
        self.calibrate_button = QPushButton("Kalibrasyon Yap")
        self.calibrate_button.clicked.connect(self.calibrate)
        control_layout.addWidget(self.calibrate_button)

        # "Başlat" butonu
        self.start_button = QPushButton("Ses Kaydını Başlat")
        self.start_button.clicked.connect(self.start_recording)
        control_layout.addWidget(self.start_button)

        # "Durdur" butonu
        self.stop_button = QPushButton("Durdur")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_recording)
        control_layout.addWidget(self.stop_button)

        # "Sil" butonu
        self.clear_button = QPushButton("Grafikleri Temizle")
        self.clear_button.clicked.connect(self.clear_plots)
        control_layout.addWidget(self.clear_button)

        # Hesaplama adımları metin kutusu
        control_layout.addWidget(QLabel("Hesaplama Adımları:"))
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        control_layout.addWidget(self.log_text_edit)

        # Spacer ekleme
        control_layout.addStretch()

        # Layoutları yerleştirme
        main_layout.addLayout(plot_layout, 70)  # Grafik alanına %70 yer ver
        main_layout.addLayout(control_layout, 30)  # Kontrol paneline %30 yer ver

        # FigureCanvas'ların boyutlandırma politikasını ayarlama
        self.canvas_spectrogram.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_spectrum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_time_series.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Zaman Serisi Grafiği Başlangıç Ayarları
        self.ax_time_series.set_xlabel('Zaman [s]')
        self.ax_time_series.set_ylabel('Dominant Frekans [Hz]')
        self.ax_time_series.set_title('Dominant Frekans Zaman Serisi')
        self.ax_time_series.set_xlim(0, 10)  # İlk 10 saniyeyi göstermek için
        self.ax_time_series.set_ylim(0, self.fs / 2)  # Yarı örnekleme frekansı maksimum
        self.ax_time_series.grid(True)
        self.time_line, = self.ax_time_series.plot([], [], 'r-o', markersize=4, linewidth=1)  # Başlangıçta boş çizgi

        self.canvas_time_series.draw()

    def list_audio_devices(self):
        """
        Mevcut ses giriş aygıtlarını listeleyip kontrol paneline ekler.
        """
        self.device_list_widget.clear()
        devices = sd.query_devices()
        input_devices = [dev for dev in devices if dev['max_input_channels'] > 0]
        for idx, dev in enumerate(input_devices):
            item = QListWidgetItem(f"{idx}: {dev['name']} - Max Input Channels: {dev['max_input_channels']}")
            item.setData(Qt.UserRole, idx)
            self.device_list_widget.addItem(item)

    def calibrate(self):
        """
        Kalibrasyon işlemi yapar. (İsteğe bağlı)
        """
        # Kullanıcıdan bilinen mesafeyi al
        distance, ok = QInputDialog.getDouble(self, "Kalibrasyon", "Bilinen mesafeyi (cm) girin:", 100.0, 1.0, 10000.0, 2)
        if not ok:
            return

        self.log_text_edit.append(f"Kalibrasyon yapılıyor... Bilinen mesafe: {distance} cm")

        try:
            # Ses kaydı başlat
            device_index = self.get_selected_device()
            if device_index is None:
                self.show_error_message("Lütfen bir ses giriş aygıtı seçin.")
                return

            audio = sd.rec(int(self.duration * self.fs), samplerate=self.fs, channels=1, device=device_index)
            sd.wait()

            # Ses seviyesini hesaplama (RMS)
            rms = np.sqrt(np.mean(audio**2))
            self.log_text_edit.append(f"Kalibrasyon tamamlandı. Referans ses seviyesi (RMS): {rms:.6f}")
            self.log_text_edit.append("Artık spektrogram, frekans spektrumu ve zaman serisi analizleri yapılabilir.")
        except Exception as e:
            self.show_error_message(f"Kalibrasyon sırasında hata oluştu: {e}")

    def start_recording(self):
        """
        Ses kaydını başlatır.
        """
        if self.get_selected_device() is None:
            self.show_error_message("Lütfen bir ses giriş aygıtı seçin.")
            return

        self.timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.log_text_edit.append("Ses kaydı başlatıldı.")

    def stop_recording(self):
        """
        Ses kaydını durdurur.
        """
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.log_text_edit.append("Ses kaydı durduruldu.")

    def record_and_plot(self):
        """
        Ses kaydı yapar, spektrogramı, frekans spektrumunu ve zaman serisi grafiğini günceller.
        """
        try:
            device_index = self.get_selected_device()
            if device_index is None:
                self.show_error_message("Lütfen bir ses giriş aygıtı seçin.")
                return

            # Ses kaydı
            audio = sd.rec(int(self.duration * self.fs), samplerate=self.fs, channels=1, device=device_index)
            sd.wait()

            # Ses seviyesini hesaplama (RMS)
            rms = np.sqrt(np.mean(audio**2))
            self.log_text_edit.append(f"Ortalama Ses Seviyesi (RMS): {rms:.6f}")

            # Filtre uygulanmadan doğrudan sinyal kullanılıyor
            signal = audio[:, 0]

            # Spektrogramı hesapla ve çiz
            f, t, Sxx = spectrogram(signal, fs=self.fs)

            # Spektrogram çizimi
            self.ax_spectrogram.clear()
            self.ax_spectrogram.pcolormesh(t, f, 10 * np.log10(Sxx + 1e-10), shading='gouraud', cmap='viridis')
            self.ax_spectrogram.set_ylabel('Frekans [Hz]')
            self.ax_spectrogram.set_xlabel('Zaman [s]')
            self.ax_spectrogram.set_title('Spektrogram')
            self.ax_spectrogram.set_ylim([0, 5000])  # İstenilen frekans aralığını ayarlayın

            # Mevcut colorbar'ı temizle
            if hasattr(self, 'colorbar_spectrogram'):
                self.colorbar_spectrogram.remove()

            # Yeni colorbar ekle
            cmap_spectrogram = plt.get_cmap('viridis')
            mappable_spectrogram = plt.cm.ScalarMappable(cmap=cmap_spectrogram)
            mappable_spectrogram.set_array(Sxx)
            self.colorbar_spectrogram = self.figure_spectrogram.colorbar(mappable_spectrogram, ax=self.ax_spectrogram, label='Güç [dB]')
            self.canvas_spectrogram.draw()
            self.log_text_edit.append("Spektrogram güncellendi.")

            # FFT Hesaplaması ve Frekans Spektrumu Çizimi
            fft_vals = np.fft.fft(signal)
            fft_freq = np.fft.fftfreq(len(fft_vals), 1/self.fs)

            # Yalnızca pozitif frekansları al
            pos_mask = fft_freq >= 0
            fft_freq = fft_freq[pos_mask]
            fft_magnitude = np.abs(fft_vals[pos_mask]) * 2 / len(fft_vals)  # Normalizasyon

            # Dominant Frekansı Bulma
            dominant_freq = fft_freq[np.argmax(fft_magnitude)]
            self.time_data.append(len(self.time_data) + 1)  # Zaman verisi (saniye)
            self.dominant_freqs.append(dominant_freq)

            # Zaman Serisi Grafiği Güncelleme
            self.ax_time_series.clear()
            self.ax_time_series.set_xlabel('Zaman [s]')
            self.ax_time_series.set_ylabel('Dominant Frekans [Hz]')
            self.ax_time_series.set_title('Dominant Frekans Zaman Serisi')
            # Dinamik x limiti: en az 10 saniye veya mevcut zaman + 1
            current_time = self.time_data[-1]
            self.ax_time_series.set_xlim(0, max(10, current_time + 1))
            # Dinamik y limiti: mevcut en yüksek dominant frekans + %10 buffer
            current_max_freq = max(self.dominant_freqs) if self.dominant_freqs else self.fs / 2
            self.ax_time_series.set_ylim(0, current_max_freq * 1.1)
            self.ax_time_series.grid(True)
            self.ax_time_series.plot(self.time_data, self.dominant_freqs, 'r-o', markersize=4, linewidth=1)
            self.canvas_time_series.draw()

            # Frekans Spektrumu çizimi
            self.ax_spectrum.clear()
            self.ax_spectrum.plot(fft_freq, fft_magnitude, color='blue')
            self.ax_spectrum.set_ylabel('Genlik')
            self.ax_spectrum.set_xlabel('Frekans [Hz]')
            self.ax_spectrum.set_title('Frekans Spektrumu')
            self.ax_spectrum.set_xlim([0, 5000])  # İstenilen frekans aralığını ayarlayın

            self.canvas_spectrum.draw()
            self.log_text_edit.append("Frekans spektrumu güncellendi.")

        except Exception as e:
            self.show_error_message(f"Ses kaydı veya spektrogram oluşturma sırasında hata oluştu: {e}")

    def clear_plots(self):
        """
        Spektrogramı, frekans spektrumunu ve zaman serisi grafiğini temizler.
        """
        # Spektrogramı temizle
        self.ax_spectrogram.clear()
        self.ax_spectrogram.set_title('Spektrogram')
        self.ax_spectrogram.set_xlabel('Zaman [s]')
        self.ax_spectrogram.set_ylabel('Frekans [Hz]')
        self.ax_spectrogram.grid(True)
        self.canvas_spectrogram.draw()

        # Frekans spektrumunu temizle
        self.ax_spectrum.clear()
        self.ax_spectrum.set_title('Frekans Spektrumu')
        self.ax_spectrum.set_xlabel('Frekans [Hz]')
        self.ax_spectrum.set_ylabel('Genlik')
        self.ax_spectrum.grid(True)
        self.canvas_spectrum.draw()

        # Zaman Serisi Grafiğini temizle
        self.ax_time_series.clear()
        self.ax_time_series.set_title('Dominant Frekans Zaman Serisi')
        self.ax_time_series.set_xlabel('Zaman [s]')
        self.ax_time_series.set_ylabel('Dominant Frekans [Hz]')
        self.ax_time_series.set_xlim(0, 10)  # İlk 10 saniyeyi göstermek için
        self.ax_time_series.set_ylim(0, self.fs / 2)  # Y limiti
        self.ax_time_series.grid(True)
        self.canvas_time_series.draw()

        # Zaman serisi verilerini temizle
        self.time_data.clear()
        self.dominant_freqs.clear()

        self.log_text_edit.append("Spektrogram, frekans spektrumu ve zaman serisi grafikleri temizlendi.")

    def get_selected_device(self):
        """
        Seçilen ses giriş aygıtının indeksini döndürür.
        """
        selected_items = self.device_list_widget.selectedItems()
        if not selected_items:
            return None
        device_idx = selected_items[0].data(Qt.UserRole)
        return device_idx

    def show_error_message(self, message):
        """
        Hata mesajını bir ileti kutusunda gösterir.
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Hata")
        msg_box.setText("Bir hata oluştu:")
        msg_box.setInformativeText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

def main():
    app = QApplication(sys.argv)
    window = SingleMicrophoneApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
