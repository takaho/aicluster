# aicluster
Practical examination of AI

This application depends on following Python packages.
- wxPython (for GUI users)
- sklearn
- numpy
- scipy
- pillow (alternative package of Python Imaging Library, version >= 2.6)

Web server requires Javascript environment.
- Node.js
- express
In addition SQLite3 should be installed to manage database and intall it if your environment does not have it.

To install additional packages for web server, run the following command before starting up the service.

 npm install

The server starts with "node aicserver" or "forever start aicserver" if you have the package "forever."
The default port of the server is 8091 and you can access the page at the URL http://localhost:8091/.


