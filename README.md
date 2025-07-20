# Kemuncen

**Kemuncen** adalah proyek IoT yang dirancang untuk mengamankan rak 
miniOLT menggunakan mekanisme *solenoid lock*. Kunci ini dioperasikan 
dengan kombinasi ketukan pada pintu, menawarkan metode akses yang inovatif 
dan terintegrasi dengan teknologi IoT.

---

## Konfigurasi Pin ESP32

Dokumen ini menjelaskan alokasi pin GPIO pada ESP32 yang digunakan dalam 
proyek ini untuk koneksi modul-modul eksternal.

## Diagram Pin (Opsional, sangat direkomendasikan jika memungkinkan)
## Alokasi Pin GPIO

Berikut adalah daftar modul eksternal dan pin ESP32 yang terhubung 
dengannya:

| Modul           | Fungsi | Pin ESP32 (GPIO) | Catatan                                           
|
| :-------------- | :----- | :--------------- | 
:------------------------------------------------ |
| **RTC DS3231** | SDA    | D21 (GPIO21)     | Data Serial I2C untuk 
Real-Time Clock             |
| **RTC DS3231** | SCL    | D22 (GPIO22)     | Clock Serial I2C untuk 
Real-Time Clock            |
| **KY-037** | DO     | D19 (GPIO19)     | Output Digital dari Sensor 
Suara KY-037           |
| **Relay** | IN     | D18 (GPIO18)     | Input Kontrol untuk Modul Relay                   
|
| **Buzzer** | +      | D5 (GPIO5)       | Pin Positif untuk Buzzer Pasif 
atau Aktif         |

---

### Catatan Tambahan:

* **Pin I2C (D21/GPIO21 dan D22/GPIO22):** Pin-pin ini adalah pin I2C 
default pada banyak dev board ESP32 (SDA/SCL). Pastikan modul DS3231 Anda 
terhubung dengan benar ke pin-pin ini.
* **KY-037 DO (D19/GPIO19):** Ini adalah pin output digital. Anda mungkin 
perlu mengkonfigurasi mode input (pull-up/pull-down) pada kode MicroPython 
Anda sesuai kebutuhan sensor.
* **Relay IN (D18/GPIO18):** Pastikan tegangan kontrol relay Anda 
kompatibel dengan logika 3.3V ESP32. Gunakan level shifter jika 
diperlukan, meskipun sebagian besar modul relay 5V dapat dikontrol 
langsung oleh 3.3V.
* **Buzzer + (D5/GPIO5):** Jika Anda menggunakan buzzer pasif, Anda 
mungkin perlu menggerakkannya dengan PWM. Jika buzzer aktif, cukup berikan 
HIGH/LOW.

Pastikan juga Anda memberikan power (VCC/3.3V atau 5V, tergantung modul) 
dan Ground (GND) yang sesuai untuk setiap modul Anda.
