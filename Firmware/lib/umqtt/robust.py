import utime
from . import simple


class MQTTClient(simple.MQTTClient):
    DELAY = 2
    DEBUG = False
    
    subscriptions = []  # List to keep track of topic subscriptions

    def add_subscription(self, topic, qos=0):
        if (topic, qos) not in self.subscriptions:
            self.subscriptions.append((topic, qos))
        self.subscribe(topic, qos)

    def resubscribe(self):
        for topic, qos in self.subscriptions:
            self.subscribe(topic, qos)

    def delay(self, i):
        utime.sleep(self.DELAY)

    def log(self, in_reconnect, e):
        if self.DEBUG:
            if in_reconnect:
                print("mqtt reconnect: %r" % e)
            else:
                print("mqtt: %r" % e)

    def reconnect(self):
        i = 0
        while 1:
            try:
                result = super().connect(True)
                self.resubscribe()  # Resubscribe to all topics on reconnect
                return result
            except OSError as e:
                self.log(True, e)
                i += 1
                self.delay(i)

    def publish(self, topic, msg, retain=False, qos=0):
        while 1:
            try:
                return super().publish(topic, msg, retain, qos)
            except OSError as e:
                self.log(False, e)
            self.reconnect()

    def wait_msg(self):
        while 1:
            try:
                return super().wait_msg()
            except OSError as e:
                self.log(False, e)
            self.reconnect()

    def check_msg(self, attempts=2):
        while attempts:
            self.sock.setblocking(False)
            try:
                return super().wait_msg()
            except OSError as e:
                self.log(False, e)
            self.reconnect()
            attempts -= 1
