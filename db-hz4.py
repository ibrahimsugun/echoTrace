import numpy as np
import matplotlib.pyplot as plt

# Sabit frekans ve başlangıç desibeli
frequency = 1000  # 1000 Hz sabit frekans
initial_db = 120  # 120 dB başlangıç ses şiddeti (patlama)

# Mesafeler (1 metre ile 100 metre arasında)
distances = np.linspace(1, 100, 500)

# Hava koşulları (sıcaklık ve nem)
temperature = 20  # Sıcaklık (°C)
humidity = 50     # Bağıl nem (%)

# Sabit ortam gürültüsü (örneğin ofis ortamı, 40 dB)
ambient_noise_db = 40

# Sesin sıcaklığa bağlı hızı (m/s)
def sound_speed(temperature):
    return 331.3 + 0.606 * temperature

# Hava emilim katsayısı (frekansta ve hava koşullarında zayıflama) - basit model
def air_absorption_coefficient(frequency, temperature, humidity):
    # Bu formül, sesin havadaki zayıflaması için basit bir modeldir
    # Daha karmaşık bir model eklenebilir.
    return 0.01 * frequency * (humidity / 100) * (temperature / 20)  # Örnek emilim katsayısı

# Sesin mesafeye göre desibel zayıflaması (hava koşullarına bağlı)
def calculate_db_with_air_absorption(initial_db, distance, ambient_noise_db, temperature, humidity, frequency):
    # Temel desibel düşüşü (Inverse Square Law)
    db_without_noise = initial_db - 20 * np.log10(distance)
    
    # Hava emilimi (frekansta zayıflama)
    air_absorption = air_absorption_coefficient(frequency, temperature, humidity)
    db_after_air_absorption = db_without_noise - air_absorption * distance  # Hava emilimine bağlı düşüş
    
    # Ortam gürültüsüyle birlikte toplam desibel
    total_db = 10 * np.log10(10**(db_after_air_absorption / 10) + 10**(ambient_noise_db / 10))
    return total_db

# Her mesafe için desibel seviyesini hesaplayalım (hava emilimi dahil)
db_levels_with_air_absorption = calculate_db_with_air_absorption(initial_db, distances, ambient_noise_db, temperature, humidity, frequency)

# Grafik oluşturma
plt.figure(figsize=(10, 6))
plt.plot(distances, db_levels_with_air_absorption, label=f"Frequency: {frequency} Hz, Temp: {temperature}°C, Humidity: {humidity}%", color='b')

# Grafik özellikleri
plt.title("Mesafe, Sıcaklık ve Nem ile Desibel Seviyesi")
plt.xlabel("Mesafe (metre)")
plt.ylabel("Desibel (dB)")
plt.grid(True)
plt.legend()
plt.show()
