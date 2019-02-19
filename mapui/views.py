import os, shutil

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.db.models import Sum
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from tiler.models.Document import Document, TiledDocument
from tiler.views import convert_html
from .forms import QueryForm
import pandas as pd
import json
import pdb

max_usage = 25000
query_output = ""
query_df = None

def index(request):
    return HttpResponse("Hello, world. You're at the map ui index.")

def leaflet(request):
    """

    Responds to requests to the csv viewer. Renders html for the csv viewer.

    Args:
        request (HTTPRequest): a http request object

    Returns:
        HTTPResponse containing html for the leaflet JS based csv viewer 

    """
    
    file_name = request.GET.get("file")

    rows, columns = check_csv(file_name)

    output_name = file_name[:-4] + ".html"
    form = QueryForm(initial={'file_name':file_name})
    context = {'form': form, 'file': file_name, 'rows': str(rows), 'columns': str(columns)}
    return render(request, 'leaflet_map.html', context)

def query_handle(request):
    if request.method == 'POST':
        form = QueryForm(request.POST)
        if form.is_valid():
            query_type = form.cleaned_data['query_type']
            query = form.cleaned_data['query']
            file_name = form.cleaned_data['file_name']
            if query_type[0] == 'Pandas':
                pandas_handler(file_name, query)
                pdb.set_trace()
                return redirect('leaflet?file=' + file_name[0:-4] + 'query.csv')
    else:
        return None

def pandas_handler(file_name, query):
    global query_output
    global query_df
    query_df = pd.read_csv(os.path.join(settings.MEDIA_ROOT, "documents", file_name))
    dotIndex = query.find('.')
    if dotIndex == -1:
        query_output = query_df
    else:
        init_query = query[dotIndex+1:len(query)]
        command = "query_output = query_df." + init_query
        exec(command, globals())
    if isinstance(query_output, pd.DataFrame):
        file_name = file_name[0:-4] + 'query.csv'
        csv_path = os.path.join(settings.MEDIA_ROOT, 'documents', file_name)
        query_output.to_csv(csv_path, index=False)
        csv_file = open(csv_path)
        newDoc = Document(file_name=file_name, rows=0, columns=0)
        newDoc.docfile.name = csv_path
        newDoc.save()

def tilecount(request):
    """

    Utility function used by the front end slider defined in 'leaflet_map.html'. Returns the number of
    rows of tiles available for the current csv. This value is returned to the client.

    Args:
        request (HTTPRequest): a http request object

    Returns:
        Json response containing the number of tiles available for the current csv

    """
    file_name = request.GET.get("file")
    tilecount = TiledDocument.objects.filter(document__file_name=file_name).aggregate(Sum('tile_count_on_y'))['tile_count_on_y__sum']
    return JsonResponse({'tilecount': tilecount})

@method_decorator(csrf_exempt)
def delete(request):
    """

    Response function for a post request to delete a csv file. The csrf_exempt decorator is required in
    order for a post requested generated without a form to work correctly.

    Args:
        request (HTTPRequest): a http request object

    Returns:
        Success message

    """
    file_name = request.POST.get("file_name")
    Document.objects.get(file_name=file_name).delete()

    dir_name = file_name[0:-4]
    shutil.rmtree(os.path.join(settings.MEDIA_ROOT, 'tiles', dir_name))
    return HttpResponse("Success")

def check_csv(file_name):
    """

    Check if subtable images for requested csv are present on disk, else create them.

    Args:
        filename (str): Name of the csv file

    Returns:
        The number of rows and number of columns in the csv file

    """
    doc = Document.objects.get(file_name=file_name)
    rows, columns = 0, 0
    if not os.path.isdir(os.path.join(settings.MEDIA_ROOT, 'tiles', file_name[:-4])):
        #check_disk_usage()
        rows, columns = convert_html(doc, file_name)
        doc.rows = rows
        doc.columns = columns
    else:
        rows = doc.rows
        columns = doc.columns
    doc.save()
    return rows, columns

def check_disk_usage():
    """

    Check if disk usage exceeds the maximum allowed. If yes, delete subtable images of csv
    files in least recently used order until disk usage is below the maximum.

    """
    csv_sizes = {}
    total_size = 0
    for dir_name in os.listdir(os.path.join(settings.MEDIA_ROOT, 'tiles')):
        size = get_directory_size(os.path.join(settings.MEDIA_ROOT, 'tiles', dir_name))
        total_size = size + total_size
        csv_sizes[dir_name] = size

    if total_size < max_usage:
        return
    accesses = {}

    for csv_name in csv_sizes:
        doc = Document.objects.get(file_name=csv_name+'.csv')
        accesses[doc.last_access] = csv_name

    while total_size > max_usage:
        oldest = accesses.pop(min(accesses.keys()))
        shutil.rmtree(os.path.join(settings.MEDIA_ROOT, 'tiles', oldest))
        total_size = total_size - csv_sizes.pop(oldest)

def get_directory_size(dir_path):
    """

    Utility function to get the size of a directory

    Args:
        dir_path (str): Path to the directory

    Returns:
        Size of directory in MB

    """
    total_size = 0
    for path, dirs, files in os.walk(dir_path):
        for f in files:
            fp = os.path.join(path, f)
            total_size = total_size + os.path.getsize(fp)

    return total_size / (1024 * 1024)
