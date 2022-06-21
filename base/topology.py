
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSSwitch, Controller, RemoteController
from time import sleep


class MyTopo(Topo):
    "Single switch connected to n hosts."
    def build(self):
        s0 = self.addSwitch('s0', failMode='secure')
        s1 = self.addSwitch('s1', failMode='secure')
        s2 = self.addSwitch('s2', failMode='secure')

        h1 = self.addHost('h1', mac="00:00:00:00:00:01", ip="10.0.0.1/24")
        h2 = self.addHost('h2', mac="00:00:00:00:00:02", ip="10.0.0.2/24")

        self.addLink(h1, s1)
        self.addLink(h2, s2)

        self.addLink(s0, s1)
        self.addLink(s0, s2)

if __name__ == '__main__':
    setLogLevel('info')
    topo = MyTopo()
    net = Mininet(topo=topo,  build=False)
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653)
    c1 = RemoteController('c1', ip='127.0.0.1', port=6654)
    net.addController(c0)
    net.addController(c1)
    net.build()
    net.start()
    CLI(net)
    net.stop()
