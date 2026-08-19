import httpx
from django.conf import settings

def api_request(request, method, endpoint, **kwargs):
    """
    Wrapper centralizado em torno do httpx para conectar com a API do backend FastAPI.
    Injeta o token automaticamente e, em caso de 401, tenta o refresh transparente.
    """
    url = f"{settings.API_BASE_URL}{endpoint}" if str(endpoint).startswith('/') else f"{settings.API_BASE_URL}/{endpoint}"
    
    headers = kwargs.pop('headers', {})
    token = request.session.get('access_token')
    if token:
        headers['Authorization'] = f'Bearer {token}'
        
    try:
        response = httpx.request(method, url, headers=headers, **kwargs)
        
        # Se o token expirar
        if response.status_code == 401:
            refresh_token = request.session.get('refresh_token')
            if refresh_token:
                refresh_url = f"{settings.API_BASE_URL}/auth/refresh"
                refresh_headers = {'Authorization': f'Bearer {refresh_token}'}
                refresh_resp = httpx.post(refresh_url, headers=refresh_headers)
                
                if refresh_resp.status_code == 200:
                    token_data = refresh_resp.json()
                    new_access = token_data.get('access_token')
                    new_refresh = token_data.get('refresh_token')
                    
                    # Atualiza a sessão
                    request.session['access_token'] = new_access
                    if new_refresh:
                        request.session['refresh_token'] = new_refresh
                        
                    # Refaz o request original com o novo token
                    headers['Authorization'] = f'Bearer {new_access}'
                    response = httpx.request(method, url, headers=headers, **kwargs)
                else:
                    # Falhou no refresh (ex: refresh_token expirado)
                    request.session.flush()
            else:
                request.session.flush()
                
        return response
    except httpx.RequestError as e:
        raise e
