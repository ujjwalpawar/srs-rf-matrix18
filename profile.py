#!/usr/bin/env python

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as pn
import geni.rspec.emulab as emulab


tourDescription = """
### srsRAN 5G using the POWDER RF Attenuator Matrix

This profile instantiates an experiment for running srsRAN_Project 5G with a COTS
UE and/or SDR UE.

The following will be deployed:

"""

tourInstructions = """

Startup scripts will still be running when your experiment becomes ready.
Watch the "Startup" column on the "List View" tab for your experiment and wait
until all of the compute nodes show "Finished" before proceeding.

"""

BIN_PATH = "/local/repository/bin"
ETC_PATH = "/local/repository/etc"
UBUNTU_IMG = "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD"
COTS_UE_IMG = "urn:publicid:IDN+emulab.net+image+PowderTeam:cots-jammy-image"
COMP_MANAGER_ID = "urn:publicid:IDN+emulab.net+authority+cm"
DEFAULT_SRSRAN_HASH = "a15950301c5f3a1a166b79bb6c9ee901a4e8c2dd"
OPEN5GS_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-open5gs.sh")
SRSRAN_DEPLOY_SCRIPT = os.path.join(BIN_PATH, "deploy-srsran.sh")
NODE_IDS = {
    "sdru": "x310-1",
    "uemon": "n300-2",
    "ue": "nuc27",
    "rumon": "n310-1",
}
MATRIX_GRAPH = {
    "sdru": ["ue", "rumon"],
    "uemon": ["ue", "rumon"],
    "ue": ["sdru", "uemon"],
    "rumon": ["sdru", "uemon"],
}
MATRIX_INPUTS = ["sdru", "uemon"]
RF_IFACES = {}
RF_LINK_NAMES = {}
for k, v in MATRIX_GRAPH.items():
    RF_IFACES[k] = {}
    for node in (v):
        RF_IFACES[k][node] = "{}_{}_rf".format(k, node)
        if k in MATRIX_INPUTS:
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)] = []

for k, v in MATRIX_GRAPH.items():
    if k in MATRIX_INPUTS:
        for node in (v):
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)].append(RF_IFACES[k][node])
            RF_LINK_NAMES["rflink_{}_{}".format(k, node)].append(RF_IFACES[node][k])

def sdr_node_pair(role, sdr_id):
    node = request.RawPC("{}-{}-comp".format(sdr_id, role))
    node.component_manager_id = COMP_MANAGER_ID
    if role == "gnb":
        node.hardware_type = params.sdru_nodetype
    else:
        node.hardware_type = params.mon_nodetype

    if params.sdr_compute_image:
        node.disk_image = params.sdr_compute_image
    else:
        node.disk_image = UBUNTU_IMG

    node_radio_if = node.addInterface("usrp_if")
    if role == "gnb":
        ipaddr = "192.168.40.1"
    else:
        ipaddr = "192.168.20.1"

    node_radio_if.addAddress(pg.IPv4Address(ipaddr, "255.255.255.0"))

    radio_link = request.Link("sdr_id-link-{}".format(role))
    radio_link.bandwidth = 10*1000*1000
    radio_link.addInterface(node_radio_if)

    sdr = request.RawPC("{}-{}-sdr".format(sdr_id, role))
    sdr.component_id = sdr_id
    sdr.component_manager_id = COMP_MANAGER_ID
    radio_link.addNode(sdr)

    if params.srsran_commit_hash:
        srsran_hash = params.srsran_commit_hash
    else:
        srsran_hash = DEFAULT_SRSRAN_HASH

    if role == "gnb":
        nodeb_cn_if = node.addInterface("nodeb-cn-if")
        nodeb_cn_if.addAddress(pg.IPv4Address("192.168.1.2", "255.255.255.0"))
        cn_link.addInterface(nodeb_cn_if)
        cmd = "{} '{}'".format(SRSRAN_DEPLOY_SCRIPT, srsran_hash)
        node.addService(pg.Execute(shell="bash", command=cmd))
        node.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-cpu.sh"))
        node.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))

def b210_nuc_pair(b210_node):
    node = request.RawPC("{}-cots-ue".format(b210_node))
    node.component_manager_id = COMP_MANAGER_ID
    node.component_id = b210_node
    node.disk_image = COTS_UE_IMG
    node.addService(pg.Execute(shell="bash", command="/local/repository/bin/module-off.sh"))
    node.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-udhcpc-script.sh"))

pc = portal.Context()
node_types = [
    ("d430", "Emulab, d430"),
    ("d740", "Emulab, d740"),
]

pc.defineParameter(
    name="sdru_nodetype",
    description="Type of compute node paired with the RU SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[1],
    legalValues=node_types
)

pc.defineParameter(
    name="mon_nodetype",
    description="Type of compute node paired with the RU SDR",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[0],
    legalValues=node_types
)

pc.defineParameter(
    name="cn_nodetype",
    description="Type of compute node to use for CN node",
    typ=portal.ParameterType.STRING,
    defaultValue=node_types[0],
    legalValues=node_types
)

pc.defineParameter(
    name="sdr_compute_image",
    description="Image to use for compute connected to SDRs",
    typ=portal.ParameterType.STRING,
    defaultValue="",
    advanced=True
)

pc.defineParameter(
    name="srsran_commit_hash",
    description="Commit hash for srsRAN",
    typ=portal.ParameterType.STRING,
    defaultValue="",
    advanced=True
)

params = pc.bindParameters()
pc.verifyParameters()
request = pc.makeRequestRSpec()

role = "cn5g"
cn_node = request.RawPC(role)
cn_node.component_manager_id = COMP_MANAGER_ID
cn_node.hardware_type = params.cn_nodetype
cn_node.disk_image = UBUNTU_IMG
cn_if = cn_node.addInterface("{}-if".format(role))
cn_if.addAddress(pg.IPv4Address("192.168.1.1", "255.255.255.0"))
cn_link = request.Link("{}-link".format(role))
cn_link.setNoBandwidthShaping()
cn_link.addInterface(cn_if)
cn_node.addService(pg.Execute(shell="bash", command=OPEN5GS_DEPLOY_SCRIPT))
cn_node.addService(pg.Execute(shell="bash", command="/local/repository/bin/install-improved-iperf3.sh"))
cn_node.addService(pg.Execute(shell="bash", command="/local/repository/bin/start-iperf.sh"))
cn_node.addService(pg.Execute(shell="bash", command="/local/repository/bin/install-vsftpd.sh.sh"))

# collect node objects for RF matrix
matrix_nodes = {}

node_name = "cudu"
cudu = request.RawPC(node_name)
cudu.component_manager_id = COMP_MANAGER_ID
cudu.hardware_type = params.sdru_nodetype
if params.sdr_compute_image:
    cudu.disk_image = params.sdr_compute_image
else:
    cudu.disk_image = UBUNTU_IMG
cudu_cn_if = cudu.addInterface("{}-cn-if".format(node_name))
cudu_cn_if.addAddress(pg.IPv4Address("192.168.1.2", "255.255.255.0"))
cn_link.addInterface(cudu_cn_if)
node_sdr_if = cudu.addInterface("usrp_if")
node_sdr_if.addAddress(pg.IPv4Address("192.168.40.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
if params.srsran_commit_hash:
    srsran_hash = params.srsran_commit_hash
else:
    srsran_hash = DEFAULT_SRSRAN_HASH
cmd = "{} '{}'".format(SRSRAN_DEPLOY_SCRIPT, srsran_hash)
cudu.addService(pg.Execute(shell="bash", command=cmd))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens sdru1 0"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens sdru2 95"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))

node_name = "sdru"
sdru = request.RawPC("{}-sdr".format(node_name))
sdru.component_id = NODE_IDS[node_name]
sdr_link.addNode(sdru)
sdru.Desire("rf-controlled", 1)
matrix_nodes[node_name] = sdru

node_name = "uemncmp"
uemncmp = request.RawPC(node_name)
uemncmp.component_manager_id = COMP_MANAGER_ID
uemncmp.hardware_type = params.mon_nodetype
if params.sdr_compute_image:
    uemncmp.disk_image = params.sdr_compute_image
else:
    uemncmp.disk_image = UBUNTU_IMG
node_sdr_if = uemncmp.addInterface("{}-sdr-if".format(node_name))
node_sdr_if.addAddress(pg.IPv4Address("192.168.20.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)

node_name = "uemon"
uemon = request.RawPC("{}-sdr".format(node_name))
uemon.component_id = NODE_IDS[node_name]
sdr_link.addNode(uemon)
uemon.Desire("rf-controlled", 1)
matrix_nodes[node_name] = uemon

node_name = "rumncmp"
rumncmp = request.RawPC(node_name)
rumncmp.component_manager_id = COMP_MANAGER_ID
rumncmp.hardware_type = params.mon_nodetype
if params.sdr_compute_image:
    rumncmp.disk_image = params.sdr_compute_image
else:
    rumncmp.disk_image = UBUNTU_IMG
node_sdr_if = uemncmp.addInterface("{}-sdr-if".format(node_name))
node_sdr_if.addAddress(pg.IPv4Address("192.168.20.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)

node_name = "rumon"
rumon = request.RawPC("{}-sdr".format(node_name))
rumon.component_id = NODE_IDS[node_name]
sdr_link.addNode(rumon)
rumon.Desire("rf-controlled", 1)
matrix_nodes[node_name] = rumon

# ue node with COTS UE and B210
node_name = "ue"
ue = request.RawPC(node_name)
ue.component_manager_id = COMP_MANAGER_ID
ue.component_id = NODE_IDS[node_name]
ue.disk_image = COTS_UE_IMG
ue.Desire("rf-controlled", 1)
ue.addService(pg.Execute(shell="bash", command="/local/repository/bin/module-airplane.sh"))
ue.addService(pg.Execute(shell="bash", command="/local/repository/bin/setup-cots-ue.sh internet"))
matrix_nodes[node_name] = ue

rf_ifaces = {}
for node_name, node in matrix_nodes.items():
    for rf_iface_name in RF_IFACES[node_name].values():
        rf_ifaces[rf_iface_name] = node.addInterface(rf_iface_name)

for rf_link_name, rf_iface_names in RF_LINK_NAMES.items():
    rf_link = request.RFLink(rf_link_name)
    for iface_name in rf_iface_names:
        rf_link.addInterface(rf_ifaces[iface_name])


tour = ig.Tour()
tour.Description(ig.Tour.MARKDOWN, tourDescription)
tour.Instructions(ig.Tour.MARKDOWN, tourInstructions)
request.addTour(tour)

pc.printRequestRSpec(request)
