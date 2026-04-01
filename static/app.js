/**
 * AItonomo - Core Application Javascript
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
    calMonth: new Date().getMonth() + 1, // 1-based
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
        // Enviada has same color logic as Pendiente for now
        if (s === 'enviada') cls = 'badge-pending';
        if (s === 'pagada') cls = 'badge-paid';
        if (s === 'moroso') cls = 'badge-overdue';
        if (s === 'active') cls = 'badge-active';
        return `<span class="badge ${cls}">${status}</span>`;
    }
};

const API = {
    request: async (endpoint, options = {}) => {
        try {
            const res = await fetch(endpoint, options);
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));

                // Handle Pydantic 422 Validation Arrays
                if (res.status === 422 && Array.isArray(errorData.detail)) {
                    const messages = errorData.detail.map(err => {
                        const field = err.loc ? err.loc[err.loc.length - 1] : 'Field';
                        return `${field}: ${err.msg}`;
                    });
                    throw new Error(messages.join(' | '));
                }

                throw new Error(errorData.detail || `HTTP Error ${res.status}`);
            }
            // Hande Blob vs JSON
            if (options.responseType === 'blob') {
                return await res.blob();
            }
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

        // Auth Tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.auth-form').forEach(f => f.classList.add('hidden'));
                e.target.classList.add('active');
                document.getElementById(e.target.dataset.target).classList.remove('hidden');
            });
        });

        // Sidebar Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const viewId = e.currentTarget.dataset.view;
                appState.navigate(viewId);
            });
        });

        // Auth Forms
        document.getElementById('login-form').addEventListener('submit', appLogic.handleLogin);
        document.getElementById('register-form').addEventListener('submit', appLogic.handleRegister);
        document.getElementById('btn-logout').addEventListener('click', appLogic.handleLogout);



        // CRM
        document.getElementById('add-client-form').addEventListener('submit', appLogic.addClient);

        // Invoicing Upload Area
        const fileInput = document.getElementById('file-upload');
        const invoiceDropZone = document.getElementById('drop-zone');
        if (invoiceDropZone) {
            invoiceDropZone.addEventListener('click', (e) => { if (e.target !== fileInput && !e.target.closest('button')) fileInput.click(); });
            invoiceDropZone.addEventListener('dragover', (e) => { e.preventDefault(); invoiceDropZone.classList.add('dragover'); });
            invoiceDropZone.addEventListener('dragleave', () => invoiceDropZone.classList.remove('dragover'));
            invoiceDropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                invoiceDropZone.classList.remove('dragover');
                if (e.dataTransfer.files.length) appLogic.handleFileSelect(e.dataTransfer.files[0]);
            });
        }
        fileInput.addEventListener('change', (e) => appLogic.handleFileSelect(e.target.files[0]));
        document.getElementById('btn-remove-file').addEventListener('click', appLogic.clearFile);
        document.getElementById('btn-process-ai').addEventListener('click', appLogic.processDocument);

        // Invoice Actions
        document.getElementById('btn-save-db').addEventListener('click', appLogic.saveExtractedInvoice);
        document.getElementById('btn-gen-pdf').addEventListener('click', appLogic.generatePDF);

        // Catalog
        document.getElementById('add-catalog-form').addEventListener('submit', appLogic.addProduct);
        document.getElementById('btn-add-catalog-item').addEventListener('click', appLogic.addCatalogItemToInvoice);

        // Expenses
        const expenseInput = document.getElementById('file-input-expense');
        const expenseDropZone = document.getElementById('drop-zone-expense');
        if (expenseDropZone) {
            expenseDropZone.addEventListener('click', (e) => { if (e.target !== expenseInput && !e.target.closest('button')) expenseInput.click(); });
            expenseDropZone.addEventListener('dragover', (e) => { e.preventDefault(); expenseDropZone.classList.add('dragover'); });
            expenseDropZone.addEventListener('dragleave', () => expenseDropZone.classList.remove('dragover'));
            expenseDropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                expenseDropZone.classList.remove('dragover');
                if (e.dataTransfer.files.length) appLogic.processExpenseDocument(e.dataTransfer.files[0]);
            });
        }
        expenseInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                appLogic.processExpenseDocument(e.target.files[0]);
            }
        });
        document.getElementById('expense-form').addEventListener('submit', appLogic.saveExpense);

        // Voice Recording
        document.getElementById('btn-start-record').addEventListener('click', appLogic.startRecording);
        document.getElementById('btn-stop-record').addEventListener('click', appLogic.stopRecording);

        // CRM Voice
        const crmStartBtn = document.getElementById('btn-crm-start-record');
        if (crmStartBtn) crmStartBtn.addEventListener('click', appLogic.startCrmRecording);
        const crmStopBtn = document.getElementById('btn-crm-stop-record');
        if (crmStopBtn) crmStopBtn.addEventListener('click', appLogic.stopCrmRecording);

        // AI Consultant
        const chatForm = document.getElementById('chat-form');
        if (chatForm) chatForm.addEventListener('submit', appLogic.handleChatSubmit);

        // Profile Edition
        const sidebarBtn = document.getElementById('sidebar-user-btn');
        if (sidebarBtn) sidebarBtn.addEventListener('click', appLogic.loadProfile);
        const profileForm = document.getElementById('profile-form');
        if (profileForm) profileForm.addEventListener('submit', appLogic.saveProfile);

        // Check session
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
        // Update nav UI
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        const activeNav = document.querySelector(`.nav-item[data-view="${viewId}"]`);
        if (activeNav) {
            activeNav.classList.add('active');
            let titles = {
                'dashboard-view': 'Resumen Financiero',
                'invoicing-view': 'Facturación Inteligente',
                'crm-view': 'CRM y Clientes',
                'catalog-view': 'Productos y Servicios',
                'expenses-view': 'Gastos',
                'consultant-view': 'Consultor Financiero IA',
                'taxes-view': 'Impuestos y Modelos',
                'calendar-view': 'Calendario Fiscal'
            };
            document.getElementById('page-title').textContent = titles[viewId] || 'AItonomo';
        }

        // Hide all views, show target
        document.querySelectorAll('main.view').forEach(v => {
            if (v.id !== 'auth-view') v.classList.add('hidden');
        });
        document.getElementById(viewId).classList.remove('hidden');
    }
};

const appLogic = {
    showAuth: (targetFormId) => {
        document.getElementById('landing-view').classList.add('hidden');
        document.getElementById('auth-view').classList.remove('hidden');
        if (targetFormId) {
            document.querySelector(`.tab-btn[data-target="${targetFormId}"]`)?.click();
        }
    },
    hideAuth: () => {
        document.getElementById('auth-view').classList.add('hidden');
        document.getElementById('landing-view').classList.remove('hidden');
    },
    handleLogin: async (e) => {
        e.preventDefault();
        const dni = document.getElementById('login-dni').value;
        const pwd = document.getElementById('login-pwd').value;
        const btn = e.target.querySelector('button');

        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Authenticating...';
        btn.disabled = true;

        try {
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
                Utils.showToast('Inicio de sesión exitoso', 'success');
            }
        } finally {
            btn.innerHTML = 'Acceder al Sistema';
            btn.disabled = false;
        }
    },

    handleRegister: async (e) => {
        e.preventDefault();

        const data = {
            nombre: document.getElementById('reg-nombre').value,
            apellidos: document.getElementById('reg-apellidos').value,
            nif_cif: document.getElementById('reg-dni').value,
            email: document.getElementById('reg-email').value,
            telefono: document.getElementById('reg-tel').value,
            domicilio: document.getElementById('reg-dir').value,
            poblacion: document.getElementById('reg-poblacion').value || "",
            provincia: document.getElementById('reg-provincia').value || "",
            codigo_postal: document.getElementById('reg-cp').value || "",
            cnae: document.getElementById('reg-cnae').value || "",
            password: document.getElementById('reg-pwd').value
        };

        const btn = e.target.querySelector('button');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Creating...';
        btn.disabled = true;

        try {
            const res = await API.request('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (res.success) {
                Utils.showToast('¡Cuenta creada! Por favor, inicie sesión.', 'success');
                document.querySelector('.tab-btn[data-target="login-form"]').click();
            }
        } finally {
            btn.innerHTML = 'Crear Cuenta';
            btn.disabled = false;
        }
    },

    handleLogout: () => {
        sessionStorage.clear();
        AppState.userId = null;
        document.getElementById('main-layout').classList.add('hidden');
        document.getElementById('landing-view')?.classList.remove('hidden');
    },

    enterApp: () => {
        document.getElementById('auth-view').classList.add('hidden');
        document.getElementById('main-layout').classList.remove('hidden');
        document.getElementById('sidebar-user-id').textContent = `ID: ${AppState.dni}`;
        appLogic.initProfileState();
        appLogic.loadExpenses();
        appState.navigate('dashboard-view');
    },



    loadDashboard: async () => {
        try {
            const params = new URLSearchParams({
                period: AppState.period,
                offset: AppState.periodOffset
            });
            const data = await API.request(`/api/dashboard/${AppState.userId}?${params}`);

            // Update period selector UI
            const label = data.period?.label || '';
            document.querySelectorAll('.period-label-display').forEach(el => el.textContent = label);
            // Enable/disable the "next period" buttons based on whether a newer period exists
            document.querySelectorAll('.btn-period-next').forEach(btn => {
                btn.disabled = !data.period?.has_next;
            });
            document.querySelectorAll('.period-tab').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.period === AppState.period);
            });

            // Metrics
            document.getElementById('dash-total-revenue').textContent = Utils.formatCurrency(data.metrics.total_revenue);
            document.getElementById('dash-pending').textContent = Utils.formatCurrency(data.metrics.pending_revenue);
            document.getElementById('dash-overdue').textContent = Utils.formatCurrency(data.metrics.overdue_revenue);
            // New Expense Metrics
            document.getElementById('dash-expenses').textContent = Utils.formatCurrency(data.metrics.total_expenses || 0);
            document.getElementById('dash-net-balance').textContent = Utils.formatCurrency(data.metrics.net_balance_after_taxes || data.metrics.net_balance || 0);
            document.getElementById('dash-clients').textContent = document.querySelectorAll('#crm-clients-table tbody tr').length || 0; // Fallback sync

            // New Taxes Metrics population
            if (document.getElementById('tax-iva-rep')) {
                document.getElementById('tax-iva-rep').textContent = Utils.formatCurrency(data.metrics.iva_repercutido || 0);
                document.getElementById('tax-iva-sop').textContent = Utils.formatCurrency(data.metrics.iva_soportado || 0);
                document.getElementById('tax-iva-total').textContent = Utils.formatCurrency(data.metrics.iva_a_pagar || 0);

                document.getElementById('tax-base-ingresos').textContent = Utils.formatCurrency(data.metrics.base_imponible_ingresos || 0);
                document.getElementById('tax-base-gastos').textContent = Utils.formatCurrency(data.metrics.base_imponible_gastos || 0);
                document.getElementById('tax-net-before').textContent = Utils.formatCurrency(data.metrics.net_balance || 0);
                document.getElementById('tax-irpf-total').textContent = Utils.formatCurrency(data.metrics.irpf_estimado || 0);

                if (document.getElementById('display-irpf-rate-title')) {
                    const ratePerc = Math.round((data.metrics.irpf_rate || 0.20) * 100);
                    document.getElementById('display-irpf-rate-title').textContent = ratePerc;

                    const inputEl = document.getElementById('irpf-rate-input');
                    if (inputEl) inputEl.value = ratePerc;
                }
            }

            // Cuota de Autonomo (Seguridad Social)
            if (document.getElementById('tax-ss-cuota')) {
                document.getElementById('tax-ss-rendimiento').textContent = Utils.formatCurrency(data.metrics.rendimiento_neto_mensual || 0);
                document.getElementById('tax-ss-tramo').textContent = data.metrics.tramo_ss || '–';
                document.getElementById('tax-ss-base').textContent = Utils.formatCurrency(data.metrics.base_cotizacion_ss || 0);
                document.getElementById('tax-ss-cuota').textContent = Utils.formatCurrency(data.metrics.cuota_autonomo || 0);
            }

            const deltaEl = document.getElementById('dash-delta-revenue');
            deltaEl.textContent = data.metrics.delta_revenue;
            deltaEl.className = 'hero-delta ' + (data.metrics.delta_revenue.includes('+') ? 'positive' : 'negative');

            // Table
            const tbody = document.querySelector('#recent-transactions-table tbody');
            tbody.innerHTML = '';
            (data.recent_transactions || []).forEach(tx => {
                const isExpense = tx.type === 'expense';
                const textColor = isExpense ? 'text-red' : 'text-accent';
                const amountStr = (isExpense ? '-' : '+') + Utils.formatCurrency(tx.amount);

                let badge = '';
                if (isExpense) {
                    badge = `<span class="badge badge-pending" style="background-color: var(--clr-danger-bg); color: var(--clr-danger)">Gasto</span>`;
                } else {
                    badge = Utils.getStatusBadge(tx.status);
                }

                tbody.innerHTML += `
                    <tr>
                        <td>${Utils.formatDate(tx.date)}</td>
                        <td class="${isExpense ? 'italic text-muted' : ''}">${tx.name}</td>
                        <td class="font-bold ${textColor}">${amountStr}</td>
                        <td>${badge}</td>
                    </tr>
                `;
            });

            // Update clients count natively
            appLogic.loadCRM();

        } catch (e) { console.error(e); }
    },

    loadCRM: async () => {
        try {
            const clients = await API.request(`/api/clients/${AppState.userId}`);
            const tbody = document.querySelector('#crm-clients-table tbody');
            tbody.innerHTML = '';
            clients.forEach(c => {
                tbody.innerHTML += `
                    <tr>
                        <td class="font-bold">${c.name}</td>
                        <td>${c.email}</td>
                        <td>${c.phone}</td>
                        <td>
                            <button class="btn-icon text-accent" onclick="appLogic.viewClientProfile('${c.id}')" title="Ver Perfil">
                                <i class="fa-solid fa-eye"></i>
                            </button>
                            <button class="btn-icon btn-danger-icon" onclick="appLogic.deleteClient('${c.id}')" title="Eliminar Cliente" style="margin-left: 8px;">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });
            document.getElementById('dash-clients').textContent = clients.length;
        } catch (e) { }
    },

    viewClientProfile: async (clientId) => {
        try {
            const res = await API.request(`/api/clients/${AppState.userId}/${clientId}`);
            if (res.success) {
                const c = res.client;
                document.getElementById('modal-client-name').textContent = c.name;
                document.getElementById('modal-client-name-input').value = c.name || '';
                document.getElementById('modal-client-id').value = c.id || '';
                document.getElementById('modal-client-nif').value = c.nif_cif || '';
                document.getElementById('modal-client-email').value = c.email || '';
                document.getElementById('modal-client-phone').value = c.phone || '';
                document.getElementById('modal-client-dir').value = c.direccion || '';
                document.getElementById('modal-client-loc').value = c.poblacion || '';

                const tbody = document.querySelector('#modal-client-invoices tbody');
                tbody.innerHTML = '';
                if (res.invoices && res.invoices.length > 0) {
                    res.invoices.forEach(inv => {
                        tbody.innerHTML += `
                            <tr>
                                <td class="text-muted">#${inv.invoice_number}</td>
                                <td>${Utils.formatDate(inv.date)}</td>
                                <td class="font-bold">${Utils.formatCurrency(inv.amount)}</td>
                                <td>${Utils.getStatusBadge(inv.status)}</td>
                            </tr>
                        `;
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No se encontraron facturas para este cliente.</td></tr>';
                }

                document.getElementById('client-profile-modal').classList.remove('hidden');
                document.getElementById('client-profile-modal').classList.add('show');
            }
        } catch (e) {
            console.error('Error viewing client profile:', e);
            Utils.showToast('Error loading profile', 'error');
        }
    },

    saveClientChanges: async (btn) => {
        const id = document.getElementById('modal-client-id').value;
        const req = {
            name: document.getElementById('modal-client-name-input').value,
            nif_cif: document.getElementById('modal-client-nif').value,
            email: document.getElementById('modal-client-email').value,
            phone: document.getElementById('modal-client-phone').value,
            direccion: document.getElementById('modal-client-dir').value,
            poblacion: document.getElementById('modal-client-loc').value,
            provincia: "",
            codigo_postal: ""
        };
        const prevHtml = btn.innerHTML;
        try {
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            btn.disabled = true;
            const res = await API.request(`/api/clients/${AppState.userId}/${id}`, {
                method: 'PUT',
                body: JSON.stringify(req),
                headers: { 'Content-Type': 'application/json' }
            });
            if (res.success) {
                Utils.showToast("Datos de cliente guardados", "success");
                document.getElementById('client-profile-modal').classList.add('hidden');
                document.getElementById('client-profile-modal').classList.remove('show');
                appLogic.loadCRM();
            } else {
                throw new Error(res.detail || "Error al actualizar el cliente");
            }
        } catch (e) {
            Utils.showToast(e.message, 'error');
        } finally {
            btn.innerHTML = prevHtml;
            btn.disabled = false;
        }
    },

    deleteClient: async (clientId) => {
        if (!confirm('¿Está seguro de que desea eliminar este cliente? Esta acción no se puede deshacer (las facturas anteriores se conservarán).')) return;
        try {
            const res = await API.request(`/api/clients/${AppState.userId}/${clientId}`, { method: 'DELETE' });
            if (res.success) {
                Utils.showToast("Cliente eliminado con éxito", "success");
                appLogic.loadCRM();
            }
        } catch (e) { }
    },

    addClient: async (e) => {
        e.preventDefault();
        const data = {
            user_id: AppState.userId,
            name: document.getElementById('new-client-name').value,
            nif_cif: document.getElementById('new-client-nif').value,
            direccion: document.getElementById('new-client-dir').value,
            poblacion: document.getElementById('new-client-poblacion').value || "",
            provincia: document.getElementById('new-client-provincia').value || "",
            codigo_postal: document.getElementById('new-client-cp').value || "",
            email: document.getElementById('new-client-email').value,
            phone: document.getElementById('new-client-phone').value,
        };

        const btn = e.target.querySelector('button');
        btn.disabled = true;

        try {
            const res = await API.request('/api/clients', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (res.success) {
                Utils.showToast('Cliente Registrado', 'success');
                document.getElementById('add-client-form').reset();
                appLogic.loadCRM();
            }
        } finally {
            btn.disabled = false;
        }
    },

    // --- Catalog Logic ---
    loadCatalog: async () => {
        try {
            const products = await API.request(`/api/products/${AppState.userId}`);

            AppState.catalogProducts = products;

            // Populate Catalog Table
            const tbody = document.querySelector('#catalog-table tbody');
            tbody.innerHTML = '';
            products.forEach(p => {
                tbody.innerHTML += `
                    <tr>
                        <td class="font-bold">${p.nombre}</td>
                        <td>${p.tipo}</td>
                        <td>${Utils.formatCurrency(p.precio_unitario)}</td>
                        <td>
                            <button class="btn-icon text-accent" onclick="appLogic.editProduct('${p.id}')" title="Editar">
                                <i class="fa-solid fa-pencil"></i>
                            </button>
                            <button class="btn-icon btn-danger-icon" onclick="appLogic.deleteProduct('${p.id}')" title="Eliminar">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });

            // Populate Invoice Extractor Selector
            const select = document.getElementById('ext-catalog-select');
            select.innerHTML = '<option value="">Selecciona un producto/servicio...</option>';
            products.forEach(p => {
                select.innerHTML += `<option value='${JSON.stringify({ desc: p.nombre, price: p.precio_unitario })}'>${p.nombre} - ${Utils.formatCurrency(p.precio_unitario)}</option>`;
            });

        } catch (e) {
            console.error("Error loading catalog:", e);
        }
    },

    addProduct: async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button[type="submit"]');
        btn.disabled = true;
        const editId = document.getElementById('edit-prod-id').value;

        try {
            const payload = {
                user_id: AppState.userId,
                nombre: document.getElementById('new-prod-name').value,
                descripcion: document.getElementById('new-prod-desc').value,
                precio_unitario: parseFloat(document.getElementById('new-prod-price').value),
                tipo: document.getElementById('new-prod-type').value
            };

            let res;
            if (editId) {
                res = await API.request(`/api/products/${AppState.userId}/${editId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                res = await API.request('/api/products', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }

            if (res.success) {
                Utils.showToast("Guardado en el Catálogo", "success");
                appLogic.cancelEditProduct();
                appLogic.loadCatalog();
            }
        } catch (e) {
        } finally {
            btn.disabled = false;
        }
    },

    editProduct: (id) => {
        const prod = AppState.catalogProducts?.find(p => p.id === id);
        if (!prod) return;
        document.getElementById('edit-prod-id').value = prod.id;
        document.getElementById('new-prod-name').value = prod.nombre;
        document.getElementById('new-prod-desc').value = prod.descripcion || '';
        document.getElementById('new-prod-price').value = prod.precio_unitario;
        document.getElementById('new-prod-type').value = prod.tipo;

        document.getElementById('btn-submit-prod').innerHTML = '<i class="fa-solid fa-save"></i> Actualizar Producto';
        document.getElementById('btn-cancel-edit-prod').classList.remove('hidden');
    },

    cancelEditProduct: () => {
        document.getElementById('add-catalog-form').reset();
        document.getElementById('edit-prod-id').value = '';
        document.getElementById('btn-submit-prod').innerHTML = '<i class="fa-solid fa-plus"></i> Guardar en Catálogo';
        document.getElementById('btn-cancel-edit-prod').classList.add('hidden');
    },

    deleteProduct: async (prodId) => {
        if (!confirm('¿Eliminar este artículo de su catálogo?')) return;
        try {
            await API.request(`/api/products/${AppState.userId}/${prodId}`, { method: 'DELETE' });
            Utils.showToast('Eliminado', 'success');
            appLogic.loadCatalog();
        } catch (e) { }
    },

    addCatalogItemToInvoice: () => {
        const select = document.getElementById('ext-catalog-select');
        const val = select.value;
        if (!val) return;

        const itemData = JSON.parse(val);

        // Ensure items array exists in active extractedData
        if (!AppState.extractedData) {
            AppState.extractedData = { items: [] };
        }
        if (!AppState.extractedData.items) AppState.extractedData.items = [];

        // Add line
        AppState.extractedData.items.push({
            concepto: itemData.desc,
            cantidad: 1,
            precio_unitario: parseFloat(itemData.price)
        });

        Utils.showToast(`Añadido ${itemData.desc} a la Factura`, 'success');

        // Reset selector
        select.value = "";

        // Render lines and recompute total
        appLogic.renderExtractedItems();
    },

    renderExtractedItems: () => {
        const tbody = document.querySelector('#ext-items-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!AppState.extractedData || !AppState.extractedData.items || AppState.extractedData.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No hay líneas detectadas.</td></tr>';
            document.getElementById('ext-amount').value = '0.00';
            return;
        }

        let total = 0;
        AppState.extractedData.items.forEach((item, index) => {
            // Fallbacks if data structure differs slightly
            const qty = parseFloat(item.cantidad || item.quantity || 1);
            const price = parseFloat(item.precio_unitario || item.unit_price || 0);
            const desc = item.concepto || item.description || 'Artículo';
            const lineTotal = qty * price;
            total += lineTotal;

            tbody.innerHTML += `
                <tr>
                    <td class="font-bold">${desc}</td>
                    <td style="text-align: center;">${qty}</td>
                    <td style="text-align: right;">${Utils.formatCurrency(price)}</td>
                    <td style="text-align: right; color: var(--clr-accent); font-weight: bold;">${Utils.formatCurrency(lineTotal)}</td>
                    <td style="text-align: center;">
                        <button type="button" class="btn-icon text-red" onclick="appLogic.removeExtractedItem(${index})" title="Eliminar fila">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        });

        // Add VAT to global amount since table is for base lines generally, or assume total is final?
        // Let's assume lines are base amounts.
        const finalTotal = total * 1.21;
        AppState.extractedData.total_amount = finalTotal;
        document.getElementById('ext-amount').value = parseFloat(finalTotal).toFixed(2);
    },

    removeExtractedItem: (index) => {
        if (!AppState.extractedData || !AppState.extractedData.items) return;
        AppState.extractedData.items.splice(index, 1);
        appLogic.renderExtractedItems();
    },

    loadInvoices: async () => {
        try {
            const invoices = await API.request(`/api/invoices/${AppState.userId}`);
            const tbody = document.querySelector('#all-invoices-table tbody');
            tbody.innerHTML = '';
            invoices.forEach(inv => {
                tbody.innerHTML += `
                    <tr>
                        <td class="text-muted">#${inv.id}</td>
                        <td>${Utils.formatDate(inv.date)}</td>
                        <td class="font-bold">${inv.client_name}</td>
                        <td class="font-bold">${Utils.formatCurrency(inv.amount)}</td>
                        <td>
                            <select class="status-select" onchange="appLogic.updateInvoiceStatus('${inv.id}', this.value)" style="padding: 2px 4px; border-radius: 4px; background: transparent; border: 1px solid var(--clr-border);">
                                <option value="Pendiente" ${inv.status === 'Pendiente' ? 'selected' : ''}>Pendiente</option>
                                <option value="Enviada" ${inv.status === 'Enviada' ? 'selected' : ''}>Enviada</option>
                                <option value="Pagada" ${inv.status === 'Pagada' ? 'selected' : ''}>Pagada</option>
                            </select>
                        </td>
                        <td>
                            <button class="btn-icon text-primary" style="color: #1a56db" onclick="appLogic.sendInvoice('${inv.id}', this)" title="Enviar Correo al Cliente">
                                <i class="fa-solid fa-paper-plane"></i>
                            </button>
                            <button class="btn-icon text-gold" style="color: #ca8a04" onclick="appLogic.downloadPDF('${inv.id}')" title="Descargar PDF">
                                <i class="fa-solid fa-file-pdf"></i>
                            </button>
                            <button class="btn-icon btn-danger-icon" onclick="appLogic.deleteInvoice('${inv.id}')" title="Eliminar">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });
        } catch (e) { }
    },

    sendInvoice: async (invId, btn) => {
        if (!confirm('¿Enviar esta factura por correo automático al cliente? Asegúrate de tener el Token de Gmail configurado en tu perfil.')) return;
        const originalHtml = btn.innerHTML;
        try {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

            const res = await fetch(`/api/invoices/${AppState.userId}/${invId}/send`, { method: 'POST' });
            const data = await res.json();

            if (res.ok && data.success) {
                Utils.showToast('Factura enviada al cliente por correo', 'success');
            } else {
                throw new Error(data.detail || "Error al conectar con Google/SMTP");
            }
        } catch (e) {
            Utils.showToast(e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    },

    deleteInvoice: async (invId) => {
        if (!confirm('¿Eliminar esta factura permanentemente?')) return;
        try {
            await API.request(`/api/invoices/${AppState.userId}/${invId}`, { method: 'DELETE' });
            Utils.showToast('Factura Eliminada', 'success');
            appLogic.loadInvoices();
            appLogic.loadDashboard();
        } catch (e) { }
    },

    updateInvoiceStatus: async (invId, newStatus) => {
        try {
            const res = await API.request(`/api/invoices/${AppState.userId}/${invId}/status`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });
            if (res.success) {
                Utils.showToast('Estado Actualizado', 'success');
                appLogic.loadDashboard();
            }
        } catch (e) { }
    },

    downloadPDF: (invId) => {
        window.open(`/api/generate_pdf/${invId}`, '_blank');
    },

    handleFileSelect: (file) => {
        if (!file) return;
        AppState.activeFile = file;
        document.getElementById('drop-zone').classList.add('hidden');
        document.getElementById('file-preview-area').classList.remove('hidden');
        document.getElementById('preview-filename').textContent = file.name;
    },

    clearFile: () => {
        AppState.activeFile = null;
        document.getElementById('drop-zone').classList.remove('hidden');
        document.getElementById('file-preview-area').classList.add('hidden');
        document.getElementById('file-upload').value = '';
    },

    startRecording: async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            AppState.mediaRecorder = new MediaRecorder(stream);
            AppState.audioChunks = [];

            AppState.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    AppState.audioChunks.push(event.data);
                }
            };

            AppState.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(AppState.audioChunks, { type: 'audio/webm' });
                const file = new File([audioBlob], "voice_note.webm", { type: "audio/webm" });
                appLogic.handleFileSelect(file);

                // Reset UI
                document.getElementById('btn-start-record').classList.remove('hidden');
                document.getElementById('btn-stop-record').classList.add('hidden');
                document.getElementById('recording-status').textContent = 'Audio Capturado. Listo para procesar.';
                document.getElementById('recording-status').classList.remove('text-red', 'font-bold', 'blink');

                // Stop tracks to release mic
                stream.getTracks().forEach(track => track.stop());
            };

            AppState.mediaRecorder.start();
            AppState.isRecording = true;

            // Toggle UI
            document.getElementById('btn-start-record').classList.add('hidden');
            document.getElementById('btn-stop-record').classList.remove('hidden');
            const statusBox = document.getElementById('recording-status');
            statusBox.textContent = 'Grabación activa...';
            statusBox.classList.add('text-red', 'font-bold', 'blink');

        } catch (err) {
            Utils.showToast('Acceso al micrófono denegado o no disponible.', 'error');
        }
    },

    stopRecording: () => {
        if (AppState.mediaRecorder && AppState.isRecording) {
            AppState.mediaRecorder.stop();
            AppState.isRecording = false;
        }
    },

    startCrmRecording: async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            AppState.crmMediaRecorder = new MediaRecorder(stream);
            AppState.crmAudioChunks = [];

            AppState.crmMediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) AppState.crmAudioChunks.push(event.data);
            };

            AppState.crmMediaRecorder.onstop = () => {
                const audioBlob = new Blob(AppState.crmAudioChunks, { type: 'audio/webm' });
                const file = new File([audioBlob], "client_voice.webm", { type: "audio/webm" });
                appLogic.processCrmVoice(file);

                document.getElementById('btn-crm-start-record').classList.remove('hidden');
                document.getElementById('btn-crm-stop-record').classList.add('hidden');
                document.getElementById('crm-voice-status').textContent = 'Procesando Voz...';

                stream.getTracks().forEach(track => track.stop());
            };

            AppState.crmMediaRecorder.start();
            AppState.isCrmRecording = true;

            document.getElementById('btn-crm-start-record').classList.add('hidden');
            document.getElementById('btn-crm-stop-record').classList.remove('hidden');
            document.getElementById('crm-voice-status').textContent = 'Grabando detalles del cliente...';
        } catch (e) {
            Utils.showToast('Acceso al micrófono denegado.', 'error');
        }
    },

    processExpenseDocument: async (file) => {
        if (!file) {
            Utils.showToast('Selecciona un archivo primero', 'error');
            return;
        }

        const btnStatus = document.getElementById('expense-upload-status');
        btnStatus.classList.remove('hidden');

        try {
            const formData = new FormData();
            formData.append('file', file);

            const res = await API.request('/api/process_expense', {
                method: 'POST',
                body: formData
            });

            if (res.success && res.data) {
                // Fill form
                document.getElementById('exp-provider').value = res.data.proveedor || '';
                document.getElementById('exp-date').value = res.data.fecha || '';
                document.getElementById('exp-concept').value = res.data.concepto || '';
                document.getElementById('exp-amount').value = parseFloat(res.data.importe_total || 0).toFixed(2);

                Utils.showToast('Detalles del gasto extraídos con éxito', 'success');
            }
        } finally {
            btnStatus.classList.add('hidden');
            document.getElementById('file-input-expense').value = ''; // Reset
        }
    },

    saveExpense: async (e) => {
        if (e) e.preventDefault();

        const payload = {
            user_id: AppState.userId,
            proveedor: document.getElementById('exp-provider').value,
            fecha: document.getElementById('exp-date').value,
            concepto: document.getElementById('exp-concept').value,
            importe_total: parseFloat(document.getElementById('exp-amount').value)
        };

        const btn = document.getElementById('btn-save-expense');
        const ogText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';
        btn.disabled = true;

        try {
            const res = await API.request('/api/expenses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res && res.success) {
                Utils.showToast('Gasto registrado con éxito.', 'success');
                appLogic.loadExpenses();
                appLogic.loadDashboard(); // Refresh Net Balance
                document.getElementById('expense-form').reset();
            }
        } finally {
            btn.innerHTML = ogText;
            btn.disabled = false;
        }
    },

    loadExpenses: async () => {
        if (!AppState.userId) return;
        const res = await API.request(`/api/expenses/${AppState.userId}`);
        const tbody = document.querySelector('#recent-expenses-table tbody');
        tbody.innerHTML = '';

        if (!res || res.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No se encontraron gastos.</td></tr>';
            return;
        }

        res.forEach(exp => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${exp.fecha.split('T')[0]}</td>
                <td class="font-bold">${exp.proveedor}</td>
                <td class="text-muted text-sm">${exp.concepto}</td>
                <td class="text-accent font-bold">${Utils.formatCurrency(exp.importe_total)}</td>
                <td>
                    <button class="btn-icon text-red hover-animate" onclick="appLogic.deleteExpense('${exp.id}')" title="Eliminar Gasto">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    deleteExpense: async (expenseId) => {
        if (!confirm("¿Está seguro de que desea eliminar este gasto?")) return;

        const res = await API.request(`/api/expenses/${AppState.userId}/${expenseId}`, { method: 'DELETE' });
        if (res && res.success) {
            Utils.showToast('Gasto eliminado con éxito', 'success');
            appLogic.loadExpenses();
            appLogic.loadDashboard();
        }
    },

    stopCrmRecording: () => {
        if (AppState.crmMediaRecorder && AppState.isCrmRecording) {
            AppState.crmMediaRecorder.stop();
            AppState.isCrmRecording = false;
        }
    },

    processCrmVoice: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await API.request('/api/process_client_voice', {
                method: 'POST',
                body: formData
            });

            if (res.success && res.data) {
                document.getElementById('new-client-name').value = res.data.nombre_empresa || '';
                document.getElementById('new-client-nif').value = res.data.nif_cif || '';
                document.getElementById('new-client-dir').value = res.data.direccion_fiscal || '';
                document.getElementById('new-client-poblacion').value = res.data.poblacion || '';
                document.getElementById('new-client-provincia').value = res.data.provincia || '';
                document.getElementById('new-client-cp').value = res.data.codigo_postal || '';
                document.getElementById('new-client-email').value = res.data.email || '';
                document.getElementById('new-client-phone').value = res.data.telefono || '';

                document.getElementById('crm-voice-status').textContent = '¡Campos Extraídos!';
                Utils.showToast('Datos del Cliente Extraídos', 'success');
            }
        } catch (e) {
            document.getElementById('crm-voice-status').textContent = 'La extracción falló.';
        }
    },

    processDocument: async () => {
        if (!AppState.activeFile) {
            Utils.showToast('Por favor, explora un archivo o graba audio primero.', 'error');
            return;
        }

        const btn = document.getElementById('btn-process-ai');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analizando...';
        btn.disabled = true;

        const formData = new FormData();
        formData.append('file', AppState.activeFile);
        formData.append('user_id', AppState.userId);

        try {
            const data = await API.request('/api/process_document', {
                method: 'POST',
                body: formData
            });

            AppState.extractedData = data;

            // Populate Form

            // Populate Dropdown for client
            const select = document.getElementById('ext-client');
            select.innerHTML = '<option value="">-- Seleccionar Cliente --</option>';
            try {
                const clients = await API.request(`/api/clients/${AppState.userId}`);
                let matchedId = null;
                clients.forEach(c => {
                    const selected = (c.name.toLowerCase() === (data.client_name || '').toLowerCase() ||
                        c.nif_cif === data.client_nif) ? 'selected' : '';
                    if (selected) matchedId = c.id;
                    select.innerHTML += `<option value="${c.id}" ${selected}>${c.name} (${c.nif_cif})</option>`;
                });
                if (matchedId) {
                    AppState.extractedData.client_id = matchedId;
                    AppState.extractedData.client_name = select.options[select.selectedIndex].text;
                }
            } catch (e) { }

            select.addEventListener('change', (e) => {
                AppState.extractedData.client_id = e.target.value;
                AppState.extractedData.client_name = e.target.options[e.target.selectedIndex].text;
            });

            document.getElementById('ext-invoice-num').value = data.invoice_number || 'BORRADOR / Auto Gen';
            document.getElementById('ext-date').value = data.date || new Date().toISOString().split('T')[0];

            // Render table lines
            appLogic.renderExtractedItems();

            // Handle special cases when invoice has total_amount explicitly set by AI from PDF
            if (data.total_amount && (!data.items || data.items.length === 0)) {
                document.getElementById('ext-amount').value = parseFloat(data.total_amount).toFixed(2);
            }

            document.getElementById('extracted-data-placeholder').classList.add('hidden');
            document.getElementById('extracted-form').classList.remove('hidden');
            Utils.showToast('Extracción Completa', 'success');

        } finally {
            btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Procesar con IA';
            btn.disabled = false;
        }
    },

    saveExtractedInvoice: async (isPdfGeneration = false) => {
        if (!AppState.extractedData) return null;
        const data = AppState.extractedData;
        if (!data.client_id) {
            Utils.showToast("Por favor seleccione un cliente válido primero", "error");
            return null;
        }

        const payload = {
            user_id: AppState.userId,
            client_id: data.client_id,
            fecha: data.date || new Date().toISOString().split('T')[0],
            due_date: document.getElementById('ext-due-date').value || "",
            items: data.items || []
        };

        const btn = document.getElementById('btn-save-db');
        const ogText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

        try {
            const res = await API.request('/api/invoices', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.success) {
                Utils.showToast('Factura guardada con éxito.', 'success');
                appLogic.loadInvoices();
                appLogic.loadDashboard();

                if (isPdfGeneration !== true) {
                    document.getElementById('extracted-form').classList.add('hidden');
                    document.getElementById('extracted-data-placeholder').classList.remove('hidden');
                    AppState.extractedData = null;
                }
                return res;
            }
        } finally {
            btn.innerHTML = ogText;
        }
        return null;
    },

    generatePDF: async () => {
        const res = await appLogic.saveExtractedInvoice(true);
        if (res && res.invoice_id) {
            Utils.showToast("Generando Documento PDF...", "info");
            window.open(`/api/generate_pdf/${res.invoice_id}`, '_blank');

            // Clean UI
            document.getElementById('extracted-form').classList.add('hidden');
            document.getElementById('extracted-data-placeholder').classList.remove('hidden');
            AppState.extractedData = null;
        }
    },

    handleChatSubmit: async (e) => {
        e.preventDefault();
        const input = document.getElementById('chat-input');
        const msg = input.value.trim();
        if (!msg) return;

        // Limpiar input y añadir mensaje de usuario
        input.value = '';
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML += `
            <div class="chat-message user-message" style="align-self: flex-end; max-width: 80%; background: var(--clr-primary-900); color: white; border-radius: 12px 12px 0 12px; padding: 12px 16px;">
                <div class="message-content">${msg}</div>
            </div>
        `;

        // Añadir indicador de "Pensando..."
        const typingId = 'typing-' + Date.now();
        chatMessages.innerHTML += `
            <div id="${typingId}" class="chat-message ai-message" style="align-self: flex-start; max-width: 80%; background: rgba(212, 175, 55, 0.1); border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 12px 12px 12px 0; padding: 12px 16px;">
                <div class="message-content"><i class="fa-solid fa-spinner fa-spin text-gold"></i> Analizando datos...</div>
            </div>
        `;
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const res = await API.request('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: AppState.userId, message: msg })
            });

            document.getElementById(typingId).remove();

            if (res.success && res.answer) {
                // Formatear respuesta (Markdown básico a HTML muy simple, o insertarlo como texto formateado)
                let formattedAnswer = res.answer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                formattedAnswer = formattedAnswer.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');

                chatMessages.innerHTML += `
                    <div class="chat-message ai-message" style="align-self: flex-start; max-width: 80%; background: rgba(212, 175, 55, 0.1); border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 12px 12px 12px 0; padding: 12px 16px;">
                        <div class="message-content">${formattedAnswer}</div>
                    </div>
                `;
            }
        } catch (e) {
            document.getElementById(typingId).remove();
            chatMessages.innerHTML += `
                <div class="chat-message alert-message" style="align-self: center; background: rgba(255,0,0,0.1); color: red; border-radius: 8px; padding: 8px 12px;">
                    <i class="fa-solid fa-triangle-exclamation"></i> Error al conectar con el Consultor IA.
                </div>
            `;
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },

    initProfileState: async () => {
        try {
            const res = await API.request(`/api/profile/${AppState.userId}`);
            if (res.success && res.profile) {
                document.getElementById('sidebar-user-name').textContent = res.profile.nombre;
                const avatar = document.getElementById('sidebar-avatar');
                if (res.profile.profile_picture) {
                    avatar.innerHTML = `<img src="${res.profile.profile_picture}" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">`;
                }
            }
        } catch (e) { console.error("Error initProfileState:", e); }
    },

    loadProfile: async () => {
        try {
            const res = await API.request(`/api/profile/${AppState.userId}`);
            if (res.success && res.profile) {
                const p = res.profile;
                document.getElementById('prof-nombre').value = p.nombre || '';
                document.getElementById('prof-apellidos').value = p.apellidos || '';
                document.getElementById('prof-email').value = p.email || '';
                document.getElementById('prof-telefono').value = p.telefono || '';
                document.getElementById('prof-nif').value = p.nif_cif || '';
                document.getElementById('prof-cnae').value = p.cnae || '';
                document.getElementById('prof-iban').value = p.iban || '';
                document.getElementById('prof-gmail-token').value = p.gmail_token || '';
                document.getElementById('prof-domicilio').value = p.domicilio || '';
                document.getElementById('prof-poblacion').value = p.poblacion || '';
                document.getElementById('prof-provincia').value = p.provincia || '';
                document.getElementById('prof-cp').value = p.codigo_postal || '';

                if (p.profile_picture) {
                    document.getElementById('profile-avatar-preview').src = p.profile_picture;
                    document.getElementById('profile-avatar-preview').style.display = 'block';
                    document.getElementById('profile-avatar-icon').style.display = 'none';
                }

                document.getElementById('profile-modal').classList.remove('hidden');
                document.getElementById('profile-modal').classList.add('show');
            }
        } catch (e) {
            console.error(e);
            alert("Error al cargar el perfil: " + (e.message || "desconocido"));
        }
    },

    saveProfile: async (e) => {
        e.preventDefault();
        const btn = document.getElementById('btn-save-profile');
        if (btn.disabled) return;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';

        try {
            const formData = new FormData();
            formData.append("nombre", document.getElementById('prof-nombre').value);
            formData.append("apellidos", document.getElementById('prof-apellidos').value);
            formData.append("email", document.getElementById('prof-email').value);
            formData.append("telefono", document.getElementById('prof-telefono').value);
            formData.append("nif_cif", document.getElementById('prof-nif').value);
            formData.append("cnae", document.getElementById('prof-cnae').value);
            formData.append("iban", document.getElementById('prof-iban').value);
            formData.append("gmail_token", document.getElementById('prof-gmail-token').value);
            formData.append("domicilio", document.getElementById('prof-domicilio').value);
            formData.append("poblacion", document.getElementById('prof-poblacion').value);
            formData.append("provincia", document.getElementById('prof-provincia').value);
            formData.append("codigo_postal", document.getElementById('prof-cp').value);

            const fileInput = document.getElementById('prof-avatar');
            if (fileInput.files.length > 0) {
                formData.append("avatar", fileInput.files[0]);
            }

            const res = await fetch(`/api/profile/${AppState.userId}`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok && data.success) {
                Utils.showToast("Perfil actualizado correctamente.", "success");
                document.getElementById('profile-modal').classList.add('hidden');
                document.getElementById('profile-modal').classList.remove('show');

                // Update sidebar UI directly
                if (data.nombre) document.getElementById('sidebar-user-name').textContent = data.nombre;
                if (data.profile_picture) {
                    const avatar = document.getElementById('sidebar-avatar');
                    avatar.innerHTML = `<img src="${data.profile_picture}" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">`;
                }
            } else {
                throw new Error(data.detail || "Error guardando el perfil");
            }
        } catch (e) {
            Utils.showToast(e.message, "error");
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Guardar Cambios';
        }
    }
};

const appState = {
    navigate: (viewId) => {
        AppState.currentView = viewId;
        UI.switchMainView(viewId);

        // Contextual loading
        if (viewId === 'dashboard-view') appLogic.loadDashboard();
        if (viewId === 'crm-view') appLogic.loadCRM();
        if (viewId === 'expenses-view') appLogic.loadExpenses();
        if (viewId === 'invoicing-view') { appLogic.loadInvoices(); appLogic.loadCatalog(); }
        if (viewId === 'catalog-view') appLogic.loadCatalog();
        if (viewId === 'calendar-view') appLogic.loadCalendar();
    }
};

window.appLogic = appLogic;
window.API = API;
window.UI = UI;

// IRPF Configuration Modal Logic
window.openIRPFModal = function () {
    const modal = document.getElementById('irpf-settings-modal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('show');
    }
};

window.saveIRPFRate = async function () {
    const inputEl = document.getElementById('irpf-rate-input');
    let rate = parseFloat(inputEl.value);
    if (isNaN(rate) || rate < 0 || rate > 100) {
        Utils.showToast("Porcentaje inválido", "error");
        return;
    }

    const decimalRate = rate / 100.0;

    try {
        const btn = document.getElementById('btn-save-irpf');
        if (btn) {
            btn.textContent = "Guardando...";
            btn.disabled = true;
        }

        await API.request(`/api/profile/${AppState.userId}/irpf`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ irpf_rate: decimalRate })
        });

        Utils.showToast("Configuración de IRPF guardada", "success");
        document.getElementById('irpf-settings-modal').classList.add('hidden');

        // Recalculate dashboard immediately
        if (appLogic && typeof appLogic.loadDashboard === 'function') {
            appLogic.loadDashboard();
        }

    } catch (err) {
        console.error(err);
    } finally {
        const btn = document.getElementById('btn-save-irpf');
        if (btn) {
            btn.textContent = "Guardar Porcentaje";
            btn.disabled = false;
        }
    }
};


// Start
document.addEventListener('DOMContentLoaded', UI.init);

// ─── Period Selector Controls ─────────────────────────────────────────────
window.setPeriodType = function (type) {
    AppState.period = type;
    AppState.periodOffset = 0; // reset to current period when switching type
    // Refresh whichever view is active
    if (AppState.currentView === 'dashboard-view' || AppState.currentView === 'taxes-view') {
        appLogic.loadDashboard();
    }
};

window.shiftPeriod = function (direction) {
    const newOffset = AppState.periodOffset + direction;
    // Don't allow going into the future (offset > 0)
    if (newOffset > 0) return;
    AppState.periodOffset = newOffset;
    appLogic.loadDashboard();
};

// ─── Calendar Module ───────────────────────────────────────────────────────

const MONTH_NAMES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

// Store events for current month
let _calEvents = [];

appLogic.loadCalendar = async function () {
    const { calYear, calMonth, showInvoiceDueDates } = AppState;
    try {
        const params = new URLSearchParams({ year: calYear, month: calMonth, include_invoices: showInvoiceDueDates });
        const data = await API.request(`/api/calendar/${AppState.userId}?${params}`);
        _calEvents = data.events || [];
        _renderCalendarGrid(calYear, calMonth, _calEvents);
        document.getElementById('cal-month-title').textContent = `${MONTH_NAMES_ES[calMonth]} ${calYear}`;
    } catch (e) {
        console.error('Error loading calendar:', e);
    }
};

function _renderCalendarGrid(year, month, events) {
    const grid = document.getElementById('cal-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const today = new Date();
    const firstDay = new Date(year, month - 1, 1);
    const daysInMonth = new Date(year, month, 0).getDate();
    // Monday-based offset (0=Mon, 6=Sun)
    let startOffset = firstDay.getDay(); // 0=Sun
    startOffset = (startOffset + 6) % 7; // convert to Mon=0

    // Prev month padding
    const prevMonthDays = new Date(year, month - 1, 0).getDate();
    for (let i = startOffset - 1; i >= 0; i--) {
        const cell = document.createElement('div');
        cell.className = 'cal-day other-month';
        cell.innerHTML = `<span class="cal-day-num">${prevMonthDays - i}</span>`;
        grid.appendChild(cell);
    }

    // Current month days
    for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        const dayEvents = events.filter(e => e.fecha === dateStr);

        const cell = document.createElement('div');
        cell.className = 'cal-day';
        const isToday = (today.getFullYear() === year && today.getMonth() + 1 === month && today.getDate() === d);
        if (isToday) cell.classList.add('today');

        const numEl = document.createElement('span');
        numEl.className = 'cal-day-num';
        numEl.textContent = d;
        cell.appendChild(numEl);

        // Badges (max 3 visible)
        const visible = dayEvents.slice(0, 3);
        visible.forEach(ev => {
            const badge = document.createElement('span');
            badge.className = 'cal-badge';
            badge.style.background = ev.color;
            badge.textContent = ev.titulo;
            cell.appendChild(badge);
        });
        if (dayEvents.length > 3) {
            const more = document.createElement('span');
            more.className = 'cal-badge';
            more.style.background = '#555';
            more.style.color = '#fff';
            more.textContent = `+${dayEvents.length - 3} más`;
            cell.appendChild(more);
        }

        cell.addEventListener('click', () => _openDayPanel(dateStr, dayEvents));
        grid.appendChild(cell);
    }

    // Fill remaining cells
    const totalCells = startOffset + daysInMonth;
    const remaining = (7 - (totalCells % 7)) % 7;
    for (let d = 1; d <= remaining; d++) {
        const cell = document.createElement('div');
        cell.className = 'cal-day other-month';
        cell.innerHTML = `<span class="cal-day-num">${d}</span>`;
        grid.appendChild(cell);
    }
}

function _openDayPanel(dateStr, events) {
    AppState.calSelectedDate = dateStr;
    const panel = document.getElementById('cal-detail-panel');
    const dateTitle = document.getElementById('cal-detail-date');
    const eventList = document.getElementById('cal-event-list');
    if (!panel) return;

    // Format date nicely
    const [y, m, d] = dateStr.split('-');
    dateTitle.textContent = `${parseInt(d)} de ${MONTH_NAMES_ES[parseInt(m)]} de ${y}`;

    eventList.innerHTML = '';
    if (events.length === 0) {
        eventList.innerHTML = '<li style="color:var(--clr-text-muted); font-size:0.85rem; padding:8px;">Sin eventos este día.</li>';
    } else {
        events.forEach(ev => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span class="cal-event-dot" style="background:${ev.color}"></span>
                <div class="cal-event-info">
                    <div class="cal-event-title">${ev.titulo}</div>
                    ${ev.descripcion ? `<div class="cal-event-desc">${ev.descripcion}</div>` : ''}
                </div>
                ${ev.tipo === 'personal' ? `<button class="cal-delete-btn" onclick="deleteCalendarEvent('${ev.id}')"><i class="fa-solid fa-trash"></i></button>` : ''}
            `;
            eventList.appendChild(li);
        });
    }

    panel.classList.remove('hidden');
    document.getElementById('cal-detail-backdrop')?.classList.remove('hidden');
}

window.closeCalDetail = function () {
    document.getElementById('cal-detail-panel')?.classList.add('hidden');
    document.getElementById('cal-detail-backdrop')?.classList.add('hidden');
};

window.calShiftMonth = function (dir) {
    let m = AppState.calMonth + dir;
    let y = AppState.calYear;
    if (m < 1) { m = 12; y--; }
    if (m > 12) { m = 1; y++; }
    AppState.calMonth = m;
    AppState.calYear = y;
    closeCalDetail();
    appLogic.loadCalendar();
};

window.calToggleInvoices = function (checked) {
    AppState.showInvoiceDueDates = checked;
    appLogic.loadCalendar();
};

window.openAddEventModal = function () {
    const dateStr = AppState.calSelectedDate || new Date().toISOString().split('T')[0];
    const [y, m, d] = dateStr.split('-');
    document.getElementById('event-date-input').value = dateStr;
    document.getElementById('event-date-display').value = `${parseInt(d)} de ${MONTH_NAMES_ES[parseInt(m)]} de ${y}`;
    document.getElementById('event-title-input').value = '';
    document.getElementById('event-desc-input').value = '';
    document.getElementById('add-event-modal').classList.remove('hidden');
};

window.saveCalendarEvent = async function () {
    const titulo = document.getElementById('event-title-input').value.trim();
    const fecha = document.getElementById('event-date-input').value;
    const descripcion = document.getElementById('event-desc-input').value.trim();
    if (!titulo) { Utils.showToast('El título del evento es obligatorio.', 'warning'); return; }

    const btn = document.getElementById('btn-save-event');
    btn.disabled = true; btn.textContent = 'Guardando...';

    try {
        await API.request(`/api/calendar/${AppState.userId}/evento`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha, titulo, descripcion })
        });
        document.getElementById('add-event-modal').classList.add('hidden');
        Utils.showToast('Evento añadido correctamente.', 'success');
        await appLogic.loadCalendar();
        // Refresh detail panel if same date
        if (AppState.calSelectedDate === fecha) {
            const refreshed = _calEvents.filter(e => e.fecha === fecha);
            _openDayPanel(fecha, refreshed);
        }
    } catch (e) {
        Utils.showToast('Error al guardar el evento.', 'error');
    } finally {
        btn.disabled = false; btn.textContent = 'Guardar';
    }
};

window.deleteCalendarEvent = async function (eventId) {
    if (!confirm('¿Eliminar este evento?')) return;
    try {
        await API.request(`/api/calendar/${AppState.userId}/evento/${eventId}`, { method: 'DELETE' });
        Utils.showToast('Evento eliminado.', 'success');
        await appLogic.loadCalendar();
        const refreshed = _calEvents.filter(e => e.fecha === AppState.calSelectedDate);
        _openDayPanel(AppState.calSelectedDate, refreshed);
    } catch (e) {
        Utils.showToast('Error al eliminar el evento.', 'error');
    }
};

// Voice input via Web Speech API
window.startVoiceInput = function () {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { Utils.showToast('Tu navegador no soporta reconocimiento de voz.', 'warning'); return; }
    const rec = new SpeechRecognition();
    rec.lang = 'es-ES';
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    const btn = document.getElementById('voice-btn');
    btn.style.color = '#e74c3c';
    btn.innerHTML = '<i class="fa-solid fa-microphone-lines"></i>';

    rec.start();
    rec.onresult = (e) => {
        document.getElementById('event-title-input').value = e.results[0][0].transcript;
        btn.style.color = ''; btn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    };
    rec.onerror = () => { btn.style.color = ''; btn.innerHTML = '<i class="fa-solid fa-microphone"></i>'; };
    rec.onend = () => { btn.style.color = ''; btn.innerHTML = '<i class="fa-solid fa-microphone"></i>'; };
};
// ─── Mobile Menu ───────────────────────────────────────────────────────────

window.toggleMobileMenu = function () {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    const isOpen = sidebar?.classList.toggle('open');
    backdrop?.classList.toggle('open', isOpen);
};

// Close sidebar when a nav item is clicked on mobile
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                document.getElementById('sidebar')?.classList.remove('open');
                document.getElementById('sidebar-backdrop')?.classList.remove('open');
            }
        });
    });
});

// Dismiss add-event modal when clicking the background overlay
window._calModalBgClick = function (e) {
    if (e.target === document.getElementById('add-event-modal')) {
        document.getElementById('add-event-modal').classList.add('hidden');
    }
};

