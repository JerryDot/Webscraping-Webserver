#!/usr/bin/python3.8

import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("localhost", 8080))
message = "GBP:JPY"
s.send(message.encode())
count = 0

while True:
    time.sleep(0.5)
    receive = s.recv(4096).decode()
    print(receive)
    s.send(message.encode())
    count += 1
