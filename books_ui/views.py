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

    # Construir active_chips para UI
    active_chips = []
    
    if grupo_id:
        name = next((c['name'] for c in categories if str(c['id']) == str(grupo_id)), grupo_id)
        active_chips.append({'key': 'grupo_id', 'label': 'Grupo', 'value': name})
    
    if categoria_id:
        name = next((c['name'] for c in categories if str(c['id']) == str(categoria_id)), categoria_id)
        active_chips.append({'key': 'categoria_id', 'label': 'Categoria', 'value': name})
        
    if subcategoria_id:
        name = next((c['name'] for c in categories if str(c['id']) == str(subcategoria_id)), subcategoria_id)
        active_chips.append({'key': 'subcategoria_id', 'label': 'Subcategoria', 'value': name})
        
    if active_filters.get('tag_id'):
        name = next((t['name'] for t in tags if str(t['id']) == str(active_filters['tag_id'])), active_filters['tag_id'])
        active_chips.append({'key': 'tag_id', 'label': 'Tag', 'value': name})

    if active_filters.get('status_id'):
        name = next((s['name'] for s in statuses if str(s['id']) == str(active_filters['status_id'])), active_filters['status_id'])
        active_chips.append({'key': 'status_id', 'label': 'Status', 'value': name})

    if active_filters.get('author_country'):
        active_chips.append({'key': 'author_country', 'label': 'País do Autor', 'value': active_filters['author_country']})
        
    if active_filters.get('author_gender'):
        g = active_filters['author_gender']
        label = "Feminino" if g == 'F' else ("Masculino" if g == 'M' else "Outros")
        active_chips.append({'key': 'author_gender', 'label': 'Gênero do Autor', 'value': label})

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
        'active_chips': active_chips,
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
        
    # Buscar opções para os formulários de edição
    options = {}
    headers = get_headers(request)
    try:
        options['categories'] = httpx.get(f"{API_URL}/categories", headers=headers).json().get('data', [])
        options['authors'] = httpx.get(f"{API_URL}/authors", headers=headers).json().get('data', [])
        options['formats'] = httpx.get(f"{API_URL}/formats", headers=headers).json().get('data', [])
        options['publishers'] = httpx.get(f"{API_URL}/publishers", headers=headers).json().get('data', [])
        options['collections'] = httpx.get(f"{API_URL}/collections", headers=headers).json().get('data', [])
        options['statuses'] = httpx.get(f"{API_URL}/reading_status", headers=headers).json().get('data', [])
        options['tags'] = httpx.get(f"{API_URL}/tags", headers=headers).json().get('data', [])
    except Exception:
        pass
        
    return render(request, 'books/detail.html', {'book': book, 'options': options})

def edit_book_view(request, book_id):
    if request.method == 'POST':
        headers = get_headers(request)
        data = {}
        # Mapeamento dos campos permitidos
        fields = ['title', 'original_publication_year', 'total_pages', 'author_id', 'category_id', 'format_id', 'publisher_id', 'collection_id', 'cover_url']
        for field in fields:
            val = request.POST.get(field)
            if val:
                if field in ['original_publication_year', 'total_pages', 'author_id', 'category_id', 'format_id', 'publisher_id', 'collection_id']:
                    data[field] = int(val)
                else:
                    data[field] = val
                    
        try:
            resp = httpx.put(f"{API_URL}/books/{book_id}", json=data, headers=headers)
            if resp.status_code == 200:
                messages.success(request, "Livro atualizado com sucesso!")
            else:
                messages.error(request, "Erro ao atualizar livro.")
        except Exception:
            messages.error(request, "Erro de comunicação com servidor.")
            
    return redirect('book_detail', book_id=book_id)

def edit_reading_view(request, book_id):
    if request.method == 'POST':
        headers = get_headers(request)
        data = {}
        fields = ['status_id', 'pages_read', 'personal_goal', 'club_name', 'start_date', 'club_date']
        for field in fields:
            val = request.POST.get(field)
            if val:
                if field in ['status_id', 'pages_read']:
                    data[field] = int(val)
                else:
                    data[field] = val
                    
        # Múltiplas tags
        tag_ids = request.POST.getlist('tag_ids')
        if tag_ids:
            data['tag_ids'] = [int(tid) for tid in tag_ids]
            
        try:
            resp = httpx.put(f"{API_URL}/readings/{book_id}", json=data, headers=headers)
            
            if resp.status_code == 404:
                # Se a leitura não existir (404), vamos criá-la
                create_data = data.copy()
                create_data['book_id'] = book_id
                
                # ReadingCreate não possui tag_ids, precisamos remover para o POST
                if 'tag_ids' in create_data:
                    del create_data['tag_ids']
                    
                post_resp = httpx.post(f"{API_URL}/readings", json=create_data, headers=headers)
                
                if post_resp.status_code in [200, 201]:
                    if tag_ids:
                        # Se criou com sucesso, fazemos um PUT apenas para setar as tags
                        httpx.put(f"{API_URL}/readings/{book_id}", json={'tag_ids': data['tag_ids']}, headers=headers)
                    messages.success(request, "Leitura criada e atualizada com sucesso!")
                else:
                    messages.error(request, f"Erro ao criar leitura: {post_resp.text}")
                    
            elif resp.status_code == 200:
                messages.success(request, "Leitura atualizada com sucesso!")
            else:
                messages.error(request, f"Erro ao atualizar leitura: {resp.text}")
        except Exception as e:
            messages.error(request, f"Erro de comunicação com servidor: {e}")
            
    return redirect('book_detail', book_id=book_id)
