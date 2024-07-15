import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech.audio import AudioStreamFormat, PushAudioInputStream
import time
import threading
from queue import Queue


class AzureSpeechService:
    def __init__(self, speech_key, service_region, mqtt_audio_topic, robot_topic, recognition_language,
                 synthesis_voice_name, output_format, data_queue):
        self.speech_key = speech_key
        self.service_region = service_region
        self.mqtt_audio_topic = mqtt_audio_topic
        self.mqtt_robot_topic = robot_topic
        self.speech_config = self.create_speech_config(recognition_language, synthesis_voice_name, output_format)
        self.data_queue = data_queue
        self.speech_recognizer = None
        self.push_stream = None
        self.audio_config = None
        self.recognized_callback = None
        self.last_audio_time = None
        self.speech_timeout = 2.0  # 2秒没有新的音频输入就认为说话结束并停止识别
        self.timeout_timer = None
        self.is_recognizing = False
        self.synthesizer = self.setup_synthesizer()
        self.tts_queue = Queue()
        self.tts_thread = threading.Thread(target=self.tts_worker, daemon=True)
        self.tts_thread.start()
        self.tts_buffer = b""
        self.tts_buffer_size = 32000  # 大约2秒的音频数据 (16kHz, 16-bit)
        self.tts_buffer_lock = threading.Lock()

    def create_speech_config(self, recognition_language, synthesis_voice_name, output_format):
        speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.service_region)
        speech_config.speech_recognition_language = recognition_language
        speech_config.speech_synthesis_voice_name = synthesis_voice_name
        speech_config.set_speech_synthesis_output_format(output_format)
        return speech_config

    def setup_recognizer(self, callback):
        self.recognized_callback = callback
        self.reset_recognizer()

    def reset_recognizer(self):
        audio_format = AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
        print(f"Setting up audio stream with format: {audio_format}")
        self.push_stream = PushAudioInputStream(audio_format)
        self.audio_config = speechsdk.audio.AudioConfig(stream=self.push_stream)
        self.speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config,
                                                            audio_config=self.audio_config)

        self.speech_recognizer.recognizing.connect(lambda evt: print('RECOGNIZING: {}'.format(evt)))
        self.speech_recognizer.recognized.connect(self.handle_final_result)
        self.speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
        self.speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
        self.speech_recognizer.canceled.connect(self.on_canceled)

    def start_timeout_timer(self):
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.timeout_timer = threading.Timer(self.speech_timeout, self.stop_recognition)
        self.timeout_timer.start()

    def process_audio_chunk(self, audio_chunk):
        if self.push_stream:
            try:
                self.push_stream.write(audio_chunk)
                self.last_audio_time = time.time()
                print(f"Successfully wrote {len(audio_chunk)} bytes to the push stream")

                if not self.is_recognizing:
                    self.start_continuous_recognition()

                self.start_timeout_timer()  # 重置超时定时器
            except Exception as e:
                print(f"Error writing to push stream: {e}")
                self.reset_recognizer()  # 错误发生时重置识别器
        else:
            print("Push stream is not initialized")
            self.reset_recognizer()

    def start_continuous_recognition(self):
        if not self.speech_recognizer:
            print("Error: Speech recognizer is not set up. Resetting recognizer...")
            self.reset_recognizer()

        if not self.is_recognizing:
            print("Starting continuous recognition...")
            self.is_recognizing = True
            self.speech_recognizer.start_continuous_recognition()

    def stop_recognition(self):
        if self.speech_recognizer and self.is_recognizing:
            print("Stopping recognition...")
            self.speech_recognizer.stop_continuous_recognition()
            self.is_recognizing = False
        if self.timeout_timer:
            self.timeout_timer.cancel()
        print("Recognition stopped")

    def handle_final_result(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f"FINAL RESULT: {evt.result.text}")
            if self.recognized_callback:
                self.recognized_callback(evt.result.text)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech could be recognized")

        # 识别结果处理完后，重置状态以准备下一次识别
        self.is_recognizing = False
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.reset_recognizer()  # 每次识别结束后重置识别器

    def on_canceled(self, evt):
        print(f"CANCELED: {evt}")
        cancellation_details = evt.cancellation_details
        print(f"CANCELED: Reason={cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"CANCELED: ErrorDetails={cancellation_details.error_details}")

        self.is_recognizing = False
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.reset_recognizer()  # 取消事件发生时重置识别器

    def setup_synthesizer(self):
        print("Setting up synthesizer")
        stream = speechsdk.audio.PullAudioOutputStream()
        audio_config = speechsdk.audio.AudioOutputConfig(stream=stream)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=audio_config)
        synthesizer.synthesizing.connect(self.synthesis_callback)
        synthesizer.synthesis_completed.connect(self.on_synthesis_completed)
        print("Synthesizer setup complete")
        return synthesizer

    def synthesis_callback(self, evt):
        if evt.result.reason == speechsdk.ResultReason.SynthesizingAudio:
            audio_data = evt.result.audio_data
            if audio_data:
                with self.tts_buffer_lock:
                    self.tts_buffer += audio_data
                    if len(self.tts_buffer) >= self.tts_buffer_size:
                        print(f"Sending {len(self.tts_buffer)} bytes of audio data to MQTT queue")
                        self.data_queue.put((self.mqtt_audio_topic, self.tts_buffer))
                        self.tts_buffer = b""
            else:
                print("No audio data received in synthesis event")

    def on_synthesis_completed(self, evt):
        with self.tts_buffer_lock:
            if self.tts_buffer:
                print(
                    f"Synthesis completed. Sending remaining {len(self.tts_buffer)} bytes of audio data to MQTT queue")
                self.data_queue.put((self.mqtt_audio_topic, self.tts_buffer))
                self.tts_buffer = b""

    def text_to_speech(self, text):
        print(f"Queueing text for synthesis: {text}")
        self.tts_queue.put(text)

    def tts_worker(self):
        while True:
            text = self.tts_queue.get()
            print(f"Processing text-to-speech for: {text}")

            try:
                result = self.synthesizer.speak_text_async(text).get()
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    print("Synthesis completed successfully")
                else:
                    print(f"Synthesis failed: {result.reason}")
            except Exception as e:
                print(f"An error occurred during synthesis: {e}")

            self.tts_queue.task_done()

    def robot_cmd(self, cmd):
        print(f"发送命令到机器人: {cmd} {self.mqtt_robot_topic}")
        self.data_queue.put((self.mqtt_robot_topic, cmd))