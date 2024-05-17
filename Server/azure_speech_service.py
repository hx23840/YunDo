import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech.audio import PullAudioInputStreamCallback, PullAudioInputStream


class ByteArrayAudioStream(PullAudioInputStreamCallback):
    def __init__(self, audio_data):
        super().__init__()
        self._audio_data = audio_data
        self._position = 0

    def read(self, buffer):
        buffer_length = len(buffer)
        remaining_audio_data = len(self._audio_data) - self._position
        if remaining_audio_data == 0:
            return 0
        bytes_to_write = min(buffer_length, remaining_audio_data)
        buffer[:bytes_to_write] = self._audio_data[self._position:self._position + bytes_to_write]
        self._position += bytes_to_write
        return bytes_to_write

    def close(self):
        pass


class AzureSpeechService:
    def __init__(self,
                 speech_key,
                 service_region,
                 mqtt_audio_topic,
                 recognition_language,
                 synthesis_voice_name,
                 output_format,
                 data_queue):
        self.speech_key = speech_key
        self.service_region = service_region
        self.mqtt_audio_topic = mqtt_audio_topic
        self.speech_config = self.create_speech_config(recognition_language, synthesis_voice_name, output_format)
        self.data_queue = data_queue

    def create_speech_config(self, recognition_language, synthesis_voice_name, output_format):
        speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.service_region)
        speech_config.speech_recognition_language = recognition_language
        speech_config.speech_synthesis_voice_name = synthesis_voice_name
        speech_config.set_speech_synthesis_output_format(output_format)
        return speech_config

    def synthesis_callback(self, evt):
        if evt.result.reason == speechsdk.ResultReason.SynthesizingAudio:
            audio_data = evt.result.audio_data
            if audio_data:
                self.data_queue.put((self.mqtt_audio_topic, audio_data))

    def setup_synthesizer(self):
        # This method creates and returns a well-configured synthesizer, using the given data_queue for
        # synthesis_callback.
        stream = speechsdk.audio.PullAudioOutputStream()
        audio_config = speechsdk.audio.AudioOutputConfig(stream=stream)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=audio_config)

        # Use internal functions instead of lambda expressions to connect events.
        def event_handler(evt):
            self.synthesis_callback(evt)

        synthesizer.synthesizing.connect(event_handler)
        return synthesizer

    def text_to_speech(self, text):
        synthesizer = self.setup_synthesizer()
        result = synthesizer.speak_text_async(text).get()
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("Audio synthesis completed.")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"Synthesis has been cancelled：{cancellation_details.reason}")

    def recognize_speech_from_bytes(self, audio_bytes):
        try:
            my_callback = ByteArrayAudioStream(audio_bytes)
            stream = speechsdk.audio.PullAudioInputStream(my_callback)
            audio_config = speechsdk.audio.AudioConfig(stream=stream)
            recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=audio_config)
            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return result.text
            else:
                print(f"Voice recognition failure：{result.reason}")
        except Exception as e:
            print(f"An error occurred in voice recognition：{e}")
            return None
