'''
Master App, testing for master controller
'''
# -*- encoding: utf-8 -*-
# file: MasterApp.py

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import HANDSHAKE_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import packet
from ryu.controller import dpset
from ryu.ofproto import ofproto_v1_3
from threading import Thread
import socket
import time
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ipv4

class MasterApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super(MasterApp, self).__init__(*args, **kwargs)
        print('prepare server')
        master_server = MasterServer(7999)
        print('starting server')
        master_server.start()
        print('echo server started')
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        self.send_role_request(datapath, ofproto.OFPCR_ROLE_MASTER, 0)
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
    
    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                                actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:

            # check IP Protocol and create a match for IP
            if eth.ethertype == ether_types.ETH_TYPE_IP:
                ip = pkt.get_protocol(ipv4.ipv4)
                srcip = ip.src
                dstip = ip.dst
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                        ipv4_src=srcip,
                                        ipv4_dst=dstip
                                        )
                # verify if we have a valid buffer_id, if yes avoid to send both
                # flow_mod & packet_out
                if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                    self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                    return
                else:
                    self.add_flow(datapath, 1, match, actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    @set_ev_cls(dpset.EventDP, MAIN_DISPATCHER)
    def on_dp_change(self, ev):

        if ev.enter:
            dp = ev.dp
            dpid = dp.id
            ofp = dp.ofproto
            ofp_parser = dp.ofproto_parser

            print('dp entered, id is %s' % (dpid))
            self.send_role_request(dp, ofp.OFPCR_ROLE_MASTER, 0)


    @set_ev_cls(ofp_event.EventOFPErrorMsg,
            [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def on_error_msg(self, ev):
        msg = ev.msg
        print('receive a error message: %s' % (msg))

    @set_ev_cls(ofp_event.EventOFPRoleReply, MAIN_DISPATCHER)
    def on_role_reply(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        role = msg.role
        gen_id = msg.generation_id

        if role == ofp.OFPCR_ROLE_EQUAL:
            print('now is equal')
        elif role == ofp.OFPCR_ROLE_MASTER:
            print('now is master')
        elif role == ofp.OFPCR_ROLE_SLAVE:
            print('now is slave')
        print('')

    def send_role_request(self, datapath, role, gen_id):
        ofp_parser = datapath.ofproto_parser
        msg = ofp_parser.OFPRoleRequest(datapath, role, gen_id)
        datapath.send_msg(msg)


class ServerTask(Thread):

    def __init__(self, server, client_socket):
        Thread.__init__(self)
        self.server = server
        self.client_socket = client_socket

    def run(self):
        try:
            while True:
                self.client_socket.send('hello')
                client_data = self.client_socket.recv(1024)
                # print('from client: %s' % (client_data)
                time.sleep(1)
        except Exception as e:
            print('client break')
            client_sockets = self.server.client_sockets
            client_socket = self.client_socket
            client_sockets.remove(client_socket)
            print(e)

class MasterServer(Thread):
    '''
    server for master, shows that it is alive
    '''
    def __init__(self, port):
        Thread.__init__(self)
        self.client_sockets = []
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.server_socket.bind(('127.0.0.1', port))

    def run(self):

        self.server_socket.listen(5)
        while True:
            (client_socket, addr) = self.server_socket.accept()
            self.client_sockets.append(client_socket)
            server_task = ServerTask(self, client_socket)
            server_task.start()

