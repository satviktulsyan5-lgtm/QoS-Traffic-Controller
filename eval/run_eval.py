import json, os, re, signal, subprocess, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__)); APP = os.path.join(ROOT, "..", "app")
OUT = os.path.join(ROOT, "results"); os.makedirs(OUT, exist_ok=True)
TOTAL, START, STOP = 24, 6, 18      # HIGH runs 0-24 s; MEDIUM+LOW run 6-18 s (baseline / congestion / recovery)

def run(mode):
    log = os.path.join(OUT, f"{mode}.csv")
    srv = subprocess.Popen([sys.executable, os.path.join(APP, "server.py"), "--ports", "21001,21002,21003",
                            "--log", log, "--report", "999"], stdout=open(os.path.join(OUT, f"{mode}_server.txt"), "w"))
    time.sleep(0.5)
    rel = subprocess.Popen([sys.executable, os.path.join(ROOT, "link_emulator.py"), "--mode", mode, "--fwd-base", "16000"])
    time.sleep(0.5)
    t0 = time.time(); procs = {}
    def cl(name, port, dur, delay):
        cmd = f"sleep {delay}; {sys.executable} {APP}/client.py 127.0.0.1 {port} {name} {dur}"
        procs[name] = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, text=True)
    cl("HIGH", 5001, TOTAL, 0); cl("MEDIUM", 5002, STOP - START, START); cl("LOW", 5003, STOP - START, START)
    sent = {}
    for n, pr in procs.items():
        o = pr.communicate()[0]; sent[n] = int(re.search(r"Sent (\d+) packets", o).group(1)); print(mode, n, o.strip().splitlines()[-1])
    time.sleep(1.5)
    rel.terminate(); srv.send_signal(signal.SIGINT)
    srv.wait(timeout=5); rel.kill()
    json.dump({"t0": t0, "sent": sent, "start": START, "stop": STOP, "total": TOTAL}, open(os.path.join(OUT, f"{mode}.json"), "w"))

for m in ("fifo", "priority"): run(m)
