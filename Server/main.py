import os
import threading
import queue

from dotenv import load_dotenv

import azure.cognitiveservices.speech as speechsdk

from azureSpeechService import AzureSpeechService
from difyChatClient import DifyChatClient
from mqttService import MQTTService
from streamProcessor import StreamProcessor

load_dotenv()

# Initialize Azure Voice Service and DIFY client
SPEECH_KEY = os.getenv('SPEECH_KEY')
SERVICE_REGION = os.getenv('SERVICE_REGION')
RECOGNITION_LANGUAGE = os.getenv('RECOGNITION_LANGUAGE')
SYNTHESIS_VOICE_NAME = os.getenv('SYNTHESIS_VOICE_NAME')

DIFY_API_KEY = os.getenv('DIFY_API_KEY')
DIFY_BASE_URL = os.getenv('DIFY_BASE_URL')

MQTT_BROKER = os.getenv('MQTT_BROKER')
MQTT_PORT = 1883
MQTT_AUDIO_TOPIC = "audio"
MQTT_MIC_TOPIC = "mic"
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_CLIENT_ID = "robot_server"

# Global variable, used for handling accumulated audio data.
last_message_time = None

# Create a thread-safe queue
data_queue = queue.Queue()


class Application:
    def __init__(self):
        self.azure_speech_service = AzureSpeechService(speech_key=SPEECH_KEY,
                                                       service_region=SERVICE_REGION,
                                                       mqtt_audio_topic=MQTT_AUDIO_TOPIC,
                                                       recognition_language=RECOGNITION_LANGUAGE,
                                                       synthesis_voice_name=SYNTHESIS_VOICE_NAME,
                                                       output_format=speechsdk
                                                       .SpeechSynthesisOutputFormat
                                                       .Raw16Khz16BitMonoPcm,
                                                       data_queue=data_queue)

        self.dify_chat_client = DifyChatClient(DIFY_API_KEY, DIFY_BASE_URL)
        self.mqtt_service = MQTTService(MQTT_BROKER,
                                        MQTT_PORT,
                                        MQTT_AUDIO_TOPIC,
                                        MQTT_MIC_TOPIC,
                                        MQTT_USER,
                                        MQTT_PASSWORD,
                                        MQTT_CLIENT_ID)
        self.stream_processor = StreamProcessor(self.azure_speech_service)

    def main(self):
        try:
            self.mqtt_service.listen_mqtt(self.on_message_callback)
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            print("Attempting to restart the application...")
            #self.main()

    def on_message_callback(self, nil, userdata, message):
        global last_message_time
        if message.payload == b"END":
            print("Received End Signal, processing audio data.")
            if last_message_time is not None:
                last_message_time.cancel()
                last_message_time = None
                print("Timer cancelled on END signal.")
            self.end_accumulate(userdata)
        else:
            userdata['audio_chunks'].append(message.payload)
            print("Received audio chunk, accumulating.")
            if last_message_time is not None:
                last_message_time.cancel()
                print("Timer cancelled on new chunk.")
            self.schedule_end_accumulate(userdata)

    def end_accumulate(self, userdata):
        global last_message_time
        last_message_time = None
        print("Timer triggered.")
        if userdata['audio_chunks']:
            if len(userdata['audio_chunks']) > 1:
                print("Processing accumulated audio chunks.")
                complete_audio_data = b''.join(userdata['audio_chunks'])
                recognized_text = self.azure_speech_service.recognize_speech_from_bytes(complete_audio_data)
                if recognized_text:
                    self.dify_chat_client.handle_dify_dialog(recognized_text, userdata, self.stream_processor)

            userdata['audio_chunks'] = []
        else:
            print("No audio chunks to process.")

    def schedule_end_accumulate(self, userdata):
        global last_message_time
        if last_message_time is not None:
            last_message_time.cancel()
        last_message_time = threading.Timer(3.0, lambda: self.end_accumulate(userdata))
        last_message_time.start()
        print("New timer scheduled with audio chunks count: ", len(userdata['audio_chunks']))


def mqtt_sender(mqtt_service):
    while True:
        # Retrieve data from the queue, block until data is available.
        topic, data = data_queue.get()
        if topic is None:
            break  # None as a stop signal

        mqtt_service.publish_audio_to_device(topic, data, )
        #print(f"Sent data of size {len(data)} to {topic}")


if __name__ == '__main__':
    app = Application()

    # Start sending thread
    sender_thread = threading.Thread(target=mqtt_sender, args=(app.mqtt_service,), daemon=True)
    sender_thread.start()

    app.main()
