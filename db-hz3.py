import numpy as np
import matplotlib.pyplot as plt

# Sabit frekans ve başlangıç desibeli
frequency = 1000  # 1000 Hz sabit frekans
initial_db = 120  # 120 dB başlangıç ses şiddeti (patlama)

# Mesafeler (1 metre ile 100 metre arasında)
distances = np.linspace(1, 100, 500)

# Sabit ortam gürültüsü (örneğin ofis ortamı, 40 dB)
ambient_noise_db = 40

# Farklı malzemelerin emilim katsayıları (örnek malzemeler)
materials_absorption = {
    'Beton Duvar': 0.05,
    'Kumaş Kaplı Yüzey': 0.3,
    'Halı': 0.6,
    'Ses Emici Paneller': 0.9
}

# Seçilen malzeme (emilim katsayısı)
chosen_material = 'Halı'  # Bu malzemeyi simülasyon için seçiyoruz
absorption_coefficient = materials_absorption[chosen_material]

# Engel nedeniyle sesin zayıflaması (örneğin, duvar veya zemin malzemesi)
def calculate_db_with_absorption(initial_db, distance, ambient_noise_db, absorption_coefficient):
    # Temel desibel düşüşü (Inverse Square Law)
    db_without_noise = initial_db - 20 * np.log10(distance)
    
    # Emilim katsayısına göre sesin zayıflaması
    db_after_absorption = db_without_noise * (1 - absorption_coefficient)
    
    # Ortam gürültüsüyle birlikte toplam desibel
    total_db = 10 * np.log10(10**(db_after_absorption / 10) + 10**(ambient_noise_db / 10))
    return total_db

# Her mesafe için desibel seviyesini hesaplayalım (emilim katsayısı dahil)
db_levels_with_absorption = calculate_db_with_absorption(initial_db, distances, ambient_noise_db, absorption_coefficient)

# Grafik oluşturma
plt.figure(figsize=(10, 6))
plt.plot(distances, db_levels_with_absorption, label=f"Material: {chosen_material}, Frequency: {frequency} Hz", color='r')

# Grafik özellikleri
plt.title(f"Mesafe, {chosen_material} ve Ortam Gürültüsüne Göre Desibel Seviyesi")
plt.xlabel("Mesafe (metre)")
plt.ylabel("Desibel (dB)")
plt.grid(True)
plt.legend()
plt.show()
