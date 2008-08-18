class CollectorException(RuntimeError):
    pass

class NoCommunity(CollectorException):
    pass

class UnknownEquipment(CollectorException):
    pass

class NoLLDP(CollectorException):
    pass

class CollectorAlreadyRunning(CollectorException):
    pass
