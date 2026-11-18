# LoanManager — Sistema Profesional de Gestión de Préstamos

> **Plataforma web fintech para control y administración centralizada de préstamos de dinero, cartera, cuotas, recaudos y flujo de caja.**  
> *Moneda: Pesos Colombianos (COP) | Zona Horaria: America/Bogota (UTC-5)*

---

## 1. Tecnologías Principales

* **Backend:** Python 3.12+, Django 5.1 (Arquitectura modular por aplicaciones, Domain Services desacoplados, Django ORM).
* **Base de Datos:** PostgreSQL (compatible con Neon PostgreSQL en producción y SQLite en desarrollo local ágil).
* **Frontend:** Django Templates + Tailwind CSS + HTMX + Alpine.js + Chart.js + Lucide Icons.
* **Formatos y Documentos:** ReportLab (recibos y comprobantes PDF) y OpenPyXL (reportes Excel).
* **Seguridad:** Aislamiento transaccional, bloqueos pesimistas, tipo numérico exacto `Decimal(14, 2)` con redondeo `ROUND_HALF_UP` y auditoría inmutable de pagos y caja.

---

## 2. Estructura del Proyecto

```text
PROYECTO TECNICO/
├── config/
│   ├── settings/
│   │   ├── base.py          # Configuración base, apps y middleware
│   │   ├── local.py         # Desarrollo local (SQLite o PostgreSQL local)
│   │   └── production.py    # Producción (Neon PostgreSQL, WhiteNoise, HTTPS)
│   ├── urls.py              # Enrutamiento central sin enlaces rotos
│   └── wsgi.py
├── apps/
│   ├── core/                # Modelos base, utilidades COP, context processors
│   ├── users/               # CustomUser con roles, login y perfil
│   ├── customers/           # Directorio y ficha financiera de clientes
│   ├── loans/               # Préstamos, cuotas y motor financiero
│   ├── payments/            # Recaudos, waterfall de asignación y reversión
│   ├── cashflow/            # Movimientos de caja real y arqueos
│   ├── portfolio/           # Análisis de cartera y buckets de morosidad
│   ├── calendar_app/        # Calendario interactivo con código de semáforo
│   ├── notifications/       # Alertas internas y resumen diario matutino (7 AM)
│   ├── reports/             # Generador de informes y exportaciones
│   └── audit/               # Auditoría inmutable de cambios financieros
├── templates/
│   ├── base.html            # Layout maestro con Tailwind, Lucide, Alpine y Chart.js
│   ├── components/          # Sidebar colapsable, Navbar, Toasts y Modales
│   ├── core/                # Dashboard financiero con 8 KPIs y gráficos
│   └── users/               # Vistas de autenticación (Login, Perfil, Contraseña)
├── tests/                   # Suite de pruebas automatizadas
├── static/                  # Archivos estáticos y estilos
├── manage.py
├── requirements.txt
└── .env.example
```

---

## 3. Instalación y Ejecución Local

### Paso 1: Clonar o ingresar al directorio del proyecto
```bash
cd "PROYECTO TECNICO"
```

### Paso 2: Crear y activar entorno virtual
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Paso 3: Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 4: Configurar variables de entorno
```bash
cp .env.example .env
```

### Paso 5: Aplicar migraciones de base de datos
```bash
python manage.py migrate
```

### Paso 6: Inicializar el superusuario administrador
```bash
python manage.py init_admin
```
* **Usuario:** `admin@loanmanager.local`
* **Contraseña predeterminada:** `AdminLoan2026!`

### Paso 7: Ejecutar la suite de pruebas
```bash
python manage.py test tests
```

### Paso 8: Iniciar el servidor de desarrollo
```bash
python manage.py runserver
```
Acceder en el navegador a: `http://127.0.0.1:8000/`

---

## 4. Estado de Avance por Fases

- [x] **Fase 0: Análisis, Arquitectura y Modelo de Datos** (Finalizada).
- [x] **Fase 1: Base del Proyecto y UI Foundation** (Finalizada y probada con 7 tests automatizados).
- [ ] **Fase 2: Módulo de Clientes** (En cola).
- [ ] **Fase 3: Préstamos y Motor de Cálculo Financiero**.
- [ ] **Fase 4: Módulo de Cuotas y Cronograma de Amortización**.
- [ ] **Fase 5: Módulo de Pagos, Abonos y Recibos PDF**.
- [ ] **Fase 6: Calendario de Cobros y Sistema de Alertas Automáticas**.
- [ ] **Fase 7: Caja, Arqueos y Análisis de Cartera**.
- [ ] **Fase 8: Reportes Financieros y Exportaciones (Excel, PDF, CSV)**.
- [ ] **Fase 9: Seguridad, Auditoría y QA Integral**.
- [ ] **Fase 10: Docker, DevOps y Despliegue en Neon + Render**.

