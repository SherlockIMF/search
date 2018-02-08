#!flask/bin/python

from flask import Flask, render_template, request, redirect, url_for
from gensim import corpora, models, similarities, utils
from gensim.parsing.preprocessing import STOPWORDS
import pandas as pd
import re, operator

app = Flask(__name__)

dictionary = corpora.Dictionary.load('./index/imf.dict')
corpus = corpora.MmCorpus('./index/corpus.mm')
tfidf = models.TfidfModel.load('./index/tfidf.model')
lsi = models.LsiModel.load('./index/lsi.model')
lda = models.LdaModel.load('./index/lda.model')
bigram = models.Phrases.load('./index/bigram.model')
trigram = models.Phrases.load('./index/trigram.model')
doc2vec = models.Word2Vec.load('./index/clean_imf2vec_CBOW300.model')
tfidf_index = similarities.MatrixSimilarity.load('./index/tfidf.index')
lsi_index = similarities.MatrixSimilarity.load('./index/lsi.index')
lda_index = similarities.MatrixSimilarity.load('./index/lda.index')


def tokenize(text):
    return [token for token in utils.simple_preprocess(text) if token not in STOPWORDS]

def highlight_sentence(x, keys):
    highlights = []
    for key in keys:
        if key in STOPWORDS:
            continue
        for i, m in enumerate(re.finditer('\\b(' + key + ')\\b', x, re.I|re.M)):
            snippet = x[m.start()-60:m.end() + 60]
            snippet = snippet.replace(m.group(), '<span class="bg-primary">&nbsp;' + m.group() + '&nbsp;</span>')
            highlights.append(snippet)
            if i > 3:
                break

    return '...' + '... <br> ...'.join(highlights) + '...'


search_request = {
    'txt': '',
    'index': 0
}


class SearchEngine:
    search_criteria = ''
    master_keys = []
    cols = []
    num_best = 1000
    pdfs = pd.DataFrame()
    results = pd.DataFrame()
    authors = {}
    
    def __init__(self, data_url, best=1000, columns=['title', 'Authors', 'subject', 'summary', 'issue', 'Country ISO Codes', 'FullTextURL',  'Text', 'FileName']):
        self.pdfs = pd.read_pickle(data_url)
        self.cols = columns
        self.num_best = best

    def search_by_author(self, author):
        keys = author.split()
        query = '^' + ''.join(['(?=.*\\b' + key.replace('.','\.').replace(',', '') + '\\b)' for key in keys if len(key) > 2]) + '.*'
        self.search_criteria = self.search_criteria + ' author: [' + '+'.join(keys) + '] '
        self.master_keys.extend(keys)
        self.authors = []
        self.results = self.pdfs[self.pdfs['Authors'].str.contains(query, regex=True, case=False)].reset_index(drop=False)
        self.results['ID'] = self.results['index']
        self.results.sort_values('issue', ascending=False, inplace=True)
        return self.results
    
    def search_by_title(self, title):
        keys = title.split()
        query = '^' + ''.join(['(?=.*\\b' + key.replace('.','\.') + '\\b)' for key in keys if key not in STOPWORDS and len(key) > 2]) + '.*'
        self.search_criteria = self.search_criteria + ' title: [' + '+'.join(keys) + '] '
        self.master_keys.extend(keys)
        self.authors = []
        self.results = self.pdfs[self.pdfs['title'].str.contains(query, regex=True, case=False)].reset_index(drop=False)
        self.results['ID'] = self.results['index']  
        self.results.sort_values('issue', ascending=False, inplace=True)
        return self.results    
    
    def search_by_index(self, index, query, method):
        self.results = pd.DataFrame(columns=self.cols)
        index.num_best = self.num_best
        self.authors = {}
        r = 1
        for i, w in index[query]:
            row = self.pdfs.ix[i]
            self.results.loc[len(self.results)] = row[self.cols]
            self.results.loc[len(self.results)-1, method + '_Score'] = w
            self.results.loc[len(self.results)-1, 'ID'] = i
            for a in row['Authors'].split(';'):
                a = a.strip()
                if a in self.authors.keys():
                    self.authors[a] = self.authors[a] + w / r**2
                else:
                    self.authors[a] = w / r**2
            r += 1

        self.authors = sorted(self.authors.items(), key=operator.itemgetter(1), reverse=True)
        
        self.results['Sentence'] = self.results['Text'].apply(lambda x: highlight_sentence(x, self.master_keys))
        self.results.sort_values(method + '_Score', ascending=False, inplace=True)
        return self.results
    
    def query_expansion(self, text):
        query_phrase = trigram[bigram[tokenize(text)]]
        self.master_keys = [p.replace('_', ' ') for p in query_phrase]
        query = dictionary.doc2bow(query_phrase)
        return query    
    
    def search_tfidf(self, text):
        query = tfidf[self.query_expansion(text)]
        index = tfidf_index
        self.search_criteria = 'method: tf-idf, '
        return self.search_by_index(index, query, 'TFIDF')

    def search_lsi(self, text):
        query = lsi[self.query_expansion(text)]
        index = lsi_index
        self.search_criteria = 'method: lsi, '
        return self.search_by_index(index, query, 'LSI')
    
    def search_lda(self, text):
        query = lda[self.query_expansion(text)]
        index = lda_index
        self.search_criteria = 'method: lda, '
        return self.search_by_index(index, query, 'LDA')

    def search_w2v(self, text):
        keys = trigram[bigram[tokenize(text)]]
        query_phrase = []
        for key in keys:
            query_phrase.append(key)
            if key in doc2vec.wv.vocab:
                query_phrase.extend([t for t, w in doc2vec.most_similar(positive=[key], topn=5)])

        self.master_keys.extend([p.replace('_', ' ') for p in query_phrase])
        query = dictionary.doc2bow(query_phrase)
        index = tfidf_index
        self.search_criteria = 'method: tf-idf, '
        return self.search_by_index(index, query, 'TFIDF')

    def resubmit_request(self):
        model = search_request['index']
        all_txt = search_request['txt']

        print 'Resubmit:', model, all_txt
        print len(engine.results)

        if model == '0':
            return self.search_tfidf(all_txt)
        elif model == '1':
            return self.search_lsi(all_txt)
        elif model == '2':
            return self.search_lda(all_txt)
        elif model == '3':
            return self.search_w2v(all_txt)
        elif model == '4':
            return self.search_by_title(all_txt)
        elif model == '5':
            return self.search_by_author(all_txt)

        return self.search_tfidf(all_txt)

    def get_similar_docs(self, did):
        document = self.pdfs.ix[did]
        tfidf_index.num_best = 11
        query_bow = dictionary.doc2bow(document['Text'].lower().split())
        query_tfidf = tfidf[query_bow]

        self.results = pd.DataFrame(columns=self.cols)
        for i, w in tfidf_index[query_tfidf]:
            row = self.pdfs.ix[i]
            self.results.loc[len(self.results)] = row[self.cols]
            self.results.loc[len(self.results)-1, 'Score'] = w
            self.results.loc[len(self.results)-1, 'ID'] = int(i)

        return document

    
    def apply_range(self, begin, end):
        self.results = self.results[(self.results['issue'] >= begin) & (self.results['issue'] <= end)]
        self.results.sort_values('issue', ascending=False, inplace=True)
        return self.results
    
    def sort_by(self, column):
        self.results.sort_values(column, ascending=False, inplace=True)            
        return self.results


engine = SearchEngine('./scraped_meta_join_updated.pickle')


@app.route('/advanced-search/', methods=['POST'])
def render_advanced_search():
    if request.method == 'GET':
        return render_template('search.html')

    author = request.form.get('author').lower()
    title = request.form.get('title').lower()
    all_txt = request.form.get('all').lower()
    model = request.form.get('filter')

    search_request['index'] = model
    engine.search_criteria = ''

    if title != None and title.strip() != '':
        engine.search_by_title(title)
        search_request['txt'] = title
        search_request['index'] = 4

    elif author != None and author.strip() != '':
        engine.search_by_author(author)
        search_request['txt'] = author
        search_request['index'] = 5

    elif all_txt != None and all_txt.strip() != '':
        search_request['txt'] = all_txt        
        if model == '0':
            engine.search_tfidf(all_txt)
        elif model == '1':
            engine.search_lsi(all_txt)
        elif model == '2':
            engine.search_lda(all_txt)
        elif model == '3':
            engine.search_w2v(all_txt)

    return render_template('search.html',
                            title=engine.search_criteria,
                            authors=engine.authors,                            
                            table=engine.results)

@app.route('/search/', methods=['GET', 'POST'])
def render_search():
    if request.method == 'GET':
        return render_template('search.html')

    txt = request.form.get('textinput').lower()
    search_request['txt'] = txt
    search_request['index'] = 0
    if txt == None or txt.strip() == '':
        return render_template('search.html')

    engine.search_tfidf(txt)
    return render_template('search.html',
                            title=engine.search_criteria,
                            authors=engine.authors,
                            table=engine.results)


@app.route('/apply-range/', methods=['GET', 'POST'])
def apply_range():
    begin = int(request.args.get('begin'))
    end = int(request.args.get('end'))
    engine.resubmit_request()    
    engine.apply_range(begin, end)
    return render_template('search.html',
                            title=engine.search_criteria,
                            authors=engine.authors,
                            table=engine.results)


@app.route('/view-doc/', methods=['GET', 'POST'])
def render_doc():
    did = int(request.args.get('id'))
    document = engine.get_similar_docs(did)
    return render_template('view.html',
                            document=document,
                            similar=engine.results)

@app.route('/view-expert/', methods=['GET', 'POST'])
def render_author():
    aid = request.args.get('id')
    engine.search_by_author(aid)
    return render_template('author.html',
                            author=aid,
                            table=engine.results)

@app.route('/similarity/')
def render_similarity():
    return render_template('similarity.html')

@app.route('/sense-embeddings/')
def render_sense_embeddings():
    return render_template('sense_embeddings.html')
        
@app.route('/embeddings-pca/')
def render_pca_embeddings():
    return render_template('embedding.html')

@app.route('/embeddings-clean-skip/')
def render_skip_embeddings():
    return render_template('embedding2.html')

@app.route('/embeddings-sense-cbow/')
def render_cbow_embeddings():
    return render_template('embedding3.html')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
