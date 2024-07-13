import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech.audio import AudioStreamFormat, PushAudioInputStream
import time
import threading


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
        self.done = False
        self.recognized_callback = None
        self.last_audio_time = None
        self.audio_timeout = 2.0  # 2秒没有音频输入就停止识别
        self.timeout_timer = None
        self.is_recognizing = False
        self.synthesizer = self.setup_synthesizer()  # 初始化时创建合成器

    def create_speech_config(self, recognition_language, synthesis_voice_name, output_format):
        speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.service_region)
        speech_config.speech_recognition_language = recognition_language
        speech_config.speech_synthesis_voice_name = synthesis_voice_name
        speech_config.set_speech_synthesis_output_format(output_format)
        return speech_config

    def setup_recognizer(self, callback):
        self.recognized_callback = callback
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
        self.speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))

        self.speech_recognizer.session_stopped.connect(self.stop_cb)
        self.speech_recognizer.canceled.connect(self.stop_cb)

    def handle_final_result(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f"RECOGNIZED: {evt.result.text}")
            if self.recognized_callback:
                self.recognized_callback(evt.result.text)

    def stop_cb(self, evt):
        print('CLOSING on {}'.format(evt))
        self.is_recognizing = False
        if self.timeout_timer:
            self.timeout_timer.cancel()

    def start_recognition(self):
        if not self.speech_recognizer:
            print("Error: Speech recognizer is not set up. Call setup_recognizer first.")
            return

        if not self.is_recognizing:
            self.is_recognizing = True
            self.done = False
            print("Starting continuous recognition...")
            self.speech_recognizer.start_continuous_recognition()
            self.start_timeout_timer()

    def start_timeout_timer(self):
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.timeout_timer = threading.Timer(1.0, self.check_audio_timeout)
        self.timeout_timer.start()

    def check_audio_timeout(self):
        if self.is_recognizing and time.time() - self.last_audio_time > self.audio_timeout:
            print("音频输入超时，停止识别")
            self.stop_recognition()
        elif self.is_recognizing:
            self.start_timeout_timer()

    def stop_recognition(self):
        if self.is_recognizing:
            self.is_recognizing = False
            self.done = True
            if self.speech_recognizer:
                self.speech_recognizer.stop_continuous_recognition()
            if self.timeout_timer:
                self.timeout_timer.cancel()
            print("Recognition stopped")

    def process_audio_chunk(self, audio_chunk):
        if self.push_stream:
            try:
                self.push_stream.write(audio_chunk)
                self.last_audio_time = time.time()  # 更新最后接收音频的时间
                if not self.is_recognizing:
                    self.start_recognition()
                else:
                    self.start_timeout_timer()  # 重置超时定时器
            except Exception as e:
                print(f"Error writing to push stream: {e}")
        else:
            print("Push stream is not initialized")

    def synthesis_callback(self, evt):
        if evt.result.reason == speechsdk.ResultReason.SynthesizingAudio:
            audio_data = evt.result.audio_data
            if audio_data:
                self.data_queue.put((self.mqtt_audio_topic, audio_data))
            else:
                print("No audio data received in synthesis event")

    def setup_synthesizer(self):
        print("Setting up synthesizer")
        stream = speechsdk.audio.PullAudioOutputStream()
        audio_config = speechsdk.audio.AudioOutputConfig(stream=stream)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=audio_config)
        synthesizer.synthesizing.connect(self.synthesis_callback)
        print("Synthesizer setup complete")
        return synthesizer

    def robot_cmd(self, cmd):
        print(f"发送命令到机器人: {cmd} {self.mqtt_robot_topic}")
        self.data_queue.put((self.mqtt_robot_topic, cmd))

    def text_to_speech(self, text):
        print(f"Starting text-to-speech for text: {text}")

        def synthesis_completed(evt):
            print(f"音频合成完成。Event: {evt}")

        def synthesis_canceled(evt):
            cancellation_details = evt.cancellation_details
            print(f"合成已取消：{cancellation_details.reason}")

        # 连接事件处理器
        self.synthesizer.synthesis_completed.connect(synthesis_completed)
        self.synthesizer.synthesis_canceled.connect(synthesis_canceled)

        # 开始异步合成
        print("Starting asynchronous synthesis")
        future = self.synthesizer.speak_text_async(text)

        try:
            result = future.get()
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print("Synthesis completed successfully")
            else:
                print(f"Synthesis failed: {result.reason}")
        except Exception as e:
            print(f"An error occurred during synthesis: {e}")
