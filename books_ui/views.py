import httpx
import json
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST

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
    formats = []
    shelves = []
    try:
        cat_resp = httpx.get(f"{API_URL}/categories", headers=headers)
        if cat_resp.status_code == 200:
            categories = cat_resp.json().get('data', [])

        tag_resp = httpx.get(f"{API_URL}/tags", headers=headers)
        if tag_resp.status_code == 200:
            tags = sorted(tag_resp.json().get('data', []), key=lambda x: x['name'])

        status_resp = httpx.get(f"{API_URL}/reading_status", headers=headers)
        if status_resp.status_code == 200:
            statuses = sorted(status_resp.json().get('data', []), key=lambda x: x['name'])

        format_resp = httpx.get(f"{API_URL}/formats", headers=headers)
        if format_resp.status_code == 200:
            formats = sorted(format_resp.json().get('data', []), key=lambda x: x['name'])

        shelve_resp = httpx.get(f"{API_URL}/shelves", headers=headers)
        if shelve_resp.status_code == 200:
            shelves = sorted(shelve_resp.json().get('data', []), key=lambda x: x['name'])

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
    for key in ('tag_id', 'status_id', 'author_country', 'author_gender', 'q', 'format_id', 'shelve_id'):
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

    if active_filters.get('format_id'):
        name = next((f['name'] for f in formats if str(f['id']) == str(active_filters['format_id'])), active_filters['format_id'])
        active_chips.append({'key': 'format_id', 'label': 'Formato', 'value': name})

    if active_filters.get('shelve_id'):
        name = next((s['name'] for s in shelves if str(s['id']) == str(active_filters['shelve_id'])), active_filters['shelve_id'])
        active_chips.append({'key': 'shelve_id', 'label': 'Estante', 'value': name})

    if active_filters.get('author_country'):
        active_chips.append({'key': 'author_country', 'label': 'País do Autor', 'value': active_filters['author_country']})
        
    if active_filters.get('author_gender'):
        g = active_filters['author_gender']
        label = "Feminino" if g == 'F' else ("Masculino" if g == 'M' else "Outros")
        active_chips.append({'key': 'author_gender', 'label': 'Gênero do Autor', 'value': label})

    if active_filters.get('q'):
        active_chips.append({'key': 'q', 'label': 'Busca', 'value': active_filters['q']})

    try:
        response = httpx.get(f"{API_URL}/books", headers=headers, params=params)
        if response.status_code == 401:
            request.session.flush()
            return redirect('login')
        books = response.json().get('data', []) if response.status_code == 200 else []
    except httpx.RequestError:
        books = []
        messages.error(request, "Erro de conexão com o servidor.")

    options = {}
    try:
        options['categories'] = categories
        options['authors'] = httpx.get(f"{API_URL}/authors", headers=headers).json().get('data', [])
        options['formats'] = httpx.get(f"{API_URL}/formats", headers=headers).json().get('data', [])
        options['publishers'] = httpx.get(f"{API_URL}/publishers", headers=headers).json().get('data', [])
        options['collections'] = httpx.get(f"{API_URL}/collections", headers=headers).json().get('data', [])
    except Exception:
        pass

    reading_now = None
    try:
        lendo_id = next((s['id'] for s in statuses if s['name'].lower() == 'lendo'), None)
        if lendo_id:
            resp = httpx.get(f"{API_URL}/books?status_id={lendo_id}", headers=headers)
            if resp.status_code == 200:
                lendo_books = resp.json().get('data', [])
                if lendo_books:
                    book_stub = lendo_books[0]
                    
                    # O endpoint de listagem não devolve readings, busca os dados completos via detalhe
                    detail_resp = httpx.get(f"{API_URL}/books/{book_stub['id']}", headers=headers)
                    if detail_resp.status_code == 200:
                        detail_data = detail_resp.json().get('data', [])
                        reading_now = detail_data[0] if detail_data else book_stub
                    else:
                        reading_now = book_stub

                    if reading_now.get('readings'):
                        # Busca especificamente o registro com status "Lendo"
                        lendo_reading = None
                        for r in reading_now['readings']:
                            if r.get('status') and r['status'].get('name', '').lower() == 'lendo':
                                lendo_reading = r
                                break

                        if not lendo_reading:
                            lendo_reading = reading_now['readings'][0]

                        pages_read = lendo_reading.get('pages_read') or 0
                        total_pages = reading_now.get('total_pages') or 0

                        percentage = 0
                        if total_pages > 0:
                            percentage = int((pages_read / total_pages) * 100)
                            if percentage > 100: percentage = 100

                        reading_now['read_percentage'] = percentage
                        reading_now['pages_read'] = pages_read

                    quotes_resp = httpx.get(f"{API_URL}/quotes?book_id={reading_now['id']}", headers=headers)
                    if quotes_resp.status_code == 200:
                        quotes = quotes_resp.json().get('data', [])
                        if quotes:
                            reading_now['last_quote'] = quotes[-1]['content']
    except Exception:
        pass

    return render(request, 'books/library.html', {
        'books': books,
        'reading_now': reading_now,
        'category_tree': category_tree,
        'category_tree_json': json.dumps(category_tree),
        'tags': tags,
        'statuses': statuses,
        'formats': formats,
        'shelves': shelves,
        'countries': countries,
        'active_filters': active_filters,
        'active_chips': active_chips,
        'options': options,
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
        
    # --- NOVA BUSCA DE COLEÇÃO ---
    collection_books = []
    if book and book.get('collection'):
        try:
            col_id = book['collection']['id']
            col_resp = httpx.get(f"{API_URL}/books?collection_id={col_id}", headers=get_headers(request))
            if col_resp.status_code == 200:
                raw_col_books = col_resp.json().get('data', [])
                collection_books = [b for b in raw_col_books if str(b['id']) != str(book_id)]
                collection_books.sort(key=lambda x: x.get('original_publication_year') or 9999)
        except Exception:
            pass
    # -----------------------------

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
        
    return render(request, 'books/detail.html', {'book': book, 'options': options, 'collection_books': collection_books})

def edit_book_view(request, book_id):
    if request.method == 'POST':
        headers = get_headers(request)
        data = {}
        # Mapeamento dos campos permitidos
        fields = ['title', 'original_publication_year', 'total_pages', 'author_id', 'category_id', 'format_id', 'publisher_id', 'collection_id', 'cover_url', 'synopsis']
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
        fields = ['status_id', 'pages_read', 'personal_goal', 'club_name', 'start_date', 'club_date', 'review', 'rating']
        for field in fields:
            val = request.POST.get(field)
            if val:
                if field in ['status_id', 'pages_read', 'rating']:
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

def create_book_view(request):
    if request.method == 'POST':
        headers = get_headers(request)
        data = {}
        fields = ['title', 'original_publication_year', 'total_pages', 'author_id', 'category_id', 'format_id', 'publisher_id', 'collection_id', 'cover_url', 'synopsis']
        for field in fields:
            val = request.POST.get(field)
            if val:
                if field in ['original_publication_year', 'total_pages', 'author_id', 'category_id', 'format_id', 'publisher_id', 'collection_id']:
                    data[field] = int(val)
                else:
                    data[field] = val
                    
        try:
            resp = httpx.post(f"{API_URL}/books", json=data, headers=headers)
            if resp.status_code in [200, 201]:
                messages.success(request, "Livro adicionado com sucesso!")
            elif resp.status_code == 403:
                messages.error(request, "Você não tem permissão para criar livros.")
            else:
                messages.error(request, f"Erro ao criar livro: {resp.text}")
        except Exception:
            messages.error(request, "Erro de comunicação com o servidor.")
            
    return redirect('library')

def delete_book_view(request, book_id):
    if request.method == 'POST':
        headers = get_headers(request)
        try:
            resp = httpx.delete(f"{API_URL}/books/{book_id}", headers=headers)
            if resp.status_code == 200:
                messages.success(request, "Livro excluído com sucesso!")
            elif resp.status_code == 403:
                messages.error(request, "Você não tem permissão para excluir livros.")
            else:
                messages.error(request, "Erro ao excluir livro.")
        except Exception:
            messages.error(request, "Erro de comunicação com o servidor.")
            
    return redirect('library')

def create_entity_ajax_view(request, entity_type):
    if request.method == 'POST':
        token = request.session.get('access_token')
        if not token:
            return JsonResponse({'error': 'Não autorizado'}, status=401)
        
        headers = {'Authorization': f'Bearer {token}'}
        valid_entities = ['authors', 'publishers', 'collections']
        
        if entity_type not in valid_entities:
            return JsonResponse({'error': 'Tipo de entidade inválido'}, status=400)
            
        try:
            data = json.loads(request.body)
            resp = httpx.post(f"{API_URL}/{entity_type}", json=data, headers=headers)
            
            if resp.status_code in [200, 201]:
                return JsonResponse(resp.json())
            else:
                return JsonResponse(resp.json(), status=resp.status_code)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Método não permitido'}, status=405)

def categories_view(request):
    headers = get_headers(request)
    try:
        resp = httpx.get(f"{API_URL}/categories", headers=headers)
        categories = resp.json().get('data', []) if resp.status_code == 200 else []
    except Exception:
        categories = []
        
    tree = []
    lookup = {c['id']: {**c, 'children': []} for c in categories}
    for c in categories:
        if c['parent_id'] and c['parent_id'] in lookup:
            lookup[c['parent_id']]['children'].append(lookup[c['id']])
        elif not c['parent_id']:
            tree.append(lookup[c['id']])
            
    return render(request, 'books/categories.html', {
        'categories_tree': tree, 
        'categories_flat': categories,
        'categories_json': json.dumps(categories)
    })

def manage_category_ajax_view(request, category_id=None):
    token = request.session.get('access_token')
    if not token:
        return JsonResponse({'error': 'Não autorizado'}, status=401)
    
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            resp = httpx.post(f"{API_URL}/categories", json=data, headers=headers)
        elif request.method == 'PUT' and category_id:
            data = json.loads(request.body)
            resp = httpx.put(f"{API_URL}/categories/{category_id}", json=data, headers=headers)
        elif request.method == 'DELETE' and category_id:
            resp = httpx.delete(f"{API_URL}/categories/{category_id}", headers=headers)
        else:
            return JsonResponse({'error': 'Método não permitido'}, status=405)
            
        if resp.status_code in [200, 201]:
            return JsonResponse(resp.json())
        else:
            return JsonResponse({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def create_quote_ajax_view(request, reading_id):
    """Proxy AJAX: cria citação via API FastAPI."""
    headers = get_headers(request)
    try:
        payload = json.loads(request.body)
        resp = httpx.post(
            f"{API_URL}/quotes/{reading_id}",
            json=payload,
            headers=headers
        )
        if resp.status_code in [200, 201]:
            return JsonResponse(resp.json(), status=201)
        return JsonResponse({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def delete_quote_ajax_view(request, quote_id):
    """Proxy AJAX: deleta citação via API FastAPI."""
    headers = get_headers(request)
    try:
        resp = httpx.delete(f"{API_URL}/quotes/{quote_id}", headers=headers)
        if resp.status_code == 204:
            return JsonResponse({'ok': True})
        return JsonResponse({'error': resp.text}, status=resp.status_code)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
