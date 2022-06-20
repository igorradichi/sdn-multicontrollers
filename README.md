# Multicontrollers in SDN using Ryu

**Status**: WIP 🚧

|Work record|
|---|
|Igor Radichi|
|Professor Luciano de Errico|
|Final Paper|
|Electrical Engineering BSc, w/ Computer Science spec.|
|Universidade Federal de Minas Gerais - UFMG|

## Prerequisites
|Application|Version used|
|---|---|
|Mininet|2.3.0.dev6|
|Open vSwitch|2.13.5|
|Ryu|4.34|
|Redis|5.0.7|
|Python|3.8.10|
|Curl|7.68|

### Others
|Application|Version used|
|---|---|
|Visual Studio Code|1.68.1|
|Ubuntu|20.04 LTS| 
## Infrastructure layer
### Network
- description: single-switch topology (with 4 hosts), with automated controller creation and controller fault detection

  ```
    sudo python3 myTopology.py topo.conf
  ```
- ```myNetwork.py```
  - Mininet network file
- ```topo.conf```
  - config file for the network being initialized
  - must contain the IP address the switch should connect
  - must contain the number of controllers to be present
  - must contain the TCP of the first controller connection
    - the following ports will be added +1 and so on
  
## Control layer
### Controller

- description: master-slave learning controller for L2 Open vSwitch

  ```
  #Controller c0
  ryu-manager --ofp-tcp-listen-port 6633 --wsapi-port 50000 --config-file c0.conf myController.py ryu.app.ofctl_rest

  #Controller c1
  ryu-manager --ofp-tcp-listen-port 6634 --wsapi-port 50001 --config-file c1.conf myController.py ryu.app.ofctl_rest

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
  - config file for the controller being initialized
  - must contain the IP and the TCP port it will be listening to
    - the TCP port should be the same as the one passed in the first argument
- ```myController.py```
  - Ryu controller application file name
- ```ryu.app.ofctl_rest``` 
  - Ryu built-in application, which enables REST interactions with the controller

## Application Layer

To be developed. Probably will be used to extract statistics through the control plane vision, using REST.