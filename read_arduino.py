# THIS CODE IS FOR THE RASPBERRY PI
import serial
import time


ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
time.sleep(2)


while True:
    data = ser.readline().decode(errors='ignore').strip()
    if data:
        print("Arduino:", data)