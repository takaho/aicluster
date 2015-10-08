import os, sys, re, argparse, math
import urllib2, tempfile
import PIL.Image as Image
import PIL.ImageDraw as ImageDraw
import PIL.ImageFont as ImageFont

__default_template =  """<!DOCTYPE HTML>
<html>
<head>
<title><%=title%></title>
<style type="text/css">
body {font-size:small; margin:5%; } h2 {fond-size:large;color:#546;}
#prediction_table tr:nth-child(even){background:#eee;}
#prediction_table {border:1px solid black; border-spacing:0; font-size:x-small; font-family:monospace;}
thead{font-weight:bold; background:#444;color:white;}
td{white-space:nowrap;}
th{white-space:nowrap;}
.failure {color:#f00;}
</style>
</head>
<body>
<h1>Random forest clustering report</h1>
<h2>Conditions</h2>
<%condition%>
<h2>Best tree</h2>
<%best_tree%><br>
<p>Accuracy = <%best_score%></p>
<h2>Predicted</h2>
<%bargraph%>
<h2>Parameter occurrence</h2>
<%weightgraph%>
<h2>Results</h2>
<%datatable%>
</body>
</html>
"""

__MARKER_COLORS = ((255,100,100), (100,255,100), (100,100,255), (224,192,0), (128,0,192), (90,224,192))

def draw_bar_chart(names, predicted, group_labels=None, size=400, filename=None):
    """Bar chart
    """
    if filename is None:
        filename_bar = tempfile.mktemp('.png')
    else:
        filename_bar = filename
    image = Image.new('RGB', (size, size))
    draw = ImageDraw.ImageDraw(image)
    draw.rectangle(((0,0),(size,size)), fill=(255,255,255))
#    num_trees = forest.n_estimators
    num_individuals = len(names)
    ycnv = lambda i : ((i + .5) * size) / (num_individuals + 1)
    xcnv = lambda p : float((p + 0.15) * size * 0.7)
    draw.rectangle(((0,0),(size,size)), fill=(255,255,255))
    colors = __MARKER_COLORS

    for i, result in enumerate(predicted):
        t = 0
        scores = result['score']
        coeff = 1.0 / sum(scores)
        y0 = ycnv(i)
        y1 = ycnv(i + 0.8)
        for j, v in enumerate(scores):
            ratio = v * coeff
            x0 = xcnv(t)
            x1 = xcnv(t + ratio)
            draw.rectangle(((x0,y0),(x1,y1)), outline=(0,0,0), fill=colors[j])
            t += ratio
        name = names[i]#data[i].get(KEYWORD_ID, '{}'.format(i + 1))
        spacer = size * 0.02
        x0 = xcnv(0)
        x1 = xcnv(1)
        draw.text((x0 - draw.textsize(name)[0] - spacer, y0), name, fill=(0,0,0))
        score = result.get('score', [])
        decision = int(result.get('predicted', None))
        if decision is not None:#s[i] is not None:#output_groups is not None:
            color = colors[decision]#__MARKER_COLORS[decision]
            if group_labels is not None:
                label = group_labels[decision]
            else:
                label = '{}'.format(decision)
            #label = decisions[i]
            #label = output_groups[decisions[i]]
            draw.text((x1 + spacer, y0), label, fill=color)
    image.save(filename_bar)
    return filename_bar

def draw_weight_chart(weight, size=400, filename=None):
    """Draw a graph of parameter weights
    """
    if filename is None:
        filename = tempfile.mktemp('.png')
    w, h = size, size
    image = Image.new('RGB', (w, h))
    draw = ImageDraw.ImageDraw(image)
    draw.rectangle(((0,0),(size,size)), fill=(255,255,255), outline=(255,255,255))
    wmax = max(weight.values())
    fig = math.floor(math.log10(wmax))
    rem = math.log10(wmax) - fig
    if 0 < rem < 0.3:
        vmax = 2 * (10 ** fig)
    elif rem < 0.70:
        vmax = 5 * (10 ** fig)
    else:
        vmax = 10 ** (fig + 1)
    left = w / 3
    xcnv = lambda x_: float(x_) / vmax * (w * 2 / 3 - 10) + w / 3
    dy = h / (len(weight) + 2)
    y = dy
    bh = dy * 0.8
    by = dy
    x0 = xcnv(0)
    x1 = xcnv(vmax)
    for v in 0, vmax:
        label = '{}'.format(v)
        draw.text((xcnv(v) - draw.textsize(label)[0] / 2, 0), label, fill=(0,0,0))
    color = 0, 128, 0
    offset = dy * 0.25
    for key in sorted(weight.keys(), key=lambda x_:weight[x_], reverse=True):
        value = weight[key]
        x = xcnv(value)
        draw.rectangle(((x0, y+offset), (x,y+bh + offset)), outline=(0,0,0), fill=color)
        draw.text((x0 - draw.textsize(key)[0] - 5, y), key, fill=(0,0,0))
        y += dy
    y0 = dy
    y1 = dy * (len(weight) + 1.5)
    draw.rectangle(((x0,y0),(x1,y1)), outline=(0,0,0))
    image.save(filename)
    return filename

def draw_treemodel(tree, fields, size=400, filename=None):#**kwargs):
    """Draw a tree and save as PNG file
    @Parameters:
        tree : Decision tree converted from a skleran tree object in random forest
        fields : applied fields
        size : graph size
        filename : destination
    @Returns:
        output PNG filename
    """
    if filename is None:
        filename = tempfile.mktemp('.png')
    image = Image.new('RGB', (size, size))
    draw = ImageDraw.ImageDraw(image)
    draw.rectangle(((0,0),(size,size)), fill=(255,255,255), outline=(255,255,255))
    max_depth = max([node['y'] for node in tree])

    box_hratio = 0.25#kwargs.get('box_xratio', 0.25)
    box_vratio = 0.10#kwargs.get('box_yratio', 0.10)

    node_id = 0
    next_ids = [0,]
    layer = 1

    w = h = size
    left = top = 0

    dy = h / (max_depth + 1) # vertical step
    bw, bh = int(w * box_hratio), int(h * box_vratio) # box size
    bx, by = (w - bw) // 2 + left, top + bh / 2# box position
    position_cache = {0:[bx , by]}
    toffset = bh / 2
    colors = __MARKER_COLORS
    top = 0
    box_spacer = 5

    # count elements in layers
    lcount = {}
    for n_ in tree:
        y = n_['y']
        lcount[y] = lcount.get(y, 0) + 1

    for node in tree:
        x, layer = node['x'], node['y']
        num_elems = lcount[layer]
        bw_ = max(20, min(w / num_elems - box_spacer, bw))
        bx = ((x + .5) * w / num_elems) + left - bw_ / 2
        by = top + dy * layer + bh / 2
        #print('layer={}, n={}, x={}/{}, bx={}'.format(layer, num_elems, x, num_elems, bx))
        if not node['leaf']: # leaf
            field = int(node['feature'])
            children = node['children']
            threshold = node['threshold']
            draw.rectangle(((bx,by),(bx+bw_,by+bh)),outline=(10,10,20))
            cnd = '{} < {:.2f}'.format(fields[field], threshold)
            tw = draw.textsize(cnd)[0]
            if tw <= bw_:
                draw.text((bx + (bw_ - tw) / 2, by + toffset), cnd, fill=(0,0,0))
            else:
                draw.text((bx + (bw_ - draw.textsize(fields[field])[0]) / 2, by + toffset - bh // 4), fields[field], fill=(0,0,0))
                label = ' < {:.2f}'.format(threshold)
                draw.text((bx + (bw_ - draw.textsize(label)[0]) / 2, by + toffset + bh // 4), label, fill=(0,0,0))

            for child in children:
#                print(child, len(tree))
                if child >= len(tree): continue
                dec = tree[child]
                cx, cy = dec['x'], dec['y']
                cx = ((cx + .5) * w / lcount[cy]) + left# - bw / 2
                cy = top + dy * cy + bh / 2
                draw.line(((bx + bw_ / 2,by+bh),(cx,cy)), fill=(0,0,0))
        else:
            value = node['value']
            total = sum(value)
            color = [0,0,0]
            sections = []
            for i, val in enumerate(value): sections.append([i, val])
            theta = -90
            rect = ((bx+(bw_-bh)/2,by),(bx+(bw_+bh)/2,by+bh))
            for elem in sorted(sections, key=lambda x_:x_[1], reverse=True):
                #red, green, blue = colors[elem[0] % len(colors)]
                num = elem[1]
                if num <= 0: continue
                rad = int(round(num * 360.0 / total))
                t = (theta + rad * .5) / 180 * math.pi
                if num == total:
                    draw.ellipse(rect, fill=colors[elem[0] % len(colors)])
                    xl, yl = (bx + bw_ * .5, by + 10)
                else:
                    draw.pieslice(rect, start=int(round(theta)), end=int(round(theta + rad)), fill=colors[elem[0] % len(colors)])
                    xl = bx + bw_ * .5 + bh * 0.3 * math.cos(t)
                    yl = by + bh * .5 + bh * 0.3 * math.sin(t) - 5
                draw.text((xl, yl), '{}'.format(int(round(num))), fill=(64,64,64))
                theta += rad
            draw.ellipse(rect, outline=(20,30,20))
            pass
    image.save(filename)
    return filename

def __format_data_table(data, fields=None):
    table = data['analysisset']
    fi = data.get('field_id', None)
    fo = data.get('field_out', None)
    group_labels = data.get('group_label', None)
    if fields is None:
        fields = []
        if fi is not None: fields.append(fi)
        if fo is not None: fields.append(fo)
        fields = fields + sorted([f for f in table[0].keys() if f != fi and f != fo])
    else:
        accepted = False
        header = []
        if fi not in fields: header.append(fi)
        if fo not in fields:
            for row in table:
                if fo in row:
                    header.append(fo)
                    break
        fields = header + fields

    decision = data.get('prediction', None)
    contents = '<table id="prediction_table">\n'

    # header, fields
    contents += '<thead><tr>'
    if decision is not None:
        contents += '<th>Predicted</th>'
    for f in fields:
        if f == fi:
            label = 'ID'
        elif f == fo:
            label = 'Observed'
        else:
            label = f
        contents += '<th>{}</td>'.format(label)
    contents += '</tr></thead>\n<tbody>'

    # values
    for i, datum in enumerate(table):
        if decision is not None:
            d = int(decision[i]['predicted'])
            gp = group_labels[d]
            gg = datum.get(fo, None)
            if gp == gg:
                elem = '<tr class="success">'
            elif gg is not None:
                elem = '<tr class="failure">'
            else:
                elem = '<tr>'
        contents += elem#'<tr>'
        if decision is not None:
            d = int(decision[i]['predicted'])
            if group_labels is not None and 0 <= d < len(group_labels):
                contents += '<td>{}</td>'.format(group_labels[d])
            else:
                contents += '<td>{}</td>'.format(d)
        for f in fields:
            val = datum.get(f, '')
            if isinstance(val, float) and (val - round(val) < 1e-4):
                val = int(val)
            contents += '<td>{}</td>'.format(val)
        contents += '</tr>\n'
    contents += '</tbody></table>\n'
    return contents

def generate_report(key, data, dstdir, timestamp, verbose=False):
    """Replace HTML keywords with processed texts, figures or tables.
    @Parameters:
        key : keyword given such as <%KEY%>
        data : all data
        dstdir : document output directory
        timestamp : unique id for the document
    @Return:
        HTML elements
    """
    if verbose:
        sys.stderr.write('PROCESSING : {}\n'.format(key))
    try:
        if key == 'bargraph':
            if 'prediction' in data and 'analysisset' in data:
                field = data['field_id']
                names = [datum[field] for datum in data['analysisset']]
                filename = 'bar_{}.png'.format(timestamp)
                group_labels = data.get('group_label', None)
                draw_bar_chart(names, data['prediction'], group_labels=group_labels, filename=os.path.join(dstdir, filename))
                return '<img src="{}" id="bargraph">'.format(filename)
        elif key == 'best_tree':
            if 'best_tree' in data:
                filename = 'tree_{}.png'.format(timestamp)
                draw_treemodel(data['best_tree'], data['field'], filename=os.path.join(dstdir, filename))
                return '<img src="{}" id="besttree">'.format(filename)
        elif key == 'best_score':
            if 'best_tree' in data and 'prediction' in data:
                pred = data['prediction']
                values = data['analysisset']
                field_out = data['field_out']
                success = failure = 0
                group_labels = data['group_label']
                for i in range(len(values)):
                    p = pred[i].get('best_tree', None)
                    g = values[i].get(field_out, None)
                    if p is not None and g is not None:
                        group_label = group_labels[int(p)]
                        if group_label == g:#int(p) == int(g):
                            success += 1
                        else:
                            failure += 1
                if success + failure > 0:
                    return '<span id="best_tree_score">{:.2f}%</span>'.format(success * 100.0 / (success + failure))
        elif key == 'weightgraph':
            if 'weight' in data:
                weight = data['weight']
                filename = 'weight_{}.png'.format(timestamp)
                draw_weight_chart(weight, filename=os.path.join(dstdir, filename))
                return '<img src="{}" id="weightgraph">'.format(filename)
        elif key == 'datatable':
            if 'analysisset' in data:
                return __format_data_table(data, data.get('field', None))
        elif key == 'condition':
            if 'condition' in data:
                condition = data['condition']
                contents = '<table>\n'
                for key, value in condition.items():
                    contents += '<tr><td>{}</td><td>{}</td></tr>\n'.format(key, value)
                contents += '</table>\n'
                return contents
    except Exception as e:
        sys.stderr.write('ERROR :{}\n'.format(repr(e)))
        return '<!--ERROR-->'.format(repr(e).replace('>', ''))
    return '<!--NO_DATA:{}-->'.format(key)

def __get_timestamp():
    # timestamp
    import time
    lt = time.localtime()
    timestamp = '{}'.format(lt.tm_year)
    for n in lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec:
        timestamp += '00{}'.format(n)[-2:]
    return timestamp

def __get_default_contents():
    return __default_template

def generate_report_document(data, destination, filename_template=None):
    """Convert results into HTML document
    @Parameters:
        data : dict object containing parameters, data and predicted results
        destination : directory name for output
        filename_template : HTML template if you customize output
    @Return:
        filename of HTML report
    """
    if filename_template is None:
        contents = __get_default_contents()
    else:
        contents = ''
        with open(filename_template) as fi:
            contents += fi.readline().strip()
    if os.path.exists(destination) is None:
        os.makedirs(destination)
    timestamp = __get_timestamp()
    filename_report = os.path.join(destination, 'report_{}.html'.format(timestamp))
    pat = re.compile('<%(.*?)%>', re.M)
    pos = 0
    def escape_html(txt):
        txt.sub('<', '&lt;').replace('>', '&')
        return txt
    with open(filename_report, 'w') as fo:
        while 1:
            m = pat.search(contents, pos)
            if m is None: break
            fo.write(contents[pos:m.start()])
            label= m.group(1).strip()
            if label[0] == '=':
                value = data.get(label[1:].strip(), None)
                if value is not None:
                    fo.write(urllib2.quote(value))
            else:
                fo.write(generate_report(label.strip(), data, destination, timestamp=timestamp))#contents(key, dat.get(value, None))
            pos = m.end()
        fo.write(contents[pos:])
    return filename_report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', default=sys.argv[1], help='JSON file')
    parser.add_argument('-o', default='out', help='output directory')
    parser.add_argument('-t', default=None, help='output directory')
    args.parse_args()
    with open(args.i) as fi:
        data = json.load(fi)
    if 'title' not in data:
        fn = os.path.basename(args.i)
        if fn.rindex('.') > 0:
            title = fn[0:fn.rfind('.')]
        else:
            title = fn
        data['title'] = title
    generate_report_document(data, args.o, args.t)
