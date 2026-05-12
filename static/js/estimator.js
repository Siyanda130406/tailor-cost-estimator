// CSRF Token
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

// Format money
function formatMoney(n) {
    return 'R ' + Number(n).toLocaleString('en-ZA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Show message
function showMessage(text, type) {
    const msgDiv = document.getElementById('flashMessages');
    if (msgDiv) {
        const colors = { success: '#10b981', error: '#ef4444', info: '#3b82f6' };
        msgDiv.innerHTML = '<div class="alert-bar alert-' + type + '" style="background:' + colors[type] + '10; border-color:' + colors[type] + '20; color:' + colors[type] + '">' + text + '</div>';
        setTimeout(function() { msgDiv.innerHTML = ''; }, 3000);
    }
}

// Update result panel
function updateResultPanel(data) {
    const resultDiv = document.getElementById('result');
    if (!resultDiv) return;

    document.getElementById('priceVal').textContent = formatMoney(data.total_cost);
    document.getElementById('priceRange').innerHTML = '<strong>Garment Cost:</strong> ' + formatMoney(data.garment_cost);
    document.getElementById('costBreakItems').innerHTML =
        '<div class="break-row"><span class="break-key">Material</span><span class="break-val">' + formatMoney(data.material_cost) + '</span></div>' +
        '<div class="break-row"><span class="break-key">Overhead (8%)</span><span class="break-val">' + formatMoney(data.overhead_cost) + '</span></div>';

    document.getElementById('matVal').textContent = formatMoney(data.material_cost);
    document.getElementById('matSub').innerHTML = '<strong>' + data.fabric_m + 'm</strong> × R' + data.price_per_m + '/m · ' + data.fabric_type;
    document.getElementById('matBreakItems').innerHTML =
        '<div class="break-row"><span class="break-key">Fabric</span><span class="break-val mat-val-sm">' + data.fabric_type + '</span></div>' +
        '<div class="break-row"><span class="break-key">Metres</span><span class="break-val mat-val-sm">' + data.fabric_m + 'm</span></div>' +
        '<div class="break-row"><span class="break-key">Price/m</span><span class="break-val mat-val-sm">R ' + data.price_per_m + '</span></div>';

    document.getElementById('breakdown').innerHTML =
        '<div class="bk-cell"><div class="bk-key">Garment</div><div class="bk-val">' + data.garment + '</div></div>' +
        '<div class="bk-cell"><div class="bk-key">Fabric</div><div class="bk-val">' + data.fabric_type + '</div></div>' +
        '<div class="bk-cell"><div class="bk-key">Metres</div><div class="bk-val">' + data.fabric_m + 'm</div></div>' +
        '<div class="bk-cell"><div class="bk-key">Price/m</div><div class="bk-val">R' + data.price_per_m + '</div></div>';

    document.getElementById('matBreakdown').innerHTML =
        '<div class="mat-cell"><div class="mat-key">Material Cost</div><div class="mat-val">' + formatMoney(data.material_cost) + '</div></div>' +
        '<div class="mat-cell"><div class="bk-key">Total Cost</div><div class="bk-val" style="color:var(--amber);font-weight:700">' + formatMoney(data.total_cost) + '</div></div>';

    resultDiv.style.display = 'flex';
    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Reset form
function resetForm() {
    document.getElementById('estimateForm').reset();
    document.getElementById('result').style.display = 'none';
}

// Submit estimate via AJAX
async function submitEstimate(event) {
    event.preventDefault();
    
    const garment = document.getElementById('garmentType').value;
    const fabric_type = document.getElementById('fabricType').value;
    const fabric_m = document.getElementById('fabricMeter').value;
    
    if (!garment || !fabric_type || !fabric_m) {
        showMessage('Please fill in all fields', 'error');
        return;
    }
    
    const estBtn = document.getElementById('estBtn');
    const btnTxt = document.getElementById('btnTxt');
    const btnDots = document.getElementById('btnDots');
    
    btnTxt.style.display = 'none';
    btnDots.style.display = 'flex';
    estBtn.disabled = true;
    
    try {
        const response = await fetch('/api/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ garment: garment, fabric_type: fabric_type, fabric_m: parseFloat(fabric_m) })
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateResultPanel(data);
            showMessage('Estimate saved successfully!', 'success');
            updateRecentEstimates();
        } else {
            showMessage(data.error || 'Prediction failed', 'error');
        }
    } catch (error) {
        showMessage('Network error. Please try again.', 'error');
    } finally {
        btnTxt.style.display = 'flex';
        btnDots.style.display = 'none';
        estBtn.disabled = false;
    }
}

// Chat function - NO PAGE REFRESH
async function sendChat() {
    const input = document.getElementById('chatIn');
    const message = input.value.trim();
    
    if (!message) {
        showChatMessage('Please enter a message first.', 'error');
        return;
    }

    input.disabled = true;
    input.placeholder = 'Processing...';
    showChatMessage('Processing your request...', 'info');

    try {
        const response = await fetch('/api/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();

        if (data.success) {
            updateResultPanel(data);
            showChatMessage('✅ ' + data.reply, 'success');
            input.value = '';
            updateRecentEstimates();
        } else {
            showChatMessage('❌ ' + data.reply, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showChatMessage('❌ Network error. Make sure the server is running', 'error');
    } finally {
        input.disabled = false;
        input.placeholder = 'Describe a garment... e.g. "silk dress 3m"';
        input.focus();
    }
}

// Update recent estimates
async function updateRecentEstimates() {
    try {
        const response = await fetch('/estimator/recent');
        if (response.ok) {
            const data = await response.json();
            const recentList = document.getElementById('recentList');
            if (recentList && data.recent) {
                recentList.innerHTML = data.recent;
            }
        }
    } catch (error) { }
}

// Show chat message
function showChatMessage(text, type) {
    const resultDiv = document.getElementById('chatResult');
    if (resultDiv) {
        const colors = { success: '#10b981', error: '#ef4444', info: '#3b82f6' };
        resultDiv.style.color = colors[type] || '#6b7280';
        resultDiv.style.backgroundColor = colors[type] + '10';
        resultDiv.style.padding = '8px';
        resultDiv.style.borderRadius = '8px';
        resultDiv.innerHTML = text;
        setTimeout(function() {
            if (resultDiv.innerHTML === text) {
                resultDiv.style.backgroundColor = '';
                resultDiv.innerHTML = '';
            }
        }, 4000);
    }
}

// Enter key for chat
document.addEventListener('DOMContentLoaded', function() {
    const chatInput = document.getElementById('chatIn');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendChat();
            }
        });
    }
});