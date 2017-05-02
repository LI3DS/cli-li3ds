#!/bin/bash

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

mm2li import-autocal  $MM2LIARGS $@ data/AutoCal_Foc-12000_Cam-Caml024_20161205a.xml
mm2li import-autocal  $MM2LIARGS $@ data/AutoCal_Foc-12000_Cam-Caml025_20161205a.xml
mm2li import-autocal  $MM2LIARGS $@ data/AutoCal_Foc-15000_Cam-Caml023_20161205a.xml
mm2li import-autocal  $MM2LIARGS $@ data/AutoCal_Foc-15000_Cam-Caml026_20161205a.xml
mm2li import-autocal  $MM2LIARGS $@ data/Calib-00.xml
mm2li import-autocal  $MM2LIARGS $@ data/Calib-1.xml
mm2li import-autocal  $MM2LIARGS $@ data/CalibFrancesco.xml
mm2li import-autocal  $MM2LIARGS $@ data/NewCalibD3X-mm.xml
mm2li import-autocal  $MM2LIARGS $@ data/NewCalibD3X-pix.xml

mm2li import-blinis   $MM2LIARGS $@ data/blinis_20161205.xml

mm2li import-orimatis $MM2LIARGS $@ data/spheric.ori.xml
mm2li import-orimatis $MM2LIARGS $@ data/conic.ori.xml
mm2li import-orimatis $MM2LIARGS $@ data/conic2.ori.xml

mm2li import-ori      $MM2LIARGS $@ data/Orientation-00.xml
mm2li import-ori      $MM2LIARGS $@ data/Orientation-1.xml
mm2li import-ori      $MM2LIARGS $@ data/OriFrancesco.xml
mm2li import-ori      $MM2LIARGS $@ data/TestOri-1.xml
mm2li import-ori      $MM2LIARGS $@ data/TestOri-2.xml
