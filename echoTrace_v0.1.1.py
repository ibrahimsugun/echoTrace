import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from matplotlib.widgets import Button

# Ses hızı
SOUND_SPEED = 343

# Mikrofonların konumları
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
    """Ses kaynağı koordinatlarının tahmini için loss fonksiyonu."""
    ref_mic_pos = mic_positions[0]  # Referans mikrofon
    ref_time = time_stamps[0]  # Referans mikrofonun zaman ölçümü
    
    total_loss = 0.0
    for i in range(1, len(mic_positions)):
        delta_t = time_stamps[i] - ref_time
        delta_d = time_to_distance(delta_t, SOUND_SPEED)

        dist_ref = calculate_distance(ref_mic_pos, source_pos)
        dist_other = calculate_distance(mic_positions[i], source_pos)

        total_loss += (dist_other - dist_ref - delta_d) ** 2
    
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
    
    ax.set_xlim(-1, 11)
    ax.set_ylim(-1, 11)
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
fig, ax = plt.subplots()
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
