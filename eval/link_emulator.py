"""Software bottleneck link used to emulate congestion where Mininet/tc is unavailable.
Listens on UDP 5001-5003, forwards to the server ports at a fixed link rate.
mode=fifo      : one shared queue (no QoS)
mode=priority  : strict priority HIGH > MEDIUM > LOW (what the QoS rules are meant to achieve)"""
import argparse, select, socket, struct, threading, time
from collections import deque

p = argparse.ArgumentParser()
p.add_argument("--mode", choices=["fifo", "priority"], required=True)
p.add_argument("--rate-mbps", type=float, default=0.8)
p.add_argument("--fwd-base", type=int, default=16000)
p.add_argument("--buffer", type=int, default=24000, help="total queue bytes")
a = p.parse_args()

IN = [5001, 5002, 5003]
ins = []
for port in IN:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", port)); ins.append(s)
out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
qs = [deque(), deque(), deque()]
qbytes = [0, 0, 0]
cv = threading.Condition()
WIRE = 28  # IP + UDP header

def admit(cls, n):
    if a.mode == "fifo":
        return sum(qbytes) + n <= a.buffer
    return qbytes[cls] + n <= a.buffer // 3

def sender():
    free_at = time.time()
    while True:
        with cv:
            while not any(qs):
                cv.wait()
            order = [0] if a.mode == "fifo" else [0, 1, 2]
            if a.mode == "fifo":      # arrival order across classes
                cls = min((i for i in range(3) if qs[i]), key=lambda i: qs[i][0][0])
            else:
                cls = next(i for i in order if qs[i])
            _, data = qs[cls].popleft(); qbytes[cls] -= len(data) + WIRE
        free_at = max(free_at, time.time()) + (len(data) + WIRE) * 8 / (a.rate_mbps * 1e6)
        d = free_at - time.time()
        if d > 0: time.sleep(d)
        out.sendto(data, ("127.0.0.1", a.fwd_base + IN[cls]))

threading.Thread(target=sender, daemon=True).start()
while True:
    r, _, _ = select.select(ins, [], [])
    for s in r:
        data, _ = s.recvfrom(65535)
        cls = ins.index(s); n = len(data) + WIRE
        with cv:
            if admit(cls, n):
                qs[cls].append((time.time(), data)); qbytes[cls] += n; cv.notify()
