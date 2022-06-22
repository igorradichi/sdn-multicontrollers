from ast import While
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

class Conf:  
    def readConfig(self, file):
        config = configparser.ConfigParser()
        config.read(file)
        
        self.netId = config['DEFAULT']['netId']
        self.ip = config['DEFAULT']['ip']
        self.nControllers = int(config['DEFAULT']['nControllers'])
        self.flowIdleTimeout = config['DEFAULT']['flowIdleTimeout']
        self.flowHardTimeout = config['DEFAULT']['flowHardTimeout']

class MyTopo(Topo):
    def build(self):

        networks = readRedisDatabase(conf.ip,redisPort,0)

        s1 = self.addSwitch('s'+nextSwitchIndex(networks), failMode='secure')
        s2 = self.addSwitch('s'+nextSwitchIndex(networks), failMode='secure')
        
        h1 = self.addHost('h'+nextHostIndex(networks), mac="00:00:00:00:00:01", ip="10.0.0.1/24")
        h2 = self.addHost('h'+nextHostIndex(networks), mac="00:00:00:00:00:02", ip="10.0.0.2/24")
        h3 = self.addHost('h'+nextHostIndex(networks), mac="00:00:00:00:00:03", ip="10.0.0.3/24")
        h4 = self.addHost('h'+nextHostIndex(networks), mac="00:00:00:00:00:04", ip="10.0.0.4/24")
        
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s2)
        self.addLink(h4, s2)
        self.addLink(s1, s2)

def readRedisDatabase(host,port,db,flush=False):
    r = redis.Redis(host, port, db)
    if flush == True:
        r.flushdb()
    return r

def freeMasterCredits(master,conf):
    master.hset(conf.netId,"credits",1)
    master.hset(conf.netId,"port",0)

def monitorMasterConnection(conf, net, ports, master, controllers, myControllers):
    nControllers=conf.nControllers
    ip=conf.ip
    #while True:
    sleep(1)
    for i in range(0,nControllers):                    
        controller = net.getNodeByName(myControllers[i])
        #check controllers connections
        if controller.isListening(ip,ports[i]) == False:
            print("-------------")
            controllers.hset(str(ports[i]),"up",0)
            if int(master.hget(conf.netId,"port"))==ports[i]: #if MASTER is down
                freeMasterCredits(master,conf)
        else:
            controllers.hset(str(ports[i]),"up",1)

    raise MyException("An error in thread ")

def addControllers(conf, net, controllers, networks):
    ports = []
    myControllers = []

    #setting ports for each controller
    for i in range(0,conf.nControllers):
        port = nextControllerPort(networks)
        ports.append(port)

    #creating controllers
    for i in range(0,conf.nControllers):
        index = nextControllerIndex(networks)
        controller = RemoteController('c'+index,conf.ip,ports[i])
        net.addController(controller)
        #networks.hset('c'+index,"netId",conf.netId)
        myControllers.append('c'+index)
    
        config = configparser.ConfigParser()
        config.set("DEFAULT","netId",conf.netId)
        config.set("DEFAULT","ip",conf.ip)
        config.set("DEFAULT","port",str(ports[i]))
        config.set("DEFAULT","connectionModel",connectionModel)
        config.set("DEFAULT","flowIdleTimeout",conf.flowIdleTimeout)
        config.set("DEFAULT","flowHardTimeout",conf.flowHardTimeout)
        config.set("DEFAULT","redisPort",str(redisPort))

        with open(r"c"+index+".conf",'w') as configfileObj:
            config.write(configfileObj)
            configfileObj.flush()
            configfileObj.close()
        
        controllers.hset(ports[i],"up",1)
    
    return ports, myControllers

def nextControllerPort(networks):
    port = int(networks.hget("network","nextControllerPort"))
    networks.hset("network","nextControllerPort",int(port)+1)
    return port

def nextControllerIndex(networks):
    index = str(int(networks.hget("network","nextControllerIndex")))
    networks.hset("network","nextControllerIndex",int(index)+1)
    return index

def nextSwitchIndex(networks):
    index = str(int(networks.hget("network","nextSwitchIndex")))
    networks.hset("network","nextSwitchIndex",int(index)+1)
    return index

def nextHostIndex(networks):
    index = str(int(networks.hget("network","nextHostIndex")))
    networks.hset("network","nextHostIndex",int(index)+1)
    return index

class MyException(Exception):
    pass

class MyThread(threading.Thread):
    def run(self):
       
        self.exc = None           
        while True:
            try:
                monitorMasterConnection(conf,net,ports,master,controllers,myControllers)
            except BaseException as e:
                self.exc = e
       
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

if __name__ == '__main__':

    os.system('cls||clear')
    
    setLogLevel(sys.argv[3])
    connectionModel = sys.argv[2]

    #config file
    file = sys.argv[1]
    conf = Conf()
    conf.readConfig(file)

    redisConfig = configparser.ConfigParser()
    redisConfig.read("init.conf")
    redisPort = int(redisConfig['DEFAULT']['redisPort'])

    networks = readRedisDatabase(conf.ip,redisPort,0)

    #initializing and flushing redis DBS
    master = readRedisDatabase(conf.ip,redisPort,1)
    controllers = readRedisDatabase(conf.ip,redisPort,2,flush=True)
    routing_table = readRedisDatabase(conf.ip,redisPort,3,flush=True)

    freeMasterCredits(master,conf)
    
    topo = MyTopo()
    net = Mininet(topo=topo,  build=False)
    
    result = addControllers(conf,net,controllers,networks)
    ports = result[0]
    myControllers = result[1]
    
    net.build()
    net.start()
    
    #multithreading monitorConnections
    t = MyThread(target=monitorMasterConnection,args=[conf,net,ports,master,controllers,myControllers])
    t.start()
    #thread = threading.Thread(target=monitorMasterConnection,args=[conf,net,ports,master,controllers,myControllers])
    #thread.start()

    CLI(net)
    try:
        t.join()
    except Exception as e:
        print("thread error:", e)

    net.stop()


