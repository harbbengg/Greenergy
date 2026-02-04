import re 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Region, Envelope, Document
from .forms import CustomSignupForm

# --- Signup View ---
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login') 
    else:
        form = CustomSignupForm()
    return render(request, 'registration/signup.html', {'form': form})

# --- Main Dashboard ---
@login_required
def dashboard(request):
    # --- 1. AUTO-POPULATE PHILIPPINE REGIONS (If Database is Empty) ---
    if not Region.objects.exists():
        ph_regions = [
            "NCR - National Capital Region",
            "CAR - Cordillera Administrative Region",
            "Region I - Ilocos Region",
            "Region II - Cagayan Valley",
            "Region III - Central Luzon",
            "Region IV-A - CALABARZON",
            "Region IV-B - MIMAROPA",
            "Region V - Bicol Region",
            "Region VI - Western Visayas",
            "Region VII - Central Visayas",
            "Region VIII - Eastern Visayas",
            "Region IX - Zamboanga Peninsula",
            "Region X - Northern Mindanao",
            "Region XI - Davao Region",
            "Region XII - SOCCSKSARGEN",
            "Region XIII - Caraga",
            "BARMM - Bangsamoro Autonomous Region"
        ]
        for reg_name in ph_regions:
            Region.objects.create(name=reg_name)

    # --- 2. Fetch Regions (Naturally Sorted) ---
    regions_queryset = Region.objects.all()
    regions = sorted(
        regions_queryset, 
        key=lambda r: [int(t) if t.isdigit() else t.lower() for t in re.split('(\d+)', r.name)]
    )
    
    selected_region_id = request.GET.get('region')
    
    # Fetch Envelopes
    envelopes = Envelope.objects.all().prefetch_related('documents')

    # Filter by Region
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
        
        # Add Region (Manual)
        if 'add_region' in request.POST:
            region_name = request.POST.get('region_name')
            if region_name:
                Region.objects.get_or_create(name=region_name)
            return redirect('dashboard')

        # Add Envelope
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
                    region=region, 
                    title=title,
                    project_entity=p_entity,
                    procuring_entity=proc_entity,
                    sales_name=sales
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
            return redirect('dashboard')

    for env in envelopes:
        env.total_pages = sum(doc.num_pages for doc in env.documents.all())

    context = {
        'regions': regions,
        'envelopes': envelopes,
        'selected_region_id': int(selected_region_id) if selected_region_id else None,
        'user': request.user
    }
    return render(request, 'core/dashboard.html', context)

# --- Envelope Actions ---
@login_required
def delete_envelope(request, id):
    envelope = get_object_or_404(Envelope, id=id)
    envelope.delete()
    return redirect('dashboard')

@login_required
def edit_envelope(request, id):
    if request.method == 'POST':
        envelope = get_object_or_404(Envelope, id=id)
        envelope.title = request.POST.get('title')
        envelope.region_id = request.POST.get('region_id')
        envelope.project_entity = request.POST.get('project_entity')
        envelope.procuring_entity = request.POST.get('procuring_entity')
        envelope.sales_name = request.POST.get('sales_name')
        envelope.save()
        
        doc_ids = request.POST.getlist('doc_id[]')
        contexts = request.POST.getlist('context[]')
        pages = request.POST.getlist('pages[]')
        dates = request.POST.getlist('date[]')
        
        for i, doc_id in enumerate(doc_ids):
            if i < len(contexts):
                doc = Document.objects.get(id=doc_id)
                doc.content_context = contexts[i]
                doc.num_pages = int(pages[i]) if pages[i] else 0
                raw_date = dates[i]
                doc.date_notarized = raw_date if raw_date.strip() != '' else None
                doc.save()
        return redirect('dashboard')
    return redirect('dashboard')

# --- Region Actions ---
@login_required
def edit_region(request, id):
    if request.method == 'POST':
        region = get_object_or_404(Region, id=id)
        new_name = request.POST.get('region_name')
        if new_name:
            region.name = new_name
            region.save()
    return redirect('dashboard')

@login_required
def delete_region(request, id):
    region = get_object_or_404(Region, id=id)
    region.delete()
    return redirect('dashboard')