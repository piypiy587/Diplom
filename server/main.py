from flask import Flask, render_template, request, jsonify, send_file
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config
from datetime import datetime
import json
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os

basedir = os.path.abspath(os.path.dirname(__file__)) # папка server
rootdir = os.path.abspath(os.path.join(basedir, "..")) # папка podpisi
template_path = os.path.join(rootdir, 'templates')
static_path = os.path.join(rootdir, 'static')


base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static')
)

app.secret_key = 'kirov-energo-secret'

# Подключение к PostgreSQL
def get_db_connection():
    """Создает подключение к PostgreSQL"""
    try:
        conn = psycopg2.connect(
            dbname="diplomm",
            user="postgres",
            password="maksim8897",
            host="localhost"
        )
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None

def init_permits_table():
    """Создает таблицу наряд-допусков, если её нет"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Создаем таблицу наряд-допусков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permits (
                id SERIAL PRIMARY KEY,
                permit_number VARCHAR(50) UNIQUE NOT NULL,
                organization VARCHAR(200) DEFAULT 'Филиал "Кировэнерго"',
                department VARCHAR(200),
                work_type_id INTEGER,
                location_id INTEGER,
                responsible_manager_id INTEGER,
                admitting_person_id INTEGER,
                work_producer_id INTEGER,
                observer_id INTEGER,
                team_members JSONB,
                work_description TEXT,
                start_date DATE,
                start_time TIME,
                end_date DATE,
                end_time TIME,
                safety_measures JSONB,
                special_instructions TEXT,
                status VARCHAR(50) DEFAULT 'created',
                signature_data TEXT,
                gps_route JSONB,
                photos JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем таблицу GPS координат для маршрутов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gps_checkpoints (
                id SERIAL PRIMARY KEY,
                location_id INTEGER,
                checkpoint_number INTEGER,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                description TEXT,
                pole_number VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем таблицу для отчетов с мобильного приложения
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspection_reports (
                id SERIAL PRIMARY KEY,
                permit_id INTEGER REFERENCES permits(id),
                checkpoint_id INTEGER REFERENCES gps_checkpoints(id),
                inspector_id INTEGER,
                visit_datetime TIMESTAMP,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                distance_from_checkpoint DECIMAL(10, 2),
                photos JSONB,
                insulator_condition VARCHAR(100),
                vegetation_status VARCHAR(100),
                pole_marking VARCHAR(200),
                wire_condition VARCHAR(100),
                issues_found TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем таблицу для подписей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permit_signatures (
                id SERIAL PRIMARY KEY,
                permit_id INTEGER REFERENCES permits(id),
                employee_id INTEGER,
                role VARCHAR(100),
                signature_image TEXT,
                signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cursor.close()
        print("Таблицы успешно созданы/проверены")
    except Exception as e:
        print(f"Ошибка создания таблиц: {e}")
        conn.rollback()
    finally:
        conn.close()

# Инициализация таблиц при запуске
init_permits_table()

# --- ЛОГИКА ВХОДА ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # ЖЕСТКАЯ ПРОВЕРКА: разрешаем вход только admin и user
            allowed_web_roles = ['admin', 'user']
            
            if user['role'] not in allowed_web_roles:
                return render_template('login.html', 
                    error="Доступ к веб-версии запрещен. Пожалуйста, используйте мобильное приложение.")

            # Если роль подходит - пускаем
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
            
        return render_template('login.html', error="Неверный логин или пароль")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# 1. Страница списка отчетов
@app.route('/view-reports')
def view_reports_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('view_reports.html')

# 2. API для получения списка нарядов, по которым есть отчеты
@app.route('/api/reports-list')
def get_reports_list():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Используем простой JOIN для получения списка нарядов с координатами
    cursor.execute("""
        SELECT DISTINCT ON (p.id) 
            p.id, p.p_num, p.dept_name, p.work_task, 
            ir.latitude, ir.longitude
        FROM permits p
        JOIN inspection_reports ir ON p.id = ir.permit_id
        ORDER BY p.id DESC
    """)
    list_data = cursor.fetchall()
    conn.close()
    return jsonify(list_data)

@app.route('/api/reports/<int:permit_id>')
def get_report_details(permit_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT ir.*, e.fio as inspector_name 
        FROM inspection_reports ir
        LEFT JOIN employees e ON ir.inspector_id = e.id 
        WHERE ir.permit_id = %s
        ORDER BY ir.created_at DESC
    """, (permit_id,))
    reports = cursor.fetchall()
    for r in reports:
        if r.get('photos') and isinstance(r['photos'], str):
            r['photos'] = json.loads(r['photos'])
    conn.close()
    return jsonify(reports)
# --- ГЛАВНАЯ СТРАНИЦА ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # СЧИТАЕМ ПРАВИЛЬНО
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM permits) as total,
            
            (SELECT COUNT(*) FROM permits 
             WHERE status IN ('new', 'in_progress', 'signed')) as count_active,
             
            (SELECT COUNT(DISTINCT permit_id) FROM inspection_reports) as count_completed
    """)
    stats = cursor.fetchone()

    # 2. Получаем последние наряды (чистим данные от возможных ошибок)
    cursor.execute("""
        SELECT id, p_num, dept_name, status, 
               TO_CHAR(created_at, 'DD.MM HH24:MI') as time_short
        FROM permits 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    recent_permits = cursor.fetchall()
    
    # 3. Статистика по базе (для админа структуры)
    cursor.execute("SELECT COUNT(*) as c FROM departments")
    depts_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) as c FROM employees")
    emps_count = cursor.fetchone()['c']

    conn.close()
    
    return render_template('index.html', 
                         stats=stats, 
                         recent_permits=recent_permits,
                         depts_count=depts_count,
                         emps_count=emps_count)

# Управление подразделениями
@app.route('/manage-departments', methods=['GET', 'POST'])
def manage_departments():
    # ВАЖНО: Проверяем роль 'admin'
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        name = request.form.get('dept_name')
        cursor.execute("INSERT INTO departments (name) VALUES (%s) ON CONFLICT DO NOTHING", (name,))
        conn.commit()
    
    cursor.execute("SELECT * FROM departments ORDER BY name")
    depts = cursor.fetchall()
    conn.close()
    return render_template('manage_depts.html', depts=depts)

@app.route('/api/mobile/login', methods=['POST'])
def mobile_login():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Мы ОБЯЗАТЕЛЬНО выбираем employee_id (он же emp_id в коде Android)
    cursor.execute("""
        SELECT u.id, u.username, u.role, e.fio, u.employee_id as emp_id 
        FROM users u 
        LEFT JOIN employees e ON u.employee_id = e.id 
        WHERE u.username = %s AND u.password = %s
    """, (data.get('username'), data.get('password')))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        if user['role'] == 'admin':
            return jsonify({"success": False, "error": "Админам вход запрещен"}), 403
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "error": "Ошибка входа"}), 401

# API для получения данных наряда с подписями (Live-обновление)
@app.route('/api/mobile/permit-status/<int:permit_id>')
def mobile_permit_status(permit_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # ОБЯЗАТЕЛЬНО выбираем printed_name
    cursor.execute("SELECT role, printed_name, signature_image FROM permit_signatures WHERE permit_id = %s", (permit_id,))
    sigs = cursor.fetchall()
    conn.close()
    return jsonify({"signatures": sigs})

# Управление сотрудниками
@app.route('/manage-employees', methods=['GET', 'POST'])
def manage_employees():
    # ВАЖНО: Проверяем роль 'admin'
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        fio = request.form.get('fio')
        cursor.execute("INSERT INTO employees (fio) VALUES (%s)", (fio,))
        conn.commit()
    
    cursor.execute("SELECT * FROM employees ORDER BY fio")
    employees = cursor.fetchall()
    conn.close()
    return render_template('manage_employees.html', employees=employees)

# ========== МАРШРУТЫ API ==========


@app.route('/create-permit')
def create_permit_page():
    # Проверяем, что пользователь вообще вошел (роль либо admin, либо user)
    if session.get('role') not in ['admin', 'user']:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Загружаем списки для выбора (теперь они нужны всем)
    cursor.execute('SELECT id, fio FROM employees ORDER BY fio')
    employees = cursor.fetchall()
    
    cursor.execute('SELECT name as place_name FROM departments ORDER BY name')
    locations = cursor.fetchall()
    
    cursor.execute('SELECT id, work_name FROM work_types ORDER BY work_name')
    work_types = cursor.fetchall()
    
    conn.close()
    
    # Передаем mode='create', чтобы поля были активными
    return render_template('create_permit.html', 
                         mode='create', 
                         permit=None, 
                         employees=employees, 
                         locations=locations, 
                         work_types=work_types)

@app.route('/api/work-types', methods=['GET'])
def get_work_types():
    """Получить все типы работ"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT id, work_name FROM work_types ORDER BY work_name')
    work_types = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(work_types)

@app.route('/api/locations', methods=['GET'])
def get_locations():
    """Получить все локации"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT id, place_name FROM locations ORDER BY place_name')
    locations = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(locations)

@app.route('/api/employees', methods=['GET'])
def get_employees():
    """Получить всех сотрудников с поиском"""
    search = request.args.get('search', '')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    if search:
        cursor.execute('''
            SELECT id, fio 
            FROM employees 
            WHERE LOWER(fio) LIKE LOWER(%s)
            ORDER BY fio
            LIMIT 20
        ''', (f'%{search}%',))
    else:
        cursor.execute('SELECT id, fio FROM employees ORDER BY fio')
    
    employees = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(employees)

@app.route('/api/locations/<int:location_id>/checkpoints', methods=['GET'])
def get_location_checkpoints(location_id):
    """Получить GPS точки для конкретной локации"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT id, checkpoint_number, latitude, longitude, 
               description, pole_number
        FROM gps_checkpoints
        WHERE location_id = %s
        ORDER BY checkpoint_number
    ''', (location_id,))
    
    checkpoints = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(checkpoints)


def create_permit_api():
    data = request.json@app.route('/api/permits', methods=['POST'])
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Нет подключения к БД'}), 500
    
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO permits (
                permit_number, organization, department, resp_manager, 
                admitter, producer, team_list, work_task, 
                date_start, time_start, date_end, time_end, 
                measures, special_notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            data.get('permit_number'),
            data.get('organization'),
            data.get('department'),
            data.get('resp_manager'),
            data.get('admitter'),
            data.get('producer'),
            data.get('team_list'),
            data.get('work_task'),
            data.get('date_start'),
            data.get('time_start'),
            data.get('date_end'),
            data.get('time_end'),
            json.dumps(data.get('measures')),
            data.get('special_notes')
        )
        cursor.execute(query, params)
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"ОШИБКА БД: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()

# 1. ПОЛУЧЕНИЕ СПИСКА (GET)
@app.route('/api/permits', methods=['GET'])
def get_permits():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT 
            id, 
            p_num, 
            dept_name, 
            work_task, 
            resp_manager, 
            status,
            TO_CHAR(created_at, 'DD.MM.YYYY HH24:MI') as date_created,
            EXISTS(SELECT 1 FROM inspection_reports WHERE permit_id = permits.id) as has_report
        FROM permits 
        ORDER BY created_at DESC
    """)
    permits = cursor.fetchall()
    conn.close()
    return jsonify(permits)

@app.route('/api/permits/<int:permit_id>', methods=['PUT'])
def update_permit_api(permit_id):
    if session.get('role') != 'admin':
        return jsonify({"success": False, "error": "Доступ запрещен"}), 403

    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        fields = []
        values = []
        
        for key, value in data.items():
            # ВАЖНО: Пропускаем технические ID, их нельзя менять в UPDATE
            if key in ['id', 'current_permit_id']:
                continue
            
            fields.append(f"{key} = %s")
            # Если значение - таблица (список), упаковываем в JSON
            if isinstance(value, (list, dict)):
                values.append(json.dumps(value))
            else:
                values.append(value)
        
        if not fields:
            return jsonify({"success": False, "error": "Нет данных для обновления"}), 400

        values.append(permit_id) # Добавляем ID для условия WHERE
        query = f"UPDATE permits SET {', '.join(fields)} WHERE id = %s"
        
        # Печатаем в терминал для проверки
        print(f"ВЫПОЛНЯЮ ОБНОВЛЕНИЕ: {query}")
        
        cursor.execute(query, values)
        conn.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"ОШИБКА ПРИ ОБНОВЛЕНИИ БД: {e}")
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@app.route('/api/permits/<int:permit_id>', methods=['PUT'])
def update_permit(permit_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Динамически собираем запрос на обновление
    fields = []
    values = []
    for key, value in data.items():
        if key == 'id': continue
        fields.append(f"{key} = %s")
        values.append(json.dumps(value) if isinstance(value, list) else value)
    
    values.append(permit_id)
    query = f"UPDATE permits SET {', '.join(fields)} WHERE id = %s"
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/permits/<int:permit_id>/status', methods=['PATCH'])
def update_permit_status(permit_id):
    # ВАЖНО: Проверяем новую роль 'admin'
    if session.get('role') != 'admin':
        return jsonify({"success": False, "error": "Нет прав"}), 403

    data = request.json
    new_status = data.get('status')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE permits SET status = %s WHERE id = %s", (new_status, permit_id))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        conn.close()

# 2. СОХРАНЕНИЕ НОВОГО НАРЯДА (POST)
@app.route('/api/permits', methods=['POST'])
def save_permit_api():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Составляем списки полей и значений динамически
    fields = []
    values = []
    
    for key, value in data.items():
        fields.append(key)
        # Если значение - список (таблица), превращаем в JSON строку
        if isinstance(value, list) or isinstance(value, dict):
            values.append(json.dumps(value))
        else:
            values.append(value)
            
    # Добавляем статус по умолчанию
    if 'status' not in fields:
        fields.append('status')
        values.append('new') 

    # Формируем SQL запрос
    query = f"INSERT INTO permits ({', '.join(fields)}) VALUES ({', '.join(['%s'] * len(values))})"
    
    try:
        cursor.execute(query, values)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print(f"ОШИБКА INSERT: {e}")
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/permits/<int:permit_id>', methods=['GET'])
def get_permit_details(permit_id):
    """Получить детальную информацию о наряд-допуске"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('''
            SELECT * FROM permits WHERE id = %s
        ''', (permit_id,))
        
        permit = cursor.fetchone()
        
        # Для совместимости с шаблоном просмотра добавим нужные ключи
        if permit:
            permit['responsible_manager_fio'] = permit['resp_manager']
            permit['admitting_person_fio'] = permit['admitter']
            permit['work_producer_fio'] = permit['producer']
            permit['place_name'] = permit['department']
            permit['work_name'] = permit['work_task']
            # Т.к. мероприятия лежат в JSON, они подгрузятся автоматически
            
        return jsonify(permit) if permit else ({'error': 'Not found'}, 404)
    finally:
        cursor.close()
        conn.close()

@app.route('/api/permits/<int:permit_id>/signatures', methods=['POST'])
def add_signature(permit_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ВАЖНО: Получаем имя, которое прислал телефон
    printed_name = data.get('printed_name') 
    employee_id = data.get('employee_id')
    role = data.get('role')
    image = data.get('signature_image')

    try:
        cursor.execute("""
            INSERT INTO permit_signatures (permit_id, employee_id, role, signature_image, printed_name)
            VALUES (%s, %s, %s, %s, %s)
        """, (permit_id, employee_id, role, image, printed_name))
        
        # Обновляем статус наряда на 'signed'
        cursor.execute("UPDATE permits SET status = 'in_progress' WHERE id = %s", (permit_id,))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Ошибка сохранения подписи: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()
# 1. Список для ПОДПИСАНИЯ (теперь ищем статус 'new')
@app.route('/api/mobile/permits/to-sign')
def get_permits_to_sign():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # ИСПРАВЛЕНО: ищем статус 'new'
    cursor.execute("""
        SELECT id, p_num, work_task, status, 
        EXISTS(SELECT 1 FROM inspection_reports WHERE permit_id = permits.id) as has_report 
        FROM permits 
        WHERE status = 'new' 
        ORDER BY created_at DESC
    """)
    permits = cursor.fetchall()
    conn.close()
    return jsonify(permits)

# 2. Список для ОТЧЕТНОСТИ (теперь ищем статус 'in_progress')
@app.route('/api/mobile/permits/to-report')
def get_permits_to_report():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # ИСПРАВЛЕНО: ищем статус 'in_progress' (то есть уже подписанные)
    cursor.execute("""
        SELECT p.id, p.p_num, p.work_task, p.status, true as has_report
        FROM permits p
        WHERE p.status = 'in_progress' 
        AND NOT EXISTS (SELECT 1 FROM inspection_reports ir WHERE ir.permit_id = p.id)
        ORDER BY p.created_at DESC
    """)
    permits = cursor.fetchall()
    conn.close()
    return jsonify(permits)

# --- УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (Для Админа) ---
@app.route('/manage-users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    error_msg = None # Для хранения ошибки

    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        e_id = request.form.get('employee_id')
        r = request.form.get('role')
        
        # Если сотрудник не выбран (пустая строка), ставим None для базы
        e_id = e_id if e_id and e_id.strip() else None
        
        try:
            cursor.execute("""
                INSERT INTO users (username, password, employee_id, role) 
                VALUES (%s, %s, %s, %s)
            """, (u, p, e_id, r))
            conn.commit()
            return redirect(url_for('manage_users')) # Перезагрузка после успеха
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            error_msg = f"Ошибка: Логин '{u}' уже занят! Выберите другое имя."
        except Exception as e:
            conn.rollback()
            error_msg = f"Произошла ошибка: {e}"

    # Загружаем данные для страницы
    cursor.execute("SELECT id, fio FROM employees ORDER BY fio")
    employees = cursor.fetchall()
    cursor.execute("""
        SELECT u.id, u.username, u.role, e.fio 
        FROM users u 
        LEFT JOIN employees e ON u.employee_id = e.id 
        ORDER BY u.id
    """)
    users = cursor.fetchall()
    conn.close()
    
    return render_template('manage_users.html', users=users, employees=employees, error=error_msg)

@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'admin': return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_users'))

@app.route('/api/inspection-report', methods=['POST'])
def create_inspection_report():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Проверяем на Upsert (обновление или создание)
        cursor.execute("SELECT id FROM inspection_reports WHERE permit_id = %s", (data.get('permit_id'),))
        exists = cursor.fetchone()

        if exists:
            query = """UPDATE inspection_reports SET 
                       report_text=%s, weather=%s, equip_condition=%s, safety_check=%s, 
                       latitude=%s, longitude=%s, photos=%s, created_at=CURRENT_TIMESTAMP 
                       WHERE permit_id=%s"""
            params = (data.get('report_text'), data.get('weather'), data.get('equip_condition'), 
                      data.get('safety_check'), data.get('latitude'), data.get('longitude'), 
                      json.dumps(data.get('photos')), data.get('permit_id'))
        else:
            query = """INSERT INTO inspection_reports 
                       (permit_id, inspector_id, report_text, weather, equip_condition, safety_check, latitude, longitude, photos)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            params = (data.get('permit_id'), data.get('inspector_id'), data.get('report_text'), 
                      data.get('weather'), data.get('equip_condition'), data.get('safety_check'), 
                      data.get('latitude'), data.get('longitude'), json.dumps(data.get('photos')))

        cursor.execute(query, params)
        # Также обновляем статус наряда
        cursor.execute("UPDATE permits SET status = 'completed' WHERE id = %s", (data.get('permit_id'),))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Ошибка акта: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/reports/by-permit/<int:permit_id>')
def get_report_by_permit(permit_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM inspection_reports WHERE permit_id = %s LIMIT 1", (permit_id,))
    report = cursor.fetchone()
    if report and report['photos']:
        report['photos'] = json.loads(report['photos'])
    conn.close()
    return jsonify(report) if report else ({}, 404)

@app.route('/api/permits/<int:permit_id>/reports', methods=['GET'])
def get_permit_reports(permit_id):
    """Получить все отчеты по наряд-допуску"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT 
            ir.*,
            e.fio as inspector_name,
            gc.pole_number,
            gc.description as checkpoint_description
        FROM inspection_reports ir
        LEFT JOIN employees e ON ir.inspector_id = e.id
        LEFT JOIN gps_checkpoints gc ON ir.checkpoint_id = gc.id
        WHERE ir.permit_id = %s
        ORDER BY ir.visit_datetime
    ''', (permit_id,))
    
    reports = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(reports)

@app.route('/view-permit/<int:permit_id>')
def view_permit(permit_id):
    is_mobile = request.args.get('mobile') == 'true'
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Загружаем сам наряд
    cursor.execute("SELECT * FROM permits WHERE id = %s", (permit_id,))
    permit = cursor.fetchone()
    
    if not permit:
        return "Наряд не найден", 404

    # 2. ОБЯЗАТЕЛЬНО загружаем списки для выбора (чтобы админ мог редактировать)
    cursor.execute('SELECT id, fio FROM employees ORDER BY fio')
    employees = cursor.fetchall()
    
    cursor.execute('SELECT name as place_name FROM departments ORDER BY name')
    locations = cursor.fetchall()
    
    cursor.execute('SELECT id, work_name FROM work_types ORDER BY work_name')
    work_types = cursor.fetchall()

    # 3. Загружаем подписи
    cursor.execute("SELECT role, printed_name, signature_image FROM permit_signatures WHERE permit_id = %s", (permit_id,))
    sigs_raw = cursor.fetchall()
    
    # СОЗДАЕМ УМНЫЙ СЛОВАРЬ: {'Производитель работ': {'image': '...', 'name': '...'}}
    sig_dict = {}
    for s in sigs_raw:
        sig_dict[s['role']] = {
            'image': s['signature_image'],
            'name': s['printed_name']
        }

    # 4. Парсим таблицу мероприятий
    if permit.get('measures') and isinstance(permit['measures'], str):
        permit['measures'] = json.loads(permit['measures'])

    conn.close()
    
    # Передаем ВСЕ данные в шаблон
    return render_template('create_permit.html', 
                         mode='view', 
                         permit=permit, 
                         signatures=sig_dict,
                         employees=employees, 
                         locations=locations,
                         is_mobile=is_mobile,
                         work_types=work_types)

@app.route('/view-permits')
def view_permits():
    # Передаем роль из сессии. Если её нет - ставим 'guest'
    return render_template('view_permits.html', role=session.get('role', 'guest'))

# API для Android приложения
@app.route('/api/mobile/permits/active', methods=['GET'])
def get_active_permits_for_mobile():
    """Получить активные наряды для мобильного приложения"""
    employee_id = request.args.get('employee_id', type=int)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Ищем наряды, где сотрудник является членом бригады
    cursor.execute('''
        SELECT 
            p.id,
            p.permit_number,
            p.work_description,
            wt.work_name,
            l.place_name,
            p.start_date,
            p.start_time,
            p.end_date,
            p.end_time,
            p.status
        FROM permits p
        LEFT JOIN work_types wt ON p.work_type_id = wt.id
        LEFT JOIN locations l ON p.location_id = l.id
        WHERE p.status IN ('created', 'in_progress')
        AND (
            p.responsible_manager_id = %s
            OR p.work_producer_id = %s
            OR p.team_members @> %s::jsonb
        )
        ORDER BY p.start_date DESC, p.start_time DESC
    ''', (employee_id, employee_id, json.dumps([employee_id])))
    
    permits = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(permits)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

@app.route('/api/mobile/permits', methods=['GET'])
def get_active_permits():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Берем наряды, которые еще не завершены
    cursor.execute("SELECT id, permit_number, work_task, date_start FROM permits ORDER BY created_at DESC")
    permits = cursor.fetchall()
    conn.close()
    return jsonify(permits)

if __name__ == '__main__':
    # host='0.0.0.0' заставляет Flask слушать все сетевые интерфейсы
    app.run(debug=True, host='0.0.0.0', port=5000)
