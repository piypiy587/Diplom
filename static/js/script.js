window.USER_ROLE = "{{ session['role'] }}";
window.APP_MODE = "{{ mode }}";


const API_BASE_URL = '';

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU');
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.classList.add('show'), 100);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

class PermitVisualBuilder {
    constructor() {
        console.log("Инициализация конструктора наряда...");
        
        // Привязка элементов интерфейса
        this.drawer = document.getElementById('selection-drawer');
        this.overlay = document.getElementById('drawer-overlay');
        this.listContainer = document.getElementById('drawer-items-list');
        this.drawerTitle = document.getElementById('drawer-title');
        this.searchInput = document.getElementById('drawerSearchInput');
        this.multiActions = document.getElementById('drawer-multi-actions');
        this.selectedCountLabel = document.getElementById('selectedCount');
        this.doneBtn = document.getElementById('multiSelectDone');

        this.activeFieldId = null;
        this.tempSelected = [];

        // Если мы на странице с листами наряда (есть класс .a4-sheet или сам drawer)
        if (this.drawer) {
            this.init();
        }
    }

    // МЕТОД ИНИЦИАЛИЗАЦИИ (Важно, чтобы он был внутри class {})
    init() {
        if (document.querySelector('.readonly-mode')) {
            console.log("Система: Режим 'Только чтение' активен.");
            return; // Дальше код инициализации кликов просто не пойдет
        }
        document.addEventListener('mousedown', (e) => {
            const field = e.target.closest('.clickable');
            if (field) {
                // ГЛАВНОЕ УСЛОВИЕ БЛОКИРОВКИ:
                // Если мы в режиме просмотра И мы НЕ админ — выходим из функции
                if (window.APP_MODE === 'view' && window.USER_ROLE !== 'admin') {
                    console.log("Доступ только для чтения");
                    return; 
                }

                const type = field.getAttribute('data-type');
                if (type && type !== 'text') {
                    e.preventDefault();
                    e.stopPropagation();
                    this.openDrawer(type, field.id);
                }
            }
        });
        // 1. Клик по интерактивным полям в бланке
        document.querySelectorAll('.clickable').forEach(field => {
            field.onclick = () => {
                // Проверяем, не в режиме ли мы просмотра (если нет кнопки сохранить)
                if (!document.getElementById('submitData')) return;

                const type = field.getAttribute('data-type');
                // Если тип "text" - меню не открываем (это для ручного ввода)
                if (type && type !== 'text') {
                    this.openDrawer(type, field.id);
                }
            };
        });

        // 2. Кнопка сохранения
        const saveBtn = document.getElementById('submitData');
        if (saveBtn) {
            saveBtn.onclick = () => this.savePermit();
        }

        // 3. Закрытие меню
        document.querySelector('.close-drawer')?.addEventListener('click', () => this.closeDrawer());
        this.overlay?.addEventListener('click', () => this.closeDrawer());

        // 4. Логика поиска в меню
        this.searchInput?.addEventListener('input', (e) => {
            const filter = e.target.value.toLowerCase();
            const items = this.listContainer.querySelectorAll('.drawer-item');
            items.forEach(item => {
                const text = item.innerText.toLowerCase();
                item.style.display = text.includes(filter) ? "" : "none";
            });
        });

        // 5. Кнопка "Готово" для мульти-выбора
        this.doneBtn?.addEventListener('click', () => {
            const field = document.getElementById(this.activeFieldId);
            if (field) {
                field.innerText = this.tempSelected.join('; ');
            }
            this.closeDrawer();
        });
    }

    openDrawer(type, fieldId) {
        console.log("Открываем Drawer для:", type);
        this.activeFieldId = fieldId;
        this.drawer.classList.add('open');
        this.overlay.classList.add('active');

        if (this.searchInput) this.searchInput.value = "";

        // Режим множественного выбора
        if (type.includes('_multi')) {
            if (this.multiActions) this.multiActions.style.display = "block";
            this.tempSelected = []; 
            this.updateCount();
        } else {
            if (this.multiActions) this.multiActions.style.display = "none";
        }

        let items = [];
        if (window.DB_DATA) {
            if (type.includes('employee')) items = window.DB_DATA.employees || [];
            else if (type.includes('location')) items = window.DB_DATA.locations || [];
            else if (type.includes('work_type')) items = window.DB_DATA.work_types || [];
        }

        this.renderItems(items, type);
    }

    renderItems(items, type) {
        this.listContainer.innerHTML = '';
        if (!items || items.length === 0) {
            this.listContainer.innerHTML = '<div style="padding:20px; color:gray;">Данные не загружены из базы</div>';
            return;
        }

        items.forEach(item => {
            const text = item.fio || item.place_name || item.work_name;
            const div = document.createElement('div');
            div.className = 'drawer-item';
            div.innerHTML = `<strong>${text}</strong>`;
            
            div.onclick = () => {
                if (type.includes('_multi')) {
                    if (this.tempSelected.includes(text)) {
                        this.tempSelected = this.tempSelected.filter(i => i !== text);
                        div.classList.remove('selected');
                    } else {
                        this.tempSelected.push(text);
                        div.classList.add('selected');
                    }
                    this.updateCount();
                } else {
                    const field = document.getElementById(this.activeFieldId);
                    if (field) {
                        field.innerText = text;
                        field.setAttribute('data-db-id', item.id);
                    }
                    this.closeDrawer();
                }
            };
            this.listContainer.appendChild(div);
        });
    }

    updateCount() {
        if (this.selectedCountLabel) {
            this.selectedCountLabel.innerText = this.tempSelected.length;
        }
    }

    closeDrawer() {
        this.drawer.classList.remove('open');
        this.overlay.classList.remove('active');
    }

    collectTable(tableId) {
        const rows = [];
        const table = document.getElementById(tableId);
        if (!table) return rows;

        table.querySelectorAll('tbody tr').forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length > 0) {
                const rowData = {};
                cells.forEach((cell, i) => { 
                    rowData[`col${i+1}`] = cell.innerText.trim(); 
                });
                // Сохраняем строку, только если в ней есть хоть какой-то текст
                const hasContent = Object.values(rowData).some(val => val !== "");
                if (hasContent) rows.push(rowData);
            }
        });
        return rows;
    }

    // --- УНИВЕРСАЛЬНОЕ СОХРАНЕНИЕ (ИСПРАВЛЕННОЕ) ---
    async savePermit() {
        // 1. Пытаемся получить ID текущего наряда из скрытого поля
        const permitId = document.getElementById('current_permit_id')?.value;
        const payload = {};
        
        // 2. Собираем данные из всех полей внутри .permit-wrapper
        const permitArea = document.querySelector('.permit-wrapper');
        const elements = permitArea.querySelectorAll('[id]');
        elements.forEach(el => {
            if (['measuresTable', 'permissionTable', 'dailyAdmissionTable', 'teamChangesTable', 'current_permit_id'].includes(el.id)) return;
            
            if (el.tagName === 'INPUT') {
                payload[el.id] = el.value;
            } else {
                payload[el.id] = el.innerText.trim();
            }
        });

        // 3. Собираем таблицы
        payload.measures = this.collectTable('measuresTable');
        payload.permissions = this.collectTable('permissionTable');
        payload.daily_admissions = this.collectTable('dailyAdmissionTable');
        payload.team_changes = this.collectTable('teamChangesTable');

        // ОПРЕДЕЛЯЕМ: создаем новый или обновляем старый
        const url = permitId ? `/api/permits/${permitId}` : '/api/permits';
        const method = permitId ? 'PUT' : 'POST';

        console.log(`Отправка данных (${method}) на адрес: ${url}`, payload);

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            if (result.success) {
                alert(permitId ? "Изменения сохранены!" : "Наряд создан!");
                window.location.href = '/view-permits';
            } else {
                alert("Ошибка: " + result.error);
            }
        } catch (e) {
            console.error("Ошибка сети:", e);
        }
    }
}

// ЗАПУСК ПРИ ЗАГРУЗКЕ
document.addEventListener('DOMContentLoaded', () => {
    window.visualBuilder = new PermitVisualBuilder();
});
// ============================================
// ПОИСК СОТРУДНИКОВ
// ============================================

class EmployeeSearch {
    constructor(fieldId) {
        this.fieldId = fieldId;
        this.searchInput = document.getElementById(`${fieldId}_search`);
        this.selectElement = document.getElementById(fieldId);
        this.resultsDiv = document.getElementById(`${fieldId}_results`);
        
        if (this.searchInput) {
            this.init();
        }
    }
    
    init() {
        // Обработчик ввода
        this.searchInput.addEventListener('input', this.handleInput.bind(this));
        
        // Закрытие при клике вне поля
        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) && !this.resultsDiv.contains(e.target)) {
                this.hideResults();
            }
        });
        
        // Обработка клавиш (навигация стрелками)
        this.searchInput.addEventListener('keydown', this.handleKeyDown.bind(this));
    }
    
    async handleInput(e) {
        const searchTerm = e.target.value.trim();
        
        if (searchTerm.length < 2) {
            this.hideResults();
            this.selectElement.value = '';
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE_URL}/api/employees?search=${encodeURIComponent(searchTerm)}`);
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки данных');
            }
            
            const employees = await response.json();
            this.displayResults(employees);
            
        } catch (error) {
            console.error('Ошибка поиска сотрудников:', error);
            this.showError('Ошибка загрузки списка сотрудников');
        }
    }
    
    displayResults(employees) {
        if (employees.length === 0) {
            this.resultsDiv.innerHTML = '<div class="search-result-item no-results">Сотрудники не найдены</div>';
            this.showResults();
            return;
        }
        
        this.resultsDiv.innerHTML = employees.map(emp => `
            <div class="search-result-item" 
                 data-id="${emp.id}" 
                 data-fio="${this.escapeHtml(emp.fio)}"
                 tabindex="0">
                <strong>${this.highlightMatch(emp.fio, this.searchInput.value)}</strong>
            </div>
        `).join('');
        
        // Добавляем обработчики кликов
        this.resultsDiv.querySelectorAll('.search-result-item').forEach(item => {
            if (!item.classList.contains('no-results')) {
                item.addEventListener('click', () => this.selectEmployee(item));
                item.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') this.selectEmployee(item);
                });
            }
        });
        
        this.showResults();
    }
    
    selectEmployee(item) {
        const empId = item.dataset.id;
        const empFio = item.dataset.fio;
        
        this.searchInput.value = empFio;
        this.selectElement.value = empId;
        this.hideResults();
        
        // Добавляем визуальную индикацию выбора
        this.searchInput.classList.add('selected');
        setTimeout(() => this.searchInput.classList.remove('selected'), 300);
    }
    
    handleKeyDown(e) {
        const items = this.resultsDiv.querySelectorAll('.search-result-item:not(.no-results)');
        
        if (items.length === 0) return;
        
        const currentIndex = Array.from(items).findIndex(item => item === document.activeElement);
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                if (currentIndex < items.length - 1) {
                    items[currentIndex + 1].focus();
                } else {
                    items[0].focus();
                }
                break;
            case 'ArrowUp':
                e.preventDefault();
                if (currentIndex > 0) {
                    items[currentIndex - 1].focus();
                } else {
                    items[items.length - 1].focus();
                }
                break;
            case 'Escape':
                this.hideResults();
                this.searchInput.focus();
                break;
        }
    }
    
    showResults() {
        this.resultsDiv.classList.add('active');
    }
    
    hideResults() {
        this.resultsDiv.classList.remove('active');
    }
    
    showError(message) {
        this.resultsDiv.innerHTML = `<div class="search-result-item error">${message}</div>`;
        this.showResults();
    }
    
    highlightMatch(text, query) {
        if (!query) return this.escapeHtml(text);
        
        const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
        return this.escapeHtml(text).replace(regex, '<mark>$1</mark>');
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    escapeRegex(text) {
        return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
}

// ============================================
// ФОРМА СОЗДАНИЯ НАРЯД-ДОПУСКА
// ============================================

class PermitForm {
    constructor(formId) {
        this.form = document.getElementById(formId);
        
        if (this.form) {
            this.init();
        }
    }
    
    init() {
        // Инициализация полей поиска сотрудников
        this.initEmployeeSearchFields();
        
        // Установка минимальных дат
        this.setMinDates();
        
        // Автоматическая генерация номера наряда
        this.generatePermitNumber();
        
        // Обработка отправки формы
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
        
        // Валидация дат
        this.setupDateValidation();
        
        // Автозаполнение времени
        this.setupTimeAutoFill();
    }
    
    initEmployeeSearchFields() {
        const searchFields = [
            'responsible_manager',
            'admitting_person',
            'work_producer',
            'team_member1',
            'team_member2'
        ];
        
        searchFields.forEach(fieldId => {
            new EmployeeSearch(fieldId);
        });
    }
    
    setMinDates() {
        const today = new Date().toISOString().split('T')[0];
        const startDateInput = document.getElementById('start_date');
        const endDateInput = document.getElementById('end_date');
        
        if (startDateInput) {
            startDateInput.min = today;
            startDateInput.value = today;
        }
        
        if (endDateInput) {
            endDateInput.min = today;
            endDateInput.value = today;
        }
    }
    
    generatePermitNumber() {
        const permitNumberInput = document.getElementById('permit_number');
        if (permitNumberInput && !permitNumberInput.value) {
            const now = new Date();
            const number = now.getFullYear().toString() +
                          (now.getMonth() + 1).toString().padStart(2, '0') +
                          now.getDate().toString().padStart(2, '0') +
                          now.getHours().toString().padStart(2, '0') +
                          now.getMinutes().toString().padStart(2, '0') +
                          now.getSeconds().toString().padStart(2, '0');
            permitNumberInput.value = number;
        }
    }
    
    setupDateValidation() {
        const startDateInput = document.getElementById('start_date');
        const endDateInput = document.getElementById('end_date');
        
        if (startDateInput && endDateInput) {
            startDateInput.addEventListener('change', () => {
                endDateInput.min = startDateInput.value;
                if (endDateInput.value && endDateInput.value < startDateInput.value) {
                    endDateInput.value = startDateInput.value;
                }
            });
        }
    }
    
    setupTimeAutoFill() {
        const startTimeInput = document.getElementById('start_time');
        const endTimeInput = document.getElementById('end_time');
        
        if (startTimeInput && !startTimeInput.value) {
            const now = new Date();
            startTimeInput.value = now.getHours().toString().padStart(2, '0') + ':' + 
                                   now.getMinutes().toString().padStart(2, '0');
        }
        
        if (endTimeInput && !endTimeInput.value) {
            const now = new Date();
            now.setHours(now.getHours() + 4); // +4 часа по умолчанию
            endTimeInput.value = now.getHours().toString().padStart(2, '0') + ':' + 
                                now.getMinutes().toString().padStart(2, '0');
        }
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        
        // Проверка валидности формы
        if (!this.validateForm()) {
            return;
        }
        
        // Показываем индикатор загрузки
        this.showLoading(true);
        
        // Собираем данные формы
        const formData = new FormData(this.form);
        const data = Object.fromEntries(formData.entries());
        
        // Преобразуем ID в числа
        ['work_type_id', 'location_id', 'responsible_manager_id', 
         'admitting_person_id', 'work_producer_id', 'team_member1_id', 'team_member2_id']
        .forEach(field => {
            if (data[field]) {
                data[field] = parseInt(data[field]);
            }
        });
        
        try {
            const response = await fetch(`${API_BASE_URL}/api/permits`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showSuccess(result.permit_number, result.permit_id);
            } else {
                throw new Error(result.error || 'Ошибка при создании наряда');
            }
            
        } catch (error) {
            console.error('Ошибка:', error);
            showNotification('Ошибка при создании наряда: ' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    validateForm() {
        // Проверка обязательных полей
        const requiredFields = this.form.querySelectorAll('[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.classList.add('error');
                isValid = false;
            } else {
                field.classList.remove('error');
            }
        });
        
        // Проверка что выбраны разные сотрудники для членов бригады
        const member1 = document.getElementById('team_member1').value;
        const member2 = document.getElementById('team_member2').value;
        
        if (member1 && member2 && member1 === member2) {
            showNotification('Члены бригады должны быть разными людьми', 'error');
            isValid = false;
        }
        
        if (!isValid) {
            showNotification('Заполните все обязательные поля', 'error');
        }
        
        return isValid;
    }
    
    showLoading(show) {
        const submitButton = this.form.querySelector('button[type="submit"]');
        if (submitButton) {
            if (show) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<span class="spinner"></span> Создание...';
            } else {
                submitButton.disabled = false;
                submitButton.innerHTML = 'Создать наряд-допуск';
            }
        }
    }
    
    showSuccess(permitNumber, permitId) {
        const modal = document.getElementById('successModal');
        const permitNumberSpan = document.getElementById('createdPermitNumber');
        
        if (permitNumberSpan) {
            permitNumberSpan.textContent = permitNumber;
        }
        
        if (modal) {
            modal.classList.add('active');
            
            // Добавляем ссылку на просмотр созданного наряда
            const modalActions = modal.querySelector('.modal-actions');
            if (modalActions && !modalActions.querySelector('.view-permit-btn')) {
                const viewButton = document.createElement('a');
                viewButton.href = `/view-permit/${permitId}`;
                viewButton.className = 'btn btn-secondary view-permit-btn';
                viewButton.textContent = 'Просмотреть наряд';
                modalActions.insertBefore(viewButton, modalActions.firstChild);
            }
        }
    }
}

// ============================================
// ПРОСМОТР СПИСКА НАРЯД-ДОПУСКОВ
// ============================================

class PermitsList {
    constructor() {
        this.table = document.getElementById('permitsTable');
        
        if (this.table) {
            this.init();
        }
    }
    
    async init() {
        await this.loadPermits();
        this.setupFilters();
        this.setupSearch();
    }
    
    async loadPermits() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/permits`);
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки данных');
            }
            
            const permits = await response.json();
            this.displayPermits(permits);
            
        } catch (error) {
            console.error('Ошибка загрузки наряд-допусков:', error);
            this.showError('Ошибка загрузки данных');
        }
    }
    
    displayPermits(permits) {
        const tbody = this.table.querySelector('tbody');
        
        if (permits.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; padding: 40px;">
                        <div style="color: #718096;">
                            <svg width="64" height="64" style="margin-bottom: 15px; opacity: 0.5;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M9 12h6M9 16h6M9 8h6M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" stroke-width="2"/>
                            </svg>
                            <p style="font-size: 1.1rem;">Наряд-допуски не найдены</p>
                            <a href="/create-permit" class="btn btn-primary" style="margin-top: 15px;">Создать первый наряд</a>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = permits.map(permit => `
            <tr data-permit-id="${permit.id}">
                <td><strong>${this.escapeHtml(permit.permit_number)}</strong></td>
                <td>${this.escapeHtml(permit.department || '-')}</td>
                <td>${this.escapeHtml(permit.work_name || '-')}</td>
                <td>${this.escapeHtml(permit.place_name || '-')}</td>
                <td>${formatDate(permit.start_date)}</td>
                <td>${this.escapeHtml(permit.responsible_manager || '-')}</td>
                <td>${this.getStatusBadge(permit.status)}</td>
                <td>
                    <div style="display: flex; gap: 5px;">
                        <a href="/view-permit/${permit.id}" class="btn btn-small btn-secondary" title="Просмотр">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke-width="2"/>
                                <circle cx="12" cy="12" r="3" stroke-width="2"/>
                            </svg>
                        </a>
                        <button onclick="permitsList.downloadPermit(${permit.id})" class="btn btn-small btn-primary" title="Скачать PDF">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke-width="2" stroke-linecap="round"/>
                            </svg>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
        
        // Анимация появления строк
        this.animateRows();
    }
    
    animateRows() {
        const rows = this.table.querySelectorAll('tbody tr');
        rows.forEach((row, index) => {
            row.style.opacity = '0';
            row.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                row.style.transition = 'all 0.3s ease';
                row.style.opacity = '1';
                row.style.transform = 'translateY(0)';
            }, index * 50);
        });
    }
    
    getStatusBadge(status) {
        const statuses = {
            'created': { text: 'Создан', class: 'status-created' },
            'signed': { text: 'Подписан', class: 'status-signed' },
            'in_progress': { text: 'В работе', class: 'status-in-progress' },
            'completed': { text: 'Завершен', class: 'status-completed' },
            'cancelled': { text: 'Отменен', class: 'status-cancelled' }
        };
        
        const statusInfo = statuses[status] || { text: status, class: 'status-created' };
        
        return `<span class="status-badge ${statusInfo.class}">${statusInfo.text}</span>`;
    }
    
    setupFilters() {
        // Здесь можно добавить фильтры по статусу, дате и т.д.
        // Пока оставим заглушку
    }
    
    setupSearch() {
        const searchInput = document.getElementById('permitSearch');
        
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const searchTerm = e.target.value.toLowerCase();
                const rows = this.table.querySelectorAll('tbody tr');
                
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(searchTerm) ? '' : 'none';
                });
            });
        }
    }
    
    async downloadPermit(permitId) {
        try {
            showNotification('Подготовка документа...', 'info');
            
            const response = await fetch(`${API_BASE_URL}/api/permits/${permitId}/download`);
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки документа');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `permit_${permitId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showNotification('Документ успешно загружен', 'success');
            
        } catch (error) {
            console.error('Ошибка загрузки документа:', error);
            showNotification('Ошибка при загрузке документа', 'error');
        }
    }
    
    showError(message) {
        const tbody = this.table.querySelector('tbody');
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px; color: #f56565;">
                    ${message}
                </td>
            </tr>
        `;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}


// ============================================
// ПРОСМОТР ДЕТАЛЬНОЙ ИНФОРМАЦИИ О НАРЯДЕ
// ============================================

class PermitDetails {
    constructor(permitId) {
        this.permitId = permitId;
        
        if (this.permitId) {
            this.init();
        }
    }
    
    async init() {
        await this.loadPermitDetails();
        await this.loadInspectionReports();
        this.setupSignatureCanvas();
    }
    
    async loadPermitDetails() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/permits/${this.permitId}`);
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки данных');
            }
            
            const permit = await response.json();
            this.displayPermitDetails(permit);
            
        } catch (error) {
            console.error('Ошибка загрузки деталей наряда:', error);
            showNotification('Ошибка загрузки данных', 'error');
        }
    }
    
    displayPermitDetails(permit) {
        // Здесь будет отображение детальной информации
        // Реализация зависит от структуры HTML шаблона
    }
    
    async loadInspectionReports() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/permits/${this.permitId}/reports`);
            
            if (!response.ok) {
                throw new Error('Ошибка загрузки отчетов');
            }
            
            const reports = await response.json();
            this.displayInspectionReports(reports);
            
        } catch (error) {
            console.error('Ошибка загрузки отчетов:', error);
        }
    }
    
    displayInspectionReports(reports) {
        const container = document.getElementById('inspectionReports');
        
        if (!container) return;
        
        if (reports.length === 0) {
            container.innerHTML = '<p class="no-data">Отчеты об осмотре отсутствуют</p>';
            return;
        }
        
        container.innerHTML = reports.map(report => `
            <div class="report-card">
                <div class="report-header">
                    <strong>${this.escapeHtml(report.inspector_name)}</strong>
                    <span class="report-date">${formatDate(report.visit_datetime)}</span>
                </div>
                <div class="report-content">
                    <p><strong>Опора:</strong> ${this.escapeHtml(report.pole_number || '-')}</p>
                    <p><strong>Состояние изоляторов:</strong> ${this.escapeHtml(report.insulator_condition || '-')}</p>
                    <p><strong>Растительность:</strong> ${this.escapeHtml(report.vegetation_status || '-')}</p>
                    <p><strong>Состояние проводов:</strong> ${this.escapeHtml(report.wire_condition || '-')}</p>
                    ${report.issues_found ? `<p class="issues"><strong>Обнаружено:</strong> ${this.escapeHtml(report.issues_found)}</p>` : ''}
                </div>
                ${report.photos ? this.displayPhotos(report.photos) : ''}
            </div>
        `).join('');
    }
    
    displayPhotos(photosJson) {
        try {
            const photos = JSON.parse(photosJson);
            
            if (!Array.isArray(photos) || photos.length === 0) return '';
            
            return `
                <div class="report-photos">
                    ${photos.map(photo => `
                        <img src="${photo}" alt="Фото осмотра" onclick="openPhotoModal('${photo}')">
                    `).join('')}
                </div>
            `;
        } catch (e) {
            return '';
        }
    }
    
    setupSignatureCanvas() {
        const canvas = document.getElementById('signatureCanvas');
        
        if (!canvas) return;
        
        const signaturePad = new SignaturePad(canvas);
        
        // Кнопка очистки
        const clearButton = document.getElementById('clearSignature');
        if (clearButton) {
            clearButton.addEventListener('click', () => signaturePad.clear());
        }
        
        // Кнопка сохранения
        const saveButton = document.getElementById('saveSignature');
        if (saveButton) {
            saveButton.addEventListener('click', async () => {
                if (signaturePad.isEmpty()) {
                    showNotification('Пожалуйста, поставьте подпись', 'error');
                    return;
                }
                
                const signatureData = signaturePad.toDataURL();
                await this.saveSignature(signatureData);
            });
        }
    }
    
    async saveSignature(signatureData) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/permits/${this.permitId}/signatures`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    employee_id: getCurrentUserId(), // Нужно реализовать
                    role: 'work_producer',
                    signature_image: signatureData
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                showNotification('Подпись успешно сохранена', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                throw new Error(result.error || 'Ошибка сохранения подписи');
            }
            
        } catch (error) {
            console.error('Ошибка сохранения подписи:', error);
            showNotification('Ошибка при сохранении подписи', 'error');
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ============================================
// МОДАЛЬНЫЕ ОКНА
// ============================================

function openPhotoModal(photoUrl) {
    const modal = document.createElement('div');
    modal.className = 'photo-modal';
    modal.innerHTML = `
        <div class="photo-modal-content">
            <button class="photo-modal-close" onclick="this.parentElement.parentElement.remove()">×</button>
            <img src="${photoUrl}" alt="Фото">
        </div>
    `;
    
    document.body.appendChild(modal);
    
    setTimeout(() => modal.classList.add('active'), 10);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// ============================================
// ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ СТРАНИЦЫ
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    // Если на странице есть элемент визуального конструктора
    if (document.querySelector('.paper-sheet')) {
        window.visualBuilder = new PermitVisualBuilder();
    }

    // Твоя старая инициализация
    if (document.getElementById('permitForm')) {
        new PermitForm('permitForm');
    }
    
    if (document.getElementById('permitsTable')) {
        window.permitsList = new PermitsList();
    }
    
    const permitIdElement = document.getElementById('permitId');
    if (permitIdElement) {
        new PermitDetails(parseInt(permitIdElement.value));
    }
});
// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================

function getCurrentUserId() {
    // Здесь должна быть логика получения ID текущего пользователя
    // Например, из session storage или cookie
    return localStorage.getItem('currentUserId') || null;
}

// Экспорт для использования в других скриптах
window.EmployeeSearch = EmployeeSearch;
window.PermitForm = PermitForm;
window.PermitsList = PermitsList;
window.PermitDetails = PermitDetails;