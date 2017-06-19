# Networking Design



# Code Modularity
Things I did to make prod updating really really simple:

* <b>Abstract command handling</b>.  I designed the code to make handling parsed commands as abstract as possible with respect to the ClientThread.  Basically, when a client thread parses a command, it generates a command object that stores both the package and dependencies, and also a pointer to the handler function.  This makes three things easy: 

    1. Adding/subtracting/modifying index commands: just add/delete/change the function in the index class, and change the function that gets bound during parsing.

    2. Support for alternative data models: consider that we want to modify the project to support 1 index per client, instead of one global index that anyone can see/update.  With this design, this case is already handled by just passing in the appropriate index object to the client thread upon creation, and binding the command object to that index instance's handler function.

    3. Support for alternative computation models: there are various reasons why we would want to not immediately run the handler function.  For example, we might want to aggregate and batch a bunch of calls at once, or reorder them for consistency, or log them somewhere and run meta-analysis, or any number of other reasons.  By generating an object that can be stored and immediately fired off when ready, we can easily add in these features without restructuring the code.

#TODO
(ADD MORE NOTES HERE)
#ENDTODO

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


Additionally, here are some other security measures which I did not implement in this project but would definitely warrant inclusion in a real server.  I did not implement these, because they either broke the DigitalOcean testing harness or were nontrivial to implement:

* <b>No repeat connections</b>.  The server may maintain a list of IPs of connected and recently closed clients, and if a client tries to reconnect too soon or open multiple connections at once, the server will close the socket with an error.  This is an attempt to guarantee fairness, so clients that spam requests can't lock out others.

* <b>Max num connections</b>.  The server may only allow some maxumum number of clients to connect at once, to prevent its resources from being exhausted.

* <b>Fuzz protection</b>.  With the help of a fuzzer (tool to generate random inputs with uncommon charcters), the server's parser and other handlers could be hardened to prevent any possible crashes that might result from using strangely formed inputs.
