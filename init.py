from http.client import NETWORK_AUTHENTICATION_REQUIRED
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
    controllersFirstPort = config['DEFAULT']['controllersFirstPort']

    networks = redis.Redis(ip,redisPort,0)

    controllers = redis.Redis(ip,redisPort,2)

    #delete controllers config files
    nextControllerIndex = int(networks.hget("network","nextControllerIndex"))
    
    for i in range(1,nextControllerIndex):
        print('c'+str(i)+'.conf')
        os.remove('c'+str(i)+'.conf')

    controllers.flushdb()
    networks.flushdb()

    networks.hset("network","nextControllerPort",controllersFirstPort)
    networks.hset("network","nextControllerIndex",1)
    networks.hset("network","nextSwitchIndex",1)
    networks.hset("network","nextHostIndex",1)

    master = redis.Redis(ip,redisPort,1)
    master.flushdb()

    routingTable = redis.Redis(ip,redisPort,3)
    routingTable.flushdb()