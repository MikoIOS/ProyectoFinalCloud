import React, { useEffect, useState } from 'react';
import { label } from './api.js';

const paths = {
  home: 'm3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8m6 10v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  wallet: 'M20 8V5a2 2 0 0 0-2-2H5a3 3 0 0 0 0 6h15v12H5a3 3 0 0 1-3-3V6m18 7h-5v4h5m-3-2h.01',
  clock: 'M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  briefcase: 'M8 6V4h8v2M3 7h18v13H3Zm0 5a20 20 0 0 0 18 0m-9-1v4',
  star: 'm12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-11 12a2 2 0 0 0 4 0',
  search: 'm21 21-5-5M18 10A8 8 0 1 1 2 10a8 8 0 0 1 16 0',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  plus: 'M12 5v14M5 12h14',
  logout: 'M9 3H3v18h6m5-14 5 5-5 5m-7-5h12',
  chevron: 'm9 5 7 7-7 7',
  check: 'm5 12 4 4L19 6',
  download: 'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',
  refresh: 'M20 7v5h-5m5-1a8 8 0 1 0-1 7',
  menu: 'M4 6h16M4 12h16M4 18h16',
  flower: 'M12 8c-8-14-14 3-5 5-13 6 3 15 5 6 7 13 15-3 6-6 13-7-4-16-6-5Z',
};
export function Icon({ name, size = 20, ...props }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={paths[name] || paths.star} /></svg>; }
export function Buddy({ kind = 'bunny', small = false }) { return <div aria-hidden="true" className={`buddy ${kind} ${small ? 'small' : ''}`}><i className="ear left"/><i className="ear right"/><div className="buddy-body"><i className="cheek left"/><i className="cheek right"/><i className="eye left"/><i className="eye right"/><span className="mouth">ω</span><i className="paw left"/><i className="paw right"/></div></div>; }
export function Skeleton({ rows = 4, cards = false }) { return <div className={cards ? 'stats-grid' : 'skeleton-list'} role="status" aria-label="Cargando contenido" aria-busy="true"><span className="sr-only">Cargando contenido…</span>{Array.from({ length: rows }, (_, i) => <div className={`skeleton-row ${cards ? 'skeleton-card' : ''}`} key={i}><span className="skeleton skeleton-avatar"/><div><span className="skeleton skeleton-line"/><span className="skeleton skeleton-line short"/></div><span className="skeleton skeleton-pill"/></div>)}</div>; }
export function Empty({ title = 'Un espacio para lo que viene', text = 'Todavía no hay registros en esta vista.', children }) { return <div className="empty"><span className="empty-icon"><Icon name="flower" size={30}/></span><h3>{title}</h3><p>{text}</p>{children}</div>; }
export function ErrorState({ error, retry }) { return <div className="error-state" role="alert"><strong>Algo no salió como esperábamos</strong><p>{error?.name === 'TimeoutError' ? 'La respuesta tardó demasiado. Puedes volver a intentarlo.' : error?.message || 'Revisa tu conexión e inténtalo otra vez.'}</p>{retry && <button className="button secondary" onClick={retry}><Icon name="refresh"/>Volver a intentar</button>}</div>; }
export function Notice({ value }) { return value ? <div className={`notice ${value.type || 'success'}`} role={value.type === 'error' ? 'alert' : 'status'}>{value.text}</div> : null; }
export function Badge({ value }) { return <span className={`badge ${['ACTIVO', 'APROBADA', 'COMPLETADA', 'GENERADA', 'ABIERTA', 'CERRADA', 'CONTRATADO'].includes(value) ? 'mint' : ['CESADO', 'RECHAZADA', 'CANCELADA', 'FALLIDA'].includes(value) ? 'rose' : 'blue'}`}><span/>{label(value)}</span>; }
export function Avatar({ name, index = 0 }) { return <span className={`avatar color-${index % 4}`} aria-hidden="true">{(name || '?').trim().split(/\s+/).slice(0, 2).map(s => s[0]).join('').toUpperCase()}</span>; }
export function SectionHead({ title, text, children }) { return <div className="section-head"><div><h2>{title}</h2>{text && <p>{text}</p>}</div><div className="head-actions">{children}</div></div>; }
export function useLoad(load, dependencies = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, data: null, error: null });
    Promise.resolve().then(() => load(controller.signal)).then(data => {
      if (!controller.signal.aborted) setState({ loading: false, data, error: null });
    }).catch(error => { if (!controller.signal.aborted) setState({ loading: false, data: null, error }); });
    return () => controller.abort();
  }, [...dependencies, revision]);
  return { ...state, reload: () => setRevision(v => v + 1) };
}
export function Resource({ state, empty, children }) {
  if (state.loading) return <Skeleton/>;
  if (state.error) return <ErrorState error={state.error} retry={state.reload}/>;
  if (empty) return <Empty/>;
  return children;
}
export function DataTable({ columns, rows, rowKey, actions }) {
  return <div className="table-wrap"><table><thead><tr>{columns.map(c => <th key={c.key} scope="col">{c.title}</th>)}{actions && <th scope="col"><span className="sr-only">Acciones</span></th>}</tr></thead><tbody>{rows.map((row, i) => <tr key={row[rowKey] || row.sk || i}>{columns.map(c => <td key={c.key}>{c.render ? c.render(row, i) : row[c.key] ?? '—'}</td>)}{actions && <td className="row-actions">{actions(row)}</td>}</tr>)}</tbody></table></div>;
}
export function FormPanel({ title, fields, onSubmit, button = 'Guardar', initial = {}, onClose, children }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  return <section className="panel form-panel"><SectionHead title={title}>{onClose && <button className="text-button" onClick={onClose}>Cerrar</button>}</SectionHead><form onSubmit={async e => {
    e.preventDefault(); if (busy) return;
    const form = e.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    for (const f of fields) if (f.type === 'number' && values[f.name] !== '') values[f.name] = Number(values[f.name]);
    const data = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== ''));
    setBusy(true); setNotice(null);
    try { const result = await onSubmit(data); setNotice({ text: typeof result === 'string' ? result : 'Listo, los cambios se guardaron.' }); form.reset(); }
    catch (error) { setNotice({ type: 'error', text: error.message || 'No se pudo guardar. Inténtalo de nuevo.' }); }
    finally { setBusy(false); }
  }}><fieldset disabled={busy} className="fields-grid">{fields.map(f => <label key={f.name} className={f.wide ? 'wide' : ''}>{f.label}{f.required && <span className="required" aria-hidden="true"> *</span>}{f.options ? <select name={f.name} required={f.required} defaultValue={initial[f.name] ?? f.defaultValue ?? ''}>{!f.defaultValue && <option value="">Selecciona una opción</option>}{f.options.map(o => <option key={typeof o === 'string' ? o : o.value} value={typeof o === 'string' ? o : o.value}>{typeof o === 'string' ? label(o) : o.label}</option>)}</select> : f.type === 'textarea' ? <textarea name={f.name} rows={3} maxLength={500} required={f.required} defaultValue={initial[f.name] || ''}/> : <input name={f.name} type={f.type || 'text'} min={f.min} max={f.max} step={f.step} maxLength={f.maxLength || 150} minLength={f.minLength} pattern={f.pattern} inputMode={f.inputMode} autoComplete={f.autoComplete} required={f.required} placeholder={f.placeholder} defaultValue={initial[f.name] ?? f.defaultValue ?? ''}/>}</label>)}</fieldset>{children}<Notice value={notice}/><button type="submit" className="button primary" disabled={busy}>{busy ? 'Guardando…' : button}<Icon name="arrow"/></button></form></section>;
}
