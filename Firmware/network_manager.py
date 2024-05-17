import uasyncio as asyncio
import machine
from machine import Pin, WDT, I2S
import network


class NetworkManager:
    # Class to manage WiFi network connection
    def __init__(self, ssid, password):
        self.sta_if = network.WLAN(network.STA_IF)  # WiFi station interface
        self.ssid = ssid  # WiFi SSID
        self.password = password  # WiFi password

    def connect(self):
        # Connects to the specified WiFi network
        if not self.sta_if.isconnected():
            print('connecting to network...')
            self.sta_if.active(True)
            self.sta_if.connect(self.ssid, self.password)
            while not self.sta_if.isconnected():
                pass
        print('network config:', self.sta_if.ifconfig())

    async def monitor(self):
        wdt = WDT(timeout=10000)  # Watchdog timer with 10 seconds timeout
        failure_count = 0  # Initialize failure counter
        max_failures = 5  # Set maximum consecutive failures

        while True:
            wdt.feed()  # Feed the watchdog before network test
            if not self.sta_if.isconnected():
                print("*******Network test failed******")
                failure_count += 1  # Increment failure counter on network test failure
                if failure_count >= max_failures:
                    print("Consecutive network test failures reached 5, preparing to reset device")
                    machine.reset()  # Reset device after 5 consecutive failures
            else:
                print("******Network is operational******")
                failure_count = 0  # Reset failure counter on successful network test

            await asyncio.sleep(5)  # Wait 5 seconds before next network test
            wdt.feed()  # Feed the watchdog after network test
