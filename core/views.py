import re 
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, F
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

# --- AJAX VIEWS ---
@login_required
def add_document_type(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        doc_name = data.get('name')
        if doc_name:
            obj, created = DocumentType.objects.get_or_create(name=doc_name.upper())
            if created:
                log_activity(request.user, "Added Document Type", f"Added: {doc_name}")
            return JsonResponse({'success': True, 'name': obj.name, 'id': obj.id})
    return JsonResponse({'success': False})

@login_required
def delete_document_type(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        doc_id = data.get('id')
        if doc_id:
            try:
                doc = DocumentType.objects.get(id=doc_id)
                name = doc.name
                doc.delete()
                log_activity(request.user, "Deleted Document Type", f"Deleted: {name}")
                return JsonResponse({'success': True})
            except DocumentType.DoesNotExist:
                pass
    return JsonResponse({'success': False})

@login_required
def update_print_status(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        ids = data.get('ids', []) 
        status = data.get('status')
        if ids:
            count = Envelope.objects.filter(id__in=ids).update(is_printed=status)
            verb = "Printed" if status else "Unprinted"
            if len(ids) == 1:
                try:
                    title = Envelope.objects.get(id=ids[0]).title
                    log_activity(request.user, "Print Status", f"Marked '{title}' as {verb}")
                except:
                    log_activity(request.user, "Print Status", f"Marked item as {verb}")
            else:
                log_activity(request.user, "Print Status", f"Marked {count} items as {verb}")
            return JsonResponse({'success': True})
    return JsonResponse({'success': False})

# --- BULK UPDATE DOOR ---
# In views.py

@login_required
def bulk_update_door(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        old_val = data.get('old_door')
        new_val = data.get('new_door')
        
        if new_val is not None:
            # Check for our special empty flag
            if old_val == "__EMPTY__":
                EnvelopeMeta.objects.filter(
                    Q(door_number__isnull=True) | Q(door_number='')
                ).update(door_number=new_val)
            else:
                EnvelopeMeta.objects.filter(door_number=old_val).update(door_number=new_val)
                
            return JsonResponse({'success': True})
            
    return JsonResponse({'success': False})

# --- DASHBOARD (Main View) ---
@login_required
def dashboard(request):
    if not Region.objects.exists():
        ph_regions = ["NCR", "CAR", "Region I", "Region II", "Region III", "Region IV-A", "Region IV-B", "Region V", "Region VI", "Region VII", "Region VIII", "Region IX", "Region X", "Region XI", "Region XII", "Region XIII", "BARMM"]
        for r in ph_regions: Region.objects.create(name=r)
    
    if not DocumentType.objects.exists():
        DocumentType.objects.create(name="SECRETARY'S CERTIFICATE")
        DocumentType.objects.create(name="OMNIBUS SWORN STATEMENT")

    regions = sorted(Region.objects.all(), key=lambda r: [int(t) if t.isdigit() else t.lower() for t in re.split('(\d+)', r.name)])
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

    # --- NEW: Get Unique Door Numbers for Filter ---
    # We fetch all distinct door numbers to populate the dropdown
    unique_doors = EnvelopeMeta.objects.values_list('door_number', flat=True).distinct().order_by('door_number')

    if request.method == 'POST':
        if 'add_region' in request.POST:
            Region.objects.get_or_create(name=request.POST.get('region_name'))
            return redirect('dashboard')
        
        elif 'add_envelope' in request.POST:
            r_id = request.POST.get('region_id')
            title = request.POST.get('title')
            
            if r_id and title:
                region = get_object_or_404(Region, id=r_id)
                env = Envelope.objects.create(region=region, title=title)

                p_entities = request.POST.getlist('project_entity[]')
                proc_entities = request.POST.getlist('procuring_entity[]')
                sales = request.POST.getlist('sales_name[]')
                doors = request.POST.getlist('door_number[]')

                for i in range(len(p_entities)):
                    if p_entities[i] or (i < len(sales) and sales[i]): 
                        EnvelopeMeta.objects.create(
                            envelope=env, 
                            project_entity=p_entities[i], 
                            procuring_entity=proc_entities[i] if i < len(proc_entities) else "",
                            sales_name=sales[i] if i < len(sales) else "",
                            door_number=doors[i] if i < len(doors) else ""
                        )

                contexts = request.POST.getlist('context[]')
                pages = request.POST.getlist('pages[]')
                dates = request.POST.getlist('date[]')

                for i in range(len(contexts)):
                    if contexts[i]:
                        raw_date = dates[i]
                        final_date = None
                        if raw_date and raw_date.strip():
                            try:
                                if len(raw_date) == 10 and raw_date.count('-') == 2:
                                    final_date = raw_date
                            except:
                                final_date = None

                        Document.objects.create(
                            envelope=env, 
                            content_context=contexts[i], 
                            num_pages=int(pages[i]) if pages[i] and pages[i].isdigit() else 0, 
                            date_notarized=final_date
                        )
                
                log_activity(request.user, "Created Folder", f"Created '{title}'")
            return redirect('dashboard')

    for env in envelopes:
        env.total_pages = sum(d.num_pages for d in env.documents.all())

    recent_activity = AuditLog.objects.select_related('user').order_by('-timestamp')[:20]

    return render(request, 'core/dashboard.html', {
        'regions': regions, 
        'envelopes': envelopes, 
        'doc_types': doc_types,
        'unique_doors': unique_doors, # Passed to template
        'selected_region_id': int(selected_region_id) if selected_region_id else None,
        'user': request.user, 
        'recent_activity': recent_activity
    })

# --- VIEW: Edit Envelope ---
@login_required
def edit_envelope(request, id):
    if request.method == 'POST':
        env = get_object_or_404(Envelope, id=id)
        old_title = env.title
        env.title = request.POST.get('title')
        env.region_id = request.POST.get('region_id')
        env.save()

        env.meta_details.all().delete()
        p_entities = request.POST.getlist('project_entity[]')
        proc_entities = request.POST.getlist('procuring_entity[]')
        sales = request.POST.getlist('sales_name[]')
        doors = request.POST.getlist('door_number[]')

        for i in range(len(p_entities)):
            if p_entities[i] or (i < len(sales) and sales[i]):
                EnvelopeMeta.objects.create(
                    envelope=env, 
                    project_entity=p_entities[i], 
                    procuring_entity=proc_entities[i] if i < len(proc_entities) else "",
                    sales_name=sales[i] if i < len(sales) else "",
                    door_number=doors[i] if i < len(doors) else ""
                )

        env.documents.all().delete()
        contexts = request.POST.getlist('context[]')
        pages = request.POST.getlist('pages[]')
        dates = request.POST.getlist('date[]')

        for i in range(len(contexts)):
            if contexts[i]:
                raw_date = dates[i]
                final_date = None
                if raw_date and raw_date.strip():
                    try:
                        if len(raw_date) == 10 and raw_date.count('-') == 2:
                            final_date = raw_date
                    except:
                        final_date = None

                Document.objects.create(
                    envelope=env, 
                    content_context=contexts[i], 
                    num_pages=int(pages[i]) if pages[i] and pages[i].isdigit() else 0, 
                    date_notarized=final_date
                )
        
        log_activity(request.user, "Edited Folder", f"Updated '{old_title}'")
    return redirect('dashboard')

@login_required
def delete_envelope(request, id):
    env = get_object_or_404(Envelope, id=id)
    title = env.title
    env.delete()
    log_activity(request.user, "Deleted Folder", f"Deleted '{title}'")
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
    r = get_object_or_404(Region, id=id)
    name = r.name
    r.delete()
    log_activity(request.user, "Deleted Region", f"Deleted region: {name}")
    return redirect('dashboard')