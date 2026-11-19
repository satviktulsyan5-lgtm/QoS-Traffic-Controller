# QoS Traffic Management (Mininet + OS-Ken)

## Setup
    sudo apt install mininet openvswitch-switch python3-pip python3-venv iproute2 -y
    python3 -m venv --system-site-packages ~/qos-venv && source ~/qos-venv/bin/activate
    pip install os-ken
    sudo systemctl enable --now openvswitch-switch && sudo mn -c

## Run (from the project folder)
Terminal 1 – controller:

    osken-manager controller.qos_controller --ofp-tcp-listen-port 6653
    (or: python3 run_controller.py)

Terminal 2 – topology (`--link tc` is REQUIRED so the 1 Mbps bottleneck on h2 works):

    sudo mn --custom topology/topology.py --topo qos --link tc \
        --controller remote,ip=127.0.0.1,port=6653 --switch ovs,protocols=OpenFlow13

Inside mininet (server.py already listens on 5001/5002/5003 – NO sed copies needed):

    mininet> h2 python3 app/server.py --log /tmp/run.csv &
    mininet> h1 python3 app/client.py 10.0.0.2 5001 HIGH 24 &
    mininet> h1 python3 app/client.py 10.0.0.2 5002 MEDIUM 12 &
    mininet> h1 python3 app/client.py 10.0.0.2 5003 LOW 12 &

Congestion / recovery events (any terminal):

    python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'CONGESTION',('127.0.0.1',9000))"
    python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'RECOVERY',('127.0.0.1',9000))"

## Graph
`eval/results/performance_evaluation.png` was produced by `python3 eval/run_eval.py` + `python3 eval/plot_results.py`
(real client.py/server.py through a software 0.8 Mbps bottleneck, FIFO vs strict priority).
For your Mininet run, stop the server with Ctrl-C and plot its log:
    mkdir r && cp /tmp/run.csv r/priority.csv   # plus a r/priority.json: {"sent":{"HIGH":..,"MEDIUM":..,"LOW":..},"start":6,"stop":18,"total":24}

## Known limitation
Flow priorities 100/50/10 (and the dynamic 200 rule) choose between *overlapping* matches only. The HIGH/MEDIUM/LOW
rules match different UDP ports and output to the same port, so they never compete: OpenFlow priority alone does not
change throughput/latency. Real prioritisation needs OVS queues (OFPActionSetQueue + ovs-vsctl QoS) or meters.
