# Notes on the sample data

This page includes a description and notes about the sample data provided in the [data](../data)
directory.

## Sample Dataset

In the [data](data) directory, some sample files from micmac may be found, such as :
- [AutoCal_{?}.xml](data/AutoCal_Foc-12000_Cam-Caml024_20161205a.xml) : intrinsic camera calibrations
- [blinis_{YYYYMMDD?}.xml](data/blinis_20161205.xml) : extrinsic camera-rig calibrations
- [{session.name?}_ori-export_{referential.name?}.txt](data/blocA_ori-export_023.txt) : SFM-estimated camera poses (using micmac/apero). This file should be augmented with image timestamps to generate a trajectory (e.g. as a sbet file)


In addition of these files, a json file could be produced for the metadata of the mission. This json file will contain the references to other micmac files and provide the missing parameters in its json structure.

```
TODO: example
```

## Creation of the Earth sensor

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{compound=true;subgraph%20cluster_earth{rankdir=LR;label="Earth";"..."[shape=box];ECEF[shape=box];Lambert93[shape=box];}})

If not done already, it's necessary to create a sensor group that will regroup all the earth-fixed referentials (together with there postgis srid code).

```
{
    -- "id" : [server generated],
    "short_name": "Earth",
    "description": "Fixed Earth group of referentials, such as EPSG SRIDs",
    "type": "group"
    "brand": "",
    "model": "",
    "serial_number": "",
    "specifications": {},
}
```

## Intrinsic Camera Calibration
Example Calib XML file : data/AutoCal_Foc-12000_Cam-Caml024_20161205a.xml

### Creating a Camera Sensor

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{compound=true;subgraph%20cluster_sensor{rankdir=LR;label="Camera";rawImage[shape=box,color=red];idealImage[shape=box];euclidean[shape=box];}})

1 camera sensor needs to be created :
```
{
    "short_name": "{cmdline.sensor_name else {calib_file_basename}}", -- maybe only the relevant substring of {calib_file_basename}
    "description": "camera sensor, imported from {calib_file_basename}",
    "type": "camera"
    "brand": "{cmdline.brand}",
    "model": "{cmdline.model}",
    "serial_number": "{cmdline.serial_number}",
    "specifications": {
      "size" : [{<ExportAPERO/CalibrationInternConique/SzIm>}],
      {cmdline.specifications}
    }
}
```

3 referentials need to be created :
- the `euclidean` external referential : the camera node is at the origin, and it is oriented with +Z in front of the camera (the optical axis), +X to the right of the camera and +Y to the bottom of the camera.
- the `idealImage` frame : X and Y are the raster coordinates in pixels that would used to lookup the pixel values if the camera were an ideal pinhole camera, Z is the inverse depth (measured along the optical axis).
- the `rawImage` frame : X and Y are the raster coordinates in pixels used to lookup the pixel values, Z is the inverse depth (measured along the optical axis).
```
[
  {
    "name": "euclidean",
    "description": "origin: camera position, +X: right of the camera, +Y: bottom of the camera, +Z: optical axis (in front of the camera), imported from {calib_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
  },
  {
    "name": "idealImage",
    "description": "origin: top left corner of top left pixel, +XY: raster pixel coordinates , +Z: inverse depth (measured along the optical axis), imported from {calib_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
  },
  {
    "name": "rawImage",
    "description": "origin: top left corner of top left pixel, +XY: raster pixel coordinates , +Z: inverse depth (measured along the optical axis), imported from {calib_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
  }
]  
```

### Creating the Transfo-Tree of a Camera Calibration
(given an pre-existing camera sensor created by a similar calib file)

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor{label="Camera";euclidean[shape=box];idealImage[shape=box];rawImage[shape=box;color=red];{rank=same;euclidean%20idealImage%20rawImage}subgraph%20cluster_transfotree{label="TransfoTree%20:%20AutoCal_Foc-12000_Cam-Caml024_20161205a.xml";projection;distortion;}euclidean->projection->idealImage;idealImage->distortion->rawImage;}})

2 transforms need to be created :
- `euclidean -> idealImage` Projective Pinhole Transform : the principal point is given by the XML node `PP`, and the focal by the XML node `F`. This is a perspective transform given by the 4x4 matrix:
```
F, 0, PP[0], 0
0, F, PP[1], 0
0, 0, 0, 1
0, 0, 1, 0
```
- `idealImage -> rawImage` Distortion Transform : distortion type and parameters are in `CalibDistortion` (see [micmac documentation](https://github.com/micmacIGN/Documentation/blob/master/DocMicMac.pdf))


```
[
  {
    "description": "projection", -- should be a name
    "parameters": {
        "focal": <ExportAPERO/CalibrationInternConique/F>
        "ppa"  : [<ExportAPERO/CalibrationInternConique/PP>]
    },
    "source": {euclidean.id},
    "target": {idealImage.id},
    "transfo_type": {transfo_type["pinhole"].id},
    "tdate": {cmdline.tdate else undefined},
    "validity_start": {cmdline.validity_start else undefined},
    "validity_end": {cmdline.validity_end else undefined}
  },
  {
    "description": "distortion", -- should be a name
    "parameters": {
        {extracted from <ExportAPERO/CalibrationInternConique/CalibDistortion/ModUnif/Params> according to transfo_type}
    },
    "source": {idealImage.id},
    "target": {rawImage.id},
    "transfo_type": {transfo_type["<ExportAPERO/CalibrationInternConique/CalibDistortion/ModUnif/TypeModele>"].id},
    "tdate": {cmdline.tdate else undefined},
    "validity_start": {cmdline.validity_start else undefined},
    "validity_end": {cmdline.validity_end else undefined}
  }
]
```
As a note, `<ExportAPERO/CalibrationInternConique/KnownConv>` and `<ExportAPERO/CalibrationInternConique/RayonUtile>` are, maybe mistakenly, not currently taken into account.

A transfo tree may now be created to regroup these two transforms :
```
{
    "name": "{cmdline.transfotree_name else {calib_file_basename}}", -- maybe only the relevant substring of {calib_file_basename}
    "owner": "{cmdline.owner else {unix username}}",
    "sensor": "{sensor.id}",
    "transfos": [{projection.id}, {distortion.id}]
}
```

## Sensor Group Calibration
Example Blini XML file : data/blinis_20161205.xml

### Creating a Sensor Group

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{compound=true;subgraph%20cluster_sensor{rankdir=LR;label="Group";026[shape=box];025[shape=box];024[shape=box];023[shape=box];base[shape=box,color=red];}})

1 sensor group needs to be created :
```
{
    "short_name": "{cmdline.sensor_name else <StructBlockCam/KeyIm2TimeCam>}",
    "description": "sensor group, imported from {blinis_file_basename}",
    "type": "group"
    "brand": "",
    "model": "",
    "serial_number": "",
    "specifications": {},
}
```

N+1 referentials need to be created :
- 1 is the base referential
```
{
    "name": "base",
    "description": "referential for sensor group {sensor.id}, imported from {blinis_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
}
```
- 1 for each of the N XML nodes `ParamOrientSHC` should create a referential , named using `ParamOrientSHC/IdGrp`
```
{
    "name": "{<StructBlockCam/LiaisonsSHC/ParamOrientSHC/IdGrp>}",
    "description": "referential for sensor group {sensor.id}, imported from {blinis_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
}
```

### Creating the Transfo-Tree of a Sensor Group Calibration
(given an pre-existing sensor group created by a similar blini file)

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor{label="Group";026[shape=box];025[shape=box];024[shape=box];023[shape=box];base[shape=box;color=red];subgraph%20cluster_transfotree{label="TransfoTree%20:%20blinis_20161205.xml";affine026;affine025;affine024;affine023;}}base->affine026->026;base->affine025->025;base->affine024->024;base->affine023->023;})

N `affine` transforms need to be created, linking the base referential to each of the camera position referentials through a 4x3 matrix :
- The translation part is given by `ParamOrientSHC/Vecteur`
- The linear part, which happen to be a rotation, is given by `ParamOrientSHC/Rot`

```
{
    "description": "Affine_{<StructBlockCam/LiaisonsSHC/ParamOrientSHC/IdGrp>}",
    "parameters": {
        "mat4x3": [ -- comma-separated values (FIXME: ordering of values)
            {<StructBlockCam/LiaisonsSHC/ParamOrientSHC/Rot/L1>}
            {<StructBlockCam/LiaisonsSHC/ParamOrientSHC/Rot/L2>}
            {<StructBlockCam/LiaisonsSHC/ParamOrientSHC/Rot/L3>}
            {<StructBlockCam/LiaisonsSHC/ParamOrientSHC/Vecteur>}
        ]
    },
    "source": {base_referential.id},
    "target": {IdGrp_referential.id},
    "transfo_type": {transfo_type["affine"].id},
    "tdate": {cmdline.tdate else undefined},
    "validity_start": {cmdline.validity_start else undefined},
    "validity_end": {cmdline.validity_end else undefined}
}
```

A transfo tree may now be created to regroup all these transforms :
```
{
    "name": "{cmdline.transfotree_name else {blinis_file_basename}}",
    "owner": "{cmdline.owner else {unix username}}",
    "sensor": "{sensor.id}",
    "transfos": {array of the N newly-created transfo ids}
}
```


## Orientation of a single image
Example Image orientation XML files :
- https://github.com/micmacIGN/Documentation/blob/master/FilesSamples/OriFrancesco.xml
- https://github.com/micmacIGN/Documentation/blob/master/FilesSamples/Orientation-00.xml
- https://github.com/micmacIGN/Documentation/blob/master/FilesSamples/Orientation-1.xml
- https://github.com/micmacIGN/Documentation/blob/master/FilesSamples/TestOri-1.xml
- https://github.com/micmacIGN/Documentation/blob/master/FilesSamples/TestOri-2.xml

(`<ExportAPERO/OrientationConique/ConvOri/KnownConv>` is, surely mistakenly, not taken into account)

### Creating the Intrinsic Group and transfo trees
The internal calibration is either given in line in the XML node `<ExportAPERO/OrientationConique/Interne>` or as an external file given by `<ExportAPERO/OrientationConique/FileInterne>` ( `<ExportAPERO/OrientationConique/RelativeNameFI>` indicating if the path is relative or absolute). Importing it is described above in "Intrinsic Camera Calibration".


### Creating the Extrinsic Group
This group encodes the extrinsic calibration (a.k.a. pose, trajectory...)

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{compound=true;subgraph%20cluster_sensor{rankdir=LR;label="Extrinsic";camera[shape=box];world[shape=box,color=red];}})

1 sensor group needs to be created :
```
{
    "short_name": "{cmdline.sensor_name} else extrinsic_{xml_file_basename}",
    "description": "sensor group, imported from {xml_file_basename}",
    "type": "group"
    "brand": "",
    "model": "",
    "serial_number": "",
    "specifications": {},
}
```

2 referentials need to be created :
```
{
    "name": "world",
    "description": "world referential, imported from {xml_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
}
```
```
{
    "name": "camera",
    "description": "camera referential, imported from {xml_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
}
```

### Creating the image Group

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{compound=true;subgraph%20cluster_sensor{rankdir=LR;label="Image";full[shape=box];crop[shape=box,color=red];}})

1 sensor group needs to be created :
```
{
    "short_name": "{cmdline.sensor_name} else image_{xml_file_basename}",
    "description": "sensor group, imported from {xml_file_basename}",
    "type": "group"
    "brand": "",
    "model": "",
    "serial_number": "",
    "specifications": {},
}
```

2 referentials need to be created :
```
{
    "name": "full",
    "description": "full image referential, imported from {xml_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
}
```
```
{
    "name": "crop",
    "description": "cropped image referential, imported from {xml_file_basename}",
    "sensor": {sensor.id},
    "srid": 0,
}
```

### Creating the Transfo-Tree of the Extrinsic Group
(given a pre-existing sensor group created by a similar orientation file)

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor{label="Extrinsic";camera[shape=box];world[shape=box;color=red];subgraph%20cluster_transfotree{label="TransfoTree";pose;}}world->pose->camera;})

1 `affine` transform needs to be created, linking the world referential to the camera referential through a 4x3 matrix :
- The translation part is given by `<ExportAPERO/OrientationConique/Externe/Centre>`
- The linear part, which happens to be a rotation, is given by `<ExportAPERO/OrientationConique/Externe/ParamRotation>`

```
{
    "description": "pose_{xml_file_basename}",
    "parameters": {
        "mat4x3": [ -- comma-separated values (FIXME: ordering of values)
            {<ExportAPERO/OrientationConique/Externe/ParamRotation/CodageMatr/L1>}
            {<ExportAPERO/OrientationConique/Externe/ParamRotation/CodageMatr/L2>}
            {<ExportAPERO/OrientationConique/Externe/ParamRotation/CodageMatr/L3>}
            {<ExportAPERO/OrientationConique/Externe/Centre>}
        ]
    },
    "source": {<ExportAPERO/OrientationConique/Externe/KnownConv>==eConvApero_DistM2C ? camera_referential.id : world_referential.id},
    "target": {<ExportAPERO/OrientationConique/Externe/KnownConv>==eConvApero_DistM2C ? world_referential.id : camera_referential.id},
    "transfo_type": {transfo_type["affine"].id},
    "tdate": {cmdline.tdate else undefined},
    "validity_start": {cmdline.validity_start else undefined},
    "validity_end": {cmdline.validity_end else undefined}
}
```

A transfo tree may now be created to regroup this single transform :
```
{
    "name": "{cmdline.transfotree_name else pose_{xml_file_basename}}",
    "owner": "{cmdline.owner else {unix username}}",
    "sensor": "{sensor.id}"
    "transfos": [ {pose_transfo.id} ]
}
```

### Creating the Transfo-Tree of an image Group
(given a pre-existing sensor group created by a similar orientation file)

![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{rankdir=LR;compound=true;subgraph%20cluster_sensor{label="Image";full[shape=box];crop[shape=box;color=red];subgraph%20cluster_transfotree{label="TransfoTree";affine;}full->affine->crop;}})

1 2D `affine` transform needs to be created, linking the world referential to the camera referential through a 3x2 matrix, using `<ExportAPERO/OrientationConique/OrIntImaM2C>` values :
```
{
    "description": "crop_{xml_file_basename}",
    "parameters": {
        "mat3x2": [ -- comma-separated values (FIXME: ordering of values)
            {<ExportAPERO/OrientationConique/OrIntImaM2C/V10>}
            {<ExportAPERO/OrientationConique/OrIntImaM2C/V01>}
            {<ExportAPERO/OrientationConique/OrIntImaM2C/I00>}
        ]
    },
    "source": {full_referential.id},
    "target": {crop_referential.id},
    "transfo_type": {transfo_type["affine2"].id},
    "tdate": {cmdline.tdate else undefined},
    "validity_start": {cmdline.validity_start else undefined},
    "validity_end": {cmdline.validity_end else undefined}
}
```

A transfo tree may now be created to regroup this single transform :
```
{
    "name": "{cmdline.transfotree_name else crop_{xml_file_basename}}",
    "owner": "{cmdline.owner else {unix username}}",
    "sensor": null,
    "transfos": [ {pose_transfo.id} ]
}
```

### Creating the Transfo-Tree connecting these sensors
![XML Calib graph](https://g.gravizo.com/g?digraph%20G%20{compound=true;subgraph%20cluster_sensors{subgraph%20cluster_crop{label="Image";crop[shape=box;color=red];full[shape=box];}subgraph%20cluster_intrinsic{label="Intrinsic";euclidean[shape=box];rawImage[shape=box;color=red];}subgraph%20cluster_extrinsic{label="Extrinsic";camera[shape=box];world[shape=box;color=red];}}subgraph%20cluster_tf{label="TransfoTree";camera->connection1->euclidean;rawImage->connection2->full;})

This introduces 2 transforms and a transfo tree
```
{
    "description": "Extrinsic2Intrinsic",
    "parameters": {},
    "source": {Extrinsic/camera_referential.id},
    "target": {Intrinsic/euclidean_referential.id},
    "transfo_type": {transfo_type["identity"].id},
    "tdate": {cmdline.tdate else undefined},
    "validity_start": {cmdline.validity_start else undefined},
    "validity_end": {cmdline.validity_end else undefined}
}
```

```
{
    "description": "Intrinsic2Image",
    "parameters": {},
    "source": {Intrinsic/rawImage_referential.id},
    "target": {Image/full_referential.id},
    "transfo_type": {transfo_type["identity"].id},
    "tdate": {cmdline.tdate else undefined},
    "validity_start": {cmdline.validity_start else undefined},
    "validity_end": {cmdline.validity_end else undefined}
}
```

```
{
    "name": "{cmdline.transfotree_name else connection_{xml_file_basename}}",
    "owner": "{cmdline.owner else {unix username}}",
    "sensor": null,
    "transfos": [ {Extrinsic2Intrinsic.id} , {Intrinsic2Image.id} }
}
```

## TODO : platform, config ...
may be guided by a XML [chantierDescripteur](https://github.com/micmacIGN/Documentation/blob/master/Data/Arbre/MicMac-LocalChantierDescripteur.xml) or an XML [APERO](https://github.com/micmacIGN/Documentation/blob/master/FilesSamples/Test-NewApero-mm.xml) file. To be discussed...
