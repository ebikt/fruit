FruIt
=====

Library for encoding and decoding IPMI FRU information. (MultiValue not supported.)

Also bidirectional convertor between IPMI FRU binary format and enhanced Toml representation is included.

Tested only with SuperMicro servers.

Synopsis
--------

```
ipmitool fru read 0 fru-orig.bin
./fruit fru-orig.bin fru.toml
$EDITOR fru.toml
./fruit fru.toml fru-new.bin
ipmitool fru write 0 fru-new.bin
```


Usage
-----

  ./fruit [INPUTFILE [OUTPUTFILE]]

If OUTPUTFILE is not specified, fru2yml outputs to stdout (with refusing to write binary data to terminal).
If INPUTFILE is also not specified then fru2yml reads input from stdin.

If input file starts with byte "\x01" then conversion from binary to toml is performed. Otherwise conversion from toml to binary is performed.

FruIt can be also used as library.
```
  from fruit import decode, encode
  # fruit.Val = Union[str, int, List[str], None]
  fruit.decode(data_in: bytes) -> Dict[str, Dict[str, fruit.Val]]
  fruit.encode(cfg: Dict[str, Dict[str, fruit.Val]]) -> bytes
```

Note that importing fruit registers two new codecs: `ucs2le` and `packed_ascii`.

Toml enhancement
----------------
We enhanced our TOML decoder and encoder by typed strings:

 * `h""` - content must be hex digits and endoced as FRU text type 0: hexadecimal
 * `b""` - content consist only from digits, minus, dot and space and it is encoded as FRU text type 1: bcd-text
 * `p""` - content must be of ascii characters between 32(space) and 95(underscore). Lowercase characters are automatically uppercased. Encoding type 2: packed-ascii is used.
 * `a""` - content must be ascii+latin1 and it is encoded as type 3 using ASCII+LATIN1 encoding even if specification expects 16-bit unicode.
 * `u""` - content is unicode with codepoints less than 65536, i.e., BMP + codepoints reserved for surrogate pairs. It is encoded as type 3 using 16-bit unicode encoding even if specification expects ASCII+LATIN1.

When decoding odd number of characters when specification says 16-bit unicode, then `a""` string is returned.

TODO
----
 * Decode and encode MultiValue entries (various PSU information, etc.).
 * Test on various hardware and recover from exiting violations of specification. Better guess correct encoding in case of specification violation.
 * Decode and encode enumerations (languages and chassis types)
 * Add `setup.py`

Note: Specification is not consistent with itself, e.g. when specifying encoding of board and product fru. Using language 0 (English) is recommended (that turns off completely 16bit unicode).

External resources
------------------

IPMI FRU specification:
https://www.intel.com/content/dam/www/public/us/en/documents/specification-updates/ipmi-platform-mgt-fru-info-storage-def-v1-0-rev-1-3-spec-update.pdf

SMBIOS specification (list of chassis types): https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.0.0.pdf
