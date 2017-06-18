#indexer.py
"""Package Indexer server code.
Optional Args:
  debug - halts availability protections to make debugging easier."""

import re
import sys
import time
import socket
from threading import Lock, Thread

#-------------------------- Constants -----------------------------
PORT_LISTEN= 8080
MAX_QUEUED_CONNECTIONS= 5
MAX_SOCK_TIMEOUT_SECS= 4.0# 60.0
MAX_PKT_BYTES= 1024
MAX_SESSION_SECS= 120.0


#------------------------- Global State ---------------------------
isDebug= False
index= None


#--------------------------- Classes -----------------------------
class PackageIndex(object):
    def __init__(self):
        """Class to serve as the representation of the package indexer."""
        self.commands= {
            "INDEX": self.handleIndex,
            "REMOVE": self.handleRemove,
            "QUERY": self.handleQuery
        }
        self.forwards= {}
        self.backwards= {}
        self.Locks= {}
    #Have funcs to lock the state and unlock it as necessary
    #Funcs to get a piece of data and block in the meantime

    def getHandlerPtr(self, cmd):
        """Returns: pointer to function to handle the given command if it
             exists in this index instance; None otherwise."""
        if cmd not in self.commands:
            return None
        return self.commands[cmd]

    def handleIndex(self):
        pass
    
    def handleRemove(self):
        pass
    
    def handleQuery(self):
        pass
        

class IndexCommand(object):
    def __init__(self, handlerFunc, packageName, dependencies):
        """Class to model a command on an index, by storing a pointer to that
             index instance's handler function, along with any needed arguments.
           Precondition: handlerFunc is a function pointer, packageName is a str,
             dependencies is a list of str."""
        self.handlerFunc= handlerFunc
        self.packageName= packageName
        self.dependencies= dependencies

    def runCommand(self):
        return self.handlerFunc(packageName, dependencies)


class IndexThread(Thread):
    def __init__(self, threadId, cltSock, indexPtr):
        """Class to serve as a handling thread to handle each new client
             that connects to the indexer."""
        Thread.__init__(self)
        self.threadId= threadId
        self.cltSock= cltSock
        self.indexPtr= indexPtr
        self.sessionSecsRemaining= MAX_SESSION_SECS
        self.lastActionTimestamp= time.time()
    
    def run(self):
        print "Starting new clt thread"
        try:
            while self.isSessionAlive():
                cmd= self.cltSock.recv(MAX_PKT_BYTES)
                if len(cmd) == 0:
                    print "Caught EOF on client thread %d" % self.threadId
                    break
                print "Received command: %s" % cmd
                cmdObj= self.parseInput(cmd)
                if cmdObj == None:
                    print "Received malformed command from thr %d, exiting" % self.threadId
                    self.cltSock.send("ERROR\n")
                    break
                #Done last to not count server work time in the session's duration (fairness)
                self.updateSessionTimeout()
        except Exception as e:
            errMsgTup= (e.__class__.__name__, self.threadId, e)
            print "Caught exception <%s> from client thread %d: %s" % errMsgTup
        print "Shutting down client thread %d" % self.threadId
        try:
            self.cltSock.shutdown(socket.SHUT_RDWR)
            self.cltSock.close()
        except:
            pass
        print "Ending client thread %d" % self.threadId

    def updateSessionTimeout(self):
        """Reduces the remaining time in this client's session by subtracting
             the difference between the last action timestamp and now."""
        print "About to reduce TTL of session"
        self.sessionSecsRemaining-= time.time() - self.lastActionTimestamp
        self.lastActionTimestamp= time.time()
        print "%f secs remaining in session" % self.sessionSecsRemaining

    def isSessionAlive(self):
        """Returns: True if the session has not expired; False otherwise."""
        return self.sessionSecsRemaining > 0.0

    def parseInput(self, s):
        """Returns: IndexCommand object if the command could be successfully
             parsed; None otherwise.
           Precondition: s is a string."""
        print "Attempting to parse input..."
        if not isinstance(s, str):
            return None
        if not re.match(".*\n", s):
            return None
        s= s.rstrip()
        if s.count("|") != 2:
            return None
        (cmd, pkg, deps)= s.split("|")
        #Parse command portion
        cmdHandlerPtr= self.indexPtr.getHandlerPtr(cmd)
        if cmdHandlerPtr == None:
            return None
        #Parse package portion
        if len(pkg) == 0:
            return None
        #Parse dependency portion (optional)
        deps= deps.split(",")
        #Completed command
        return IndexCommand(cmdHandlerPtr, pkg, deps)
        

#---------------------- Server Functions -------------------------
def parseFlags():
    if len(sys.argv) == 1:
        return
    if "debug" in sys.argv:
        global isDebug
        isDebug= True


def createSrvSocket():
    """Returns: server socket object that listens on port PORT_LISTEN and can
         spawn new client sockets upon connection."""
    srvSock= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srvSock.bind((socket.gethostname(), PORT_LISTEN))
    return srvSock


def main():
    print "DEBUG STATE: %s" % (str(isDebug))
    print "Creating server socket..."
    srvSock= createSrvSocket()
    print "Created server socket on %s" % (str(srvSock.getsockname()))
    srvSock.listen(MAX_QUEUED_CONNECTIONS)
    threadNum= 1
    global index
    index= PackageIndex()
    while True:
        print "Listening for connections..."
        (cliSock, addr)= srvSock.accept()
        cliSock.settimeout(MAX_SOCK_TIMEOUT_SECS)
        print "Found new connection, launching handler thread"
        cliThr= IndexThread(threadNum, cliSock, index)
        cliThr.start()
        print "Thread spawned, back to listening..."
        threadNum+= 1
    







if __name__ == "__main__":
    parseFlags()
    main()
