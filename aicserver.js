/**
 * Module dependencies.
 */

var express = require('express')
//  , routes = require('./routes')
//  , user = require('./routes/user')
  , http = require('http')
  , child_process = require('child_process')
  , fs = require('fs')
  , path = require('path');

var aicsvr = require('./dblibs.js');
var temp = require('temp');
var crypto = require('crypto');
var async = require('async');
var open = require('open');
var app = express();

var filename_db = 'db/datastore.db';
var table_db = 'processed_data';
var table_model = 'saved_model';
var port_number = 8091;
var accept_url = 'result';
var error_url = 'index';
var pure_server = false;
var admin_host = 'localhost';
var server = null;

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

/** rename the name of temporary file as having extension of original file
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

/** Remove temporary files */
function __remove_temporary_files(filenames) {
  if (typeof filenames === 'string') {
    filenames = [filenames];
  }
  for (var i = 0; i < filenames.length; i++) {
    if (typeof filenames !== 'undefined' && filenames[i] !== null && fs.existsSync(filenames[i])) {
      console.log("REMOVING " + filenames[i]);
      fs.unlink(filenames[i]);
    }
  }
}

/**
  Process uploaded data at top path using POST method.
  The process execute prediction and save the results in database.
  If the calculation finished, users can download data from the databse using their unique key.
**/
function process_data(req, res) {
  if (__verbose) {
    process.stderr.write('uploading\n');
  }
  if (typeof req.files === 'undefiend') {
    display_error("no files contained");
    return;
  }

//  var format = req.body.format;
  var options;
  // console.log('MODE: ' + req.body.mode);
  // for (var p_ in req.files) {
  //   console.log(p_);
  // }
  //
  // console.log("FILES");
  // console.log(req.files);

  if (req.body.mode === 'predict') {
    // calculation with preset data
  //  console.log(req.files.predictionfile);
    var analysisfile = __rename_file_with_extension(req.files.analysis);
//    console.log(analysisfile);
//    process.exit();
    //var modelfile = 'sqlite:' + filename_db + ':' + table_model + ':' + req.body.model;
    options = [python_program, '-i', analysisfile];
    //res.end();
//    console.log(options);
    aicsvr.save_model_file(filename_db, table_db, req.body.model,
      function(err, filename_tmp) {
//        console.log(filename_tmp);
        if (err) {
          res.writeHead(500, {'Content-Type':'text/plain'});
          res.write('could not retrieve models having id:' + req.body.model);
          res.end();
        } else {
          options.push('--model');
          options.push(filename_tmp);
          __spawn_rfprogram(options, function(err, key) {
            __respond_to_client(err, key, res);
          });
//          __remove_temporary_files([filename_tmp]);
        }
      }
    );
  } else {
  //  console.log(req.files.training);
    var trainingfile = __rename_file_with_extension(req.files.training);
    var analysisfile = __rename_file_with_extension(req.files.analysis);
    if (typeof analysisfile === 'undefined') {
      analysisfile = null;
    } else {
//      console.log(analysisfile);
//      analysisfile = null;
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

    var options = [python_program, '-t', trainingfile,
    '-d', tree_depth, '-n', num_trees, '-F', field_out, '-I', field_id];
    //, '--verbose'];
    if (typeof iteration !== 'undefined' && 1 < iteration && iteration <= 1000) {
      options = options.concat(['--iteration', iteration])
    }
    if (analysisfile !== null) {
      options = options.concat(['-i', analysisfile]);
    }
    __spawn_rfprogram(options, function(err, key) {
//      console.log('received key ' + key);
      __respond_to_client(err, key, res);
      // remove temporary files
  //    __remove_temporary_files([trainingfile, analysisfile]);
    });
  }
}

function __respond_to_client(err, key, res) {
  // console.log('responding');
  // console.log(key);
  if (err) {
    send_json_message(res, {error:null, key:key});
  } else {
    res.writeHead(301, {location:'/result?id=' + key});
    res.end();
  }
}

function __spawn_rfprogram(options, callback) {
//  console.log(analysisfile);
  // This process reserve a unique key before calculation.
//  var format = 'json';
  aicsvr.generate_unique_key(filename_db, table_db, function(err, key) {
    if (err) {
//      if (format === 'json') {
        send_json_message(res, {error:'FAILED_TO_INSERT_ENTRY_TO_DATABASE'});
      // } else {
      //   res.render(filename_error);
      // }
    } else {
      if (__verbose) {
        options = options.concat(['--verbose']);
      }
      options.push('--key');
      options.push(key);
      var filename_output = temp.path({suffix:'.json'});
      options.push('-o');
      options.push(filename_output);

//      console.log(options.join(' '));
//      console.log('CALLBACK with ' + key);
      callback(null, key);

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
        if (err) {
          if (__verbose) {
            process.stderr.write('ERROR in execution : ' + err + '\n');
          }
//          callback(err, key);
        } else {
          if (__verbose) {
            process.stderr.write('finished ' + key + ', saving to database\n');
          }
          var data = fs.readFile(filename_output, function(err, data) {
            //__remove_temporary_files([filename_output]);
            if (err) { // error
              process.stderr.write('failed to load data from ' + filename_output + '\n');
              aicsvr.save_data(filename_db, table_db, {key:key, state:-1}, function(err) {
                if (err) {
                  process.stderr.write('failed to set failure flag on ' + key + ' : ' + err + '\n');
                }
              });
//              callback(err, key);
            } else {
              process.stderr.write('saving ' + filename_output + ' to database\n');
              aicsvr.save_data(filename_db, table_db, {data:data, key:key, state:1}, function(err) {
                if (err) {
                  process.stderr.write('failed to save data ' + key + '\n');
                } else {
                  if (__verbose) {process.stderr.write('results were saved into database\n');}
                }
//                callback(err, key);
              });
            }});
          }});



      // if (format == 'json') {
      //   send_json_message(res, {error:null, key:key});
      // } else {
      //   res.writeHead(301, {location:'/result?id=' + key});
      //   // var params = get_parameters();
      //   // params.key = key;
      //   // res.render(accept_url, params);
      // }
      // res.end();
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

/**
Provide name and keys
*/
function get_models(req, res) {
  // sqlite3 : select id, name from models
//  var models = {};
  aicsvr.get_models(filename_db, table_model, function(err, models) {
//    console.log('recieved from db');
//    console.log(models);
    if (err) {
      res.writeHead(500, {'Content-Type':'text/plain'});
      res.write('could not retrieve models');
      res.end();
    } else { //if (row === null) {
      res.writeHead(200, {'Content-Type':'aplication/json'});
      res.write(JSON.stringify(models));
      res.end();
    // } else {
    //   models[row.id] = row.name;
    }
  });
};

function get_model_fields(req, res) {
  var model_id = req.query['id'];
  aicsvr.get_model_fields(filename_db, table_model, model_id,
    function(err, fields) {
      if (err) {
//        console.log(err);
        res.writeHead(500, {'Content-Type':'text/plain'});
        res.write('could not retrieve fields');
        res.end();
      } else {
        res.writeHead(200, {'Content-Type':'aplication/json'});
        res.write(JSON.stringify(fields));
        res.end();
      }
    });

};

// save or remove
function manage_model(req, res) {
  var model_id = req.query['model_id'];
  var command = req.query['command'];
  res.end();
};

function predict_data(req, res) {
  var model_id = req.query['id'];
  res.render('/');
};

function save_model(req, res) {
  var model_id = req.body.key;
//  console.log(req.body.key);
//  console.log(req.body.name);
  if (!model_id) {
    res.writeHead(500, {'Content-Type':'text/plain'});
    res.write('No model ID is given');
    res.end();
    return;
  }
  var name = req.body.name;
  if (!name) {
    var date = dateformat(Date(), 'isoUtcDateTime');
    name = 'Unnamed model ' + (new Date()).toString();
  }
  aicsvr.save_model(filename_db, model_id, name, table_db, table_model,
    function(err) {
      if (err) {
        res.writeHead(500, {'Content-Type':'text/plain'});
        res.write('Commitment of ' + model_id + ' failed');
        res.end();
      } else {
        res.writeHead(200, {'Content-Type':'text/plain'});
        res.write(model_id + ' commited');
        res.end();
      }
    });
};

var admin_host
function process_command(req, res) {
  var cmd = req.query['cmd'];
  var message = cmd;
  var callback = null;
  if (cmd === 'shutdown') {
    var host = req.headers['host'];
    if (host === admin_host + ':' + port_number) {
      callback = function() {
        process.stderr.write('exitting\n');
        process.exit();
      }
      message = 'process shutdown\n\n';
    }
  }
  res.writeHead(200, {'Content-Type':'text/plain'});
  res.write(message);
  res.end();
  if (callback) {
    setTimeout(
      function() {
        callback(null, message);
      }, 1000);
  }
};


/////////////////////////////////////
////// Server configurations ////////
/////////////////////////////////////

/**
Commands
 --admin-host [host_name] : administration host name
 --server                 : do not launch browser
 --db                     : database path (SQLite)
 --port [number]          : port number
 --verbose                : verbosity
**/

for (var i = 0; i < process.argv.length; i++) {
  var arg = process.argv[i];
  if (arg === '--verbose') {
    __verbose = true;
  } else if (arg === '--port') {
    port_number = parseInt(process.argv[i + 1], 10);
    i++;
  } else if (arg === '--db') {
    filename_db = process.argv[++i];
  } else if (arg === '--server') {
    pure_server = true;
  } else if (arg === '--admin-host') {
    admin_host = process.argv[++i];
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
app.get('/models', get_models);
app.get('/feature', get_model_fields);
app.get('/admin', process_command);

app.post('/', process_data);
app.post('/predict', predict_data);
app.post('/save', save_model);

aicsvr.verbose(__verbose);

server = http.createServer(app).listen(app.get('port'), function(){
  aicsvr.setup_db(filename_db, table_db, table_model, function(err) {
    if (err) {
      console.log(err);
      console.log('failed to set up database');
      process.exit(0);
    }
  });
  if (__verbose) {
    console.log("Express server listening on port " + app.get('port'));
  }
  if (!pure_server) {
    open('http://localhost:' + port_number + '/');
  }
});
