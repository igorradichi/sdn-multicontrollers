from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSSwitch, Controller, RemoteController
from time import sleep
import redis
import configparser
import sys

#read config
def read_config(file):
    config = configparser.ConfigParser()
    config.read(file)
    return config

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

def free_credits(master):

    master.hset("master","credits",1)
    master.hset("master","port",0)


if __name__ == '__main__':

    #config file
    file = sys.argv[1]
    config = read_config(file)
    ip = config['DEFAULT']['IP']
    controllersFirstPort = int(config['DEFAULT']['CONTROLLERSFIRSTPORT'])
    nControllers = int(config['DEFAULT']['NCONTROLLERS'])

    #initializing and flushing redis DBS
    routing_table = redis.Redis(host=ip, port=6379, db = 0)
    routing_table.flushdb()

    master = redis.Redis(host=ip, port=6379, db = 1)
    master.flushdb()
    free_credits(master)

    setLogLevel('output')
    
    topo = MyTopo()
    net = Mininet(topo=topo,  build=False)
    
    ports = []

    #setting ports for each controller
    for i in range(0,nControllers):
        ports.append(controllersFirstPort + i)

    #creating controllers
    for i in range(0,len(ports)):
        controller = RemoteController('c'+str(i),ip,ports[i])
        net.addController(controller)

    net.build()
    net.start()
    

    #pending: automate c0, c1, c2, ... conf files

    #pending: implement multithreading
    while True:
        sleep(1)
        print("------------------------")
        print("Checking controllers connections...")
        for i in range(0,len(ports)):
            controller = net.getNodeByName('c'+str(i))
            if controller.isListening(ip,ports[i])==False and int(master.hget("master","port"))==ports[i]:
                free_credits(master)
                print("------------------------")
                print("MASTER DOWN")

    CLI(net)
    net.stop()