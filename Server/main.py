import os
import threading
from queue import Queue
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import time

from azure_speech_service import AzureSpeechService
from dify_chat_client import DifyChatClient
from mqtt_service import MQTTService
from stream_processor import StreamProcessor

load_dotenv()


class Application:
    def __init__(self):
        self.data_queue = Queue()
        self.azure_speech_service = AzureSpeechService(
            speech_key=os.getenv('SPEECH_KEY'),
            service_region=os.getenv('SERVICE_REGION'),
            mqtt_audio_topic=os.getenv('MQTT_AUDIO_TOPIC'),
            robot_topic=os.getenv('MQTT_ROBOT_TOPIC'),
            recognition_language=os.getenv('RECOGNITION_LANGUAGE'),
            synthesis_voice_name=os.getenv('SYNTHESIS_VOICE_NAME'),
            output_format=speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm,
            data_queue=self.data_queue
        )

        self.mqtt_service = MQTTService(
            broker=os.getenv('MQTT_BROKER'),
            port=1883,
            audio_topic=os.getenv('MQTT_AUDIO_TOPIC'),
            mic_topic=os.getenv('MQTT_MIC_TOPIC'),
            robot_topic=os.getenv('MQTT_ROBOT_TOPIC'),
            user=os.getenv('MQTT_USER'),
            password=os.getenv('MQTT_PASSWORD'),
            client_id="robot_server"
        )

        self.dify_chat_client = DifyChatClient(
            api_key=os.getenv('DIFY_API_KEY'),
            base_url=os.getenv('DIFY_BASE_URL')
        )

        self.stream_processor = StreamProcessor(self.azure_speech_service)

    def main(self):
        try:
            print("Setting up speech recognizer...")
            self.azure_speech_service.setup_recognizer(self.handle_recognized_text)

            print("Setting up MQTT...")
            self.mqtt_service.listen_mqtt(self.on_message_callback)

            # Keep the main thread running
            while not self.azure_speech_service.done:
                time.sleep(0.1)
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            print("Application is shutting down...")

    def on_message_callback(self, nil, userdata, message):
        if message.topic == self.mqtt_service.MQTT_MIC_TOPIC:
            self.azure_speech_service.process_audio_chunk(message.payload)

    def handle_recognized_text(self, recognized_text):
        if recognized_text:
            print(f"Recognized text: {recognized_text}")
            self.dify_chat_client.handle_dify_dialog(recognized_text, {'conversation_id': None}, self.stream_processor)

    def mqtt_sender(self):
        while True:
            topic, data = self.data_queue.get()
            if topic is None:
                break
            self.mqtt_service.publish_data_to_device(topic, data)

    def run(self):
        sender_thread = threading.Thread(target=self.mqtt_sender, daemon=True)
        sender_thread.start()
        self.main()


if __name__ == "__main__":
    app = Application()
    app.run()