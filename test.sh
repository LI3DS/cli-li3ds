#!/bin/sh

echo "# mm2li testsuite #"
echo "Command line parameters (such as -u, -k, -v, --debug...) are forwarded from this script to each test."

mm2li import-autocal  $@ data/AutoCal_Foc-12000_Cam-Caml024_20161205a.xml
mm2li import-autocal  $@ data/AutoCal_Foc-12000_Cam-Caml025_20161205a.xml
mm2li import-autocal  $@ data/AutoCal_Foc-15000_Cam-Caml023_20161205a.xml
mm2li import-autocal  $@ data/AutoCal_Foc-15000_Cam-Caml026_20161205a.xml
mm2li import-autocal  $@ data/Calib-00.xml
mm2li import-autocal  $@ data/Calib-1.xml
mm2li import-autocal  $@ data/CalibFrancesco.xml
mm2li import-autocal  $@ data/NewCalibD3X-mm.xml
mm2li import-autocal  $@ data/NewCalibD3X-pix.xml

mm2li import-blinis   $@ data/blinis_20161205.xml

mm2li import-orimatis $@ data/spheric.ori.xml
mm2li import-orimatis $@ data/conic.ori.xml
mm2li import-orimatis $@ data/conic2.ori.xml
