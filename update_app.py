import re

with open('static/app.js', 'r') as f:
    js = f.read()

# Add loadBudgets logic before loadInvoices
load_budgets_code = """
    convertBudgetToInvoice: async (budgetId) => {
        if(!confirm('¿Estás seguro de que quieres convertir este presupuesto a factura? Se creará una nueva factura con los mismos datos y el presupuesto se marcará como Aceptado.')) return;
        try {
            const res = await API.request(`/api/presupuestos/${AppState.userId}/${budgetId}/convertir`, { method: 'POST' });
            if(res.success) {
                Utils.showToast('Presupuesto convertido a factura con éxito', 'success');
                appLogic.loadBudgets();
                appLogic.loadInvoices();
            }
        } catch(e) {
            Utils.showToast('Error al convertir', 'error');
        }
    },
    
    downloadBudget: (id) => {
        const finalUrl = API_BASE_URL.includes("PON_AQUI_LA_URL") ? `/api/generate_pdf/${id}` : `${API_BASE_URL}/api/generate_pdf/${id}`;
        window.open(finalUrl, '_blank');
    },

    loadBudgets: async () => {
        try {
            const budgets = await API.request(`/api/presupuestos/${AppState.userId}`);
            const tbody = document.querySelector('#all-budgets-table tbody');
            tbody.innerHTML = '';
            budgets.forEach(b => {
                tbody.innerHTML += `
                    <tr>
                        <td class="text-muted">#${b.id.substring(0,8)}...</td>
                        <td>${Utils.formatDate(b.date)}</td>
                        <td class="font-bold">${b.client_name}</td>
                        <td class="font-bold">${Utils.formatCurrency(b.amount)}</td>
                        <td>
                            <span class="status-badge ${b.status === 'Aceptado' ? 'bg-success' : 'bg-warning'}">${b.status}</span>
                        </td>
                        <td>
                            <button class="btn-icon text-accent" onclick="appLogic.editBudget('${b.id}')" title="Editar">
                                <i class="fa-solid fa-pencil"></i>
                            </button>
                            <button class="btn-icon text-success" onclick="appLogic.convertBudgetToInvoice('${b.id}')" title="Convertir a Factura" style="margin-left: 8px;">
                                <i class="fa-solid fa-file-invoice-dollar"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });
        } catch (e) { }
    },
    
    editBudget: async (budgetId) => {
        // Needs API endpoint to get single budget if you want to load data perfectly.
        // As a shortcut, we can just say "Edición no implementada en la UI todavía" or implement it:
        Utils.showToast('Edición rápida desde la tabla próximamente.', 'info');
    },

    saveExtractedBudget: async () => {
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
            due_date: document.getElementById('ext-due-date-budgets').value || "",
            items: data.items || []
        };

        const btn = document.getElementById('btn-save-db-budgets');
        const ogText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

        try {
            const res = await API.request('/api/presupuestos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.success) {
                Utils.showToast('Presupuesto guardado con éxito.', 'success');
                appLogic.loadBudgets();
                
                document.getElementById('extracted-form-budgets').classList.add('hidden');
                document.getElementById('extracted-data-placeholder-budgets').classList.remove('hidden');
                AppState.extractedData = null;
                return res;
            }
        } catch(e) {
        } finally {
            btn.innerHTML = ogText;
        }
        return null;
    },
"""

js = js.replace('loadInvoices: async () => {', load_budgets_code + '\n    loadInvoices: async () => {')

# Add navigation hook
nav_hook = "if (viewId === 'invoicing-view') { appLogic.loadInvoices(); appLogic.loadCatalog(); }"
nav_budgets_hook = "if (viewId === 'budgeting-view') { appLogic.loadBudgets(); appLogic.loadCatalog(); }\n        " + nav_hook
js = js.replace(nav_hook, nav_budgets_hook)

with open('static/app.js', 'w') as f:
    f.write(js)
