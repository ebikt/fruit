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
    """ Chasis type, see SMBIOS specification for meaning of values. """
    minvalue = 1
    maxvalue = 32
    default  = 2

class Lang(Byte):
    """ Language, see IPMI FRU specification for meaning of values.
        Values 0 and 25 are English, no 16-bit unicode is used. Other
        languages has some entries encoded in 16-bit unicode. """
    minvalue = 0
    maxvalue = 136
    default  = 0

class Date(EntrySpec):
    """ Date value (encoded as 3 bytes: minutes since 1996-01-01T00:00:00Z) """
    pass

class Str(EntrySpec):
    """ String value. Encoded as 8-bit latin1 string or 16-bit unicode. """
    use_lang = None # type: bool

class L1Str(Str):
    """ String value, encoded as 8-bit latin1 string. """
    use_lang = False

class U16Str(Str):
    """ String value, encoded as 16-bit unicode when lang is not English. """
    use_lang = True

class OemStrList(EntrySpec):
    """ List of U16Str. (Specification is not clear if latin1 or 16bit unicode
        should be used. We should provide some better heuristics when decoding.) """
    pass

class AreaSpec(object):
    """ FRU Header entry base class """
    name       = None # type: str
    def __init__(self, name): # type: (str) -> None
        self.name = name

class AreaByte(AreaSpec):
    """ FRU Header entry that is not area offset. """
    value     = None # type: int
    mandatory = None # type: bool
    virtual   = None # type: bool
    def __init__(self, name, value, mandatory, virtual): # type: (str, int, bool, bool) -> None
        super(AreaByte, self).__init__(name)
        self.value     = value
        self.mandatory = mandatory
        self.virtual   = virtual

class AreaOffset(AreaSpec):
    """ Area base class. This FRU Header entry is interpreted as offset. """
    pass

class InternalUse(AreaOffset):
    """ Internal Use Area. This starts with two byte header, rest is not interpreted. """
    pass

class InfoTable(AreaOffset):
    """ Area with information about chassis, board or product. I.e., area with predefined entries. """
    entries    = None # type: Tuple[EntrySpec, ...]
    def __init__(self, name, entries): # type: (str, Tuple[EntrySpec, ...]) -> None
        super(InfoTable, self).__init__(name)
        self.entries = entries

class MultiValue(AreaOffset):
    """ Multi-value area. Currently no decoding is implemented. """
    pass


FRU_EPOCH_SEC = 820454400 # 1996-01-01 00:00 UTC
# }}}

""" FRU Specification. """
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

""" FRU bcd encoding """
HEX2BCD={
    ord('a'): ord(' '),
    ord('b'): ord('-'),
    ord('c'): ord('.'),
    # Following digits are defined to allow decoding of invalid bcd values unambiguously (so we can encode such value to original bytes.)
    ord('d'): 0x24B9, # d in circle
    ord('e'): 0x24BA, # e in circle
    ord('f'): 0x24BB, # f in circle
}

# BCD2HEX: Map everything of HEX2BCD in reverse
BCD2HEX = { v:k for k, v in HEX2BCD.items() }
# BCD2HEX: effectively disable a-f letters
BCD2HEX.update( { (ord('a') + x):(0x24B9 + x) for x in range(6) } )
# BCD2HEX: effectively disable A-F letters
BCD2HEX.update( { (ord('A') + x):(0x24B9 + x) for x in range(6) } )
