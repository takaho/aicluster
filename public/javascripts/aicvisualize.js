var aic = {};

aic.__polling_period = 2000;
aic.__panel_size = 400;
aic.__padding = 0.05; // percent of canvas
aic.__spacer = 5;
aic.__verbose = true;

aic.__container = '#contents';
aic.__dialog = null;

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

aic.display_message = function(code, message) {
  var modal = code <= 0;
  if (aic.__dialog === null) {
    aic.__dialog = $('<div>').attr('id', 'dialog').text(message).dialog({modal:modal});
  }
};

aic.hide_message = function() {
  if (aic.__dialog) {
    aic.__dialog.dialog("close");
    aic.__dialog = null;
  }
}

aic.load_data = function(key, element_id) {
  aic.hide_message();
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


aic.initialize_components = function() {
  $(aic.__container).children().remove();
};

aic.visualize = function(data) {
//  console.log(data);
  var conditions = data.condition;
  var num_trees = conditions.num_trees;
  var tree_depth = conditions.depth;
  var prediction = data.prediction;
  // prediction
  if (prediction) {
    var result_table = aic.generate_prediction_table(data);
    var panel = $('<div class="figure">').append($('<h2>').text('Results')).append(result_table);
    $(aic.__container).append(panel);
  }

  // loadings
  if (data.weight) {
    var weight_table = aic.generate_weight_table(data);
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
    panel.append(aic.generate_rawdata_table(data));
    $(aic.__container).append(panel);
  }

  // jquery-ui tooltip
  $(document).tooltip();
};

aic.generate_rawdata_table = function(data) {
  var table = $('<table>');
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
    for (j = 0; j < fields.length; j++) {
      if (fields[j] !== field_id && fields[j] != field_out) {
        tr.append($('<td>').text(values[i][fields[j]]));
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
  //console.log(layers);

  // draw conditions
  ctx.save();
  //ctx.lineWidth = 1;
  //ctx.strokeStyle = 'darkgray';
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

      //ctx.fillRect(lx, ly, lw, lh);
      ctx.rect(lx, ly, lw, lh);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = 'black';
      ctx.fillText(condition, p0[0] - hs, p0[1]);
      // var children = node.children;
      // for (j = 0; j < children.length; j++) {
      //   var p1 = node2pos[children[j]];
      //   ctx.beginPath()
      //   ctx.moveTo(p0[0], p0[1]);
      //   ctx.bezierCurveTo(p0[0], p0[1], p1[0], p0[1], p1[0], p1[1]);
      //   ctx.stroke();
      // }
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

aic.generate_prediction_table = function(data) {
  var having_rawdata = typeof data.analysisset !== 'undefined' && data.analysisset !== null;
  // console.log(having_rawdata);
  // console.log(typeof data);
  // console.log(typeof data.analysiset);

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
      }
    }

    var graph = $('<td>').appendTo(tr);
    var bar = $('<div>').width(bar_width).css('height', bh).css('position', 'relative');
    var x = 0;
    for (j = 0; j < res.score.length; j++) {
      var percent = (res.score[j] * 100).toFixed(2) + '%';
      var w = parseInt(res.score[j] * bar_width * 100) * 0.01;
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

aic.generate_weight_table = function(data) {
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
    var loading = weights[i][1];
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

// aic.draw_prediction_results = function(cnv, data) {
// //  console.log('predictions');
//   var labels = data.group_label;
//   var predictions = data.prediction;
//   console.log(data.prediction);
//
//   var width = cnv.width();
//   var height = cnv.height();
//   var left = width * aic.__padding;
//   var right = width * (1.0 - aic.__padding);
//   var top = height * (1.0 - aic.__padding);
//   var bottom = height * aic.__padding;
//
//   var colors = ['CornflowerBlue','HotPink', 'Teal', 'Peru', 'DarkMagenta', 'GoldenRod', 'LightBlue', 'LightSteelBlue', 'RebeccaPurple'];
//   //console.log(width + ' x ' + height);
//   cnv.attr('width', width).attr('height', height);
//   var ctx = cnv[0].getContext('2d');
// //  ctx.fillStyle = 'white';//white';
// //  ctx.fillRect(0, 0, width, height);
//   var left = aic.__padding;
//   var wid_bar = (right - left) * 0.60;
//   var hgt_bar = (top - bottom) / predictions.length * 0.75;
//   //console.log(predictions);
//   console.log(labels);
//   for (var i = 0; i < predictions.length; i++) {
//     ctx.save();
//     var y = parseFloat(i + 1) / (predictions.length + 1) * (top - bottom);
//     var x0 = left + (right - left) * 0.2;
//     var score = predictions[i].score;
// //    console.log(predictions[i]);
//     for (var j = 0; j < score.length; j++) {
//     //  console.log(x0 + ',' + wid_bar);
//       var x1 = x0 + score[j] * wid_bar;
//     //  console.log(colors[j]);
//       ctx.fillStyle = colors[j % colors.length];
//       ctx.fillRect(x0, y, x1 - x0, hgt_bar);
// //      ctx.fill();
//       x0 = x1;
//
//     }
//     ctx.strokeStyle = 'black';
//     ctx.lineWidth = 0.4;
//     ctx.rect(left + (right - left) * .2, y, wid_bar, hgt_bar);
//     ctx.stroke();
//
//     var name = data.analysisset[i][data.field_id];
//     if (typeof name !== 'undefined') {
//       ctx.fillStyle = 'black';
//       var sw = ctx.measureText(name).width;
//       //console.log(name + " at " + sw);//(left + (right - left) * 0.2 - sw) + ', ' + y);
//       ctx.fillText(name, left + (right - left) * 0.2 - sw - aic.__spacer, y + hgt_bar);
//     }
// //    ctx.stroke();
//     ctx.fillStyle = colors[predictions[i].prediction % colors.length];
// //    console.log(predictions[i].prediction);
//     ctx.fillText(labels[predictions[i].prediction], aic.__spacer + left + 0.8 * (right - left), y + hgt_bar);
//
//     var given = data.analysisset[i][data.field_out];
//     if (typeof given !== 'undefined') {
//       console.log(given);
//       ctx.fillStyle = colors[given % colors.length];
//       ctx.fillText(given, right + 10, y + hgt_bar);
//     }
//     ctx.restore();
//   }
//   return cnv;
// };

aic.initialize = function(key) {
  aic.initialize_components();
  aic.load_data(key);
};
