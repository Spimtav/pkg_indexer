#indexer.py
"""Package Indexer server code.
Usage: python indexer.py
Optional Args:
  --debug       prints various debug stats, such as the duration of each API call.
  --localhost   sets the server's bound IP to localhost instead of the default network IP."""

import re
import sys
import time
import socket
from threading import Lock, Thread

#-------------------------- Constants -----------------------------
PORT_LISTEN= 8080           #the TCP/IP port to bind to and wait for clients on
MAX_QUEUED_CONNECTIONS= 100 #how many connection requests the server will queue before denying
                            #NOTE: this must be >= the test script's concurrency value
MAX_SOCK_TIMEOUT_SECS= 30.0 #if client doesn't respond for this many secs, socket closed
MAX_PKT_BYTES= 1024         #max bytes read from a packet at once
MAX_SESSION_SECS= 120.0     #max total time the server will stay connected to one client
MAX_ERRORS= 100000          #max bad requests server will tolerate b4 disconnecting

RESP_OK= "OK\n"
RESP_FAIL= "FAIL\n"
RESP_ERR= "ERROR\n"


#------------------------- Global State ---------------------------
isDebug= False
useLocalhost= False
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
        self.entries= {}
        self.lock= Lock()
        self.cycleMemo= {}

    def __str__(self):
        """Returns: repr of the index as a str, for visual debugging."""
        s= "EntryMap:\n    %s\nEntries:" % str(self.entries)
        for entry in [self.entries[name] for name in self.entries]:
            s+= "\n    %s:" % entry.getName()
            s+= "\n        Dependencies:"
            for dependency in entry.getDependencies():
                s+= "\n            %s" % dependency.getName()
            s+= "\n        Dependees:"
            for dependee in entry.getDependees():
                s+= "\n            %s" % dependee.getName()
        return s
    
    def getLock(self):
        """Returns: this index's lock object, for concurrency control."""
        return self.lock

    def getHandlerPtr(self, cmd):
        """Returns: pointer to function to handle the given command if it
             exists in this index instance; None otherwise."""
        if cmd not in self.commands:
            return None
        return self.commands[cmd]

    def hasCycle(self, root, visited):
        """Returns: True if there is a cycle in the graph containing the
             root node; False otherwise.
           Precondition: root is an IndexEntry instance; visited is a map of
             IndexEntry->bool.
           Note: using DFS to find the cycle."""
        if root in self.cycleMemo:
            return self.cycleMemo[root]
        if root in visited:
            return True
        visited[root]= True
        cycleFound= False
        for child in root.dependees:
            foundCycle= self.hasCycle(child, dict(visited))
            if foundCycle:
                cycleFound= True
                break
        self.cycleMemo[root]= cycleFound
        return cycleFound

    def updateExisting(self, entryPtr, newDeps):
        """Attempts to update the index to reflect <newDeps> as <entryPtr>'s
             new dependency list.  Fails if this would create a cyclic
             dependency.
           Returns: RESP_OK if updating was successful; RESP_FAIL otherwise 
             (ie: cycle created).
           Precondition: entryPtr is an IndexEntry instance; newDeps is a
             list of strs."""
        newDepPtrs= []
        for dep in newDeps:
            if dep == entryPtr.getName():
                return RESP_FAIL
            newDepPtrs.append(self.entries[dep])
        #Efficiency: only check NEW packages, because others are known good
        existingPtrs= {}
        onlyNewPtrs= []
        for dep in entryPtr.getDependencies():
            existingPtrs[dep]= 1
        for dep in newDepPtrs:
            if dep not in existingPtrs:
                onlyNewPtrs.append(dep)
        oldDeps= entryPtr.dependencies
        entryPtr.dependencies= onlyNewPtrs
        #Check for cycles in new deps only
        for dep in oldDeps:
            dependees= dep.getDependees()
            dependees.pop(dependees.index(entryPtr))
        for dep in newDepPtrs:
            dep.getDependees().append(entryPtr)
        foundCycle= self.hasCycle(entryPtr, {})
        self.cycleMemo= {}
        if foundCycle:
            entryPtr.dependencies= oldDeps
            for dep in oldDeps:
                dep.getDependees().append(entryPtr)
            for dep in newDepPtrs:
                dependees= dep.getDependees()
                dependees.pop(dependees.index(entryPtr))
            return RESP_FAIL
        entryPtr.dependencies= newDepPtrs
        return RESP_OK

    def handleIndex(self, pkg, deps):
        """Returns: RESP_OK if pkg was successfully added to or updated in the index;
             RESP_FAIL otherwise.
           Precondition: pkg is a str; deps is a list of str."""
        with self.lock:
            depPtrs= []
            for dep in deps:
                if dep not in self.entries:
                    return RESP_FAIL
                depPtrs.append(self.entries[dep])
            if pkg in self.entries:
                return self.updateExisting(self.entries[pkg], deps)
            newEntry= IndexEntry(pkg, depPtrs, [])
            self.entries[pkg]= newEntry
            for depPtr in depPtrs:
                depPtr.getDependees().append(newEntry)
            return RESP_OK
    
    def handleRemove(self, pkg, deps):
        """Returns: RESP_OK if pkg isn't in the index or could be removed
             successfully; RESP_FAIL otherwise.
           Precondition: pkg is a str; deps is a list of str."""
        with self.lock:
            if pkg not in self.entries:
                return RESP_OK
            entry= self.entries[pkg]
            if len(entry.getDependees()) > 0:
                return RESP_FAIL
            for depPtr in entry.getDependencies():
                dependees= depPtr.getDependees()
                dependees.pop(dependees.index(entry))
            del self.entries[pkg]
            return RESP_OK
    
    def handleQuery(self, pkg, deps):
        """Returns: RESP_OK if <pkg> has an entry in the index; RESP_FAIL otherwise.
           Precondition: pkg is a str; deps is a list of str."""
        with self.lock:
            if pkg not in self.entries:
                return RESP_FAIL
            return RESP_OK


class IndexEntry(object):
    def __init__(self, name, dependencies=[], dependees=[]):
        """Class to model a node in the dependency graph.  Contains two lists:
             -dependencies: forward ptrs to the nodes this depends on
             -dependees: back ptrs to the nodes that depend on this node."""
        self.name= name
        self.dependencies= dependencies
        self.dependees= dependees
        self.lock= Lock()

    def getName(self):
        """Returns: str name of the package this node represents."""
        return self.name

    def getDependencies(self):
        """Returns: list of IndexEntry objs that is self.dependencies."""
        return self.dependencies

    def getDependees(self):
        """Returns: list of IndexEntry objs that is self.dependees."""
        return self.dependees
    
    def getLock(self):
        """Returns: Lock object for this instance."""
        return self.lock
        

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
        return self.handlerFunc(self.packageName, self.dependencies)


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
        self.numFailures= 0
    
    def run(self):
        try:
            while self.isSessionAlive():
                cmd= self.cltSock.recv(MAX_PKT_BYTES)
                if len(cmd) == 0:
                    break
                cmdObj= self.parseInput(cmd)
                if cmdObj == None:
                    self.cltSock.send(RESP_ERR)
                    self.numFailures+= 1
                    continue
                start= time.time()
                result= cmdObj.runCommand()
                if isDebug:
                    info= (cmd.split("|")[0], (time.time()-start) * 1000)
                    print "Elapsed time for call %s: %f ms" % info
                self.cltSock.send(result)
                #Done last to not count server work time in the session's duration (fairness)
                self.updateSessionTimeout()
        except Exception as e:
            errMsgTup= (e.__class__.__name__, self.threadId, e)
            print "Caught exception <%s> from client thread %d: %s" % errMsgTup
        try:
            self.cltSock.shutdown(socket.SHUT_RDWR)
            self.cltSock.close()
        except:
            pass

    def updateSessionTimeout(self):
        """Reduces the remaining time in this client's session by subtracting
             the difference between the last action timestamp and now."""
        self.sessionSecsRemaining-= time.time() - self.lastActionTimestamp
        self.lastActionTimestamp= time.time()

    def isSessionAlive(self):
        """Returns: True if the session has not expired; False otherwise."""
        aliveChecks= [
            self.sessionSecsRemaining > 0.0,
            self.numFailures <= MAX_ERRORS
        ]
        isAlive= reduce(lambda x,y: x and y, aliveChecks)
        return isAlive


    def parseInput(self, s):
        """Returns: IndexCommand object if the command could be successfully
             parsed; None otherwise.
           Precondition: s is a string."""
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
        deps= [dep for dep in deps if len(dep) > 0]
        deps= list(set(deps))
        #Completed command
        return IndexCommand(cmdHandlerPtr, pkg, deps)


#---------------------- Server Functions -------------------------
def parseFlags():
    if len(sys.argv) == 1:
        return
    if "--debug" in sys.argv:
        global isDebug
        isDebug= True
    if "--localhost" in sys.argv:
        global useLocalhost
        useLocalhost= True


def createSrvSocket():
    """Returns: server socket object that listens on port PORT_LISTEN and can
         spawn new client sockets upon connection."""
    srvSock= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ip= socket.gethostname()
    if useLocalhost:
        ip= "127.0.0.1"
    srvSock.bind((ip, PORT_LISTEN))
    return srvSock


def main():
    print "Creating server socket..."
    srvSock= createSrvSocket()
    print "Created server socket on %s" % (str(srvSock.getsockname()))
    srvSock.listen(MAX_QUEUED_CONNECTIONS)
    threadNum= 1
    global index
    index= PackageIndex()
    while True:
        (cliSock, addr)= srvSock.accept()
        cliSock.settimeout(MAX_SOCK_TIMEOUT_SECS)
        cliThr= IndexThread(threadNum, cliSock, index)
        cliThr.start()
        threadNum+= 1




if __name__ == "__main__":
    parseFlags()
    main()
