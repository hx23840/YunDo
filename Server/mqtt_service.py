import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish


class MQTTService:
    def __init__(self, broker, port, audio_topic, mic_topic, robot_topic, user, password, client_id):
        self.MQTT_BROKER = broker
        self.MQTT_PORT = port
        self.MQTT_AUDIO_TOPIC = audio_topic
        self.MQTT_MIC_TOPIC = mic_topic
        self.MQTT_ROBOT_TOPIC = robot_topic
        self.MQTT_USER = user
        self.MQTT_PASSWORD = password
        self.MQTT_CLIENT_ID = client_id
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=self.MQTT_CLIENT_ID,
                                  clean_session=True,
                                  userdata={'audio_chunks': [], 'conversation_id': None})
        self.client.username_pw_set(self.MQTT_USER, self.MQTT_PASSWORD)

    def get_client_id(self):
        return self.MQTT_CLIENT_ID

    def publish_data_to_device(self, topic, data):
        if data:
            chunk_size = 20000
            for start in range(0, len(data), chunk_size):
                end = start + chunk_size
                publish.single(topic, data[start:end], hostname=self.MQTT_BROKER, qos=0,
                               auth={'username': self.MQTT_USER, 'password': self.MQTT_PASSWORD})

    def on_connect(self, userdata, connect_flags, reason_code, properties, nil):
        print("Connected with result code " + str(reason_code))
        self.client.subscribe(self.MQTT_MIC_TOPIC)

    def listen_mqtt(self, on_message_callback):
        self.client.on_message = on_message_callback
        self.client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
        self.client.on_connect = self.on_connect
        print("Starting to listen for MQTT messages...")
        self.client.loop_forever()
