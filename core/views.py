import re 
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, F, Prefetch
from django.http import JsonResponse
from .models import Region, Envelope, EnvelopeMeta, Document, AuditLog, DocumentType
from .forms import CustomSignupForm

def log_activity(user, action, details):
    AuditLog.objects.create(user=user, action=action, details=details)

def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login') 
    else:
        form = CustomSignupForm()
    return render(request, 'registration/signup.html', {'form': form})

# --- AJAX VIEW: Add New Document Type ---
@login_required
def add_document_type(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        doc_name = data.get('name')
        if doc_name:
            obj, created = DocumentType.objects.get_or_create(name=doc_name.upper())
            if created:
                log_activity(request.user, "Added Document Type", f"Added new doc type: {doc_name}")
            return JsonResponse({'success': True, 'name': obj.name, 'id': obj.id})
    return JsonResponse({'success': False})

@login_required
def dashboard(request):
    # 1. Auto-Populate Regions
    if not Region.objects.exists():
        ph_regions = ["NCR", "CAR", "Region I", "Region II", "Region III", "Region IV-A", "Region IV-B", "Region V", "Region VI", "Region VII", "Region VIII", "Region IX", "Region X", "Region XI", "Region XII", "Region XIII", "BARMM"]
        for reg_name in ph_regions: Region.objects.create(name=reg_name)

    # 2. Auto-Populate Document Types (The 2 defaults)
    if not DocumentType.objects.exists():
        DocumentType.objects.create(name="SECRETARY'S CERTIFICATE")
        DocumentType.objects.create(name="OMNIBUS SWORN STATEMENT")

    regions = sorted(Region.objects.all(), key=lambda r: [int(t) if t.isdigit() else t.lower() for t in re.split('(\d+)', r.name)])
    
    # Fetch all document types for the dropdowns
    doc_types = DocumentType.objects.all().order_by('name')

    selected_region_id = request.GET.get('region')

    envelopes = Envelope.objects.prefetch_related('documents', 'meta_details').annotate(
        latest_doc_date=Max('documents__date_notarized')
    ).order_by(F('latest_doc_date').desc(nulls_last=True), '-id')

    if selected_region_id:
        envelopes = envelopes.filter(region_id=selected_region_id)

    query = request.GET.get('q')
    if query:
        envelopes = envelopes.filter(
            Q(title__icontains=query) | 
            Q(documents__content_context__icontains=query) |
            Q(meta_details__project_entity__icontains=query) |
            Q(meta_details__procuring_entity__icontains=query) |
            Q(meta_details__sales_name__icontains=query) |
            Q(meta_details__door_number__icontains=query)
        ).distinct()

    if request.method == 'POST':
        if 'add_region' in request.POST:
            Region.objects.get_or_create(name=request.POST.get('region_name'))
            return redirect('dashboard')

        elif 'add_envelope' in request.POST:
            region = get_object_or_404(Region, id=request.POST.get('region_id'))
            env = Envelope.objects.create(region=region, title=request.POST.get('title'))

            p_entities = request.POST.getlist('project_entity[]')
            proc_entities = request.POST.getlist('procuring_entity[]')
            sales = request.POST.getlist('sales_name[]')
            doors = request.POST.getlist('door_number[]')

            for i in range(len(p_entities)):
                if p_entities[i] or sales[i] or doors[i] or proc_entities[i]: 
                    EnvelopeMeta.objects.create(
                        envelope=env,
                        project_entity=p_entities[i],
                        procuring_entity=proc_entities[i],
                        sales_name=sales[i],
                        door_number=doors[i]
                    )

            contexts = request.POST.getlist('context[]')
            pages = request.POST.getlist('pages[]')
            dates = request.POST.getlist('date[]')

            for i in range(len(contexts)):
                if contexts[i]:
                    Document.objects.create(
                        envelope=env,
                        content_context=contexts[i],
                        num_pages=int(pages[i]) if pages[i] else 0,
                        date_notarized=dates[i] if dates[i] else None
                    )
            
            log_activity(request.user, "Created Folder", f"Created {env.title}")
            return redirect('dashboard')

    for env in envelopes:
        env.total_pages = sum(doc.num_pages for doc in env.documents.all())

    return render(request, 'core/dashboard.html', {
        'regions': regions, 
        'envelopes': envelopes, 
        'doc_types': doc_types, # Passed to template
        'selected_region_id': int(selected_region_id) if selected_region_id else None,
        'user': request.user, 
        'recent_activity': AuditLog.objects.select_related('user').order_by('-timestamp')[:20]
    })

@login_required
def edit_envelope(request, id):
    if request.method == 'POST':
        env = get_object_or_404(Envelope, id=id)
        env.title = request.POST.get('title')
        env.region_id = request.POST.get('region_id')
        env.save()

        env.meta_details.all().delete()
        p_entities = request.POST.getlist('project_entity[]')
        proc_entities = request.POST.getlist('procuring_entity[]')
        sales = request.POST.getlist('sales_name[]')
        doors = request.POST.getlist('door_number[]')

        for i in range(len(p_entities)):
            if p_entities[i] or sales[i] or doors[i] or proc_entities[i]:
                EnvelopeMeta.objects.create(
                    envelope=env,
                    project_entity=p_entities[i],
                    procuring_entity=proc_entities[i],
                    sales_name=sales[i],
                    door_number=doors[i]
                )

        env.documents.all().delete()
        contexts = request.POST.getlist('context[]')
        pages = request.POST.getlist('pages[]')
        dates = request.POST.getlist('date[]')

        for i in range(len(contexts)):
            if contexts[i]:
                Document.objects.create(
                    envelope=env,
                    content_context=contexts[i],
                    num_pages=int(pages[i]) if pages[i] else 0,
                    date_notarized=dates[i] if dates[i] else None
                )
        
        log_activity(request.user, "Edited Folder", f"Updated {env.title}")
    return redirect('dashboard')

@login_required
def delete_envelope(request, id):
    get_object_or_404(Envelope, id=id).delete()
    return redirect('dashboard')

@login_required
def edit_region(request, id):
    if request.method == 'POST':
        r = get_object_or_404(Region, id=id)
        r.name = request.POST.get('region_name')
        r.save()
    return redirect('dashboard')

@login_required
def delete_region(request, id):
    get_object_or_404(Region, id=id).delete()
    return redirect('dashboard')