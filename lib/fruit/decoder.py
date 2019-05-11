from .specification import *
from .logging       import *
from .types         import *
from .utils         import *

import binascii, datetime, codecs

MYPY = False
if MYPY:
    from typing import Optional, Tuple, Union, Dict, Callable, Type

if MYPY:
    unichr = chr
else:
    try:
        unichr
    except NameError:
        unichr = chr

class StrDecoders:
    @staticmethod
    def hex(data): # type: (bytearray) -> StrWithEncoding
        return Hexadecimal(binascii.b2a_hex(data).decode('utf8'))

    @staticmethod
    def bcd(data): # type: (bytearray) -> StrWithEncoding
        return BcdString(StrDecoders.hex(data).translate(HEX2BCD))

    @staticmethod
    def packed(data): # type: (bytearray) -> StrWithEncoding
        return PackedAscii(codecs.decode(data, 'packed_ascii'))

    @staticmethod
    def l1bytes(data): # type: (bytearray) -> StrWithEncoding
        return ProperLatin1String(codecs.decode(data, 'latin1'))

    @staticmethod
    def u16bytes(data): # type: (bytearray) -> StrWithEncoding
        if len(data) % 2 != 0:
            return MisusedLatin1String(codecs.decode(data, 'latin1'))
        else:
            return ProperU16String(codecs.decode(data, 'ucs2le'))

    decoders = None # type: Tuple[Callable[[bytearray], StrWithEncoding], ...]
StrDecoders.decoders = (StrDecoders.hex, StrDecoders.bcd, StrDecoders.packed, StrDecoders.l1bytes)

class DecoderArea(object):
    pos    = None # type: int
    offset = None # type: int
    spec   = None # type: AreaOffset
    def __init__(self, spec, pos, offset): # type: (AreaOffset, int, int) -> None
        self.spec   = spec
        self.pos    = pos
        self.offset = offset

class Decoder(object):
    logger          = None # type: Logger
    entry_decoders  = None # type: Dict[Type[EntrySpec], Callable[[EntrySpec, bytearray], Tuple[int, EntryValue]]]
    area_decoders   = None # type: Dict[Type[AreaSpec], Callable[[AreaSpec, bytearray], Tuple[int, AreaValue]]]
    header_decoders = None # type: Dict[Type[AreaSpec], Callable[[AreaSpec, int, int], Union[None, EntryValue, DecoderArea]]]

    def __init__(self, logger = None): # type: (Optional[Logger]) -> None
        if logger is None:
            self.logger = StdErrLogger()
        else:
            self.logger = logger

        self.entry_decoders = dict()
        self.entry_decoders[Byte]       = self.decode_byte
        self.entry_decoders[Date]       = self.decode_date
        self.entry_decoders[Str]        = self.decode_str
        self.entry_decoders[OemStrList] = self.decode_oem

        self.area_decoders = dict()
        self.area_decoders[InternalUse] = self.decode_internal
        self.area_decoders[InfoTable]   = self.decode_info_table
        self.area_decoders[MultiValue]  = self.decode_multivalue

        self.header_decoders = dict()
        self.header_decoders[AreaByte]   = self.decode_header_byte
        self.header_decoders[AreaOffset] = self.decode_header_area


    def decodererror(self, msg): # type: (str) -> None
        self.logger.decodererror(msg)
    def warning(self, msg): # type: (str) -> None
        self.logger.warning(msg)
    def info(self, msg): # type: (str) -> None
        self.logger.info(msg)

    lang      = None # type: int
    msgprefix = None # type: str

    # Simple decoders are allowed to raise IndexError only by accessing `data`

    def decode_byte(self, spec, data): # type: (EntrySpec, bytearray) -> Tuple[int, EntryValue]
        assert isinstance(spec, Byte)
        val = data[0]
        if (val < spec.minvalue or val > spec.maxvalue):
            self.logger.warning("Byte %s%s has value %d out of bounds" % (self.msgprefix, spec.name, val))
        return 1, val

    def decode_date(self, spec, data): # type: (EntrySpec, bytearray) -> Tuple[int, EntryValue]
        assert isinstance(spec, Date)
        minutes = data[0] + 256 * data[1] + 65536 * data[2]
        epoch   = minutes * 60 + FRU_EPOCH_SEC
        d = datetime.datetime.fromtimestamp(epoch, UTC)
        return 3, d

    def decode_str(self, spec, data): # type: (EntrySpec, bytearray) -> Tuple[int, EntryValue]
        return self.decode_str2(spec, data)

    def decode_str2(self, spec, data): # type: (EntrySpec, bytearray) -> Tuple[int, StrWithEncoding]
        assert isinstance(spec, Str)
        tl = data[0]
        if tl == 0xc1:
            self.warning("%s%s String with length 1 byte found. This is forbidden in specification."
                % (self.msgprefix, spec.name))
        l = tl % (1 << 6)
        t = (tl - l) >> 6
        assert spec.use_lang in (True, False)
        if spec.use_lang and t==3 and self.lang not in (None, 0, 25):
            dec = StrDecoders.u16bytes # type: Callable[[bytearray], StrWithEncoding]
        else:
            try:
                dec = StrDecoders.decoders[t]
            except IndexError:
                raise AssertionError("type out of bounds")
        return l+1, dec(data[1:l+1])

    def decode_oem(self, spec, data): # type: (EntrySpec, bytearray) -> Tuple[int, EntryValue]
        assert isinstance(spec, OemStrList)
        out = [] # type: List[StrValue]
        while len(data):
            l, s = self.decode_str2(U16Str("oem%d" % (len(out)+1)), data)
            data = data[l:]
            out.append(s)
        return len(data), out

    def decode_info_table_inner(self, spec, data): #type: (InfoTable, bytearray) -> OrderedDict[str, EntryValue]
        self.msgprefix = "%s." % (spec.name,)
        pos = 0
        out = OrderedDict() # type: OrderedDict[str, EntryValue]
        self.lang = 0
        for entry in spec.entries:
            decoder = None # type: Optional[Callable[[EntrySpec, bytearray], Tuple[int, EntryValue]]]
            for t, d in self.entry_decoders.items():
                if isinstance(entry, t):
                    decoder = d
                    break
            assert decoder is not None
            try:
                l, v = decoder(entry, data)
            except IndexError:
                raise DecoderError("Entry %s%s overlaps ending byte (0xC1)" % (self.msgprefix, entry.name))
            data = data[l:]
            out[entry.name] = v
            if isinstance(entry, Lang):
                assert isinstance(v, int)
                self.lang = v
        assert len(data) == 0
        self.msgprefix = None # type: ignore
        self.lang = None # type: ignore
        return out

    def decode_area_len(self, spec, data): # type: (AreaSpec, bytearray) -> int
        """ Also checks that first byte is equal to 1 """
        try:
            if data[0] != 1:
                self.decodererror("Table %s has unkown/unsupported version %d" % (spec.name, data[0]))
            l = data[1] * 8
            data[l-1]
        except IndexError:
            raise DecoderError("Premature end of data when parsing table %s" % (spec.name,))
        return l

    def decode_info_table(self, spec, data): # type: (AreaSpec, bytearray) -> Tuple[int, AreaValue]
        assert isinstance(spec, InfoTable)
        l = self.decode_area_len(spec, data)
        data = data[:l]
        if sum(data) % 256 != 0:
            self.decodererror("Invalid check sum for table %s, got %d expected %d" % (spec.name, data[-1], checksum(data[:-1])))

        eot = l - 2
        while eot > 2 and data[eot] != 0xc1:
            if data[eot] != 0:
                self.warning("Table %s, padding at pos %d is nonzero" % (spec.name, eot))
            eot -=1
        if l - eot > 9:
            self.warning("Table %s has %d padding bytes, it should be no more than 7" % (spec.name, l - eot - 2))

        return l, self.decode_info_table_inner(spec, data[2:eot])

    def area_hexdump(self, data): # type: (bytearray) -> Tuple[int, AreaValue]
        ret = binascii.b2a_hex(data).decode('ascii')
        lines = ['hex:'] # type: List[str]
        for i in range(0, len(ret), 64):
            lines.append(ret[i:i+64])
        return len(data), '\n'.join(lines)

    def decode_internal(self, spec, data): # type: (AreaSpec, bytearray) -> Tuple[int, AreaValue]
        assert isinstance(spec, InternalUse)
        l = self.decode_area_len(spec, data)
        return self.area_hexdump(data[:l])

    def decode_multivalue(self, spec, data): # type: (AreaSpec, bytearray) -> Tuple[int, AreaValue]
        self.warning("No decoding of multivalue data is performed, just returning hexdump of remaining data")
        return self.area_hexdump(data)

    def decode_header_byte(self, spec, pos, value): # type: (AreaSpec, int, int) -> Union[None, EntryValue, DecoderArea]
        assert isinstance(spec, AreaByte)
        if spec.value != value:
            msg = "Base header entry header.%s(%d) has wrong value, got %d expected %d" % (spec.name, pos, value, spec.value)
            if spec.mandatory:
                self.decodererror(msg)
            else:
                self.warning(msg)
        if spec.virtual or spec.value == value:
            return None
        else:
            return value

    def decode_header_area(self, spec, pos, value): # type: (AreaSpec, int, int) -> Union[None, EntryValue, DecoderArea]
        assert isinstance(spec, AreaOffset)
        if value:
            return DecoderArea(spec, pos, value * 8)
        else:
            return None

    def decode_header(self, data): # type: (bytearray) -> Tuple[AreaValue, List[DecoderArea], int]
        ret   = OrderedDict() # type: OrderedDict[str, EntryValue]
        areas = [] # type: List[DecoderArea]
        checksum_pos = len(FRU_SPEC)
        try:
            data[checksum_pos]
        except IndexError:
            raise DecoderError("Cannot decode base header, data too short.")
        if sum(data[:checksum_pos+1]) % 256 != 0:
            self.decodererror("Base header has wrong checksum, expected: %d, got: %d"
                % (checksum(data[:checksum_pos]), data[checksum_pos]))

        for i in range(len(FRU_SPEC)):
            area = FRU_SPEC[i]
            decoder = None # type: Optional[Callable[[AreaSpec, int, int], Union[None, EntryValue, DecoderArea]]]
            for t, h in self.header_decoders.items():
                if isinstance(area, t):
                    decoder = h
                    break
            assert decoder is not None
            r = decoder(area, i, data[i])
            if r is None:
                continue
            elif isinstance(r, DecoderArea):
                areas.append(r)
            else:
                ret[area.name] = r

        return ret, areas, checksum_pos + 1

    def decode(self, data): # type: (Union[bytes,bytearray]) -> OrderedDict[str, AreaValue]
        if not isinstance(data, bytearray):
            data = bytearray(data)
        ret = OrderedDict() # type: OrderedDict[str, AreaValue]
        header_data, areas, pos = self.decode_header(data)
        if len(header_data):
            ret["header"] = header_data

        offset_order = [x.offset for x in areas]
        areas.sort(key=lambda x: x.offset)
        if offset_order != [x.offset for x in areas]:
            self.warning("Areas are not ordered as required by specification.")

        prev_area = "header"
        for a in areas:
            spec = a.spec
            if pos > a.offset:
                raise DecoderError("Area '%s' overlaps area %s" % (spec.name, prev_area))
            if pos < a.offset:
                self.warning("Ignoring gap of size %d bytes between areas %s and %s."
                    % (a.offset - pos, prev_area, spec.name))
            decoder = None # type: Optional[Callable[[AreaSpec, bytearray], Tuple[int, AreaValue]]]
            for t, h in self.area_decoders.items():
                if isinstance(spec, t):
                    decoder = h
                    break
            assert decoder is not None
            area_len, area_data = decoder(spec, data[a.offset:])
            pos = a.offset + area_len
            if len(area_data):
                ret[spec.name] = area_data

        nz = [i for i in range(pos, len(data)) if data[i]]
        if len(nz):
            self.warning("Ignoring %d bytes after last area (%d are nonzero)"
                % (len(data) - pos, len(nz)))
        elif (pos < len(data)):
            self.info("Ignoring %d zero bytes after last area"
                % (len(data) - pos, ))
        return ret

def decode(data_in, logger = None): # type: (Union[bytes, bytearray], Optional[Logger]) -> OrderedDict[str, AreaValue]
    d = Decoder(logger)
    return d.decode(data_in)
