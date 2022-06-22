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

## Pendências

- Reorganizar código do network.py, ficou bagunçado de novo. Também rever se dá pra enxugar algo das threads.
- Deixar endereços MAC em função do hostIndex ('00:00:00:00:00:0'+index)
- Tabela de controladores exclusiva (que mostra o up), de acordo com o netId
- Tabela de roteamento exclusiva, de acordo com o netId
- Implementar auto-delete de todos os c0,c1,c2.conf etc dentro do init.py
- Implementar modelos de arquitetura

## Initialization
- description: resets some Redis databases
- must be run every time, before starting the other layers (in this order):
  - Initizalization -> Infrastructure -> Control -> Application
- tip: always run ```sudo mn -c``` first, just in case

  ```
  sudo python3 init.py
  ```

## Infrastructure layer
### Network
- description: single-switch topology (with 4 hosts), with automated controller creation and controller fault detection

  ```
  sudo python3 network.py net1.conf master-slave info
  ```
- ```network.py```
  - Mininet network file
- ```net1.conf```
  - config file for the network being initialized
  - ```netId``` must contain the network Id
  - ```ip``` must contain the IP address the switch should connect
  - ```nControllers``` must contain the number of controllers to be present
  - ```flowIdleTimeout``` must contain the switches' flow entries idle timeout
  - ```flowHardTimeout``` must contain the switches' flow entries hard timeout
- ```master-slave```
  - switch-controller connection model (either ```master-slave``` or ```equal```)
- ```critical```
  - logger level (debug, info, output, warning, error, critical)
  
## Control layer
### Controller

- description: master-slave learning controller for L2 Open vSwitch

  ```
  #Controller c0
  ryu-manager --ofp-tcp-listen-port 6633 --wsapi-port 50000 --config-file c0.conf controller.py ryu.app.ofctl_rest

  #Controller c1
  ryu-manager --ofp-tcp-listen-port 6634 --wsapi-port 50001 --config-file c1.conf controller.py ryu.app.ofctl_rest

  #Controller c2
  ryu-manager --ofp-tcp-listen-port 6635 --wsapi-port 50002 --config-file c2.conf controller.py ryu.app.ofctl_rest

  #Controller c3
  ryu-manager --ofp-tcp-listen-port 6636 --wsapi-port 50003 --config-file c3.conf controller.py ryu.app.ofctl_rest

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
  - ```net1.conf```
  - config file for the network being initialized
  - ```ip``` must contain the IP address of the connection
  - ```port``` must contain TCP port it should listen to
    - the TCP port should be the same as the one passed in the first argument
  - auto configured when ```network.py``` runs
  - ```connectionmodel``` must contain the switch-controller connection model  (either ```master-slave``` or ```equal```)
  - ```flowIdleTimeout``` must contain the switches' flow entries idle timeout
  - ```flowHardTimeout``` must contain the switches' flow entries hard timeout
  - ```redisPort``` must contain the Redis Server port
- ```controller.py```
  - Ryu controller application file name
- ```ryu.app.ofctl_rest``` 
  - Ryu built-in application, which enables REST interactions with the controller

## Application Layer

To be developed. Probably will be used to extract statistics through the control plane vision, using REST.