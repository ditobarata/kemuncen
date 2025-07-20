# ds3231.py - Library untuk DS3231 Real Time Clock

from machine import Pin, I2C, RTC # <-- Tambahkan RTC di sini
import time # Import time untuk time.localtime() dan time.sleep()

# Alamat I2C default untuk DS3231
DS3231_I2C_ADDR = 0x68

class DS3231:
    def __init__(self, pin_sda=21, pin_scl=22):
        i2c = I2C(1, scl=Pin(pin_scl), sda=Pin(pin_sda), freq=400000) # freq=400kHz direkomendasikan
        self.i2c = i2c
        # Pastikan DS3231 terdeteksi di bus I2C
        if DS3231_I2C_ADDR not in self.i2c.scan():
            raise RuntimeError("DS3231 tidak ditemukan pada bus I2C. Pastikan koneksi benar.")

    def _bcd2dec(self, bcd):
        return (bcd // 16) * 10 + (bcd % 16)

    def _dec2bcd(self, dec):
        return (dec // 10) * 16 + (dec % 16)

    def _read_time_raw(self):
        """Membaca 7 byte waktu dari DS3231 (detik, menit, jam, hari, tanggal, bulan, tahun)"""
        return self.i2c.readfrom_mem(DS3231_I2C_ADDR, 0x00, 7)

    def get_time(self):
        """
        Mengambil waktu saat ini dari DS3231.
        Mengembalikan tuple: (tahun, bulan, tanggal, jam, menit, detik, hari_dalam_minggu, hari_dalam_tahun)
        Hari dalam minggu: Senin=0, Selasa=1, ..., Minggu=6
        """
        buf = self._read_time_raw()

        second = self._bcd2dec(buf[0] & 0x7F)
        minute = self._bcd2dec(buf[1] & 0x7F)
        
        # Penanganan format 12/24 jam dan AM/PM (jika bit 6 disetel)
        hour_byte = buf[2]
        if hour_byte & 0x40: # Cek bit 6 (format 12 jam)
            # Konversi dari format 12-jam ke 24-jam
            hour = self._bcd2dec(hour_byte & 0x1F) # Hapus bit 6 dan 7
            if hour_byte & 0x80: # Cek bit 7 (PM)
                if hour != 12: # 12 PM tetap 12
                    hour += 12
            else: # AM
                if hour == 12: # 12 AM menjadi 0 (tengah malam)
                    hour = 0
        else: # Format 24 jam
            hour = self._bcd2dec(hour_byte & 0x3F) # Hapus bit 6 dan 7

        day_of_week = self._bcd2dec(buf[3] & 0x07) - 1 # DS3231: 1=Minggu, ..., 7=Sabtu. Ubah ke 0=Senin, ..., 6=Minggu
        if day_of_week == -1: # Koreksi jika hasilnya -1 (saat DS3231 membaca Minggu=1)
            day_of_week = 6
            
        date = self._bcd2dec(buf[4] & 0x3F)
        
        month_byte = buf[5]
        century = 0
        if month_byte & 0x80: # Cek bit 7 (Century bit)
            century = 100 # Jika disetel, tambahkan 100 tahun
        month = self._bcd2dec(month_byte & 0x1F)
        
        year_raw = self._bcd2dec(buf[6])
        year = 2000 + year_raw + century # Tambahkan 2000 dan century jika ada

        # Kita perlu menghitung hari_dalam_tahun secara manual jika diperlukan
        # Untuk saat ini, kita kembalikan 0.

        # Mengembalikan format yang kompatibel dengan time.localtime()
        # (year, month, mday, hour, minute, second, weekday, yearday)
        return (year, month, date, hour, minute, second, day_of_week, 0)

    def set_time(self, year, month, date, hour, minute, second, day_of_week=0):
        """
        Mengatur waktu pada DS3231.
        day_of_week: Senin=0, Selasa=1, ..., Minggu=6 (akan dikonversi ke format DS3231)
        """
        # Konversi hari_dalam_minggu ke format DS3231 (1=Minggu, 2=Senin, ...)
        # MicroPython: 0=Senin, 6=Minggu. DS3231: 1=Minggu, 2=Senin, ..., 7=Sabtu.
        # Jadi, jika MicroPython day=0 (Senin), DS3231 day=2.
        # Jika MicroPython day=6 (Minggu), DS3231 day=1.
        if day_of_week == 6: # Jika Minggu
            ds_day_of_week = 1
        else:
            ds_day_of_week = day_of_week + 2

        buf = bytearray(7)
        buf[0] = self._dec2bcd(second)
        buf[1] = self._dec2bcd(minute)
        buf[2] = self._dec2bcd(hour)
        buf[3] = self._dec2bcd(ds_day_of_week) # Hari dalam seminggu (1=Minggu, 7=Sabtu)
        buf[4] = self._dec2bcd(date)
        
        # Menangani bit abad (century bit)
        century_bit = 0x00
        if year >= 2100: # Jika tahun 2100 atau lebih, set bit abad
            century_bit = 0x80
            year_to_set = year - 100 # Kurangi 100 untuk menyimpan 2 digit terakhir tahun
        else:
            year_to_set = year
        
        buf[5] = self._dec2bcd(month) | century_bit
        buf[6] = self._dec2bcd(year_to_set % 100) # Hanya 2 digit terakhir tahun

        self.i2c.writeto_mem(DS3231_I2C_ADDR, 0x00, buf)

    def get_temperature(self):
        """
        Mengambil suhu dari DS3231.
        Mengembalikan suhu dalam derajat Celsius.
        """
        # Suhu disimpan di register 0x11 dan 0x12 (MSB, LSB)
        buf = self.i2c.readfrom_mem(DS3231_I2C_ADDR, 0x11, 2)
        temp_msb = buf[0]
        temp_lsb = buf[1] >> 6 # Hanya 2 bit paling signifikan

        temperature = temp_msb + (temp_lsb * 0.25)
        return temperature

    def sync_to_rtc(self):
        """
        Menyinkronkan waktu RTC internal ESP32 dengan waktu dari DS3231.
        """
        # Pastikan modul 'machine' sudah diimpor secara global di file ini
        rtc = RTC() 
        ds_time = self.get_time()
        # Mengatur RTC internal dengan waktu dari DS3231
        # Perhatikan: ds_time (yang dari get_time) adalah (year, month, mday, hour, minute, second, weekday, yearday)
        # RTC.datetime() mengharapkan (year, month, mday, weekday, hour, minute, second, microsecond)
        rtc.datetime((ds_time[0], ds_time[1], ds_time[2], ds_time[6], ds_time[3], ds_time[4], ds_time[5], 0))
        print("Waktu RTC internal ESP32 telah disinkronkan dengan DS3231.")

# --- Contoh Penggunaan Langsung (hanya berjalan jika skrip ini dieksekusi langsung) ---
if __name__ == "__main__":
    print("Menjalankan contoh penggunaan DS3231...")

    # Buat objek DS3231
    try:
        rtc_ds3231 = DS3231()
        print("DS3231 berhasil diinisialisasi dan ditemukan.")
    except RuntimeError as e:
        print(f"Error: {e}")
        print("Pastikan DS3231 terhubung dengan benar dan pin I2C sudah sesuai.")
        exit() # Keluar jika RTC tidak ditemukan

    # --- Mengatur Waktu (Uncomment baris di bawah untuk mengatur waktu) ---
    # **** PENTING: Atur waktu DS3231 Anda di sini! ****
    # Gunakan waktu saat ini (Minggu, 20 Juli 2025, 11:26:22 AM WIB).
    # Parameter: (tahun, bulan, tanggal, jam_24_jam, menit, detik, hari_minggu_micropython)
    # Hari minggu di MicroPython: Senin=0, Selasa=1, ..., Minggu=6
    
    # ATUR WAKTU INI HANYA SEKALI ATAU SAAT BATERAI RTC ANDA HABIS!
    # Anda bisa uncomment baris di bawah, jalankan skrip, kemudian comment lagi.
    # rtc_ds3231.set_time(2025, 7, 20, 11, 26, 22, 6) # Tahun, Bulan, Tanggal, Jam, Menit, Detik, Hari (6=Minggu)
    # print("Waktu DS3231 telah diatur ke 2025/07/20 11:26:22 (Minggu).")
    # time.sleep(1) # Beri waktu sebentar agar RTC sempat diatur

    # --- Membaca Waktu ---
    print("\n--- Membaca waktu dari DS3231 ---")
    current_time_ds3231 = rtc_ds3231.get_time()
    year, month, date, hour, minute, second, day_of_week, _ = current_time_ds3231

    days = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
    print(f"Waktu DS3231: {days[day_of_week]}, {date:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}:{second:02d}")

    # --- Membaca Suhu ---
    print("\n--- Membaca suhu dari DS3231 ---")
    temperature = rtc_ds3231.get_temperature()
    print(f"Suhu DS3231: {temperature:.2f} °C")

    # --- Menyinkronkan waktu RTC internal ESP32 dengan DS3231 ---
    print("\n--- Menyinkronkan RTC internal ESP32 dengan DS3231 ---")
    rtc_ds3231.sync_to_rtc()

    # --- Verifikasi waktu RTC internal ESP32 ---
    print("\n--- Waktu RTC internal ESP32 setelah sinkronisasi ---")
    rtc_internal = RTC()
    current_time_internal = rtc_internal.datetime()
    # rtc_internal.datetime() mengembalikan (year, month, mday, weekday, hour, minute, second, microsecond)
    year_int, month_int, date_int, day_of_week_int, hour_int, minute_int, second_int, _ = current_time_internal
    print(f"Waktu RTC Internal ESP32: {days[day_of_week_int]}, {date_int:02d}/{month_int:02d}/{year_int} {hour_int:02d}:{minute_int:02d}:{second_int:02d}")

    print("\nMemulai loop pembacaan waktu setiap 5 detik (tekan Ctrl+C untuk berhenti)...")
    while True:
        current_time_ds3231 = rtc_ds3231.get_time()
        year, month, date, hour, minute, second, day_of_week, _ = current_time_ds3231
        print(current_time_ds3231)
        print(f"DS3231: {days[day_of_week]}, {date:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}:{second:02d}")
        time.sleep(5)