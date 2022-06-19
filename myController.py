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

class myController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(myController, self).__init__(*args, **kwargs)
        self.r = redis.Redis()

        self.CONF = cfg.CONF
        self.CONF.register_opts([
            cfg.IntOpt('PORT', 
                        default=6633, help = ('Who am I?'))]
        )

        self.logger.info("My port: %s",self.CONF.PORT)
        self.datapaths = []
        #self.monitor_thread = hub.spawn(self._monitor)
        hub.spawn(self.myfunction)
        
    
    def myfunction(self):
        self.logger.info("waiting fot a master to fall")
        while True:
            hub.sleep(1)
            if int(self.r.hget("master","port"))==0:
                self.logger.info("FREE MASTER")
            else:
                self.logger.info("THERE IS STILL A MASTER")

    def _monitor(self):
        self.logger.info("waiting fot a master to fall")
        while True:
            hub.sleep(5)
            if int(self.r.hget("master","port"))==0 and len(self.datapaths)>0:
                self.selfElectMaster(1,self.datapaths[0].ofproto) ########
    
    def selfElectMaster(self,datapath,ofproto):
        self.r.hset("master","credits",0)
        self.r.hset("master","port",self.CONF.PORT)
        self.send_role_request(datapath,ofproto.OFPCR_ROLE_MASTER)

    #EVENT: SWITCH FEATURES
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        print("here")
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        if int(self.r.hget("master","credits")) == 1:
            self.selfElectMaster(datapath,ofproto)
        else:
            self.send_role_request(datapath,ofproto.OFPCR_ROLE_SLAVE)
        
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def send_role_request(self, datapath, role):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPRoleRequest(datapath, role,
                                        ofp.OFPCID_UNDEFINED, 0)
        datapath.send_msg(req)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    #EVENT: OTHER CONTROLLERS STATUS - DOESNT WORK
    @set_ev_cls(ofp_event.EventOFPControllerStatusStatsReply,
                MAIN_DISPATCHER)
    def controller_status_multipart_reply_handler(self, ev):
        status = []
        for s in ev.msg.body:
            status.append('short_id=%d role=%d reason=%d '
                        'channel_status=%d properties=%s' %
                        (s.short_id, s.role, s.reason,
                        s.channel_status, repr(s.properties)))
        self.logger.info('OFPControllerStatusStatsReply received: %s',
                        status)

    #EVENT: ROLE REPLY
    @set_ev_cls(ofp_event.EventOFPRoleReply, MAIN_DISPATCHER)
    def role_reply_handler(self, ev):
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
                        'role=%s short_id=%d, generation_id=%d\n',
                        role, msg.short_id, msg.generation_id)


    #EVENT: STATUS CHANGE ORDER FROM THE SWITCH
    @set_ev_cls(ofp_event.EventOFPRoleStatus, MAIN_DISPATCHER)
    def role_status_handler(self, ev):
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

        self.logger.info('OFPRoleStatus received: role=%s reason=%s '
                        'generation_id=%d properties=%s', role, reason,
                        msg.generation_id, repr(msg.properties))
    
        self.r.hset(0, self.id, role)

    #EVENT: PACKET IN
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        
        dst = eth.dst
        src = eth.src

        dpid = datapath.id

        self.datapaths.append(dpid)

        #self.logger.info("PACKET IN\n dpid: %s\n in_port: %s\n src: %s\n dst: %s\n", dpid, in_port, src, dst)

        self.r.hset(dpid, src, in_port)

        if self.r.hexists(dpid,dst):
            out_port = int(self.r.hget(dpid,dst))
            print("I already knew this port")
        else:
            out_port = ofproto.OFPP_FLOOD
        
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        
        match = parser.OFPMatch(in_port=in_port)

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  match=match, actions=actions, data=data)
        datapath.send_msg(out)