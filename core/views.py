import re 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, F, Prefetch
# Make sure to import the new EnvelopeMeta model
from .models import Region, Envelope, EnvelopeMeta, Document, AuditLog
from .forms import CustomSignupForm

# --- HELPER: Log Activity ---
def log_activity(user, action, details):
    AuditLog.objects.create(user=user, action=action, details=details)

# --- VIEW: Signup ---
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login') 
    else:
        form = CustomSignupForm()
    return render(request, 'registration/signup.html', {'form': form})

# --- VIEW: Dashboard (Main Logic) ---
@login_required
def dashboard(request):
    # 1. Auto-Populate Regions if empty
    if not Region.objects.exists():
        ph_regions = [
            "NCR", "CAR", "Region I", "Region II", "Region III",
            "Region IV-A", "Region IV-B", "Region V", "Region VI", 
            "Region VII", "Region VIII", "Region IX", "Region X", 
            "Region XI", "Region XII", "Region XIII", "BARMM"
        ]
        for reg_name in ph_regions:
            Region.objects.create(name=reg_name)

    # 2. Fetch Regions (Natural Sort: Region 1, Region 2, Region 10...)
    regions_queryset = Region.objects.all()
    regions = sorted(
        regions_queryset, 
        key=lambda r: [int(t) if t.isdigit() else t.lower() for t in re.split('(\d+)', r.name)]
    )
    
    selected_region_id = request.GET.get('region')
    
    # 3. QUERY OPTIMIZATION
    # We use prefetch_related to load Documents AND the new Meta Details efficiently
    envelopes = Envelope.objects.prefetch_related(
        'documents', 
        'meta_details' 
    ).annotate(
        latest_doc_date=Max('documents__date_notarized')
    ).order_by(F('latest_doc_date').desc(nulls_last=True), '-id')

    if selected_region_id:
        envelopes = envelopes.filter(region_id=selected_region_id)

    # 4. SEARCH LOGIC (Updated for EnvelopeMeta)
    query = request.GET.get('q')
    if query:
        envelopes = envelopes.filter(
            Q(title__icontains=query) | 
            Q(documents__content_context__icontains=query) |
            # Search inside the new child table (EnvelopeMeta)
            Q(meta_details__project_entity__icontains=query) |
            Q(meta_details__procuring_entity__icontains=query) |
            Q(meta_details__sales_name__icontains=query) |
            Q(meta_details__door_number__icontains=query)
        ).distinct()

    # --- HANDLE POST REQUESTS (Add) ---
    if request.method == 'POST':
        
        # A. Add Region
        if 'add_region' in request.POST:
            region_name = request.POST.get('region_name')
            if region_name:
                Region.objects.get_or_create(name=region_name)
                log_activity(request.user, "Added Region", f"Created region: {region_name}")
            return redirect('dashboard')

        # B. Add Envelope (Folder)
        elif 'add_envelope' in request.POST:
            r_id = request.POST.get('region_id')
            title = request.POST.get('title')
            
            if r_id and title:
                region = get_object_or_404(Region, id=r_id)
                envelope = Envelope.objects.create(
                    region=region, 
                    title=title
                )

                # 1. Save Meta Rows (Project, Sales, Door, etc.) - HANDLING LISTS
                p_entities = request.POST.getlist('project_entity[]')
                proc_entities = request.POST.getlist('procuring_entity[]')
                sales_names = request.POST.getlist('sales_name[]')
                door_numbers = request.POST.getlist('door_number[]')

                # Iterate through the list and create rows
                for i in range(len(p_entities)):
                    # Check if the row has any data before saving
                    has_data = (
                        p_entities[i].strip() or 
                        (i < len(proc_entities) and proc_entities[i].strip()) or 
                        (i < len(sales_names) and sales_names[i].strip()) or 
                        (i < len(door_numbers) and door_numbers[i].strip())
                    )
                    
                    if has_data:
                        EnvelopeMeta.objects.create(
                            envelope=envelope,
                            project_entity=p_entities[i],
                            procuring_entity=proc_entities[i] if i < len(proc_entities) else "",
                            sales_name=sales_names[i] if i < len(sales_names) else "",
                            door_number=door_numbers[i] if i < len(door_numbers) else ""
                        )

                # 2. Save Documents
                contexts = request.POST.getlist('context[]')
                pages_list = request.POST.getlist('pages[]')
                dates = request.POST.getlist('date[]')

                for i in range(len(contexts)):
                    if contexts[i]: 
                        raw_date = dates[i]
                        final_date = raw_date if raw_date.strip() != '' else None
                        Document.objects.create(
                            envelope=envelope,
                            content_context=contexts[i],
                            num_pages=int(pages_list[i]) if pages_list[i] else 0,
                            date_notarized=final_date
                        )
                
                log_activity(request.user, "Created Folder", f"Created '{title}' in {region.name}")
            return redirect('dashboard')

    # Calculate total pages for display
    for env in envelopes:
        env.total_pages = sum(doc.num_pages for doc in env.documents.all())

    recent_activity = AuditLog.objects.select_related('user').order_by('-timestamp')[:20]

    context = {
        'regions': regions,
        'envelopes': envelopes,
        'selected_region_id': int(selected_region_id) if selected_region_id else None,
        'user': request.user,
        'recent_activity': recent_activity
    }
    return render(request, 'core/dashboard.html', context)

# --- VIEW: Edit Envelope ---
@login_required
def edit_envelope(request, id):
    if request.method == 'POST':
        envelope = get_object_or_404(Envelope, id=id)
        old_title = envelope.title
        
        # 1. Update Basic Info
        envelope.title = request.POST.get('title')
        envelope.region_id = request.POST.get('region_id')
        envelope.save()
        
        # 2. Update Meta Rows (Project/Sales/Door)
        # Strategy: Delete all existing meta rows for this folder and recreate them.
        # This is the safest way to handle dynamic additions/deletions from the frontend.
        envelope.meta_details.all().delete()
        
        p_entities = request.POST.getlist('project_entity[]')
        proc_entities = request.POST.getlist('procuring_entity[]')
        sales_names = request.POST.getlist('sales_name[]')
        door_numbers = request.POST.getlist('door_number[]')

        for i in range(len(p_entities)):
            has_data = (
                p_entities[i].strip() or 
                (i < len(proc_entities) and proc_entities[i].strip()) or 
                (i < len(sales_names) and sales_names[i].strip()) or 
                (i < len(door_numbers) and door_numbers[i].strip())
            )
            
            if has_data:
                EnvelopeMeta.objects.create(
                    envelope=envelope,
                    project_entity=p_entities[i],
                    procuring_entity=proc_entities[i] if i < len(proc_entities) else "",
                    sales_name=sales_names[i] if i < len(sales_names) else "",
                    door_number=door_numbers[i] if i < len(door_numbers) else ""
                )

        # 3. Update Documents
        # Same Strategy: Delete all documents and recreate. 
        # This prevents ID mismatch errors when re-ordering or adding new rows.
        envelope.documents.all().delete()
        
        contexts = request.POST.getlist('context[]')
        pages = request.POST.getlist('pages[]')
        dates = request.POST.getlist('date[]')
        
        for i in range(len(contexts)):
            if contexts[i]:
                raw_date = dates[i]
                final_date = raw_date if raw_date.strip() != '' else None
                Document.objects.create(
                    envelope=envelope,
                    content_context=contexts[i],
                    num_pages=int(pages[i]) if pages[i] else 0,
                    date_notarized=final_date
                )
        
        log_activity(request.user, "Edited Folder", f"Updated folder: {old_title}")
        return redirect('dashboard')
    return redirect('dashboard')

# --- VIEW: Delete Envelope ---
@login_required
def delete_envelope(request, id):
    envelope = get_object_or_404(Envelope, id=id)
    title = envelope.title
    envelope.delete()
    log_activity(request.user, "Deleted Folder", f"Deleted folder: {title}")
    return redirect('dashboard')

# --- VIEW: Edit Region ---
@login_required
def edit_region(request, id):
    if request.method == 'POST':
        region = get_object_or_404(Region, id=id)
        old_name = region.name
        new_name = request.POST.get('region_name')
        if new_name:
            region.name = new_name
            region.save()
            log_activity(request.user, "Edited Region", f"Renamed {old_name} to {new_name}")
    return redirect('dashboard')

# --- VIEW: Delete Region ---
@login_required
def delete_region(request, id):
    region = get_object_or_404(Region, id=id)
    name = region.name
    region.delete()
    log_activity(request.user, "Deleted Region", f"Deleted region: {name}")
    return redirect('dashboard')