import socket
import struct
import sys
import time

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5001
TRAFFIC_CLASS = sys.argv[3].upper() if len(sys.argv) > 3 else "HIGH"
DURATION = float(sys.argv[4]) if len(sys.argv) > 4 else 10

# FIX: LOW packet size was 1500 B of UDP payload. With the 20 B IP + 8 B UDP
# headers that is 1528 B on the wire (> 1500 MTU), so every LOW packet was
# IP-fragmented. Fragment #2 carries no UDP header, so the controller's
# udp_dst=5003 rule can never match it. 1472 B is the largest payload that fits.
traffic_config = {
    "HIGH":   {"class_id": 1, "rate": 100, "size": 512,  "port": 5001},
    "MEDIUM": {"class_id": 2, "rate": 50,  "size": 1024, "port": 5002},
    "LOW":    {"class_id": 3, "rate": 20,  "size": 1472, "port": 5003},
}

if TRAFFIC_CLASS not in traffic_config:
    print("Invalid traffic class.")
    print("Use HIGH, MEDIUM or LOW.")
    sys.exit(1)

config = traffic_config[TRAFFIC_CLASS]

# FIX: a class sent to the wrong port silently bypasses its QoS flow rule.
if PORT != config["port"]:
    print(f"WARNING: {TRAFFIC_CLASS} traffic is normally sent to UDP port "
          f"{config['port']}, but port {PORT} was given. "
          f"The controller's {TRAFFIC_CLASS} flow rule will not match.")

class_id = config["class_id"]
rate = config["rate"]
packet_size = config["size"]
interval = 1.0 / rate

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"Destination : {SERVER_IP}:{PORT}")
print(f"Class       : {TRAFFIC_CLASS}")
print(f"Packet size : {packet_size} bytes")
print(f"Rate        : {rate} packets/sec")
print(f"Duration    : {DURATION} seconds")

HEADER_FMT = "!IIdI"                       # class, seq, timestamp, size = 20 B
HEADER_LEN = struct.calcsize(HEADER_FMT)

sequence = 0
start_time = time.time()
next_send = start_time

while time.time() - start_time < DURATION:
    header = struct.pack(HEADER_FMT, class_id, sequence, time.time(), packet_size)
    payload = b"X" * max(0, packet_size - HEADER_LEN)
    sock.sendto(header + payload, (SERVER_IP, PORT))
    sequence += 1

    # FIX: time.sleep(interval) after every send makes the real rate drift
    # below the nominal one (send time + sleep overshoot). Schedule against an
    # absolute clock so 100 pkt/s really is 100 pkt/s.
    next_send += interval
    delay = next_send - time.time()
    if delay > 0:
        time.sleep(delay)

# FIX: original did `for s in sockets: s.close()` -> NameError (no variable
# called `sockets` exists in client.py), so the script crashed right before
# printing the completion message.
sock.close()

print(f"Traffic generation completed. Sent {sequence} packets.")
