from django.db import models


# Create your models here.
class Document(models.Model):
    title = models.CharField(max_length=400, null=True)
    date = models.DateField(null=True)
    sex_choices = ('m', 'f')
    sex = models.CharField(max_length=1, choices=[(i,i) for i in sex_choices], null=True)
    mark = models.PositiveSmallIntegerField(null=True)
    study_year = models.IntegerField(null=True)
    department = models.CharField(max_length=30, null=True)

class Lemma(models.Model):
    text = models.CharField(max_length=150)
    pos_tags = ('ADV', 'ADJ', 'INTJ', 'NOUN',
    'VERB', 'PROPN', 'ADP', 'AUX', 'CCONJ',
    'DET', 'NUM', 'PART', 'PRON', 'SCONJ',
    'PUNCT', 'SYM', 'X')
    pos = models.CharField(max_length=5,
    choices=[(i, i) for i in pos_tags])

class Token(models.Model):
    text = models.CharField(max_length=200)
    lemma = models.ForeignKey(Lemma, on_delete=models.CASCADE, null=True)
    xpos = models.CharField(max_length=5, null=True)

class Occurence(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    index = models.IntegerField()

class DepRel(models.Model):
    head = models.ForeignKey(Occurence, related_name='head', on_delete=models.CASCADE, null=True)
    dependant = models.ForeignKey(Occurence, related_name='dependant', on_delete=models.CASCADE, null=True)
    # typerels = (
    #     'nsubj', 'obj', 'iobj', 'obl', 'vocative', 'expl', 'dislocated',
    #     'nmod', 'appos', 'nummod', 'csubj', 'ccomp', 'xcomp', 'advcl',
    #     'acl', 'advmod', 'discourse', 'amod', 'aux', 'cop', 'mark',
    #     'det', 'clf', 'case', 'conj', 'cc', 'fixed', 'flat', 'compound',
    #     'list', 'parataxis', 'orphan', 'goeswith', 'reparandum', 'punct',
    #     'root', 'dep'
    # )
    typerel = models.CharField(max_length=50)#, choices=[(i,i) for i in typerels])
