#!/usr/bin/env python
# Coding: Both python2.7 and python3 should execute this code correctly

"""
https://www.intel.com/content/dam/www/public/us/en/documents/specification-updates/ipmi-platform-mgt-fru-info-storage-def-v1-0-rev-1-3-spec-update.pdf
https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.0.0.pdf
"""

import sys, datetime, binascii
MYPY=False
if MYPY:
    from typing import Any, Dict, List, Union, Tuple
    Val = Union[str, int, List[str], None]

# {{{ auxiliary functions
def div8(n): # type: (int) -> int
    assert n % 8 == 0
    return int(n/8)

def checksum(b): # type: (bytearray) -> int
    return (256 * len(b) - sum(b)) % 256
# }}}

FRU_TABLE_DEF = ( # {{{
    (None, 1),
    (None, 0),
    ("chassis",
        ("B", "type", 2, 1, 0x20),
        "partno",
        "serial",
    ),
    ("board",
        ("B", "lang", 0, 0, 0), # We do not support NLS
        ("D", "date"), #We do not support date encoding yet
        "manufacturer",
        "product",
        "serial",
        "partno",
        "fru",
    ),
    ("product",
        ("B", "lang", 0, 0, 0), # We do not support NLS
        "manufacturer",
        "name",
        "partno",
        "version",
        "serial",
        "asset",
        "fru"
    ),
    (None, 0),
    (None, 0),
) # type: Tuple[tuple, ...]

assert len(FRU_TABLE_DEF) % 8 == 7
# }}}



class Logger(object): # {{{
    def info(self, msg): # type: (str) -> None
        raise NotImplementedError()

    def warning(self, msg): # type: (str) -> None
        raise NotImplementedError()

    def decodererror(self, msg): # type: (str) -> None
        raise NotImplementedError()

class StdErrLogger(Logger):
    def _log(self, prefix, msg): # type: (str, str) -> None
        sys.stderr.write("%s: %s\n" % (prefix, msg))

    def info(self, msg): # type: (str) -> None
        self._log('Inf', msg)

    def warning(self, msg): # type: (str) -> None
        self._log('Wrn', msg)

    def decodererror(self, msg): # type: (str) -> None
        raise DecoderError(msg)
# }}}


class EncoderError(Exception): # {{{
    pass
# }}}

class DecoderError(Exception): # {{{
    pass
# }}}

class EndOfTable(Exception): # {{{
    pass
# }}}


class Entry(object): # {{{
    key     = None # type: str
    default = None # type: Val
    val     = None # type: Val
    logger  = None # type: Logger

    def __init__(self, key, default = None): # type: (str, Val) -> None
        self.key     = key
        self.default = default

    def cfgpop(self, cfg): # type: (Dict[str, Val]) -> None
        self.val = cfg.pop(self.key, self.default)

    def process(self, cfg, data): # type: (Dict[str, Val], bytearray) -> None
        self.cfgpop(cfg)
        try:
            self.enc_validate()
        except EncoderError as e:
            EncoderError(self.key + ': ' + e.args[0])
        self.enc_append(data)

    def save_val(self, cfg): # type: (Dict[str, Val]) -> None
        cfg[self.key] = self.val

    def decode(self, data, tname): # type: (bytearray, str) -> int
        raise NotImplementedError()

    def decode_default(self): # type: () -> None
        self.val = self.default

    def enc_validate(self): # type: () -> None
        raise NotImplementedError()

    def enc_append(self, data): #type: (bytearray) -> None
        raise NotImplementedError()

    def setlogger(self, logger): #type: (Logger) -> None
        self.logger = logger
# }}}

class Byte(Entry): # {{{
    val = None # type: int
    def __init__(self, key, default=0, minval=0, maxval=255): # type: (str, int, int, int) -> None
        super(Byte, self).__init__(key, default)
        self.minval  = minval
        self.maxval  = maxval
        self.default = default

    def enc_validate(self): # type: () -> None
        try:
            n = int(self.val)
        except ValueError:
            raise EncoderError("Invalid value, expecting integer")
        if n < self.minval or n < 0:
            raise EncoderError("Value too low, expecting >= %d" % (self.minval))
        if n > self.maxval or n > 255:
            raise EncoderError("Value too high, expecting <= %d" % (self.maxval))

    def enc_append(self, data): # type: (bytearray) -> None
        data.append(self.val)

    def decode(self, data, tname): # type: (bytearray, str) -> int
        self.val = data[0]
        return 1

    def decode_default(self): # type: () -> None
        """ This should be prevented by table length """
        assert False
# }}}

class Date(Entry): # {{{
    val = None # type: str

    def __init__(self, key): # type: (str) -> None
        super(Date, self).__init__(key, u'1996-01-01T00:00:00Z')

    def enc_validate(self): # type: () -> None
        if self.val != self.default:
            self.logger.warning("Setting date not supported (got: %r) - ignoring" % (self.val,))

    def enc_append(self, data): # type: (bytearray) -> None
        data += bytearray( (0,0,0) )

    def decode(self, data, tname): # type: (bytearray, str) -> int
        mins  = data[0] + data[1] * 256 + data[2] * 65536
        epoch = mins * 60 + 820454400
        d = datetime.datetime.utcfromtimestamp(epoch)
        self.val = d.isoformat() + 'Z'
        return 3

    def decode_default(self): # type: () -> None
        """ This should be prevented by table length """
        assert False
# }}}

# {{{ Str decoders
def strhex(b): # type: (bytes) -> str
    return binascii.hexlify(b).decode('ascii')

def bcdplus(b): # type: (bytes) -> str
    s = strhex(b)
    s = s.replace('a', ' ')
    s = s.replace('b', '-')
    s = s.replace('c', '.')
    s = s.replace('d', "\u24B9")
    s = s.replace('e', '\u24BA')
    s = s.replace('f', '\u24BB')
    return s

def packedAscii(data): # type: (bytes) -> str
    bits   = 0
    bitval = 0
    pos    = 0
    ret = bytearray()
    while pos < len(data):
        bitval = bitval * 256 + data[pos]
        pos += 1
        bits += 8
        while bits > 6:
            bits -= 6
            rem = bitval % (2**bits)
            ret.append(32 + rem)
            bitval = (bitval - rem) >> 6
        if bits == 6:
            bits -= 6
            ret.append(32 + bitval)
            bitval = 0
    return ret.decode('ascii')

def str8bit(data): # type: (bytes) -> str
    # python2&3 sane results
    return str(data.decode('ascii'))
# }}}


class Str(Entry): # {{{
    DECODERS = (strhex, bcdplus, packedAscii, str8bit)
    val = None # type: str

    def __init__(self, key, default = ""): # type: (str, str) -> None
        super(Str, self).__init__(key, default)

    def enc_validate(self): # type: () -> None
        try:
            self.bval = self.val.encode('ascii')
        except Exception:
            raise EncoderError("Invalid value, allowing only ASCII string")
        if len(self.bval) == 1:
            raise EncoderError("Invalid length, single character is forbidden by specification")
        if len(self.bval) > 63:
            raise EncoderError("Value too long (at most 63 characters allowed)")

    def enc_append(self, data): # type: (bytearray) -> None
        #Other encodings not (yet) supported
        data.append(0xc0 + len(self.bval))
        data += self.bval

    def decode(self, data, tname): # type: (bytearray, str) -> int
        tl = data[0]
        t = tl >> 6
        l = tl % (1 << 6)
        if t != 3:
            self.logger.warning("Entry %s.%s has type %d, note that this is not supported when constructing fru data" %
                (tname, self.key, t))
        elif l == 1:
            raise EndOfTable(1)
        data[l] # raises IndexError if datga is too short
        self.val = self.DECODERS[t](data[1:l+1])
        return l + 1
# }}}

class OemStr(Entry): # {{{
    val  = None # type: List[str]
    strs = None # type: List[Str]

    def __init__(self, key): # type: (str) -> None
        super(OemStr, self).__init__(key, [])

    def enc_validate(self): # type: () -> None
        if not isinstance(self.val, list):
            raise EncoderError("Invalid value, expected list of strings")
        self.strs = []
        for i in range(len(self.val)):
            s = Str(str(i))
            s.val = self.val[i]
            try:
                s.enc_validate()
            except EncoderError as e:
                raise EncoderError(" item %d: %s" % (i, e.args[0]))
            self.strs.append(s)

    def enc_append(self, data): # type: (bytearray) -> None
        for s in self.strs:
            s.enc_append(data)

    def decode(self, data, tname): # type: (bytearray, str) -> int
        self.val = []
        i = 1
        pos = 0
        while True:
            s = Str("oem%d" % i)
            try:
                pos += s.decode(data[pos:], tname)
            except EndOfTable as e:
                return pos + int(e.args[0])
            self.val.append(s.val)
# }}}

class Table(object): # {{{
    ENTRIES=dict(
        B=Byte,
        D=Date,
        S=Str
    )
    logger  = None # type: Logger
    pos     = None # type: int
    offset  = None # type: int
    name    = None # type: str
    entries = None # type: List[Entry]

    def __init__(self, logger, spec, pos, offset = 0): # type: (Logger, tuple, int, int) -> None
        def mkentry(espec): # type: (tuple) -> Entry
            """ Creates Entry() object from entry specification tuple """
            if not isinstance(espec, tuple):
                espec = ("S", espec)
            return self.ENTRIES[espec[0]](*(espec[1:])) # type: ignore
        self.logger = logger
        self.pos = pos
        self.offset = offset
        self.name = spec[0]
        self.entries = [ mkentry(x) for x in spec[1:] ]
        self.entries.append(OemStr("oem"))
        for e in self.entries: e.setlogger(logger)

    # {{{ encoding
    def process(self, cfg, data): # type: (Dict[str,Dict[str,Val]], bytearray) -> None
        self.cfgpop(cfg)
        if len(self.cfg) > 0:
            self.open(data)
            for entry in self.entries:
                try:
                    entry.process(self.cfg, data)
                except EncoderError as e:
                    raise EncoderError("%s.%s" % (self.name, e.args[0]))
            self.close(data)
        else:
            data[self.pos] = 0
        if len(self.cfg) > 0:
            raise EncoderError("%s: Unknown configuration entries: %s" % (self.name, ", ".join(self.cfg.keys())))

    def cfgpop(self, cfg): # type: (Dict[str,Dict[str,Val]]) -> None
        self.cfg = cfg.pop(self.name, {})
        if not isinstance(self.cfg, dict):
            raise EncoderError("%s: Configuration must be a dictionary" % (self.name, ))

    def open(self, data): # type: (bytearray) -> None
        self.offset = len(data)
        data[self.pos] = div8(self.offset)
        data += bytearray( (1, 0) )

    def close(self, data): # type: (bytearray) -> None
        data.append(0xc1)
        while len(data) % 8 != 7:
            data.append( 0 )
        data[self.offset + 1] = div8(len(data) + 1 - self.offset)
        data.append(checksum(data[self.offset:]))
    # }}}

    def decode(self, data): # type: (bytearray) -> Dict[str, Val] # {{{
        eot = False
        pos = 0
        ret = {} # type: Dict[str, Val]
        try:
            for entry in self.entries:
                try:
                    if eot:
                        entry.decode_default()
                    else:
                        pos += entry.decode(data[pos:], self.name)
                except IndexError:
                    raise DecoderError("%s: Runaway entry - entry overlaps checksum of its table" % (entry.key,))
                except EndOfTable as e:
                    self.logger.warning("Table ended when parsing predefined fields.")
                    eot = True
                    pos += e.args[0]
                    entry.decode_default()
                entry.save_val(ret)
        except DecoderError as e:
            raise DecoderError("%s.%s" % (self.name, e.args[0]))
        return ret
    # }}}

# }}}



class FruEncoder(object): # {{{
    logger = None # type: Logger
    data   = None # type: bytearray
    cfg    = None # type: Dict[str,Dict[str,Val]]

    def __init__(self, logger = None): # type: (Logger) -> None
        self.data = bytearray()
        if logger is None:
            logger = StdErrLogger()
        self.logger = logger

    def encode(self, cfg): # type: (Dict[str,Dict[str,Val]]) -> bytearray # {{{
        self.cfg = cfg
        if not isinstance(self.cfg, dict):
            raise EncoderError("Configuration must be a dictionary")
        self.tables = [] # type: List[Table]
        self.prepare_header()
        for table in self.tables:
            table.process(self.cfg, self.data)
        self.close_header()
        if len(self.cfg):
            raise EncoderError("Invalid configuration entries: %s" % (', '.join(self.cfg.keys()),))
        return self.data
    # }}}

    def prepare_header(self): # type: () -> None # {{{
        for hdr_entry in FRU_TABLE_DEF:
            if hdr_entry[0] is None:
                self.data.append(hdr_entry[1])
            else:
                self.tables.append(Table( self.logger, hdr_entry, len(self.data) ))
                self.data.append(0)
        self.hdr_sum_pos = len(self.data)
        self.data.append(0)
        assert len(self.data) % 8 == 0
    # }}}

    def close_header(self): # type: () -> None # {{{
        self.data[self.hdr_sum_pos] = checksum(self.data[:self.hdr_sum_pos])
    # }}}

# }}}


class FruDecoder(object): # {{{
    logger = None # type: Logger
    pos    = None # type: int
    output = None # type: Dict[str, Dict[str, Val]]
    data   = None # type: bytearray

    def __init__(self, logger = None): # type: (Logger) -> None
        if logger is None:
            logger = StdErrLogger()
        self.logger = logger

    def decodeheader(self): # type: () -> None # {{{
        self.tables = [] # type: List[Table]
        torder = []      # type: List[int]
        hdrlen = len(FRU_TABLE_DEF)
        try:
            for i in range(hdrlen):
                if FRU_TABLE_DEF[i][0] is None:
                    if self.data[i] != FRU_TABLE_DEF[i][1]:
                        self.logger.warning("Header entry %d contains unsupported value %d" % (i, self.data[i]))
                else:
                    torder.append(self.data[i])
                    self.tables.append(Table( self.logger, FRU_TABLE_DEF[i], i, self.data[i]*8 ))
            if sum(self.data[:hdrlen + 1]) % 256 != 0:
                self.logger.decodererror("Invalid header checksum (got %d, expected %d)" %
                                        (self.data[hdrlen], checksum(self.data[:hdrlen])))
        except IndexError:
            raise DecoderError("Premature end of file while parsing header (%d < %d bytes)" %
                                    (len(self.data), hdrlen + 1))
        if torder != sorted(torder):
            self.logger.warning("Tables are not in cannonical order.")
        self.pos = hdrlen + 1
    # }}}

    def decodetables(self): # type: () -> None # {{{
        for table in sorted(self.tables, key = lambda x: x.offset):
            if table.offset == 0:
                self.logger.info("Table %s is missing" % (table.name, ))
                continue
            self.decodetable(table)
        if self.pos < len(self.data):
            if len(filter(lambda x: x, self.data[self.pos:])): # type: ignore
                self.logger.warning("Remaining %d bytes ignored" % (len(self.data) - self.pos,))
            else:
                self.logger.info("Trailing %d zero bytes ignored" % (len(self.data) - self.pos,))
    # }}}

    def decodetable(self, table): # type: (Table) -> None # {{{
        if table.offset < self.pos:
            self.logger.decodererror("Table %s overlaps previous data" % (table.name,))
        if table.offset > self.pos:
            self.logger.warning("Gap detected before table %s. Data in gap ignored." % (table.name, ))
        tabledata = self.data[table.offset:]
        if len(tabledata) < 8:
            explen = 8
        else:
            explen = tabledata[1] * 8
        if explen == 0:
            raise DecoderError("Invalid length of table %s (0)" % (table.name))
        if explen > len(tabledata):
            raise DecoderError("Premature end of file, expected %d bytes, but %d are remaining for table %s" % (explen, len(tabledata), table.name))
        if tabledata[0] != 1:
            self.logger.decodererror("Invalid specification version of table %s: %d (expected 1)" % (table.name, tabledata[0]))
        self.logger.info("Table %s has %d bytes" % (table.name, explen))
        tabledata = tabledata[:explen]
        self.pos = table.offset + explen
        if sum(tabledata) % 256 != 0:
            self.logger.decodererror("Invalid checksum of table %s expected %s got %s" %
                (table.name, tabledata[explen-1], checksum(tabledata[:explen-1])))
        self.output[table.name] = table.decode(tabledata[2:explen -1])
    # }}}

    def decode(self, data): # type: (bytes) -> Dict[str, Dict[str, Val]] # {{{
        self.data = bytearray(data)
        self.output = dict()
        self.decodeheader()
        self.decodetables()
        return self.output
    # }}}

# }}}

def decode(data, logger = None): # type: (bytes, Logger) -> Dict[str, Dict[str, Val]]
    return FruDecoder(logger).decode(data)

def encode(cfg, logger = None): # type: (Dict[str, Dict[str, Val]], Logger) -> bytearray
    return FruEncoder(logger).encode(cfg)
