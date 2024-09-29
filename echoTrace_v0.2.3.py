import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from matplotlib.widgets import Button
import matplotlib.animation as animation

# Ses hızı
SOUND_SPEED = 343

# Mikrofonların konumları
mic_positions = np.array([
    [0, 0],    # Mikrofon 1
    [10, 0],   # Mikrofon 2
    [0, 10],   # Mikrofon 3
    [10, 10]   # Mikrofon 4
])

# Ses kaynağı ve tahmin edilen nokta (Başlangıçta boş)
source_point = None
estimated_point = None
calculation_steps = ""  # Hesaplama adımlarını tutacak değişken

# Farenin konumu (Başlangıçta None)
mouse_x = None
mouse_y = None

def calculate_distance(mic_pos, source_pos):
    """Mikrofon ile ses kaynağı arasındaki mesafeyi hesaplar."""
    distance = np.sqrt((mic_pos[0] - source_pos[0]) ** 2 + (mic_pos[1] - source_pos[1]) ** 2)
    return distance

def tdoa_loss(source_pos, mic_positions, time_stamps):
    """Tüm mikrofon çiftleri arasındaki zaman farklarını kullanan kayıp fonksiyonu."""
    total_loss = 0.0
    steps = []  # Hesaplama adımlarını kaydetmek için liste
    num_mics = len(mic_positions)
    for i in range(num_mics):
        for j in range(i + 1, num_mics):
            # Gerçek mesafe farkı
            observed_delta_d = (time_stamps[i] - time_stamps[j]) * SOUND_SPEED

            # Tahmin edilen mesafe farkı
            dist_i = calculate_distance(mic_positions[i], source_pos)
            dist_j = calculate_distance(mic_positions[j], source_pos)
            predicted_delta_d = dist_i - dist_j

            # Kayıp hesaplaması
            residual = observed_delta_d - predicted_delta_d
            total_loss += residual ** 2

            # Hesaplama adımlarını kaydet
            step_info = (
                f"Çift ({i+1}, {j+1}):\n"
                f"  Zaman Farkı (t{i+1} - t{j+1}): {time_stamps[i] - time_stamps[j]:.6f} s\n"
                f"  Gerçek Mesafe Farkı (d{i+1} - d{j+1}): {observed_delta_d:.6f} m\n"
                f"  Tahmini Mesafe Farkı: {predicted_delta_d:.6f} m\n"
                f"  Kalan (Residual): {residual:.6f}\n"
            )
            steps.append(step_info)

    # Hesaplama adımlarını global değişkene aktar
    global calculation_steps
    calculation_steps = "\n".join(steps)

    return total_loss

def find_sound_source(mic_positions, time_stamps):
    """Ses kaynağının konumunu optimize eder."""
    initial_guess = [5, 5]  # Başlangıç tahmini

    result = minimize(tdoa_loss, initial_guess, args=(mic_positions, time_stamps), method='Nelder-Mead')

    return result.x  # Tahmin edilen ses kaynağının koordinatları

def on_mouse_move(event):
    """Farenin hareketini takip eder."""
    global mouse_x, mouse_y
    if event.inaxes == ax:
        mouse_x, mouse_y = event.xdata, event.ydata
    else:
        mouse_x, mouse_y = None, None

def update_data(frame):
    """Her saniye çalışarak hesaplamaları günceller."""
    global source_point, estimated_point, calculation_steps
    if mouse_x is not None and mouse_y is not None:
        source_point = [mouse_x, mouse_y]
        time_stamps = np.array([calculate_distance(mic, source_point) / SOUND_SPEED for mic in mic_positions])
        estimated_point = find_sound_source(mic_positions, time_stamps)
        update_plot()
        # Hesaplama adımlarını metin alanında güncelle
        text_box.set_text(f"Gerçek Ses Kaynağı: ({source_point[0]:.2f}, {source_point[1]:.2f})\n"
                          f"Tahmin Edilen Konum: ({estimated_point[0]:.2f}, {estimated_point[1]:.2f})\n\n"
                          f"Hesaplama Adımları:\n{calculation_steps}")
    else:
        # Fare grafiğin dışında ise metin alanını temizle
        calculation_steps = ""
        text_box.set_text("")
        source_point = None
        estimated_point = None
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
    xlim = [-20, 30]
    ylim = [-20, 30]
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_xticks(np.arange(-20, 31, 5))  # X ekseninde 5 birimde bir çizgi
    ax.set_yticks(np.arange(-20, 31, 5))  # Y ekseninde 5 birimde bir çizgi
    ax.grid(True)
    ax.set_xlabel('X Koordinatı')
    ax.set_ylabel('Y Koordinatı')

    ax.set_title('Ses Kaynağı Simülasyonu')
    ax.legend()
    plt.draw()

def clear(event):
    """Tüm işaretleri ve metin alanını temizler."""
    global source_point, estimated_point, calculation_steps, mouse_x, mouse_y
    source_point = None
    estimated_point = None
    calculation_steps = ""
    mouse_x = None
    mouse_y = None
    text_box.set_text("")
    update_plot()

# Grafik oluşturma
fig = plt.figure(figsize=(12, 8))
gs = fig.add_gridspec(1, 2, width_ratios=[2, 1])

# Grafik eksenleri
ax = fig.add_subplot(gs[0])
ax_text = fig.add_subplot(gs[1])
ax_text.axis('off')  # Metin alanında eksenleri gizle

# Metin kutusu oluşturma
text_box = ax_text.text(0, 1, "", fontsize=10, va='top', ha='left')

plt.subplots_adjust(bottom=0.2)

# "Sil" butonunu ekleyin
ax_clear = plt.axes([0.45, 0.05, 0.1, 0.075])  # Butonun yerini ayarladık
button_clear = Button(ax_clear, 'Sil')
button_clear.on_clicked(clear)

# Fare hareketlerini takip etme
fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)

# Her saniye update_data fonksiyonunu çağırmak için animasyon kullanın
ani = animation.FuncAnimation(fig, update_data, interval=1000)

# Başlangıç grafiği
update_plot()
plt.show()
