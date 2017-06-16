#indexer.py
"""Package Indexer server code."""

import socket
from threading import Lock, Thread

#-------------------------- Constants -----------------------------
PORT_LISTEN= 8080
MAX_QUEUED_CONNECTIONS= 5
MAX_SOCK_TIMEOUT_SECS= 60.0
MAX_PKT_BYTES= 1024


#------------------------- Global State ---------------------------
indexLock= Lock()
forwards= {}
backwards= {}

#--------------------- Threading Constructs -----------------------
class IndexThread(Thread):
    def __init__(self, cltSock):
        Thread.__init__(self)
        self.cltSock= cltSock
    
    def run(self):
        print "Starting new clt thread"
        cmd= "dummy"
        while len(cmd) > 0:
            cmd= self.cltSock.recv(MAX_PKT_BYTES)
            print "Received command: %s" % cmd
        print "Ending clt thread"


#-------------------------- Functions -----------------------------
def testAcceptConnection(sock):
    pass


def createSrvSocket():
    """Returns: socket object that listens on port PORT_LISTEN and has
         a timeout of MAX_SOCK_TIMEOUT_SECS."""
    srvSock= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #TODO srvSock.settimeout(MAX_SOCK_TIMEOUT_SECS)
    srvSock.bind((socket.gethostname(), PORT_LISTEN))
    return srvSock

    

def main():
    srvSock= createSrvSocket()
    srvSock.listen(MAX_QUEUED_CONNECTIONS)
    while True:
        (cliSock, addr)= srvSock.accept()
        cliThr= IndexThread(cliSock)
        cliThr.start()

    







if __name__ == "__main__":
    main()
