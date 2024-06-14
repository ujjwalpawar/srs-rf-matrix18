set -ex
COMMIT_HASH=$1
BINDIR=`dirname $0`
ETCDIR=/local/repository/etc
source $BINDIR/common.sh

if [ -f $SRCDIR/gnuradio-setup-complete ]; then
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

sudo apt-get install -y --no-install-recommends libuhd-dev uhd-host gnuradio
sudo uhd_images_downloader

touch $SRCDIR/gnuradio-setup-complete
