#!/usr/bin/env python
# Coding: Both python2.7 and python3 should execute this code correctly

"""
https://www.intel.com/content/dam/www/public/us/en/documents/specification-updates/ipmi-platform-mgt-fru-info-storage-def-v1-0-rev-1-3-spec-update.pdf
https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.0.0.pdf
"""

import os, sys, yaml, datetime

# {{{ auxiliary functions
def error(msg):
    sys.stderr.write("Err: " + msg + "\n")
    sys.exit(1)

def warning(msg):
    sys.stderr.write("Wrn: " + msg + "\n")

def info(msg):
    sys.stderr.write("Inf: " + msg + "\n")

def div8(n):
    assert n % 8 == 0
    return int(n/8)

def checksum(b):
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
)

assert len(FRU_TABLE_DEF) % 8 == 7
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
    def __init__(self, key, default = None):
        self.key     = key
        self.default = default

    def cfgpop(self, cfg):
        self.val = cfg.pop(self.key, self.default)

    def enc_validate(self):
        pass

    def process(self, cfg, data):
        self.cfgpop(cfg)
        try:
            self.enc_validate()
        except EncoderError as e:
            EncoderError(self.key + ': ' + e.message)
        self.enc_append(data)

    def save_val(self, cfg):
        cfg[self.key] = self.val

    def decode_default(self):
        self.val = self.default
# }}}

class Byte(Entry): # {{{
    def __init__(self, key, default=0, minval=0, maxval=255):
        super(Byte, self).__init__(key, default)
        self.minval  = minval
        self.maxval  = maxval
        self.default = default

    def enc_validate(self):
        try:
            n = int(self.val)
        except ValueError:
            raise EncoderError("Invalid value, expecting integer")
        if n < self.minval or n < 0:
            raise EncoderError("Value too low, expecting >= %d" % (self.minval))
        if n > self.maxval or n > 255:
            raise EncoderError("Value too high, expecting <= %d" % (self.maxval))

    def enc_append(self, data):
        data.append(self.val)

    def decode(self, data, tname):
        self.val = data[0]
        return 1

    def decode_default(self):
        """ This should be prevented by table length """
        assert False
# }}}

class Date(Entry): # {{{
    def __init__(self, key):
        super(Date, self).__init__(key, u'1996-01-01T00:00:00Z')

    def enc_validate(self):
        if self.val != self.default:
            warning("Setting date not supported (got: %r) - ignoring" % (self.val,))

    def enc_append(self, data):
        data += bytearray( (0,0,0) )

    def decode(self, data, tname):
        mins  = data[0] + data[1] * 256 + data[2] * 65536
        epoch = mins * 60 + 820454400
        d = datetime.datetime.utcfromtimestamp(epoch)
        self.val = d.isoformat() + 'Z'
        return 3

    def decode_default(self):
        """ This should be prevented by table length """
        assert False
# }}}

# {{{ Str decoders
def strhex(b):
    return b.encode("hex")

def bcdplus(b):
    s = strhex(b)
    s = s.replace('a', ' ')
    s = s.replace('b', '-')
    s = s.replace('c', '.')
    s = s.replace('d', "\u24B9")
    s = s.replace('e', '\u24BA')
    s = s.replace('f', '\u24BB')

def packedAscii(data):
    bits   = 0
    bitval = 0
    pos    = 0
    ret = []
    while pos < len(data):
        bitval = bitval * 256 + struct.unpack_from("B", data, pos)[0]
        pos += 1
        bits += 8
        while bits > 6:
            bits -= 6
            rem = bitval % (2**bits)
            ret.append(struct.pack("B", 32 + rem))
            bitval = (bitval - rem) >> 6
        if bits == 6:
            bits -= 6
            ret.append(struct.pack("B", 32 + bitval))
            bitval = 0
    return repr(''.join(data))

def str8bit(data):
    # python2&3 sane results
    return str(data.decode('ascii'))
# }}}


class Str(Entry): # {{{
    DECODERS = (strhex, bcdplus, packedAscii, str8bit)

    def __init__(self, key, default = ""):
        super(Str, self).__init__(key, default)

    def enc_validate(self):
        try:
            self.bval = self.val.encode('ascii')
        except Exception:
            raise EncoderError("Invalid value, allowing only ASCII string")
        if len(self.bval) == 1:
            raise EncoderError("Invalid length, single character is forbidden by specification")
        if len(self.bval) > 63:
            raise EncoderError("Value too long (at most 63 characters allowed)")

    def enc_append(self, data):
        #Other encodings not (yet) supported
        data.append(0xc0 + len(self.bval))
        data += self.bval

    def decode(self, data, tname):
        tl = data[0]
        t = tl >> 6
        l = tl % (1 << 6)
        if t != 3:
            warning("Entry %s.%s has type %s, note that this is not supported when constructing fru data" %
                (tname, self.name, t))
        elif l == 1:
            raise EndOfTable(1)
        data[l] # raises IndexError if datga is too short
        self.val = self.DECODERS[t](data[1:l+1])
        return l + 1
# }}}

class OemStr(Entry): # {{{
    def __init__(self, key):
        super(OemStr, self).__init__(key, [])

    def enc_validate(self):
        if not isinstance(self.val, list):
            raise EncoderError("Invalid value, expected list of strings")
        self.strs = []
        for i in range(len(self.val)):
            s = Str(i)
            s.val = self.val[i]
            try:
                s.enc_validate()
            except EncoderError as e:
                raise EncoderError(" item %d: %s" % (i, e.message))
            self.strs.append(s)

    def enc_append(self, data):
        for s in self.strs:
            s.enc_append(data)

    def decode(self, data, tname):
        self.val = []
        i = 1
        pos = 0
        while True:
            s = Str("oem%d" % i)
            try:
                pos += s.decode(data[pos:], tname)
            except EndOfTable as e:
                return pos + e.args[0]
            self.val.append(s.val)
# }}}

class Table(object): # {{{
    ENTRIES=dict(
        B=Byte,
        D=Date,
        S=Str
    )

    def __init__(self, spec, pos, offset = 0):
        def mkentry(espec):
            """ Creates Entry() object from entry specification tuple """
            if not isinstance(espec, tuple):
                espec = ("S", espec)
            return self.ENTRIES[espec[0]](*(espec[1:]))
        self.pos = pos
        self.offset = offset
        self.name = spec[0]
        self.entries = [ mkentry(x) for x in spec[1:] ]
        self.entries.append(OemStr("oem"))

    # {{{ encoding
    def process(self, cfg, data):
        self.cfgpop(cfg)
        if len(self.cfg) > 0:
            self.open(data)
            for entry in self.entries:
                try:
                    entry.process(self.cfg, data)
                except EncoderError as e:
                    raise EncoderError("%s.%s" % (self.name, e.message))
            self.close(data)
        else:
            data[self.pos] = 0
        if len(self.cfg) > 0:
            raise EncoderError("%s: Unknown configuration entries: %s" % (self.name, ", ".join(self.cfg.keys())))

    def cfgpop(self, cfg):
        self.cfg = cfg.pop(self.name, {})
        if not isinstance(self.cfg, dict):
            raise EncoderError("%s: Configuration must be a dictionary" % (self.name, ))

    def open(self, data):
        self.offset = len(data)
        data[self.pos] = div8(self.offset)
        data += bytearray( (1, 0) )

    def close(self, data):
        data.append(0xc1)
        while len(data) % 8 != 7:
            data.append( 0 )
        data[self.offset + 1] = div8(len(data) + 1 - self.offset)
        data.append(checksum(data[self.offset:]))
    # }}}

    def decode(self, data): # {{{
        eot = False
        pos = 0
        ret = {}
        try:
            for entry in self.entries:
                try:
                    if eot:
                        entry.decode_default()
                    else:
                        pos += entry.decode(data[pos:], eot)
                except IndexError:
                    raise DecoderError("%s: Runaway entry - entry overlaps checksum of its table" % (entry.name,))
                except EndOfTable as e:
                    warning("Table ended when parsing predefined fields.")
                    eot = True
                    pos += e.args[0]
                    entry.decode_default()
                entry.save_val(ret)
        except DecoderError as e:
            raise DecoderError("%s.%s" % (self.name, e.message))
        return ret
    # }}}

# }}}



class FruEncoder(object): # {{{
    def __init__(self):
        self.data = bytearray()

    def process(self, cfg): # {{{
        self.cfg = cfg
        if not isinstance(self.cfg, dict):
            raise EncoderError("Configuration must be a dictionary")
        self.tables = []
        self.prepare_header()
        for table in self.tables:
            table.process(self.cfg, self.data)
        self.close_header()
        if len(self.cfg):
            raise EncoderError("Invalid configuration entries: %s" % (', '.join(self.cfg.keys()),))
        return self.data
    # }}}

    def prepare_header(self): # {{{
        for hdr_entry in FRU_TABLE_DEF:
            if hdr_entry[0] is None:
                self.data.append(hdr_entry[1])
            else:
                self.tables.append(Table( hdr_entry, len(self.data) ))
                self.data.append(0)
        self.hdr_sum_pos = len(self.data)
        self.data.append(0)
        assert len(self.data) % 8 == 0
    # }}}

    def close_header(self): # {{{
        self.data[self.hdr_sum_pos] = checksum(self.data[:self.hdr_sum_pos])
    # }}}

# }}}


class FruDecoder(object): # {{{
    def __init__(self, force = False):
        self.pos = None
        self.force = force

    def mayRaise(self, msg): # {{{
        if self.force:
            warning(msg)
        else:
            raise DecoderError(msg)
    # }}}

    def decodeheader(self): # {{{
        self.tables = []
        torder = []
        hdrlen = len(FRU_TABLE_DEF)
        try:
            for i in range(hdrlen):
                if FRU_TABLE_DEF[i][0] is None:
                    if self.data[i] != FRU_TABLE_DEF[i][1]:
                        warning("Header entry %d contains unsupported value %d" % (i, self.data[i]))
                else:
                    torder.append(self.data[i])
                    self.tables.append(Table( FRU_TABLE_DEF[i], i, self.data[i]*8 ))
            if sum(self.data[:hdrlen + 1]) % 256 != 0:
                self.mayRaise("Invalid header checksum (got %d, expected %d)" %
                                (self.data[hdrlen], checksum(self.data[:hdrlen])))
        except IndexError:
            raise DecoderError("Premature end of file while parsing header (%d < %d bytes)" %
                                    (len(self.data), hdrlen + 1))
        if torder != sorted(torder):
            warning("Tables are not in cannonical order.")
        self.pos = hdrlen + 1
    # }}}

    def decodetables(self): # {{{
        for table in sorted(self.tables, key = lambda x: x.offset):
            if table.offset == 0:
                info("Table %s is missing" % (table.name, ))
                continue
            self.decodetable(table)
        if self.pos < len(self.data):
            if len(filter(lambda x: x, self.data[self.pos:])):
                warning("Remaining %d bytes ignored" % (len(self.data) - self.pos,))
            else:
                info("Trailing %d zero bytes ignored" % (len(self.data) - self.pos,))
    # }}}

    def decodetable(self, table): # {{{
        if table.offset < self.pos:
            self.mayRaise("Table %s overlaps previous data" % (table.name,))
        if table.offset > self.pos:
            warning("Gap detected before table %s. Data in gap ignored." % (table.name, ))
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
            self.mayRaise("Invalid specification version of table %s: %d (expected 1)" % (table.name, tabledata[0]))
        info("Table %s has %d bytes" % (table.name, explen))
        tabledata = tabledata[:explen]
        self.pos = table.offset + explen
        if sum(tabledata) % 256 != 0:
            self.mayRaise("Invalid checksum of table %s expected %s got %s" %
                (table.name, tabledata[explen-1], checksum(tabledata[:explen-1])))
        self.output[table.name] = table.decode(tabledata[2:explen -1])
    # }}}

    def decode(self, data): # {{{
        self.data = bytearray(data)
        try:
            self.output = dict()
            self.decodeheader()
            self.decodetables()
        except DecoderError as e:
            error(e.message)
        return self.output
    # }}}

# }}}



def process_data(data_in): # {{{
    firstbyte = bytearray(data_in[0:1])
    if len(firstbyte) == 0:
        error("empty input")
    if firstbyte[0] == 1:
        f         = FruDecoder()
        cfg       = f.decode(data_in)
        data_out  = yaml.dump(cfg).encode('utf-8')
        is_binary = False
    else:
        f         = FruEncoder()
        cfg       = yaml.load(data_in)
        data_out  = f.process(cfg)
        is_binary = True
    return data_out, is_binary
# }}}

def read_input(): # {{{
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            data_in = f.read()
    else:
        try:
            data_in = sys.stdin.buffer.read()
        except AttributeError:
            data_in = sys.stdin.read()
    return data_in
# }}}

def write_output(data_out, is_binary): # {{{
    if len(sys.argv) > 2:
        with open(sys.argv[2], "wb") as f:
            f.write(data_out)
    elif is_binary and sys.stdout.isatty():
        error("Stdout is terminal, refusing to print binary file")
    else:
        try:
            sys.stdout.buffer.write(data_out)
        except AttributeError:
            sys.stdout.write(data_out)
# }}}

data_in = read_input()
data_out, is_binary = process_data(data_in)
write_output(data_out, is_binary)
