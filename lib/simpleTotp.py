# simple_totp.py - Pustaka TOTP sederhana untuk integer 0-63

from ds3231 import DS3231 # Mengimpor kelas DS3231 yang sudah dimodifikasi
from machine import Pin, I2C # Diperlukan untuk inisialisasi I2C jika diuji langsung
import time, logging

class SimpleTOTP:
    def __init__(self, rtc_ds3231, secret_key, time_step_seconds=60):
        """
        Inisialisasi generator TOTP.
        :param rtc_ds3231: Objek DS3231 yang sudah diinisialisasi.
        :param secret_key: Kunci rahasia integer. Harus sama di kedua sisi (generator dan verifikator).
                           Nilai yang direkomendasikan adalah integer yang cukup acak.
        :param time_step_seconds: Interval waktu (dalam detik) di mana sandi akan berubah. Default 60 detik (1 menit).
        """
        if not isinstance(rtc_ds3231, DS3231):
            raise TypeError("rtc_ds3231 harus merupakan instance dari kelas DS3231.")
        if not isinstance(secret_key, int) or not (0 <= secret_key < 2**32): # Batasi secret_key agar wajar
             raise ValueError("secret_key harus integer positif.")
        if not isinstance(time_step_seconds, int) or time_step_seconds <= 0:
            raise ValueError("time_step_seconds harus integer positif.")

        self.rtc_ds3231 = rtc_ds3231
        self.secret_key = secret_key
        self.time_step_seconds = time_step_seconds
        self.max_password_value = 63 # 2^6 - 1
        self.password = 0
        self.kode_ketuk = "......"

    def generate_password(self):
        """
        Menghasilkan sandi TOTP berupa integer 0-63.
        """
        # Dapatkan Unix epoch time dari DS3231
        current_unix_time = self.rtc_ds3231.get_unix_time()

        # Hitung counter waktu (T)
        # Ini adalah jumlah interval waktu yang telah berlalu sejak epoch
        time_counter = current_unix_time // self.time_step_seconds

        # Algoritma sederhana untuk TOTP (modifikasi)
        # Kita akan menggunakan XOR dengan secret_key dan kemudian modulo 64
        # untuk mendapatkan nilai antara 0 dan 63.
        # Penggunaan XOR sangat sensitif terhadap perubahan bit, yang membantu dalam randomness.
        self.password = (time_counter ^ self.secret_key) % (self.max_password_value + 1)
        self.kode_ketuk = self.integer_to_custom_binary_string(self.password)
        
    def integer_to_custom_binary_string(self, value):
        """
        Mengubah nilai integer (0-63) menjadi representasi biner 6-bit
        dengan '.' sebagai 0 dan '-' sebagai 1.

        Args:
            value (int): Nilai integer antara 0 dan 63.

        Returns:
            str: Representasi biner kustom.
        Raises:
            ValueError: Jika nilai di luar rentang 0-63.
        """
        if not (0 <= value <= 63):
            raise ValueError("Nilai harus dalam rentang 0 hingga 63.")

        # Ubah integer ke string biner tanpa '0b'
        binary_string_raw = bin(value)[2:]

        # Lakukan padding nol di depan secara manual hingga panjang 6 bit
        # Jika panjang kurang dari 6, tambahkan '0' di depan
        padded_binary_string = '0' * (6 - len(binary_string_raw)) + binary_string_raw

        # Ganti '0' dengan '.' dan '1' dengan '-'
        custom_binary_string = ""
        for bit in padded_binary_string: # Gunakan string yang sudah di-padding
            if bit == '0':
                custom_binary_string += '.'
            elif bit == '1':
                custom_binary_string += '-'
        custom_binary_string += '.'
        
        return custom_binary_string    

# --- Contoh Penggunaan Langsung (hanya berjalan jika skrip ini dieksekusi langsung) ---
if __name__ == "__main__":
    print("Menjalankan contoh penggunaan SimpleTOTP...")

    try:
        rtc = DS3231()
        print("DS3231 berhasil diinisialisasi.")
    except RuntimeError as e:
        print(f"Error DS3231: {e}")
        print("Pastikan DS3231 terhubung.")
        exit()

    # --- PENTING: ATUR WAKTU DS3231 jika belum akurat ---
    # rtc.set_time(2025, 7, 20, 11, 59, 0, 0) # Tahun, Bulan, Tanggal, Jam, Menit, Detik, Hari (0=Minggu)
    # time.sleep(1) # Beri waktu DS3231 untuk menyimpan

    print(f"Waktu DS3231 saat ini: {rtc.get_time()}")
    print(f"Unix Epoch Time dari DS3231: {rtc.get_unix_time()}")
    print(f"Waktu Internal RTC ESP32: {time.localtime()}")

    # --- Inisialisasi SimpleTOTP ---
    # Ganti SECRET_KEY ini dengan nilai yang unik dan rahasia!
    # Kunci ini harus sama di sisi ESP32 dan verifikator.
    MY_SECRET_KEY = 123456789 # Contoh kunci rahasia
    TOTP_TIME_STEP = 60      # 60 detik (1 menit)

    totp_generator = SimpleTOTP(rtc, MY_SECRET_KEY, TOTP_TIME_STEP)
    print(f"\nSimpleTOTP diinisialisasi dengan kunci rahasia: {MY_SECRET_KEY} dan time step: {TOTP_TIME_STEP}s")

    print("\n--- Generating TOTP Passwords setiap 5 detik (Ctrl+C untuk berhenti) ---")
    last_password = -1
    while True:
        totp_generator.generate_password()
        #current_time_str = time.strftime('%H:%M:%S', time.localtime(rtc.get_unix_time()))
        
        if totp_generator.password != last_password:
            print(f"Sandi Baru: {totp_generator.kode_ketuk} (Perubahan!)")
            last_password = totp_generator.password
        else:
            print(f"Sandi Saat Ini: {totp_generator.kode_ketuk}")
            
        time.sleep(5)