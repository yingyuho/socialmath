from django.db import models
from django.db.models import Avg, Max, Min
import datetime
from django.utils.timezone import utc
from django.contrib.auth.models import User



''' Create the following tables:
CREATE TABLE "prooftree_node" (
    "node_id" integer NOT NULL PRIMARY KEY,
    "kind" varchar(3) NOT NULL,
    "title" varchar(100),
    "statement" text NOT NULL,
    "pub_time" datetime NOT NULL
)
;
CREATE TABLE "prooftree_dag" (
    "id" integer NOT NULL PRIMARY KEY,
    "parent_id" integer NOT NULL REFERENCES "prooftree_node" ("node_id"),
    "child_id" integer NOT NULL REFERENCES "prooftree_node" ("node_id"),
    "dep_type" varchar(5) NOT NULL
)
;
CREATE TABLE "prooftree_keyword" (
    "kw_id" integer NOT NULL PRIMARY KEY,
    "word" varchar(100) NOT NULL
)
;
CREATE TABLE "prooftree_kwmap" (
    "id" integer NOT NULL PRIMARY KEY,
    "node_id" integer NOT NULL REFERENCES "prooftree_node" ("node_id"),
    "kw_id" integer NOT NULL REFERENCES "prooftree_keyword" ("kw_id")
)
;

'''

# Custom manager for DAG relations
class NodeManager(models.Manager):
    # Usage: Node.objects.max_nodes()
    # Return: maximum primary key
    def max_nodes(self):
        if self.all().count() == 0:
            return 1
        return self.max_id() - self.all().aggregate(Min('node_id'))['node_id__min'] + 1

    # Usage: Node.objects.max_nodes()
    # Return: maximum primary key
    def max_id(self):
        if self.all().count() == 0:
            return 1
        return self.all().aggregate(Max('node_id'))['node_id__max']

    # Usage: Node.objects.max_pageno() 
    # Return: maximum page number, assuming we are loading 100
    #         entries per page
    def max_pageno(self):
        return (self.max_nodes() - 1) / 100 + 1;

    def authenticate(self, node, user):
        graph = GNMap.objects.filter(node=node)
        if len(graph) == 0:
            return True
        return PGPermission.objects.authenticate(graph[0].graph, user)


# Custom manager for DAG relations
class DAGManager(models.Manager):
    # Usage: DAG.objects.get_children(node_id)
    # Return: [child_id1, child_id2, ...]
    def get_children(self, node_id):
        return self.filter(parent=node_id).values_list('child_id', flat=True)

    # Usage: DAG.objects.get_parents(node_id)
    # Return: [parent_id1, parent_id2, ...]
    def get_parents(self, node_id):
        return self.filter(child=node_id).values_list('parent_id', flat=True)


# Custom manager for Keyword class
class KWManager(models.Manager):
    # Usage: Keyword.objects.get_related(keyword)
    # Return: List of node_id for theorems tagged with keyword
    def get_related(self, keyword):
        kw = Keyword.objects.filter(word__exact=keyword)
        return KWMap.objects.filter(kw=kw).values_list('node', flat=True)

    # Usage: Keyword.objects.get_keywords(node_id)
    # Return: List of keywords for the theorems
    def get_keywords(self, node_id):
        keywords = list(KWMap.objects.filter(node_id=node_id).values_list('kw', flat=True))
        return keywords

class EVManager(models.Manager):
    def get_userhistory(self, user):
        events = self.filter(user=user)
        return events

    def get_userfollowing(self, user):
        interests = [ev.node for ev in self.filter(user=user).filter(event_type="followed")]
        return interests

# Entity for a node in DAG. 
class Node(models.Model):
    TYPES = (
        ('thm', 'Theorem'),
        ('ax', 'Axiom'),
        ('def', 'Definition'),
        ('pf', 'Proof'),
    )
    node_id = models.AutoField(primary_key=True)
    kind = models.CharField(max_length=3, choices=TYPES)
    title = models.CharField(max_length=100, null=True)
    statement = models.TextField()
    pub_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now_add=False, auto_now=False)
    objects = NodeManager()

    def __str__kind(self):
        return self.title        


# Adjacency list of nodes in the DAG
class DAG(models.Model):
    TYPES = (
        ('prove', 'prove'),
        ('any', 'any'),
        ('all', 'all'),
    )
    parent = models.ForeignKey(Node, related_name="parent_id")
    child = models.ForeignKey(Node, related_name="child_id")
    dep_type = models.CharField(max_length=5, choices=TYPES)
    objects = DAGManager()

# Entity for keywords
class Keyword(models.Model):
    kw_id = models.AutoField(primary_key=True)
    word = models.CharField(max_length=100)
    objects = KWManager() 

# Many to many mapping between nodes and keywords
class KWMap(models.Model):
    node = models.ForeignKey(Node)
    kw = models.ForeignKey(Keyword)


class Event(models.Model):
    TYPES = (
        ('added', 'added'),
        ('modified', 'modified'), 
        ('followed', 'followed'),
    )
    node = models.ForeignKey(Node)
    pub_time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, blank=True, null=True)
    event_type = models.CharField(max_length=8, choices=TYPES)
    objects = EVManager()

# Private Graph classes
class PGManager(models.Manager):
    def get_userpg(self, user):
        pgs = self.filter(owner=user)

class PGPManager(models.Manager):
    def authenticate(self, graph, user):
        if graph.perm_type == "public":
            return True
        return ((graph.owner == user) or (len(self.filter(graph=graph).filter(user=user)) > 0))
    def authorized_users(self, graph):
        if graph.perm_type == "public":
            return "all"
        pu = list(self.filter(graph=graph).values_list('user'))
        return pu
    def authorized_graphs(self, user):
        pg = {}
        pg['authorized'] = list(self.filter(user=user).values_list('graph'))
        pg['owned'] = list(PGraph.objects.filter(owner=user))
        return pg

class GNManager(models.Manager):
    def get_nodes(self, graph=None):
        if graph == None:
            nodes = Node.objects.all().order_by('-pub_time')
            pnodes = self.all().values_list('node_id', flat=True)
            nodes = nodes.exclude(pk__in=pnodes)
            return nodes
        nodes = self.filter(graph=graph).values_list('node_id')
        anodes = Node.objects.all().order_by('-pub_time')
        anodes = anodes.filter(pk__in=nodes)
        return anodes
    def get_graph(self, node):
        graph = list(self.filter(node=node).values_list('graph'))
        if len(graph) == 0:
            return None
        return PGraph.objects.get(pk=graph[0][0])

class PGraph(models.Model):
    TYPES = (
        ('public', 'public'),
        ('protected', 'protected'),
    )
    pgraph_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, null=False)
    description = models.TextField()
    pub_time = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User)
    perm_type = models.CharField(max_length=9, choices=TYPES)
    objects = PGManager()

class PGPermission(models.Model):
    graph = models.ForeignKey(PGraph, null=False)
    user = models.ForeignKey(User, related_name="user")
    objects = PGPManager()

class GNMap(models.Model):
    graph = models.ForeignKey(PGraph, related_name="graph")
    node = models.ForeignKey(Node)
    objects = GNManager()