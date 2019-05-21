from corpustool.models import *
from stattool.settings import LANG_MODEL_PATH, TEXT_FILE_PATH
from django.core.management.base import BaseCommand
import os
import json
import re
import time

import spacy


def cached(func, *args, **kwargs):  # correct signature is not known
    if not hasattr(cached, "cache"):
        cached.cache = []
    
    def cache_clear():
        cached.cache = []

    def find_in_cache(*args, **kwargs):
        if (args, kwargs) in cached.cache:
            return None
        cached.cache.append((args, kwargs))
        return func(*args, **kwargs)
    
    find_in_cache.cache_clear = cache_clear
    find_in_cache.__name__ = func.__name__
    find_in_cache.__doc__ = func.__doc__
    find_in_cache.__module__ = func.__module__
    return find_in_cache

@cached
def try_to_get(Model, *args, **kwargs):
    ''' 
    Returns Model instance with specified property if it exists,
    If it doesn't creates a new one
    
    Arguments:
    Model - a class inherited from django models.Model
    *args, **kwargs - unnamed and named properties of needed object
    '''
    #print(kwargs)
    try:
        obj = Model.objects.get(*args, **kwargs)
    except Model.DoesNotExist:
        obj = Model(*args, **kwargs)
        return obj

def parse_rus_date(s):
    s = s.split('.')
    if len(s) != 3 or len(s[0]) != 2 or len(s[1]) != 2 or len(s[2]) != 4:
        return None
    try:
        datetime.datetime(int(s[2]), int(s[1]), int(s[0]))
        return s[2]+'-'+s[1]+'-'+s[0]
    except:
        return None

def check_int(s):
    try:
        int(s)
        return True
    except:
        return False

def escapepath(fp):
    return fp.replace(os.sep, '%').replace('/', '%')

extension_split = lambda x: x[:x.rfind('.')]

class TextBaseFiller(object):
    def __init__(self, model=None, folder='.', recursive=True, include_metadata=False):
        self.parser = model
        
        self.include_metadata = include_metadata
        self.folder = folder
        self.text_filenames = []
        if recursive:
            for root, dirs, files in os.walk(self.folder):
                for f in files:
                    if f.endswith('.txt'):
                        self.text_filenames.append(os.path.join(root, f))
        else:
            self.text_filenames = [os.path.join(self.folder, f) for f in os.listdir(self.folder) if f.endswith('.txt')]
        self.current_text_id = 0
    
    
    def process_all(self, show_titles=False, show_time = False):
        st_time = time.time()
        while self.current_text_id < len(self.text_filenames):
            if show_titles:
                print(self.text_filenames[self.current_text_id])
            if show_time:
                print(time.time() - st_time)
            self.process_next()
    
    
    def process_next_n(self, n, show_titles=False, show_time = False):
        st_time = time.time()
        limit = min(self.current_text_id + n, len(self.text_filenames))
        while self.current_text_id < limit:
            if show_titles:
                print(self.text_filenames[self.current_text_id])
            if show_time:
                print(time.time() - st_time)
            self.process_next()
    
    
    def process_next(self):
        if self.current_text_id >= len(self.text_filenames):
            print('Specified folder is fully processed')
            return
        
        fn = self.text_filenames[self.current_text_id]
        
        title = escapepath(fn[len(self.folder):])
        self.textobj = Document(title=title)
        if self.include_metadata:
            self.process_metadata()
        self.textobj.save()
        with open(fn, 'r', encoding='utf-8') as f:
            parsed = self.parser(f.read().replace('\ufeff', ''))
        
        try_to_get.cache_clear()
        
        ##saving lemmas to db:
        # try:
        lemmas = [try_to_get(Lemma, text=token.lemma_, pos=token.pos_) for token in parsed]
        Lemma.objects.bulk_create([lemma for lemma in lemmas if lemma is not None and lemma.pk is None])
        # except:
        #     ## skipping files with any non-utf8 shit:
        #     self.current_text_id += 1
        #     return
        
        ##saving tokens to db:
        # try:
        tokens = [try_to_get(Token, text=token.text, lemma = Lemma.objects.get(text=token.lemma_,
                                                                                pos=token.pos_),
                                                                                xpos=token.tag_) for token in parsed]
        Token.objects.bulk_create([token for token in tokens if token is not None and token.pk is None])
        # except:
        #     ## skipping files with any non-utf8 shit:
        #     self.current_text_id += 1
        #     return
        
        ##saving occurences to db:
        # try:
        occurences = [Occurence(document=self.textobj,
                                token=Token.objects.get(text=token.text,
                                                        lemma = Lemma.objects.get(text=token.lemma_,
                                                                                    pos=token.pos_),
                                                                                    xpos=token.tag_),
                                index=token.i) for token in parsed]
        Occurence.objects.bulk_create(occurences)
        # except:
        #    ## skipping any non-utf8 shit:
        #    pass
        
        ##saving deprels to db:
        relations = [DepRel(head=Occurence.objects.get(document=self.textobj, index=token.head.i),
                            dependant=Occurence.objects.get(document=self.textobj, index=token.i),
                            typerel=token.dep_) for token in parsed if token.head.text != 'ROOT']
        DepRel.objects.bulk_create(relations)

        self.current_text_id += 1
    
    def process_metadata(self):
        fn = extension_split(self.text_filenames[self.current_text_id]) + '.json'
        if os.path.exists(fn):
            with open(fn, 'r', encoding='utf-8') as inp:
                try:
                    meta = json.load(inp)
                except:
                    return
            if 'sex' in meta:
                if meta['sex'] in ('m','f'):
                    self.textobj.sex = meta['sex']
            if 'date' in meta:
                parsed_date = parse_rus_date(meta['date'])
                if parsed_date is not None:
                    self.textobj.date = parsed_date
            if 'mark' in meta:
                if check_int(meta['mark']):
                    self.textobj.mark = meta['mark']
            if 'study_year' in meta:
                if check_int(meta['study_year']):
                    self.textobj.study_year = meta['study_year']
            if 'department' in meta:
                if len(meta['department']) < 30:
                    self.textobj.department = meta['department']

class Command(BaseCommand):
    help = 'Fills database with text data extracted by parser'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--folder', type=str, help='Folder to process')

    def handle(self, *args, **kwargs):
        nlp = spacy.load(LANG_MODEL_PATH)

        if kwargs['folder']:
            if os.path.exists(kwargs['folder']):
                folder = kwargs['folder']
            else:
                folder = os.path.join(TEXT_FILE_PATH, kwargs['folder'])
        else:
            folder = TEXT_FILE_PATH
    
        base_filler = TextBaseFiller(model=nlp, folder=folder, include_metadata=True)
        base_filler.process_all(show_titles=True)