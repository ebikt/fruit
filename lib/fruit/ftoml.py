MYPY=False
from .types import *

__all__=["dump", "load"]
if MYPY:
    from typing import Dict
    unicode = str
    def dump(cfg): # type: (Dict[str, AreaValue]) -> bytes
        return b''

    def load(cfg): # type: (bytes) -> Dict[str, AreaValue]
        return {}
else:
    import toml
    class FruTomlEncoder(toml.TomlEncoder):
        def __init__(self, _dict = OrderedDict, preserve = False):
            super(FruTomlEncoder, self).__init__(_dict, preserve)

        def dump_value(self, v):
            if isinstance(v, StrWithEncoding):
                l = u''
                if isinstance(v, Hexadecimal):
                    l = u'h'
                elif isinstance(v, BcdString):
                    l = u'b'
                elif isinstance(v, PackedAscii):
                    l = u'p'
                elif isinstance(v, MisusedLatin1String):
                    l = u'a'
                elif isinstance(v, MisusedU16String):
                    l = u'u'
                return l + super(FruTomlEncoder, self).dump_value(unicode(v))
            if isinstance(v, str):
                # Python3 str has __iter__
                v = str(v)
            return super(FruTomlEncoder, self).dump_value(v)


    class FruTomlDecoder(toml.TomlDecoder):
        FruTypes = {
            'h': Hexadecimal,
            'b': BcdString,
            'p': PackedAscii,
            'a': Latin1String,
            'u': U16String,
        }
        def __init__(self, _dict = OrderedDict):
            super(FruTomlDecoder, self).__init__(_dict)

        def load_value(self, v, strictly_valid = True):
            sv = v.strip()
            if len(sv) > 2 and sv[1] in u"\"'" and sv[0] in self.FruTypes:
                retv, rett = super(FruTomlDecoder, self).load_value(sv[1:], strictly_valid)
                assert rett == "str"
                return self.FruTypes[sv[0]](retv), rett
            return super(FruTomlDecoder, self).load_value(v, strictly_valid)

    def dump(cfg):
        return toml.dumps(cfg, FruTomlEncoder()).encode('utf8')

    def load(data):
        return toml.loads(data.decode("utf8"), decoder = FruTomlDecoder())
