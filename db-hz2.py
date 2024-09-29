import numpy as np
import matplotlib.pyplot as plt

# Sabit frekans ve başlangıç desibeli
frequency = 1000  # 1000 Hz sabit frekans
initial_db = 120  # 120 dB başlangıç ses şiddeti (patlama)

# Mesafeler (1 metre ile 100 metre arasında)
distances = np.linspace(1, 100, 500)

# Sabit ortam gürültüsü (örneğin ofis ortamı, 40 dB)
ambient_noise_db = 40

# Engel nedeniyle sesin zayıflaması (örneğin bir duvar %50 ses kaybına neden olabilir)
wall_absorption = 0.5  # %50 zayıflama

# Desibel hesaplaması (Inverse Square Law + Engel Etkisi)
def calculate_db_with_obstacle(initial_db, distance, ambient_noise_db, wall_absorption):
    # Temel desibel düşüşü (Inverse Square Law)
    db_without_noise = initial_db - 20 * np.log10(distance)
    
    # Engel nedeniyle zayıflama
    db_after_obstacle = db_without_noise * (1 - wall_absorption)
    
    # Ortam gürültüsüyle birlikte toplam desibel
    total_db = 10 * np.log10(10**(db_after_obstacle / 10) + 10**(ambient_noise_db / 10))
    return total_db

# Her mesafe için desibel seviyesini hesaplayalım (engel etkisi dahil)
db_levels_with_noise = calculate_db_with_obstacle(initial_db, distances, ambient_noise_db, wall_absorption)

# Grafik oluşturma
plt.figure(figsize=(10, 6))
plt.plot(distances, db_levels_with_noise, label=f"Frequency: {frequency} Hz", color='g')

# Grafik özellikleri
plt.title("Mesafe, Engel ve Ortam Gürültüsüne Göre Desibel Seviyesi")
plt.xlabel("Mesafe (metre)")
plt.ylabel("Desibel (dB)")
plt.grid(True)
plt.legend()
plt.show()
