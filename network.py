#from _typeshed import Self
from ast import While
from audioop import add
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
import time

class Conf:  

    def readConfig(self, file):

        config = configparser.ConfigParser()
        config.read(file)
        
        self.netId = config['DEFAULT']['netId']
        self.failMode = config['DEFAULT']['failMode']
        self.ip = config['DEFAULT']['ip']
        self.connectionModel = config['DEFAULT']['connectionModel']
        self.primaryReplicaLoadBalancingTime = int(config['DEFAULT']['primaryReplicaLoadBalancingTime'])
        self.nSwitches = int(config['DEFAULT']['nSwitches'])
        self.nHostsPerSwitch = int(config['DEFAULT']['nHostsPerSwitch'])
        self.flowIdleTimeout = config['DEFAULT']['flowIdleTimeout']
        self.flowHardTimeout = config['DEFAULT']['flowHardTimeout']

class MyTopo(Topo):

    def build(self, nSwitches, nHostsPerSwitch, netId, failMode, experiments):

        networks = readRedisDatabase(conf.ip,conf.redisPort,1)
        namespaces = readRedisDatabase(conf.ip,conf.redisPort,2)
        datapaths = []

        hostsNames = []

        for s in range(1,nSwitches+1):
            switchIndex = str(nextElementIndex(namespaces,"nextSwitchIndex"))
            sw = self.addSwitch('s'+switchIndex, failMode=failMode)
            datapaths.append(switchIndex)
            for h in range(1,nHostsPerSwitch+1):
                hostIndex = str(nextElementIndex(namespaces,"nextHostIndex"))
                hostMAC = nexthostMAC(hostIndex)
                ht = self.addHost('h'+hostIndex, mac=hostMAC)
                self.addLink(sw,ht)
                hostsNames.append(ht)

        networks.hset(netId,"datapaths",str(datapaths))
        experiments.hset("experiment","hostsNames",str(hostsNames))

class MyException(Exception):
    pass

class ThreadExperiment1(threading.Thread):

    def run(self):
        self.exc = None           
        try:
            experiment1(net,experiments,conf)
        except BaseException as e:
            self.exc = e
    
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

class ThreadExperiment2(threading.Thread):

    def run(self):
        self.exc = None           
        try:
            experiment2(net,experiments,conf)
        except BaseException as e:
            self.exc = e
    
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

class ThreadExperiment1TakeControllerDown(threading.Thread):

    def run(self):
        self.exc = None           
        try:
            experiment1TakeControllerDown(experiments,conf)
        except BaseException as e:
            self.exc = e
    
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

class ThreadExperimentPing(threading.Thread):

    def run(self):
        self.exc = None           
        try:
            experimentPing(net,experiments)
        except BaseException as e:
            self.exc = e
    
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

class ThreadMonitorControllersConnection(threading.Thread):

    def run(self):
        self.exc = None           
        while True:
            try:
                monitorControllers(net,conf,networks,controllers)
            except BaseException as e:
                self.exc = e
       
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

class ThreadPrimaryLoadBalancing(threading.Thread):

    def run(self):
        self.exc = None           
        while True:
            try:
                primaryLoadBalancing(networks,conf,controllers)
            except BaseException as e:
                self.exc = e
       
    def join(self):
        threading.Thread.join(self)
        if self.exc:
            raise self.exc

def experiment1(net,experiments,conf):

    experiment1Threads = []

    while(1):
        if int(experiments.hget("1","start")) == 1: #start the experiment
            
            start = time.time()

            print("\n****************************\nStarting EXPERIMENT 1...\n****************************")
            
            #start ping thread
            tex11 = ThreadExperimentPing(target=experimentPing,args=[net,experiments])
            tex11.start()
            experiment1Threads.append(tex11)

            #start controller fail thread
            tex12 = ThreadExperiment1TakeControllerDown(target=experiment1TakeControllerDown,args=[experiments,conf])
            tex12.start()
            experiment1Threads.append(tex12)

            #wait for both threads to complete
            for t in experiment1Threads:
                try:
                    t.join()
                except Exception as e:
                    print("Thread error!", e)

            end = time.time()
        
            failTime = int(experiments.hget("1","failTime"))

            #experiment headers
            with open('experiment1.txt', 'a') as f:
                f.write("* Connection Model: "+conf.connectionModel+"\n")
                f.write("* N Switches: "+str(conf.nSwitches)+"\n")
                f.write("* N Hosts: "+str(int(conf.nHostsPerSwitch)*int(conf.nSwitches))+"\n")              
                f.write("* N Packets: "+str(experiments.hget("experiment","nPackets"))+"\n")
                f.write(str("* Fail time (s): "+str(failTime)+"\n"))                

            if conf.connectionModel == "primary-replica":
                clockPrimaryFail = float(experiments.hget("1","clockPrimaryFail"))
                clockPrimaryRecovery = float(experiments.hget("1","clockPrimaryRecovery"))
                with open('experiment1.txt', 'a') as f:
                    f.write(str("* Primary recovery time (s): "+str(clockPrimaryRecovery-clockPrimaryFail)+"\n"))                

            with open('experiment1.txt', 'a') as f:
                f.write(str("* Execution duration (s): "+str(end-start)+"\n"))
                f.write("-------------\n")

            print("\n****************************\nEnded EXPERIMENT 1...\n****************************")
            
            experiments.hset("1","start",0)

            break

def experiment2(net,experiments,conf):

    experiment2Threads = []

    while(1):
        if int(experiments.hget("2","start")) == 1: #start the experiment
            
            start = time.time()

            print("\n****************************\nStarting EXPERIMENT 2...\n****************************")
            
            #start ping thread
            tex21 = ThreadExperimentPing(target=experimentPing,args=[net,experiments])
            tex21.start()
            experiment2Threads.append(tex21)

            #start load balancing thread
            if conf.connectionModel == "primary-replica" and conf.primaryReplicaLoadBalancingTime > 0:
                tex22 = ThreadPrimaryLoadBalancing(target=primaryLoadBalancing,args=[networks,conf,controllers])
                tex22.start()

            #wait for threads to complete
            for t in experiment2Threads:
                try:
                    t.join()
                except Exception as e:
                    print("Thread error!", e)

            end = time.time()

            #experiment headers
            with open('experiment2.txt', 'a') as f:
                f.write("* Connection Model: "+conf.connectionModel+"\n")
                f.write("* N Switches: "+str(conf.nSwitches)+"\n")
                f.write("* N Hosts: "+str(int(conf.nHostsPerSwitch)*int(conf.nSwitches))+"\n")              
                f.write("* N Packets: "+str(experiments.hget("experiment","nPackets"))+"\n")              
                
            with open('experiment2.txt', 'a') as f:
                f.write(str("* Switch-to-controller messages: "+experiments.hget("2","nSwitchControllerMsgs")+"\n"))
                f.write(str("* Controller-to-switch messages: "+experiments.hget("2","nControllerSwitchMsgs")+"\n"))
                f.write(str("* Execution duration (s): "+str(end-start)+"\n"))
                f.write("-------------\n")

            print("\n****************************\nEnded EXPERIMENT 2...\n****************************")
            
            experiments.hset("1","start",0)

            break

def experiment1TakeControllerDown(experiments,conf):

    failTime = int(experiments.hget("1","failTime"))
    sleep(failTime)
    print("\n[!] Taking down controller 6001...")
    
    os.system('sudo kill -9 `sudo lsof -t -i:6001`')

    if conf.connectionModel == "primary-replica":
        experiments.hset("1","clockPrimaryFail",time.time())

def experimentsHostsIPs(experiments,net):

    hosts = ast.literal_eval(experiments.hget("experiment","hostsNames"))
    hostsIPs = []

    for host in hosts:
        h = net.get(host)
        hostsIPs.append(h.IP())

    experiments.hset("experiment","hostsIPs",str(hostsIPs))

def experimentPing(net, experiments):

    nPackets = experiments.hget("experiment","nPackets")

    hostsNames = ast.literal_eval(experiments.hget("experiment","hostsNames"))
    hostsIPs = ast.literal_eval(experiments.hget("experiment","hostsIPs"))

    #each host ping each other host
    for src in hostsNames:
        pingAddresses = ""
        for dst in hostsNames:
            if src != dst:
                pingAddresses += hostsIPs[hostsNames.index(dst)]
                pingAddresses += " "

        hsrc = net.get(src)
        ping = hsrc.cmd(str('fping ' + pingAddresses + '-c ' + nPackets + ' -q -r 0'))

        with open(str('experiment'+experiments.hget("experiment","running")+'.txt'), 'a') as f:
            f.write(ping)

    print("\n[OK] Experiment output saved to file")

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

def electNewPrimary(networks,conf,allControllers):

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

        #get the last PRIMARY
        if networks.hget(conf.netId,"currentPrimary") == None:
            lastPrimary = random.choice(ports) #choose any
        else:
            lastPrimary = int(networks.hget(conf.netId,"currentPrimary"))

        #elect the next PRIMARY (based on least amount of reqs)
        nextPrimary = int(ports[reqs.index(min(reqs))])

        #if there has been a change in mastery
        if lastPrimary != nextPrimary:
            print("-------------")
            print("Electing new PRIMARY...")
            print("Available controllers: ",availableControllers)
            print(availableControllers[ports.index(nextPrimary)],"elected as PRIMARY")
            print("-------------")
            #set the new PRIMARY as current PRIMARY
            networks.hset(conf.netId,"currentPrimary",nextPrimary)
            freePrimary(networks,conf)
        else:
            print("-------------")
            print("No changes to mastery...")
            print("-------------")
    else: #if there were no controllers available
        networks.hdel(conf.netId,"currentPrimary")
        freePrimary(networks,conf)

def freePrimary(networks,conf):

    datapaths = ast.literal_eval(networks.hget(conf.netId,"datapaths"))
    networks.hset(conf.netId,"primaryCredits",len(datapaths))

def monitorControllers(net,conf,networks,controllers):

    sleep(1)
    print("\n*** Monitoring controllers...")
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

        try:
            controller = net.getNodeByName(controllerName)
        except:
            addController(net,controllerName,myControllers[controllerName],conf)
            controller = net.getNodeByName(controllerName)

        c = networks.hgetall(conf.netId)
        d = ast.literal_eval(c[controllerName])
        
        #check controllers connections
        if controller.isListening(ip,myControllers[controllerName]) == False: #if the controller is down

            d["connected"] = 0
            networks.hset(conf.netId,controllerName,str(d))
            
            #the controller down was the PRIMARY
            if networks.hget(conf.netId,"currentPrimary") != None:
                if int(networks.hget(conf.netId,"currentPrimary"))==int(myControllers[controllerName]):
                    print("PRIMARY is down!!!")
                    electNewPrimary(networks,conf,allControllers)
        else:
            d["connected"] = 1
            networks.hset(conf.netId,controllerName,str(d))

    raise MyException("An error in thread")

def primaryLoadBalancing(networks,conf,controllers):

    allControllers = controllers.keys()

    sleep(conf.primaryReplicaLoadBalancingTime)
    print("-------------")
    electNewPrimary(networks,conf,allControllers)

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
    experiments = readRedisDatabase(conf.ip,conf.redisPort,4)
  
    #create network
    topo = MyTopo(conf.nSwitches,conf.nHostsPerSwitch,conf.netId,conf.failMode,experiments)
    net = Mininet(topo=topo,  build=False)

    #add initial controllers
    initialControllers = networks.hgetall(conf.netId) #controllers defined to initilization
    allControllers = controllers.keys()

    for c in initialControllers:
        if c in allControllers:
            d = ast.literal_eval(initialControllers[c])
            addController(net,c,int(d["port"]),conf)

    #build network
    net.build()
    net = addSwitchToSwitchLinks(net,namespaces,conf.nSwitches)
    experimentsHostsIPs(experiments,net)

    #start network
    net.start()
    freePrimary(networks,conf)

    threads = []

    #multithreading monitorControllers
    t1 = ThreadMonitorControllersConnection(target=monitorControllers,args=[net,conf,networks,controllers])
    t1.start()
    threads.append(t1)

    #multithreading primaryLoadBalancing
    if conf.connectionModel == "primary-replica" and conf.primaryReplicaLoadBalancingTime > 0 and (experiments.hget("experiment","running")) == 0:
        t2 = ThreadPrimaryLoadBalancing(target=primaryLoadBalancing,args=[networks,conf,controllers])
        t2.start()
        threads.append(t2)

    #EXPERIMENT 1
    if int(experiments.hget("experiment","running")) == 1:

        #start the experiment
        tex1 = ThreadExperiment1(target=experiment1,args=[net,experiments,conf])
        tex1.start()
        threads.append(tex1)

    #EXPERIMENT 2
    elif int(experiments.hget("experiment","running")) == 2:
        
        #start the experiment
        tex2 = ThreadExperiment2(target=experiment2,args=[net,experiments,conf])
        tex2.start()
        threads.append(tex2)

    else:
        cli = CLI(net)

    for t in threads:
        try:
            t.join()
        except Exception as e:
            print("Thread error!", e)

    net.stop()
