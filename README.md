FruIt
=====

Bidirectional convertor between IPMI FRU binary format and Yaml representation.

Currently supports only subset of IPMI specification, suitable for dealing with SuperMicro MicroCloud servers.

Synopsis
--------

```
ipmitool fru read 0 fru-orig.bin
./fruit.py fru-orig.bin fru.yaml
$EDITOR fru.yaml
./fruit.py fru.yaml fru-new.bin
ipmitool fru write 0 fru-new.bin
```


Usage
-----

  ./fruit.py [INPUTFILE [OUTPUTFILE]]

If OUTPUTFILE is not specified, fru2yml outputs to stdout (with refusing to write binary data to terminal).
If INPUTFILE is also not specified then fru2yml reads input from stdin.

If input file starts with byte "\x01" then conversion from binary to yaml is performed. Otherwise conversion from yaml to binary is performed.

FruIt can be also used as library.
```
  # fruit.Val = Union[str, int, List[str], None]
  fruit.decode(data_in: bytes) -> Dict[str, Dict[str, fruit.Val]]
  fruit.encode(cfg: Dict[str, Dict[str, fruit.Val]]) -> bytes
```

External sources
----------------

IPMI FRU specification:
https://www.intel.com/content/dam/www/public/us/en/documents/specification-updates/ipmi-platform-mgt-fru-info-storage-def-v1-0-rev-1-3-spec-update.pdf

SMBIOS specification (list of chassis types): https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.0.0.pdf

