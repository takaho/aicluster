var aic = {};

aic.__polling_period = 1000;//0;
aic.__panel_size = 400;
aic.__padding = 0.05; // percent of canvas
aic.__spacer = 5;
aic.__verbose = true;

aic.__container = '#contents';
aic.__dialog = null;

aic.current_data_id = null;

if (typeof process === 'undefined') {
  process = {}
}
if (typeof process.stderr === 'undefined') {
  process.stderr = {}
  process.stdout = {}
  process.stderr.write = process.stdout.write = function(message) {
    console.log(message);
  }
}

/**
  Display modal dialog while loading and on error
  Parameters :
     code : not used currently, but negative values means errors
     message : Message shown on display
*/
aic.display_message = function(code, message) {
  var modal = code <= 0;
  if (aic.__dialog === null) {
    aic.__dialog = $('<div>').attr('id', 'dialog').text(message).dialog({modal:modal});
  } else {
    aic.__dialog.text(message);
  }
};
/**
  Hide dialog after load.
  */
aic.hide_message = function() {
  if (aic.__dialog) {
    aic.__dialog.dialog("close");
    aic.__dialog = null;
  }
}

/**
  Asynchronous loading from server using unique keys. If the contents are loaded, this function call aic.initialize_components to display results.

  Parameters
    key : Provided key by server
    element_id (optional): identifier of container element
*/
aic.load_data = function(key, element_id) {
  if (aic.__verbose) {process.stderr.write('loading data : ' + key);}
  if (element_id) {
    aic.__container = element_id;
  }
  $.ajax(
    {
      url:'retrieve',
      type:'GET',
      data:{id:key},
      cache:false,
      async:true
    })
    .success(
      function(data) { // receive JSON object
        console.log(data);
        if (data.state >= 1 && data.prediction) {
          aic.hide_message();
          aic.current_data_id = key;
          aic.visualize(data);
        } else if (data.message === 'processing') {
          aic.display_message(0, 'Wait for a while');//calculation failed " + data.message);
//          console.log('waiting for ' + key);
          setTimeout(function() { aic.load_data(key, element_id); }, aic.__polling_period);
        } else { // error
          aic.display_message(-1, "calculation failed " + data.message);
        }
      })
    .fail(
      function(err) {
        aic.display_message(-2, "connection failed");
      });
};

/**
  Clear all components
*/
aic.initialize_components = function() {
  $(aic.__container).children().remove();
};

/**
  Generate several elements and place them on the page.
*/
aic.visualize = function(data) {
//  console.log(data);
  var conditions = data.condition;
  var num_trees = conditions.num_trees;
  var tree_depth = conditions.depth;
  var prediction = data.prediction;

  // statistics
  if (prediction) {
    var result_table = aic.create_result_table(data);
    var condition_table = aic.create_condition_table(data);
    var panel = $('<div class="figure">');
    try {
      if (data.analysisset[0][data.field_out]) { // where analysis set has answer
        panel.append($('<h2>').text('Results')).append(result_table);
      }
    } catch (e) {
      console.log(e);
    }
    panel.append($('<h2>').text('Conditions')).append(condition_table);

    // save
    var button = $('<div>').text('Save').button();
    button.click(function() {
      console.log('button');
      console.log($('#model_name'));
      $.ajax({url:'/save',
        type:'POST',
        data:{key:aic.current_data_id, name:$('#model_name').val()},
        async:true})
      .success(function(data) { console.log('successfully commited : ' + data); })
      .fail(function(data) {console.log('failed : ' + data);});
    });
    panel.append($('<input>').attr('id', 'model_name')).append($('<br>')).append(button);
    $(aic.__container).append(panel);
  }

  // prediction
  if (prediction) {
    var result_table = aic.create_prediction_table(data);
    var panel = $('<div class="figure">').append($('<h2>').text('Results')).append(result_table);
    $(aic.__container).append(panel);
  }

  // loadings
  if (data.weight) {
    var weight_table = aic.create_weight_table(data);
    table_title = $('<h2>').text('Property loadings');
    var panel = $('<div class="figure">').append(table_title).append(weight_table);
    $(aic.__container).append(panel);
  }

  // best tree
  if (data.best_tree) {
    var tree_cnv = aic.draw_best_tree(data);
    var canvas_title = $('<h2>').text('Best decision tree');
    var panel = $('<div class="figure">').append(canvas_title).append(tree_cnv);
    $(aic.__container).append(panel);
  }

  // raw data
  if (data.analysisset) {
    var panel = $('<div class="figure">');
    panel.append($('<h2>').text('Analysis data'));
    panel.append(aic.create_rawdata_table(data));
    $(aic.__container).append(panel);
  }


  // jquery-ui tooltip
  $(document).tooltip();
};

/**
  Create a table showing experimental conditions
*/
aic.create_condition_table = function(data) {
  var labels = data.group_label;
  var condition = data.condition;
  var table = $('<table>').attr('class', 'sstable');
  // conditions
  $('<tr>').append($('<td>').text('Num. samples')).append($('<td>').text(data.analysisset.length)).appendTo(table);
  $('<tr>').append($('<td>').text('Num. groups')).append($('<td>').text(labels.length)).appendTo(table);

  $('<tr>').append($('<td>').text('Max depth')).append($('<td>').text(condition.depth)).appendTo(table);
  $('<tr>').append($('<td>').text('Num. trees')).append($('<td>').text(condition.num_trees)).appendTo(table);
  $('<tr>').append($('<td>').text('Iteration')).append($('<td>').text(condition.iterations)).appendTo(table);

  // Results
  return table;
};

/**
  Create results
*/
aic.create_result_table = function(data) {
  var ratio_solo = 0.0;
  var ratio_aggregated = 0.0;
  var table = $('<table>').attr('class', 'sstable');
  var answers = [];
  var field = data.field_out;
  var labels = data.group_label;
  for (var i = 0; i < data.analysisset.length; i++) {
    var prop = data.analysisset[i][field];
    var gid = -1;
    for (var j = 0; j < labels.length; j++) {
      if (prop == labels[j]) {
        gid = j;
        break;
      }
    }
    answers.push(gid);
  }
  var n00 = 0, n01 = 0, n10 = 0, n11 = 0;
  var pred = data.prediction;
  for (var i = 0; i < pred.length; i++) {
    var given = answers[i];
    if (given < 0) { continue; }
    var solo = pred[i].best_tree;
    var aggr = pred[i].prediction;
    if (solo === given) {
      n00 ++;
    } else {
      n01 ++;
    }
    if (aggr === given) {
      n10 ++;
    } else {
      n11 ++;
    }
  }
  if (n00 + n01 > 0) {
    ratio_solo = n00 / (n00 + n01);
  }
  if (n10 + n11 > 0) {
    ratio_aggregated = n01 / (n01 + n11);
  }

  // conditions
  $('<tr>').append($('<td>').text('Aggregation')).append($('<td>').text((ratio_aggregated * 100).toFixed(2) + ' %')).appendTo(table);
  $('<tr>').append($('<td>').text('Solo')).append($('<td>').text((ratio_solo * 100).toFixed(2) + ' %')).appendTo(table);

  return table;
};

aic.__arrange_float = function(val, maximum_figures) {
  var f = 10;
  var esr = Math.pow(0.1, maximum_figures + 1);
  for (var i = 0; i < maximum_figures; i++) {
    var m = val * f;
    if (Math.abs(m - Math.round(m)) < esr) {
      return val.toFixed(i + 1);
    }
    f *= 10;
  }
  return val.toFixed(maximum_figures + 1);
};

/**
  Create rawdata table.
*/
aic.create_rawdata_table = function(data) {
  var table = $('<table>').attr('class', 'rawdata');
  var fields = data.field;
  var field_id = data.field_id;
  var field_out = data.field_out;
  var i;
  var num = 0;//fields.length;
  var header = $('<tr>');
  //var having_id = false, having_out = false;
  var values = data.analysisset;
  header.append($('<th>').text('ID'));
  header.append($('<th>').text('OUT'));
  var having_id = typeof values[0][field_id] !== 'undefined';
  var having_out = typeof values[0][field_out] !== 'undefined';
  //console.log(values[0]);
  //console.log(typeof values[0].field_id);
  //console.log(values[0].field_id);


  for (i = 0; i < fields.length; i++) {
//    console.log(fields[i] + ' // ' + field_id + ' // ' + field_out);
    if (fields[i] === field_id) {
//      having_id = true;
    } else if (fields[i] === field_out) {
//      having_out = true;
    } else {
      num++;
      header.append($('<th>').text(fields[i]));
    }
  }

  table.append(header);
  for (i = 0; i < values.length; i++) {
    var tr = $('<tr>').appendTo(table);
    if (having_id) {
      tr.append($('<td>').text(values[i][field_id]));
    } else {
      tr.append($('<td>').text(i));
    }
    if (having_out) {
      tr.append($('<td>').text(values[i][field_out]));
    } else {
      tr.append($('<td>'));
    }
    var row = values[i];
    for (j = 0; j < fields.length; j++) {
      if (fields[j] !== field_id && fields[j] != field_out) {
        var val = row[fields[j]];
        if (val % 1 == 0) { // integer
          val = parseInt(val);
        } else {
          val = aic.__arrange_float(val, 4);
        }
        tr.append($('<td>').text(val));//values[i][fields[j]]));
      }
    }
  }
  return table;
};

aic.__create_canvas = function(width, height) {
  var cnv = $('<canvas>');
  cnv.attr('width', width).attr('height', height);
  cnv.width(width).height(height);
  var ctx = cnv[0].getContext('2d');
  ctx.fillStyle = 'white';
  ctx.fillRect(0, 0, width, height);
  return cnv;
}

/**
  Draw a representative tree in CANVAS element.
*/
aic.draw_best_tree = function(data) {
  var size = aic.__panel_size;
  var cnv = aic.__create_canvas(size, size);
  var width = size;
  var height = size;
  var labels = data.group_label;
  var fields = data.field;
  var tree = data.best_tree;
  var i, j;
  var xmax = 0;
  var ymax = 0;
  var layers = [];
  var node2pos = [];
  var depth = data.condition.depth;

  for (i = 0; i <= depth; i++) { layers.push([]); }

  for (i = 0; i < tree.length; i++) {
    var node = tree[i];
    var x = node.x;
    var y = node.y;
    layers[y].push(x);
    if (i == 0) {
      xmax = x; ymax = y;
    } else {
      if (x > xmax) { xmax = x; }
      if (y > ymax) { ymax = y; }
    }
  }
  for (i = 0; i < layers.length; i++) {
    layers[i] = Math.max.apply(this, layers[i]);
  }
  for (i = 0; i < tree.length; i++) {
    var node = tree[i];
    var x = node.x;
    var y = node.y;
    var vx = (x + .5) / (layers[y] + 1) * width;
    var vy = (y + .5) / (depth + 1) * height;
    node2pos.push([vx, vy]);
  }
  var ctx = cnv[0].getContext('2d');

  // draw branches
  ctx.save();
  ctx.lineWidth = 1;
  ctx.strokeStyle = 'darkgray';
  ctx.font = '8pt Courier';
  var hy = ctx.measureText('Yes').width / 2;
  var hn = ctx.measureText('No').width / 2;
  ctx.fillStyle = '#668';
  for (i = 0; i < tree.length; i++) {
    var node = tree[i];
    if (!node.leaf) {
      var p0 = node2pos[i];
      var children = node.children;
      for (j = 0; j < children.length; j++) {
        var p1 = node2pos[children[j]];
        ctx.beginPath()
        ctx.moveTo(p0[0], p0[1]);
        ctx.bezierCurveTo(p0[0], p0[1], p1[0], p0[1], p1[0], p1[1]);
        ctx.stroke();
        if (j == 0) {//p0[0] > p1[0]) {
          ctx.fillText('Yes', p1[0] - hy, (p0[1] + p1[1]) * .5);
        } else {
          ctx.fillText('No', p1[0] - hn, (p0[1] + p1[1]) * .5);
        }
      }
    }
  }
  ctx.restore();

  // draw decisions
  ctx.save();
  ctx.lineWidth = 0.5;
  var radius = size * 0.05;
  for (i = 0; i < tree.length; i++) {
    var node = tree[i];
    if (node.leaf) {
      var p0 = node2pos[i];
      var values = node.value;
      var sum = 0;
      for (j = 0; j < values.length; j++) { sum += values[j]; }
      var theta = - Math.PI * 0.5;
      for (j = 0; j < values.length; j++) {
        if (values[j] > 0) {
          var rad = values[j] * Math.PI * 2 / sum;
          ctx.beginPath()
          ctx.moveTo(p0[0], p0[1]);
          ctx.arc(p0[0], p0[1], radius, theta, theta + rad);
          ctx.lineTo(p0[0], p0[1]);
          ctx.fillStyle = aic.__label_colors[j % aic.__label_colors.length];
          ctx.fill();
          theta += rad;
        }
      }
      ctx.strokeStyle = 'black';
      ctx.beginPath();
      ctx.arc(p0[0], p0[1], radius, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  ctx.restore();

  // draw conditions
  ctx.save();
  ctx.font = '10pt Times';

  for (i = 0; i < tree.length; i++) {
    var node = tree[i];
    if (!node.leaf) {
      var p0 = node2pos[i];
      //var feature = node.feature;
      var feature_label = fields[node.feature];
      var condition = feature_label + ' < ' + (node.threshold % 1 == 0 ? node.threshold : node.threshold.toFixed(1));
      var hs = ctx.measureText(condition).width * .5;
      ctx.fillStyle = 'rgba(220,220,255,0.5)';
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.5)';
      var lx = p0[0] - hs - 2;
      var ly = p0[1] - 12;
      var lw = hs * 2 + 4;
      var lh = 14;
      ctx.beginPath();

      ctx.rect(lx, ly, lw, lh);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = 'black';
      ctx.fillText(condition, p0[0] - hs, p0[1]);
    }
  }
  ctx.restore();

  return cnv;
  //var
}

aic.__label_colors = ['CornflowerBlue','LightPink', 'Teal', 'Peru', 'DarkMagenta', 'GoldenRod', 'LightBlue', 'LightSteelBlue', 'RebeccaPurple'];

aic.__create_label_data_element = function(value, labels) {
  var td = $('<td>');
  var label = labels ? labels[value] : value;
  td.css('color', aic.__label_colors[value % aic.__label_colors.length]).text(label);
  return td;
};

/**
  Create a table element containing predicted results.
*/
aic.create_prediction_table = function(data) {
  var having_rawdata = typeof data.analysisset !== 'undefined' && data.analysisset !== null;
  var i, j;
  var tr;
  var labels = data.group_label;
  var colors = aic.__label_colors;
  var predictions = data.prediction;
  var table = $('<table>').attr('id', 'prediction_table');
  var elements = having_rawdata ? ['ID', 'Given', 'Results', 'Aggr.', 'Solo'] : ['ID', 'Results', 'Aggr.', 'Solo'];
  var bh = '10px';
  tr = $('<tr>');
  for (i = 0; i < elements.length; i++) {
    var th = $('<th>').text(elements[i]).appendTo(tr);
  }
  table.append(tr);
  var bar_width = 200;
  for (i = 0; i < predictions.length; i++) {
    tr = $('<tr>').appendTo(table);
    var res = predictions[i];
    var given_label;
    if (having_rawdata) {
      var input = data.analysisset[i];
      tr.append($('<td>').text(input[data.field_id]));
//      console.log(input);
      given_label = input[data.field_out];
    } else {
      tr.append($('<td>').text('.'));
      given_label = null;
    }
    if (typeof given_label !== 'undefined') {
      var index = null;
      for (j = 0; j < labels.length; j++) {
        if (labels[j] == given_label) {
          index = j;
          break;
        }
      }
      if (index !== null) {
        aic.__create_label_data_element(index, labels).appendTo(tr);
      } else {
        tr.append($('<td>'));
      }
    }

    var graph = $('<td>').appendTo(tr);
    var bar = $('<div>').width(bar_width).css('height', bh).css('position', 'relative');
    var x = 0;
    var accum = 0;
    for (j = 0; j < res.score.length; j++) {
      accum += res.score[j];
    }
    if (accum <= 0) {
      continue;
    }
    var coeff = 100.0 / accum;
    for (j = 0; j < res.score.length; j++) {
      var percent = (res.score[j] * coeff).toFixed(2) + '%';
      var w = parseInt(res.score[j] * coeff * bar_width) * 0.01;
      var color = aic.__label_colors[j % aic.__label_colors.length];
      var rect = $('<div>').css('background', color).css('left', x + 'px').css('top', '0px').css('width', w).css('height', bh).css('position', 'absolute').attr('title', percent);
      x += w;
      bar.append(rect);
    }
    graph.append(bar);
    var score = predictions[i].score;
    aic.__create_label_data_element(res.prediction, labels).appendTo(tr);
    aic.__create_label_data_element(res.best_tree, labels).appendTo(tr);

  }
  return table;
};

/**
  Generate loadings of parameters in HTML elements.
*/
aic.create_weight_table = function(data) {
  var table = $('<table>').attr('id', 'weight_table');
  $('<tr>').append($('<th>').text('Property')).append($('<th>').text('Loading')).appendTo(table);
  var weights = [];
  var val_max = 0;
  var bar_width = 200;
  var bh = '10px';
  for (var prop in data.weight) {
    var val = data.weight[prop];
    if (val > val_max) { val_max = val; }
    weights.push([prop, val]);
  }
  weights.sort(function(a, b) { if (a[1] > b[1]) { return -1; } else if (a[1] < b[1] ) { return 1; } else { return 0; } });
  if (val_max <= 0.0001) { val_max = 1.0; }

  for (var i = 0; i < weights.length; i++) {
    //console.log(weights[i]);
    var loading = weights[i][1].toFixed(4);
    var w = parseInt(bar_width * loading / val_max * 100) * 0.01;
    //var w = weights[i][1]
    var tr = $('<tr>').append($('<td>').text(weights[i][0])).appendTo(table);
    var bar = $('<div>').width(bar_width).css('height', bh).css('position', 'relative');
    $('<td>').append(bar).appendTo(tr);
    var rect = $('<div>') //.css('position', 'absolute').css('left', '0px').css('top', '0px')
    .css('width', w).css('height', '10px').attr('title', loading)
    .css('background', 'navy').appendTo(bar);
  }
  return table;
};

// construct visualization page
aic.initialize = function(key) {
  aic.initialize_components();
  aic.load_data(key);
};

aic.load_models = function() {
  console.log('load models');
  $.ajax({url:'/models', type:'get'})
    .success(function(data) {
      console.log(data);
      var selection = $('#model');
//      var flag = selection.prop('disabled');
//      selection.prop('disabled', false);
      selection.children().remove();
      if (data.length == 0) {
        selection.append($('<option>').attr('value', '').text('No model saved'));
        $('#predictionbutton').prop('disabled', true);
      } else {
        selection.append($('<option>').attr('value', '').text('Select saved model'));
        for (var prop in data) {
          console.log(selection);
          console.log(prop);
          selection.append($('<option>').attr('value', prop).text(data[prop]));
        }
        console.log(selection);
      }
      //selection.prop('disabled', flag);
    })
    .fail(function() {
      console.log('failed to load models');
    });
};

aic.display_fields = function() {
  var model_id = $('#model').val();
  if (typeof model_id !== 'string' || model_id.length < 4) {
    console.log('no data id set');
    return;
  }
  console.log(name);
  $.ajax({url:'/feature', type:'get', data:{"id":model_id}})
    .success(function(data) {
      console.log('feature obtained');
      console.log(data);
    })
    .fail(function() {
      console.log('could not retrieve features');
    });


};

// construct start page
aic.display_models = function() {
  $('#constructionbutton')
    .on('click', function() {
      $('#prediction input').prop('disabled', true);//.animate({opacity:0.2});
      $('#construction input').prop('disabled', false);//.animate({opacity:1.0});
      $('#prediction').animate({opacity:0.2});
      $('#construction').animate({opacity:1.0});

    });
    $('#predictionbutton')
      .on('click', function() {
        $('#prediction input').prop('disabled', false);//.animate({opacity:0.2});
        $('#construction input').prop('disabled', true);//.animate({opacity:1.0});
        $('#prediction').animate({opacity:1.0});
        $('#construction').animate({opacity:0.2});
        // $('#construction input').prop('disabled', true).animate({opacity:0.2});
        // $('#prediction input').prop('disabled', false).animate({opacity:1.0});
      });
  $('#model').change(aic.display_fields);

  $('#constructionbutton').click();

  aic.load_models();
};
