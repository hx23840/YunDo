import uasyncio as asyncio
import utime

from audio_system import AudioSystem
from mqtt_client_wrapper import MQTTClientWrapper
from network_manager import NetworkManager
from i2s_audio import play_audio_from_file
import machine

# Pin definitions for LEDs on the board
LED3 = 2  # Pin for LED3
LED2 = 18  # Pin for LED2
LED1 = 19  # Pin for LED1

# Configuration Section - Modify the configurations here
SSID = "YOUR_SSID_HERE"  # The WiFi SSID to connect to
PASSWORD = "YOUR_PASSWORD_HERE"  # The WiFi password
MQTT_BROKER = "YOUR_MQTT_BROKER_IP_HERE"  # The IP address of the MQTT broker
MQTT_USER = "YOUR_MQTT_USER_HERE"  # The MQTT username
MQTT_PASSWORD = "YOUR_MQTT_PASSWORD_HERE"  # The MQTT password


async def main():
    try:
        # Network connection setup
        network_manager = NetworkManager(ssid=SSID, password=PASSWORD)
        network_manager.connect()

        # Wait for network connection to establish
        while not network_manager.sta_if.isconnected():
            print("Waiting for network connection...")
            utime.sleep(5)

        # Setup MQTT client
        mqtt_client = MQTTClientWrapper(led_data_pin=2,
                                        led_mqtt_pin=19,
                                        mqtt_broker=MQTT_BROKER,
                                        mqtt_port=1883,
                                        mqtt_audio_topic="audio",
                                        mqtt_mic_topic="mic",
                                        mqtt_user=MQTT_USER,
                                        mqtt_password=MQTT_PASSWORD)

        # Initialize audio system
        audio_system = AudioSystem(button_pin=0,
                                   mqtt_mic_topic="mic",
                                   mqtt_audio_topic="audio",
                                   client=mqtt_client,
                                   sample_rate_in_hz_input=16000,
                                   sample_rate_in_hz_output=16000)

        mqtt_client.set_callback(audio_system.on_audio_data)
        mqtt_client.connect()

        await asyncio.gather(
            audio_system.record_audio(),
            audio_system.play_audio_queue(),
            mqtt_client.listen(),
            #network_manager.monitor()  # Optional: Monitor network connectivity
        )
    except Exception as e:
        print("Anomaly detected, restarting now:", e)
        # Play restart sound
        play_audio_from_file(file_path="res/restart.wav", sample_rate_in_hz=16000, sample_size_in_bits=16, mono=False)

        machine.reset()


if __name__ == "__main__":
    asyncio.run(main())
