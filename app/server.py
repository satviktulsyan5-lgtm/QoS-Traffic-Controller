
import socket
import struct
import time
import select

HOST = "0.0.0.0"
PORTS = [5001, 5002, 5003]

# Create sockets for all three traffic classes
sockets = []

for port in PORTS:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, port))
    sockets.append(s)

print("UDP Performance Server listening on ports:", PORTS)

stats = {
    "HIGH": {
        "packets": 0, "bytes": 0, "latencies": [],
        "min_seq": None, "max_seq": 0
    },
    "MEDIUM": {
        "packets": 0, "bytes": 0, "latencies": [],
        "min_seq": None, "max_seq": 0
    },
    "LOW": {
        "packets": 0, "bytes": 0, "latencies": [],
        "min_seq": None, "max_seq": 0
    }
}

classes = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}

start_time = time.time()
last_report_time = start_time

try:
    while True:

        # Wait for packets on any of the three sockets
        ready_sockets, _, _ = select.select(
            sockets, [], [], 2.0
        )

        for active_sock in ready_sockets:

            data, addr = active_sock.recvfrom(65535)

            if len(data) < 20:
                continue

            class_id, seq, timestamp, packet_size = struct.unpack(
                "!IIdI", data[:20]
            )

            traffic_class = classes.get(class_id, "UNKNOWN")

            if traffic_class in stats:

                now = time.time()
                latency = (now - timestamp) * 1000

                s = stats[traffic_class]

                s["packets"] += 1
                s["bytes"] += len(data)
                s["latencies"].append(latency)

                if s["min_seq"] is None or seq < s["min_seq"]:
                    s["min_seq"] = seq

                if seq > s["max_seq"]:
                    s["max_seq"] = seq

        # Print report every five seconds
        if time.time() - last_report_time >= 5.0:

            elapsed = time.time() - start_time

            print("\n--- LIVE PERFORMANCE REPORT ---")

            for tc, data_dict in stats.items():

                if data_dict["packets"] > 0:

                    duration = max(elapsed, 1.0)

                    throughput = (
                        data_dict["bytes"] * 8
                    ) / (duration * 1000000)

                    avg_lat = (
                        sum(data_dict["latencies"])
                        / len(data_dict["latencies"])
                    )

                    expected = (
                        data_dict["max_seq"]
                        - data_dict["min_seq"] + 1
                    )

                    lost = max(
                        0, expected - data_dict["packets"]
                    )

                    loss_pct = (
                        lost / expected * 100
                        if expected > 0 else 0.0
                    )

                    print(
                        f"[{tc}] Throughput: {throughput:.3f} Mbps | "
                        f"Avg Latency: {avg_lat:.2f} ms | "
                        f"Loss: {loss_pct:.1f}% "
                        f"({data_dict['packets']} pkts)"
                    )

            print("-------------------------------\n")

            last_report_time = time.time()

except KeyboardInterrupt:

    print("\nServer shutting down. Final Statistics:")

    for tc, data_dict in stats.items():

        if data_dict["packets"] > 0:

            print(f"--- {tc} Traffic ---")
            print(f"Total Packets Received: {data_dict['packets']}")

            print(
                f"Average Latency: "
                f"{sum(data_dict['latencies']) / len(data_dict['latencies']):.2f} ms"
            )

finally:
    for s in sockets:
        s.close()
