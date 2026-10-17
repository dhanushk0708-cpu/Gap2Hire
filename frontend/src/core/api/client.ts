export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

const TOKEN_KEY = 'gap2hire_token';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, headers = {}, ...rest } = options;

  let url = endpoint;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const token = getStoredToken();
  const requestHeaders = new Headers(headers);

  if (token && !requestHeaders.has('Authorization')) {
    requestHeaders.set('Authorization', `Bearer ${token}`);
  }

  // Don't set Content-Type if body is FormData (let browser set multipart/form-data boundary)
  if (!(rest.body instanceof FormData) && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...rest,
    headers: requestHeaders,
  });

  if (response.status === 401) {
    // If not already on /login or /register, handle logout
    if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
      clearStoredToken();
      window.location.href = '/login?session_expired=true';
    }
  }

  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred';
    let responseData = null;
    try {
      responseData = await response.json();
      if (responseData && typeof responseData === 'object') {
        errorDetail = responseData.detail || responseData.message || JSON.stringify(responseData);
      }
    } catch {
      errorDetail = response.statusText || `HTTP Error ${response.status}`;
    }
    throw new ApiError(errorDetail, response.status, responseData);
  }

  // 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    return {} as T;
  }
}
