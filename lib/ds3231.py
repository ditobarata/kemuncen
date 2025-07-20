# ds3231.py - Library untuk DS3231 Real Time Clock

from machine import Pin, I2C, RTC
import time # Menggunakan time untuk time.mktime dan time.localtime

# Alamat I2C default untuk DS3231
DS3231_I2C_ADDR = 0x68

class DS3231:
    def __init__(self, pin_sda=21, pin_scl=22, freq=400000):
        i2c = I2C(1, scl=Pin(pin_scl), sda=Pin(pin_sda), freq=freq) 
        self.i2c = i2c
        if DS3231_I2C_ADDR not in self.i2c.scan():
            raise RuntimeError("DS3231 tidak ditemukan pada bus I2C. Pastikan koneksi benar.")

    def __repr__(self):
        try:
            year, month, date, hour, minute, second, day_of_week, _ = self.get_time()
            return f"DS3231(time='{year:04d}-{month:02d}-{date:02d} {hour:02d}:{minute:02d}:{second:02d}')"
        except Exception as e:
            return f"DS3231(Error membaca waktu: {e})"

    def _bcd2dec(self, bcd):
        return (bcd // 16) * 10 + (bcd % 16)

    def _dec2bcd(self, dec):
        return (dec // 10) * 16 + (dec % 16)

    def _read_time_raw(self):
        return self.i2c.readfrom_mem(DS3231_I2C_ADDR, 0x00, 7)

    def get_time(self):
        buf = self._read_time_raw()

        second = self._bcd2dec(buf[0] & 0x7F)
        minute = self._bcd2dec(buf[1] & 0x7F)
        
        hour_byte = buf[2]
        if hour_byte & 0x40:
            hour = self._bcd2dec(hour_byte & 0x1F)
            if hour_byte & 0x80:
                if hour != 12: hour += 12
            else:
                if hour == 12: hour = 0
        else:
            hour = self._bcd2dec(hour_byte & 0x3F)

        # Konversi day_of_week dari DS3231 (1=Minggu, 7=Sabtu) ke konvensi 0=Minggu, 6=Sabtu
        ds_day = self._bcd2dec(buf[3] & 0x07)
        if ds_day == 1: # DS3231 Minggu adalah indeks 0 kita
            day_of_week = 0
        elif ds_day == 7: # DS3231 Sabtu adalah indeks 6 kita
            day_of_week = 6
        else: # Senin (2) -> 1, Selasa (3) -> 2, dst.
            day_of_week = ds_day - 1 
            
        date = self._bcd2dec(buf[4] & 0x3F)
        
        month_byte = buf[5]
        century = 0
        if month_byte & 0x80: century = 100 
        month = self._bcd2dec(month_byte & 0x1F)
        
        year_raw = self._bcd2dec(buf[6])
        year = 2000 + year_raw + century 

        return (year, month, date, hour, minute, second, day_of_week, 0) # Hari dalam tahun selalu 0

    def set_time(self, year, month, date, hour, minute, second, day_of_week=0):
        # Konversi hari_dalam_minggu dari konvensi 0=Minggu, 6=Sabtu ke format DS3231 (1=Minggu, 7=Sabtu)
        if day_of_week == 0:
            ds_day_of_week = 1
        else:
            ds_day_of_week = day_of_week + 1

        buf = bytearray(7)
        buf[0] = self._dec2bcd(second)
        buf[1] = self._dec2bcd(minute)
        buf[2] = self._dec2bcd(hour)
        buf[3] = self._dec2bcd(ds_day_of_week) 
        buf[4] = self._dec2bcd(date)
        
        century_bit = 0x00
        if year >= 2100: 
            century_bit = 0x80
            year_to_set = year - 100 
        else:
            year_to_set = year
        
        buf[5] = self._dec2bcd(month) | century_bit
        buf[6] = self._dec2bcd(year_to_set % 100) 

        self.i2c.writeto_mem(DS3231_I2C_ADDR, 0x00, buf)

    def get_temperature(self):
        buf = self.i2c.readfrom_mem(DS3231_I2C_ADDR, 0x11, 2)
        temp_msb = buf[0]
        temp_lsb = buf[1] >> 6 
        temperature = temp_msb + (temp_lsb * 0.25)
        return temperature

    def get_unix_time(self):
        """
        Mengambil waktu dari DS3231 dan mengembalikannya sebagai Unix epoch timestamp (detik sejak 2000-01-01 00:00:00 UTC).
        MicroPython mktime dimulai dari 2000-01-01 00:00:00 UTC (bukan 1970).
        """
        year, month, date, hour, minute, second, day_of_week, _ = self.get_time()
        # time.mktime() mengharapkan tuple (year, month, mday, hour, minute, second, weekday, yearday)
        # Kita perlu mengkonversi weekday dari 0=Minggu ke 0=Senin (standar mktime)
        # DS3231: 0=Minggu, 1=Senin, ..., 6=Sabtu
        # mktime: 0=Senin, 1=Selasa, ..., 6=Minggu
        
        # Konversi day_of_week dari konvensi kita (0=Minggu, ..., 6=Sabtu) ke mktime (0=Senin, ..., 6=Minggu)
        if day_of_week == 0: # Minggu
            mktime_weekday = 6 # mktime Minggu
        else:
            mktime_weekday = day_of_week - 1 # Senin (1) -> 0, Selasa (2) -> 1, dst.
            
        return time.mktime((year, month, date, hour, minute, second, mktime_weekday, 0))

    def sync_to_rtc(self):
        rtc = RTC() 
        ds_time = self.get_time()
        # ds_time: (year, month, mday, hour, minute, second, weekday(0=Minggu), yearday)
        # RTC.datetime(): (year, month, mday, weekday(0=Senin), hour, minute, second, microsecond)
        
        # Konversi weekday dari 0=Minggu ke 0=Senin untuk RTC.datetime()
        if ds_time[6] == 0: # Jika DS3231 Minggu (indeks 0)
            rtc_weekday = 6 # Jadi Minggu di RTC.datetime() (indeks 6)
        else:
            rtc_weekday = ds_time[6] - 1 # Senin (1) -> 0, Selasa (2) -> 1, dst.
            
        rtc.datetime((ds_time[0], ds_time[1], ds_time[2], rtc_weekday, ds_time[3], ds_time[4], ds_time[5], 0))
        print("Waktu RTC internal ESP32 telah disinkronkan dengan DS3231.")

# --- Contoh Penggunaan Langsung (hanya berjalan jika skrip ini dieksekusi langsung) ---
if __name__ == "__main__":
    # --- PENTING: ATUR WAKTU DS3231 PERTAMA KALI ATAU JIKA BATERAI HABIS ---
    # Gunakan waktu saat ini.
    # Contoh: Minggu, 20 Juli 2025, 11:59:00 WIB
    # Perhatikan day_of_week: Minggu=0, Senin=1, ..., Sabtu=6
    # Uncomment baris di bawah, sesuaikan waktu saat ini, jalankan sekali, lalu comment lagi.
    # rtc_ds3231.set_time(2025, 7, 20, 11, 59, 0, 0) # Tahun, Bulan, Tanggal, Jam, Menit, Detik, Hari (0=Minggu)
    # print("Waktu DS3231 telah diatur ke 2025/07/20 11:59:00 (Minggu).")
    # time.sleep(1) 

    print("\n--- Membaca waktu dari DS3231 ---")
    rtc_ds3231 = DS3231()
    current_time_ds3231 = rtc_ds3231.get_time()
    year, month, date, hour, minute, second, day_of_week, _ = current_time_ds3231

    days = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"] 
    print(f"Waktu DS3231: {days[day_of_week]}, {date:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}:{second:02d}")

    print("\n--- Representasi objek DS3231 (memanggil __repr__) ---")
    print(rtc_ds3231) 
    print(repr(rtc_ds3231)) 

    print("\n--- Membaca suhu dari DS3231 ---")
    temperature = rtc_ds3231.get_temperature()
    print(f"Suhu DS3231: {temperature:.2f} °C")

    print("\n--- Menyinkronkan waktu RTC internal ESP32 dengan DS3231 ---")
    rtc_ds3231.sync_to_rtc()

    print("\n--- Verifikasi waktu RTC internal ESP32 ---")
    rtc_internal = RTC()
    current_time_internal = rtc_internal.datetime()
    year_int, month_int, date_int, day_of_week_int, hour_int, minute_int, second_int, _ = current_time_internal
    # Sesuaikan day_of_week_int dari mktime (0=Senin) ke konvensi kita (0=Minggu) untuk tampilan
    if day_of_week_int == 6: # mktime Minggu
        display_weekday = 0 # Konvensi kita Minggu
    else:
        display_weekday = day_of_week_int + 1 # mktime Senin (0) -> 1, dst.
    print(f"Waktu RTC Internal ESP32: {days[display_weekday]}, {date_int:02d}/{month_int:02d}/{year_int} {hour_int:02d}:{minute_int:02d}:{second_int:02d}")

    # --- Contoh penggunaan get_unix_time() ---
    print(f"\nUnix Time (dari DS3231): {rtc_ds3231.get_unix_time()}")
    print(f"Unix Time (dari internal RTC): {time.time()}") # Bandingkan dengan RTC internal

    print("\nMemulai loop pembacaan waktu setiap 5 detik (tekan Ctrl+C untuk berhenti)...")
    try:
        while True:
            current_time_ds3231 = rtc_ds3231.get_time()
            year, month, date, hour, minute, second, day_of_week, _ = current_time_ds3231
            print(f"DS3231: {days[day_of_week]}, {date:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}:{second:02d}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh pengguna.")