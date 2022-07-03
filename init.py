from http.client import NETWORK_AUTHENTICATION_REQUIRED
#from types import NoneType
import redis
import configparser
import sys
import os

if __name__ == '__main__':

    os.system('sudo mn -c')

    config = configparser.ConfigParser()
    config.read('init.conf')
    
    ip = config['DEFAULT']['ip']
    redisPort = config['DEFAULT']['redisPort']
    controllersFirstPort = int(config['DEFAULT']['controllersFirstPort'])
    nNetworks = int(config['DEFAULT']['nNetworks'])
    nControllersPerNetwork = int(config['DEFAULT']['nControllersPerNetwork'])

    controllers = redis.Redis(ip,redisPort,0)
    networks = redis.Redis(ip,redisPort,1)
    namespaces = redis.Redis(ip,redisPort,2)
    routingTable = redis.Redis(ip,redisPort,3)

    controllers.flushdb()
    networks.flushdb()
    namespaces.flushdb()
    routingTable.flushdb()

    nControllers = nNetworks*nControllersPerNetwork
    controllerPort = controllersFirstPort

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
    
    #delete controllers config files
    
    for i in range(1,controllerIndex):
        print('c'+str(i)+'.conf')
        os.remove('c'+str(i)+'.conf')