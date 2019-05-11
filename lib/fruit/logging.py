import sys

class ExceptionWithMsg(Exception):
    """ Typed Exception for MYPY """
    message = None # type: str
    def __init__(self, message): # type: (str) -> None
        self.message = message
        super(ExceptionWithMsg, self).__init__(message)

class DecoderError(ExceptionWithMsg):
    pass

class EncoderError(ExceptionWithMsg):
    pass
 
class Logger(object):
    def info(self, msg): # type: (str) -> None
        raise NotImplementedError()

    def warning(self, msg): # type: (str) -> None
        raise NotImplementedError()

    def decodererror(self, msg): # type: (str) -> None
        # This will typically raise DecoderError, but log error
        # and continue decoding is valid option.
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

