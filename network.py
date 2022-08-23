from ast import While
from concurrent.futures import thread
from doctest import master
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
import ast


class Conf:  

    def readConfig(self, file):

        config = configparser.ConfigParser()
        config.read(file)
        
        self.netId = config['DEFAULT']['netId']
        self.ip = config['DEFAULT']['ip']
        self.connectionModel = config['DEFAULT']['connectionModel']
        self.masterSlaveLoadBalancingTime = int(config['DEFAULT']['masterSlaveLoadBalancingTime'])
        self.nSwitches = int(config['DEFAULT']['nSwitches'])
        self.nHostsPerSwitch = int(config['DEFAULT']['nHostsPerSwitch'])
        self.flowIdleTimeout = config['DEFAULT']['flowIdleTimeout']
        self.flowHardTimeout = config['DEFAULT']['flowHardTimeout']

class MyTopo(Topo):

    def build(self, nSwitches, nHostsPerSwitch, netId):

        networks = readRedisDatabase(conf.ip,conf.redisPort,1)
        namespaces = readRedisDatabase(conf.ip,conf.redisPort,2)
        datapaths = []

        for s in range(1,nSwitches+1):
            switchIndex = str(nextElementIndex(namespaces,"nextSwitchIndex"))
            sw = self.addSwitch('s'+switchIndex, failMode='secure')
            datapaths.append(switchIndex)
            for h in range(1,nHostsPerSwitch+1):
                hostIndex = str(nextElementIndex(namespaces,"nextHostIndex"))
                ht = self.addHost('h'+hostIndex, mac=nexthostMAC(hostIndex))
                self.addLink(sw,ht)

        networks.hset(netId,"datapaths",str(datapaths))

class MyException(Exception):
    pass

class ThreadMonitorControllersConnection(threading.Thread):

    def run(self):
        self.exc = None           
        while True:
            try:
                monitorControllers(conf,networks,controllers)
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
                masterLoadBalancing(networks,conf,controllers)
            except BaseException as e:
                self.exc = e
       
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

def readRedisDatabase(host,port,db,flush=False):

    r = redis.Redis(host, port, db, decode_responses=True)

    if flush == True:
        r.flushdb()
    return r

def nextElementIndex(namespaces,element):
    index = int(namespaces.get(element))
    namespaces.incrby(element,1)
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

def addSwitchToSwitchLinks(net,namespaces,nSwitches):

    lastSwitch = int(namespaces.get("nextSwitchIndex"))-1

    sws = []
    for s in range(lastSwitch-nSwitches+1,lastSwitch+1):
        sws.append('s'+str(s))
    for s in range(0,nSwitches-1):
        net.addLink(sws[s],sws[s+1])
    return net

def addController(net,controllerName,controllerPort,conf):
    
    controller = RemoteController(controllerName,conf.ip,controllerPort)
    net.addController(controller)

    #create config file
    config = configparser.ConfigParser()
    config.set("DEFAULT","name",controllerName)
    config.set("DEFAULT","ip",conf.ip)
    config.set("DEFAULT","port",str(controllerPort))
    config.set("DEFAULT","connectionModel",conf.connectionModel)
    config.set("DEFAULT","flowIdleTimeout",conf.flowIdleTimeout)
    config.set("DEFAULT","flowHardTimeout",conf.flowHardTimeout)
    config.set("DEFAULT","redisPort",str(conf.redisPort))

    with open(r""+controllerName+".conf",'w') as configfileObj:
        config.write(configfileObj)
        configfileObj.flush()
        configfileObj.close()

def electNewMaster(networks,conf,allControllers):

    sleep(1)

    availableControllers = []
    reqs = []
    ports = []

    #aggregate controllers status for that network
    c = networks.hgetall(conf.netId)
    for controller in c:
        if controller in allControllers:
            d = ast.literal_eval(c[controller])
            if int(d["connected"]) == 1:
                availableControllers.append(controller)
                reqs.append(int(d["reqs"]))
                ports.append(int(d["port"]))
    
    print("available:",availableControllers)
    print("reqs:",reqs)
    print("ports:",ports)
    
    #if there is a least one controller available
    if len(availableControllers) > 0: 

        #get the last MASTER
        if networks.hget(conf.netId,"currentMaster") == None:
            lastMaster = random.choice(ports) #choose any
        else:
            lastMaster = int(networks.hget(conf.netId,"currentMaster"))

        #elect the next MASTER (based on least amount of reqs)
        nextMaster = int(ports[reqs.index(min(reqs))])

        #if there has been a change in mastery
        if lastMaster != nextMaster:
            print("-------------")
            print("Electing new MASTER...")
            print("Available controllers: ",availableControllers)
            print(availableControllers[ports.index(nextMaster)],"elected as MASTER")
            print("-------------")
            #set the new MASTER as current MASTER
            networks.hset(conf.netId,"currentMaster",nextMaster)
            freeMaster(networks,conf)
        else:
            print("-------------")
            print("No changes to mastery...")
            print("-------------")
    else: #if there were no controllers available
        networks.hdel(conf.netId,"currentMaster")
        freeMaster(networks,conf)

def freeMaster(networks,conf):

    datapaths = ast.literal_eval(networks.hget(conf.netId,"datapaths"))
    networks.hset(conf.netId,"masterCredits",len(datapaths))

def monitorControllers(conf,networks,controllers):

    sleep(1)
    print("MONITORING...")
    allControllers = controllers.keys()

    myControllers = {}

    #get controllers known by that network
    c = networks.hgetall(conf.netId)
    for controller in c:
        if controller in allControllers:
            d = ast.literal_eval(c[controller])
            myControllers[controller] = int(d["port"])
            
    nControllers = len(myControllers)
    ip=conf.ip

    #monitor each known controller
    for i in range(0,nControllers):
        controllerName = list(myControllers.keys())[i]
        controller = net.getNodeByName(controllerName)

        c = networks.hgetall(conf.netId)
        d = ast.literal_eval(c[controllerName])
        
        #check controllers connections
        if controller.isListening(ip,myControllers[controllerName]) == False: #if the controller is down

            d["connected"] = 0
            networks.hset(conf.netId,controllerName,str(d))
            
            #the controller down was the MASTER
            if networks.hget(conf.netId,"currentMaster") != None:
                if int(networks.hget(conf.netId,"currentMaster"))==int(myControllers[controllerName]):
                    print("MASTER is down!!!")
                    electNewMaster(networks,conf,allControllers)
        else:
            d["connected"] = 1
            networks.hset(conf.netId,controllerName,str(d))

    raise MyException("An error in thread")

def masterLoadBalancing(networks,conf,controllers):

    allControllers = controllers.keys()

    sleep(conf.masterSlaveLoadBalancingTime)
    print("-------------")
    electNewMaster(networks,conf,allControllers)

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
    conf.redisPort = int(redisConfig['DEFAULT']['redisPort'])

    #initializing redis DBs
    controllers = readRedisDatabase(conf.ip,conf.redisPort,0)
    networks = readRedisDatabase(conf.ip,conf.redisPort,1)
    namespaces = readRedisDatabase(conf.ip,conf.redisPort,2)
  
    #create network
    topo = MyTopo(conf.nSwitches,conf.nHostsPerSwitch,conf.netId)
    net = Mininet(topo=topo,  build=False)

    #add initial controllers
    initialControllers = networks.hgetall(conf.netId) #controllers defined to initilization
    allControllers = controllers.keys()

    for c in initialControllers:
        if c in allControllers:
            d = ast.literal_eval(initialControllers[c])
            addController(net,c,int(d["port"]),conf)

    #build and start network
    net.build()
    net = addSwitchToSwitchLinks(net,namespaces,conf.nSwitches)
    net.start()
    freeMaster(networks,conf)

    threads = []

    #multithreading monitorControllers
    t1 = ThreadMonitorControllersConnection(target=monitorControllers,args=[conf,networks,controllers])
    t1.start()
    threads.append(t1)

    #multithreading masterLoadBalancing
    if conf.connectionModel == "master-slave" and conf.masterSlaveLoadBalancingTime > 0:
        t2 = ThreadMasterLoadBalancing(target=masterLoadBalancing,args=[networks,conf,controllers])
        t2.start()
        threads.append(t2)

    CLI(net)

    for t in threads:
        try:
            t.join()
        except Exception as e:
            print("Thread error!", e)

    net.stop()


