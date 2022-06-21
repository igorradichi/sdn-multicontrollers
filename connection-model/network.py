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

redisPort = 6379

class Conf:  
    def readConfig(self, file):
        config = configparser.ConfigParser()
        config.read(file)
        
        self.ip = config['DEFAULT']['ip']
        self.controllersFirstPort = int(config['DEFAULT']['controllersFirstPort'])
        self.nControllers = int(config['DEFAULT']['nControllers'])
        self.flowIdleTimeout = config['DEFAULT']['flowIdleTimeout']
        self.flowHardTimeout = config['DEFAULT']['flowHardTimeout']
        
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

def readAndFlushRedisDatabase(host,port,db):
    r = redis.Redis(host, port, db)
    r.flushdb()
    return r

def freeMasterCredits(master):
    master.hset("master","credits",1)
    master.hset("master","port",0)

def monitorMasterConnection(net, nControllers, ip, ports, master):
    while True:
        sleep(1)
        for i in range(0,nControllers):
            controller = net.getNodeByName('c'+str(i))
            #if MASTER is down
            if controller.isListening(ip,ports[i])==False and int(master.hget("master","port"))==ports[i]:
                freeMasterCredits(master)

def addControllers(conf, net):
    ports = []

    #setting ports for each controller
    for i in range(0,conf.nControllers):
        ports.append(conf.controllersFirstPort + i)

    #creating controllers
    for i in range(0,conf.nControllers):
        controller = RemoteController('c'+str(i),conf.ip,ports[i])
        net.addController(controller)
    
        config = configparser.ConfigParser()
        config.set("DEFAULT","ip",conf.ip)
        config.set("DEFAULT","port",str(ports[i]))
        config.set("DEFAULT","connectionModel",connectionModel)
        config.set("DEFAULT","flowIdleTimeout",conf.flowIdleTimeout)
        config.set("DEFAULT","flowHardTimeout",conf.flowHardTimeout)

        with open(r"c"+str(i)+".conf",'w') as configfileObj:
            config.write(configfileObj)
            configfileObj.flush()
            configfileObj.close()
    
    return ports

if __name__ == '__main__':

    os.system('cls||clear')
    
    setLogLevel(sys.argv[3])
    connectionModel = sys.argv[2]

    #config file
    file = sys.argv[1]
    conf = Conf()
    conf.readConfig(file)

    #initializing and flushing redis DBS
    routing_table = readAndFlushRedisDatabase(conf.ip,redisPort,0)
    master = readAndFlushRedisDatabase(conf.ip,redisPort,1)
    
    if connectionModel == "master-slave":
        freeMasterCredits(master)
    
    topo = MyTopo()
    net = Mininet(topo=topo,  build=False)
    
    ports = addControllers(conf,net)

    net.build()
    net.start()
    
    if connectionModel == "master-slave":
        #multithreading monitorConnections
        thread = threading.Thread(target=monitorMasterConnection,args=[net,conf.nControllers,conf.ip,ports,master])
        thread.start()

        CLI(net)
        
        thread.join()
    else:
        CLI(net)

    net.stop()


