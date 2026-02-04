import re 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, F 
from .models import Region, Envelope, Document, AuditLog
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

@login_required
def dashboard(request):
    # 1. Auto-Populate Regions
    if not Region.objects.exists():
        ph_regions = [
            "NCR - National Capital Region", "CAR - Cordillera Administrative Region",
            "Region I - Ilocos Region", "Region II - Cagayan Valley", "Region III - Central Luzon",
            "Region IV-A - CALABARZON", "Region IV-B - MIMAROPA", "Region V - Bicol Region",
            "Region VI - Western Visayas", "Region VII - Central Visayas", "Region VIII - Eastern Visayas",
            "Region IX - Zamboanga Peninsula", "Region X - Northern Mindanao", "Region XI - Davao Region",
            "Region XII - SOCCSKSARGEN", "Region XIII - Caraga", "BARMM - Bangsamoro Autonomous Region"
        ]
        for reg_name in ph_regions:
            Region.objects.create(name=reg_name)

    # 2. Fetch Regions (Sorted Natural)
    regions_queryset = Region.objects.all()
    regions = sorted(
        regions_queryset, 
        key=lambda r: [int(t) if t.isdigit() else t.lower() for t in re.split('(\d+)', r.name)]
    )
    
    selected_region_id = request.GET.get('region')
    
    # 3. SORTING LOGIC (Newest Date First, Empty Dates Last)
    envelopes = Envelope.objects.annotate(
        latest_doc_date=Max('documents__date_notarized')
    ).prefetch_related('documents')

    # F('latest_doc_date').desc(nulls_last=True) ensures folders with NO date go to the bottom
    envelopes = envelopes.order_by(F('latest_doc_date').desc(nulls_last=True), '-id')

    if selected_region_id:
        envelopes = envelopes.filter(region_id=selected_region_id)

    # Search Logic
    query = request.GET.get('q')
    if query:
        envelopes = envelopes.filter(
            Q(title__icontains=query) | 
            Q(documents__content_context__icontains=query) |
            Q(project_entity__icontains=query) |
            Q(procuring_entity__icontains=query) |
            Q(sales_name__icontains=query)
        ).distinct()

    # --- HANDLE FORMS ---
    if request.method == 'POST':
        
        if 'add_region' in request.POST:
            region_name = request.POST.get('region_name')
            if region_name:
                Region.objects.get_or_create(name=region_name)
                log_activity(request.user, "Added Region", f"Created region: {region_name}")
            return redirect('dashboard')

        elif 'add_envelope' in request.POST:
            r_id = request.POST.get('region_id')
            title = request.POST.get('title')
            p_entity = request.POST.get('project_entity')
            proc_entity = request.POST.get('procuring_entity')
            sales = request.POST.get('sales_name')
            
            contexts = request.POST.getlist('context[]')
            pages_list = request.POST.getlist('pages[]')
            dates = request.POST.getlist('date[]')

            if r_id and title:
                region = get_object_or_404(Region, id=r_id)
                envelope = Envelope.objects.create(
                    region=region, title=title,
                    project_entity=p_entity, procuring_entity=proc_entity, sales_name=sales
                )
                
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

@login_required
def delete_envelope(request, id):
    envelope = get_object_or_404(Envelope, id=id)
    title = envelope.title
    envelope.delete()
    log_activity(request.user, "Deleted Folder", f"Deleted folder: {title}")
    return redirect('dashboard')

@login_required
def edit_envelope(request, id):
    if request.method == 'POST':
        envelope = get_object_or_404(Envelope, id=id)
        old_title = envelope.title
        
        # Update Main Info
        envelope.title = request.POST.get('title')
        envelope.region_id = request.POST.get('region_id')
        envelope.project_entity = request.POST.get('project_entity')
        envelope.procuring_entity = request.POST.get('procuring_entity')
        envelope.sales_name = request.POST.get('sales_name')
        envelope.save()
        
        # Update/Create Documents
        # In HTML, we ensure every row sends a doc_id. 
        # Existing rows send their ID. New rows send "0" or "".
        doc_ids = request.POST.getlist('doc_id[]')
        contexts = request.POST.getlist('context[]')
        pages = request.POST.getlist('pages[]')
        dates = request.POST.getlist('date[]')
        
        # We loop through 'contexts' because that determines how many rows there are
        for i in range(len(contexts)):
            if not contexts[i]: continue # Skip empty rows
            
            current_id = doc_ids[i] if i < len(doc_ids) else None
            
            raw_date = dates[i]
            final_date = raw_date if raw_date.strip() != '' else None
            num_pages = int(pages[i]) if pages[i] else 0

            if current_id and current_id != "0" and current_id != "":
                # Update Existing
                try:
                    doc = Document.objects.get(id=current_id)
                    doc.content_context = contexts[i]
                    doc.num_pages = num_pages
                    doc.date_notarized = final_date
                    doc.save()
                except Document.DoesNotExist:
                    pass
            else:
                # Create New
                Document.objects.create(
                    envelope=envelope,
                    content_context=contexts[i],
                    num_pages=num_pages,
                    date_notarized=final_date
                )
        
        log_activity(request.user, "Edited Folder", f"Updated folder: {old_title}")
        return redirect('dashboard')
    return redirect('dashboard')

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

@login_required
def delete_region(request, id):
    region = get_object_or_404(Region, id=id)
    name = region.name
    region.delete()
    log_activity(request.user, "Deleted Region", f"Deleted region: {name}")
    return redirect('dashboard')