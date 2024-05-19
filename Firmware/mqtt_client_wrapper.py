import sys
sys.path.insert(0, '/lib')

from umqtt.robust import MQTTClient
from machine import Pin, WDT, I2S
import ubinascii
import machine
import uasyncio as asyncio
from i2s_audio import play_audio_from_file


class MQTTClientWrapper:
    # A wrapper class for managing an MQTT client
    def __init__(self,
                 led_data_pin,
                 led_mqtt_pin,
                 mqtt_broker,
                 mqtt_port,
                 mqtt_audio_topic,
                 mqtt_mic_topic,
                 mqtt_user,
                 mqtt_password):
        self.led_data = Pin(led_data_pin, Pin.OUT)  # Data LED pin
        self.led_mqtt = Pin(led_mqtt_pin, Pin.OUT)  # WiFi LED pin

        self.mqtt_broker = mqtt_broker  # MQTT broker address
        self.mqtt_port = mqtt_port  # MQTT broker port
        self.mqtt_audio_topic = mqtt_audio_topic  # Topic for audio data
        self.mqtt_mic_topic = mqtt_mic_topic  # Topic for microphone data
        self.mqtt_user = mqtt_user  # MQTT user
        self.mqtt_password = mqtt_password  # MQTT password
        self.client_id = f'esp32_{ubinascii.hexlify(machine.unique_id()).decode()}'  # Unique MQTT client ID
        self.client = None
        
        self.client = MQTTClient(client_id=self.client_id, server=self.mqtt_broker, user=self.mqtt_user,
                                 password=self.mqtt_password, keepalive=60)

    def connect(self):
        # Connects to the MQTT broker and subscribes to the audio topic
        self.client.DEBUG = True

        self.client.connect(clean_session=True)
        
        print("Initializing subscriptions")
        self.client.add_subscription(self.mqtt_audio_topic)
        
        print("Starting to listen for MQTT messages...")

        # Start led
        self.led_mqtt.value(1)

        # Play start sound
        play_audio_from_file(file_path="res/init.wav", sample_rate_in_hz=16000, sample_size_in_bits=16, mono=False)

    def publish(self, topic, msg, retain=False, qos=0):
        # Publish a message to a given MQTT topic
        self.client.publish(topic, msg, qos=qos)

    async def listen(self):
        # Coroutine to continuously listen for incoming MQTT messages
        while True:
            self.client.check_msg()
            await asyncio.sleep_ms(1)  # Allows coroutine switching

    def set_callback(self, callback):
        # Sets the callback function for received messages
        self.client.set_callback(callback)
