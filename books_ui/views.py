import httpx
import json
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden

API_URL = settings.API_BASE_URL

def get_headers(request):
    token = request.session.get('access_token')
    if token:
        return {'Authorization': f'Bearer {token}'}
    return {}

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            # FastAPI OAuth2PasswordRequestForm expects form data
            data = {'username': username, 'password': password}
            response = httpx.post(f"{API_URL}/auth/token", data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                request.session['access_token'] = token_data.get('access_token')
                return redirect('library')
            else:
                error = "E-mail ou senha incorretos."
                return render(request, 'auth/login.html', {'error': error})
        except httpx.RequestError:
            error = "Erro ao conectar com a API do backend."
            return render(request, 'auth/login.html', {'error': error})
            
    return render(request, 'auth/login.html')

def logout_view(request):
    request.session.flush()
    return redirect('login')

def library_view(request):
    token = request.session.get('access_token')
    if not token:
        return redirect('login')

    headers = get_headers(request)

    # Buscar dados para os dropdowns de filtro
    categories = []
    tags = []
    statuses = []
    try:
        cat_resp = httpx.get(f"{API_URL}/categories", headers=headers)
        if cat_resp.status_code == 200:
            categories = cat_resp.json().get('data', [])

        tag_resp = httpx.get(f"{API_URL}/tags", headers=headers)
        if tag_resp.status_code == 200:
            tags = tag_resp.json().get('data', [])

        status_resp = httpx.get(f"{API_URL}/reading_status", headers=headers)
        if status_resp.status_code == 200:
            statuses = status_resp.json().get('data', [])

        country_resp = httpx.get(f"{API_URL}/authors/countries", headers=headers)
        if country_resp.status_code == 200:
            countries = country_resp.json().get('data', [])
        else:
            countries = []
    except httpx.RequestError:
        countries = []
        pass

    # Montar árvore de categorias para o dropdown hierárquico
    category_tree = []
    grupos = [c for c in categories if c.get('parent_id') is None]
    for grupo in sorted(grupos, key=lambda x: x['name']):
        group_entry = {'grupo': grupo, 'categorias': []}
        categorias = [c for c in categories if c.get('parent_id') == grupo['id']]
        for categoria in sorted(categorias, key=lambda x: x['name']):
            categoria_entry = {'categoria': categoria, 'subcategorias': []}
            subcategorias = [c for c in categories if c.get('parent_id') == categoria['id']]
            categoria_entry['subcategorias'] = sorted(subcategorias, key=lambda x: x['name'])
            group_entry['categorias'].append(categoria_entry)
        category_tree.append(group_entry)

    # Construir query params a partir dos filtros selecionados
    params = {}
    for key in ('tag_id', 'status_id', 'author_country', 'author_gender'):
        value = request.GET.get(key)
        if value:
            params[key] = value

    grupo_id = request.GET.get('grupo_id')
    categoria_id = request.GET.get('categoria_id')
    subcategoria_id = request.GET.get('subcategoria_id')
    
    if subcategoria_id:
        params['category_id'] = subcategoria_id
    elif categoria_id:
        params['category_id'] = categoria_id
    elif grupo_id:
        params['category_id'] = grupo_id
    
    active_filters = params.copy()
    if grupo_id: active_filters['grupo_id'] = grupo_id
    if categoria_id: active_filters['categoria_id'] = categoria_id
    if subcategoria_id: active_filters['subcategoria_id'] = subcategoria_id

    try:
        response = httpx.get(f"{API_URL}/books", headers=headers, params=params)
        if response.status_code == 401:
            request.session.flush()
            return redirect('login')
        books = response.json().get('data', []) if response.status_code == 200 else []
    except httpx.RequestError:
        books = []
        messages.error(request, "Erro de conexão com o servidor.")

    return render(request, 'books/library.html', {
        'books': books,
        'category_tree': category_tree,
        'category_tree_json': json.dumps(category_tree),
        'tags': tags,
        'statuses': statuses,
        'countries': countries,
        'active_filters': active_filters,
    })

def book_detail_view(request, book_id):
    token = request.session.get('access_token')
    if not token:
        return redirect('login')
        
    try:
        response = httpx.get(f"{API_URL}/books/{book_id}", headers=get_headers(request))
        if response.status_code == 401:
            request.session.flush()
            return redirect('login')
            
        data_list = response.json().get('data', []) if response.status_code == 200 else []
        book = data_list[0] if data_list else None
    except httpx.RequestError:
        book = None
        
    if not book:
        return render(request, 'components/empty_state.html') # fallback
        
    return render(request, 'books/detail.html', {'book': book})
