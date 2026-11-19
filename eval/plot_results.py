"""Usage: python3 plot_results.py [results_dir]   (reads <mode>.csv from server.py --log and <mode>.json)"""
import glob, json, os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RATE = {"HIGH": 100, "MEDIUM": 50, "LOW": 20}
COL = {"HIGH": "#d62728", "MEDIUM": "#ff7f0e", "LOW": "#1f77b4"}
TITLE = {"fifo": "Without QoS (shared FIFO queue)", "priority": "With QoS (strict priority HIGH > MEDIUM > LOW)"}
modes = sorted(os.path.basename(f)[:-4] for f in glob.glob(f"{D}/*.csv") if not f.endswith("summary.csv"))
modes.sort(key=lambda m: {"fifo": 0, "priority": 1}.get(m, 2))
fig, ax = plt.subplots(3, len(modes), figsize=(6.5 * len(modes), 10), sharex=True, squeeze=False)
rows = []
for c, mode in enumerate(modes):
    df = pd.read_csv(f"{D}/{mode}.csv"); t0 = df.send_ts.min(); df["t"] = df.recv_ts - t0
    if os.path.exists(f"{D}/{mode}.json"): meta = json.load(open(f"{D}/{mode}.json"))
    else:  # Mininet run: infer from the log (sent = highest seq + 1; MEDIUM/LOW assumed to start at 6 s, end at 18 s)
        meta = {"sent": {"HIGH": 2400, "MEDIUM": 600, "LOW": 240}, "start": 6, "stop": 18, "total": int(np.ceil(df.t.max()))}  # = counts from the 24 s / 12 s test commands
    for k in RATE: meta["sent"].setdefault(k, 1)
    for tc in RATE:
        d = df[df["class"] == tc]; bins = np.arange(0, meta["total"] + 1)
        thr = np.histogram(d.t, bins, weights=d["size"] * 8 / 1e6)[0]
        lat = d.groupby(np.floor(d.t).astype(int)).latency_ms.mean().reindex(range(meta["total"]))
        # loss per second of *send* time: missing sequence numbers mapped to nominal send time
        off = (d.send_ts - t0 - d.seq / RATE[tc]).median(); got = set(d.seq)
        lost_t = [off + s / RATE[tc] for s in range(meta["sent"][tc]) if s not in got]
        sent_per = np.histogram([off + s / RATE[tc] for s in range(meta["sent"][tc])], bins)[0]
        loss = 100 * np.histogram(lost_t, bins)[0] / np.maximum(sent_per, 1); loss[sent_per == 0] = np.nan
        x = bins[:-1] + 0.5
        ax[0, c].plot(x, thr, color=COL[tc], label=tc, lw=2); ax[1, c].plot(x, lat.values, color=COL[tc], lw=2)
        ax[2, c].plot(x, loss, color=COL[tc], lw=2)
        rows.append({"scenario": mode, "class": tc, "sent": meta["sent"][tc], "received": len(d),
                     "loss_%": round(100 * (1 - len(d) / meta["sent"][tc]), 1),
                     "avg_latency_ms (congested 6-18s)": round(d[(d.t > 7) & (d.t < 18)].latency_ms.mean(), 1),
                     "p95_latency_ms": round(d.latency_ms.quantile(.95), 1)})
    ax[0, c].set_title(TITLE.get(mode, mode), fontsize=11, fontweight="bold")
    for r in range(3):
        ax[r, c].axvspan(meta["start"], meta["stop"], color="grey", alpha=.12); ax[r, c].grid(alpha=.3)
for c in range(len(modes)):
    ax[1, c].set_ylim(0, 300)
if "priority" in modes: ax[1, modes.index("priority")].annotate("LOW is starved: its few packets leave the queue only after congestion ends (up to ~12 s, off-scale)", xy=(0.02, 0.88), xycoords="axes fraction", fontsize=8, color="#1f77b4")
for r, lab in enumerate(("Throughput (Mbps)", "Avg latency (ms)", "Packet loss (%)")): ax[r, 0].set_ylabel(lab)
for c in range(len(modes)): ax[2, c].set_xlabel("Time (s)  —  shaded = congestion window (MEDIUM + LOW active)")
ax[0, 0].legend(title="Traffic class", loc="upper left")
fig.suptitle("QoS Traffic Management – UDP data-transmission performance\n(bottleneck link 0.8 Mbps; offered load ≈ 1.09 Mbps during congestion)", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, .95]); fig.savefig(f"{D}/performance_evaluation.png", dpi=150)
s = pd.DataFrame(rows); s.to_csv(f"{D}/summary.csv", index=False); print(s.to_string(index=False))
