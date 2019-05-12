MYPY = False
__all__ = ["UTC", "checksum", "div8"]

def checksum(b): # type: (bytearray) -> int
    """ Calculate checksum byte c, so that sum(b) + c is zero (modulo 256). """
    return (256 * len(b) - sum(b)) % 256

def div8(i): # type: (int) -> int
    """ Return i/8, raise exception if i is not divisible by 8. """
    assert i % 8 == 0
    return int(i/8)

import datetime
try:
    UTC = datetime.timezone.utc
except AttributeError:
    if not MYPY:
        _ZERO_INTERVAL = datetime.timedelta(0)
        class UTCClass(datetime.tzinfo):
            """ UTC """
            def utcoffset(self, dt):
                return _ZERO_INTERVAL
            def tzname(self, dt):
                return "UTC"
            def dst(self, dt):
                return _ZERO_INTERVAL
        UTC = UTCClass()

if MYPY:
    from typing import Union, Tuple, List, Optional, Callable, Type
    unicode    = str
    unichr     = chr
    basestring = str
else:
    try:
        unicode
        unichr
        basestring
    except NameError:
        unicode    = str
        unichr     = chr
        basestring = str

import codecs # {{{

class CustomCodec(object):
    """ Simple custom codec. Only stateless encoding and decoding is supported. """
    name = None # type: str # to be filled by @register

    @classmethod
    def charerror(cls, text, pos, msg): # type: (unicode, int, str) -> UnicodeEncodeError
        """ UnicodeEncodeError helper for error in single character. """
        return UnicodeEncodeError( cls.name, text, pos, pos+1, msg)

    @classmethod
    def byteerror(cls, text, pos, msg): # type: (bytes, int, str) -> UnicodeDecodeError
        """ UnicodeDecodeError helper for error in single byte. """
        return UnicodeDecodeError( cls.name, text, pos, pos+1, msg)

def register(codec_name): # type: (str) -> Callable[[Type[CustomCodec]], Type[CustomCodec]]
    """ Registers CustomCodec with name `codec_name`. """
    def decorator(cls): # type: (Type[CustomCodec]) -> Type[CustomCodec]
        if not MYPY:
            assert cls.decode
            assert cls.encode
        cls.name = codec_name
        def search(encoding_name): # type: (str) -> codecs.CodecInfo
            # Uh, don't know what correct types are here.
            # But it works, so we disable MYPY here
            # FIXME: examine correct types around codecs
            if encoding_name == codec_name:
                return codecs.CodecInfo(cls.encode, cls.decode, name=cls.name) # type: ignore
            else:
                return None # type: ignore
        codecs.register(search)
        return cls
    return decorator
# }}}

@register('ucs2le') # {{{
class Ucs2Le(CustomCodec):
    """ ucs2le is similar to utf16le, but it does not decode/encode surrogate pairs,
        it generates codepoints that are not valid in unicode (reserved for surrogate
        pairs). """

    @classmethod
    def encode(cls, text, errors="strict"): # type: (unicode, str) -> Tuple[bytes, int]
        error_handler = codecs.lookup_error(errors)
        s = bytearray()
        for i in range(len(text)):
            c = ord(text[i])
            if c >= 65536:
                e = cls.charerror(text, i, 'ordinal not in range(65536)')
                repl, l = error_handler(e)
                if len(repl) % 2 == 0:
                    s.extend([ord(str(x)) for x in repl])
                else:
                    raise e
            else:
                s.append(c % 256)
                s.append(c >> 8)
        return bytes(s), len(text)

    @classmethod
    def decode(cls, text, errors="strict"): # type: (Union[bytearray, bytes], str) -> Tuple[unicode, int]
        ret = [] # type: List[unicode]
        if not isinstance(text, bytearray):
            text = bytearray(text)
        for i in range(0, len(text)-1, 2):
            ret.append(unichr(text[i] + (text[i+1] * 256)))
        if len(text) % 2 != 0:
            e = cls.byteerror(bytes(text), len(text) - 1, "truncated data")
            error_handler = codecs.lookup_error(errors)
            repl, l = error_handler(e)
            ret.append(unicode(repl))
        return u''.join(ret), len(text)
# }}}

@register('packed_ascii') # {{{
class Packed(CustomCodec):
    """ packed_ascii encodes codepoints in range(32,96), packing 4 characters
        in 3 bytes in little endian, i.e. lowest significant bit (bit 0)
        of first character is lowest significant bit (bit 0) of first byte.
        Then bit 0 of second character is bit 6 of first byte, bit 2 of second
        character is bit 0 of second byte and so on.

        Note that if string is one character short to have length divisible by 4,
        then this encoding adds space at end of such string, because such strings
        cannot be represented in packed_ascii encoding. """

    @classmethod
    def encode(cls, text, error="strict"): # type: (unicode, str) -> Tuple[bytes, int]
        error_handler = codecs.lookup_error(error)
        ret = bytearray()
        bits = 0
        for i in range(len(text)):
            c = ord(text[i]) - 32
            if c < 0 or c >= (1 << 6):
                e = cls.charerror(text, i, 'ordinal not in range(32, 96)')
                repl, l = error_handler(e)
                c = ord(repl) - 32
                if c < 0 or c >= (1 << 6) or len(repl) != 1:
                    raise e
            if bits > 0:
                ret[-1] += (c << bits) % 256
                c = c >> (8 - bits)
            if bits != 2:
                ret.append(c)
            else:
                assert c == 0
            bits = (bits + 6) % 8
        return bytes(ret), len(text)

    @staticmethod
    def decode(text, errors="strict"): # type: (Union[bytearray, bytes], str) -> Tuple[unicode, int]
        if not isinstance(text, bytearray):
            text = bytearray(text)
        bits   = 0
        bitval = 0
        pos    = 0
        ret = bytearray()
        while pos < len(text):
            bitval += text[pos] << bits
            pos += 1
            bits += 8
            while bits >= 6:
                ret.append((bitval % (1 << 6)) + 32)
                bitval = bitval >> 6
                bits -= 6
        return ret.decode('utf8'), len(text)
# }}}
