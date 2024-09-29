import numpy as np
import matplotlib.pyplot as plt

# Sabit frekans (Hz) ve başlangıç desibeli
frequency = 1000  # 1000 Hz sabit frekans
initial_db = 120  # 120 dB başlangıç (yakın mesafedeki) ses şiddeti

# Mesafeler (1 metre ile 100 metre arasında)
distances = np.linspace(1, 100, 500)  # 1 metreden 100 metreye kadar mesafeler

# Desibel hesaplaması (Inverse Square Law)
def calculate_db(initial_db, distance):
    return initial_db - 20 * np.log10(distance)

# Her mesafe için desibel seviyesini hesaplayalım
db_levels = calculate_db(initial_db, distances)

# Grafik oluşturma
plt.figure(figsize=(10, 6))
plt.plot(distances, db_levels, label=f"Frequency: {frequency} Hz", color='b')

# Grafik özellikleri
plt.title("Mesafeye Göre Desibel Seviyesi (Ses Şiddeti)")
plt.xlabel("Mesafe (metre)")
plt.ylabel("Desibel (dB)")
plt.grid(True)
plt.legend()
plt.show()
