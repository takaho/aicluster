#coding:utf-8
import argparse, os, sys, re, math, collections, tempfile
import sklearn, sklearn.ensemble, sklearn.metrics, numpy
import openpyxl, xlrd
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont

# specific keywords for data management
KEYWORD_OUTPUT = '__output__'
KEYWORD_ID = '__id__'
GROUP_UNDETERMINED = '__undetermined__'

# Graphical presets
KEYWORDS_NON_NUMERIC = set([KEYWORD_OUTPUT, KEYWORD_ID])
MARKER_COLORS = ((255,100,100), (100,255,100), (100,100,255), (224,192,0), (128,0,192), (90,224,192))

def load_table(filename, id_field=None, output_field=None):
    """Load Excel or CSV file """
    rpos = filename.rfind('.')
    if rpos < 0:
        ext = 'csv'
    else:
        ext = filename[rpos + 1:].lower()
    # CSV
    table = None
    if ext == 'xlsx':
        import openpyxl
        table = []
        book = openpyxl.reader.excel.load_workbook(filename)
        sheet = book.get_active_sheet()
        for row in sheet.rows:
            if len(row) > 1:
                table.append([x_.value for x_ in row])
    elif ext == 'xls':
        try:
            import xlrd
            book = xlrd.open_workbook(filename)
            sheet = book.sheets[0]
            for rn in range(sheet.nrows):
                row = sheet.row(rn)
                values = [row[c].value for c in range(sheet.ncols)]
                table.append(values)
        except:
            pass
    if table is None: # CSV
        import csv
        table = []
        with open(filename) as fi:
            reader = csv.reader(fi)
            for row in reader:
                if len(row) > 1:
                    table.append(row)

    # determine fields
    header = table[0]
    props = {}
    index_output = -1
    index_id = -1
    for i, val in enumerate(header):
        if val == output_field and index_output < 0:
            index_output = i
        elif val == id_field and index_id < 0:
            index_id = i
        elif val is not None and len(val) > 0 and val not in props:# and val != 'ID_REF' and val.lower() != 'id':
            props[val] = i
    if index_output < 0:
        raise Exception('No output field in {}'.format(filename))

    data = []
    available_properties = {}
    for p in props.keys(): available_properties[p] = 0
    rownum = 0
    for row in table[1:]:
        datum = {}
        num_accepted = 0
        datum[KEYWORD_OUTPUT] = row[index_output]
        if index_id < 0:
            datum[KEYWORD_ID] = 'ID:{}'.format(rownum)
        elif isinstance(row[index_id], str) is False and isinstance(row[index_id], unicode) is False:
            datum[KEYWORD_ID] = repr(row[index_id])
        else:
            datum[KEYWORD_ID] = row[index_id]
        for pr, col in props.items():
            item = row[col]
            #print(col, item, item.__class__)
            try:
                val = float(item)
                if val < 0:
                    val = None
                else:
                    available_properties[pr] += 1
                    num_accepted += 1
            except:
                val = None
            datum[pr] = val
        if num_accepted > len(props) // 2:
            data.append(datum)
            rownum += 1
    minimum = len(data) // 2
    removing = set([p for p in props.keys() if available_properties[p] < minimum])
    for datum in data:
        for pr in removing:
            datum.pop(pr)
    return data

def complete_missing_values(data):
    """Put median values in missing data """
    N = len(data)
    M = len(data[0])#.dimensions
    for field in data[0].keys():
        if field in KEYWORDS_NON_NUMERIC: continue
        values = []
        for j, datum in enumerate(data):
            values.append(datum[field])
#            values.append(datum[i])#.get_value(i))
        if None not in values:
            continue
        sval = sorted([x_ for x_ in values if x_ is not None])
        K = len(sval)
        if K == 0:
            raise Exception('no data in {}th column'.format(i))
        if K % 2 == 0:
            median = .5 * (sval[K // 2] + sval[K // 2 + 1])
        else:
            median = sval[K // 2]
        for datum in data:
            if datum[field] is None:
                datum[field] = median

def generate_classifier(data, fields=None, max_depth=4, num_trees=20):
    """Generate random forest
    returns [Classifier object, applied fields, output groups]

    output_groups = [group_name_1, group_name_2, ...]
    """
    rf = sklearn.ensemble.RandomForestClassifier(max_depth=max_depth, n_estimators=num_trees)
    vectors = []
    labels = []
    if fields is None:
        fields = sorted([x_ for x_ in data[0].keys() if x_ not in KEYWORDS_NON_NUMERIC])
#    else:
#        fields = sorted([x_ for x_ in fields if x_ not in KEYWORDS_NON_NUMERIC])
    l2n = {}
    output_groups = []
    for datum in data:
        label = datum[KEYWORD_OUTPUT]
        if label not in l2n:
            l2n[label] = len(l2n)
            output_groups.append(label)
        labels.append(l2n[label])
        vector = [datum[x_] for x_ in fields]
        vectors.append(vector)
    rf.fit(vectors, labels)
    return rf, fields, output_groups

def predict_samples(rf, data, output_groups, fields=None, minimum_accuracy_samples=3):
    """Returns [predicted results, accuracy score]
    If output_field is not set (unknown data), accuracy will be set None """
    if fields is None:
        fields = sorted([x_ for x_ in data[0].keys() if x_ not in KEYWORDS_NON_NUMERIC])
    vectors = []
    labels = []
    l2n = {}
    for i, l in enumerate(output_groups):
        l2n[l] = i
    num_labeled = 0
    for datum in data:
        group = datum.get(KEYWORD_OUTPUT, GROUP_UNDETERMINED)
        vectors.append([datum[field] for field in fields])
        if group in l2n:
            labels.append(l2n[group])
            num_labeled += 1
        else:
            labels.append(None)
    #
    #     if KEYWORD_OUTPUT not in datum:
    #         labels = None
    #         break
    #     else:
    #         labels.append(l2n[datum[KEYWORD_OUTPUT]])
    # for datum in data:
    #     vector = []
    #     for field in fields:
    #         vector.append(datum[field])
    #     vectors.append(vector)
#    if len(vectors) < minimum_prediction:
    predicted = rf.predict(vectors)
    if num_labeled >= minimum_accuracy_samples:
        predicted_ = []
        labels_ = []
        for i, l in enumerate(labels):
            if l is not None:
                predicted_.append(predicted[i])
                labels_.append(l)
        accuracy = sklearn.metrics.accuracy_score(predicted_, labels_)
    else:
        accuracy = None
    return predicted, accuracy

def display_prediction_stats(forest, data, output_groups, fields=None):
    """Prediction results """
    vectors = []
    labels = []
    if fields is None:
        fields = sorted([x_ for x_ in data[0].keys() if x_ not in KEYWORDS_NOT_NUMERIC])
    l2n = {}
    for ind, gr in enumerate(output_groups): l2n[gr] = ind
    for datum in data:
        if labels is not None and KEYWORD_OUTPUT in datum:
            labels.append(l2n[datum[KEYWORD_OUTPUT]])
        else:
            labels = None
        vectors.append([datum[f_] for f_ in fields])
    predicted = forest.predict(vectors)
    #print(predicted)
    #print(labels)
    accuracy = sklearn.metrics.accuracy_score(predicted, labels)
    #print(sklearn.metrics.confusion_matrix(predicted, labels))
    #print('accuracy={}'.format(accuracy))
    return accuracy


def get_group_decision(forest, vector):
    """Aggregated decision by classifiers """
    decisions = None
    num = 0
    for est in forest.estimators_:
        if decisions is None:
            sample_numbers = get_total_scores(est.tree_)
            decisions = [0] * len(sample_numbers)
        decision = determine_group(est.tree_, vector)#datum)
        for i, w in enumerate(decision):
            decisions[i] += w
        num += 1
    return [float(x_) / num for x_ in decisions]

def get_total_scores(tree, node_id=0):
    """Sum up weights for normalization """
    leaf_id = sklearn.tree._tree.TREE_LEAF
    if node_id == leaf_id:
        raise ValueError("invalid node id {}".format(node_id))
    left_child = tree.children_left[node_id]
    right_child = tree.children_right[node_id]
    if left_child == leaf_id:
        lvals = tree.value[node_id][0]
        rvals = []
    else:
        lvals = get_total_scores(tree, left_child)
        rvals = get_total_scores(tree, right_child)

    values = [0] * max(len(lvals), len(rvals))
    for i, v in enumerate(lvals): values[i] += v
    for i, v in enumerate(rvals): values[i] += v
    #print(node_id, values)
    return values

def evaluate(tree, node_id, vector):
    """Evaluate vector using random forest recursively.
    return : value """
    leaf_id = sklearn.tree._tree.TREE_LEAF
    if node_id == leaf_id:
        raise ValueError("invalid node id {}".format(node_id))
    left_child = tree.children_left[node_id]
    right_child = tree.children_right[node_id]
    # output score
    if left_child == leaf_id:
        return tree.value[node_id][0]

    feature = tree.feature[node_id]
    threshold = tree.threshold[node_id]
    if vector[feature] < threshold:
        return evaluate(tree, left_child, vector)
    else:
        return evaluate(tree, right_child, vector)

def get_group_score(forest, vector):
    """return array of score for given groups"""
    scores = None
    num = 0
    for est in forest.estimators_:
        sample_numbers = get_total_scores(est.tree_)
        score = evaluate(est.tree_, 0, vector)
        div = 1.0 / sum(score)#sample_numbers)
        normalized = [(s * div) for s in score]
        if scores is None:
            scores = normalized
            num = 1
        else:
            for i, v in enumerate(normalized):
                scores[i] += v
            num += 1
    return [(float(s) / num) for s in scores]

def determine_group(tree, vector):
    """Determine group of input
    return array of weights. [1,] or [.5, .5] or something.
    """
    score = evaluate(tree, 0, vector)
    scores = {}
    for i, s in enumerate(score):
        scores[i] = s
    detected = sorted(scores.keys(), key=lambda i:scores[i], reverse=True)
    max_score = scores[detected[0]]
    end = len(detected)
    for i in range(1, len(detected)):
        if max_score > detected[i]:
            end = i
            break
    weight = 1.0 / end
    decision = [0] * len(scores)
    for i in range(end):
        decision[detected[i]] = weight
    return decision

def plot_prediction(forest, data, **kwargs):
    """Generate 3D plot for 3-group data
    retrun : PNG filename"""
    fields = kwargs.get('fields', None)
    size = kwargs.get('size', 500)#500#1000
    msize = kwargs.get('marker_size', 5)
    fontsize = kwargs.get('font_size', 24)
    fontname = kwargs.get('font', '/Library/Fonts/Courier New.ttf')
    filename_graph = kwargs.get('filename_graph', None)
    filename_bar = kwargs.get('filename_bar', None)
    output_groups = kwargs.get('output_groups', None)
    fields = kwargs.get('fields', None)
    verbose = kwargs.get('verbose', False)

    if fields is None:
        fields = sorted([f_ for f_ in data[0].keys() if f_ not in KEYWORDS_NON_NUMERIC])
        if verbose:
            sys.stderr.write('fields were interpreted as {} elements\n'.format(len(fields)))
    elif verbose:
        sys.stderr.write('{} fields\n'.format(len(fields)))

    if output_groups is None:
        dimensions = 0
        not_available = False
        output_groups = []
        for datum in data:
            if KEYWORD_OUTPUT not in datum:
                not_available = True
                continue
            gn = output_groups[output_groups]
            if gn not in output_groups:
                output_groups.append(gn)
                dimensions += 1
        if not_available:
            output_groups = None
    else:
        dimensions = len(output_groups)

    num_trees = forest.n_estimators
    decisions = []
    results = []
    for i, datum in enumerate(data):
        vector = [datum[x_] for x_ in fields]
        scores = get_group_score(forest, vector)
        decision = [int(round(x_ * num_trees)) for x_ in scores]
        detected = 0
        maxscore = decision[0]
        for i, v in enumerate(decision):
            if v > maxscore:
                maxscore = v
                detected = i
        results.append(decision)
        if output_groups is None:
            decisions.append(detected)
        else:
            decisions.append(output_groups[detected])

    # return only decisions
    if filename_graph is None and filename_bar is None: return decisions
    if filename_graph == filename_bar:
        filename_graph = None # bar graph is prior

    if filename_bar is not None:
        image = Image.new('RGB', (size, size))
        draw = ImageDraw.ImageDraw(image)
        draw.rectangle(((0,0),(size,size)), fill=(255,255,255))
        num_trees = forest.n_estimators
        num_individuals = len(data)
        ycnv = lambda i : ((i + .5) * size) / (num_individuals + 1)
        xcnv = lambda p : float((p + 0.15) * size * 0.7)
        draw.rectangle(((0,0),(size,size)), fill=(255,255,255))
        colors = MARKER_COLORS
        lcolors = {}
        for i, n in enumerate(output_groups):
            lcolors[n] = colors[i]
        for i, result in enumerate(results):
            t = 0
            coeff = 1.0 / sum(result)
            y0 = ycnv(i)
            y1 = ycnv(i + 0.8)
            for j, v in enumerate(result):
                ratio = v * coeff
                x0 = xcnv(t)
                x1 = xcnv(t + ratio)
                draw.rectangle(((x0,y0),(x1,y1)), outline=(0,0,0), fill=colors[j])
                t += ratio
            name = data[i].get(KEYWORD_ID, '{}'.format(i + 1))
            spacer = size * 0.02
            x0 = xcnv(0)
            x1 = xcnv(1)
            draw.text((x0 - draw.textsize(name)[0] - spacer, y0), name, fill=(0,0,0))
            if decisions[i] is not None:#output_groups is not None:
                label = decisions[i]
                #label = output_groups[decisions[i]]
                draw.text((x1 + spacer, y0), label, fill=lcolors[label])
        image.save(filename_bar)

    if filename_graph is None:
        return decisions

    def project_3d(point):
        points = [float(x_) / maximum for x_ in point]
        x = points[0]
        y = points[1]
        if len(points) < 3:
            z = 0
        else:
            z = points[2]
        x = 1.0 - x
        vx = size * .5 * (x * .9 + y * .3 + .5)
        vy = size * .6 - size * .4 * ((x * .3 - y * .9) * .5 + z)
        return vx, vy
    def project_2d(point):
        x = size * (.1 + .8 * point[0] / maximum)
        y = size * (0.9 - .8 * point[1] / maximum)
        return x, y

    if dimensions <= 2:
        projection_func = project_2d
    else:
        projection_func = project_3d

    image = Image.new('RGB', (size, size))
    draw = ImageDraw.ImageDraw(image)
    draw.rectangle(((0,0),(size,size)), fill=(255,255,255))
    maximum = forest.n_estimators
    GRAY = (128,128,128)
    #
    #font = ImageFont.truetype('/Library/Fonts//Courier New.ttf', 24)
    try:
        font = ImageFont.truetype(fontname, size=fontsize)
    except:
        font = None
    #draw.text(project((-1,0,0)), 'O', fill=(0,0,0), font=font)
    dotcolors = {}
    colors = MARKER_COLORS
    if output_groups is None:
        output_groups = []
        for datum in data:
            if KEYWORD_OUTPUT not in datum:
                output_groups = None
                break
            gn = output_groups[output_groups]
            if gn not in output_groups:
                output_groups.append(gn)
                dotcolors[gn] = colors[gn % len(colors)]
    else:
        for i, gn in enumerate(output_groups):
            dotcolors[gn] = colors[i % len(colors)]

    for identifier, datum in enumerate(data):
        result = results[identifier]
        xy = projection_func(result)

        outline = (0,0,0)
        given = datum.get(KEYWORD_OUTPUT, GROUP_UNDETERMINED)# if KEYWORD_OUTPUT not in datum else datum[KEYWORD_OUTPUT]
        #print(result, xy, given)
        if given == GROUP_UNDETERMINED or given != decisions[identifier]:
            if KEYWORD_ID in datum:
                label = datum[KEYWORD_ID]
            else:
                label = '{}'.format(identifier + 1)
            outline = dotcolors.get(given, GRAY)#[given]#colors[detected % len(colors)]
            fill = (255,255,2555)
            draw.text((xy[0] + msize, xy[1]), label, fill=GRAY, font=font)
        else:
            fill = dotcolors[given]#colors[detected]
            outline = (0,0,0)
        draw.ellipse((xy[0]-msize, xy[1]-msize, xy[0]+msize, xy[1]+msize),
            fill=fill, outline=outline)
    # Axes
    points = []
    if dimensions > 2:
        for i in range(8):
            points.append(((i % 2) * maximum, (i & 2 != 0) * maximum, (i & 4 != 0) * maximum))
        for i, pi in enumerate(points):
            for j, pj in enumerate(points):
                n = sum([int(pi[k] != pj[k]) for k in range(3)])
                if n == 1:
                    p0 = projection_func(pi)
                    p1 = projection_func(pj)
                    l = (p0, p1)
                    draw.line(l, fill=(0,0,0))#[p0,pi])#, fill=(0,0,0))
        if output_groups is not None:
            for i, gn in enumerate(output_groups):
                if i == 0:
                    xy = projection_func([num_trees * 1.05, 0, 0])
                elif i == 1:
                    xy = projection_func([0, num_trees * 1.05, 0])
                elif i == 2:
                    xy = projection_func([0, 0, num_trees * 1.05])
                else:
                    continue
                draw.text(xy, gn, fill=(0,0,0), font=font)
    else:
        x0, y0 = projection_func([0, 0])
        x1, y1 = projection_func([maximum, maximum])
        x2, y2 = projection_func([.5 * maximum, -.1 * maximum])
        x3, y3 = projection_func([-.1 * maximum, .5 * maximum])
        draw.rectangle(((x0, y0), (x1, y1)), outline=(0,0,0))
        draw.text((x2, y2), output_groups[0], fill=(0,0,0))
        draw.text((x3, y3), output_groups[1], fill=(0,0,0))

    image.save(filename_graph)
    return decisions

def draw_treemodel(tree, draw, rectangle, fields, **kwargs):
    """Draw a tree in a box """
    max_depth = kwargs.get('max_depth', 4)
    box_hratio = kwargs.get('box_xratio', 0.25)
    box_vratio = kwargs.get('box_yratio', 0.10)
    leaf_id = sklearn.tree._tree.TREE_LEAF
    node_id = 0
    next_ids = [0,]
    layer = 1
    x, y, w, h = rectangle
    draw.rectangle(((x,y),(w-1,h-1)), outline=(128,128,128))


    dy = h / (max_depth + 1) # vertical step
    bw, bh = int(w * box_hratio), int(h * box_vratio) # box size
    bx, by = (w - bw) // 2 + x, y + bh / 2# box position
    position_cache = {0:[bx , by]}
    toffset = bh / 2

    draw.rectangle(((bx,by),(bx+bw,by+bh)), outline=(0,0,0))
    cnd = '{} < {:.2f}'.format(fields[tree.feature[0]], tree.threshold[0])
    draw.text((bx + (bw- draw.textsize(cnd)[0]) // 2, by + toffset), cnd, fill=(0,0,0))

    leaves = {}
    while 1:
        next_layer = []
        num_elems = 0
        nodes = []
        for nid in next_ids:
            l = tree.children_left[nid]
            r = tree.children_right[nid]
            nodes.append([nid, l, tree.children_left[l] == leaf_id])
            nodes.append([nid, r, tree.children_left[r] == leaf_id])
            if tree.children_left[l] != leaf_id:
#            if l != leaf_id:
                next_layer.append(l)
            else:
                leaves[l] = tree.value[nid][0]
            if tree.children_left[r] != leaf_id:#r != leaf_id:
                next_layer.append(r)
            else:
                leaves[r] = tree.value[nid][0]
            num_elems += 2
        for i in range(num_elems):
            parent, node_id, is_leaf = nodes[i]
            bx = ((i + .5) * w / num_elems) + x - bw / 2
            by = y + dy * layer + bh
            px, py = position_cache[parent]
            draw.line(((bx+bw // 2, by),(px+bw*.5, py+bh)), fill=(0,0,0))
            position_cache[node_id] = bx, by
            if not is_leaf:
                draw.rectangle(((bx,by),(bx+bw,by+bh)),outline=(10,10,20))
                cnd = '{} < {:.2f}'.format(fields[tree.feature[node_id]], tree.threshold[node_id])
                draw.text((bx + (bw - draw.textsize(cnd)[0]) / 2, by + toffset), cnd, fill=(0,0,0))
        next_ids = next_layer
        if len(next_ids) == 0: break
        layer += 1

    colors = MARKER_COLORS
    for lid in leaves.keys():
        bx, by = position_cache[lid]
        value = tree.value[lid][0]
        total = sum(value)
        color = [0,0,0]
        sections = []
        for i, val in enumerate(value): sections.append([i, val])
        theta = -90
        rect = ((bx+(bw-bh)/2,by),(bx+(bw+bh)/2,by+bh))
        for elem in sorted(sections, key=lambda x_:x_[1], reverse=True):
            #red, green, blue = colors[elem[0] % len(colors)]
            num = elem[1]
            if num <= 0: continue
            rad = int(round(num * 360.0 / total))
            t = (theta + rad * .5) / 180 * math.pi
            if num == total:
                draw.ellipse(rect, fill=colors[elem[0] % len(colors)])
                xl, yl = (bx + bw * .5, by + 10)
            else:
                draw.pieslice(rect, start=int(round(theta)), end=int(round(theta + rad)), fill=colors[elem[0] % len(colors)])
                xl = bx + bw * .5 + bh * 0.3 * math.cos(t)
                yl = by + bh * .5 + bh * 0.3 * math.sin(t) - 5
            draw.text((xl, yl), '{}'.format(int(round(num))), fill=(64,64,64))
            theta += rad
        draw.ellipse(rect, outline=(20,30,20))

def select_best_tree(forest, data, fields, output_groups):#, **kwargs):
    """find best classifier tree and give score"""
    labels = []
    groups = {}
    nlabels = []
    vectors = []
    for datum in data:
        output = datum[KEYWORD_OUTPUT]
        label = None
        for i, l in enumerate(output_groups):
            if output == l:
                label = i
                break
        if label is None:
            raise Exception('{} cannot be classified'.format(output))
        labels.append(label)
        vectors.append([datum[x_] for x_ in fields])
    best_score = 0
    best_tree = None
    for est in forest.estimators_:
        success = fail = 0
        for index, vector in enumerate(vectors):
            decision = determine_group(est.tree_, vector)
            if decision[labels[index]] == 1:#groups[datum.group]] == 1:
                success += 1
            else:
                fail += 1
        ratio = float(success) / (success + fail)
        if ratio > best_score:
            best_score = ratio
            best_tree = est.tree_
    if best_tree is None:
        raise Exception('no tree')
    return best_tree, best_score

def draw_tree(tree, fields, **kwargs):
    """Draw a tree
    parameters
    size:given size (default=300)
    filename: filename of output (default temporary)

    return
    fileanme
     """
    size = kwargs.get('size', 300)
    filename = kwargs.get('filename', tempfile.mktemp('.png'))
    image = Image.new('RGB', (size, size))
    #verbose = kwargs.get('verbose', False)
    draw = ImageDraw.ImageDraw(image)
    draw.rectangle(((0,0), (size,size)), fill=(255,255,255))
    draw_treemodel(tree, draw, (0,0,size,size), fields)
    image.save(filename)
    return filename

def generate_report(data, decisions, **kwargs):
    """Output pdf document
    accuracy_table : given x decided
    directory_output : report
    """
    dstdir = kwargs.get('directory_output', 'out')
    accuracy_table = kwargs.get('accuracy_table', None)
    filename_plot = kwargs.get('filename_plot', None)
    filename_tree = kwargs.get('filename_tree', None)
    filename_bar = kwargs.get('filename_bar', None)
    tree_accuracy = kwargs.get('tree_accuracy', None)
    output_groups = kwargs.get('output_groups', None)
    conditions = kwargs.get('conditions', None)
    field_id = kwargs.get('id', None)
    fields = kwargs.get('fields', None)

    # timestamp
    import time
    lt = time.localtime()
    timestamp = '{}'.format(lt.tm_year)
    for n in lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec:
        timestamp += '00{}'.format(n)[-2:]

    if os.path.exists(dstdir) is False: os.makedirs(dstdir)
    html = os.path.join(dstdir, 'report_{}.html'.format(timestamp))
    contents = """<!DOCTYPE HTML><head><title>Results</title></head>"""
    if conditions is not None:
        contents += '<h1>Condisions</h1>\n<table>'
        for prop in enumerate(sorted(conditions.keys())):
            contents += '<tr><td>{}</td><td>{}</td></tr>\n'.format(prop, conditions[prop])
        contents += '</table>\n'

    if filename_plot is not None and os.path.exists(filename_plot):
        fn = 'plot_{}.png'.format(timestamp)
        dstfile = os.path.join(dstdir, fn)
        with open(filename_plot, 'rb') as fi, open(dstfile, 'wb') as fo:
            fo.write(fi.read())
        contents += '<h1>Decision plot</h1><img src="{}" width=400 height=400>\n'.format(fn)
    if filename_bar is not None and os.path.exists(filename_bar):
        fn = 'bars_{}.png'.format(timestamp)
        dstfile = os.path.join(dstdir, fn)
        with open(filename_bar, 'rb') as fi, open(dstfile, 'wb') as fo:
            fo.write(fi.read())
        contents += '<h1>Individual scores</h1><img src="{}" width=400 height=400>\n'.format(fn)

    if filename_tree is not None and os.path.exists(filename_tree):
        fn = 'tree_{}.png'.format(timestamp)
        dstfile = os.path.join(dstdir, fn)
        with open(filename_tree, 'rb') as fi, open(dstfile, 'wb') as fo:
            fo.write(fi.read())
        contents += '<h1>Best predicting tree</h1><img src="{}" width=400 height=400>\n'.format(fn)
#        if tree_accuracy is not None:
#            contents += 'accuracy={}<br>'.format(tree_accuracy)
        if tree_accuracy is not None:
            contents += 'accuracy={}<br/>\n'.format(tree_accuracy)
    if accuracy_table is not None:
        table= '<h1>Accuracy</h1><table>'
        table += '<tr><th></th>'
        for og in output_groups: table += '<th>{}</th>'.format(og)
        table += '</tr>\n'
        for i, og in enumerate(output_groups):
            table += '<tr><th>{}</th>'.format(og)
            for n in accuracy_table[i]:
                table += '<td>{}</td>'.format(n)
            table += '</tr>\n'
        table += '</table>\n'
        contents += table

    table = '<h1>Results</h1>\n<table>'
    name_given = KEYWORD_OUTPUT in data[0]
    if name_given:
        table += '<tr><td>ID</td><td>Given</td><td>Predicted</td></tr>\n'
    else:
        table += '<tr><td>ID</td><td>Predicted</td></tr>\n'
    if fields is not None:
        for f in fields:
            table += '<td>{}</td>'.format(f)
    table += '</tr>\n'
    for i, datum in enumerate(data):
        table += '<tr><td>{}</td>'.format(i + 1)
        if name_given:
            table += '<td>{}</td>'.format(datum[KEYWORD_OUTPUT])
        table += '<td>{}</td></tr>'.format(decisions[i])
        if fields is not None:
            for f in fields:
                table += '<td>{}</td>'.format(datum[f])

        table += '</tr>\n'
    table += '</table>'
    contents += table
    contents += '</body>\n</html>\n'
    with open(html, 'w') as fo:
        fo.write(contents)
    return html#os.path.join(dstdir, 'report.html')

def execute_analysis(**kargs):
    import tempfile, copy
    filename_training = kargs['training_file']
    filename_diagnosis = kargs.get('diagnosis_file', None)#filename_training)
    num_trees = kargs.get('num_trees', 20)
    max_depth = kargs.get('max_depth', 4)
    directory_output = kargs.get('output', 'rf_out')#tempfile.mktemp('.pdf'))
    field_output = kargs.get('output_field', 'OUT')
    field_id = kargs.get('id_field', None)
    verbose = kargs.get('verbose', False)

    # Set output field
    trainingset = load_table(filename_training, field_id, field_output)
    complete_missing_values(trainingset)
    predictionset = None
    fields = sorted([f_ for f_ in trainingset[0] if f_ not in KEYWORDS_NON_NUMERIC])
    if filename_diagnosis is not None and os.path.exists(filename_diagnosis):
        if filename_training != filename_diagnosis:
            predictionset = load_table(filename_diagnosis, field_id, field_output)
            complete_missing_values(predictionset)
            pfields = sorted([f_ for f_ in predictionset[0] if f_ not in KEYWORDS_NON_NUMERIC])
            if verbose:
                for f in pfields:
                    if f not in fields:
                        sys.stderr.write('{} is not included in training set\n'.format(f))
                for f in fields:
                    if f not in pfields:
                        sys.stderr.write('{} is not included in diagnosis set\n'.format(f))
            fields = [f_ for f_ in fields if f_ in pfields]

    if predictionset is None:
        predictionset = copy.deepcopy(trainingset)

    if verbose:
        for i, f in enumerate(fields):
            sys.stderr.write('{}\t{}\n'.format(i, f))
        sys.stderr.write('OUTPUT\t{}\n'.format(field_output))
        if field_id:
            sys.stderr.write('ID\t{}\n'.format(field_id))

    # calculation
    if verbose: sys.stderr.write('Fit samples\n')
    forest, fields, output_groups = generate_classifier(trainingset, fields=fields, max_depth=max_depth, num_trees=num_trees)
    if verbose:
        for i, gn in enumerate(output_groups):
            sys.stderr.write('Group{}\t{}\n'.format(i + 1, gn))
    # set "undetermined" in prediction data if the gruop is not included in training data
    for datum in predictionset:
        group = datum.get(field_output, None)
        if group not in output_groups:
            datum[field_output] = GROUP_UNDETERMINED

    # calculate accuracy
    if verbose: sys.stderr.write('Prediction\n')
    predicted, accuracy = predict_samples(forest, predictionset, output_groups, fields=fields)

    #
    #display_prediction_stats(forest, predictionset, output_groups)
    #given = [d[KEYWORD_OUTPUT] for d in predictionset]
#    print(given)

    if verbose: sys.stderr.write('Generating reports\n')
    filename_plot = tempfile.mktemp('.png')#os.path.join(directory_output, 'plot.png')
    filename_bar = tempfile.mktemp('.png')
    #filename = 'box.png'#tempfile.mktemp('.txt')

    # 3D view
    decisions = plot_prediction(forest, predictionset, fields=fields, output_groups=output_groups,
        filename_graph=filename_plot, filename_bar=filename_bar)
    if verbose:
        for i, d in enumerate(decisions):
            sys.stderr.write('{}\t{}\n'.format(i, d))

    #print(filename_png)
    num_groups = len(output_groups)
    accuracy_table = [[0] * num_groups for i in range(num_groups)]
    if KEYWORD_OUTPUT in predictionset[0]:
        l2n = {}
        for i, gr in enumerate(output_groups): l2n[gr] = i
        for j, datum in enumerate(predictionset):
            given = datum[KEYWORD_OUTPUT]
            gr_ = decisions[j]
            if given in l2n and gr_ in l2n:
                accuracy_table[l2n[given]][l2n[gr_]] += 1
    if verbose:
        sys.stderr.write(repr(accuracy_table) + '\n')

    best_tree, best_score = select_best_tree(forest, trainingset, fields, output_groups)
    #print('best score={}'.format(best_score))
    filename_tree = draw_tree(best_tree, fields, size=400)
    #print(filename_tree)

    report_file = generate_report(predictionset, decisions, accuracy_table=accuracy_table, tree_accuracy=best_score, filename_tree=filename_tree, treescore=best_score,
    filename_plot=filename_plot, filename_bar=filename_bar,
    directory_output=directory_output, output_groups=output_groups, fields=fields)
    for fn in filename_tree, filename_plot:
        if os.path.exists(fn): os.unlink(fn)

    return report_file#directory_output

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', default=None, help='input CSV file', metavar='filename')
    parser.add_argument('-t', help='teaching data', default='data/numeric_table.csv', metavar='filename')
    parser.add_argument('-o', default=None, help='output directory', metavar='filename')
    parser.add_argument('-n', default=20, type=int, help='number of trees', metavar='number')
    parser.add_argument('-d', default=4, type=int, help='maximum depth of decision tree', metavar='number')
#    parser.add_argument('-c', default=None, help='columns', metavar='columns separated by commas')
    parser.add_argument('-F', default="OUT", help='output column', metavar='field name')
    parser.add_argument('-I', default='ID', help='identifier column', metavar='field name')
    parser.add_argument('-g', default='box.png', help='graphics', metavar='filename (PNG)')
    parser.add_argument('--best', default=None, metavar='filename', help='output best tree (PDF)')
    parser.add_argument('--verbose', action='store_true', help='verbosity')
    args = parser.parse_args()

    filename_prediction = args.i if args.i is not None else args.t
    execute_analysis(training_file=args.t, diagnosis_file=args.i, num_trees=args.n,
        max_depth=args.d, output=args.o, output_field=args.F, id_field=args.I, verbose=args.verbose)
