from i2s_audio import play_audio_sample, init_audio_input, init_audio_output, play_audio_from_file, \
    cleanup_audio_output, cleanup_audio_input
from collections import deque
from machine import Pin, WDT, I2S
import gc
import uasyncio as asyncio
import utime


class AudioSystem:
    def __init__(self, button_pin, mqtt_mic_topic, mqtt_audio_topic, client, sample_rate_in_hz_input=16000,
                 sample_rate_in_hz_output=16000):
        # Button for starting/stopping recording
        self.button_pin = Pin(button_pin, Pin.IN, Pin.PULL_UP)
        self.is_recording = False
        self.record_size = 0
        self.mqtt_mic_topic = mqtt_mic_topic
        self.mqtt_audio_topic = mqtt_audio_topic
        self.client = client
        # Initialize audio input and output with different sample rates
        self.audio_in = self.init_audio_input(sample_rate_in_hz=sample_rate_in_hz_input)
        self.audio_out = self.init_audio_output(sample_rate_in_hz=sample_rate_in_hz_output)
        self.audio_queue = deque((), 10)
        # Setup button press interrupt for starting/stopping recording
        self.button_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self.start_or_stop_recording)

        self.sample_rate_in_hz_input = sample_rate_in_hz_input
        self.sample_rate_in_hz_output = sample_rate_in_hz_output

    def init_audio_input(self, sample_rate_in_hz=16000):
        return init_audio_input(mono=True, sample_rate_in_hz=sample_rate_in_hz)

    def init_audio_output(self, sample_rate_in_hz=16000):
        return init_audio_output(mono=True, sample_rate_in_hz=sample_rate_in_hz)

    def start_or_stop_recording(self, pin):
        utime.sleep_ms(100)  # Debounce delay

        if pin.value() == 0:  # If button pressed
            # 资源回收
            gc.collect()

            self.is_recording = True
            self.record_size = 0

            audio_in = init_audio_input(mono=True, sample_rate_in_hz=self.sample_rate_in_hz_input)

            cleanup_audio_output(self.audio_out)

            print("Start Record")
        elif pin.value() == 1:  # If button released
            self.is_recording = False
            self.client.publish(self.mqtt_mic_topic, "END", qos=0)

            self.audio_out = init_audio_output(mono=True, sample_rate_in_hz=self.sample_rate_in_hz_output)

            if self.audio_in:
                cleanup_audio_input(self.audio_in)

            # 资源回收
            gc.collect()

            print("Stop Record")

    async def record_audio(self):
        while True:
            try:
                if self.is_recording:
                    mic_samples = bytearray(1000)
                    mic_samples_mv = memoryview(mic_samples)
                    num_bytes_read_from_mic = self.audio_in.readinto(mic_samples_mv)
                    if num_bytes_read_from_mic > 0:
                        self.record_size += 1
                        print("Recorded audio chunks count:", self.record_size)
                        self.client.publish(self.mqtt_mic_topic, mic_samples[:num_bytes_read_from_mic], qos=0)
                        await asyncio.sleep_ms(5)
                else:
                    await asyncio.sleep_ms(10)
            except Exception as e:
                print(f"Error collecting microphone data: {e}")
                await asyncio.sleep_ms(10)

    def on_audio_data(self, topic, msg):
        if topic.decode() == self.mqtt_audio_topic:
            self.audio_queue.append(msg)
            print("Audio data enqueued")

    async def play_audio_queue(self):
        while True:
            try:
                if self.audio_queue:
                    audio_data = self.audio_queue.popleft()
                    print("Starting audio playback...")
                    self.audio_out.write(audio_data)
                    print("Audio playback finished")
                else:
                    await asyncio.sleep_ms(3)
            except Exception as e:
                print(f"Error during audio playback: {e}")
                await asyncio.sleep_ms(10)
