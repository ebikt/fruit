from .specification import *
from .logging       import *
from .types         import *
from .utils         import *

__all__ = [ "Encoder", "encode" ]

import binascii, datetime, codecs

MYPY = False
if MYPY:
    from typing import Optional, Tuple, Union, List, Type, Callable

if MYPY:
    unichr = chr
else:
    try:
        unichr
    except NameError:
        unichr = chr

class StrEncoders: # {{{
    """ Encodes into various FRU string representations. """
    @staticmethod
    def hex(text): # type: (unicode)->Tuple[int, bytes]
        return 0, binascii.a2b_hex(text)

    @staticmethod
    def bcd(text): # type: (unicode)->Tuple[int, bytes]
        return 1, binascii.a2b_hex(text.translate(BCD2HEX))

    @staticmethod
    def packed(text): # type: (unicode)->Tuple[int, bytes]
        return 2, codecs.encode(text.upper(), 'packed_ascii')

    @staticmethod
    def latin1(text): # type: (unicode)->Tuple[int, bytes]
        return 3, codecs.encode(text, 'latin1')

    @staticmethod
    def ucs2le(text): # type: (unicode)->Tuple[int, bytes]
        return 3, codecs.encode(text, 'ucs2le')

    @classmethod
    def getencoder(cls, text): # type: (str)->Callable[[unicode],Tuple[int, bytes]]
        return getattr(cls, text) # type: ignore
# }}}

class EncoderArea(object): # {{{
    """ Area with header position. """
    pos    = None # type: int
    spec   = None # type: AreaOffset
    def __init__(self, spec, pos): # type: (AreaOffset, int) -> None
        self.spec   = spec
        self.pos    = pos
# }}}

import re
def nowhite(s): # type: (unicode) -> unicode
    return re.sub(u"\\s", u"", s)

class Encoder(object):
    """ IPMI FRU Encoder """
    logger         = None # type: Logger

    # {{{ initialisation
    entry_encoders = None # type: Dict[Type[EntrySpec], Callable[[EntrySpec, Optional[EntryValue]], bytearray]]

    def __init__(self, logger = None): # type: (Optional[Logger]) -> None
        if logger is None:
            self.logger = StdErrLogger()
        else:
            self.logger = logger

        self.entry_encoders = {}
        self.entry_encoders[ChassisType]=self.encode_byte
        self.entry_encoders[Lang]=self.encode_lang
        self.entry_encoders[Date]=self.encode_date
        self.entry_encoders[L1Str]=self.encode_l1str
        self.entry_encoders[U16Str]=self.encode_u16str
        self.entry_encoders[OemStrList]=self.encode_oem

    lang      = None # type: int
    msgprefix = None # type: str
    # }}}

    # {{{ entry encoders
    def encode_byte(self, spec, cfg): # type: (EntrySpec, Optional[EntryValue]) -> bytearray
        assert isinstance(spec, Byte)
        if cfg is None:
            cfg = spec.default
        if not isinstance(cfg, int) or cfg not in range(256):
            raise EncoderError("%s.%s: only integers in range(256) allowed"
                % (self.msgprefix, spec.name))
        if cfg < spec.minvalue or cfg > spec.maxvalue:
            self.logger.warning("%s.%s: value %s out of bounds (%d, %d)"
                % (self.msgprefix, spec.name, cfg, spec.minvalue, spec.maxvalue))
        return bytearray([cfg])

    def encode_lang(self, spec, cfg): # type: (EntrySpec, Optional[EntryValue]) -> bytearray
        assert isinstance(spec, Lang)
        ret = self.encode_byte(spec, cfg)
        self.lang = ret[0]
        return ret

    FRU_EPOCH = datetime.datetime.fromtimestamp(FRU_EPOCH_SEC, UTC)

    def encode_date(self, spec, cfg): # type: (EntrySpec, Optional[EntryValue]) -> bytearray
        if cfg is None:
            dt = 0
        elif isinstance(cfg, datetime.datetime):
            if cfg.tzinfo is None:
                cfg = cfg.replace(tzinfo=UTC)
            dt = int(round((cfg - self.FRU_EPOCH).total_seconds()/60))
        elif isinstance(cfg, int):
            dt = cfg
        else:
            raise EncoderError("%s.%s: expected date (or integer) got type %s"
                % (self.msgprefix, spec.name, type(cfg).__name__))
        if dt < 0:
            raise EncoderError("%s.%s: date too low (%s is minimum), got %r"
                % (self.msgprefix, spec.name,
                    self.FRU_EPOCH.isoformat(), cfg))
        if dt >= (1 << 24):
            raise EncoderError("%s.%s: date too high (%s is mmaximum), got %r"
                % (self.msgprefix, spec.name,
                    datetime.datetime.fromtimestamp(FRU_EPOCH_SEC + (1<<24)*60 - 1, UTC),
                    cfg))
        ret = bytearray()
        for i in range(3):
            ret.append(dt % 256)
            dt = dt >> 8
        return ret

    def encode_str(self, spec, cfg, lang): # type: (EntrySpec, Optional[EntryValue], int) -> bytearray
        if cfg is None:
            cfg = u""
        english = lang in (None, 0, 25)
        if isinstance(cfg, StrWithEncoding):
            enc = cfg.encoding
            if enc == 'latin1' and not english:
                self.logger.warning("%s.%s: encoding as latin1+ascii, but interpetation will be 16bit unicode"
                    % (self.msgprefix, spec.name))
            if enc == 'ucs2le' and english:
                self.logger.warning("%s.%s: encoding as 16bit unicode, but interpetation will be latin1+ascii"
                    % (self.msgprefix, spec.name))
        else:
            try:
                cfg = unicode(cfg)
            except Exception:
                raise EncoderError("%s.%s: invalid type %s" % (self.msgprefix, spec.name, type(cfg).__name__))
            enc = ['ucs2le', 'latin1'][english]
        try:
            encoder = StrEncoders.getencoder(enc)
        except Exception:
            raise EncoderError("%s.%s: invalid encoding (%s) specified" % (self.msgprefix, spec.name, enc))

        try:
            t, b = encoder(cfg)
        except Exception as e:
            raise EncoderError("%s.%s: cannot encode string with encoding %s: %s"
                % (self.msgprefix, spec.name, enc, e))
        if len(b) > 64:
            raise EncoderError("%s.%s: too many bytes (%d)" % (self.msgprefix, spec.name, len(b)))
        ret = bytearray([(t<<6) + len(b)]) + bytearray(b)
        if ret[0] == 0xc1:
            self.logger.warning("%s.%s: single character string may be mis-interpreted as end of area"
                % (self.msgprefix, spec.name))
        return ret

    def encode_l1str(self, spec, cfg): # type: (EntrySpec, Optional[EntryValue]) -> bytearray
        return self.encode_str(spec, cfg, 0)

    def encode_u16str(self, spec, cfg): # type: (EntrySpec, Optional[EntryValue]) -> bytearray
        return self.encode_str(spec, cfg, self.lang)

    def encode_oem(self, spec, cfg): # type: (EntrySpec, Optional[EntryValue]) -> bytearray
        assert isinstance(spec, OemStrList)
        if cfg is None:
            cfgit = [] # type: List[basestring]
        elif isinstance(cfg, basestring) or not hasattr(cfg, '__iter__'):
            raise EncoderError("%s.%s: expected list of strings, got type %s"
                % (self.msgprefix, spec.name, type(cfg).__name__))
        else:
            cfgit = cfg # type: ignore
        i = 1
        ret = bytearray()
        for s in cfgit:
            ret += self.encode_u16str(U16Str("oem%d" % (i,)), s)
            i += 1
        return ret
    # }}}

    # {{{ area encoders
    def encode_info_table(self, spec, cfg): # type: (AreaOffset, AreaValue) -> bytearray
        assert isinstance(cfg, dict) or isinstance(cfg, OrderedDict)
        assert isinstance(spec, InfoTable)
        self.lang      = None # type: ignore
        self.msgprefix = spec.name
        ret = bytearray([1, 0])
        for entry in spec.entries:
            ret += self.entry_encoders[type(entry)](entry, cfg.get(entry.name, None))
        ret.append(0xc1)
        while len(ret) % 8 != 7:
            ret.append(0)
        ret[1] = div8(len(ret)+1)
        ret.append(checksum(ret))
        self.lang      = None # type: ignore
        self.msgprefix = None # type: ignore
        return ret

    def encode_area_hex(self, spec, cfg, is_last): # type: (AreaOffset, AreaValue, bool) -> bytearray
        if not (isinstance(cfg, basestring)):
            raise EncoderError("%s: unsupported area configuration type %s" % (spec.name, type(cfg).__name__))
        cfg = nowhite(cfg)
        if not unicode(cfg)[:4] == u'hex:':
            raise EncoderError("%s: only hex encoding (string starting with 'hex:') supported" % (spec.name,))
        try:
            b = binascii.a2b_hex(cfg[4:])
        except Exception as e:
            raise EncoderError("%s: failed to interpret hex data: %s" % (spec.name, e))
        ret = bytearray(b)
        if len(ret) == 0:
            return ret
        if isinstance(spec, MultiValue):
            assert is_last
        else:
            if len(ret) % 8 != 0:
                raise EncoderError("%s: hex data must be padded to multiples of 8 bytes")
            if ret[0] != 1:
                self.logger.warning("First byte of area %s should be zero, got %d" % (spec.name, ret[0]))
            if len(ret) != 8 * ret[1]:
                raise EncoderError("%s: second byte must be equal to length/8, expected: %d, got: %d"
                    % (spec.name, div8(len(ret)), ret[1]))
            if isinstance(spec, InfoTable):
                if sum(ret) % 256 != 0:
                    self.logger.warning("%s: checksum mismatch, expected last byte: %d, got %d"
                        % (spec.name, checksum(ret[:-1]), ret[-1]))
                #Note: we should probably also validate content using decoder
        return ret
    # }}}

    # {{{ header encoders
    def prepare_header(self, cfg): # type: (AreaValue) -> Tuple[bytearray, List[EncoderArea]]
        ret = bytearray()
        areas = [] # type List[EncoderArea]
        if not (isinstance(cfg, dict) or isinstance(cfg, OrderedDict)):
            raise EncoderError("header: specification must be a dictionary")
        for i in range(len(FRU_SPEC)):
            area_spec = FRU_SPEC[i]
            if isinstance(area_spec, AreaByte):
                val = area_spec.value
                if not area_spec.virtual:
                    val = cfg.get(area_spec.name, val) # type: ignore
                try:
                    ret.append(val)
                except Exception:
                    raise EncoderError("header.%s: byte value must be integer in range(256)" % (area_spec.name,))
            else:
                assert isinstance(area_spec, AreaOffset)
                areas.append(EncoderArea(area_spec, i))
                ret.append(0)
        ret.append(0) # checksup
        return ret, areas
    # }}}

    def encode(self, cfg): # type: (Union[OrderedDict[str, AreaValue], Dict[str, AreaValue]]) -> bytearray
        ret, areas = self.prepare_header(cfg.get("header", {}))
        i = 0
        for area in areas:
            assert len(ret) % 8 == 0
            try:
                area_cfg = cfg[area.spec.name]
            except Exception:
                continue
            if len(area_cfg) == 0:
                continue
            pos = len(ret)
            if isinstance(area.spec, InfoTable) or not (
                    isinstance(cfg, dict) or isinstance(cfg, OrderedDict) ):
                ret += self.encode_info_table(area.spec, area_cfg)
            else:
                ret += self.encode_area_hex(area.spec, area_cfg, i == len(areas) - 1)
            if pos != len(ret):
                ret[area.pos] = div8(pos)
            i += 1

        header_checksum_pos = len(FRU_SPEC)
        ret[header_checksum_pos] = checksum(ret[:header_checksum_pos])
        return ret

def encode(data_in, logger = None): # type: (Union[OrderedDict[str, AreaValue], Dict[str, AreaValue]], Optional[Logger]) -> bytearray
    e = Encoder(logger)
    return e.encode(data_in)

