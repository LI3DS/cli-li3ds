#!/bin/bash

set -e

echo "==================="
echo "| li3ds testsuite |"
echo "==================="
echo "Usage: $0 [--docker] [li3ds options]"
echo "The docker option tries to connect to the newest container on its port 5000, using default password"
echo "Possible docker run --> docker run --rm -ti -p 5000:5000 mbredif/api-li3ds"
echo "Command line parameters (such as -u, -k, -v, --debug...) are forwarded from this script to each test."
echo ""

if [ "$#" != "0" ]; then
	if [ $1 = "--docker" ]
	then
		CONTAINER=`docker ps -lq`
		HOST=`docker inspect -f '{{.NetworkSettings.IPAddress}}' $CONTAINER`
		li3dsARGS="-u http://$HOST:5000/ -k li3dsli3dsli3dsli3dsli3dsli3ds"
		shift
	fi
fi

set -x #echo on

li3ds import-autocal  $li3dsARGS $@ data/*-Caml023_20161205a.xml -s Caml023 --transfotree Caml023_20161205a
li3ds import-autocal  $li3dsARGS $@ data/*-Caml024_20161205a.xml -s Caml024 --transfotree Caml024_20161205a
li3ds import-autocal  $li3dsARGS $@ data/*-Caml025_20161205a.xml -s Caml025 --transfotree Caml025_20161205a
li3ds import-autocal  $li3dsARGS $@ data/*-Caml026_20161205a.xml -s Caml026 --transfotree Caml026_20161205a

li3ds import-autocal  $li3dsARGS $@ data/NewCalibD3X-*.xml -s D3X

li3ds import-extcalib $li3dsARGS $@ data/blinis_*.xml -s stea --transfotree calib20161205
li3ds import-extcalib $li3dsARGS $@ data/cameraMetaData.json -s stereopolis --transfotree calib201601

li3ds import-orimatis $li3dsARGS $@ 'conic*.ori.xml' -s matissensor -b $(pwd)/data/image -f $(pwd)/data -e .tif

li3ds import-autocal  $li3dsARGS $@ data/Calib-00.xml --transfotree Calib-00 -s Sensor-00
li3ds import-autocal  $li3dsARGS $@ data/Cali*.xml

li3ds import-ori      $li3dsARGS $@ data/Orientation-00.xml -s Sensor-00 --transfotree Ori-00 --intrinsic-transfotree Calib-00
li3ds import-ori      $li3dsARGS $@ data/Orientation-1.xml -s Sensor-1 --transfotree Ori-1
li3ds import-ori      $li3dsARGS $@ data/OriFrancesco.xml -s SensorFrancesco --transfotree OriFrancesco
li3ds import-ori      $li3dsARGS $@ data/TestOri-*.xml -s TestSensor
