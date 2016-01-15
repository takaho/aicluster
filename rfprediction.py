#coding:utf-8
import argparse, os, sys, re, math, collections, tempfile
import sklearn, sklearn.ensemble, sklearn.metrics, numpy
import json, copy
import openpyxl, xlrd

KEYWORD_OUTPUT = '__output__'
KEYWORD_ID = '__id__'
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
            table = []
            import xlrd
            book = xlrd.open_workbook(filename)
            sheet = book.sheets()[0]#[0]
            for rn in range(sheet.nrows):
                row = sheet.row(rn)
                values = [row[c].value for c in range(sheet.ncols)]
                table.append(values)
        except:
            table = None
            pass
    elif ext == 'txt':
        table = []
        with open(filename) as fi:
            items = fi.readline().strip().split('\t')
            for line in fi:
                items = []
                for item in line.strip().split('\t'):
                    if re.match('\\-?\\d*\\.?\\d+$', item):
                        items.append(float(item))
                    else:
                        items.append(item)
                table.append(items)
    if table is None: # CSV
        import csv
        table = []
        with open(filename) as fi:
            reader = csv.reader(fi)
            for row in reader:
                if len(row) > 1:
                    table.append(row)
    # fix integer values
    for rn, row in enumerate(table):
        for cn, val in enumerate(row):
            if isinstance(val, float):
                if (val - round(val)) < 1e-5:
                    row[cn] = int(val)

    # determine fields
    header_row = -1
    for rn in range(len(table)):
        num = 0
        for cn, item in enumerate(table[rn]):
            if item is not None:
                if (isinstance(item, str) or isinstance(item, unicode)) and len(item) > 0:
                    num += 1
                elif isinstance(item, int):
                    num += 1
        if num > 3:
            header_row = rn
            break
    if header_row < 0:
        raise Exception('no field row found')
    header = [(item if isinstance(item, str) or isinstance(item, unicode) else repr(item))for item in table[header_row]]
    props = {}
    index_output = -1
    index_id = -1
    for i, val in enumerate(header):
        if val == output_field and index_output < 0:
            index_output = i
        elif val == id_field and index_id < 0:
            index_id = i
        else:
            #val = repr(val)
            if val is not None and len(val) > 0 and val not in props:# and val != 'ID_REF' and val.lower() != 'id':
                props[val] = i
    if index_output < 0:
        raise Exception('No output field in {}'.format(filename))

    data = []

    available_properties = {}
    for p in props.keys(): available_properties[p] = 0
    rownum = 0
    for row in table[header_row + 1:]:
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
                raise
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
        if not isinstance(label, str) and not isinstance(label, unicode):
            label = repr(label)
            datum[KEYWORD_OUTPUT] = label
        if label not in l2n:
            l2n[label] = len(l2n)
            output_groups.append(label)
        labels.append(l2n[label])
        vector = [datum[x_] for x_ in fields]
        vectors.append(vector)
    rf.fit(vectors, labels)
    return rf, fields, output_groups

def predict_samples(rf, data, output_groups, fields=None):
    """Returns [predicted results, accuracy score]
    If output_field is not set (unknown data), accuracy will be set None """
    if fields is None:
        fields = sorted([x_ for x_ in data[0].keys() if x_ not in KEYWORDS_NON_NUMERIC])
    vectors = []
    l2n = {}
    for i, l in enumerate(output_groups):
        l2n[l] = i
    labels = []
    for datum in data:
        if KEYWORD_OUTPUT not in datum or datum[KEYWORD_OUTPUT] not in l2n:
            # having samples without name
            labels = None
            break
        else:
            labels.append(l2n[datum[KEYWORD_OUTPUT]])
    for datum in data:
        vector = []
        for field in fields:
            vector.append(datum[field])
        vectors.append(vector)
    predicted = rf.predict(vectors)
    if labels is not None:
        accuracy = sklearn.metrics.accuracy_score(predicted, labels)
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

def enumerate_features_in_tree(tree, node_id, counts):
    """Enumerate features used in a tree"""
    leaf_id = sklearn.tree._tree.TREE_LEAF
    if node_id == leaf_id:
        raise ValueError("invalid node id {}".format(node_id))
    left_child = tree.children_left[node_id]
    right_child = tree.children_right[node_id]
    # output score
    if left_child == leaf_id:
        return tree.value[node_id][0]

    feature = tree.feature[node_id]
    if feature not in counts:
        counts[feature] = 1
    else:
        counts[feature] += 1
    enumerate_features_in_tree(tree, left_child, counts)
    enumerate_features_in_tree(tree, right_child, counts)

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

def get_decision_results(forest, data, fields):
    num_trees = forest.n_estimators
    results = []
    for i, datum in enumerate(data):
        vector = [datum[x_] for x_ in fields]
        scores = get_group_score(forest, vector)
        #decision = [int(round(x_ * num_trees)) for x_ in scores]
        detected = 0
        maxscore = scores[0]#decision[0]
        for i, v in enumerate(scores):#decision):
            if v > maxscore:
                maxscore = v
                detected = i
#        results.append(decision)
        results.append({'prediction':detected, 'score':scores})
    return results

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
        given = None if KEYWORD_OUTPUT not in datum else datum[KEYWORD_OUTPUT]
        #print(result, xy, given)
        if given is not None and given != decisions[identifier]:
            if KEYWORD_ID in datum:
                label = datum[KEYWORD_ID]
            else:
                label = '{}'.format(identifier + 1)
            outline = dotcolors[given]#colors[detected % len(colors)]
            fill = (255,255,2555)
            draw.text((xy[0] + msize, xy[1]), label, fill=(128,128,128), font=font)
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

def __get_timestamp():
    # timestamp
    import time
    lt = time.localtime()
    timestamp = '{}'.format(lt.tm_year)
    for n in lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec:
        timestamp += '00{}'.format(n)[-2:]
    return timestamp


def load_files_and_determine_fields(filename_training, filename_diagnosis=None, field_id=None, field_output=None, verbose=False):
    """Return (normalized traninig data set, normalized prediction data set, available fields)"""
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
    return trainingset, predictionset, fields

def _obtain_forest(trainingset, predictionset, fields, num_trees, max_depth, num_iteration=0, verbose=False):
    """
    return best_forest, best_tree, feature_weigts
    """
    best_accuracy = 0
    best_forest = None
    best_tree = None
    best_score = 0
    if num_iteration < 1:
        num_iteration = 1
    loops = 0
    weights = {}
    while loops < num_iteration:
        forest, fields, output_groups = generate_classifier(trainingset, fields=fields, max_depth=max_depth, num_trees=num_trees)
        # if verbose:
        #     for i, gn in enumerate(output_groups):
        #         sys.stderr.write('Group{}\t{}\n'.format(i + 1, gn))

        # calculate accuracy
        #if verbose: sys.stderr.write('Out of bag\n')
        predicted, accuracy = predict_samples(forest, trainingset, output_groups, fields=fields)
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_forest = forest
        tree, score = select_best_tree(forest, trainingset, fields, output_groups)
        if best_tree is None or score > best_score:
            best_tree = tree
            best_score = score
        for est in forest.estimators_:
            weights_ = {}
            enumerate_features_in_tree(est.tree_, 0, weights_)#weights)
            for w in weights_.keys(): weights[w] = weights.get(w, 0) + 1
        if verbose:
            sys.stderr.write('{}/{}\t{:.3f}\t{:.3f}\n'.format(loops, num_iteration, score, accuracy))
        loops += 1
#        print(loops, num_iteration, loops < num_iteration)
#    print(weights)
    total = num_iteration * num_trees
    feature_weights = {}
    for i, v in weights.items():
        feature_weights[fields[i]] = float(v) / total
#    print(feature_weights)
    return best_forest, best_tree, feature_weights, output_groups

#def diagnose_samples(forest, predictionset):

######### json
def encode_tree(tree):
    contents = []
    next_ids = [0,]
    leaf_id = sklearn.tree._tree.TREE_LEAF
    depth = 0
    nid = 0
    cached_x = [0]
    while len(next_ids) > 0:
        next_layer = []
        num_elems = 0
        nodes = []
        x = 0
        nx = cached_x
        cached_x = []
        for i, nid in enumerate(next_ids):
            lid = tree.children_left[nid]
            rid = tree.children_right[nid]
            contents.append({'id':nid, 'x':nx[i], 'y':depth, 'children':[lid, rid], 'feature':tree.feature[nid], 'threshold':tree.threshold[nid], 'leaf':False})
            if tree.children_left[lid] != leaf_id: # Left node is a leaf?
                cached_x.append(x)
                next_layer.append(lid)
            else:
                leaf = {'id':lid, 'value':[float(x_) for x_ in tree.value[lid][0]], 'x':x, 'y':depth + 1, 'leaf':True}
                contents.append(leaf)
            x += 1
            if tree.children_left[rid] != leaf_id: # right node is a leaf?
                cached_x.append(x)
                next_layer.append(rid)
            else:
                leaf = {'id':rid, 'value':[float(x_) for x_ in tree.value[rid][0]], 'x':x, 'y':depth + 1, 'leaf':True}
                contents.append(leaf)
            x += 1
        depth += 1
        next_ids = next_layer
    # for c in sorted(contents, key=lambda c:c['y']):
    #     print(c)
    contents = sorted(contents, key=lambda x_:x_['id'])
#    print(contents)
#    exit()
    return contents

def encode_forest(forest):
    trees = [encode_tree(est.tree_) for est in forest.estimators_]
    return trees


def pack_json_results(trainingset, predictionset, fields, predicted, best_forest, best_tree, output_groups, weight=None, condition=None):
    """Compose a JSON object having all processed data.
    """
    treeout = encode_tree(best_tree)
    forestout = encode_forest(best_forest)

    success = 0
    failure = 0
    for i, datum in enumerate(predictionset):
        if KEYWORD_OUTPUT in datum:
            vector = [datum[f] for f in fields]
            decision = evaluate(best_tree, 0, vector)
            max_val = decision[0]
            max_dec = 0
            for j, v in enumerate(decision):
                if v > max_val:
                    max_dec = j
                    max_val = v
            predicted[i]['best_tree'] = max_dec # determined by best tree
            #print('PREDICTION BY A TREE : {} => {}'.format(i, max_dec))
    #print(predicted)
    #exit()

    results = {'best_tree':treeout, 'forest':forestout, 'group_label':output_groups,
        'prediction':predicted, 'trainingset':trainingset, 'analysisset':predictionset,
        'field_id':KEYWORD_ID, 'field_out':KEYWORD_OUTPUT, 'field':fields}
    if condition: results['condition'] = condition
    if weight: results['weight'] = weight
    return results


def execute_analysis(**kargs):
    """
    @Parameters
        training_file : filename of training
        diagnosis_file : filename of diagnosis
        num_trees : number of trees in a forest
        max_depth : maximum depth
        id_field : field name of ID
        output_field : field name of output
        iterations : number of iterations
        verbose : verbosity
    @Rerurn
        Dict object of whole results
    """
    import tempfile, copy
    filename_training = kargs['training_file']
    filename_diagnosis = kargs.get('diagnosis_file', None)#filename_training)
    num_trees = kargs.get('num_trees', 20)
    max_depth = kargs.get('max_depth', 4)
    dstdir = kargs.get('output', 'rf_out')#tempfile.mktemp('.pdf'))
    field_output = kargs.get('output_field', 'OUT')
    field_id = kargs.get('id_field', None)
    iterations = kargs.get('iterations', 1)
    verbose = kargs.get('verbose', False)

    if max_depth < 2: max_depth = 2
    if max_depth > 10: max_depth = 10
    if num_trees < 1: num_trees = 1
    if num_trees > 1000: num_trees = 1000

    conditions = {'Training data':filename_training,
        'Analysis data':filename_diagnosis,
        'Number of trees':num_trees,
        'Maximum depth':max_depth,
        'Iteration': iterations}

    # load data and define fields
    trainingset, predictionset, fields \
    = load_files_and_determine_fields(filename_training=filename_training, filename_diagnosis=filename_diagnosis, field_id=field_id, field_output=field_output, verbose=verbose)

    # generate forest and select best classifier if iterations is set
    best_forest, best_tree, weights, output_groups = _obtain_forest(trainingset, predictionset, fields, num_trees, max_depth, iterations, verbose)

    # predict unknown samples
    if predictionset is None:
        predictionset = copy.deepcopy(trainingset)
    predicted = get_decision_results(best_forest, predictionset, fields)

    # save data
    timestamp = __get_timestamp()
    filename = os.path.join(dstdir, 'report_{}.json'.format(timestamp))
    summary = save_json_results(filename, trainingset, predictionset, fields, predicted, best_forest, best_tree, output_groups, weights, )
    return summary

def __trim_data_fields(data, fields):
    trimmed = []
    for datum in data:
        values = {}
        for f in fields:
            values[f] = datum[f]
        trimmed.append(values)
    return trimmed

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', default=None, help='input CSV file', metavar='filename')
    parser.add_argument('-t', help='training data', default=None, metavar='filename')
    parser.add_argument('-o', default='out', help='output directory', metavar='directory')
    parser.add_argument('-n', default=20, type=int, help='number of trees', metavar='number')
    parser.add_argument('-d', default=4, type=int, help='maximum depth of decision tree', metavar='number')
    parser.add_argument('-F', default="OUT", help='output column', metavar='field name')
    parser.add_argument('-I', default='ID', help='identifier column', metavar='field name')
    parser.add_argument('--best', default=None, metavar='filename', help='output best tree (PDF)')
    parser.add_argument('--verbose', action='store_true', help='verbosity')
    parser.add_argument('--without-rawdata', action='store_true', help='remove rawdata from report')
    parser.add_argument('--iteration', type=int, default=0, help='the number of iteration to estimate weights of parameters')
    parser.add_argument('--key', metavar='characters', default=None, help='unique ID')
    args = parser.parse_args()

    if 2 <= args.n < 200:
        num_trees = args.n
    else:
        num_trees = 20
    if 2 <= args.d < 10:
        depth = args.d
    else:
        depth = 4
    if 0 < args.iteration < 1000:
        iteration = args.iteration
    else:
        iteration = 0

    conditions = {}
    # conditions['Training data'] = args.t
    # conditions['Analysis data'] = args.i
    # conditions['Number of trees'] = num_trees
    # conditions['Maximum depth'] = depth
    # conditions['Iteration'] = iteration
    conditions['training_data_file'] = args.t
    conditions['analysis_data_file'] = args.i
    conditions['num_trees'] = num_trees
    conditions['depth'] = depth
    conditions['iterations'] = iteration

    if args.verbose:
        for key, value in conditions.items():
            sys.stderr.write('{}\t{}\n'.format(key, value))

    filename_prediction = args.i if args.i is not None else args.t
    iteration = args.iteration
    dstdir = args.o

    # data loading
    try:
        trainingset, predictionset, fields \
        = load_files_and_determine_fields(filename_training=args.t, filename_diagnosis=args.i, field_id=args.I, field_output=args.F, verbose=args.verbose)
    except Exception as e:
        sys.stderr.write('error while loading : ' + repr(e))
        raise e
    # forest formation
    try:
        best_forest, best_tree, weights, output_groups = _obtain_forest(trainingset, predictionset, fields, args.n, args.d, iteration, args.verbose)
    except Exception as e:
        sys.stderr.write('error while forest formation : ' + repr(e))
        raise e
    # prediction
    if predictionset is None:
        predictionset = copy.deepcopy(trainingset)
    try:
        predicted = get_decision_results(best_forest, predictionset, fields)
    except Exception as e:
        sys.stderr.write('error while prediction : ' + e)
        raise e

    # Save data
    timestamp = __get_timestamp()
    summary = pack_json_results(trainingset, predictionset, fields, predicted, best_forest, best_tree, output_groups, weights, conditions)
    if args.key: # unique key for interaction with other processes
        summary['key'] = args.key
    if args.without_rawdata: # remove rawdata for privacy concern
        fields = [KEYWORD_ID, KEYWORD_OUTPUT]
        summary['trainingset'] = __trim_data_fields(summary['trainingset'], fields)
        summary['analysisset'] = __trim_data_fields(summary['trainingset'], fields)

    if dstdir.lower().endswith('.json'): # save JSON only
        filename = dstdir
        dstdir = None
        with open(filename, 'w') as fo:
            json.dump(summary, fo, indent=4, separators=(',', ': '))
    else: # HTML reports
        if os.path.exists(dstdir) is False:
            os.makedirs(dstdir)

        filename = os.path.join(dstdir, 'report_{}.json'.format(timestamp))
        with open(filename, 'w') as fo:
            json.dump(summary, fo, indent=4, separators=(',', ': '))
        # visualization
        import rfreport
        rfreport.generate_report_document(summary, dstdir)
