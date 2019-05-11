MYPY=False
if MYPY:
    from typing import Tuple

# {{{ Specification types
class EntrySpec(object):
    """ Scalar values in FRU specification. """
    name = None # type: str
    def __init__(self, name): # type: (str) -> None
        self.name = name

class Byte(EntrySpec):
    """ Single byte value - enumeration with limits. """
    minvalue = None # type: int
    maxvalue = None # type: int
    default  = None # type: int

class ChassisType(Byte):
    # Chassis type, see SMBIOS specification
    minvalue = 1
    maxvalue = 32
    default  = 2

class Lang(Byte):
    minvalue = 0
    maxvalue = 136
    default  = 0

class Date(EntrySpec):
    """ Date value (encoded as 3 bytes: numbers since 1996-01-01T00:00:00Z) """
    pass

class Str(EntrySpec):
    """ String value. Encoded as latin1 string or 16-bit unicode. """
    use_lang = None # type: bool

class L1Str(Str):
    """ String value, encoded as latin1 string. """
    use_lang = False

class U16Str(Str):
    """ String value, encoded as 16-bit unicode when lang is not English. """
    use_lang = True

class OemStrList(EntrySpec):
    """ List of Str (U16Str). """
    pass

class AreaSpec(object):
    name       = None # type: str
    def __init__(self, name): # type: (str) -> None
        self.name = name

class AreaByte(AreaSpec):
    value     = None # type: int
    mandatory = None # type: bool
    virtual   = None # type: bool
    def __init__(self, name, value, mandatory, virtual): # type: (str, int, bool, bool) -> None
        super(AreaByte, self).__init__(name)
        self.value     = value
        self.mandatory = mandatory
        self.virtual   = virtual

class AreaOffset(AreaSpec):
    pass

class InternalUse(AreaOffset):
    pass

class InfoTable(AreaOffset):
    entries    = None # type: Tuple[EntrySpec, ...]
    def __init__(self, name, entries): # type: (str, Tuple[EntrySpec, ...]) -> None
        super(InfoTable, self).__init__(name)
        self.entries = entries

class MultiValue(AreaOffset):
    pass


FRU_EPOCH_SEC = 820454400 # 1996-01-01 00:00 UTC
# }}}

FRU_SPEC = (
        AreaByte("version", 1, True, True),
        InternalUse("internal"),
        InfoTable("chassis", (
            ChassisType("type"),
            L1Str("partno"), #U16Str by spec, but there is no lang, thus English will be used anyways
            L1Str("serial"),
            OemStrList("oem"),
        )),
        InfoTable("board", (
            Lang("lang"),
            Date("date"),
            U16Str("manufacturer"),
            U16Str("product"),
            L1Str("serial"),
            U16Str("partno"),
            L1Str("fru"), # This disagrees with spec for chassis.fru, which is U16Str
            OemStrList("oem"),
        )),
        InfoTable("product", (
            Lang("lang"),
            U16Str("manufacturer"),
            U16Str("name"),
            U16Str("model"),
            U16Str("version"),
            L1Str("serial"),
            U16Str("asset"),
            U16Str("fru"), # This disagrees with spec for board.fru, which is L1Str
            OemStrList("oem"),
        )),
        MultiValue("multi"),
        AreaByte("padding", 0, False, False),
    ) # type: Tuple[AreaSpec, ...]

assert (len(FRU_SPEC) + 1) % 8 == 0

HEX2BCD={
    ord('a'): ord(' '),
    ord('b'): ord('-'),
    ord('c'): ord('.'),
    ord('d'): 0x24B9, # d in circle
    ord('e'): 0x24BA, # e in circle
    ord('f'): 0x24BB, # f in circle
}

BCD2HEX = { v:k for k, v in HEX2BCD.items() }
BCD2HEX.update( { (ord('a') + x):(0x24B9 + x) for x in range(6) } ) #Disable a-f letters
BCD2HEX.update( { (ord('A') + x):(0x24B9 + x) for x in range(6) } ) #Disable A-F letters
