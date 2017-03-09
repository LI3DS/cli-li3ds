############
micmac_li3ds
############

This project is a toolchain to fill li3ds datastore.

----

=======
Context
=======

The goal of this project is to provide a set of tool for fill li3ds datastore from micmac output files. [Micmac] (https://github.com/micmacIGN/micmac "Micmac's Homepage") is a free open source photogrammetry software tools.

============
Prerequisite
============

In the directory of this repository there is some exemple files from micmac : 
- AutoCal_Foc-12000_Cam-Caml024_20161205a.xml
- blinis_20161205.xml
- blocA_ori-export_023.txt (this file + timestaùmp from image will serve for generating a sbet file)

In addition of this files, there is a json file with the metadata of the mission. For example :

```
[
    {
        "brand": "",
        "description": "Fixed Earth group of referentials, such as EPSG SRIDs",
        "id": 26,
        "model": "",
        "serial_number": "",
        "short_name": "Earth",
        "specifications": {},
        "type": "group"
    }
]
```

This file may contain either a reference to other micmac files or contain a json structure with all the information.



