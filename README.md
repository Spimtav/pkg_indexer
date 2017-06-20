# Code Instructions

## Dependencies 

This code was designed and tested on python 2.7.10.  Both scripts in this repo depend on no external software or packages, and can be run as-is on any system running this version of python.

## Usage

```
python indexer.py
```
Optional arguments:

* --debug: prints various debug stats, such as the duration of each API call.

* --localhost: sets the server's bound IP to localhost.

Additionally, there are several constants that relate to networking security that are defined at the top of indexer.py, which may be modified as desired:

* PORT_LISTEN:            the TCP/IP port to bind to and wait for clients on               

* MAX_QUEUED_CONNECTIONS: how many connection requests the server will queue before denying.

    * NOTE: this must be >= the test script's concurrency value, or the harness will fail with an error that the server rejected the connection.

* MAX_SOCK_TIMEOUT_SECS:  if client doesn't respond for this many secs, socket closed      

* MAX_PKT_BYTES:          max bytes read from a packet at once                             

* MAX_SESSION_SECS:       max total time the server will stay connected to one client      

* MAX_ERRORS:             max bad requests server will tolerate b4 disconnecting           

# Package Index Implementation

## Basic Model
To begin, a set of package dependencies can be modeled as a directed graph, where nodes represent individual packages and arrows represent the relation "X depends on Y".  I decided to model the graph as a set of adjacency lists instead of a matrix, because it is expected that the graph will be relatively sparse due to the absence of cycles (more on this later), and therefore will minimize memory use.  

To implement this, the server script defines a class called Index, which comprises a single package index for clients to interact with.  It contains a dictionary that maps package name strs to IndexEntry instances, which allows access to any node in the index in O(1) time.

An IndexEntry represents a single node in the graph, and contains two sets of pointers: forward pointers to this object's dependency nodes, and back pointers to the nodes that depend on it.  Although storing backpointers takes extra memory and complicates insert and removal, it makes removal O(|num_stored_backpointers|) instead of O(|index|) (where the former is a subset of the latter) because you don't have to iterate through all nodes to see which ones point to the node of interest.

An important property of dependency graphs is that they are acyclic.  This is because packages are removed individually, so any packages in a cycle would be impossible to remove.  I enforce this property by running a depth-first search every time a node is reindexed, and rolling back the change if it creates a cycle.  Cycles cannot be generated when new nodes are added, because they have no backpointers.  Therefore, handling the reindexing case is sufficient.

During the DFS, the index caches the results of any fully-traversed node in a memo, which prevents repeat work and drastically improves its runtime. While this is a bit of extra state to maintain, the performance benefits are well worth the extra storage: some performance heavy calls in the DigitalOcean test harness dropped from 10-30sec to 10-50 millisec.

## Thread Safety
Thread safety is achieved in a rudimentary way: by having each API call lock the entire table for its duration.  I built it this way while the system was still in development, because it was easy to implement and understand.  After everything was built, I was planning to migrate to a more fine-grained system where API calls lock only the entries they will need to touch.

However, from both my own testing and from the DigitalOcean testing harness, it turned out that this implementation was not as slow as I was expecting: even the most performance-heavy calls only took in the tens of milliseconds, and the DO harness completed in an average of 7-12 seconds.

After seeing this relatively fast (for Python) speed, I decided to keep the original implementation.  Here are some reasons why I felt this was sufficient:

* We don't have any workload information: doing any kind of optimization requires you to know at least a little bit about the system's average workload.  For example, the index might be read-heavy with only the occasional write, write-mostly, some balance of the two, or something entirely random.  It might make more sense to redesign the code to make the most common operation run most efficiently, which may change the locking implementation and put all of its development work to waste.

* We don't want to prematurely optimize: given that we have no real-world data, it is hard to say what the speed requirements for the system are.  It could be that the speed is fine, in which case it wouldn't be a good use of limited developer resources to improve it if this were a real system.  If it were too slow, however, it would definitely make sense to invest time to improve the locking system.

* Reindexing may be a common operation: this is essentially an extension of the first point, but still relevant.  When reindexing an existing package, the server basically needs to run a depth-first search to ensure that cyclic dependencies are not created.  Given that this has the potential to touch every node in the graph, and we don't know which nodes will be touched without actually running the DFS, this essentially requires locking the entire table upfront.  If this is a common operation in the index's workload, then it is almost pointless to optimize the other calls.

# Design Future-proofing
For this project, I tried to design the code to be as abstract as possible, so that adding new features would be as simple and minimally-invasive as possible.  In particular, I designed the pathway for handling parsed commands to be abstract with regards to each ClientThread.  When a client thread parses a command, it generates a command object that stores all information necessary to make a call on an index: the package name, the dependency list, and a pointer to the appropriate handler function for that index instance.  This makes three things easy: 

1. Adding/subtracting/modifying index commands: just add/delete/change the handler function in the index class, and change the function that gets bound during parsing.

2. Support for alternative data models: consider that we want to modify the server to maintain one private index per client, instead of one global index that anyone can interact with.  With this design, this case is already handled by creating a new Index object, passing it to the client thread, and binding the command object to that index instance's handler function. 

3. Support for alternative computation models: there are various reasons why we would want to not immediately run the handler function.  For example, we might want to aggregate and batch a bunch of calls at once, or reorder them for consistency, or log them somewhere and run meta-analysis, or any number of other reasons.  By generating an object that can be stored and immediately fired off when ready, we can easily add in these features without restructuring the code.

While these features are outside the scope of this project, they might be reasonable things to implement if this were a real product.  Therefore, I feel that structuring the code in such a way is justified.

# Server Security
As with real servers in the wild, this package indexer is designed to mitigate attacks from malicious clients.  There is a concept called the "CIA principle" in system security that helps outline the main properties of a secure system, which briefly are:

1. Confidentiality: a user that interacts with a system cannot learn information that is does not have access to.  For example, the content of other users' emails, or the balance in their bank accounts.

2. Integrity: the system is resistant to attacks that would alter either its functionality or stored information.  For example, use of a hash/checksum can alert a system to unauthorized changes in a packet, and it can then decide to reject the bad data.

3. Availability: the ability for the system to remain operational for users at all times. For example, various software companies' public APIs have rate limits, to prevent users from overwhelming their resources with constant requests.


Because of the system specifications, the former two properties are not applicable to this package indexer.  We do not care about confidentiality, because every user is considered "privileged": that is, the index is public and any user has the ability to view it at any time.  Put another way, there is no private information stored that we would need to design protections around.  Similarly, we do not overtly care about integrity, because any user is able to connect and make changes at any time.  Beyond the obvious step to only allow clients to request commands in the public API, there is no state that we do not consider free game for modifying.

Therefore, most of the security measures the server implements are purposed with keeping the server operational at all times:
    
* <b>Default timeout</b>.  The server automatically closes and cleans up client sockets/threads that do not issue requests for some max time interval.  This prevents an adversary from permanently holding server resources.

* <b>Minimal nonsense tolerance</b>.  The server closes the connection if the client sends too many erroneous requests.  This disincentivizes clients from sending intentionally malformed packets and keeps server resources from being tied up in misbehaving clients.

* <b>Limiting max session length</b>.  The server will automatically close connections that have been active for some maximum duration.  This prevents malicious clients from permanently holding resources by refreshing connections before they timeout.

* <b>Max packet size</b>.  The server will only process at most X bytes of a packet at a time.  This prevents unreasonably large requests from monopolizing system resources.


Additionally, here are some other security measures which I did not implement in this project but would definitely warrant inclusion in a real server.  I did not implement these because they either broke the DigitalOcean testing harness or were nontrivial to implement:

* <b>No repeat connections</b>.  The server may maintain a list of IPs of connected and recently closed clients, and if a client tries to reconnect too soon or open multiple connections at once, the server will close the socket with an error.  This is an attempt to guarantee fairness, so clients that spam requests can't lock out others.

* <b>Max num connections</b>.  The server may only allow some maxumum number of clients to connect at once, to prevent its resources from being exhausted.

* <b>Fuzz protection</b>.  With the help of a fuzzer (tool to generate random inputs with uncommon charcters), the server's parser and other handlers could be hardened to prevent any possible crashes that might result from using strangely formed inputs.

# Future Directions
If this project were to be migrated to production, here are some additional features which I feel would be worthy inclusions:

1. <b>Persistent storage</b>.  This would amount to storing the index on disk in some form (database table, raw file...) periodically, so that it could survive crashes and reboots.  One simple way to do this would be to generate a file with one line per node, where each line contains that node's dependencies and dependees.  It might be slow to burden the server with this on every call, so it could do an expensive full write every X calls and store the most recent Y instructions separately in a smaller log as they happen.  The commands in the smaller log could then be played back on top of the most recent index file to get the most recent state (ie. basically the ARIES protocol in database crash recovery).

2. <b>Multiple indices</b>.  This project implements a single index that supports calls from an arbitrary number and identity of clients.  Each user might want their own index to play around with, so it might make sense to scale the code to support N separate indices.  This is easily achieved in the code as mentioned above, and would just require some way of pairing clients to indices.  It may also make sense to implement some sort of authentication system, to ensure clients can't modify each others' indices.  This would also require additional design work to ensure data integrity, as now some state is considered private and we must enforce this property.
