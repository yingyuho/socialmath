from django.contrib import admin
from prooftree.models import *
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

# Register your models here.
admin.site.register(Node)
admin.site.register(DAG)
admin.site.register(Keyword)
admin.site.register(KWMap)
admin.site.register(Event)
admin.site.register(PGraph)
admin.site.register(PGPermission)
admin.site.register(GNMap)

if len(User.objects.filter(username="socialmathghostuser")) == 0:
	User.objects.create_user("socialmathghostuser", "socialmathghost@socialmath.com", "socialmathghostuser2014")