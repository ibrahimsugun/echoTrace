import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from matplotlib.widgets import Button

# Ses hızı
SOUND_SPEED = 343

# Mikrofonların konumları (Aynı kaldı)
mic_positions = np.array([
    [0, 0],    # Sol alt
    [10, 0],   # Sağ alt
    [0, 10],   # Sol üst
    [10, 10]   # Sağ üst
])

# Ses kaynağı ve tahmin edilen nokta (Başlangıçta boş)
source_point = None
estimated_point = None

def calculate_distance(mic_pos, source_pos):
    """Mikrofon ile ses kaynağı arasındaki mesafeyi hesaplar."""
    return np.sqrt((mic_pos[0] - source_pos[0]) ** 2 + (mic_pos[1] - source_pos[1]) ** 2)

def time_to_distance(time, sound_speed):
    """Zaman farkını mesafeye çevirir."""
    return time * sound_speed

def tdoa_loss(source_pos, mic_positions, time_stamps):
    """Ses kaynağı koordinatlarının tahmini için kayıp fonksiyonu."""
    ref_mic_pos = mic_positions[0]  # Referans mikrofon
    total_loss = 0.0
    for i in range(1, len(mic_positions)):
        # Gerçek mesafe farkı
        observed_delta_d = (time_stamps[i] - time_stamps[0]) * SOUND_SPEED

        # Tahmin edilen mesafe farkı
        dist_ref = calculate_distance(ref_mic_pos, source_pos)
        dist_i = calculate_distance(mic_positions[i], source_pos)
        predicted_delta_d = dist_i - dist_ref

        # Kayıp hesaplaması
        residual = observed_delta_d - predicted_delta_d
        total_loss += residual ** 2

    return total_loss

def find_sound_source(mic_positions, time_stamps):
    """Ses kaynağının konumunu optimize eder."""
    initial_guess = [5, 5]  # Başlangıç tahmini

    result = minimize(tdoa_loss, initial_guess, args=(mic_positions, time_stamps), method='Nelder-Mead')

    return result.x  # Tahmin edilen ses kaynağının koordinatları

def on_click(event):
    global source_point, estimated_point
    # Fare tıklama pozisyonu ses kaynağı olarak belirlenir
    if event.inaxes:
        source_point = [event.xdata, event.ydata]
        time_stamps = np.array([calculate_distance(mic, source_point) / SOUND_SPEED for mic in mic_positions])
        estimated_point = find_sound_source(mic_positions, time_stamps)
        update_plot()

def update_plot():
    """Grafiği günceller ve ses kaynağı ile tahmini konumu gösterir."""
    ax.clear()

    # Mikrofonları göster
    ax.scatter(mic_positions[:, 0], mic_positions[:, 1], color='blue', label="Mikrofonlar")
    for i, pos in enumerate(mic_positions):
        ax.text(pos[0], pos[1], f'M{i+1}', fontsize=12, ha='right')

    # Eğer ses kaynağı seçilmişse göster (Kırmızı nokta, büyük boyutta)
    if source_point is not None:
        ax.scatter(*source_point, color='red', label="Gerçek Ses Kaynağı", s=200)  # Kırmızı nokta büyük boyut

    # Tahmin edilen ses kaynağını göster (Yeşil nokta, daha küçük boyutta)
    if estimated_point is not None:
        ax.scatter(*estimated_point, color='green', label="Tahmin Edilen Ses Kaynağı", s=100)  # Yeşil nokta küçük boyut

    # Eksen ayarları
    ax.set_xlim(-20, 30)
    ax.set_ylim(-20, 30)
    ax.set_xticks(np.arange(-20, 31, 5))  # X ekseninde 5 birimde bir çizgi
    ax.set_yticks(np.arange(-20, 31, 5))  # Y ekseninde 5 birimde bir çizgi
    ax.grid(True)
    ax.set_xlabel('X Koordinatı')
    ax.set_ylabel('Y Koordinatı')

    ax.set_title('Ses Kaynağı Simülasyonu')
    ax.legend()
    plt.draw()

def clear(event):
    """Tüm işaretleri temizler."""
    global source_point, estimated_point
    source_point = None
    estimated_point = None
    update_plot()

# Grafik oluşturma
fig, ax = plt.subplots(figsize=(8, 8))  # Grafiğin boyutunu ayarladık
plt.subplots_adjust(bottom=0.2)

# "Sil" butonunu ekleyin
ax_clear = plt.axes([0.8, 0.05, 0.1, 0.075])
button_clear = Button(ax_clear, 'Sil')
button_clear.on_clicked(clear)

# Fare tıklamaları ile ses kaynağını belirleme
fig.canvas.mpl_connect('button_press_event', on_click)

# Başlangıç grafiği
update_plot()
plt.show()
