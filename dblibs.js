var sqlite3 = require('sqlite3');
var path = require('path');
var fs = require('fs');
var dateformat = require('dateformat');
var temp = require('temp');
var __key_length = 10;
var __verbose = false;
var __states = {SUCCESS:1, READY:0, FAILURE:-1};
var __expire_period = 1000 * 60 * 60 * 24 * 180;
var __default_table_data = 'repository';
var __default_table_model = 'saved_model';
var __key_characters = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

/*****
Table format

processed data
CREATE TABLE __processed_data__ (ID not null primary key, USER, DATE, STATE, DATA blob);

saved data
CREATE TABLE __saved__ (ID not null primary key, NAME, USER, DATE, FIELDS blob, FOREST blob, BEST blob);

*****/

/**
  Recursively create directories for database file
**/
function __create_dir(directory) {
  if (directory.indexOf(path.sep) > 0) {
    __create_dir(path.dirname(directory));
  }
  if (!fs.existsSync(directory)) {
    fs.mkdirSync(directory);
  }
}

/**
  Sanitization of unique keys
**/
function __sanitize_key(key) {
  for (var i = 0; i < key.length; i++) {
    if (__key_characters.indexOf(key[i]) < 0) {
      return key.substr(0, i);
    }
  }
  return key;
}

var __already_created_tables = {};

/**
  Open database connection and call callback function.
  Parameters:
    filename : SQLite filename (default in-memory database)
    table    : SQLite table (default  __default_table_data)
**/
function open_database(filename, table, callback) {
  if (typeof filename === 'undefined') {
    filename = ':memory:';
  } else if (!fs.existsSync(filename)) {
    __create_dir(path.dirname(filename));
  }
  if (typeof table === 'undefined') { table = __default_table_data; }
  if (__verbose) {process.stderr.write('OPEINING : ' + table + '\n'); }
  var db = new sqlite3.Database(filename,
    function(err) {
      db.get('select name from sqlite_master where name=?', table,
        function(err, row) {
          if (err === null) {
            if (!row) {
              if (__already_created_tables[table]) {
                if (__verbose) { process.stderr.write('waiting for ' + table + ' is ready'); }
                setTimeout(function(){open_database(filename, table, callback);}, 100);
              } else {
                if (__verbose) { process.stderr.write('creating table\n'); }
                db.serialize(function() {
                  db.run('create table ' + table + ' (id primary key not null, user, date, state int4, data blob not null)');
                  db.run('create index index_' + table + ' on ' + table + '(id)');
                  db.close();
                  __already_created_tables[table] = true;
                  setTimeout(function(){open_database(filename, table, callback);}, 10);
                });
              }
            } else {
              if (__verbose) { process.stderr.write(table + ' is already ready\n'); }
              __already_created_tables[table] = true;
              callback(null, db);
            }
          } else {
            if (!db) { db.close(); }
            callback(err);
          }
        }
      );
    }
  );
}

/**
  Provide an unique key. If a generate key is stored in database, this function calls itself untile the key is not in the database.
*/
function __provide_unique_key(db, table, key, callback) {
  // rotate key
  var RANDOM_CHARACTERS = __key_characters;
  if (typeof key === 'string') {
    key = key.substr(key.length - __key_length + 1, __key_length - 1);
  } else {
    key = '';
  }
  for (var i = key.length; i < __key_length; i++) {
    key += RANDOM_CHARACTERS.charAt(parseInt(Math.random() * RANDOM_CHARACTERS.length), 10);
  }
  if (__verbose) {
    process.stderr.write('trying ' + key + '\n');
  }
  db.get('select id from ' + table + ' where id=?', key, function(err, row) {
    if (!row) { // unique key found, then a row will be reserved
      db.run('insert into ' + table + ' values(?, ?, ?, ?, ?)', key, '', '', 0, '',
        function(err) {
          if (err) {
            callback(err);
            db.close();
          } else {
            callback(null, key);
          }
        }
      );
    } else { // do again with current key
      setTimeout(function(){ __provide_unique_key(db, table, key, callback); }, 1);
    }
  });
}


/**
  Open database connection and call callback function.
  Parameters:
    filename : SQLite filename (default in-memory database)
    table    : SQLite table (default  )
**/
function open_model_database(filename, table, callback) {
  if (typeof filename === 'undefined') {
    filename = ':memory:';
  } else if (!fs.existsSync(filename)) {
    __create_dir(path.dirname(filename));
  }
  if (typeof table === 'undefined') { table = __default_table_data; }
  if (__verbose) {process.stderr.write('OPEINING : ' + table + '\n'); }
  var db = new sqlite3.Database(filename,
    function(err) {
      db.get('select name from sqlite_master where name=?', table,
        function(err, row) {
          if (err === null) {
            if (!row) {
              if (__already_created_tables[table]) {
                if (__verbose) {
                  process.stderr.write('waiting for ' + table + ' is ready');
                }
                setTimeout(function(){open_model_database(filename, table, callback);}, 100);
              } else {
                if (__verbose) {
                  process.stderr.write('creating table\n');
                }
                db.serialize(function() {
                  db.run('create table ' + table + ' (id primary key not null, name not null, user, date, data blob not null)');//fields blob not null, forest blob not null, best blob)');
                  db.run('create index index_' + table + ' on ' + table + '(id)');
                  db.close();
                  __already_created_tables[table] = true;
                  setTimeout(function(){open_model_database(filename, table, callback);}, 10);
                });
              }
            } else {
              if (__verbose) { process.stderr.write(table + ' is set up\n'); }

              __already_created_tables[table] = true;
              callback(null, db);
            }
          } else {
            if (!db) { db.close(); }
            callback(err);
          }
        }
      );
    }
  );
}


/**
  This function is used once after spawing the process.
  Set up database and create a file and a table if there are no database.
**/
function setup_db(filename, table_db, table_model, expire_period, callback) {
  var num_items = arguments.length;
  if (typeof arguments[arguments.length - 1] === 'function') {
    callback = arguments[arguments.length - 1];
    num_items --;
  }

  if (num_items > 0) {
    filename = arguments[0];
  } else {
    filename = undefined;
  }
  if (num_items > 1) {
    table_db = arguments[1];
  } else {
    table_db = null;
  }
  if (num_items > 2) {
    table_model = arguments[2];
  } else {
    table_model = null;
  }
  if (num_items > 3 && typeof arguments === 'number') {
    expire_period = arguments[3];
  } else {
    expire_period = __expire_period;
  }
  // if (arguments.length > 2) {
  //   table = arguments[1];
  // } else {
  //   table = __default_table_data;
  // }
  open_database(filename, table_db, function(err, db) {
    if (err) {
      if (callback) { callback(err);}
      if (db) { db.close(); }
    } else {
      db.close();
      if (expire_period > 0) {
        if (__verbose) {
          process.stderr.write('clearing cache\n');
        }
        clear_cache(filename, table_db, expire_period, function(err) {
          if (callback) { callback(err);}
        });
      }
    }
    open_model_database(filename, table_model, function(err, db) {
      db.close();
    });
  });
}

/**
  Provide a unique key for an entry.
**/
function generate_unique_key(filename, table, callback) {
  callback = arguments[arguments.length - 1];
  if (arguments.length > 1) {
    filename = arguments[0];
  } else {
    filename = undefined;
  }
  if (arguments.length > 2) {
    table = arguments[1];
  } else {
    table = __default_table_data;
  }
  open_database(filename, table, function(err, db) {
    if (err !== null) {
      callback(err);
    } else {
      __provide_unique_key(db, table, '', callback);
    }
  });
}

/**
  Save contents into a reserved row.
**/
function save_data(filename, table, contents, callback) {
  var user = contents['user'];
  if (!user) {
    user = '';
  }
  var date = dateformat(Date(), 'isoUtcDateTime');
  var key = contents['key'];
  var data = contents['data'];
  open_database(filename, table, function(err, db) {
    if (err !== null) {
      callback(err);
      if (db) { db.close(); }
    } else {
      if (__verbose) {process.stderr.write('insert data into database\n');}
      var state = __states.SUCCESS;
      db.run('insert or replace into ' + table + ' values(?, ?, ?, ?, ?)', key, user, date, state, data,
      function(err) {
        if (err) {
          if (__verbose) {process.stderr.write('ERROR ' + err);}
        } else {
          if (__verbose) {process.stderr.write('inserted ' + key);}
        }
        if (db) { db.close(); }
        callback(err);
      });
    }
//    if (db) {db.close();}
  });
}

/***
  Save a calculated model for prediction of other data
  CREATE TABLE __saved__ (ID not null primary key, NAME, USER, DATE, FOREST blob, BEST blob);

**/
function save_model(filename, model_id, name, table_db, table_model, callback) {
  //console.log('saving ' + model_id + ' as ' + name);
  open_model_database(filename, table_db, function(err, db) {
    if (err !== null) {
      if (__verbose) {
        process.stderr.write('failed to open ' + table_db + ' from ' + table_db + '\n');
      }
      callback(err);
      db.close();
    } else {
      db.get('select id, user, date, data from ' + table_db + ' where id=?', model_id,
        function(err, row) { // row : key, user, date, state, data
          if (err) {
            process.stderr.write('failed to load ' + model_id + ' from ' + table_db + '\n');
            db.close();
            callback(err);
          } else {
            var user = row.user;
            var date = row.date;
            var data = JSON.parse(row.data.toString());//[3].toString());
            // remove raw values from original data
            delete data.analysisset;
            delete data.trainingset;
            delete data.prediction;
//            var best = data['best_tree'];
            //var forest = data['forest'];
            //var fields = data['fields'];
//            CREATE TABLE __saved__ (ID not null primary key, USER, NAME, DATE, DATA blob);
            db.run('insert or replace into ' + table_model + ' values(?, ?, ?, ?, ?)', model_id, name, user, date, JSON.stringify(data),
             function(err) {
              // if (err) {
              //   console.log(err);
              // } else {
              //   console.log('successfully saved');
              // }
              db.close();
            });
          }
        }
      );
    }
  });
}

function get_models(filename, table, callback) {
//  console.log(table);
  open_model_database(filename, table, function(err, db) {
    if (err) {
      callback(err);
      db.close();
    } else {
      db.all('select id, name from ' + table,
        function(err, rows) {
          var models = {};
          if (err === null) {
            for (var i = 0; i < rows.length; i++) {
              models[rows[i].id] = rows[i].name;
            }
          }
          callback(err, models);
        })
      db.close();
    }
  });
}

function get_model_fields(filename, table, key, callback) {
  // console.log(table);
  // console.log(key);
  open_model_database(filename, table, function(err, db) {
    db.get('select data from ' + table + ' where id=?', key,
      function(err, row) {
        if (err) {
          callback(err);
        } else if (!row) {
          callback("no data ID : " + key);
        } else {
          //console.log(row);
          var data = JSON.parse(row.data.toString());
          // for (var p in data) {
          //   console.log(p);
          // }
          var fields = data.field;
          var features = [];
          var field_id = data.field_id;
          var field_out = data.field_out;
//          console.log(fields);
          features.push(field_id);
          features.push(field_out);
          for (var i = 0; i < fields.length; i++) {
            var field = fields[i];
            if (field.indexOf('__') < 0) {// !== field_id && field != field__out) {
              features.push(field);
            }
          }
          callback(null, features);
        }
//
//         console.log(row);
//         if (err) {
// //          db.close();
//           callback(err);
//         } else {
//           console.log(row);
//           // var prop = [];
//           // var tree = JSON.parse(row.best);
//           // for (var p in tree) {
//           //   prop.push(p);
//           // }
// //          db.close();
//           callback(null, row);
//         }
        db.close();
      }
    );
  });
}

/**
  Load contents from database using a unique key.
  First argument of callback function is error (null is success) and second argument is Javascript object having state and data.
**/
function load_data(filename, table, key, callback) {
  key = __sanitize_key(key);
  if (__verbose) {process.stderr.write(filename + ', ' + table + ', ' + key + '\n');}
  open_database(filename, table, function(err, db) {
    if (__verbose) {process.stderr.write('selecting data ' + key + '\n'); }
    db.get('select state, data from ' + table + ' where id=?', key, function(err, row) {
      var data = {};
      if (err) {
        process.stderr.write('ERROR : ' + err + '\n');
      } else {
        if (__verbose) {
          if (row) {
            process.stderr.write('loaded : ' + row.length + ' bytes\n');
          } else {
            process.stderr.write('failed to load ' + key);
          }
        }
        if (row) {
          try {
            //console.log(row.data.toString());
            //process.stderr.write(row.data);
            data = JSON.parse(row.data.toString());
            data.state = row.state;
          } catch (e) {
            //console.log(e);
            data = {state:0};
          }
        //console.log(row.data.toString());
        } else {
          data = {state:-1};
        }
      }
      db.close();
      callback(err, data);
    });
  });
}

function save_model_file(filename, table, key, callback) {
  open_database(filename, table, function(err, db) {
    if (err) {
      db.close();
      callback(err);
    }
    db.get('select data from ' + table + ' where id=?', key,
      function(err, row) {
        if (err) {
          callback(err);
        }
        db.close();
        var ft = temp.path({suffix:'.json'});
        var fd = fs.openSync(ft, 'w');
//        console.log(row.data.toString());
        fs.writeSync(fd, row.data.toString(), {encoding:'utf-8'});
        fs.closeSync(fd);
//        console.log('temporary filename ' + ft);
        callback(null, ft);
      }
    );
  });
}

/**
  Clear old data from database.
**/

function clear_cache(filename, table, expire_period, callback) {
  open_database(filename, table, function(err, db) {
    if (err) {
      if (db) {db.close();}
    } else {
      var current = new Date();
      var sweep_time = new Date();
      sweep_time.setTime(current.getTime() - expire_period);
      var date = dateformat(sweep_time, 'isoUtcDateTime');
      if (__verbose) {
        process.stderr.write('remove before ' + date + '\n');
      }
      db.run('delete from ' + table + ' where date < ?', date, function(err) {
        if (err === null) {
          process.stderr.write('successfully cleaned expired data\n');
        }
        if (db) {db.close();}
        callback(err);
      });
    }
  });
}

/**
  Verbosity control
*/
function verbose(flag) {
  if (typeof flag === 'undefined') {
    flag = true;
  }
  __verbose = flag;
}

exports.setup_db = setup_db;
exports.generate_unique_key = generate_unique_key;
exports.save_data = save_data;
exports.clear_cache = clear_cache;
exports.load_data = load_data;
exports.verbose = verbose;
exports.save_model = save_model;
exports.save_model_file = save_model_file;
exports.get_models = get_models;
exports.get_model_fields = get_model_fields;
exports.PROCESSING_STATES = __states;
