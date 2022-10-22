from http.client import NETWORK_AUTHENTICATION_REQUIRED
#from types import NoneType
import redis
import configparser
import sys
import os 

if __name__ == '__main__':

    os.system('sudo mn -c')

    #config file
    config = configparser.ConfigParser()
    config.read('init.conf')
    
    ip = config['DEFAULT']['ip']
    redisPort = config['DEFAULT']['redisPort']
    controllersFirstPort = int(config['DEFAULT']['controllersFirstPort'])
    nNetworks = int(config['DEFAULT']['nNetworks'])
    nControllersPerNetwork = int(config['DEFAULT']['nControllersPerNetwork'])
    experiment = int(config['DEFAULT']['experiment'])
    experiment1FailTime = int(config['DEFAULT']['experiment1FailTime'])
    experimentNPackets = config['DEFAULT']['experimentNPackets']

    #flush databases
    controllers = redis.Redis(ip,redisPort,0,decode_responses=True)
    networks = redis.Redis(ip,redisPort,1,decode_responses=True)
    namespaces = redis.Redis(ip,redisPort,2,decode_responses=True)
    routingTable = redis.Redis(ip,redisPort,3,decode_responses=True)
    experiments = redis.Redis(ip,redisPort,4,decode_responses=True)

    controllers.flushdb()
    networks.flushdb()
    namespaces.flushdb()
    routingTable.flushdb()
    experiments.flushdb()

    nControllers = nNetworks*nControllersPerNetwork
    controllerPort = controllersFirstPort

    #set controllers ports
    for controller in range (1,nControllers+1):
        controllers.set("c"+str(controller),controllerPort)
        controllerPort += 1

    #networks initial state
    controllerIndex = 1
    for network in range(1,nNetworks+1):
        for controller in range(1,nControllersPerNetwork+1):
            
            c = {
                'port': controllers.get("c"+str(controllerIndex)),
                'reqs': 0
            }

            networks.hset(network,"c"+str(controllerIndex),str(c))
            controllerIndex += 1

    print("*************",controllerIndex)
    namespaces.set("nextSwitchIndex",1)
    namespaces.set("nextHostIndex",1)
    
    experiments.hset("experiment","running",experiment)
    experiments.hset("experiment","nPackets",experimentNPackets)

    #Experiment 1
    experiments.hset("1","start",0)
    experiments.hset("1","failTime",experiment1FailTime)

    #Experiment 2
    experiments.hset("2","start",0)
    experiments.hset("2","nControllerSwitchMsgs",0)
    experiments.hset("2","nSwitchControllerMsgs",0)

    #delete controllers config files
    for i in range(1,controllerIndex):
        print('c'+str(i)+'.conf')
        os.remove('c'+str(i)+'.conf')