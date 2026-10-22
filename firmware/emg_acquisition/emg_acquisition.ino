// ESP32 ADC1 EMG stream: CSV timestamp_ms,adc_value at 1 kHz, 921600 baud.
// Lines starting with '#' are status messages; the Python readers skip them.
// Follow the sensor manufacturer's safety and wiring instructions.
#include <Arduino.h>

constexpr int EMG_PIN = 34;  // ADC1 pin; avoid ADC2 when Wi-Fi is enabled
constexpr uint32_t SAMPLE_RATE_HZ = 1000;
constexpr uint32_t SAMPLE_PERIOD_US = 1000000UL / SAMPLE_RATE_HZ;  // 1000 us
constexpr uint32_t STUCK_SAMPLES = SAMPLE_RATE_HZ;                 // 1 s at the rail
constexpr uint32_t MAX_LAG_US = 50 * SAMPLE_PERIOD_US;             // resync instead of bursting

uint32_t nextSampleTime = 0;
uint32_t zeroRun = 0;
uint32_t fullRun = 0;
uint32_t lastStatusMs = 0;

void setup() {
  Serial.begin(921600);
  analogReadResolution(12);
  analogSetPinAttenuation(EMG_PIN, ADC_11db);

  delay(500);
  Serial.println("# EMG start 1000Hz");
  nextSampleTime = micros();
  lastStatusMs = millis();
}

void loop() {
  const uint32_t now = micros();

  if ((int32_t)(now - nextSampleTime) >= 0) {
    // If the loop stalled, skip the missed slots rather than firing them back to back.
    nextSampleTime = (now - nextSampleTime > MAX_LAG_US) ? now + SAMPLE_PERIOD_US
                                                         : nextSampleTime + SAMPLE_PERIOD_US;

    const int adcValue = analogRead(EMG_PIN);
    Serial.printf("%lu,%d\n", (unsigned long)millis(), adcValue);

    zeroRun = (adcValue == 0) ? zeroRun + 1 : 0;
    fullRun = (adcValue >= 4095) ? fullRun + 1 : 0;
  }

  const uint32_t nowMs = millis();
  if (nowMs - lastStatusMs >= 1000) {
    lastStatusMs = nowMs;
    if (zeroRun >= STUCK_SAMPLES) {
      Serial.println("# WARNING: ADC stuck at 0 - check sensor power/wiring");
    } else if (fullRun >= STUCK_SAMPLES) {
      Serial.println("# WARNING: ADC stuck at 4095 - check sensor output/ground");
    } else {
      Serial.println("# OK");
    }
  }
}
