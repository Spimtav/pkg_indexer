#test_client.py
"""Dummy client to test initial network capabilities of the indexer."""

import sys
import time
import socket
from threading import Thread

NUM_ARGS= 2
MAX_PKT_BYTES= 1024
MAX_TEST_DISPLAY_CHARS= 64
MAX_SOCK_TIMEOUT_SECS= 4.0#60.0
MAX_SESSION_SECS= 20.0#120.0

RESP_OK= "OK\n"
RESP_FAIL= "FAIL\n"
RESP_ERR= "ERROR\n"


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


def runAPITests(tests, canParallel=False, suppressTests=False, suppressSummary=False):
    results= []
    cliThrs= []
    for i in range(len(tests)):
        (test, expected)= tests[i]
        results.append(Result(test))
        cliThrs.append(Client(ip, port, test, expected, results[i]))
        cliThrs[i].start()
        if not canParallel:
            cliThrs[i].join()
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
        if not suppressTests:
            print "    %s: \"%s\"" % (didPass, result.testStr)
    if not suppressSummary:
        print "Passed %d/%d tests" % (numPasses, len(tests))
    return (numPasses, len(tests))


def cleanupIndex(tests, suppressOutput=False):
    delOrder= []
    for test in tests:
        if test[1] == RESP_OK and "INDEX" in test[0]:
            delCmd= "REMOVE|" + ("|".join(test[0].split("|")[1:]))
            delOrder.insert(0, delCmd)
    results= []
    cliThrs= []
    for i in range(len(delOrder)):
        results.append(Result(delOrder[i]))
        cliThrs.append(Client(ip, port, delOrder[i], RESP_OK, results[i]))
        cliThrs[i].start()
        cliThrs[i].join()
    for result in results:
        if not result.passed and not suppressOutput:
            print "    ERROR: failed to remove testStr \"%s\"" % result.testStr


def testBadCmds():
    print "\nTesting bad commands..."
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
    for pos in range(len(failTests)):
        failTests[pos]= (failTests[pos], RESP_ERR)
    results= runAPITests(failTests, canParallel=True)
    return results


def testIndex():
    print "\nTesting basic index commands..."
    indexTests= [
        ("INDEX|A|\n", RESP_OK),
        ("INDEX|B|\n", RESP_OK),
        ("INDEX|C|\n", RESP_OK),
        ("INDEX|D|A,B,C\n", RESP_OK),
        ("INDEX|E|X\n", RESP_FAIL),
        ("INDEX|E|D,A\n", RESP_OK),
    ]
    results= runAPITests(indexTests)
    cleanupIndex(indexTests)
    return results


def testRemove():
    print "\nTesting basic remove commands..."
    inputs= [
        ("INDEX|A|\n", RESP_OK),
        ("INDEX|B|\n", RESP_OK),
        ("INDEX|C|\n", RESP_OK),
        ("INDEX|D|A,B,C\n", RESP_OK),
        ("INDEX|E|D,A\n", RESP_OK),
    ]
    runAPITests(inputs, suppressTests=True, suppressSummary=True)
    remTests= [
        ("REMOVE|X|\n", RESP_OK),
        ("REMOVE|D|\n", RESP_FAIL),
        ("REMOVE|A|\n", RESP_FAIL),
        ("REMOVE|B|\n", RESP_FAIL),
        ("REMOVE|C|\n", RESP_FAIL),
        ("REMOVE|E|\n", RESP_OK),
        ("REMOVE|E|\n", RESP_OK),
        ("REMOVE|A|\n", RESP_FAIL),
        ("REMOVE|B|\n", RESP_FAIL),
        ("REMOVE|C|\n", RESP_FAIL),
        ("REMOVE|D|\n", RESP_OK),
        ("REMOVE|D|\n", RESP_OK),
        ("REMOVE|A|\n", RESP_OK),
        ("REMOVE|B|\n", RESP_OK),
        ("REMOVE|C|\n", RESP_OK),
        ("REMOVE|A|\n", RESP_OK),
        ("REMOVE|B|\n", RESP_OK),
        ("REMOVE|C|\n", RESP_OK)
    ]
    results= runAPITests(remTests)
    return results


def testQuery():
    print "\nTesting basic query commands..."
    results= []
    queryTests1= [
        ("QUERY|A|\n", RESP_FAIL),
        ("QUERY|B|\n", RESP_FAIL),
        ("QUERY|C|\n", RESP_FAIL),
        ("QUERY|D|\n", RESP_FAIL),
        ("QUERY|E|\n", RESP_FAIL),
        ("QUERY|X|\n", RESP_FAIL),
        ("QUERY|Y|\n", RESP_FAIL),
        ("QUERY|Z|\n", RESP_FAIL)
    ]
    results.append(runAPITests(queryTests1, suppressSummary=True))
    inputs= [
        ("INDEX|A|\n", RESP_OK),
        ("INDEX|B|\n", RESP_OK),
        ("INDEX|C|\n", RESP_OK),
        ("INDEX|D|A,B,C\n", RESP_OK),
        ("INDEX|E|D,A\n", RESP_OK),
    ]
    runAPITests(inputs, suppressTests=True, suppressSummary=True)
    queryTests2= [
        ("QUERY|A|\n", RESP_OK),
        ("QUERY|B|\n", RESP_OK),
        ("QUERY|C|\n", RESP_OK),
        ("QUERY|D|\n", RESP_OK),
        ("QUERY|E|\n", RESP_OK),
        ("QUERY|X|\n", RESP_FAIL),
        ("QUERY|Y|\n", RESP_FAIL),
        ("QUERY|Z|\n", RESP_FAIL)
    ]
    results.append(runAPITests(queryTests2, suppressSummary=True))
    cleanupIndex(inputs)
    results.append(runAPITests(queryTests1, suppressSummary=True))
    numPassed= 0
    numTotal= 0
    for result in results:
        numPassed+= result[0]
        numTotal+= result[1]
    print "Passed %d/%d tests" % (numPassed, numTotal)
    return (numPassed, numTotal)


def testCycles():
    cycleTests= [
        ("INDEX|A|\n", RESP_OK),
        ("INDEX|B|\n", RESP_OK),
        ("INDEX|C|\n", RESP_OK),
        ("INDEX|A|A\n", RESP_FAIL),
        ("INDEX|B|B\n", RESP_FAIL),
        ("INDEX|C|C\n", RESP_FAIL),
        ("INDEX|A|B,A\n", RESP_FAIL),
        ("INDEX|A|A,B,C\n", RESP_FAIL),
        ("INDEX|A|B,C,A\n", RESP_FAIL),
        ("INDEX|D|A\n", RESP_OK),
        ("INDEX|A|D\n", RESP_FAIL),
        ("INDEX|E|B,C\n", RESP_OK),
        ("INDEX|B|E\n", RESP_FAIL),
        ("INDEX|C|E\n", RESP_FAIL),
        ("INDEX|F|A,D\n", RESP_OK),
        ("INDEX|A|F\n", RESP_FAIL),
        ("INDEX|D|F\n", RESP_FAIL),
        ("INDEX|G|D,E\n", RESP_OK),
        ("INDEX|A|G\n", RESP_FAIL),
        ("INDEX|D|G\n", RESP_FAIL),
        ("INDEX|B|G\n", RESP_FAIL),
        ("INDEX|C|G\n", RESP_FAIL),
        ("INDEX|G|E\n", RESP_OK),
        ("INDEX|A|G\n", RESP_OK),
        ("INDEX|B|F\n", RESP_FAIL),
        ("INDEX|C|F\n", RESP_FAIL),
        ("INDEX|B|A\n", RESP_FAIL),
        ("INDEX|G|F\n", RESP_FAIL),
        ("INDEX|G|A\n", RESP_FAIL),
        ("INDEX|E|F\n", RESP_FAIL),
        ("INDEX|A|\n", RESP_OK)
    ]
    results= runAPITests(cycleTests)
    cleanupIndex(cycleTests, suppressOutput=True)
    return results


def testMaxSessionLen():
    print "\nTesting session duration..."
    timeInSession= 0.0
    sleepDuration= MAX_SOCK_TIMEOUT_SECS - 0.5
    try:
        cliSock= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliSock.connect((ip, port))
        while True:
            cliSock.send("QUERY|package|\n")
            time.sleep(sleepDuration)
            timeInSession+= sleepDuration
    except:
        pass
    try:
        cliSock.shutdown(socket.SHUT_RDWR)
        cliSock.close()
    except:
        pass
    didPass= timeInSession >= MAX_SESSION_SECS
    displayMsg= "FAIL"
    if didPass:
        displayMsg= "PASS"
    displayTup= (displayMsg, timeInSession, MAX_SESSION_SECS)
    print "    %s: %f secs in session of %f max secs" % displayTup
    print "Passed %d/%d tests" % (didPass, 1)
    return (didPass, 1)


def main():
    global ip, port
    ip= sys.argv[1]
    port= int(sys.argv[2])
    testFuncs= [
        #testBadCmds,
        #testMaxSessionLen,
        #testIndex,
        #testRemove,
        #testQuery,
        testCycles
    ]
    numPasses= 0
    numTests= 0
    print "Running test suite:"
    for testFunc in testFuncs:
        results= testFunc()
        numPasses+= results[0]
        numTests+= results[1]
    print "\n" + ("=" * 15)
    print "All tests concluded"
    print "Passed %d/%d tests in total" % (numPasses, numTests)
    print "=" * 15


if __name__ == "__main__":
    if argsValid():
        main()
    else:
        showUsage()
