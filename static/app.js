/**
 * AItonomo - Core Application Javascript (Updated & Consolidated)
 */

const AppState = {
    userId: null,
    dni: null,
    apiKey: null,
    currentView: 'dashboard-view',
    extractedData: null,
    activeFile: null,
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
    period: 'anual',
    periodOffset: 0,
    // Calendar state
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth() + 1,
    showInvoiceDueDates: true,
    calSelectedDate: null
};

const Utils = {
    showToast: (message, type = 'info') => {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        setTimeout(() => { toast.classList.remove('show'); }, 3000);
    },
    formatCurrency: (value) => {
        return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(value || 0);
    },
    formatDate: (dateStr) => {
        if (!dateStr) return '--';
        return new Date(dateStr).toLocaleDateString();
    },
    getStatusBadge: (status) => {
        const s = (status || 'Pendiente').toLowerCase();
        let cls = 'badge-pending';
        if (s === 'enviada') cls = 'badge-pending';
        if (s === 'pagada') cls = 'badge-paid';
        if (s === 'moroso') cls = 'badge-overdue';
        if (s === 'active') cls = 'badge-active';
        return `<span class="badge ${cls}">${status}</span>`;
    }
};

const API_BASE_URL = "https://api-backend-4nrtuy3yca-no.a.run.app";

const API = {
    request: async (endpoint, options = {}) => {
        try {
            const finalUrl = API_BASE_URL + endpoint;
            const res = await fetch(finalUrl, options);
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                if (res.status === 422 && Array.isArray(errorData.detail)) {
                    const messages = errorData.detail.map(err => `${err.loc ? err.loc[err.loc.length - 1] : 'Field'}: ${err.msg}`);
                    throw new Error(messages.join(' | '));
                }
                throw new Error(errorData.detail || `HTTP Error ${res.status}`);
            }
            if (options.responseType === 'blob') return await res.blob();
            return await res.json();
        } catch (error) {
            Utils.showToast(error.message, 'error');
            throw error;
        }
    }
};

const UI = {
    init: () => {
        document.getElementById('current-date').textContent = new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

        // Auth & Nav
        document.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.add('hidden'));
            e.target.classList.add('active');
            document.getElementById(e.target.dataset.target).classList.remove('hidden');
        }));

        document.querySelectorAll('.nav-item').forEach(item => item.addEventListener('click', (e) => {
            appState.navigate(e.currentTarget.dataset.view);
        }));

        document.getElementById('login-form').addEventListener('submit', appLogic.handleLogin);
        document.getElementById('register-form').addEventListener('submit', appLogic.handleRegister);
        document.getElementById('btn-logout').addEventListener('click', appLogic.handleLogout);
        document.getElementById('add-client-form').addEventListener('submit', appLogic.addClient);

        // --- Invoicing Upload ---
        const fileInput = document.getElementById('file-upload');
        const invoiceDropZone = document.getElementById('drop-zone');
        if (invoiceDropZone) {
            invoiceDropZone.addEventListener('click', (e) => { if (e.target !== fileInput) fileInput.click(); });
            invoiceDropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                if (e.dataTransfer.files.length) appLogic.handleFileSelect(e.dataTransfer.files[0], 'invoices');
            });
        }
        fileInput.addEventListener('change', (e) => appLogic.handleFileSelect(e.target.files[0], 'invoices'));
        document.getElementById('btn-remove-file').addEventListener('click', () => appLogic.clearFile('invoices'));
        document.getElementById('btn-process-ai').addEventListener('click', () => appLogic.processDocument('invoices'));
        document.getElementById('btn-save-db').addEventListener('click', appLogic.saveExtractedInvoice);
        document.getElementById('btn-gen-pdf').addEventListener('click', appLogic.generatePDF);

        // --- Budgeting Upload & Voice (REFIXED) ---
        const fileInputBudgets = document.getElementById('file-upload-budgets');
        const budgetDropZone = document.getElementById('drop-zone-budgets');
        if (budgetDropZone) {
            budgetDropZone.addEventListener('click', (e) => { if (e.target !== fileInputBudgets) fileInputBudgets.click(); });
            budgetDropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                if (e.dataTransfer.files.length) appLogic.handleFileSelect(e.dataTransfer.files[0], 'budgets');
            });
        }
        if (fileInputBudgets) {
            fileInputBudgets.addEventListener('change', (e) => appLogic.handleFileSelect(e.target.files[0], 'budgets'));
            document.getElementById('btn-remove-file-budgets').addEventListener('click', () => appLogic.clearFile('budgets'));
            document.getElementById('btn-process-ai-budgets').addEventListener('click', () => appLogic.processDocument('budgets'));
            document.getElementById('btn-save-db-budgets').addEventListener('click', () => appLogic.saveExtractedBudget(false));
            document.getElementById('btn-gen-pdf-budgets').addEventListener('click', appLogic.generateBudgetPDF);
        }

        // Voice Listeners (Unified)
        document.getElementById('btn-start-record').addEventListener('click', () => appLogic.startRecording(''));
        document.getElementById('btn-stop-record').addEventListener('click', () => appLogic.stopRecording(''));
        
        const bStart = document.getElementById('btn-start-record-budgets');
        const bStop = document.getElementById('btn-stop-record-budgets');
        if (bStart) bStart.addEventListener('click', () => appLogic.startRecording('-budgets'));
        if (bStop) bStop.addEventListener('click', () => appLogic.stopRecording('-budgets'));

        // CRM & Catalog
        document.getElementById('add-catalog-form').addEventListener('submit', appLogic.addProduct);
        document.getElementById('btn-add-catalog-item').addEventListener('click', () => appLogic.addCatalogItemToInvoice(''));
        const bCatAdd = document.getElementById('btn-add-catalog-item-budgets');
        if (bCatAdd) bCatAdd.addEventListener('click', () => appLogic.addCatalogItemToInvoice('-budgets'));

        // Expenses
        document.getElementById('expense-form').addEventListener('submit', appLogic.saveExpense);

        // Chat & Profile
        const chatForm = document.getElementById('chat-form');
        if (chatForm) chatForm.addEventListener('submit', appLogic.handleChatSubmit);
        const sidebarBtn = document.getElementById('sidebar-user-btn');
        if (sidebarBtn) sidebarBtn.addEventListener('click', appLogic.loadProfile);
        const profileForm = document.getElementById('profile-form');
        if (profileForm) profileForm.addEventListener('submit', appLogic.saveProfile);

        // Session Check
        const storedUser = sessionStorage.getItem('aura_uid');
        if (storedUser) {
            AppState.userId = storedUser;
            AppState.dni = sessionStorage.getItem('aura_dni');
            appLogic.enterApp();
        } else {
            document.getElementById('landing-view')?.classList.remove('hidden');
        }
    },

    switchMainView: (viewId) => {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        const activeNav = document.querySelector(`.nav-item[data-view="${viewId}"]`);
        if (activeNav) {
            activeNav.classList.add('active');
            let titles = { 'dashboard-view': 'Resumen Financiero', 'invoicing-view': 'Facturación Inteligente', 'crm-view': 'CRM y Clientes', 'catalog-view': 'Catálogo', 'expenses-view': 'Gastos', 'consultant-view': 'Consultor IA', 'calendar-view': 'Calendario Fiscal' };
            document.getElementById('page-title').textContent = titles[viewId] || 'AItonomo';
        }
        document.querySelectorAll('main.view').forEach(v => v.id !== 'auth-view' ? v.classList.add('hidden') : null);
        document.getElementById(viewId).classList.remove('hidden');
    }
};

const appLogic = {
    enterApp: () => {
        document.getElementById('auth-view').classList.add('hidden');
        document.getElementById('main-layout').classList.remove('hidden');
        document.getElementById('sidebar-user-id').textContent = `ID: ${AppState.dni}`;
        appLogic.initProfileState();
        appLogic.loadExpenses();
        appState.navigate('dashboard-view');
    },

    handleLogin: async (e) => {
        e.preventDefault();
        const dni = document.getElementById('login-dni').value;
        const pwd = document.getElementById('login-pwd').value;
        const res = await API.request('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dni, password: pwd })
        });
        if (res.success) {
            AppState.userId = res.user_id;
            AppState.dni = res.dni;
            sessionStorage.setItem('aura_uid', res.user_id);
            sessionStorage.setItem('aura_dni', res.dni);
            appLogic.enterApp();
        }
    },

    // --- Core Recording Logic (Unified for Budgets & Invoices) ---
    startRecording: async (sfp = '') => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            AppState.mediaRecorder = new MediaRecorder(stream);
            AppState.audioChunks = [];

            AppState.mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) AppState.audioChunks.push(e.data); };

            AppState.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(AppState.audioChunks, { type: 'audio/webm' });
                const file = new File([audioBlob], `voice_note_${Date.now()}.webm`, { type: "audio/webm" });
                appLogic.handleFileSelect(file, sfp === '-budgets' ? 'budgets' : 'invoices');

                document.getElementById(`btn-start-record${sfp}`).classList.remove('hidden');
                document.getElementById(`btn-stop-record${sfp}`).classList.add('hidden');
                const statusBox = document.getElementById(`recording-status${sfp}`);
                if (statusBox) {
                    statusBox.textContent = 'Audio Capturado. Listo para procesar.';
                    statusBox.classList.remove('text-red', 'font-bold', 'blink');
                }
                stream.getTracks().forEach(track => track.stop());
            };

            AppState.mediaRecorder.start();
            AppState.isRecording = true;
            document.getElementById(`btn-start-record${sfp}`).classList.add('hidden');
            document.getElementById(`btn-stop-record${sfp}`).classList.remove('hidden');
            const statusBox = document.getElementById(`recording-status${sfp}`);
            if (statusBox) {
                statusBox.textContent = 'Grabación activa...';
                statusBox.classList.add('text-red', 'font-bold', 'blink');
            }
        } catch (err) {
            Utils.showToast('Error al acceder al micrófono.', 'error');
        }
    },

    stopRecording: (sfp = '') => {
        if (AppState.mediaRecorder && AppState.mediaRecorder.state !== 'inactive') {
            AppState.mediaRecorder.stop();
            AppState.isRecording = false;
        }
    },

    handleFileSelect: (file, type = 'invoices') => {
        if (!file) return;
        AppState.activeFile = file;
        const sfp = type === 'budgets' ? '-budgets' : '';
        document.getElementById(`drop-zone${sfp}`).classList.add('hidden');
        document.getElementById(`file-preview-area${sfp}`).classList.remove('hidden');
        document.getElementById(`preview-filename${sfp}`).textContent = file.name;
    },

    clearFile: (type = 'invoices') => {
        AppState.activeFile = null;
        const sfp = type === 'budgets' ? '-budgets' : '';
        document.getElementById(`drop-zone${sfp}`).classList.remove('hidden');
        document.getElementById(`file-preview-area${sfp}`).classList.add('hidden');
        const input = document.getElementById(type === 'budgets' ? 'file-upload-budgets' : 'file-upload');
        if (input) input.value = '';
    },

    processDocument: async (type = 'invoices') => {
        const sfp = type === 'budgets' ? '-budgets' : '';
        if (!AppState.activeFile) return Utils.showToast('Sube un archivo o graba audio.', 'error');

        const btn = document.getElementById(`btn-process-ai${sfp}`);
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analizando...';
        btn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('file', AppState.activeFile);
            formData.append('user_id', AppState.userId);

            const data = await API.request('/api/process_document', { method: 'POST', body: formData });
            AppState.extractedData = data;

            // Load Clients for Select
            const select = document.getElementById(`ext-client${sfp}`);
            select.innerHTML = '<option value="">-- Seleccionar Cliente --</option>';
            const clients = await API.request(`/api/clients/${AppState.userId}`);
            clients.forEach(c => {
                const isMatch = (c.name.toLowerCase() === (data.client_name || '').toLowerCase() || c.nif_cif === data.client_nif);
                select.innerHTML += `<option value="${c.id}" ${isMatch ? 'selected' : ''}>${c.name} (${c.nif_cif})</option>`;
                if (isMatch) AppState.extractedData.client_id = c.id;
            });

            select.addEventListener('change', (e) => {
                AppState.extractedData.client_id = e.target.value;
                AppState.extractedData.client_name = e.target.options[e.target.selectedIndex].text;
            });

            document.getElementById(`ext-${type === 'budgets' ? 'budget' : 'invoice'}-num`).value = data.invoice_number || 'BORRADOR';
            document.getElementById(`ext-date${sfp}`).value = data.date || new Date().toISOString().split('T')[0];

            appLogic.renderExtractedItems(sfp);
            document.getElementById(`extracted-data-placeholder${sfp}`).classList.add('hidden');
            document.getElementById(`extracted-form${sfp}`).classList.remove('hidden');
            Utils.showToast('IA: Datos extraídos', 'success');
        } finally {
            btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Procesar con IA';
            btn.disabled = false;
        }
    },

    renderExtractedItems: (sfp = '') => {
        const tbody = document.querySelector(`#ext-items-table${sfp} tbody`);
        if (!tbody) return;
        tbody.innerHTML = '';
        let total = 0;
        const items = AppState.extractedData?.items || [];
        
        items.forEach((item, index) => {
            const qty = parseFloat(item.cantidad || 1);
            const price = parseFloat(item.precio_unitario || 0);
            const sub = qty * price;
            total += sub;
            tbody.innerHTML += `<tr><td>${item.concepto || 'Item'}</td><td class="text-center">${qty}</td><td class="text-right">${Utils.formatCurrency(price)}</td><td class="text-right">${Utils.formatCurrency(sub)}</td><td class="text-center"><button class="btn-icon text-red" onclick="appLogic.removeExtractedItem(${index}, '${sfp}')"><i class="fa-solid fa-trash"></i></button></td></tr>`;
        });

        const finalTotal = total * 1.21; // Simple IVA mock
        document.getElementById(`ext-amount${sfp}`).value = finalTotal.toFixed(2);
    },

    removeExtractedItem: (index, sfp = '') => {
        AppState.extractedData.items.splice(index, 1);
        appLogic.renderExtractedItems(sfp);
    },

    addCatalogItemToInvoice: (sfp = '') => {
        const select = document.getElementById(`ext-catalog-select${sfp}`);
        if (!select || !select.value) return;
        const item = JSON.parse(select.value);
        if (!AppState.extractedData) AppState.extractedData = { items: [] };
        if (!AppState.extractedData.items) AppState.extractedData.items = [];
        AppState.extractedData.items.push({ concepto: item.desc, cantidad: 1, precio_unitario: item.price });
        appLogic.renderExtractedItems(sfp);
        select.value = "";
    },

    // --- Catalog ---
    loadCatalog: async () => {
        const products = await API.request(`/api/products/${AppState.userId}`);
        AppState.catalogProducts = products;
        const tbody = document.querySelector('#catalog-table tbody');
        if (tbody) {
            tbody.innerHTML = '';
            products.forEach(p => {
                tbody.innerHTML += `<tr><td>${p.nombre}</td><td>${p.tipo}</td><td>${Utils.formatCurrency(p.precio_unitario)}</td><td><button class="btn-icon" onclick="appLogic.editProduct('${p.id}')"><i class="fa-solid fa-pencil"></i></button></td></tr>`;
            });
        }
        ['', '-budgets'].forEach(sfx => {
            const el = document.getElementById(`ext-catalog-select${sfx}`);
            if (el) {
                el.innerHTML = '<option value="">Seleccionar del catálogo...</option>';
                products.forEach(p => el.innerHTML += `<option value='${JSON.stringify({ desc: p.nombre, price: p.precio_unitario })}'>${p.nombre}</option>`);
            }
        });
    },

    loadDashboard: async () => {
        const params = new URLSearchParams({ period: AppState.period, offset: AppState.periodOffset });
        const data = await API.request(`/api/dashboard/${AppState.userId}?${params}`);
        document.getElementById('dash-total-revenue').textContent = Utils.formatCurrency(data.metrics.total_revenue);
        document.getElementById('dash-net-balance').textContent = Utils.formatCurrency(data.metrics.net_balance_after_taxes);
    },

    handleLogout: () => { sessionStorage.clear(); location.reload(); }
};

const appState = {
    navigate: (viewId) => {
        AppState.currentView = viewId;
        UI.switchMainView(viewId);
        if (viewId === 'dashboard-view') appLogic.loadDashboard();
        if (viewId === 'catalog-view' || viewId === 'invoicing-view' || viewId === 'budgeting-view') appLogic.loadCatalog();
        if (viewId === 'crm-view') appLogic.loadCRM();
    }
};

window.appLogic = appLogic;
document.addEventListener('DOMContentLoaded', UI.init);