from mininet.topo import Topo


class QosTopo(Topo):

    def build(self, bottleneck_mbps=1.0):

        # OpenFlow 1.3 switch
        s1 = self.addSwitch('s1', protocols='OpenFlow13')

        # Three hosts representing traffic classes
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')

        # FIX: the original used plain links (unlimited bandwidth), so the
        # ~1.05 Mbps of offered load could never congest anything and the
        # CONGESTION / RECOVERY logic had nothing to react to. Rate-limit the
        # link towards the receiver (h2) to create a real bottleneck.
        # Start Mininet with `--link tc` (or Mininet(link=TCLink)) so bw= works.
        self.addLink(h1, s1)
        self.addLink(h2, s1, bw=bottleneck_mbps, max_queue_size=50)
        self.addLink(h3, s1)


topos = {
    'qos': QosTopo
}
