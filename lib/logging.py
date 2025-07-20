# mylogging.py - Modul Logging Kustom dengan Fitur Rotating File
from micropython import const
import io
import sys
import time
import os

# =========================================================
# 1. Klasifikasi 5 Jenis Log
# =========================================================
CRITICAL = const(50)
ERROR = const(40)
WARNING = const(30)
INFO = const(20)
DEBUG = const(10)
NOTSET = const(0)

# Default level jika tidak secara eksplisit diatur
_DEFAULT_LEVEL = const(WARNING)

_level_dict = {
    CRITICAL: "CRITICAL",
    ERROR: "ERROR",
    WARNING: "WARNING",
    INFO: "INFO",
    DEBUG: "DEBUG",
    NOTSET: "NOTSET",
}

_loggers = {} # Kamus global untuk menyimpan instance Logger
_default_stream = sys.stderr # Stream default untuk output konsol
_default_fmt = "%(levelname)s:%(name)s:%(message)s"
_default_datefmt = "%Y-%m-%d %H:%M:%S" # Format tanggal default untuk MicroPython time.strftime

class LogRecord:
    """
    Kelas ini merepresentasikan satu peristiwa log. 
    Ini adalah objek data yang membawa informasi log.
    """
    def set(self, name, level, message):
        self.name = name
        self.levelno = level
        self.levelname = _level_dict[level]
        self.message = message
        self.ct = time.time() # Waktu saat ini dalam detik sejak epoch
        self.asctime = None # Akan diisi oleh Formatter

class Formatter:
    """
    Kelas ini bertanggung jawab untuk memformat objek LogRecord 
    menjadi string yang dapat dibaca.
    """
    def __init__(self, fmt=None, datefmt=None):
        self.fmt = _default_fmt if fmt is None else fmt
        self.datefmt = _default_datefmt if datefmt is None else datefmt

    def usesTime(self):
        """Memeriksa apakah format string membutuhkan timestamp."""
        return "%(asctime)s" in self.fmt

    # =========================================================
    # 2. Pencatatan waktu berdasarkan WIB (Menggunakan Formatting Manual)
    # =========================================================
    def formatTime(self, datefmt, record):
        """
        Memformat timestamp dari record secara manual, 
        menggunakan time.localtime() dan string formatting.
        """
        t = time.localtime(record.ct)
        # t adalah tuple: (year, month, mday, hour, minute, second, weekday, yearday)
        year, month, mday, hour, minute, second, _, _ = t

        # Penanganan format yang umum digunakan
        if datefmt == "%Y-%m-%d %H:%M:%S":
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                year, month, mday, hour, minute, second
            )
        elif datefmt == "%H:%M:%S":
            return "{:02d}:{:02d}:{:02d}".format(
                hour, minute, second
            )
        else:
            # Fallback jika format tidak secara eksplisit ditangani.
            # Menggunakan format default '%Y-%m-%d %H:%M:%S'
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                year, month, mday, hour, minute, second
            )

    def format(self, record):
        """Memformat seluruh record log menjadi string akhir."""
        if self.usesTime():
            record.asctime = self.formatTime(self.datefmt, record)
        
        record_data = {
            "name": record.name,
            "levelname": record.levelname,
            "message": record.message,
            "asctime": record.asctime,
        }
        return self.fmt % record_data

class Handler:
    """
    Kelas dasar abstrak untuk semua handler log. 
    Handler bertanggung jawab untuk mengirim LogRecord ke tujuan tertentu.
    """
    def __init__(self, level=NOTSET):
        self.level = level
        self.formatter = None

    def close(self):
        """Menutup handler dan membebaskan sumber daya (harus diimplementasikan subclass)."""
        pass

    def setLevel(self, level):
        """Mengatur level logging handler."""
        self.level = level

    def setFormatter(self, formatter):
        """Mengatur formatter untuk handler ini."""
        self.formatter = formatter

    def format(self, record):
        """Memformat record yang diberikan menggunakan formatter yang terpasang."""
        if self.formatter:
            return self.formatter.format(record)
        # Fallback default jika tidak ada formatter
        return record.levelname + ":" + record.name + ":" + record.message

    def emit(self, record):
        """
        Metode abstrak; harus diimplementasikan oleh subclass untuk benar-benar 
        mengeluarkan record log.
        """
        raise NotImplementedError("emit must be implemented by Handler subclasses")

class StreamHandler(Handler):
    """
    Handler yang menulis record log ke stream (misalnya, sys.stdout, sys.stderr).
    """
    def __init__(self, stream=None, level=NOTSET):
        super().__init__(level)
        self.stream = _default_stream if stream is None else stream
        self.terminator = "\n"

    def close(self):
        """Membersihkan (flush) stream."""
        if hasattr(self.stream, "flush"):
            self.stream.flush()

    def emit(self, record):
        """Mengeluarkan record ke stream."""
        if record.levelno >= self.level:
            self.stream.write(self.format(record) + self.terminator)

class FileHandler(StreamHandler):
    """
    Kelas dasar untuk handler yang menulis record log ke file.
    """
    def __init__(self, filename, mode="a", encoding="UTF-8", level=NOTSET):
        # Membuka file dan meneruskan objek file ke StreamHandler
        super().__init__(stream=open(filename, mode=mode, encoding=encoding), level=level)
        self.baseFilename = filename # Nama file dasar
        self.mode = mode
        self.encoding = encoding

    def close(self):
        """Menutup stream file dan memanggil close() dari parent."""
        super().close()
        self.stream.close()

# =========================================================
# 3. Menuliskannya ke suatu file log
# 4. Membatasi ukuran file log dan mengimplementasi rotating file
# 5. Membatasi jumlah file rotating yang dihasilkan
# =========================================================
class RotatingFileHandler(FileHandler):
    """
    Handler file yang merotasi file log ketika mereka mencapai ukuran tertentu.
    """
    def __init__(self, filename, mode="a", maxBytes=0, backupCount=0, encoding="UTF-8", level=NOTSET):
        if maxBytes > 0:
            if backupCount <= 0:
                raise ValueError("backupCount must be > 0 when maxBytes > 0 for rotation")
        
        super().__init__(filename, mode, encoding, level)
        self.maxBytes = maxBytes # Ukuran maksimum file sebelum rotasi
        self.backupCount = backupCount # Jumlah file backup yang akan disimpan

    def doRotate(self):
        """
        Melakukan proses rotasi file. 
        Ini akan menutup file saat ini, mengganti nama file-file lama, 
        dan membuka file log baru.
        """
        print("DEBUG: Memulai rotasi file log...") # Debug print
        self.close() # Tutup file log aktif saat ini

        if self.backupCount > 0:
            # Iterasi mundur untuk menggeser file backup: .2 -> .3, .1 -> .2
            for i in range(self.backupCount - 1, 0, -1):
                sfn = f"{self.baseFilename}.{i}" # Source file name (misal: my_app.log.1)
                dfn = f"{self.baseFilename}.{i + 1}" # Destination file name (misal: my_app.log.2)
                if sfn in os.listdir(): # Jika source file ada
                    if dfn in os.listdir(): # Jika destination file sudah ada, hapus dulu
                        os.remove(dfn)
                        print(f"DEBUG: Menghapus file lama: {dfn}") # Debug print
                    os.rename(sfn, dfn) # Ganti nama source ke destination
                    print(f"DEBUG: Mengganti nama {sfn} ke {dfn}") # Debug print
            
            # Ganti nama file log aktif (.txt) menjadi file backup pertama (.1)
            dfn = f"{self.baseFilename}.1"
            if self.baseFilename in os.listdir(): # Jika file log aktif ada
                if dfn in os.listdir(): # Jika .1 sudah ada, hapus dulu
                    os.remove(dfn)
                    print(f"DEBUG: Menghapus file lama: {dfn}") # Debug print
                os.rename(self.baseFilename, dfn)
                print(f"DEBUG: Mengganti nama {self.baseFilename} ke {dfn}") # Debug print
        
        # Buka kembali file log dasar untuk log baru
        self.stream = open(self.baseFilename, self.mode, encoding=self.encoding)
        print("DEBUG: Rotasi file log selesai. File baru dibuka.") # Debug print

    def shouldRotate(self, record):
        """
        Menentukan apakah rotasi harus terjadi berdasarkan ukuran file.
        """
        if self.maxBytes > 0:
            # PENTING: Lakukan flush() sebelum mengecek ukuran file untuk mendapatkan ukuran yang akurat
            if hasattr(self.stream, 'flush'): 
                self.stream.flush() # Pastikan semua data di buffer ditulis ke disk

            if self.baseFilename in os.listdir():
                try:
                    current_size = os.stat(self.baseFilename)[6] # Dapatkan ukuran file dalam byte
                    print(f"DEBUG: Mengecek rotasi. Ukuran saat ini: {current_size} bytes, Ukuran max: {self.maxBytes} bytes.") # Debug print
                    if current_size >= self.maxBytes:
                        print("DEBUG: Kondisi rotasi terpenuhi!") # Debug print
                        return True
                except OSError as e:
                    print(f"DEBUG: OSError saat cek ukuran file: {e}. Memaksa rotasi.") # Debug print
                    return True # Force rotation if stat fails
        return False

    def emit(self, record):
        """Mengeluarkan record, memicu rotasi jika diperlukan."""
        try:
            if self.shouldRotate(record):
                self.doRotate() # Lakukan rotasi jika diperlukan
            super().emit(record) # Kemudian keluarkan record menggunakan metode parent (FileHandler)
        except Exception as e:
            # Fallback ke sys.stderr jika ada masalah saat logging ke file
            _default_stream.write(f"ERROR: Logging to file failed: {e}\n")
            _default_stream.write(f"{self.format(record)}\n")


class Logger:
    """
    Kelas ini merepresentasikan channel logging. 
    Ini adalah antarmuka utama bagi aplikasi Anda untuk mencatat pesan.
    """
    def __init__(self, name, level=NOTSET):
        self.name = name
        self.level = level
        self.handlers = [] # Daftar handler yang terhubung ke logger ini
        self.record = LogRecord() # Objek LogRecord yang digunakan kembali untuk mengurangi alokasi memori

    def setLevel(self, level):
        """Mengatur level logging logger ini."""
        self.level = level

    def isEnabledFor(self, level):
        """Memeriksa apakah logging diaktifkan untuk level yang diberikan."""
        return level >= self.getEffectiveLevel()

    def getEffectiveLevel(self):
        """Mendapatkan level logging efektif logger ini."""
        # Untuk versi sederhana ini, hanya mempertimbangkan level logger itu sendiri.
        return self.level or _DEFAULT_LEVEL

    def log(self, level, msg, *args):
        """Mencatat pesan pada level yang ditentukan."""
        if self.isEnabledFor(level):
            # Format pesan dengan argumen jika disediakan
            if args:
                if len(args) == 1 and isinstance(args[0], dict):
                    msg = msg % args[0]
                else:
                    msg = msg % args
            
            self.record.set(self.name, level, msg)
            
            # Jika tidak ada handler yang disetel pada logger ini, gunakan handler dari root logger
            handlers_to_use = self.handlers if self.handlers else getLogger().handlers
            
            for h in handlers_to_use:
                h.emit(self.record)

    # Metode pintas untuk setiap level log
    def debug(self, msg, *args):
        self.log(DEBUG, msg, *args)

    def info(self, msg, *args):
        self.log(INFO, msg, *args)

    def warning(self, msg, *args):
        self.log(WARNING, msg, *args)

    def error(self, msg, *args):
        self.log(ERROR, msg, *args)

    def critical(self, msg, *args):
        self.log(CRITICAL, msg, *args)

    def exception(self, msg, *args, exc_info=True):
        """Mencatat pesan ERROR dengan informasi pengecualian (traceback)."""
        self.log(ERROR, msg, *args)
        tb = None
        if exc_info is True:
            if hasattr(sys, "exc_info"):
                tb = sys.exc_info()[1]
        elif isinstance(exc_info, BaseException):
            tb = exc_info
            
        if tb:
            buf = io.StringIO()
            sys.print_exception(tb, buf)
            self.log(ERROR, "Traceback:\n" + buf.getvalue())

    def addHandler(self, handler):
        """Menambahkan handler yang ditentukan ke logger ini."""
        self.handlers.append(handler)

    def removeHandler(self, handler):
        """Menghapus handler yang ditentukan dari logger ini."""
        try:
            self.handlers.remove(handler)
        except ValueError:
            pass 

    def hasHandlers(self):
        """Memeriksa apakah logger ini memiliki handler."""
        return len(self.handlers) > 0

# --- Fungsi Global untuk Kemudahan (Mirip dengan API standar) ---

def getLogger(name=None):
    """Mengembalikan logger dengan nama yang ditentukan, membuatnya jika perlu."""
    if name is None or name == "root":
        name = "root"
        if name not in _loggers:
            _loggers[name] = Logger(name)
            # Ketika root logger pertama kali didapatkan, basicConfig secara otomatis dipanggil
            basicConfig() 
        return _loggers[name]
    
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]

def basicConfig(
    filename=None,
    filemode="a",
    format=None,
    datefmt=None,
    level=NOTSET, 
    stream=None,
    encoding="UTF-8",
    force=False,
):
    """Mengkonfigurasi root logger."""
    logger = getLogger("root") # Memastikan root logger ada

    if force or not logger.hasHandlers():
        for h in logger.handlers:
            h.close()
        logger.handlers = [] # Hapus handler yang ada

        if filename is None:
            handler = StreamHandler(stream)
        else:
            # basicConfig ini menggunakan FileHandler dasar.
            # Untuk RotatingFileHandler, Anda harus menambahkannya secara eksplisit
            # seperti dalam contoh penggunaan (if __name__ == "__main__":)
            handler = FileHandler(filename, filemode, encoding)

        handler.setLevel(level if level is not NOTSET else _DEFAULT_LEVEL)
        handler.setFormatter(Formatter(format, datefmt))
        
        logger.setLevel(level if level is not NOTSET else _DEFAULT_LEVEL)
        logger.addHandler(handler)

def shutdown():
    """Menutup semua handler aktif dan menghapus semua logger."""
    for logger_name in list(_loggers.keys()): 
        logger = _loggers[logger_name]
        for h in logger.handlers:
            h.close()
        del _loggers[logger_name] 

# Mendaftarkan fungsi shutdown untuk dipanggil saat program keluar jika atexit tersedia
if hasattr(sys, "atexit"):
    sys.atexit(shutdown)

# Fungsi pintas global yang langsung ke root logger
log = getLogger().log
debug = getLogger().debug
info = getLogger().info
warning = getLogger().warning
error = getLogger().error
critical = getLogger().critical
exception = getLogger().exception

def getLevelName(level):
    """Mengembalikan nama string untuk level log numerik."""
    return _level_dict.get(level, "UNKNOWN")

__version__ = '1.0.3_flush_fix' # Versi diperbarui untuk menandai perbaikan flush


# =========================================================
# CARA PEMAKAIAN (Jalankan file mylogging.py ini langsung)
# =========================================================
if __name__ == "__main__":
    print("--- Memulai Demo Modul mylogging ---")
    print("Log akan dicatat ke konsol dan file 'demo_log.txt'.")
    print("File akan berotasi setiap 100 byte dan menyimpan 2 backup.")

    LOG_FILE = "sandiwadi.log" 
    MAX_LOG_SIZE_BYTES = 5120  # Ukuran kecil untuk demo cepat (100 byte)
    BACKUP_COUNT = 3          # Menyimpan demo_log.txt.1 dan demo_log.txt.2

    # --- Hapus file log lama saat startup untuk demo bersih ---
    # Ini memastikan setiap demo dimulai dari nol.
    print(f"DEBUG: Membersihkan file log lama...") # Debug print
    if LOG_FILE in os.listdir(): 
        os.remove(LOG_FILE)
        print(f"File log utama '{LOG_FILE}' dihapus.")
    for i in range(1, BACKUP_COUNT + 2): # Hapus hingga backupCount + 1
        backup_file = f"{LOG_FILE}.{i}"
        if backup_file in os.listdir():
            os.remove(backup_file)
            print(f"File backup lama '{backup_file}' dihapus.")
    print(f"DEBUG: Pembersihan file log selesai.") # Debug print

    # --- Konfigurasi Root Logger ---
    # Dapatkan root logger. Jika ini pemanggilan pertama, basicConfig default akan terpanggil.
    # Kita akan override dengan handler kustom.
    root_logger = getLogger() 
    root_logger.setLevel(DEBUG) # Set level minimum root logger ke DEBUG

    # 1. Konfigurasi RotatingFileHandler
    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=MAX_LOG_SIZE_BYTES,
        backupCount=BACKUP_COUNT,
        level=DEBUG # Semua pesan dari DEBUG ke atas akan masuk ke file
    )
    file_formatter = Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S' 
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # 2. Konfigurasi StreamHandler untuk konsol
    console_handler = StreamHandler(sys.stdout)
    console_formatter = Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(INFO) # Hanya pesan INFO ke atas yang ditampilkan di konsol
    root_logger.addHandler(console_handler)

    # --- Gunakan Logger ---
    my_app_logger = getLogger("MyAppDemo")
    
    print("\n--- Mulai Mencatat Log ---")
    for i in range(1, 101): # Loop menjadi 100 kali
        my_app_logger.debug(f"Pesan Debug ke-{i}. Ini mungkin tidak terlihat di konsol.")
        my_app_logger.info(f"Pesan Info ke-{i}. Ukuran file log akan bertambah.")
        if i % 3 == 0:
            my_app_logger.warning(f"Pesan Peringatan ke-{i}. Perhatikan rotasi file!")
        if i % 5 == 0:
            my_app_logger.error(f"Pesan Error ke-{i}. Simulating an issue.")
            try:
                result = 10 / 0 # Sengaja memicu error
            except Exception as e:
                my_app_logger.exception(f"Exception di loop ke-{i}:") # Akan mencetak traceback
        
        time.sleep(0.05) # Jeda singkat untuk memungkinkan penulisan ke file

    print("\n--- Log Selesai Dicatat ---")
    print("Cek file di filesystem Anda: 'demo_log.txt', 'demo_log.txt.1', 'demo_log.txt.2'")
    
    # --- Pastikan semua handler ditutup ---
    shutdown()
    print("--- Demo Selesai ---")