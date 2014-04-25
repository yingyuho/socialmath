from django.http import HttpResponse
from prooftree.models import *
from prooftree.serializers import *
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser
from django.core.exceptions import *

class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)

def index(request):
    latest_theorem_list = Node.objects.all().order_by('-pub_time')[:10]
    context = {'latest_theorem_list': latest_theorem_list}
    return render(request, 'prooftree/index.html', context)

def pagebrief(request, pageno='1'):
    ''' **HTTP GET**
        /get/brief
        /get/brief?page=n
    '''
    if request.method == 'GET':
        # Check whether page number is valid
        max_pageno = Node.objects.max_pageno()
        pageno = int(pageno)
        if pageno > max_pageno:
            return HttpResponse(status=404)
        # Get serialized data for each node on the page
        node_range = range((pageno - 1) * 100 + 1, pageno * 100 + 1)
        contents = []
        count = 0
        for node_id in node_range:
            try:
                node = Node.objects.get(node_id=node_id)
            except Node.ObjectDoesNotExist:
                continue
            count += 1
            serializer = PageNodeSerializer(node, fields=('node_id', 'kind', 'child_ids'))
            contents.append(PageNodeSerializer(serializer.data))
        # Form responses
        response = {'paging':{'current':pageno,'total':max_pageno,'count':count},
                    'data':contents}
        return JSONResponse(response)


def pagemedium(request, pageno='1'):
    ''' **HTTP GET**
        /get/medium
        /get/medium?page=n
    '''
    if request.method == 'GET':
        # Check whether page number is valid
        max_pageno = Node.objects.max_pageno()
        pageno = int(pageno)
        if pageno > max_pageno:
            return HttpResponse(status=404)
        # Get serialized data for each node on the page
        node_range = range((pageno - 1) * 100 + 1, pageno * 100 + 1)
        contents = []
        count = 0
        for node_id in node_range:
            try:
                node = Node.objects.get(node_id=node_id)
            except Node.ObjectDoesNotExist:
                continue
            count += 1
            serializer = PageNodeSerializer(node)
            contents.append(PageNodeSerializer(serializer.data))
        # Form responses
        response = {'paging':{'current':pageno,'total':max_pageno,'count':count},
                    'data':contents}
        return JSONResponse(response)

def detail(request, node_id):
    ''' **HTTP GET**
        /get/one/<id>
    '''
    # Error handling
    maxid = int(Node.objects.max_id())
    node_id = int(node_id)
    if node_id is None:
        return HttpResponse("Bad Request. An id is required.", status=400)
    if node_id > maxid:
        return HttpResponse("Bad Request. Id not found.", status=404)
    try:
        node = Node.objects.get(node_id=node_id)
    except ObjectDoesNotExist:
        return HttpResponse("Bad Request. Id has been delete.", status=410)

    if request.method == 'GET':
        neighbor_ids = list(DAG.objects.get_children(node_id)) + \
                       list(DAG.objects.get_parents(node_id))
        neighbors = []
        for neighbor_id in neighbor_ids:
            neighbor = Node.objects.get(node_id=neighbor_id)
            serializer = NodeSerializer(neighbor)
            neighbors.append(serializer.data)

        # Form responses
        response = {'wanted': NodeSerializer(node).data, 'neighbors':neighbors}
        return JSONResponse(response)


def add(request, work_type):
    theorem_list = Node.objects.all().order_by('-pub_time')
    context = {'theorem_list': theorem_list}
    context['lemma_range'] = range(9)
    if (int(work_type) == 1):
        return render(request, 'prooftree/add_theorem.html', context)
    elif (int(work_type) == 2):
        return render(request, 'prooftree/add_article.html', context)

def delete_one(request, node_id):
    ''' **HTTP PUT**
       /delete/one/<id>'''
    # Error handling
    maxid = int(Node.objects.max_id())
    node_id = int(node_id)
    if node_id > maxid:
        return HttpResponse("Bad Request. Id not found.", status=404)
    try:
        node = Node.objects.get(node_id=node_id)
    except ObjectDoesNotExist:
        return HttpResponse("Bad Request. Id has been delete.", status=410)
    # TODO: 403 do not have authorization

    if request.method == 'PUT':
        # Delete dependencies from DAG
        DAG.objects.filter(child_id=node_id).delete()
        DAG.objects.filter(parent_id=node_id).delete()
        # Delete keyword mapping
        KWMap.objects.filter(node_id=node_id).delete()
        # Delete node
        node.delete()

def delete_pf(request, node_id, pf_id):
    ''' **HTTP PUT**
       /delete/proof/<id>/<proofid>'''
    # Error handling
    maxid = int(Node.objects.max_id())
    node_id = int(node_id)
    pf_id = int(pf_id)
    if node_id > maxid or pf_id > max_id:
        return HttpResponse("Bad Request. Id not found.", status=404)
    try:
        parent = Node.objects.get(node_id=node_id)
        proof = Node.objects.get(node_id=pf_id)
    except ObjectDoesNotExist:
        return HttpResponse("Bad Request. Id has been delete.", status=410)
    # TODO: 403 do not have authorization

    if request.method == 'PUT':
        # Delete dependencies from DAG
        DAG.objects.filter(parent_id=node_id).filter(child_id=pf_id).delete()
        # Delete keyword mapping
        KWMap.objects.filter(node_id=pf_id).delete()
        # Delete node
        proof.delete()

def delete_all(request):
    ''' **HTTP PUT**
       /delete/all/'''

    if request.method == 'PUT':
        Node.objects.all().delete()
        keyword.objects.all().delete()
        DAG.objects.all().delete()
        KWMap.objects.all().delete()

def change(request, node_id):
    return

def submit_article(request):
    article_title = request.POST['title']
    theorem = get_object_or_404(Node, pk=int(request.POST['theorem']))
    body = request.POST['body']
    newnode = Node(kind='pf', title=article_title, statement=body)
    newnode.save()
    for i in range(9):
        dep = request.POST['lemma' + str(i)]
        if dep != "blank":
            new_dag = DAG(parent=get_object_or_404(Node, pk=int(dep)), child=newnode, type='any')
            new_dag.save()
    return index(request)

def submit_theorem(request):
    theorem_title = request.POST['title']
    body = request.POST['body']
    newnode = Node(kind='thm', title=theorem_title, statement=body)
    newnode.save()
    for i in range(9):
        dep = request.POST['lemma' + str(i)]
        if dep != "blank":
            new_dag = DAG(parent=get_object_or_404(Node, pk=int(dep)), child=newnode, type='any')
            new_dag.save()
    return index(request)
