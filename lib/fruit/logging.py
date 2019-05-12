import sys

class ExceptionWithMsg(Exception):
    """ Typed Exception for MYPY """
    message = None # type: str
    def __init__(self, message): # type: (str) -> None
        self.message = message
        super(ExceptionWithMsg, self).__init__(message)

class DecoderError(ExceptionWithMsg):
    """ Raised on fatal error when decoding. """
    pass

class EncoderError(ExceptionWithMsg):
    """ Raised on fatal error when encoding. """
    pass
 
class Logger(object):
    """ Base logger for use with fruit.Encoder and fruit.Decoder """
    def info(self, msg): # type: (str) -> None
        """ Information level message (warning about harmless deviation). """
        raise NotImplementedError()

    def warning(self, msg): # type: (str) -> None
        """ Warning level message (data may be misinterpreted). """
        raise NotImplementedError()

    def decodererror(self, msg): # type: (str) -> None
        """ Decoding error, not fatal, but specification explicitly
            forbids such state. Standard logger raises DecoderError(msg)
            but it is safe to just log message and continue decoding.
            Decoder raises DecoderError directly for grave decoding errors."""
        raise NotImplementedError()

class StdErrLogger(Logger):
    """ Basic implementation of fruit.Logger, that logs to sys.stderr
        and raises DecoderError when decodererror() is called. """
    def _log(self, prefix, msg): # type: (str, str) -> None
        sys.stderr.write("%s: %s\n" % (prefix, msg))

    def info(self, msg): # type: (str) -> None
        self._log('Inf', msg)

    def warning(self, msg): # type: (str) -> None
        self._log('Wrn', msg)

    def decodererror(self, msg): # type: (str) -> None
        raise DecoderError(msg)

