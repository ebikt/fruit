MYPY=False
from .types import *

__all__=["dump", "load"]
if MYPY:
    from typing import Dict
    unicode = str
    def dump(cfg): # type: (Dict[str, AreaValue]) -> bytes
        """ Dumps decoded output into enhanced TOML. Returns utf-8 encoded bytes. """
        return b''

    def load(cfg): # type: (bytes) -> Dict[str, AreaValue]
        """ Loads enhanced TOML (bytes, utf-8 encoded) into something, that can be encoded. """
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

        def load_inline_object(self, line, currentlevel, multikey=False,
                               multibackslash=False):
            candidate_groups = line[1:-1].split(",")
            groups = []
            if len(candidate_groups) == 1 and not candidate_groups[0].strip():
                candidate_groups.pop()
            while len(candidate_groups) > 0:
                candidate_group = candidate_groups.pop(0)
                try:
                    _, value = candidate_group.split('=', 1)
                except ValueError:
                    raise ValueError("Invalid inline table encountered")
                value = value.strip()
                if ((value[0] == value[-1] and value[0] in ('"', "'")) or
                    value[0] in '-0123456789' or
                    value in ('true', 'false') or
                    (value[0] == "[" and value[-1] == "]") or
                    (value[0] == '{' and value[-1] == '}') or
                    (value[0] in self.FruTypes and value[1:2] == value[-1]
                        and value[-1] in ('"', '"')) ):
                    groups.append(candidate_group)
                elif len(candidate_groups) > 0:
                    candidate_groups[0] = (candidate_group + "," +
                                           candidate_groups[0])
                else:
                    raise ValueError("Invalid inline table value encountered")
            for group in groups:
                status = self.load_line(group, currentlevel, multikey,
                                        multibackslash)
                if status is not None:
                    break


    def dump(cfg):
        return toml.dumps(cfg, FruTomlEncoder()).encode('utf8')

    def load(data):
        return toml.loads(data.decode("utf8"), decoder = FruTomlDecoder())
