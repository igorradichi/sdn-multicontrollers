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

class Conf:  

    def readConfig(self, file):

        config = configparser.ConfigParser()
        config.read(file)
        
        self.netId = config['DEFAULT']['netId']
        self.ip = config['DEFAULT']['ip']
        self.connectionModel = config['DEFAULT']['connectionModel']
        self.nControllers = int(config['DEFAULT']['nControllers'])
        self.nSwitches = int(config['DEFAULT']['nSwitches'])
        self.nHostsPerSwitch = int(config['DEFAULT']['nHostsPerSwitch'])
        self.flowIdleTimeout = config['DEFAULT']['flowIdleTimeout']
        self.flowHardTimeout = config['DEFAULT']['flowHardTimeout']

class MyTopo(Topo):

    def build(self, nSwitches, nHostsPerSwitch):

        networks = readRedisDatabase(conf.ip,redisPort,0)

        for s in range(1,nSwitches+1):
            sw = self.addSwitch('s'+nextSwitchIndex(networks), failMode='secure')
            for h in range(1,nHostsPerSwitch+1):
                hostIndex = nextHostIndex(networks)
                ht = self.addHost('h'+hostIndex, mac=nexthostMAC(hostIndex))
                self.addLink(sw,ht)

def readRedisDatabase(host,port,db,flush=False):

    r = redis.Redis(host, port, db)

    if flush == True:
        r.flushdb()
    return r

def freeMasterCredits(master,conf):

    master.hset(conf.netId,"credits",1)
    master.hset(conf.netId,"port",0)

def monitorMasterConnection(conf,net,ports,master,controllers,myControllers):

    nControllers=conf.nControllers
    ip=conf.ip
    sleep(1)

    for i in range(0,nControllers):     

        controller = net.getNodeByName(myControllers[i])

        #check controllers connections
        if controller.isListening(ip,ports[i]) == False: #if the controller is down
            print("-------------")
            controllers.hset(conf.netId,str(ports[i]),0)

            if int(master.hget(conf.netId,"port"))==ports[i]: #if the controller down was the MASTER
                freeMasterCredits(master,conf)
        else:
            controllers.hset(conf.netId,str(ports[i]),1) #if the controller is still up

    raise MyException("An error in thread ")

def addControllers(conf,net,networks,connectionModel):
    
    ports = []
    myControllers = []

    #setting ports for each controller
    for i in range(0,conf.nControllers):
        port = nextControllerPort(networks)
        ports.append(port)

    for i in range(0,conf.nControllers):

        index = nextControllerIndex(networks)
        
        #create and add controller
        controller = RemoteController('c'+index,conf.ip,ports[i])
        net.addController(controller)
        myControllers.append('c'+index)
    
        #create config file
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
    
    return ports, myControllers

def addSwitchToSwitchLinks(net,networks,nSwitches):

    lastSwitch = int(networks.hget("network","nextSwitchIndex"))-1

    sws = []
    for s in range(lastSwitch-nSwitches+1,lastSwitch+1):
        sws.append('s'+str(s))
    for s in range(0,nSwitches-1):
        net.addLink(sws[s],sws[s+1])
    return net

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

def nexthostMAC(nextHostIndex):
    
    hostHex = hex(int(nextHostIndex))[2:]
    macLength = 12
    l = len(hostHex)

    a = []
    for i in range(1,macLength+1-l):
        a.append('0')
    s = ''.join(a)

    mac = s+hostHex
    return ':'.join(mac[i:i+2] for i in range(0, len(mac), 2))

if __name__ == '__main__':

    os.system('cls||clear')
    
    setLogLevel(sys.argv[2])

    #config file
    file = sys.argv[1]
    conf = Conf()
    conf.readConfig(file)

    #redis port
    redisConfig = configparser.ConfigParser()
    redisConfig.read("init.conf")
    redisPort = int(redisConfig['DEFAULT']['redisPort'])

    #initializing redis DBS
    networks = readRedisDatabase(conf.ip,redisPort,0)
    master = readRedisDatabase(conf.ip,redisPort,1)
    controllers = readRedisDatabase(conf.ip,redisPort,2,flush=True)

    freeMasterCredits(master,conf)
    
    #create network
    topo = MyTopo(conf.nSwitches,conf.nHostsPerSwitch)
    net = Mininet(topo=topo,  build=False)
    
    #add controllers
    result = addControllers(conf,net,networks,conf.connectionModel)
    ports = result[0]
    myControllers = result[1]
    
    #start network
    net.build()
    net = addSwitchToSwitchLinks(net,networks,conf.nSwitches)
    net.start()
    
    #multithreading monitorMasterConnection
    t = MyThread(target=monitorMasterConnection,args=[conf,net,ports,master,controllers,myControllers])
    t.start()

    CLI(net)

    try:
        t.join()
    except Exception as e:
        print("Thread error!:", e)

    net.stop()


