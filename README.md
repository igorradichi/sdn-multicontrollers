# A Ryu Multicontroller Platform (SDN)

**Status**: Finished

|Work record|
|---|
|Igor Radichi|
|Professor Luciano de Errico|
|Final Paper|
|Electrical Engineering BSc, w/ Computer Science spec.|
|Universidade Federal de Minas Gerais - UFMG|

## Programs
|Application|Version used|
|---|---|
|Mininet|2.3.0.dev6|
|Open vSwitch|2.13.8|
|Ryu|4.34|
|Redis|5.0.7|
|Python|3.8.10|
|Wireshark|3.2.3|
|fping|4.2|
|Ubuntu|20.04 LTS| 

 
## Initialization
- description: initialization program
- must be run every time, before starting the other layers (in this order):
  - Initialization -> Infrastructure -> Control

  ```
  sudo python3 init.py
  ```
- ```init.py```
  - Initialization file (calls ```init.conf``` internally)
- ```init.conf```
  - config file for initialization
  - ```ip``` IP address for the Redis server
  - ```redisPort``` Redis Server port
  - ```controllersFirstPort``` port for the first controller created
  - ```nControllersPerNetwork``` number of initial controllers per network
  - ```nNetworks``` number of networks
  - ```experiment``` experiment running (set to 0 if none)
  - ```experimentNPackets``` number of packets sent from host to host during experiments ICMP traffic
  - ```experiment1FailTime``` c1 failtime during Experiment 1 execution

## Infrastructure layer
### Network
- description: n-switch-m-hosts linear topology, with automated switch and hosts creation, automated controller creation, controller fault detection and load balancing

  ```
  sudo python3 network.py net1.conf info
  ```
- ```network.py```
  - Mininet network file
- ```net1.conf```
  - config file for the network being initialized
  - ```netId``` network Id
  - ```failMode``` OpenvSwitches failmode (either ```standalone``` ou ```secure```)
  - ```ip``` IP address the switches should connect
  - ```connectionModel``` switch-controller connection model (either ```primary-replica``` or ```equal```)
  - ```primaryReplicaLoadBalancingTime``` time in seconds for the network to recurrently balance its controllers load (set to ```0``` if not desired)
  - ```nSwitches``` number of switches to be present (each switch will connect to its neighbor - linear model)
  - ```nHostsPerSwitch``` number of hosts per switch
  - ```flowIdleTimeout``` switches' flow entries idle timeout
  - ```flowHardTimeout``` switches' flow entries hard timeout

- ```info```
  - logger level (debug, info, output, warning, error, critical)
  
## Control layer
### Controller

- description: learning controller for L2 Open vSwitch

  ```
  #Controller c1
  ryu-manager --ofp-tcp-listen-port 6001 --wsapi-port 50001 --config-file c1.conf controller.py ryu.app.ofctl_rest

  #Controller c2
  ryu-manager --ofp-tcp-listen-port 6002 --wsapi-port 50002 --config-file c2.conf controller.py ryu.app.ofctl_rest

  #Controller c3
  ryu-manager --ofp-tcp-listen-port 6003 --wsapi-port 50003 --config-file c3.conf controller.py ryu.app.ofctl_rest

  #Controller c4
  ryu-manager --ofp-tcp-listen-port 6004 --wsapi-port 50004 --config-file c4.conf controller.py ryu.app.ofctl_rest

  #...and so on
  ```
- ```--ofp-tcp-listen-port <PORT>```
  - the TCP port the controller should listen to
  - must be different for each controller
  - should be the same as the one inside the config file
- ```--wsapi-port <PORT>```
  - the TCP port for the controller's web server
  - must be different for each controller
  - enables interaction with the controller using REST
    ```
    #Example
    curl -X GET http://localhost:8080/stats/switches | jq
    ```
- ```--config-file <FILE>```
  - config file for the controller being initialized (auto configured when ```network.py``` runs)
  - ```net1.conf```
  - config file for the network being initialized
  - ```name``` controller name
  - ```ip``` IP address for the connection
  - ```port``` listening TCP port
    - the TCP port should be the same as the one passed in the first terminal argument
  - ```connectionmodel``` switch-controller connection model  (either ```primary-replica``` or ```equal```)
  - ```flowidletimeout``` switches' flow entries idle timeout
  - ```flowhardtimeout``` switches' flow entries hard timeout
  - ```redisport``` Redis Server port
- ```controller.py```
  - Ryu controller application file name
- ```ryu.app.ofctl_rest``` 
  - Ryu built-in application, which enables REST interactions with the controller