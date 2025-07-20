# sound_tap_detector_v3.py - Deteksi Ketukan Pendek/Panjang & Pola Biner (QYF-0037V3)

from machine import Pin
import time

class SoundTapDetector:
    def __init__(self, pin_number=19, debounce_time_ms=250, 
                 short_tap_max_delay_ms=500, # Jeda MAX untuk 'pendek' (0)
                 long_tap_min_delay_ms=501,  # Jeda MIN untuk 'panjang' (1)
                 total_taps_to_expect=7,     # Jumlah total ketukan fisik yang ditunggu
                 trigger_type=Pin.IRQ_FALLING,
                 sequence_timeout_ms=2000):  # DEFAULT: Reset setelah 2 detik tidak ada ketukan
        """
        Menginisialisasi detektor ketukan dengan kemampuan mendeteksi pola pendek/panjang
        dan mengonversinya menjadi representasi biner, serta fitur timeout.

        :param pin_number: Nomor pin GPIO yang terhubung ke output DO sensor suara.
        :param debounce_time_ms: Waktu debounce dalam milidetik.
        :param short_tap_max_delay_ms: Jeda waktu (ms) antar ketukan untuk dianggap pendek (representasi '.').
        :param long_tap_min_delay_ms: Jeda waktu (ms) antar ketukan untuk dianggap panjang (representasi '-').
        :param total_taps_to_expect: Jumlah total ketukan fisik yang diharapkan dalam satu urutan (misal 7).
                                     Ketukan terakhir ini digunakan untuk menentukan jeda ketukan sebelumnya,
                                     dan tidak dimasukkan ke dalam representasi biner.
        :param trigger_type: Tipe pemicu interupsi.
        :param sequence_timeout_ms: Waktu dalam milidetik setelah ketukan terakhir,
                                    jika tidak ada ketukan baru, urutan akan direset.
        """
        self.pin_number = pin_number
        self.pin = Pin(pin_number, Pin.IN, Pin.PULL_UP)
        self.debounce_time_ms = debounce_time_ms
        self.trigger_type = trigger_type
        
        self.short_tap_max_delay_ms = short_tap_max_delay_ms
        self.long_tap_min_delay_ms = long_tap_min_delay_ms
        self.total_taps_to_expect = total_taps_to_expect
        self.sequence_timeout_ms = sequence_timeout_ms

        self._tap_detected_flag = False
        self._last_tap_time = 0
        
        self._current_binary_sequence = "" # Menyimpan representasi biner (.,-)
        self._last_sequence_tap_time = 0   # Waktu ketukan terakhir yang valid dalam urutan
        self._full_sequence_ready = False  
        self._current_tap_count = 0        # Menghitung ketukan fisik yang terdeteksi dalam urutan

        self.pin.irq(trigger=self.trigger_type, handler=self._handle_tap_interrupt)
        
        print(f"SoundTapDetector diinisialisasi pada GPIO{self.pin_number}.")
        print(f"Debounce: {debounce_time_ms}ms, Trigger: {trigger_type}.")
        print(f"Jeda Pendek (0): <= {short_tap_max_delay_ms}ms.")
        print(f"Jeda Panjang (1): >= {long_tap_min_delay_ms}ms.")
        print(f"Mencari {total_taps_to_expect} ketukan fisik (hasil biner 6-bit).")
        print(f"Urutan akan direset jika tidak ada ketukan selama {sequence_timeout_ms}ms.")
        print("Pastikan potensiometer sensor diatur agar LED DO mati saat diam.")

    def _handle_tap_interrupt(self, pin_obj):
        """
        Fungsi callback interupsi internal.
        Memproses setiap deteksi ketukan untuk membangun urutan biner.
        """
        current_time = time.ticks_ms()
        
        if time.ticks_diff(current_time, self._last_tap_time) > self.debounce_time_ms:
            # Ini adalah deteksi ketukan yang valid setelah debounce
            self._tap_detected_flag = True # Set flag untuk loop utama
            
            # --- Logika Deteksi Pola Ketukan ---
            # Jika urutan sudah lengkap, atau jika ini ketukan setelah timeout reset
            if self._full_sequence_ready: # Kalau sudah selesai, dan ada ketukan lagi, reset saja
                print(f"[{time.ticks_ms()}] Urutan sudah lengkap, ketukan tambahan terdeteksi. Mereset.")
                self.reset_sequence()
            #elif self._current_tap_count == 0 and time.ticks_diff(current_time, self._last_sequence_tap_time) > self.sequence_timeout_ms:
                # Jika ini ketukan pertama setelah timeout, reset dulu.
                # Ini penting jika ada timeout di tengah urutan yang gagal dideteksi karena tidak di loop utama
            #    print(f"[{time.ticks_ms()}] Timeout terdeteksi sebelum ketukan baru. Mereset urutan.")
            #    self.reset_sequence()

            self._current_tap_count += 1 # Tambah hitungan ketukan fisik setelah potensi reset

            if self._current_tap_count <= self.total_taps_to_expect:
                if self._current_tap_count == 1:
                    # Ketukan pertama: selalu pendek (0), ini adalah bit pertama dari 6.
                    print(f"[{time.ticks_ms()}] Ketukan #1 terdeteksi")
                else:
                    # Hitung jeda dari ketukan sebelumnya dalam urutan
                    time_diff = time.ticks_diff(current_time, self._last_sequence_tap_time)
                    
                    if self._current_tap_count < self.total_taps_to_expect:
                        # Ketukan ke-2 hingga ke-6. Ini akan menentukan bit 2-6 dari urutan biner.
                        if time_diff <= self.short_tap_max_delay_ms:
                            self._current_binary_sequence += "."
                            print(f"[{time.ticks_ms()}] Ketukan #{self._current_tap_count} (Pendek, jeda: {time_diff}ms). Urutan biner: {self._current_binary_sequence}")
                        #elif time_diff >= self.long_tap_min_delay_ms:
                        else:
                            self._current_binary_sequence += "-"
                            print(f"[{time.ticks_ms()}] Ketukan #{self._current_tap_count} (Panjang, jeda: {time_diff}ms). Urutan biner: {self._current_binary_sequence}")
                        #else:
                            # Jeda tidak sesuai kriteria, reset urutan
                        #    print(f"[{time.ticks_ms()}] Jeda tidak valid ({time_diff}ms). Urutan direset.")
                        #    self.reset_sequence()
                            
                    elif self._current_tap_count == self.total_taps_to_expect:
                        # Ini adalah ketukan fisik terakhir (ke-7).
                        # Ketukan ke-7 ini hanya berfungsi sebagai penentu jeda untuk ketukan ke-6 (bit ke-6).
                        # Karena permintaan Anda, bit ke-6 (yang dibentuk oleh jeda antara ketukan fisik ke-6 dan ke-7)
                        # selalu dianggap pendek. Jadi kita hanya perlu memvalidasi jeda.
                        if time_diff <= self.short_tap_max_delay_ms:
                            self._current_binary_sequence += "." # Menambahkan bit ke-6 (selalu pendek)
                            print(f"[{time.ticks_ms()}] Ketukan terakhir (Pendek, jeda: {time_diff}ms). Urutan biner: {self._current_binary_sequence}")
                            self._full_sequence_ready = True
                        else:
                            # Jika jeda terakhir tidak pendek, tetap catat sebagai panjang, tetapi reset urutan
                            self._current_binary_sequence += "-" # Tetap tambahkan untuk melihat polanya
                            print(f"[{time.ticks_ms()}] Ketukan terakhir (Panjang, jeda: {time_diff}ms). Urutan biner: {self._current_binary_sequence}")
                            self._full_sequence_ready = True
            
            self._last_sequence_tap_time = current_time # Perbarui waktu ketukan terakhir untuk perhitungan jeda dan timeout
            self._last_tap_time = current_time # Perbarui waktu terakhir debounce
    
    def is_tap_detected(self):
        """
        Memeriksa apakah ada ketukan baru (setelah debounce) yang terdeteksi.
        Mengatur ulang flag deteksi setelah diperiksa.
        """
        if self._tap_detected_flag:
            self._tap_detected_flag = False 
            return True
        return False

    def check_for_timeout(self):
        """
        Memeriksa apakah ada timeout sejak ketukan terakhir.
        Jika ya, dan ada urutan yang sedang dibangun, urutan akan direset.
        """
        current_time = time.ticks_ms()
        # Periksa hanya jika ada urutan yang sedang dibangun (bukan kosong atau sudah lengkap)
        if self._current_tap_count > 0 and not self._full_sequence_ready:
            if time.ticks_diff(current_time, self._last_sequence_tap_time) > self.sequence_timeout_ms:
                print(f"[{time.ticks_ms()}] Timeout! Tidak ada ketukan selama {self.sequence_timeout_ms}ms. Urutan direset.")
                self.reset_sequence()
                return True
        return False

    def is_sequence_complete(self):
        """
        Memeriksa apakah urutan ketukan biner lengkap telah terdeteksi (6 bit).
        :return: True jika urutan lengkap dan siap diproses.
        """
        if self._full_sequence_ready:
            # Pastikan urutan biner memiliki panjang yang diharapkan (6 bit)
            if len(self._current_binary_sequence) == (self.total_taps_to_expect - 1): # 7-1 = 6 bit
                self._full_sequence_ready = False # Reset flag setelah dibaca
                return True
            else:
                # Jika jumlah bit tidak sesuai, mungkin ada masalah logika atau jeda yang terlewat.
                print(f"[{time.ticks_ms()}] Warning: Urutan biner tidak lengkap ({len(self._current_binary_sequence)} bit) meskipun {self.total_taps_to_expect} ketukan fisik terdeteksi. Mereset.")
                self.reset_sequence()
                return False
        return False

    def get_binary_sequence(self):
        """
        Mengembalikan urutan ketukan yang terdeteksi sebagai string biner kustom (misal: ".-..-.").
        """
        return self._current_binary_sequence

    def binary_sequence_to_integer(self, binary_str=None):
        """
        Mengonversi string representasi biner (.,-) menjadi integer (0-63).
        
        :param binary_str: String biner kustom (misal ".-..-."). Jika None, akan menggunakan
                           urutan biner yang saat ini terdeteksi oleh detektor.
        :return: Integer yang merepresentasikan urutan biner, atau None jika format tidak valid.
        """
        if binary_str is None:
            binary_str = self._current_binary_sequence
        
        if not all(c in ['.', '-'] for c in binary_str):
            print("Error: String biner kustom mengandung karakter yang tidak valid.")
            return None
        
        # Ganti '.' dengan '0' dan '-' dengan '1'
        standard_binary_str = binary_str.replace('.', '0').replace('-', '1')
        
        # Pastikan panjangnya 6 bit untuk konversi yang benar
        if len(standard_binary_str) != (self.total_taps_to_expect - 1):
            print(f"Error: Panjang string biner ({len(standard_binary_str)} bit) tidak sesuai (seharusnya {self.total_taps_to_expect - 1} bit).")
            return None

        # Konversi string biner ke integer
        try:
            return int(standard_binary_str, 2)
        except ValueError:
            print(f"Error: Gagal mengonversi '{standard_binary_str}' ke integer. Format biner tidak valid.")
            return None

    def reset_sequence(self):
        """
        Mengatur ulang urutan ketukan yang sedang dibangun.
        """
        self._current_binary_sequence = ""
        self._last_sequence_tap_time = 0 # Reset waktu terakhir ke 0 agar timeout dimulai dari 0 saat ketukan pertama
        self._full_sequence_ready = False
        self._current_tap_count = 0
        print(f"[{time.ticks_ms()}] Urutan ketukan direset.")

    def deactivate(self):
        """
        Menonaktifkan interupsi pada pin sensor.
        """
        self.pin.irq(handler=None)
        print(f"SoundTapDetector pada GPIO{self.pin_number} dinonaktifkan.")

    def __repr__(self):
        trigger_names = []
        if self.trigger_type & Pin.IRQ_FALLING:
            trigger_names.append("FALLING")
        if self.trigger_type & Pin.IRQ_RISING:
            trigger_names.append("RISING")
        trigger_str = "|".join(trigger_names) if trigger_names else "NONE" 

        return (f"SoundTapDetector(pin=GPIO{self.pin_number}, "
                f"debounce_time={self.debounce_time_ms}ms, "
                f"short_tap_max={self.short_tap_max_delay_ms}ms, "
                f"long_tap_min={self.long_tap_min_delay_ms}ms, "
                f"total_taps_expected={self.total_taps_to_expect}, "
                f"timeout={self.sequence_timeout_ms}ms, " # Tambah timeout di repr
                f"trigger_type={trigger_str})")

# --- Contoh Penggunaan Langsung ---
if __name__ == "__main__":
    print("Menjalankan contoh penggunaan SoundTapDetector (Deteksi Pola Biner & Konversi)...")

    # Sesuaikan nilai parameter sesuai kebutuhan Anda.
    detector = SoundTapDetector(
        pin_number=19, 
        debounce_time_ms=50, 
        short_tap_max_delay_ms=300,  # Max jeda 0.3 detik untuk pendek '.'
        long_tap_min_delay_ms=301,   # Min jeda 0.301 detik untuk panjang '-'
        total_taps_to_expect=7,      # Menunggu 7 ketukan fisik
        sequence_timeout_ms=2000,    # Reset jika tidak ada ketukan selama 2 detik
        trigger_type=Pin.IRQ_FALLING # Sinyal LOW saat terdeteksi
    )
    print(f"Objek detektor: {detector}")

    print("\n--- Loop utama dimulai (tekan Ctrl+C untuk berhenti) ---")
    print(f"Mulai ketuk sensor suara Anda. Harap berikan {detector.total_taps_to_expect} ketukan dengan jeda yang sesuai!")
    print(f"Ketukan pertama dianggap pendek ('.'). Jeda yang tidak valid atau timeout akan mereset urutan.")
    print("Jeda sangat cepat (di bawah debounce) akan diabaikan.")

    try:
        while True:
            # Periksa timeout di loop utama
            detector.check_for_timeout()

            if detector.is_sequence_complete():
                binary_sequence = detector.get_binary_sequence()
                integer_value = detector.binary_sequence_to_integer(binary_sequence)
                
                print(f"\n*** URUTAN KETUKAN LENGKAP TERDETEKSI! ***")
                print(f"Pola Biner: {binary_sequence}")
                if integer_value is not None:
                    print(f"Nilai Integer: {integer_value}")
                
                print("Melakukan aksi berdasarkan pola ini...")
                # Lakukan sesuatu dengan 'binary_sequence' atau 'integer_value' di sini
                # Misalnya, verifikasi pola TOTP Anda.
                
                detector.reset_sequence()
                print("\nMenunggu urutan ketukan baru...")
            
            time.sleep_ms(50) # Jeda singkat untuk menghemat daya CPU
            
    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh pengguna.")
    finally:
        detector.deactivate() 
        print("Selesai.")