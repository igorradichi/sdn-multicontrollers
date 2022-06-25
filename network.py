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
import random


class Conf:  

    def readConfig(self, file):

        config = configparser.ConfigParser()
        config.read(file)
        
        self.netId = config['DEFAULT']['netId']
        self.ip = config['DEFAULT']['ip']
        self.connectionModel = config['DEFAULT']['connectionModel']
        self.masterSlaveLoadBalancingTime = int(config['DEFAULT']['masterSlaveLoadBalancingTime'])
        self.nControllers = int(config['DEFAULT']['nControllers'])
        self.nSwitches = int(config['DEFAULT']['nSwitches'])
        self.nHostsPerSwitch = int(config['DEFAULT']['nHostsPerSwitch'])
        self.flowIdleTimeout = config['DEFAULT']['flowIdleTimeout']
        self.flowHardTimeout = config['DEFAULT']['flowHardTimeout']

class MyTopo(Topo):

    def build(self, nSwitches, nHostsPerSwitch):

        networks = readRedisDatabase(conf.ip,redisPort,0)

        for s in range(1,nSwitches+1):
            sw = self.addSwitch('s'+str(nextElementIndex(networks,"nextSwitchIndex")), failMode='secure')
            for h in range(1,nHostsPerSwitch+1):
                hostIndex = str(nextElementIndex(networks,"nextHostIndex"))
                ht = self.addHost('h'+hostIndex, mac=nexthostMAC(hostIndex))
                self.addLink(sw,ht)

class MyException(Exception):
    pass

class ThreadMonitorControllersConnection(threading.Thread):

    def run(self):
        self.exc = None           
        while True:
            try:
                monitorControllers(conf,net,ports,cluster,connections,myControllers)
            except BaseException as e:
                self.exc = e
       
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

class ThreadMasterLoadBalancing(threading.Thread):

    def run(self):
        self.exc = None           
        while True:
            try:
                masterLoadBalancing(cluster,conf,ports,connections)
            except BaseException as e:
                self.exc = e
       
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

def readRedisDatabase(host,port,db,flush=False):

    r = redis.Redis(host, port, db)

    if flush == True:
        r.flushdb()
    return r

def nextElementIndex(networks,element):
    index = int(networks.hget("network",element))
    networks.hincrby("network",element,1)
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

def addSwitchToSwitchLinks(net,networks,nSwitches):

    lastSwitch = int(networks.hget("network","nextSwitchIndex"))-1

    sws = []
    for s in range(lastSwitch-nSwitches+1,lastSwitch+1):
        sws.append('s'+str(s))
    for s in range(0,nSwitches-1):
        net.addLink(sws[s],sws[s+1])
    return net

def addControllers(conf,net,networks,connectionModel,connections,cluster):
    
    ports = []
    myControllers = []

    #setting ports for each controller
    for i in range(0,conf.nControllers):
        port = nextElementIndex(networks,"nextControllerPort")
        ports.append(port)
        connections.hset(conf.netId,port,0)
        cluster.hset(conf.netId,port,0)

    for i in range(0,conf.nControllers):

        controllerIndex = str(nextElementIndex(networks,"nextControllerIndex"))
        
        #create and add controller
        controller = RemoteController('c'+controllerIndex,conf.ip,ports[i])
        net.addController(controller)
        myControllers.append('c'+controllerIndex)
    
        #create config file
        config = configparser.ConfigParser()
        config.set("DEFAULT","netId",conf.netId)
        config.set("DEFAULT","ip",conf.ip)
        config.set("DEFAULT","port",str(ports[i]))
        config.set("DEFAULT","connectionModel",connectionModel)
        config.set("DEFAULT","flowIdleTimeout",conf.flowIdleTimeout)
        config.set("DEFAULT","flowHardTimeout",conf.flowHardTimeout)
        config.set("DEFAULT","redisPort",str(redisPort))

        with open(r"c"+controllerIndex+".conf",'w') as configfileObj:
            config.write(configfileObj)
            configfileObj.flush()
            configfileObj.close()

    return ports, myControllers

def electNewMaster(cluster,conf,ports,connections):

    availableControllers = []
    reqs = []

    for port in ports:
        if int(connections.hget(conf.netId,port)) == 1:
            availableControllers.append(port)
            reqs.append(int(cluster.hget(conf.netId,port)))

    if len(availableControllers) > 0:     
                  
        if cluster.hget(conf.netId,"currentMaster") == None:
            lastMaster = random.choice(ports)
        else:
            lastMaster = int(cluster.hget(conf.netId,"currentMaster"))
        
        nextMaster = availableControllers[reqs.index(min(reqs))] #less used is the next master

        cluster.hset(conf.netId,"currentMaster",nextMaster)

        if lastMaster != nextMaster: #if the master has changed, tell the cluster there is room
                                     #for a new master
            print("-------------")
            print("Electing new MASTER...")
            print("Available controllers: ",availableControllers)
            print(nextMaster,"elected as MASTER")
            print("-------------")
            freeMaster(cluster,conf)
        
    else:
        cluster.hdel(conf.netId,"currentMaster")
        freeMaster(cluster,conf)
        
def freeMaster(cluster,conf):
    cluster.hset(conf.netId,"masterCredits",1)

def masterLoadBalancing(master,conf,ports,connections):

    sleep(conf.masterSlaveLoadBalancingTime)
    electNewMaster(cluster,conf,ports,connections)

    raise MyException("An error in thread")

def monitorControllers(conf,net,ports,cluster,connections,myControllers):

    nControllers=conf.nControllers
    ip=conf.ip
    sleep(1)

    for i in range(0,nControllers):

        controller = net.getNodeByName(myControllers[i])

        #check controllers connections
        if controller.isListening(ip,ports[i]) == False: #if the controller is down
            print("-------------")
            connections.hset(conf.netId,str(ports[i]),0)
        
            if int(cluster.hget(conf.netId,"currentMaster"))==ports[i]: #if the controller down was the MASTER
                print("MASTER is down!!!")
                electNewMaster(cluster,conf,ports,connections)
        else:
            connections.hset(conf.netId,str(ports[i]),1) #if the controller is still up

    raise MyException("An error in thread")

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
    cluster = readRedisDatabase(conf.ip,redisPort,1)
    connections = readRedisDatabase(conf.ip,redisPort,2,flush=True)
  
    #create network
    topo = MyTopo(conf.nSwitches,conf.nHostsPerSwitch)
    net = Mininet(topo=topo,  build=False)

    #add controllers
    result = addControllers(conf,net,networks,conf.connectionModel,connections,cluster)
    ports = result[0]
    myControllers = result[1]
    
    #start network
    net.build()
    net = addSwitchToSwitchLinks(net,networks,conf.nSwitches)
    net.start()
    freeMaster(cluster,conf)

    threads = []

    #multithreading monitorControllers
    t1 = ThreadMonitorControllersConnection(target=monitorControllers,args=[conf,net,ports,cluster,connections,myControllers])
    t1.start()
    threads.append(t1)

    #multithreading masterLoadBalancing
    if conf.connectionModel == "master-slave" and conf.masterSlaveLoadBalancingTime > 0:
        t2 = ThreadMasterLoadBalancing(target=masterLoadBalancing,args=[cluster,conf,ports,connections])
        t2.start()
        threads.append(t2)

    CLI(net)

    for t in threads:
        try:
            t.join()
        except Exception as e:
            print("Thread error!:", e)

    net.stop()


