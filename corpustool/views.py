from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
# Create your views here.

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

import scipy.stats
import statsmodels.api as sm
import pandas as pd

import html
import io, urllib.parse, base64

from .models import *

def describe(subcorpus_params):
    subcorpus_description = ''
    keys = [key for key in subcorpus_params]
    i = 0
    while i < len(keys):
        if i > 0:
            subcorpus_description += ', '
        key = keys[i]
        if key.split('__') [-1] == 'lte':
            low_lim = key[:key.rfind('__')]+'__gte'
            if low_lim in keys:
                subcorpus_description += subcorpus_params[low_lim]+'<='+key[:key.rfind('__')]+'<='+subcorpus_params[key]
                keys.remove(low_lim)
            else:
                subcorpus_description += key[:key.rfind('__')]+'>='+subcorpus_params[key]
        elif key.split('__')[-1] == 'gte':
            up_lim = key[:key.rfind('__')]+'__lte'
            if up_lim in keys:
                subcorpus_description += subcorpus_params[key]+'<='+key[:key.rfind('__')]+'<='+subcorpus_params[up_lim]
                keys.remove(up_lim)
            else:
                subcorpus_description += key[:key.rfind('__')]+'<='+subcorpus_params[key]
        else:
            subcorpus_description += key+'='+subcorpus_params[key]
        i += 1
    return subcorpus_description

def st_color(p_value):
    ## Colour codes:
    ## white - p-value > 0.1
    ## yellow - 0.1 <= p-value < 0.05
    ## orange - 0.05 <= p-value < 0.01
    ## red - pvalue <= 0.01
    if p_value <= 0.1:
        if p_value <= 0.05:
            if p_value <= 0.01:
                return "red"
            return "orange"
        return "yellow"
    return "black"

def F_color(p_value):
    ## Colour codes:
    ## white - p-value in (0.1, 0.9)
    ## yellow - p-value not in (0.1, 0.9)
    ## orange - p-value not in (0.05, 0.95)
    ## red - p-value not in (0.01, 0.99)
    if p_value >= 0.9 or p_value <= 0.1:
        if p_value >= 0.95 or p_value <= 0.05:
            if p_value >= 0.99 or p_value <= 0.01:
                return "red"
            return "orange"
        return "yellow"
    return "black"

def get_all_departments():
    return pd.DataFrame(Document.objects.exclude(department=None).values('department'))['department'].value_counts().head(n=40).index

def get_all_POS():
    return [i['pos'] for i in Lemma.objects.values('pos').distinct()]

def get_all_XPOS():
    return [i['xpos'] for i in Token.objects.values('xpos').distinct()]

def get_all_deps():
    return [i['typerel'] for i in DepRel.objects.values('typerel').distinct()]

def get_counts(ling_params, corpus):
    ''' Accepts:
    ling_params - QueryDict of linguistic parameters,
    corpus - QuerySet of documents
    Returns:
    Array of linguistic item counts in selected corpus'''
    print(ling_params)
    if ling_params["type"] == 'singleItem':
        params = {'occurence__'+key: ling_params[key] for key in ling_params if key!="type"}
        corpus = corpus.annotate(item_count=Count('occurence', filter=Q(**params))).values('item_count')
    elif ling_params["type"] == "syntPair":
        dep_params = {'occurence__head__dependant__' + key[:-3]: ling_params[key] for key in ling_params if key.endswith('Dep')}
        head_params = {'occurence__' + key: ling_params[key] for key in ling_params if  key!="type" and not key.endswith('Dep')}
        corpus = corpus.annotate(item_count=Count('occurence', filter=Q(**dep_params, **head_params))).values('item_count')
    else:
        raise Exception("Invalid value for 'type' field")
    return np.array([i['item_count'] for i in corpus])

## taken from https://stackoverflow.com/questions/8671808/matplotlib-avoiding-overlapping-datapoints-in-a-scatter-dot-beeswarm-plot:
def rand_jitter(arr):
    # fix random jitter:
    np.random.seed(42)
    stdev = 0.1*(max(arr)-min(arr))
    return arr + np.random.randn(len(arr)) * stdev

colors = ['red', 'yellow', 'blue', 'green', 'cyan', 'magenta', 'black']

@login_required
def index(request):
    ''''''
    return render(request, "index.html", {'department_options': get_all_departments(), 'parts_of_speech': get_all_POS(), 'tags': get_all_XPOS(),
    'deps': get_all_deps()})

@login_required
def show_correlation(request):
    if request.POST:
        matplotlib.use('Agg')
        print(request.POST)
        plt.ioff()
        ## check that request is accepted:
        subcorpora = set([i.split('-')[0] for i in request.POST if i.startswith('subcorpus')])
        ## изменить поведение, в зависимости от того, принимает поле формы
        ## var-type1, var-type2 значение singleItem или syntPair:
        lingvar1_params = {param.split('-')[1]:request.POST[param] for param in request.POST if param.startswith("var1") and request.POST[param] and request.POST[param] != 'na'}
        lingvar2_params = {param.split('-')[1]:request.POST[param] for param in request.POST if param.startswith("var2") and request.POST[param] and request.POST[param] != 'na'}
        lingvar1_name = ', '.join([key+"="+val for key, val in lingvar1_params.items()])
        lingvar2_name = ', '.join([key+"="+val for key, val in lingvar2_params.items()])
        colIndex = 0
        correlations = []
        regressions = []
        regression_models = []
        for subcorpus in subcorpora:
            subcorpus_params = {param.split('-')[1]: request.POST[param] for param in request.POST if param.startswith(subcorpus) and request.POST[param] and request.POST[param] != 'na'}
            docs = Document.objects.filter(**subcorpus_params)
            if not docs:
                continue
            x, y = get_counts(lingvar1_params, docs), get_counts(lingvar2_params, docs)
            
            ## forming proper subcorpus description string:
            subcorpus_description = describe(subcorpus_params)
            
            ## providing names for regression x and y:
            x = pd.Series(x).rename(lingvar1_name)
            y = pd.Series(y).rename(lingvar2_name)

            correlations.append((subcorpus_description, scipy.stats.pearsonr(x, y), len(x)))
            regression = sm.OLS(y, sm.add_constant(x)).fit()
            regression_models.append(regression.params)
            regressions.append((subcorpus_description, [table.as_html() for table in regression.summary().tables]))
            plt.scatter(rand_jitter(x), rand_jitter(y), color=colors[colIndex], label=subcorpus_description)
            colIndex += 1
        
        ##plotting the regression lines:
        start, stop = plt.xlim()
        points = np.arange(start=start, stop=stop)
        colIndex = 0
        for b, a in regression_models:
            plt.plot(points, points*a + b, color=colors[colIndex])
            colIndex += 1

        ##end of plotting
        plt.xlabel(lingvar1_name)
        plt.ylabel(lingvar2_name)
        plt.legend()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.clf()
        buf.seek(0)
        string = base64.b64encode(buf.read())

        ##equality check for pearsonr:
        r2_stats = [[None for i in range(len(correlations))] for j in range(len(correlations))]
        idx1 = 0
        for descr1, corr1, n1 in correlations:
            idx2 = 0
            for descr2, corr2, n2 in correlations:
                if idx1 == idx2:
                    r2_stats[idx1][idx2] = ('', '', 'black')
                else:
                    z = np.arctanh(corr1[1]-corr2[1])
                    se = (1/(n1-3) + 1/(n2-3)) ** 0.5
                    z = z/se
                    p_value = (1-scipy.stats.norm.cdf(abs(z))) * 2
                    color = st_color(p_value)
                    r2_stats[idx1][idx2] = (z, p_value, color)
                idx2 += 1
            idx1 += 1
        
        ##formatting regression coefficients:
        for i in range(len(regression_models)):
            regression_models[i][0] = round(regression_models[i][0], 4)
            regression_models[i][1] = round(regression_models[i][1], 4)
        
        ##formatting correlations and adding regression coefficients:
        for i in range(len(correlations)):
            correlations[i] = (correlations[i][0], (round(correlations[i][1][0], 4), correlations[i][1][1]) + tuple(regression_models[i]))

        url = 'data:image/png;base64,' + urllib.parse.quote(string)

        args = {'image': url, 'correlations': correlations, 'regressions': regressions,
        'r2_stats': zip(correlations, r2_stats)}
        
        return render(request, 'corr_report.html', args)

    return HttpResponse('Invalid request')

@login_required
def entity_stats(request):
    return render(request, "entity_stats.html", {'department_options': get_all_departments(), 'parts_of_speech': get_all_POS(), 'tags': get_all_XPOS(),
    'deps': get_all_deps()})

@login_required
def show_entity_stats(request):
    ## Welch's test for means - https://stattrek.com/hypothesis-test/difference-in-proportions.aspx
    ## T-test for variances - https://stattrek.com/hypothesis-test/difference-in-proportions.aspx
    ## Z-test for proportions - https://stattrek.com/hypothesis-test/difference-in-proportions.aspx
    if request.POST:
        plt.ioff()
        subcorpora = set([i.split('-')[0] for i in request.POST if i.startswith('subcorpus')])
        ## изменить поведение, в зависимости от того, принимает поле формы
        ## var-type значение singleItem или syntPair:
        lingvar_params = {param.split('-')[1]:request.POST[param] for param in request.POST if param.startswith('var') and request.POST[param] and request.POST[param] != 'na'}
        summaries = []
        min_freq = 0
        max_freq = 0
        pdfs = []
        for subcorpus in subcorpora:
            subcorpus_params = {param.split('-')[1]: request.POST[param] for param in request.POST if param.startswith(subcorpus) and request.POST[param] and request.POST[param] != 'na'}
            docs = Document.objects.filter(**subcorpus_params)
            if not docs:
                continue
            x = get_counts(lingvar_params, docs)
            try:
                pdfs.append(scipy.stats.gaussian_kde(x))
            except:
                pass

            if x.max() > max_freq:
                max_freq = x.max()
            if x.min() < min_freq:
                min_freq = x.min()
            ## forming proper subcorpus description string:
            subcorpus_description = describe(subcorpus_params)
            summaries.append((subcorpus_description, (x.sum(), x.mean(), x.var(), x.std(), x.min(), x.max(), len(x.nonzero()[0]),
            len(x.nonzero()[0])/len(x), len(x))))
        entity_desc = ', '.join([key+"="+val for key, val in lingvar_params.items()])

        ## plotting the densities:
        points = np.arange(start=min_freq, stop=max_freq)
        colIndex = 0
        for pdf, summary in zip(pdfs, summaries):
            label = summary[0]
            plt.plot(points, pdf(points), color=colors[colIndex], label=label)
            colIndex += 1

        ##saving the density plot:
        plt.xlabel(entity_desc)
        plt.ylabel("approximated Probability Density Function")
        plt.legend()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.clf()
        buf.seek(0)
        string = base64.b64encode(buf.read())
        url = 'data:image/png;base64,' + urllib.parse.quote(string)

        ##так-с, ё-маё, тут equality tests:
        mean_test_stats = [[None for i in range(len(summaries))] for j in range(len(summaries))]
        var_test_stats = [[None for i in range(len(summaries))] for j in range(len(summaries))]
        prop_test_stats = [[None for i in range(len(summaries))] for j in range(len(summaries))]
        idx1 = 0
        for descr1, summary1 in summaries:
            idx2 = 0
            for descr2, summary2 in summaries:
                if idx1 == idx2:
                    mean_test_stats[idx1][idx2] = ('', '', 'black')
                    var_test_stats[idx1][idx2] = ('', '', 'black')
                    prop_test_stats[idx1][idx2] = ('', '', 'black')
                else:
                    ##test of mean

                    se = (summary1[2]/summary1[8] + summary2[2]/summary2[8]) ** 0.5
                    df = (se ** 4) / (summary1[2]**2 / summary1[8]**2 / (summary1[8] - 1) + summary2[2]**2 / summary2[8]**2 / (summary2[8] - 1))
                    if se == 0:
                        t = 0
                    else:
                        t = (summary1[1] - summary2[1])/se
                    p_value = (1 - scipy.stats.t.cdf(abs(t), df)) * 2
                    color = st_color(p_value)
                    mean_test_stats[idx1][idx2] = (t, p_value, color)

                    ##test of variance

                    F = summary1[2]/summary2[2]
                    df1 = summary1[8] - 1
                    df2 = summary2[8] - 1
                    p_value = scipy.stats.f.cdf(F, df1, df2)
                    color = F_color(p_value)
                    var_test_stats[idx1][idx2] = (F, p_value, color)

                    #test of proportion

                    P_hat = (summary1[7]*summary1[8] + summary2[7]*summary2[8])/(summary1[8] + summary2[8])
                    se = P_hat * (1 - P_hat) * (1/summary1[8] + 1/summary2[8])
                    if se == 0:
                        z = 0
                    else:
                        z = (summary1[8] - summary2[8])/se
                    p_value = (1-scipy.stats.norm.cdf(abs(z))) * 2
                    color = st_color(p_value)
                    prop_test_stats[idx1][idx2] = (z, p_value, color)

                idx2 += 1
            idx1 += 1
        
        args = {'entity': entity_desc, 'summaries': summaries,'mean_test_stats': zip(summaries,mean_test_stats),
        'var_test_stats': zip(summaries,var_test_stats), 'prop_test_stats': zip(summaries,prop_test_stats), 'image': url}

        return render(request, 'show_entity_stats.html', args)

    return HttpResponse('Invalid request')