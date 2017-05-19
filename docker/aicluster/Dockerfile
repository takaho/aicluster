FROM koash/miniconda-4.3.11:0.1.0

RUN conda install \
      scikit-learn \
      numpy \
      scipy \
      pillow \
      xlrd \
      openpyxl \
      nodejs

RUN npm install \
      express \
      sqlite3  

RUN ln -s /usr/bin/nodejs /usr/bin/node

