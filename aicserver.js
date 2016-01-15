/**
 * Module dependencies.
 */

var express = require('express')
  , routes = require('./routes')
  , user = require('./routes/user')
  , http = require('http')
  , child_process = require('child_process')
  , fs = require('fs')
  , path = require('path');

var aicsvr = require('./dblibs.js');
var temp = require('temp');
var crypto = require('crypto');
var temp = require('temp');

var app = express();

var filename_db = 'db/datastore.db';
var table_db = 'processed_data';
var port_number = 8091;
var accept_url = 'result';
var error_url = 'index';

var page_parameters = {title:'aiCluster webservice', author:'Takaho A. Endo', message:null, key:null};
var python_program = 'rfprediction.py'

var __defaults = {num_trees:20, tree_depth:4, field_id:'ID', field_out:'OUT'};
var __verbose = false;

/**
  Clone parameters for index.ejs
**/
function get_parameters() {
  var params = {};
  for (var prop in page_parameters) {
    params[prop] = page_parameters[prop];
  }
  return params;
};

/**
  Display index.ejs with error message
**/
function display_error(res, message) {
  var params = get_parameters();
  params.error = message;
  res.render(error_url, params);
  res.end();
}

/**
  Provide message in JSON format.
**/
function send_json_message(res, message) {
  res.writeHead(200, {'Content-Type':'application/json'});
  res.write(JSON.stringify({message:message}));
  res.end();
};

/**
*/
function __rename_file_with_extension(file) {
  if (file === null || typeof file === 'undefined' || typeof file.name !== 'string' || typeof file.path !== 'string' || file.name === '') {
    return null;
  }
  var filename_org = file.name;
  var filepath = file.path;
  var pos = filename_org.lastIndexOf('.');
  var ext = pos >= 0 ? filename_org.slice(pos) : '.csv';
  var filename_dst = temp.path({suffix:ext});
  fs.rename(filepath, filename_dst);
  return filename_dst;
}

/**
  Process uploaded data at top path using POST method.
  The process execute prediction and save the results in database.
  If the calculation finished, users can download data from the databse using their unique key.
**/
function process_upload(req, res) {
  if (__verbose) {
    process.stderr.write('uploading\n');
  }
  if (typeof req.files === 'undefiend') {
    display_error("no files contained");
    return;
  }

//  console.log(req.files.training);
  var trainingfile = __rename_file_with_extension(req.files.training);
  var analysisfile = __rename_file_with_extension(req.files.analysis);
  if (typeof analysisfile === 'undefined') {
    analysisfile = null;
  } else {
//    console.log(analysisfile);
    analysisfile = null;
  }
  if (trainingfile === null && analysisfile !== null) {
    trainingfile = analysisfile;
    analysisfile = null;
  }
  var num_trees = parseInt(req.body.num_trees);
  var tree_depth = parseInt(req.body.depth);
  var field_id = req.body.idcolumn;//'ID';
  var field_out = req.body.outcolumn;//'OUT';
  var iteration = req.body.iteration;

  // set default values


  if (isNaN(num_trees)) { num_trees = __defaults.num_trees; }
  if (isNaN(tree_depth)) { tree_depth = __defaults.tree_depth; }
  if (typeof field_id !== 'string' || field_id === '') {field_id = __defaults.field_id; }
  if (typeof field_out !== 'string' || field_out === '') { field_out = __defaults.field_out; }

  var format = req.body.format;

//  console.log(analysisfile);

  // This process reserve a unique key before calculation.
  aicsvr.generate_unique_key(filename_db, table_db, function(err, key) {
    if (err) {
      if (format === 'json') {
        send_json_message(res, {error:'FAILED_TO_INSERT_ENTRY_TO_DATABASE'});
      } else {
        res.render(filename_error);
      }
    } else {
      var filename_output = temp.path({suffix:'.json'});
      // var options = [python_program, '--emulate-wait', '4', '--key', key, '-i', filename_uploaded, '-o', filename_output];
      var options = [python_program,'--key', key, '-t', trainingfile, '-o', filename_output,
      '-d', tree_depth, '-n', num_trees, '-F', field_out, '-I', field_id];
      if (__verbose) {
        options = options.concat(['--verbose']);
      }
      //, '--verbose'];
      if (typeof iteration !== 'undefined' && 1 < iteration && iteration < 100) {
        options = options.concat(['--iteration', iteration])
      }
      console.log(options.join(' '));
      if (analysisfile !== null) {
        options = options.concat(['-i', analysisfile]);
      }
      var proc = child_process.spawn('python', options);
      proc.stdout.on('data', function(data) {
        if (__verbose) {
          process.stdout.write(data);
        }
      });
      proc.stderr.on('data', function(data) {
        if (__verbose) {
          process.stderr.write(data);
        }
      });
      proc.stdout.on('close', function(err) {
        if (__verbose) {
          if (err) {
            process.stderr.write('ERROR in execution : ' + err + '\n');
          } else {
            process.stderr.write('finished ' + key + ', saving to database\n');
          }
        }
        var data = fs.readFile(filename_output, function(err, data) {
          if (err) { // error
            process.stderr.write('failed to load data from ' + filename_output + '\n');
            aicsvr.save_data(filename_db, table_db, {key:key, state:-1}, function(err) {
              if (err) {
                process.stderr.write('failed to set failure flag on ' + key + '\n');
              }
            });
          } else {
            aicsvr.save_data(filename_db, table_db, {data:data, key:key, state:1}, function(err) {
              if (err) {
                process.stderr.write('failed to save data ' + key + '\n');
              } else {
                if (__verbose) {process.stderr.write('results were saved into database\n');}
              }
            });
        }});
      });

      if (format == 'json') {
        send_json_message(res, {error:null, key:key});
      } else {
        res.writeHead(301, {location:'/result?id=' + key});
        // var params = get_parameters();
        // params.key = key;
        // res.render(accept_url, params);
      }
      res.end();
    }
  });
}

function retrieve_data(req, res) {
  var data_id = req.query['id'];
  if (data_id) {
    aicsvr.load_data(filename_db, table_db, data_id, function(err, data) {
      if (err) {
        send_json_message(res, err);
      } else {
        //console.log('length = ' + data.length);
        // for (var prop in data) {
        //   console.log(prop);
        // }
        if (data.state == aicsvr.PROCESSING_STATES.READY) { // processing
          send_json_message(res, 'processing');
        } else if (data.state == aicsvr.PROCESSING_STATES.SUCCESS) { // finished
          // reduce data size, removing training data and arrange condition properties
          var cnd = data.condition;
          var sendingdata = {condition:data.condition, field:data.field, forest:data.forest,
            analysisset:data.analysisset, group_label:data.group_label, weight:data.weight,
            prediction:data.prediction, field_id:data.field_id, field_out:data.field_out,
            best_tree:data.best_tree};

          res.writeHead(200, {'Content-Type':'application/json'});
          res.write(JSON.stringify(data));
          res.end();
        } else {
          send_json_message(res, 'error');
        }
      }
    });
  } else {
    var params = get_parameters();
    params['message'] = 'no data given';
    res.render('index', params);
  }
}

function display_results(req, res) {
  var data_id = req.query.id;
  var params = {key:data_id, title:'Results'};
  res.render('visualize', params);
}

/////////////////////////////////////
////// Server configurations ////////
/////////////////////////////////////



for (var i = 0; i < process.argv.length; i++) {
  var arg = process.argv[i];
  if (arg === '--verbose') {
    __verbose = true;
  } else if (arg === '--port') {
    port_number = parseInt(process.argv[i + 1], 10);
    i++;
  } else if (arg === '--db') {
    filename_db = process.argv[++i];
  }
}

app.configure(function(){
  app.set('port', process.env.PORT || port_number);
  app.set('views', __dirname + '/views');
  app.set('view engine', 'ejs');
  app.use(express.favicon(path.join(__dirname, 'public/images/favicon.ico')));
  app.use(express.logger('dev'));
  app.use(express.bodyParser());
  app.use(express.methodOverride());
  app.use(app.router);
  app.use(express.static(path.join(__dirname, 'public')));
});

app.configure('development', function(){
  app.use(express.errorHandler());
});

app.get('/', function(req, res) {
  if (req.query.id) {
    display_results(req, res);
  } else {
    res.render('index', get_parameters());
  }
});

app.get('/retrieve', retrieve_data);
app.get('/result', display_results);

app.post('/', process_upload);

aicsvr.verbose(__verbose);
http.createServer(app).listen(app.get('port'), function(){
  aicsvr.setup_db(filename_db, table_db, null); // set up database first
  console.log("Express server listening on port " + app.get('port'));
});
