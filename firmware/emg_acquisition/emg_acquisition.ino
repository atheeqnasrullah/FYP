// ESP32 ADC1 EMG stream: CSV timestamp_ms,adc_value at nominal 1 kHz.
// Follow the sensor manufacturer's safety and wiring instructions.
constexpr int EMG_PIN = 34; // ADC1 pin; avoid ADC2 when Wi-Fi is enabled
constexpr uint32_t PERIOD_US = 1000;
uint32_t next_sample;

void setup() {
  Serial.begin(921600);
  analogReadResolution(12);
  analogSetPinAttenuation(EMG_PIN, ADC_11db);
  next_sample = micros();
}

void loop() {
  const uint32_t now = micros();
  if ((int32_t)(now - next_sample) >= 0) {
    next_sample += PERIOD_US;
    const int value = analogRead(EMG_PIN);
    Serial.printf("%lu,%d\n", millis(), value);
  }
}
