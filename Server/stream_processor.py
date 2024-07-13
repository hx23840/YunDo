class StreamProcessor:
    def __init__(self, azure_speech_service):
        self.azure_speech_service = azure_speech_service
        self.buffer = ""
        self.punctuations = ("，。！？；：｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～｟｠｢｣､、〃《》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿–—''‛""„‟…‧﹏.!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~\r\n\t")

    def process_and_print(self, char):
        if char.strip() and char not in self.punctuations:
            self.buffer += char
        elif char in self.punctuations:
            if len(self.buffer) >= 20:
                print(f"***{self.buffer}***{char}")
                self.azure_speech_service.text_to_speech(self.buffer)
                self.buffer = ""
            else:
                self.buffer += char

    def process_stream(self, lines):
        if lines is None:
            if self.buffer and len(self.buffer) > 0:
                print(f"***{self.buffer}***")
                self.azure_speech_service.text_to_speech(self.buffer)
                if len(self.buffer) < 10:
                    self.azure_speech_service.robot_cmd(self.buffer)
                self.buffer = ""
            print("Error: No data provided.")
            return
        for line in lines:
            for char in line:
                self.process_and_print(char)