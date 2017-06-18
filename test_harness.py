#test_client.py
"""Dummy client to test initial network capabilities of the indexer."""

import sys
import time
import socket
from threading import Thread

NUM_ARGS= 2
MAX_PKT_BYTES= 1024
RESP_ERR= "ERROR\n"
MAX_TEST_DISPLAY_CHARS= 64


#----------------------- Testing Suite ---------------------------
class Result(object):
    def __init__(self, testStr):
        self.testStr= testStr
        self.passed= False


class Client(Thread):
    def __init__(self, ip, port, msg, expected, returnObj):
        Thread.__init__(self)
        self.ip= ip
        self.port= port
        self.msg= msg
        self.expected= expected
        self.returnObj= returnObj
    
    def run(self):
        try:
            cliSock= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cliSock.connect((self.ip, self.port))
            cliSock.send(self.msg)
            status= cliSock.recv(MAX_PKT_BYTES)
            self.returnObj.passed= status == self.expected
        except:
            pass
        try:
            cliSock.shutdown(socket.SHUT_RDWR)
            cliSock.close()
        except:
            pass



#---------------------- Script Functions -------------------------
def showUsage():
    print "Usage: python test_client.py <ip> <port>"


def argsValid():
    try:
        assert(len(sys.argv) == (NUM_ARGS + 1))
        socket.inet_aton(sys.argv[1])
        int(sys.argv[2])
    except:
        return False
    return True


def testBadCmds():
    print "Testing bad commands..."
    failTests= [
        "x",
        "no pipelines",
        "onepipe|",
        "INDEX|",
        "INDEX|package",
        "INDEX|package|",
        "FAKE|package|\n",
        "INDEX||\n",
        "index|package|\n",
        " INDEX|package|\n",
        "INDEX|package|dep1|dep2\n",
        "|package|deps\n",
        "|package|\n",
        "||\n",
        "INDEX|package|derp" + ",derp"*1000 + "\n"
    ]
    results= runTests(failTests)
    return results


def runTests(tests):
    results= []
    cliThrs= []
    for i in range(len(tests)):
        results.append(Result(tests[i]))
        cliThrs.append(Client(ip, port, tests[i], RESP_ERR, results[i]))
        cliThrs[i].start()
    for thr in cliThrs:
        thr.join()
    numPasses= 0
    for result in results:
        didPass= "FAIL"
        if result.passed:
            didPass= "PASS"
            numPasses+= 1
        result.testStr= result.testStr.strip()
        if len(result.testStr) > MAX_TEST_DISPLAY_CHARS:
            result.testStr= result.testStr[:MAX_TEST_DISPLAY_CHARS] + " ..."
        print "    %s: \"%s\"" % (didPass, result.testStr)
    print "Passed %d/%d tests" % (numPasses, len(tests))
    return (numPasses, len(tests))


def main():
    global ip, port
    ip= sys.argv[1]
    port= int(sys.argv[2])
    testFuncs= [
        testBadCmds
    ]
    numPasses= 0
    numTests= 0
    print "Running test suite:\n"
    for testFunc in testFuncs:
        results= testFunc()
        numPasses+= results[0]
        numTests+= results[1]
    print "\nAll tests concluded"
    print "Passed %d/%d tests in total" % (numPasses, numTests)

if __name__ == "__main__":
    if argsValid():
        main()
    else:
        showUsage()
