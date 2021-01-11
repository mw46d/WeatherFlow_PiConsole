#include <WiFi.h>
#include <AutoConnect.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <NTPClient.h>
#include <WiFiUdp.h>
#include "DHT12.h"
#include <M5StickC.h>
#include <Wire.h>
#include "Adafruit_Sensor.h"
#include <Adafruit_BMP280.h>
#include <ArduinoJson.h>

WebServer server(80);
AutoConnect portal(server);
WiFiUDP ntpUDP;

// By default 'pool.ntp.org' is used with 60 seconds update interval and
// no offset
NTPClient timeClient(ntpUDP);

// You can specify the time server pool and the offset, (in seconds)
// additionaly you can specify the update interval (in milliseconds).
// NTPClient timeClient(ntpUDP, "europe.pool.ntp.org", 3600, 60000);

const int led = 10;

static float avg_temp = 0.0;
static float avg_hum = 0.0;
static float avg_pressure = 0.0;
unsigned long last_display_time = 0;

char *mdns_name = "m5stickc";
DynamicJsonDocument doc(2048);
DHT12 dht12; 
Adafruit_BMP280 bme;

void handleSensors() {
  digitalWrite(led, LOW);
  doc["temp_raw"] = avg_temp;
  doc["temp"] = temp_corr(avg_temp);
  doc["hum"] = avg_hum;
  doc["pressure"] = avg_pressure / 100;
  doc["timestamp"] = timeClient.getEpochTime();
  doc["vbat"] = M5.Axp.GetBatVoltage();
  doc["aps"] = M5.Axp.GetAPSVoltage();
  doc["level"] = M5.Axp.GetWarningLevel();
  doc["axp_temp"] = M5.Axp.GetTempInAXP192();
  
  char buf[1024];
  serializeJson(doc, buf);
  server.send(200, "application/json", buf);
  digitalWrite(led, HIGH);
}
void handleRoot() {
  digitalWrite(led, LOW);
  char buf[50];

  snprintf(buf, sizeof(buf), "hello from esp8266! %.1f  %.1f", avg_temp, avg_hum);
  server.send(200, "text/plain", buf);
  digitalWrite(led, HIGH);
}

void handleNotFound() {
  digitalWrite(led, LOW);
  String message = "File Not Found\n\n";
  message += "URI: ";
  message += server.uri();
  message += "\nMethod: ";
  message += (server.method() == HTTP_GET) ? "GET" : "POST";
  message += "\nArguments: ";
  message += server.args();
  message += "\n";
  for (uint8_t i = 0; i < server.args(); i++) {
    message += " " + server.argName(i) + ": " + server.arg(i) + "\n";
  }
  server.send(404, "text/plain", message);
  digitalWrite(led, HIGH);
}

float temp_corr(float tin) {
  float t = M5.Axp.GetTempInAXP192() - tin;
  t = t * t / 21.85;

  return tin - t;
}
void setup(void) {
  M5.begin();
  Wire.begin(0, 26);
  M5.Lcd.setRotation(3);
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setCursor(0, 0, 2);
  pinMode(M5_BUTTON_HOME, INPUT);
  pinMode(led, OUTPUT);

  digitalWrite(led, HIGH);
  delay(1000);

  Serial.begin(115200);
  Serial.println();

  if (!bme.begin(0x76)){  
      Serial.println("Could not find a valid BMP280 sensor, check wiring!");
      while (1);
  }

  server.on("/", handleRoot);
  server.on("/sensors", handleSensors);
  portal.onNotFound(handleNotFound);

  if (!portal.begin()) {
    char l = 0;
    while (true) {
      l = (l + 1) % 2;
      digitalWrite(led, l);
      delay(250);
    } 
  }

  String s1 = "SSID: " + WiFi.SSID();
  String s2 = "IP: " + WiFi.localIP().toString();
  Serial.println(s1);
  Serial.println(s2);

  char buf[30];
  s1.toCharArray(buf, sizeof(buf));
  M5.Lcd.setCursor(0, 0, 2);
  M5.Lcd.printf(buf);
  s2.toCharArray(buf, sizeof(buf));
  M5.Lcd.setCursor(0, 20, 2);
  M5.Lcd.printf(buf);

  if (MDNS.begin(mdns_name)) {
    Serial.println("MDNS responder started");
  }

  timeClient.begin();
  Serial.println("HTTP server started");
}

void loop(void) {
  unsigned long start_t = millis();
  float tmp = dht12.readTemperature();
  float hum = dht12.readHumidity();
  float pressure = bme.readPressure();

  avg_temp = (avg_temp * 4 + tmp) / 5.0;
  avg_hum = (avg_hum * 4 + hum) / 5.0;
  avg_pressure = (avg_pressure * 4 + pressure) / 5.0;

  if (start_t - last_display_time > 10000) {
    last_display_time = start_t;

    /*
    Serial.print("temp: "); Serial.print(tmp); Serial.print("  "); Serial.print(avg_temp); Serial.print("   "); Serial.println(temp_corr(avg_temp));
    Serial.print("hum : "); Serial.print(hum); Serial.print("  "); Serial.println(avg_hum);
    Serial.print("vbat: "); Serial.print(M5.Axp.GetBatVoltage());
    Serial.print("  aps: "); Serial.print(M5.Axp.GetAPSVoltage());
    Serial.print("  level: "); Serial.print(M5.Axp.GetWarningLevel());
    Serial.print("  axp_temp: "); Serial.println(M5.Axp.GetTempInAXP192());
    */

    M5.Lcd.setCursor(0, 40, 2);
    M5.Lcd.printf("Temp: %.1f Humi: %.1f%%", temp_corr(avg_temp), avg_hum);
    M5.Lcd.setCursor(0, 60, 2);
    M5.Lcd.printf("Pressure: %.1f", avg_pressure / 100.0);
  }
  
  portal.handleClient();
  timeClient.update();
  
  unsigned long dt = millis() - start_t;
  if (dt < 100) {
    delay(100 - dt);
  }
}
