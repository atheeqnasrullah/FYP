# Hardware and firmware

An ESP32 samples the MD0437 EMG sensor on GPIO34 at 1 kHz and streams `timestamp_ms,adc_value` lines to the PC over USB serial at 921600 baud; a webcam supplies the hand images.

## Parts

| Part | Specification |
|---|---|
| EMG sensor | MD0437, single channel. Its SIG output is an already filtered, rectified activity envelope, not raw EMG |
| Microcontroller | ESP32 DevKit (30-pin, USB-C), ADC1 pin GPIO34, 12-bit (0-4095), 11 dB attenuation. Never use ADC2 pins with Wi-Fi on |
| Electrodes | 3 Ag/AgCl surface electrodes |
| Sensor power | +9 V and -9 V supply for the MD0437; battery powered while attached to a person, never mains-connected |
| Link to PC | USB serial, 921600 baud. Wi-Fi is not implemented |
| Camera | Any webcam OpenCV can open (`camera_index` in `config/settings.yaml`) |

## Electrode placement

| Electrode | Role | Placement |
|---|---|---|
| Yellow | Reference | Bony area at the elbow |
| Green | Signal + | Upper forearm muscle belly |
| Red | Signal - | Lower forearm, 3-4 cm below green |

Clean the skin first, use single-use electrodes, and stop if there is discomfort or irritation.

## Firmware

`firmware/emg_acquisition/emg_acquisition.ino`:

- Sets 12-bit resolution and 11 dB attenuation on GPIO34.
- Uses a `micros()` timer to read the ADC every 1000 us (1 kHz).
- Prints one line per sample: `millis(),adc_value`.

Flash it with the Arduino IDE (ESP32 board package), then close the Serial Monitor before running the Python tools; only one program can open the port.

## Signal handling

Because SIG is an envelope, `config/settings.yaml` sets `signal_type: envelope`, so the software skips the 20-450 Hz bandpass and 50 Hz notch that raw EMG would need. Keep SIG inside the ESP32 ADC input range (0-3.3 V) before wiring.

The live reader (`src/realtime/pipeline.py`) ignores lines that do not have exactly two numbers or whose value is outside 0-4095. If no valid sample arrives for 2.5 s, games in Webcam + EMG mode pause on a waiting screen.

## Sample rate to confirm

The firmware streams at 1 kHz, but every file in `Dataset/` was logged at 100 Hz (10 ms between samples). Record which firmware or logger produced the dataset, and set `fs` in `config/settings.yaml` to match the data being processed.

## Port names

| OS | Typical port | Where to set it |
|---|---|---|
| Windows | `COM3`, `COM4`, ... (Device Manager) | `serial_port` in `config/settings.yaml` |
| macOS | `/dev/cu.usbserial-*` or `/dev/cu.SLAB_USBtoUART` | `serial_port`, or the `EMG_SERIAL_PORT` environment variable |
