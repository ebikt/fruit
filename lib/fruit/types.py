from collections import OrderedDict
MYPY=False
if MYPY:
    from typing import Union, Dict
    unicode    = str
    basestring = str
else:
    try:
        unicode
        basestring
    except NameError:
        unicode    = str
        basestring = str


class StrWithEncoding(unicode):
    """ Just ordinary python representation of string,
        enhanced with encoding that was decoded from or
        encoding that will be used to encode to. """
    encoding = None       # type: str
    lang_disagree = None  # type: bool

class Hexadecimal(StrWithEncoding):
    encoding = 'hex'

class BcdString(StrWithEncoding):
    encoding = 'bcd'

class PackedAscii(StrWithEncoding):
    encoding = 'packed'

class Latin1String(StrWithEncoding):
    encoding = 'latin1'

class ProperLatin1String(StrWithEncoding):
    lang_disagree = False

class MisusedLatin1String(StrWithEncoding):
    lang_disagree = True

class U16String(StrWithEncoding):
    encoding = 'ucs2le'

class ProperU16String(U16String):
    lang_disagree = False

class MisusedU16String(U16String):
    lang_disagree = True

if MYPY:
    from typing   import List
    import datetime
    StrValue   = Union[basestring, StrWithEncoding]
    EntryValue = Union[int, datetime.datetime, StrValue, List[StrValue]]

    AreaValue = Union[str, OrderedDict[str, EntryValue], Dict[str, EntryValue]]
