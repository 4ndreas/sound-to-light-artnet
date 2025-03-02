import paho.mqtt.client as mqtt
import json
import time
import random

class BeatLampController:
    def __init__(self, broker, port, lamp_topics, blink_duration=0.2):
        """
        Initialisiert den BeatLampController.

        :param broker: Adresse des MQTT-Brokers.
        :param port: Port des MQTT-Brokers.
        :param lamp_topics: Liste der MQTT-Topics der Lampen.
        :param blink_duration: Basisdauer (in Sekunden) für Blinkeffekte.
        """
        self.broker = broker
        self.port = port
        self.lamp_topics = lamp_topics
        self.blink_duration = blink_duration
        self.lamp_index = 0

        # MQTT-Client einrichten und verbinden
        self.client = mqtt.Client()
        self.client.connect(self.broker, self.port, 60)
        print(f"Verbunden mit MQTT-Broker {self.broker}:{self.port}")

        # Vordefinierte Farben für das Cycle-Muster
        self.fixed_colors = [
            {"color": {"hue": 0, "saturation": 100}, "brightness": 255},    # Rot
            {"color": {"hue": 120, "saturation": 100}, "brightness": 255},  # Grün
            {"color": {"hue": 240, "saturation": 100}, "brightness": 255},  # Blau
            {"color": {"hue": 60, "saturation": 100}, "brightness": 255}    # Gelb
        ]
        self.pattern_cycle_index = 0  # Index für das Cycle-Muster

        # Verfügbare Muster:
        # 0 = Random, 1 = Cycle, 2 = Flicker, 3 = Strobe, 4 = Pulse
        self.patterns = {
            0: self.pattern_random,
            1: self.pattern_cycle,
            2: self.pattern_flicker,
            3: self.pattern_strobe,
            4: self.pattern_pulse
        }
        self.current_pattern = self.patterns[0]

        # Globaler Dimmer (Standard = 1.0, also 100% Helligkeit)
        self.global_dimmer = 1.0

    def set_global_dimmer(self, dimmer_value: float):
        """
        Setzt den globalen Dimmerwert, mit dem der brightness-Wert multipliziert wird.
        :param dimmer_value: Wert zwischen 0.0 (aus) und 1.0 (volle Helligkeit)
        """
        if 0.0 <= dimmer_value <= 1.0:
            self.global_dimmer = dimmer_value
            print(f"Globaler Dimmer auf {self.global_dimmer*100:.0f}% gesetzt.")
        else:
            print("Dimmer-Wert muss zwischen 0.0 und 1.0 liegen.")

    def apply_dimmer(self, payload):
        """
        Multipliziert den brightness-Wert im Payload mit dem globalen Dimmer.
        :param payload: Dictionary mit mindestens dem Schlüssel "brightness".
        :return: Angepasstes Payload.
        """
        if "brightness" in payload:
            brightness = payload["brightness"]
            adjusted = int(brightness * self.global_dimmer)
            # Sicherstellen, dass der Wert im gültigen Bereich (0-255) liegt
            payload["brightness"] = max(0, min(255, adjusted))
        return payload

    def select_pattern(self, pattern_num: int):
        """
        Wählt das Blinkmuster anhand der übergebenen Zahl aus.
        Verfügbare Muster:
          0 = Random,
          1 = Cycle,
          2 = Flicker,
          3 = Strobe,
          4 = Pulse.
        :param pattern_num: Integer für das gewünschte Muster.
        """
        if pattern_num in self.patterns:
            self.current_pattern = self.patterns[pattern_num]
            print(f"Muster {pattern_num} ausgewählt.")
        else:
            print("Ungültiges Muster. Standardmuster (0) wird verwendet.")
            self.current_pattern = self.patterns[0]

    def update_on_beat(self):
        """
        Wird bei einem Beat aufgerufen. Wendet das aktuell gewählte Muster auf die
        nächste Lampe im Array an.
        """
        if not self.lamp_topics:
            print("Keine Lampen-Topics definiert.")
            return

        # Zyklisches Durchlaufen der Lampen-Topics
        topic = self.lamp_topics[self.lamp_index]
        self.lamp_index = (self.lamp_index + 1) % len(self.lamp_topics)

        # Wende das aktuelle Muster an
        self.current_pattern(topic)

    def pattern_random(self, topic):
        """
        Muster 0: Zufällige Farben.
        """
        hue = random.randint(0, 360)
        saturation = random.randint(50, 100)
        brightness = random.randint(100, 255)
        payload_on = {
            "color": {"hue": hue, "saturation": saturation},
            "brightness": brightness
        }
        payload_on = self.apply_dimmer(payload_on)
        self.client.publish(topic, json.dumps(payload_on))
        print(f"[Random] {topic} => {payload_on}")
        time.sleep(self.blink_duration)
        self.client.publish(topic, json.dumps({"state": "OFF"}))
        print(f"[Random] {topic} ausgeschaltet.")

    def pattern_cycle(self, topic):
        """
        Muster 1: Zyklisches Durchlaufen vordefinierter Farben.
        """
        base = self.fixed_colors[self.pattern_cycle_index]
        payload = {
            "color": dict(base["color"]),
            "brightness": base["brightness"]
        }
        self.pattern_cycle_index = (self.pattern_cycle_index + 1) % len(self.fixed_colors)
        payload = self.apply_dimmer(payload)
        self.client.publish(topic, json.dumps(payload))
        print(f"[Cycle] {topic} => {payload}")
        time.sleep(self.blink_duration)
        self.client.publish(topic, json.dumps({"state": "OFF"}))
        print(f"[Cycle] {topic} ausgeschaltet.")

    def pattern_flicker(self, topic):
        """
        Muster 2: Flicker-Effekt (zwei schnelle On/Off-Zyklen).
        """
        flicker_times = 2
        for i in range(flicker_times):
            hue = random.randint(0, 360)
            saturation = random.randint(50, 100)
            brightness = random.randint(100, 255)
            payload_on = {
                "color": {"hue": hue, "saturation": saturation},
                "brightness": brightness
            }
            payload_on = self.apply_dimmer(payload_on)
            self.client.publish(topic, json.dumps(payload_on))
            print(f"[Flicker] {topic} ({i+1}/{flicker_times}) => {payload_on}")
            time.sleep(self.blink_duration / 2)
            self.client.publish(topic, json.dumps({"state": "OFF"}))
            time.sleep(self.blink_duration / 2)
        print(f"[Flicker] {topic} Flicker-Effekt beendet.")

    def pattern_strobe(self, topic):
        """
        Muster 3: Strobe-Effekt mit mehreren schnellen On/Off-Zyklen.
        """
        strobe_cycles = 4
        for i in range(strobe_cycles):
            hue = random.randint(0, 360)
            saturation = random.randint(50, 100)
            brightness = random.randint(150, 255)
            payload_on = {
                "color": {"hue": hue, "saturation": saturation},
                "brightness": brightness
            }
            payload_on = self.apply_dimmer(payload_on)
            self.client.publish(topic, json.dumps(payload_on))
            print(f"[Strobe] {topic} ({i+1}/{strobe_cycles}) => {payload_on}")
            time.sleep(self.blink_duration / 4)
            self.client.publish(topic, json.dumps({"state": "OFF"}))
            time.sleep(self.blink_duration / 4)
        print(f"[Strobe] {topic} Strobe-Effekt beendet.")

    def pattern_pulse(self, topic):
        """
        Muster 4: Pulse-Effekt (sanftes Auf- und Abdimmen).
        """
        hue = random.randint(0, 360)
        saturation = random.randint(50, 100)
        target_brightness = random.randint(150, 255)
        steps = 10
        step_duration = self.blink_duration / (steps * 2)

        # Fade-In
        for i in range(steps):
            brightness = int(((i + 1) / steps) * target_brightness)
            payload = {
                "color": {"hue": hue, "saturation": saturation},
                "brightness": brightness
            }
            payload = self.apply_dimmer(payload)
            self.client.publish(topic, json.dumps(payload))
            time.sleep(step_duration)

        # Fade-Out
        for i in range(steps):
            brightness = int(((steps - i - 1) / steps) * target_brightness)
            payload = {
                "color": {"hue": hue, "saturation": saturation},
                "brightness": brightness
            }
            payload = self.apply_dimmer(payload)
            self.client.publish(topic, json.dumps(payload))
            time.sleep(step_duration)

        self.client.publish(topic, json.dumps({"state": "OFF"}))
        print(f"[Pulse] {topic} Pulse-Effekt beendet.")

    def disconnect(self):
        """Trennt die MQTT-Verbindung."""
        self.client.disconnect()
        print("MQTT-Verbindung getrennt.")


# Beispiel zur Verwendung der Klasse:
if __name__ == "__main__":
    BROKER = "mqtt.example.com"
    PORT = 1883
    lamp_topics = [
        "zigbee2mqtt/lamp1/set",
        "zigbee2mqtt/lamp2/set",
        "zigbee2mqtt/lamp3/set",
        "zigbee2mqtt/lamp4/set"
    ]

    beat_controller = BeatLampController(BROKER, PORT, lamp_topics, blink_duration=0.2)

    try:
        pattern_num = int(input("Welches Blinkmuster soll verwendet werden? (0: Random, 1: Cycle, 2: Flicker, 3: Strobe, 4: Pulse): "))
    except ValueError:
        pattern_num = 0
    beat_controller.select_pattern(pattern_num)

    # Globalen Dimmer setzen (z. B. 70% Helligkeit)
    beat_controller.set_global_dimmer(0.7)

    print("Drücke ENTER für einen Beat oder 'q' zum Beenden.")
    try:
        while True:
            user_input = input("Beat? (ENTER für Beat, 'q' zum Beenden): ")
            if user_input.lower() == 'q':
                break
            beat_controller.update_on_beat()
    except KeyboardInterrupt:
        pass

    beat_controller.disconnect()
