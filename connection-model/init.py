import redis
import configparser
import sys

if __name__ == '__main__':

    config = configparser.ConfigParser()
    config.read('init.conf')
    
    ip = config['DEFAULT']['ip']
    redisPort = config['DEFAULT']['redisPort']
    controllersFirstPort = config['DEFAULT']['controllersFirstPort']
    
    networks = redis.Redis(ip,redisPort,0)
    networks.flushdb()

    networks.hset("network","nextControllerPort",controllersFirstPort)
    networks.hset("network","nextControllerIndex",0)
    networks.hset("network","nextSwitchIndex",0)
    networks.hset("network","nextHostIndex",0)

    master = redis.Redis(ip,redisPort,1)
    master.flushdb()