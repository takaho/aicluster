import sys, os, re
import wx, wx.html
import wx.lib.sized_controls
import wx.lib.newevent

class MainPanel(wx.Panel):
    """Parameter handler panel
    """
    _event_class, EVT_REPORT = wx.lib.newevent.NewEvent()
    EVT_SET_OUTPUT_DIR = 4
    EVT_SELECT_TRAINING_FILE = 1
    EVT_SELECT_PROCESS_FILE = 2
    EVT_EXECUTE = 3
    RANGE_TREE_DEPTH = (2, 10)
    RANGE_NUM_TREES = (2, 200)

    def __init__(self, parent):#, log):
        self.__datadirectory = os.path.curdir#None
        self.__reportdirectory = os.path.curdir#os.path.expanduser('~')
        self.__report = None, None
        self.__output_field = 'OUT'
        self.__id_field = 'ID'
        self.__init_ui(parent)
        self.Bind(self.EVT_REPORT, self.__OnCalculationEnd)

    def __init_ui(self, parent):
        wx.Panel.__init__(self, parent, -1)

        # training data
        l1 = wx.StaticText(self, -1, 'Traning data')#wx.TextCtrl')
        t1 = wx.TextCtrl(self, -1, 'not selected', size=(250, -1))
        b1 = wx.Button(self, 1, "Select file")
        self.fileinput_training = t1
        self.button_training = b1
        self.Bind(wx.EVT_BUTTON, self.OnSelectFile, id=self.EVT_SELECT_TRAINING_FILE)

        # analysis data
        l2 = wx.StaticText(self, -1, "Analysis data")
        t2 = wx.TextCtrl(self, -1, 'not selected', size=(250, -1))
        b2 = wx.Button(self, 2, "Select file")
        self.fileinput_analysis = t2
        self.button_analysis = b2
        self.Bind(wx.EVT_BUTTON, self.OnSelectFile, id=self.EVT_SELECT_PROCESS_FILE)

        #
        l3 = wx.StaticText(self, -1, "Number of trees")
        t3 = wx.TextCtrl(self, -1, "20", size=(40, -1))#, validator=IntValidator())
        t3.Bind(wx.EVT_CHAR, self.__onlyNumber, t3)
        r = MainPanel.RANGE_NUM_TREES
        l3r = wx.StaticText(self, -1, "[{}-{}]".format(r[0], r[1]))
        self.text_numtrees = t3

        l4 = wx.StaticText(self, -1, "Maximum depth")
        t4 = wx.TextCtrl(self, -1, "4", size=(40, -1))#, validator=IntValidator())
        t4.Bind(wx.EVT_CHAR, self.__onlyNumber, t4)
        r = MainPanel.RANGE_TREE_DEPTH
        l4r = wx.StaticText(self, -1, "[{}-{}]".format(r[0], r[1]))
        self.text_maxdepth = t4

        l5 = wx.StaticText(self, -1, "Report")
        t5 = wx.TextCtrl(self, -1, self.__datadirectory, size=(250,-1))
        b5 = wx.Button(self, self.EVT_SET_OUTPUT_DIR, 'Select directory')
        self.dstdir = t5
        self.Bind(wx.EVT_BUTTON, self.OnSelectDir, id=4)

        l6 = wx.StaticText(self, -1, "Output column")
        self.output_field = wx.TextCtrl(self, -1, self.__output_field, size=(40, -1))

        l7 = wx.StaticText(self, -1, 'ID column')
        self.id_field = wx.TextCtrl(self, -1, self.__id_field, size=(40, -1))

        space = 6
        sizer = wx.FlexGridSizer(cols=3, hgap=space, vgap=space)

        bt_ex = wx.Button(self, self.EVT_EXECUTE, "Execute")
        self.Bind(wx.EVT_BUTTON, self.OnExecuteButton, id=self.EVT_EXECUTE)
        self.button_execute = bt_ex

        sizer.AddMany([l1, t1, b1,
                    l2, t2, b2,
                    l5, t5, b5,
                    l3, t3, l3r,
                    l4, t4, l4r,
                    l6, self.output_field, (-1,-1),
                    l7, self.id_field, (-1, -1),
                    bt_ex, (-1,-1),(-1,-1)]
                        )
        border = wx.BoxSizer(wx.VERTICAL)
        border.Add(sizer, 0, wx.ALL, 25)
        self.SetSizer(border)
        self.SetAutoLayout(True)

    def __validate_parameters(self):
        num_trees = self.text_numtrees.GetValue()
        max_depth = self.text_maxdepth.GetValue()
        error = None
        try:
            num_trees = int(num_trees)
            max_depth = int(max_depth)
            if num_trees < 5 or num_trees > 100:
                error = 'Number of trees must be within 5-100'
            elif max_depth < 2 or max_depth > 10:
                error = 'Maximum depth of decision tree must be within 2-10'
        except Exception as e:
            error = repr(e)
        if error:
            diag = wx.MessageDialog(self, error, 'ERROR', wx.OK | wx.ICON_ERROR)
            diag.ShowModal()
            diag.Destroy()
            return False
        else:
            return True

    def __OnCalculationEnd(self, evt):
        """Receive completion of calculation in thread-safe way.
        Display reports writtin in HTML format.
        """
        if evt.error is not None and len(evt.error) > 0:
            diag = wx.MessageDialog(self, evt.error, 'ERROR', wx.OK | wx.ICON_ERROR)
            ret = diag.ShowModal()
            diag.Destroy()
        else:
            frame = wx.Frame(None, -1, 'Report', size=(600,700))
#            print(evt.result)
            html = wx.html.HtmlWindow(frame)
            try:
                html.LoadFile(evt.result)#res)#SetPage(contents)
                frame.Show(True)
            except:
                frame.Show(False)
                diag = wx.MessageDialog(self, 'cannot open the report', 'ERROR', wx.OK | wx.ICON_ERROR)
        #self.button_execute.SetLabel('Execute')
        self.button_execute.Enable()
        wx.EndBusyCursor()

    def OnExecuteButton(self, evt):
        """Start calculation thread"""
        if self.__validate_parameters() is not True:
            return
        # check overwriting ...?

        import threading
        class CalcThread(threading.Thread):
            """Thread of calculator"""
            def __init__(self, parent, params):
                threading.Thread.__init__(self)
                self.parent = parent
                self.parameters = params
                self.__interrupted = False
            def join(self, timeout=None):
                threading.Thread.join(self, timeout)
                self.__interrupted = True
            interrupted = property(lambda s:s.__interrupted)
            def run(self):
                import rfprediction
                fn_t = self.parameters['filename_training']
                fn_i = self.parameters['filename_input']
                dir_out = self.parameters['directory_report']
                output_column = self.parameters.get('output_field', 'OUT')
                id_column = self.parameters.get('id_field', 'ID')
                num_trees = self.parameters.get('num_trees', 20)
                max_depth = self.parameters.get('max_depth', 4)
                try:
                    report_file = rfprediction.execute_analysis(training_file=fn_t,
                        diagnosis_file=fn_i,
                        um_trees=num_trees,
                        max_depth=max_depth,
                        id_field=id_column,
                        output_field=output_column,
                        output=dir_out)
                    result = report_file
                    error = None
                except Exception as e:
                    result = None
                    error = repr(e)
                event = MainPanel._event_class(error=error, result=result)
                wx.PostEvent(self.parent, event) # throw results via messaging system

        self.button_execute.Disable()
        fn_t = self.fileinput_training.GetValue()
        fn_i = self.fileinput_analysis.GetValue()
        if os.path.exists(fn_i) is False:
            fn_i = fn_t
        if os.path.exists(fn_i) is False:
            sys.stderr.write('File not exists\n')
            return
        num_trees = min(MainPanel.RANGE_NUM_TREES[1], max(MainPanel.RANGE_NUM_TREES[0], int(self.text_numtrees.GetValue())))
        max_depth = min(MainPanel.RANGE_TREE_DEPTH[1], max(MainPanel.RANGE_TREE_DEPTH[0], int(self.text_maxdepth.GetValue())))
        dstdir = self.dstdir.GetValue()
        output_field = self.output_field.GetValue()
        id_field = self.id_field.GetValue()
        params = {'filename_training':fn_t, 'filename_input':fn_i, 'directory_report':dstdir,
        'num_trees':num_trees, 'max_depth':max_depth, 'output_field':output_field, 'id_field':id_field}
        CalcThread(self, params).start()
        #self.button_execute.SetLabel('Calculating')
        wx.BeginBusyCursor()
        return

    def __onlyNumber(self, evt):
        keycode = evt.GetKeyCode()
        if 32 <= keycode < 255:
            if chr(keycode).isdigit(): evt.Skip()
            return False
        return evt.Skip()

    def OnSelectDir(self, evt):
        """Select report directory"""
        src = evt.GetEventObject()
        target = None
        if evt.GetId() == self.EVT_SET_OUTPUT_DIR:
            target = self.dstdir
        else:
            return
        dd = wx.DirDialog(self, 'Select directory', self.__reportdirectory, wx.DD_DEFAULT_STYLE)
        if dd.ShowModal() == wx.ID_OK:#CENCEL:
            path = dd.GetPath()
            self.dstdir.SetValue(path)
            self.__reportdirectory = path
            return
        dd.Destroy()
#        path = dd.GetPath()
#        print(path)


    def OnSelectFile(self, evt):
        """Open file dialog of data """
        evid = evt.GetId()
        if evid ==  self.EVT_SELECT_TRAINING_FILE:
            target = self.fileinput_training
        elif evid == self.EVT_SELECT_PROCESS_FILE:
            target = self.fileinput_analysis
        else:
            return
        fd = wx.FileDialog(self, 'Open file', 'a', 'b',
            'Excel file (*.xlsx,*.xls)|*.xlsx;*.xls|CSV file (*.csv,*.txt)|*.txt;*.csv', wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if self.__datadirectory is None:
            self.__datadirectory = os.path.curdir
        fd.SetDirectory(self.__datadirectory)
        if fd.ShowModal() == wx.ID_OK:#CANCEL:
            self.__datadirectory = os.path.dirname(fd.GetPath())
            target.SetValue(fd.GetPath())
        fd.Destroy()

class AppMainWindow(wx.Frame):
    """Container window of the application"""
    def __init__(self, *args, **kwargs):
        super(AppMainWindow, self).__init__(*args, **kwargs)
        self.InitUI()

    def InitUI(self):
        menuBar = wx.MenuBar()
        menu = wx.Menu()
        item = menu.Append(wx.ID_EXIT, "E&xit\tCtrl-Q", "Exit demo")

        #self.Bind(wx.EVT_MENU, self.OnExitApp, item)
        menuBar.Append(menu, "&File")
        #self.Bind(wx.EVT_MENU, self.OnExitApp, item)
        self.SetMenuBar(menuBar)

        #self.ShowStatusBar()
        MainPanel(self)

        self.SetTitle("Atopy cluster machine")
        self.SetPosition((200, 200))
        self.SetSize((600, 400))
        self.Show(True)

if __name__ == '__main__':
    app = wx.App()
    win = AppMainWindow(None)
    app.MainLoop()
