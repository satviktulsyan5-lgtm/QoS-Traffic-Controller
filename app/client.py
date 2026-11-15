import socket 

import struct 

import time 

import sys 

 

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1" 
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5001 

TRAFFIC_CLASS = sys.argv[3].upper() if len(sys.argv) > 3 else "HIGH" 

DURATION = int(sys.argv[4]) if len(sys.argv) > 4 else 10 

 

traffic_config = { 

    "HIGH": { 

        "class_id": 1, 

        "rate": 100, 

        "size": 512 

    }, 

    "MEDIUM": { 

        "class_id": 2, 

        "rate": 50, 

        "size": 1024 

    }, 

    "LOW": { 

        "class_id": 3, 

        "rate": 20, 

        "size": 1500 

    } 

} 

 

if TRAFFIC_CLASS not in traffic_config: 

    print("Invalid traffic class.") 

    print("Use HIGH, MEDIUM or LOW.") 

    sys.exit(1) 

 

config = traffic_config[TRAFFIC_CLASS] 

 

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 

 

class_id = config["class_id"] 

rate = config["rate"] 

packet_size = config["size"] 

 

interval = 1.0 / rate 

 

print(f"Destination : {SERVER_IP}:{PORT}") 

print(f"Class       : {TRAFFIC_CLASS}") 

print(f"Packet size : {packet_size} bytes") 

print(f"Rate        : {rate} packets/sec") 

print(f"Duration    : {DURATION} seconds") 

 

sequence = 0 

start_time = time.time() 

 

while time.time() - start_time < DURATION: 

 

    timestamp = time.time() 

 

    header = struct.pack( 

        "!IIdI", 

        class_id, 

        sequence, 

        timestamp, 

        packet_size 

    ) 

 

    payload_size = packet_size - len(header) 

 

    if payload_size < 0: 

        payload_size = 0 

 

    payload = b"X" * payload_size 

 

    packet = header + payload 

 

    sock.sendto(packet, (SERVER_IP, PORT)) 

 

    sequence += 1 

 

    time.sleep(interval) 

 

for s in sockets:
    s.close()

 

print("Traffic generation completed.") 