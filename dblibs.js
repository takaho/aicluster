var sqlite3 = require('sqlite3');
var path = require('path');
var fs = require('fs');
var dateformat = require('dateformat');
var __key_length = 10;
var __verbose = false;
var __states = {SUCCESS:1, READY:0, FAILURE:-1};
var __expire_period = 1000 * 60 * 60 * 24 * 180;

var __key_characters = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";

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


/**
  Open database connection and call callback function.
  Parameters:
    filename : SQLite filename (default in-memory database)
    table    : SQLite table (default  "repository")
**/
function open_database(filename, table, callback) {
  if (typeof filename === 'undefined') {
    filename = ':memory:';
  } else if (!fs.existsSync(filename)) {
    __create_dir(path.dirname(filename));
  }
  if (typeof table === 'undefined') { table = "repository"; }
  if (__verbose) {process.stderr.write('OPEINING : ' + table + '\n'); }
  var db = new sqlite3.Database(filename,
    function(err) {
      db.get('select name from sqlite_master where name=?', table,
        function(err, row) {
          if (!err) {
            if (!row) {
              if (__verbose) {
                process.stderr.write('creating table\n');
              }
              db.serialize(function() {
                db.run('create table ' + table + ' (id primary key not null, user, date, state int4, data blob not null)');
                db.run('create index index_' + table + ' on ' + table + '(id)');
                db.close();
                setTimeout(function(){open_database(filename, table, callback);}, 10);
              });
            } else {
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
    table    : SQLite table (default  "repository")
**/
function open_model_database(filename, table, callback) {
  if (typeof filename === 'undefined') {
    filename = ':memory:';
  } else if (!fs.existsSync(filename)) {
    __create_dir(path.dirname(filename));
  }
  if (typeof table === 'undefined') { table = "repository"; }
  if (__verbose) {process.stderr.write('OPEINING : ' + table + '\n'); }
  var db = new sqlite3.Database(filename,
    function(err) {
      db.get('select name from sqlite_master where name=?', table,
        function(err, row) {
          if (!err) {
            if (!row) {
              if (__verbose) {
                process.stderr.write('creating table\n');
              }
              db.serialize(function() {
                db.run('create table ' + table + ' (id primary key not null, user, date, data blob not null, best blob)');
                db.run('create index index_' + table + ' on ' + table + '(id)');
                db.close();
                setTimeout(function(){open_model_database(filename, table, callback);}, 10);
              });
            } else {
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
function setup_db(filename, table, callback) {
  callback = arguments[arguments.length - 1];
  if (arguments.length > 1) {
    filename = arguments[0];
  } else {
    filename = undefined;
  }
  if (arguments.length > 2) {
    table = arguments[1];
  } else {
    table = 'repository';
  }
  open_database(filename, table, function(err, db) {
    if (db) { db.close(); }
    if (err) {
      if (callback) { callback(err);}
    } else {
      if (__verbose) {
        process.stderr.write('clearing cache\n');
      }
      clear_cache(filename, table, function(err) {
        if (callback) { callback(err);}
      });
    }
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
    table = 'repository';
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
**/
function save_model(filename, table, model, best_tree, callback) {
  var user = contents['user'];
  if (!user) {
    user = '';
  }
  var date = dateformat(Date(), 'isoUtcDateTime');
  var key = contents['key'];
  open_model_database(filename, table, function(err, db) {
    if (err !== null) {
      callback(err);
      if (db) { db.close(); }
    } else {
      if (__verbose) {process.stderr.write('save model data into database\n');}
      db.run('insert into ' + table + ' values(?, ?, ?, ?, ?)', key, user, date, model,
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
  });
}

function get_models(filename, table, callback) {
  open_model_database(filename, table, function(err, db) {
    db.serialize(function() {
      db.each('select id, namefrom ' + table,
        function(err, row) {
          callback(err, row);
        });
      });
    db.close();
  });
}

function get_model_fields(filename, table, key, callback) {
  open_model_database(filename, table, function(err, db) {
    db.get('select model from ' + table + ' where id=?', key,
      function(err, row) {
        if (err) {
          db.close();
          callback(err);
        } else {
          var prop = [];
          var tree = JSON.parse(row[0])[0];
          for (var p in tree) {
            prop.push(p);
          }
          db.close();
          callback(null, prop);
        }
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

/**
  Clear old data from database.
**/

function clear_cache(filename, table, callback) {
  open_database(filename, table, function(err, db) {
    if (err) {
      if (db) {db.close();}
    } else {
      var current = new Date();
      var sweep_time = new Date();
      sweep_time.setTime(current.getTime() - __expire_period);
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
exports.PROCESSING_STATES = __states;
