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

li3ds import-autocal  $li3dsARGS $@ data/AutoCal_Foc-12000_Cam-Caml024_20161205a.xml
li3ds import-autocal  $li3dsARGS $@ data/AutoCal_Foc-12000_Cam-Caml025_20161205a.xml
li3ds import-autocal  $li3dsARGS $@ data/AutoCal_Foc-15000_Cam-Caml023_20161205a.xml
li3ds import-autocal  $li3dsARGS $@ data/AutoCal_Foc-15000_Cam-Caml026_20161205a.xml
li3ds import-autocal  $li3dsARGS $@ data/Calib-00.xml
li3ds import-autocal  $li3dsARGS $@ data/Calib-1.xml
li3ds import-autocal  $li3dsARGS $@ data/CalibFrancesco.xml
li3ds import-autocal  $li3dsARGS $@ data/NewCalibD3X-mm.xml
li3ds import-autocal  $li3dsARGS $@ data/NewCalibD3X-pix.xml

li3ds import-extcalib $li3dsARGS $@ data/blinis_20161205.xml data/cameraMetaData.json

li3ds import-orimatis $li3dsARGS $@ --sensor Sensor0 -b $(pwd)/data/image -f $(pwd)/data  -e .tif spheric.ori.xml
li3ds import-orimatis $li3dsARGS $@ -b $(pwd)/data/image -f $(pwd)/data -e .tif 'conic*.ori.xml'

li3ds import-ori      $li3dsARGS $@ data/Orientation-00.xml
li3ds import-ori      $li3dsARGS $@ data/Orientation-1.xml
li3ds import-ori      $li3dsARGS $@ data/OriFrancesco.xml
li3ds import-ori      $li3dsARGS $@ data/TestOri-1.xml
li3ds import-ori      $li3dsARGS $@ data/TestOri-2.xml
