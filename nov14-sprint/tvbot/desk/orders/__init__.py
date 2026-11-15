"""Paper desk order engine and controls (offline, simulated).

Worker A package for tvbot/desk. Standard library only, Python 3.9.
Nothing here opens a network connection, reads a key or places a real order.
Every fill comes from the in-process FakeBroker and carries "mock": true.
"""
