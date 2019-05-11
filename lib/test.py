from fruit.decoder import Decoder
from fruit.encoder import Encoder
import fruit.logging
import fruit.types

#d = fruit.decoder.Decoder()
#data_in = open('ego-authd1.bin', 'rb').read()
#cfg = d.decode(data_in)

from fruit.ftoml import *

e        = Encoder()
data_in  = open('../test.toml', "rb").read()
cfg      = load(data_in)
data_out = e.encode(cfg)
open('../test.bin', 'wb').write(data_out)

d        = Decoder()
cfg2     = d.decode(data_out)

print(dump(cfg2).decode('utf8'))
