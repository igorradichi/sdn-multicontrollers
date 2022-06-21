from concurrent.futures import thread
import threading
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSSwitch, Controller, RemoteController
from time import sleep
import redis
import configparser
import sys
from threading import Thread
import os

#read config
def readConfig(file):
    config = configparser.ConfigParser()
    config.read(file)
    return config

def freeCredits(master):

    master.hset("master","credits",1)
    master.hset("master","port",0)

def monitorConnections(net, nControllers, ip, ports, master):
    while True:
        sleep(1)
        for i in range(0,nControllers):
            controller = net.getNodeByName('c'+str(i))
            #if MASTER is down
            if controller.isListening(ip,ports[i])==False and int(master.hget("master","port"))==ports[i]:
                freeCredits(master)

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

if __name__ == '__main__':

    os.system('cls||clear')
    setLogLevel(sys.argv[2])

    #config file
    file = sys.argv[1]
    config = readConfig(file)
    ip = config['DEFAULT']['ip']
    controllersFirstPort = int(config['DEFAULT']['controllersFirstPort'])
    nControllers = int(config['DEFAULT']['nControllers'])

    #initializing and flushing redis DBS
    routing_table = redis.Redis(host=ip, port=6379, db = 0)
    routing_table.flushdb()

    master = redis.Redis(host=ip, port=6379, db = 1)
    master.flushdb()
    freeCredits(master)
    
    topo = MyTopo()
    net = Mininet(topo=topo,  build=False)
    
    ports = []

    #setting ports for each controller
    for i in range(0,nControllers):
        ports.append(controllersFirstPort + i)

    #creating controllers
    for i in range(0,nControllers):
        controller = RemoteController('c'+str(i),ip,ports[i])
        net.addController(controller)
        print(controller.checkListening())
    
        config = configparser.ConfigParser()
        config.set("DEFAULT","ip",ip)
        config.set("DEFAULT","port",str(ports[i]))

        with open(r"c"+str(i)+".conf",'w') as configfileObj:
            config.write(configfileObj)
            configfileObj.flush()
            configfileObj.close()
            
    net.build()
    net.start()
    
    #multithreading monitorConnections
    thread = threading.Thread(target=monitorConnections,args=[net,nControllers,ip,ports,master])
    thread.start()

    CLI(net)
    
    thread.join()

    net.stop()


