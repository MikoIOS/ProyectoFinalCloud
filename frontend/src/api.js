const env = import.meta.env ?? {};
export const endpoints = {
  usuarios: env.VITE_USUARIOS_URL || 'https://ckuqmvszfj.execute-api.us-east-1.amazonaws.com/dev',
  empleados: env.VITE_EMPLEADOS_URL || 'https://39vy8bpqn4.execute-api.us-east-1.amazonaws.com/dev',
  nominas: env.VITE_NOMINAS_URL || 'https://0f0k9vomdk.execute-api.us-east-1.amazonaws.com/dev',
  asistencia: env.VITE_ASISTENCIA_URL || 'https://p79musr10g.execute-api.us-east-1.amazonaws.com/dev',
  reclutamiento: env.VITE_RECLUTAMIENTO_URL || 'https://ts3pqiwi7e.execute-api.us-east-1.amazonaws.com/dev',
  desempeno: env.VITE_DESEMPENO_URL || 'https://4gchww17uh.execute-api.us-east-1.amazonaws.com/dev',
  notificaciones: env.VITE_NOTIFICACIONES_URL || 'https://3wfj6ozaga.execute-api.us-east-1.amazonaws.com/dev',
};

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
export function createApi(token, onExpired = () => {}) {
  return async function request(service, path, { method = 'GET', body, signal, pdf = false } = {}) {
    const controller = AbortSignal.timeout(25000);
    const response = await fetch(endpoints[service] + path, {
      method, cache: 'no-store', signal: signal ? AbortSignal.any([signal, controller]) : controller,
      headers: { Accept: pdf ? 'application/pdf' : 'application/json', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      if (response.status === 401 && token) onExpired();
      throw new ApiError(data?.error?.mensaje || (typeof data?.error === 'string' ? data.error : null) || (response.status === 403 ? 'No tienes permiso para realizar esta acción.' : 'No pudimos completar la solicitud. Inténtalo otra vez.'), response.status);
    }
    if (pdf) {
      if (!response.headers.get('content-type')?.includes('application/pdf')) throw new Error('El servidor no devolvió una boleta PDF.');
      return response.blob();
    }
    return response.status === 204 ? null : response.json();
  };
}
export const query = (values) => {
  const params = new URLSearchParams(Object.entries(values).filter(([, value]) => value !== '' && value != null));
  return params.size ? '?' + params : '';
};
export const money = (value) => new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN', maximumFractionDigits: 2 }).format(Number(value) || 0);
export const number = (value) => new Intl.NumberFormat('es-PE').format(Number(value) || 0);
export const label = (value) => value ? String(value).replaceAll('_', ' ').toLocaleLowerCase('es').replace(/^./, c => c.toUpperCase()) : '—';
export const month = () => new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', timeZone: 'America/Lima' }).format(new Date()).replace('/', '-');
export const isSupervisor = (user) => ['admin_rrhh', 'gerente'].includes(user.rol);
export function allowedPages(user) {
  return ['inicio', ...(isSupervisor(user) ? ['empleados'] : []), 'perfil', 'nominas', 'asistencia', ...(['admin_rrhh', 'reclutador'].includes(user.rol) ? ['reclutamiento'] : []), 'desempeno', 'notificaciones'];
}
