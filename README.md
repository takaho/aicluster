# aicluster
Practical examination of machine learning

INSTALLATION

This application depends on following Python (>=2.7 or >3.0) packages.
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

The server starts with "node aicserver" or "forever start aicserver."
The default port of the server is 8091 and you can access the page at the URL http://localhost:8091/.


USAGE

Command line version can be used as following options

usage: rfprediction.py [-h] [-i filename] [-t filename] [-o directory]
                       [-n number] [-d number] [-F field name] [-I field name]
                       [--best filename] [--verbose] [--without-rawdata]
                       [--iteration ITERATION] [--key characters]
                       [--model json file]

optional arguments:
  -h, --help            show this help message and exit
  -i filename           input CSV file
  -t filename           training data
  -o directory          output directory (default out)
  -n number             number of trees
  -d number             maximum depth of decision tree
  -F field name         output column
  -I field name         identifier column
  --best filename       output best tree (PDF)
  --verbose             verbosity
  --without-rawdata     remove rawdata from report
  --iteration ITERATION
                        the number of iteration to estimate weights of
                        parameters
  --key characters      unique ID
  --model json file     JSON filename of model

If you construct prediction trees with given data, use -t option.
Prediction mode is available if you use '--model' option with JSON file generated by this script run with -t option.
-o option specifies output directory having an HTML document, images and a file containing JSON object. The JSON file can be reused to predict other data. If you require only JSON object, set a filename 'xxxx.json' for -o option.

Web server starts with Express framework with Node.js.

usage
node aicserver [--port port_number] [--db database path] [--verbose]

optional arguments:
 --port                port number of service (default 8091)
 --db                  SQLite database path (default db/datastore.db)
 --verbose             verbosity
