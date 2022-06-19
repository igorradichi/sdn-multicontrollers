from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSSwitch, Controller, RemoteController
from time import sleep
import redis

class MyTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1', failMode='secure')
        
        h1 = self.addHost('h1', mac="00:00:00:00:00:01", ip="10.0.0.1/24")
        h2 = self.addHost('h2', mac="00:00:00:00:00:02", ip="10.0.0.2/24")
        h3 = self.addHost('h3', mac="00:00:00:00:00:03", ip="10.0.0.3/24")
        h4 = self.addHost('h4', mac="00:00:00:00:00:04", ip="10.0.0.4/24")
        
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s1)

def free_credits(r):

    r.hset("master","credits",1)
    r.hset("master","port",0)


if __name__ == '__main__':
    
    controller_to_port = {}

    r = redis.Redis()
    r.flushdb()

    free_credits(r)

    setLogLevel('output')
    
    topo = MyTopo()
    net = Mininet(topo=topo,  build=False)
    
    ip = '127.0.0.1'
    ports = [6633, 6634]

    for i in range(0,len(ports)):
        controller = RemoteController('c'+str(i),ip,ports[i])
        net.addController(controller)

    net.build()
    net.start()
    
    while True:
        sleep(5)
        print("Checking...\n")
        for i in range(0,len(ports)):
            controller = net.getNodeByName('c'+str(i))
            if controller.isListening(ip,ports[i])==False and int(r.hget("master","port"))==ports[i]:
                free_credits(r)
                print("MASTER DOWN")
           

    

    CLI(net)

    net.stop()