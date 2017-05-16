#!/bin/bash

set -e

echo "==================="
echo "| mm2li testsuite |"
echo "==================="
echo "Usage: $0 [--docker] [mm2li options]"
echo "The docker option tries to connect to the newest container on its port 5000, using default password"
echo "Possible docker run --> docker run --rm -ti -p 5000:5000 mbredif/api-li3ds"
echo "Command line parameters (such as -u, -k, -v, --debug...) are forwarded from this script to each test."
echo ""

if [ "$#" != "0" ]; then
	if [ $1 = "--docker" ]
	then
		CONTAINER=`docker ps -lq`
		HOST=`docker inspect -f '{{.NetworkSettings.IPAddress}}' $CONTAINER`
		MM2LIARGS="-u http://$HOST:5000/ -k li3dsli3dsli3dsli3dsli3dsli3ds"
		shift
	fi
fi

set -x #echo on

mm2li import-autocal  $MM2LIARGS $@ data/*-Caml023_20161205a.xml -s Caml023 --transfotree Caml023_20161205a
mm2li import-autocal  $MM2LIARGS $@ data/*-Caml024_20161205a.xml -s Caml024 --transfotree Caml024_20161205a
mm2li import-autocal  $MM2LIARGS $@ data/*-Caml025_20161205a.xml -s Caml025 --transfotree Caml025_20161205a
mm2li import-autocal  $MM2LIARGS $@ data/*-Caml026_20161205a.xml -s Caml026 --transfotree Caml026_20161205a

mm2li import-autocal  $MM2LIARGS $@ data/NewCalibD3X-*.xml -s D3X

mm2li import-blinis   $MM2LIARGS $@ data/blinis_*.xml -s stea --transfotree calib20161205

mm2li import-orimatis $MM2LIARGS $@ data/conic*.ori.xml -s matissensor -I $(pwd)/data

mm2li import-autocal  $MM2LIARGS $@ data/Calib-00.xml --transfotree Calib-00 -s Sensor-00
mm2li import-autocal  $MM2LIARGS $@ data/Cali*.xml

mm2li import-ori      $MM2LIARGS $@ data/Orientation-00.xml -s Sensor-00 --transfotree Ori-00 --intrinsic-transfotree Calib-00
mm2li import-ori      $MM2LIARGS $@ data/Orientation-1.xml -s Sensor-1 --transfotree Ori-1
mm2li import-ori      $MM2LIARGS $@ data/OriFrancesco.xml -s SensorFrancesco --transfotree OriFrancesco
mm2li import-ori      $MM2LIARGS $@ data/TestOri-*.xml -s TestSensor
