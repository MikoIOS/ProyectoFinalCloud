"""Pruebas de UI con APIs simuladas: no escriben en los servicios AWS."""
import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    checks = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors, posts = [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        mode = {'team_error': False}

        async def api(route):
            req = route.request
            path = req.url.split('/dev', 1)[-1].split('?')[0]
            if req.method == 'OPTIONS':
                await route.fulfill(status=204, headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,OPTIONS'})
                return
            tenant = req.headers.get('authorization', '').replace('Bearer test-', '') or 'pacifico'
            user = {'tenant_id': tenant, 'nombre': 'Equipo de prueba', 'rol': 'admin_rrhh', 'user_id': 'usr-000001', 'empleado_id': 'emp-000001'}
            status, data = 200, {}
            if path == '/auth/login':
                assert set(req.post_data_json) == {'email', 'password'}
                tenant = 'pacifico'; user['tenant_id'] = tenant
                data = {'token': 'test-' + tenant, 'usuario': user}
            elif path == '/empleados/resumen':
                data = {'total': 1, 'por_estado': {'ACTIVO': 1}, 'por_area': {'Equipo de prueba': 1}}
            elif path == '/empleados':
                await asyncio.sleep(1.5)
                if mode['team_error']:
                    status, data = 500, {'error': {'mensaje': 'Error simulado de consulta'}}
                else:
                    data = {'items': [{'empleado_id': 'emp-000001', 'nombres': 'Persona', 'apellidos': tenant, 'area': 'Equipo de prueba', 'cargo': 'Prueba', 'estado': 'ACTIVO'}], 'next_token': None}
            elif path == '/nominas/resumen':
                data = {'estado': 'GENERADA', 'total_neto': 100}
            elif path == '/notificaciones':
                data = {'items': [], 'total': 0}
            elif path == '/vacantes':
                data = [{'vacante_id': 'vac-A', 'titulo': 'Vacante A de prueba', 'area': 'Equipo', 'estado': 'ABIERTA'}, {'vacante_id': 'vac-B', 'titulo': 'Vacante B de prueba', 'area': 'Equipo', 'estado': 'ABIERTA'}]
            elif path.startswith('/vacantes/'):
                data = []
            elif path == '/postulaciones' and req.method == 'POST':
                posts.append(req.post_data_json)
                data = {'postulacion': {'postulacion_id': 'pos-prueba'}, 'cv_upload_url': 'https://test.s3.amazonaws.com/cv.pdf'}; status = 201
            else:
                data = {'items': [], 'next_token': None}
            await route.fulfill(status=status, content_type='application/json', body=json.dumps(data), headers={'Access-Control-Allow-Origin': '*'})

        await page.route('https://*.execute-api.us-east-1.amazonaws.com/**', api)
        await page.goto(os.environ.get('HCM_UI_URL', 'http://127.0.0.1:5173'), wait_until='networkidle')
        assert await page.get_by_role('combobox').count() == 0
        await page.get_by_label('Correo electrónico').fill('prueba@example.invalid')
        await page.get_by_label('Contraseña', exact=True).fill('prueba-local')
        await page.get_by_role('button', name='Entrar a mi espacio').click()
        await page.get_by_role('heading', name='Tu espacio de hoy.').wait_for()
        assert await page.locator('.app-shell').get_attribute('data-tenant') == 'pacifico'
        assert await page.get_by_label('Empresa de tu cuenta').inner_text() == 'Pacífico'
        await page.get_by_role('status', name='Cargando contenido').first.wait_for(state='visible')
        await page.screenshot(path='/tmp/hcm-skeleton-desktop.png', full_page=True)
        checks.append('Skeleton en el espacio de las filas durante la petición demorada')
        await page.get_by_role('navigation').get_by_role('button', name='Mi equipo', exact=True).click()
        await page.get_by_role('cell', name='Persona pacifico').wait_for()
        mode['team_error'] = True
        await page.get_by_role('button', name='Actualizar datos').click()
        await page.get_by_role('alert').wait_for()
        mode['team_error'] = False
        await page.get_by_role('button', name='Volver a intentar').click()
        await page.get_by_role('cell', name='Persona pacifico').wait_for()
        checks.append('Error de consulta y reintento recuperan el listado')
        await page.get_by_role('navigation').get_by_role('button', name='Reclutamiento', exact=True).click()
        await page.get_by_role('button', name='Vacante A de prueba').click()
        await page.get_by_role('button', name='Nuevo candidato').click()
        await page.get_by_label('Nombre completo').fill('Candidata de prueba')
        await page.get_by_label('Correo', exact=False).fill('candidata@example.invalid')
        await page.get_by_label('Documento', exact=False).fill('ABC')
        await page.get_by_label('Sueldo ofrecido (S/)').fill('3000')
        await page.get_by_role('button', name='Guardar', exact=True).click()
        assert not posts
        await page.get_by_label('Documento', exact=False).fill('01234567')
        await page.get_by_role('button', name='Guardar', exact=True).click()
        await page.get_by_role('heading', name='CV de Candidata de prueba').wait_for()
        assert posts[0]['documento'] == '01234567' and posts[0]['vacante_id'] == 'vac-A'
        await page.get_by_role('button', name='Vacante B de prueba').click()
        assert await page.get_by_role('heading', name='CV de Candidata de prueba').count() == 0
        checks.append('Documento de ocho dígitos y subida de CV asociada a la vacante correcta')
        await page.get_by_role('button', name='Cerrar sesión', exact=True).click()
        assert await page.get_by_role('combobox').count() == 0
        checks.append('Ingreso solo con correo y contraseña; empresa obtenida de la cuenta')
        await page.set_viewport_size({'width': 375, 'height': 812})
        await page.get_by_label('Correo electrónico').fill('prueba@example.invalid')
        await page.get_by_label('Contraseña', exact=True).fill('prueba-local')
        await page.get_by_role('button', name='Entrar a mi espacio').click()
        await page.get_by_role('heading', name='Tu espacio de hoy.').wait_for()
        assert await page.locator('.sidebar').evaluate('(el) => getComputedStyle(el).visibility') == 'hidden'
        await page.get_by_role('button', name='Abrir menú', exact=True).click()
        await page.keyboard.press('Escape')
        assert await page.get_by_role('button', name='Abrir menú', exact=True).get_attribute('aria-expanded') == 'false'
        assert await page.locator('.sidebar').evaluate('(el) => getComputedStyle(el).visibility') == 'hidden'
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        checks.append('Menú móvil oculto para teclado y lectores, cierre con Escape y sin desbordamiento')
        await page.emulate_media(reduced_motion='reduce')
        await page.get_by_role('button', name='Abrir menú', exact=True).click()
        await page.get_by_role('navigation').get_by_role('button', name='Mi equipo', exact=True).click()
        await page.get_by_role('status', name='Cargando contenido').wait_for()
        assert await page.locator('.skeleton').first.evaluate('(el) => getComputedStyle(el).animationName') == 'none'
        await page.screenshot(path='/tmp/hcm-skeleton-mobile.png', full_page=True)
        checks.append('Skeleton móvil respeta movimiento reducido')
        assert await page.evaluate('localStorage.length === 0 && sessionStorage.length === 0')
        assert not errors, errors
        checks.append('Sin tokens persistidos ni errores de JavaScript')
        await browser.close()
    Path('/tmp/hcm-browser-smoke.json').write_text(json.dumps({'checks': checks}, ensure_ascii=False, indent=2))
    print(json.dumps({'comprobaciones': checks, 'total': len(checks)}, ensure_ascii=False, indent=2))


asyncio.run(main())
