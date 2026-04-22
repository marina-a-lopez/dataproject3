import re

with open('static/app.js', 'r') as f:
    js = f.read()

events = """
        // Budgeting Actions
        const fileInputBudgets = document.getElementById('file-upload-budgets');
        if(fileInputBudgets) {
            fileInputBudgets.addEventListener('change', (e) => appLogic.handleFileSelect(e.target.files[0], 'budgets'));
            document.getElementById('btn-remove-file-budgets').addEventListener('click', () => appLogic.clearFile('budgets'));
            document.getElementById('btn-process-ai-budgets').addEventListener('click', () => appLogic.processDocument('budgets'));
            document.getElementById('btn-save-db-budgets').addEventListener('click', appLogic.saveExtractedBudget);
        }
"""
js = js.replace('// Invoice Actions', events + '\n        // Invoice Actions')

# I need to modify handleFileSelect and clearFile and processDocument to support suffixes
handle_file_mod = """
    handleFileSelect: (file, type='invoices') => {
        if (!file) return;
        AppState.activeFile = file;
        const sfp = type === 'budgets' ? '-budgets' : '';
        document.getElementById(`drop-zone${sfp}`).classList.add('hidden');
        document.getElementById(`file-preview-area${sfp}`).classList.remove('hidden');
        document.getElementById(`preview-filename${sfp}`).textContent = file.name;
    },

    clearFile: (type='invoices') => {
        AppState.activeFile = null;
        const sfp = type === 'budgets' ? '-budgets' : '';
        document.getElementById(`drop-zone${sfp}`).classList.remove('hidden');
        document.getElementById(`file-preview-area${sfp}`).classList.add('hidden');
        document.getElementById(`file-upload${sfp}`).value = '';
    },
"""
# Replace handleFileSelect & clearFile
# Removing old definitions
js = re.sub(r'handleFileSelect:\s*\(file\)\s*=>\s*\{.*?(?=clearFile:)', '', js, flags=re.DOTALL)
js = re.sub(r'clearFile:\s*\(\)\s*=>\s*\{.*?(?=startRecording:)', handle_file_mod, js, flags=re.DOTALL)

# Modify processDocument to accept type
process_mod = """
    processDocument: async (type='invoices') => {
        const sfp = type === 'budgets' ? '-budgets' : '';
        if (!AppState.activeFile) {
            Utils.showToast('Por favor, explora un archivo o graba audio primero.', 'error');
            return;
        }

        const btn = document.getElementById(`btn-process-ai${sfp}`);
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

            const select = document.getElementById(`ext-client${sfp}`);
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

            if(type === 'budgets') {
                document.getElementById('ext-budget-num').value = data.invoice_number || 'BORRADOR / Auto Gen';
            } else {
                document.getElementById('ext-invoice-num').value = data.invoice_number || 'BORRADOR / Auto Gen';
            }
            
            document.getElementById(`ext-date${sfp}`).value = data.date || new Date().toISOString().split('T')[0];

            // Render table lines
            appLogic.renderExtractedItems(sfp);

            if (data.total_amount && (!data.items || data.items.length === 0)) {
                document.getElementById(`ext-amount${sfp}`).value = parseFloat(data.total_amount).toFixed(2);
            }

            document.getElementById(`extracted-data-placeholder${sfp}`).classList.add('hidden');
            document.getElementById(`extracted-form${sfp}`).classList.remove('hidden');
            Utils.showToast('Extracción Completa', 'success');

        } finally {
            btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Procesar con IA';
            btn.disabled = false;
        }
    },
"""
js = re.sub(r'processDocument:\s*async\s*\(\)\s*=>\s*\{.*?(?=saveExtractedInvoice:)', process_mod, js, flags=re.DOTALL)

# Modify renderExtractedItems
render_mod = """
    renderExtractedItems: (sfp='') => {
        const tbody = document.querySelector(`#ext-items-table${sfp} tbody`);
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!AppState.extractedData || !AppState.extractedData.items || AppState.extractedData.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No hay líneas detectadas.</td></tr>';
            document.getElementById(`ext-amount${sfp}`).value = '0.00';
            return;
        }

        let total = 0;
        AppState.extractedData.items.forEach((item, index) => {
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
                        <button type="button" class="btn-icon text-red" onclick="appLogic.removeExtractedItem(${index}, '${sfp}')" title="Eliminar fila">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        });

        const finalTotal = total * 1.21;
        AppState.extractedData.total_amount = finalTotal;
        document.getElementById(`ext-amount${sfp}`).value = parseFloat(finalTotal).toFixed(2);
    },

    removeExtractedItem: (index, sfp='') => {
        if (!AppState.extractedData || !AppState.extractedData.items) return;
        AppState.extractedData.items.splice(index, 1);
        appLogic.renderExtractedItems(sfp);
    },
"""
js = re.sub(r'renderExtractedItems:\s*\(\)\s*=>\s*\{.*?(?=loadInvoices:)', render_mod, js, flags=re.DOTALL)

# Replace old usages in addCatalogItemToInvoice
js = js.replace('appLogic.renderExtractedItems()', "appLogic.renderExtractedItems(document.getElementById('budgeting-view') && !document.getElementById('budgeting-view').classList.contains('hidden') ? '-budgets' : '')")

with open('static/app.js', 'w') as f:
    f.write(js)
