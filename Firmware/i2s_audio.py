import os
from machine import I2S
from machine import Pin


def file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def init_audio_input(i2s_id=0, sck_pin=14, ws_pin=15, sd_pin=32, sample_rate_in_hz=8000, sample_size_in_bits=16,
                     mono=True, buffer_length_in_bytes=20000):
    """
    Initializes the I2S interface for audio input.
    """
    # Configure audio format
    format = I2S.MONO if mono else I2S.STEREO

    audio_in = I2S(
        i2s_id,
        sck=Pin(sck_pin),
        ws=Pin(ws_pin),
        sd=Pin(sd_pin),
        mode=I2S.RX,
        bits=sample_size_in_bits,
        format=format,
        rate=sample_rate_in_hz,
        ibuf=buffer_length_in_bytes,
    )

    return audio_in


def cleanup_audio_input(audio_in):
    """
    Cleans up the resources used by the I2S interface.
    """
    audio_in.deinit()
    print("Audio input resources cleaned up")


def record_audio_to_wav(wav_file_path, record_time_in_seconds):
    # ======= I2S CONFIGURATION =======
    SCK_PIN = 14
    WS_PIN = 15
    SD_PIN = 32
    I2S_ID = 0
    BUFFER_LENGTH_IN_BYTES = 40000
    # ======= I2S CONFIGURATION =======

    # ======= AUDIO CONFIGURATION =======
    WAV_FILE = wav_file_path
    RECORD_TIME_IN_SECONDS = record_time_in_seconds
    WAV_SAMPLE_SIZE_IN_BITS = 16
    FORMAT = I2S.MONO
    SAMPLE_RATE_IN_HZ = 8000
    # ======= AUDIO CONFIGURATION =======

    # If the WAV file already exists, delete it
    if file_exists(WAV_FILE):
        os.remove(WAV_FILE)

    format_to_channels = {I2S.MONO: 1, I2S.STEREO: 2}
    NUM_CHANNELS = format_to_channels[FORMAT]
    WAV_SAMPLE_SIZE_IN_BYTES = WAV_SAMPLE_SIZE_IN_BITS // 8
    RECORDING_SIZE_IN_BYTES = (
            RECORD_TIME_IN_SECONDS * SAMPLE_RATE_IN_HZ * WAV_SAMPLE_SIZE_IN_BYTES * NUM_CHANNELS
    )

    def create_wav_header(sampleRate, bitsPerSample, num_channels, num_samples):
        datasize = num_samples * num_channels * bitsPerSample // 8
        o = bytes("RIFF", "ascii")  # (4byte) Marks file as RIFF
        o += (datasize + 36).to_bytes(4, "little")
        o += bytes("WAVE", "ascii")  # (4byte) File type
        o += bytes("fmt ", "ascii")  # (4byte) Format Chunk Marker
        o += (16).to_bytes(4, "little")  # (4byte) Length of above format data
        o += (1).to_bytes(2, "little")  # (2byte) Format type (1 - PCM)
        o += (num_channels).to_bytes(2, "little")  # (2byte)
        o += (sampleRate).to_bytes(4, "little")  # (4byte)
        o += (sampleRate * num_channels * bitsPerSample // 8).to_bytes(4, "little")  # (4byte)
        o += (num_channels * bitsPerSample // 8).to_bytes(2, "little")  # (2byte)
        o += (bitsPerSample).to_bytes(2, "little")  # (2byte)
        o += bytes("data", "ascii")  # (4byte) Data Chunk Marker
        o += (datasize).to_bytes(4, "little")  # (4byte) Data size in bytes
        return o

    wav = open(WAV_FILE, "wb")
    wav_header = create_wav_header(
        SAMPLE_RATE_IN_HZ, WAV_SAMPLE_SIZE_IN_BITS, NUM_CHANNELS, SAMPLE_RATE_IN_HZ * RECORD_TIME_IN_SECONDS
    )
    wav.write(wav_header)

    audio_in = I2S(
        I2S_ID,
        sck=Pin(SCK_PIN),
        ws=Pin(WS_PIN),
        sd=Pin(SD_PIN),
        mode=I2S.RX,
        bits=WAV_SAMPLE_SIZE_IN_BITS,
        format=FORMAT,
        rate=SAMPLE_RATE_IN_HZ,
        ibuf=BUFFER_LENGTH_IN_BYTES,
    )

    mic_samples = bytearray(10000)
    mic_samples_mv = memoryview(mic_samples)

    num_sample_bytes_written_to_wav = 0

    audio_buffer = bytearray()

    print("Recording size: {} bytes".format(RECORDING_SIZE_IN_BYTES))
    print("==========  START RECORDING ==========")
    try:
        while num_sample_bytes_written_to_wav < RECORDING_SIZE_IN_BYTES:
            num_bytes_read_from_mic = audio_in.readinto(mic_samples_mv)
            if num_bytes_read_from_mic > 0:
                num_bytes_to_write = min(num_bytes_read_from_mic,
                                         RECORDING_SIZE_IN_BYTES - num_sample_bytes_written_to_wav)
                num_bytes_written = wav.write(mic_samples_mv[:num_bytes_to_write])
                # 将从麦克风读取的数据添加到缓冲区
                audio_buffer += mic_samples_mv[:num_bytes_read_from_mic]
                num_sample_bytes_written_to_wav += num_bytes_written

        print("==========  DONE RECORDING ==========")
    except (KeyboardInterrupt, Exception) as e:
        print(f"caught exception {type(e).__name__} {e}")

    # Cleanup
    wav.close()
    audio_in.deinit()
    print("Done")


def init_audio_output(i2s_id=1, sck_pin=27, ws_pin=26, sd_pin=25, sample_rate_in_hz=8000, sample_size_in_bits=16,
                      mono=True, buffer_length_in_bytes=10000):
    """
    Initializes the I2S interface for audio output.
    """
    format = I2S.MONO if mono else I2S.STEREO

    audio_out = I2S(
        i2s_id,
        sck=Pin(sck_pin),
        ws=Pin(ws_pin),
        sd=Pin(sd_pin),
        mode=I2S.TX,
        bits=sample_size_in_bits,
        format=format,
        rate=sample_rate_in_hz,
        ibuf=buffer_length_in_bytes,
    )
    return audio_out


def play_audio_sample(audiodata, audio_out, data_index=0):
    """
    Plays provided audio data without initializing or cleaning up I2S interface.
    Assumes audio data skips header and starts at index 44 for WAV files.
    """
    while data_index < len(audiodata):
        end_index = min(data_index + 10000, len(audiodata))
        num_bytes = end_index - data_index
        samples_mv = memoryview(audiodata)[data_index:end_index]
        audio_out.write(samples_mv[:num_bytes])
        data_index += num_bytes


def cleanup_audio_output(audio_out):
    """
    Cleans up the resources used by the I2S interface.
    """
    audio_out.deinit()
    print("Audio output resources cleaned up")


def play_audio(audiodata, sample_rate_in_hz=8000, sample_size_in_bits=16, mono=True, i2s_id=1, sck_pin=27, ws_pin=26,
               sd_pin=25, buffer_length_in_bytes=10000):
    """
    Play provided audio data using I2S interface.

    :param audiodata: The byte array of audio data.
    :param sample_rate_in_hz: The sample rate of the audio data in Hz.
    :param sample_size_in_bits: Bit depth of audio samples.
    :param mono: Set True for mono audio, False for stereo.
    :param i2s_id: The ID for the I2S peripheral.
    :param sck_pin: The Serial Clock (SCK) pin.
    :param ws_pin: The Word Select (WS) pin.
    :param sd_pin: The Serial Data (SD) pin.
    :param buffer_length_in_bytes: The internal buffer size in bytes.
    """
    # Configure audio format
    format = I2S.MONO if mono else I2S.STEREO

    # Initialize I2S interface
    audio_out = I2S(
        i2s_id,
        sck=Pin(sck_pin),
        ws=Pin(ws_pin),
        sd=Pin(sd_pin),
        mode=I2S.TX,
        bits=sample_size_in_bits,
        format=format,
        rate=sample_rate_in_hz,
        ibuf=buffer_length_in_bytes,
    )

    # Assume audio data skips header and starts at index 44 for WAV files
    data_index = 44
    while data_index < len(audiodata):
        end_index = min(data_index + 10000, len(audiodata))
        num_bytes = end_index - data_index
        samples_mv = memoryview(audiodata)[data_index:end_index]
        audio_out.write(samples_mv[:num_bytes])
        data_index += num_bytes

    # Cleanup
    audio_out.deinit()
    print("Playback finished and resources cleaned up")


def play_audio_from_file(file_path, sample_rate_in_hz=8000, sample_size_in_bits=16, mono=True, i2s_id=0, sck_pin=27,
                         ws_pin=26, sd_pin=25, buffer_size=4096, buffer_length_in_bytes=20000):
    """Plays audio from a file using I2S interface.

    :param file_path: Path to the audio file.
    :param sample_rate_in_hz: The sample rate of the audio data in Hz.
    :param sample_size_in_bits: Bit depth of audio samples.
    :param mono: Set True for mono audio, False for stereo.
    :param i2s_id: The ID for the I2S peripheral.
    :param sck_pin: The Serial Clock (SCK) pin.
    :param ws_pin: The Word Select (WS) pin.
    :param sd_pin: The Serial Data (SD) pin.
    :param buffer_size: Size of the buffer used for reading audio file chunks.
    """
    # Ensure the file exists
    if not file_exists(file_path):
        print("Audio file does not exist")
        return

    # Configure audio format
    format_type = I2S.MONO if mono else I2S.STEREO

    # Initialize I2S interface
    audio_out = I2S(
        i2s_id,
        sck=Pin(sck_pin),
        ws=Pin(ws_pin),
        sd=Pin(sd_pin),
        mode=I2S.TX,
        bits=sample_size_in_bits,
        format=format_type,
        rate=sample_rate_in_hz,
        # other possible parameters depending on your hardware and library
        ibuf=buffer_length_in_bytes,
    )

    try:
        with open(file_path, 'rb') as f:
            # Assuming the audio file has a header that we need to skip.
            # For a WAV file, headers are typically 44 bytes long.
            f.seek(44)

            chunk = f.read(buffer_size)
            while chunk:
                audio_out.write(chunk)
                chunk = f.read(buffer_size)

            print("Playback finished")

    except Exception as e:
        print("An error occurred during playback:", str(e))

    finally:
        # Cleanup
        audio_out.deinit()
        print("Resources cleaned up")


def is_silence(samples, threshold=500):
    """
    判断给定的采样数据是否为静音。
    根据采样数据的振幅平均值与预设阈值比较来判断。
    
    :param samples: 采样数据的memoryview或bytearray。
    :param threshold: 判断为静音的阈值。
    :return: 如果是静音则返回True，否则返回False。
    """
    # 将bytearray转换为整数进行振幅判断
    amplitude_sum = 0
    for sample in samples:
        amplitude_sum += abs(sample - 128)  # 假设采样数据为8位，中间值为128
    average_amplitude = amplitude_sum / len(samples)
    return average_amplitude < threshold


def slice_audio(audio_stream, slice_size=1000):
    """
    将音频流以指定大小切片。
    :param audio_stream: 音频流的memoryview或bytearray。
    :param slice_size: 每片的大小，单位为字节。
    :return: 生成器，按片输出音频数据。
    """
    for i in range(0, len(audio_stream), slice_size):
        yield audio_stream[i:i + slice_size]
