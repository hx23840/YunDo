import requests
import json


class DifyChatClient:
    def __init__(self, api_key, base_url, user_id='esp32-001', response_mode='streaming'):
        self.api_key = api_key
        self.base_url = base_url
        self.user_id = user_id
        self.response_mode = response_mode

    def handle_dify_dialog(self, query, userdata, processor):
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "inputs": {},
                "query": query,
                "user": self.user_id,
                "response_mode": self.response_mode,
                "conversation_id": userdata.get('conversation_id')
            }

            chat_response = requests.post(
                f"{self.base_url}/chat-messages",
                headers=headers,
                json=payload,
                stream=True
            )
            chat_response.raise_for_status()

            for line in chat_response.iter_lines(decode_unicode=True):
                line = line.split('data:', 1)[-1].strip()
                if line:
                    try:
                        line_json = json.loads(line)
                        processor.process_stream(line_json.get('answer'))
                        if userdata['conversation_id'] is None and 'conversation_id' in line_json:
                            userdata['conversation_id'] = line_json['conversation_id']
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON: {line}")
        except Exception as e:
            print(f"Error handling dialog: {e}")