import argparse
import select
import signal
import socket
import struct
import time
from collections import defaultdict

parser = argparse.ArgumentParser(description="UDP QoS performance server")
parser.add_argument("--host", default="0.0.0.0")
parser.add_argument("--ports", default="5001,5002,5003",
                    help="comma separated UDP ports (HIGH,MEDIUM,LOW)")
parser.add_argument("--log", default=None,
                    help="optional CSV file with one row per received packet")
parser.add_argument("--report", type=float, default=5.0,
                    help="seconds between live reports")
args = parser.parse_args()

PORTS = [int(p) for p in args.ports.split(",")]
classes = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}
HEADER_FMT = "!IIdI"
HEADER_LEN = struct.calcsize(HEADER_FMT)

sockets = []
for port in PORTS:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((args.host, port))
    sockets.append(s)

# FIX: processes started with `&` from a non-interactive shell (e.g. the Mininet
# CLI) start with SIGINT ignored, so `pkill -INT` never reached the final-stats
# code and server.log stayed empty. Handle SIGINT and SIGTERM explicitly.
def _stop(signum, frame):
    raise KeyboardInterrupt
signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

print("UDP Performance Server listening on ports:", PORTS, flush=True)

# FIX: statistics are now kept per (traffic class, sender address). The client
# opens a new socket (new source port) on every run and restarts its sequence
# number at 0. Previously min_seq/max_seq were shared across runs, so a second
# run of the same class (e.g. after congestion/recovery) corrupted the loss
# figure and the packet counts were added on top of the old ones.
def new_stat():
    return {"packets": 0, "bytes": 0, "lat_sum": 0.0, "min_seq": None,
            "max_seq": -1, "first_rx": None, "last_rx": None}

stats = defaultdict(new_stat)
all_latencies = defaultdict(list)

log = None
if args.log:
    log = open(args.log, "w", buffering=1)
    log.write("class,src,seq,size,send_ts,recv_ts,latency_ms\n")


def summarise():
    """Aggregate per-flow stats into one row per traffic class."""
    out = {}
    for (tc, _src), st in stats.items():
        o = out.setdefault(tc, {"packets": 0, "bytes": 0, "lat_sum": 0.0,
                                "expected": 0, "active": 0.0})
        o["packets"] += st["packets"]
        o["bytes"] += st["bytes"]
        o["lat_sum"] += st["lat_sum"]
        o["expected"] += st["max_seq"] - st["min_seq"] + 1
        # FIX: throughput used total server uptime as the divisor, so it was
        # under-reported whenever the server had been waiting before traffic
        # started. Use the flow's own active window (first -> last packet).
        o["active"] += max(st["last_rx"] - st["first_rx"], 1e-3)
    return out


def print_report(title):
    print(f"\n--- {title} ---")
    for tc, o in summarise().items():
        thr = o["bytes"] * 8 / (o["active"] * 1e6)
        avg = o["lat_sum"] / o["packets"]
        lost = max(0, o["expected"] - o["packets"])
        loss = lost / o["expected"] * 100 if o["expected"] else 0.0
        print(f"[{tc}] Throughput: {thr:.3f} Mbps | Avg Latency: {avg:.2f} ms | "
              f"Loss: {loss:.1f}% ({o['packets']} pkts)")
    print("-------------------------------\n", flush=True)


last_report = time.time()
try:
    while True:
        ready, _, _ = select.select(sockets, [], [], 2.0)

        for active_sock in ready:
            data, addr = active_sock.recvfrom(65535)
            now = time.time()
            if len(data) < HEADER_LEN:
                continue

            class_id, seq, ts, _size = struct.unpack(HEADER_FMT, data[:HEADER_LEN])
            tc = classes.get(class_id)
            if tc is None:
                continue

            lat = (now - ts) * 1000.0
            st = stats[(tc, addr)]
            st["packets"] += 1
            st["bytes"] += len(data)
            st["lat_sum"] += lat
            st["min_seq"] = seq if st["min_seq"] is None else min(st["min_seq"], seq)
            st["max_seq"] = max(st["max_seq"], seq)
            st["first_rx"] = now if st["first_rx"] is None else st["first_rx"]
            st["last_rx"] = now
            all_latencies[tc].append(lat)
            if log:
                log.write(f"{tc},{addr[0]}:{addr[1]},{seq},{len(data)},"
                          f"{ts:.6f},{now:.6f},{lat:.3f}\n")

        if time.time() - last_report >= args.report:
            if stats:
                print_report("LIVE PERFORMANCE REPORT")
            last_report = time.time()

except KeyboardInterrupt:
    print("\nServer shutting down. Final Statistics:")
    for tc, o in summarise().items():
        lats = sorted(all_latencies[tc])
        lost = max(0, o["expected"] - o["packets"])
        print(f"--- {tc} Traffic ---")
        print(f"Total Packets Received: {o['packets']}")
        print(f"Average Latency: {o['lat_sum'] / o['packets']:.2f} ms")
        print(f"95th pct Latency: {lats[int(0.95 * (len(lats) - 1))]:.2f} ms")
        print(f"Packets Lost: {lost} / {o['expected']}")
finally:
    for s in sockets:
        s.close()
    if log:
        log.close()
