"""Contract tests: the HTTP API between the R client and the Python service.

Both sides are checked against the same example requests (contract/examples/*.json):
- Python (here): every example is valid for the API and accepted in protocol order;
  status codes and error answers are what the client relies on.
- R (contract/r/, `make test-r`): what the client actually sends has the shape of the examples.
A change on one side that the other does not follow breaks a test instead of a sync.
"""
