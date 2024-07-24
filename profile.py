#!/usr/bin/env python

import os

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.igext as ig
import geni.rspec.emulab.pnext as pn
import geni.rspec.emulab as emulab


tourDescription = """
### srsRAN 5G Handover using the Programmable Attenuator Matrix

This profile instantiates a 5G network with srsRAN and Open5GS on POWDER in a
conducted RF evironment with programmable attenuators for emulating different
channel conditions.

The following will be deployed:
- Open5GS CN node (Dell R430)
- srsRAN CU/DU node (Dell R740 + USRP X310 w/ 2x UBX-160 daughter cards)
- DL monitoring node (Dell R430 + USRP N300)
- UL monitoring node (Dell R430 + USRP N300)
- UE node (Intel NUC w/ COTS UE)

"""

tourInstructions = """

Startup scripts will still be running when your experiment becomes ready. Watch
the "Startup" column on the "List View" tab for your experiment and wait until
all of the compute nodes show "Finished" before proceeding.

Once the experiment is ready, you can log into the Open5GS CN node (`cn5g`) and
monitor the AMF and SMF logs:

```
# on the cn5g node
sudo journalctl -u open5gs-amfd -u open5gs-smfd -f --output cat
```

Next, in a session on the srsRAN Project CU/DU node (`cudu`), start the srsRAN
gNB:

```
# on the cudu node
sudo numactl --membind 0 --cpubind 0 \
  /var/tmp/srsRAN_Project/build/apps/gnb/gnb -c /var/tmp/etc/srsran/gnb_rf_x310.yml \
  -c /var/tmp/etc/srsran/slicing.yml
```

In a session on the `ue` node, start the UE connection manager with the target
DNN `internet` in `ipv4` mode:

```
# on the ue node
sudo quectel-CM -s internet -4
```

In aother session on the `ue` node, bring the COTS UE out of airplane mode:

```
# on the ue node
/local/repository/bin/module-on.sh
```

At this point the UE should attach to the gNB...

```
# output of srsran gnb process on cudu node
          |--------------------DL---------------------|-------------------------UL------------------------------
 pci rnti | cqi  ri  mcs  brate   ok  nok  (%)  dl_bs | pusch  rsrp  mcs  brate   ok  nok  (%)    bsr    ta  phr
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  37.5  -5.0   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   28   4.2k    4    0   0%      0 |  37.9  -5.0   28    13k    3    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  35.8  -4.9   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  36.8  -5.1   28    17k    4    0   0%      0   0us   24
   1 4604 |  15   1   27   4.8k    5    0   0%      0 |  36.3  -5.0   28    22k    5    0   0%      0   0us   24
```

In a session on the `ue` node, start a ping process pointed at the core network
UPF, so we can verify that traffic still passes throughout the handover process:

```
# on ue node
ping 10.45.0.1
```

Now that there is some traffic being generated, we can adjust the attenuation on
the paths between the gNB and UE to simulate a degraded channel:

```
# on any node in the experiment
# this command will add 5 dB of attenuation to the path between the gNB and UE
/local/repository/bin/update-attens ru1ue 5
```

You can continue to add more attenuation and witness the effects on the metrics
being output by the gNB process.

The `rumncmp` and `uemncmp` nodes and acompanying SDRs are included to allow for, e.g.:

- realtime monitoring of 5G transmissions
- injecting interference in the DL or UL paths
- recording samples of DL and/or UL transmissions for data gathering purposes

GnuRadio and UHD tools are installed on these nodes.

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
    "rumon": "n300-1",
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
node_sdr_if.addAddress(pg.IPv4Address("192.168.30.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
if params.srsran_commit_hash:
    srsran_hash = params.srsran_commit_hash
else:
    srsran_hash = DEFAULT_SRSRAN_HASH
cmd = "{} '{}'".format(SRSRAN_DEPLOY_SCRIPT, srsran_hash)
cudu.addService(pg.Execute(shell="bash", command=cmd))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru1ue 0"))
cudu.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens ru2ue 95"))

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
node_sdr_if.addAddress(pg.IPv4Address("192.168.10.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
uemncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
uemncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/deploy-gnuradio.sh"))
uemncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens uemon 0"))

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
node_sdr_if = rumncmp.addInterface("{}-sdr-if".format(node_name))
node_sdr_if.addAddress(pg.IPv4Address("192.168.10.1", "255.255.255.0"))
sdr_link = request.Link("{}-sdr-link".format(node_name))
sdr_link.bandwidth = 10*1000*1000
sdr_link.addInterface(node_sdr_if)
rumncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/tune-sdr-iface.sh"))
rumncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/deploy-gnuradio.sh"))
rumncmp.addService(pg.Execute(shell="bash", command="/local/repository/bin/update-attens rumon 0"))


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
