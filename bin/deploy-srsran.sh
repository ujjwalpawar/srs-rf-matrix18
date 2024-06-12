set -ex
COMMIT_HASH=$1
BINDIR=`dirname $0`
ETCDIR=/local/repository/etc
source $BINDIR/common.sh

if [ -f $SRCDIR/srs-setup-complete ]; then
  echo "setup already ran; not running again"
  exit 0
fi

# Get the emulab repo
while ! wget -qO - http://repos.emulab.net/emulab.key | sudo apt-key add -
do
  echo Failed to get emulab key, retrying
done

while ! sudo add-apt-repository -y http://repos.emulab.net/powder/ubuntu/
do
  echo Failed to get johnsond ppa, retrying
done

while ! sudo apt-get update
do
  echo Failed to update, retrying
done

sudo apt-get install -y libuhd-dev uhd-host
sudo uhd_images_downloader

sudo apt-get install -y \
  cmake \
  make \
  gcc \
  g++ \
  iperf3 \
  pkg-config \
  libfftw3-dev \
  libmbedtls-dev \
  libsctp-dev \
  libyaml-cpp-dev \
  libgtest-dev \
  ppp

cd $SRCDIR
git clone $SRS_PROJECT_REPO
cd srsRAN_Project
git checkout $COMMIT_HASH
# git apply $ETCDIR/srsran/srsran.patch
mkdir build
cd build
cmake ../
make -j $(nproc)

echo configuring nodeb...
mkdir -p $SRCDIR/etc/srsran
cp -r $ETCDIR/srsran/* $SRCDIR/etc/srsran/
LANIF=`ip r | awk '/192\.168\.1\.0/{print $3}'`
if [ ! -z $LANIF ]; then
  LANIP=`ip r | awk '/192\.168\.1\.0/{print $NF}'`
  echo LAN IFACE is $LANIF IP is $LANIP.. updating nodeb config
  find $SRCDIR/etc/srsran/ -type f -exec sed -i "s/LANIP/$LANIP/" {} \;
  IPLAST=`echo $LANIP | awk -F. '{print $NF}'`
  find $SRCDIR/etc/srsran/ -type f -exec sed -i "s/GNBID/$IPLAST/" {} \;
else
  echo No LAN IFACE.. not updating nodeb config
fi
echo configuring nodeb... done.

sudo cp $SERVICESDIR/srs-gnb.service /etc/systemd/system/srs-gnb.service
sudo cp $SERVICESDIR/srs-gnb-metrics.service /etc/systemd/system/srs-gnb-metrics.service
sudo systemctl daemon-reload
sudo cp $BINDIR/metrics-receiver.py $SRCDIR

touch $SRCDIR/srs-setup-complete
