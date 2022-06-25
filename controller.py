from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_5
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4
import redis
from ryu import cfg
from ryu.lib import hub
from time import sleep

class controller(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(controller, self).__init__(*args, **kwargs)

        #config file
        self.CONF = cfg.CONF
        self.CONF.register_opts([
            cfg.IntOpt(
                'netid', default=1, help = ('Network Id')
            ),
            cfg.IntOpt(
                'port', default=6001, help = ('Controller Port')
            ),
            cfg.StrOpt(
                'ip', default='127.0.0.1', help = ('Controller IP')
            ),
            cfg.StrOpt(
                'connectionmodel', default='equal', help = ('Switch-controller connection model')
            ),
            cfg.IntOpt(
                'flowidletimeout', default='0', help = ('Switches flow entry idle timeout')
            ),
            cfg.IntOpt(
                'flowhardtimeout', default='0', help = ('Switches flow entry hard timeout')
            ),
            cfg.IntOpt(
                'redisport', default='6379', help = ('Redis server port')
            )
            ]
        )
        
        #initializing redis DBs
        self.routingTable = redis.Redis(host=self.CONF.ip, port=self.CONF.redisport, db = 3)
        self.cluster = redis.Redis(host=self.CONF.ip, port=self.CONF.redisport, db = 1)

        #datapaths dictionary
        self.datapaths = {}

        #controller identity
        self.logger.info("------------------------")
        self.logger.info("Controller port: %s",self.CONF.port)
        self.logger.info("------------------------")
        self.logger.info("Network Id: %s",self.CONF.netid)
        self.logger.info("------------------------")

        if self.CONF.connectionmodel == 'master-slave':
            #start another thread
            hub.spawn(self.monitorMaster)
    
    #note when a MASTER controller is down
    def monitorMaster(self):
        self.logger.info("------------------------")
        self.logger.info("Master is being monitored...")
        self.logger.info("------------------------")
        while True:
            hub.sleep(1)
            if int(self.cluster.hget(self.CONF.netid,"masterCredits"))==1: #if no MASTER is present
                self.logger.info("------------------------")
                self.logger.info("No MASTER present")
                self.logger.info("------------------------")

                if self.cluster.hget(self.CONF.netid,"currentMaster") == None:
                    self.logger.info("Requesting master role...")
                    for datapath in self.datapaths.values():
                        self.selfElectMaster(datapath) #take MASTER role for each datapath
                else:
                    if int(self.CONF.port) == int(self.cluster.hget(self.CONF.netid,"currentMaster")):
                        self.logger.info("Requesting master role...")
                        for datapath in self.datapaths.values():
                            self.selfElectMaster(datapath) #take MASTER role for each datapath

    #send MASTER role request to the datapath
    def selfElectMaster(self,datapath):
        ofproto = datapath.ofproto
        
        self.cluster.hset(self.CONF.netid,"masterCredits",0)
        self.cluster.hset(self.CONF.netid,"currentMaster",self.CONF.port)
        self.sendRoleRequest(datapath,ofproto.OFPCR_ROLE_MASTER)

    #generic role request
    def sendRoleRequest(self, datapath, role):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPRoleRequest(datapath, role,
                                        ofp.OFPCID_UNDEFINED, 0)
        datapath.send_msg(req)

    #add flow entry to the switch flow table
    def addFlow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout)
        datapath.send_msg(mod)

    #EVENT: SWITCH FEATURES
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switchFeaturesHandler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        #register new datapath
        self.datapaths[datapath.id] = datapath

        if self.CONF.connectionmodel == 'master-slave':
            #if there is no MASTER present
            if int(self.cluster.hget(self.CONF.netid,"masterCredits")) == 1 or int(self.cluster.hget(self.CONF.netid,"currentMaster"))==self.CONF.port:
                self.selfElectMaster(datapath) #take MASTER role for this datapath
            else: #else, take SLAVE role
                self.sendRoleRequest(datapath,ofproto.OFPCR_ROLE_SLAVE)
        else:
            self.sendRoleRequest(datapath,ofproto.OFPCR_ROLE_EQUAL)

        #table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.addFlow(datapath, 0, match, actions)

    #EVENT: ROLE REPLY
    @set_ev_cls(ofp_event.EventOFPRoleReply, MAIN_DISPATCHER)
    def roleReplyHandler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto

        if msg.role == ofp.OFPCR_ROLE_NOCHANGE:
            role = 'NOCHANGE'
        elif msg.role == ofp.OFPCR_ROLE_EQUAL:
            role = 'EQUAL'
        elif msg.role == ofp.OFPCR_ROLE_MASTER:
            role = 'MASTER'
        elif msg.role == ofp.OFPCR_ROLE_SLAVE:
            role = 'SLAVE'
        else:
            role = 'unknown'

        self.logger.info('OFPRoleReply received: '
                        'role=%s datapath=%d',
                        role, dp.id)


    #EVENT: STATUS CHANGE ORDER FROM THE SWITCH
    #useful when a controller takes MASTER role from another one
    @set_ev_cls(ofp_event.EventOFPRoleStatus, MAIN_DISPATCHER)
    def roleStatusHandler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto

        if msg.role == ofp.OFPCR_ROLE_NOCHANGE:
            role = 'ROLE NOCHANGE'
        elif msg.role == ofp.OFPCR_ROLE_EQUAL:
            role = 'ROLE EQUAL'
        elif msg.role == ofp.OFPCR_ROLE_MASTER:
            role = 'ROLE MASTER'
        elif msg.role == ofp.OFPCR_ROLE_SLAVE:
            role = 'SLAVE'
        else:
            role = 'unknown'

        if msg.reason == ofp.OFPCRR_MASTER_REQUEST:
            reason = 'MASTER REQUEST'
        elif msg.reason == ofp.OFPCRR_CONFIG:
            reason = 'CONFIG'
        elif msg.reason == ofp.OFPCRR_EXPERIMENTER:
            reason = 'EXPERIMENTER'
        else:
            reason = 'unknown'

        self.logger.info('OFPRoleStatus received: role=%s reason=%s datapath=%s',
                        role, reason, dp.id)


    #EVENT: PACKET IN
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetInHandler(self, ev):

        self.cluster.hincrby(self.CONF.netid,self.CONF.port,1)

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        #ignora LLDP packets
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        
        dst = eth.dst
        src = eth.src

        dpid = datapath.id

        self.logger.info("PACKET IN\n dpid: %s\n in_port: %s\n src: %s\n dst: %s\n", dpid, in_port, src, dst)

        #add to the routing table
        self.routingTable.hset(dpid, src, in_port)

        #if the table already has the info
        if self.routingTable.hexists(dpid,dst):
            out_port = int(self.routingTable.hget(dpid,dst)) #use the info
        else: #else, FLOOD all ports
            out_port = ofproto.OFPP_FLOOD
        
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.addFlow(datapath, 1, match, actions, self.CONF.flowidletimeout, self.CONF.flowhardtimeout)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        
        match = parser.OFPMatch(in_port=in_port)

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  match=match, actions=actions, data=data)
        datapath.send_msg(out)