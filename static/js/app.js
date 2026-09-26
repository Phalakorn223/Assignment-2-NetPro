/* ==========================================================================
   NetConfig Tracer Studio v2 — Frontend Application Logic
   ========================================================================== */

// ─── State ────────────────────────────────────────────────────────────────
let activeDeviceId = "R1";
let topoNetwork = null;  // vis-network instance
let inventoryDevices = [];
let cliHistory = [];     // command history buffer
let cliHistoryIdx = -1;  // history navigation index
let selectedInterfaceName = "";
let drawerDeviceId = null;
let cachedInterfaces = {};  // {deviceId: [iface, ...]} — cache interface จากอุปกรณ์

const TOPO_ICON = {
    router: "/static/icons/router.svg",
    switch: "/static/icons/switch.svg",
    pc: "/static/icons/pc.svg",
};


// ─── Init ─────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadInventory();
    initRoutingRows();
    updateIfPreview();
    updateRoutingPreview();
    loadActiveConnections();
    toggleRedistributionPanel(document.getElementById("routing-type-input")?.value || "static");
});

// =============================================================================
// TAB NAVIGATION
// =============================================================================
function switchTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-page").forEach(p => p.classList.remove("active"));
    const page = document.getElementById(tabId);
    if (page) page.classList.add("active");
    const btnId = "btn-" + tabId;
    const btn = document.getElementById(btnId);
    if (btn) btn.classList.add("active");
    if (tabId === "tab-if" || tabId === "tab-interface") {
        refreshInterfaceTable();
    }
    if (tabId === "tab-cli") {
        updatePromptLabel();
        refreshDeviceCliPrompt();
        setTimeout(() => {
            focusCliInput();
            scrollToBottom();
        }, 50);
    }
}

// =============================================================================
// DEVICE INVENTORY & AUTO-RECONNECT ENGINE
// =============================================================================
let isAutoConnectingAll = false;
let autoReconnectTimer = null;

function updateInventoryDot(deviceId, state) {
    const dot = document.getElementById(`inv-dot-${deviceId}`);
    if (!dot) return;
    dot.className = `inv-status-dot ${state}`;
    if (state === "connected") dot.title = "Connected (Online)";
    else if (state === "connecting") dot.title = "Connecting / Auto-reconnecting...";
    else dot.title = "Disconnected (Offline - Click to Connect)";
}

async function autoConnectDevice(deviceId, silent = false) {
    const dev = inventoryDevices.find(d => d.id === deviceId || d.name === deviceId);
    if (!dev) return;
    const connType = (dev.connection_type || "SSH").toUpperCase();
    const dtype = (dev.device_type_label || "").toLowerCase();
    if (dtype === "network" || dtype === "cloud" || (dtype === "pc" && connType === "PC")) return;

    updateInventoryDot(dev.id, "connecting");

    const badge = document.getElementById("cli-conn-badge");
    if (badge && activeDeviceId === dev.id) {
        badge.className = "badge badge-warning";
        badge.style.background = "#854d0e";
        badge.style.borderColor = "#eab308";
        badge.style.color = "#fef08a";
        badge.textContent = `◌ Connecting to ${dev.name || dev.id}...`;
    }

    try {
        const res = await fetch(`/api/connect/${encodeURIComponent(dev.id)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ skip_ping: true })
        });
        const data = await res.json();
        if (data.success) {
            dev.connected = true;
            updateInventoryDot(dev.id, "connected");
            if (activeDeviceId === dev.id) {
                updateCliConnectionBadge();
                refreshDeviceCliPrompt();
            }
            if (!silent) {
                showNotification(`เชื่อมต่อกับ ${dev.name || dev.id} สำเร็จแล้ว`, "success");
            }
        } else {
            updateInventoryDot(dev.id, "disconnected");
            if (activeDeviceId === dev.id) {
                updateCliConnectionBadge();
            }
        }
    } catch (e) {
        updateInventoryDot(dev.id, "disconnected");
        if (activeDeviceId === dev.id) {
            updateCliConnectionBadge();
        }
    }
}

async function triggerAutoConnectAll(userInitiated = false) {
    if (isAutoConnectingAll) return;
    isAutoConnectingAll = true;

    const btn = document.getElementById("btn-reconnect-all");
    if (btn) {
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Reconnecting...`;
        btn.disabled = true;
    }

    // Mark disconnected devices as connecting
    inventoryDevices.forEach(dev => {
        const connType = (dev.connection_type || "SSH").toUpperCase();
        const dtype = (dev.device_type_label || "").toLowerCase();
        if (dtype === "network" || dtype === "cloud" || (dtype === "pc" && connType === "PC")) return;
        if (!dev.connected) {
            updateInventoryDot(dev.id, "connecting");
        }
    });

    try {
        const res = await fetch("/api/connections/auto-connect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.success && data.connected) {
            const connectedIds = new Set(data.connected.map(c => c.id));
            let newlyConnected = 0;
            inventoryDevices.forEach(dev => {
                const isConn = connectedIds.has(dev.id) || connectedIds.has(dev.name);
                if (isConn && !dev.connected) newlyConnected++;
                dev.connected = isConn;
                updateInventoryDot(dev.id, isConn ? "connected" : "disconnected");
            });
            updateCliConnectionBadge();
            if (activeDeviceId) {
                const act = inventoryDevices.find(d => d.id === activeDeviceId);
                if (act && act.connected && !cliDirectPrompt) {
                    refreshDeviceCliPrompt();
                }
            }
            if (userInitiated) {
                showNotification(`ระบบ Auto-Reconnect ตรวจสอบและเชื่อมต่ออุปกรณ์สำเร็จ (${newlyConnected} เครื่อง)`, "success");
            }
        }
    } catch (e) {
        console.error("Auto-connect all failed:", e);
    } finally {
        isAutoConnectingAll = false;
        if (btn) {
            btn.innerHTML = `<i class="fa-solid fa-rotate-right"></i> Reconnect All`;
            btn.disabled = false;
        }
    }
}

function startAutoReconnectLoop() {
    if (autoReconnectTimer) clearInterval(autoReconnectTimer);
    autoReconnectTimer = setInterval(async () => {
        try {
            const res = await fetch("/api/connections/keepalive", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ auto_reconnect: true })
            });
            const data = await res.json();
            if (data.success && data.connected) {
                const connectedIds = new Set(data.connected.map(c => c.id));
                let changed = false;
                inventoryDevices.forEach(dev => {
                    const isConn = connectedIds.has(dev.id) || connectedIds.has(dev.name);
                    if (dev.connected !== isConn) {
                        dev.connected = isConn;
                        changed = true;
                        updateInventoryDot(dev.id, isConn ? "connected" : "disconnected");
                    }
                });
                if (changed) {
                    updateCliConnectionBadge();
                }
            }
        } catch (e) {}
    }, 15000);
}

async function loadInventory() {
    try {
        const res = await fetch("/api/inventory");
        const data = await res.json();
        if (data.success) {
            inventoryDevices = data.devices;
            renderInventoryList();
            populateDeviceSelects();
            runAutoDiscovery();
            refreshInterfaceTable();
            // Automatically auto-connect and maintain connection in background
            triggerAutoConnectAll(false);
            startAutoReconnectLoop();
        }
    } catch (e) { console.error("Inventory load failed:", e); }
}

function renderInventoryList() {
    const list = document.getElementById("inventory-list");
    if (!list) return;
    list.innerHTML = "";
    if (!inventoryDevices.length) {
        list.innerHTML = '<div style="padding:10px 16px;font-size:12px;color:var(--text-dim)">No devices. Click Add Device.</div>';
        return;
    }
    inventoryDevices.forEach(dev => {
        const item = document.createElement("div");
        item.className = "inventory-item" + (dev.id === activeDeviceId ? " active" : "");
        const port = dev.port || 0;
        const ipDisplay = dev.ip
            ? (port > 1000 ? `${dev.ip}:${port}` : dev.ip)
            : (dev.serial_port || '');
        item.innerHTML = `
            <span class="inv-status-dot ${dev.connected ? 'connected' : 'disconnected'}" id="inv-dot-${dev.id}" title="${dev.connected ? 'Connected' : 'Disconnected'}"></span>
            <span class="inv-name">${dev.name || dev.id}</span>
            <span class="inv-ip">${ipDisplay}</span>
            <span class="inv-type-badge">${(dev.connection_type || 'SSH').toUpperCase()}</span>
            <button class="inv-del-btn" onclick="deleteDevice('${dev.id}')" title="Remove"><i class="fa-solid fa-xmark"></i></button>
        `;
        item.addEventListener("click", (e) => {
            if (e.target.closest(".inv-del-btn")) return;
            selectActiveDevice(dev.id);
        });
        list.appendChild(item);
    });
}

function populateDeviceSelects() {
    const selects = ["active-device-select", "conn-device-select"];
    selects.forEach(sid => {
        const sel = document.getElementById(sid);
        if (!sel) return;
        const current = sel.value;
        sel.innerHTML = "";
        inventoryDevices.forEach(dev => {
            const opt = document.createElement("option");
            opt.value = dev.id;
            opt.textContent = `${dev.name || dev.id} (${dev.ip || dev.serial_port || ''}) [${dev.connection_type || 'SSH'}]`;
            if (dev.id === current || dev.id === activeDeviceId) opt.selected = true;
            sel.appendChild(opt);
        });
    });
    updatePromptLabel();
}

// Terminal Emulator multi-session state store (per device buffer)
const deviceTerminalState = {};
let cliIsPasswordMode = false;

function saveCurrentDeviceTerminalState() {
    if (!activeDeviceId) return;
    const linesEl = document.getElementById("cli-lines");
    deviceTerminalState[activeDeviceId] = {
        html: linesEl ? linesEl.innerHTML : "",
        prompt: cliDirectPrompt || getCliPrompt(),
        isPassword: cliIsPasswordMode,
        history: [...cliHistory]
    };
}

function restoreDeviceTerminalState(deviceId) {
    const linesEl = document.getElementById("cli-lines");
    const input = document.getElementById("cli-input");
    const state = deviceTerminalState[deviceId];
    if (state) {
        if (linesEl) linesEl.innerHTML = state.html;
        cliDirectPrompt = state.prompt || "";
        cliIsPasswordMode = !!state.isPassword;
        cliHistory = state.history || [];
    } else {
        if (linesEl) linesEl.innerHTML = "";
        cliDirectPrompt = "";
        cliIsPasswordMode = false;
        cliHistory = [];
        refreshDeviceCliPrompt();
    }
    if (input) {
        input.type = cliIsPasswordMode ? "password" : "text";
        input.value = "";
    }
    updatePromptLabel();
    updateCliConnectionBadge();
    scrollToBottom();
}

function updateCliConnectionBadge() {
    const badge = document.getElementById("cli-conn-badge");
    if (!badge) return;
    const dev = inventoryDevices.find(d => d.id === activeDeviceId);
    const connType = dev?.connection_type || (dev?.device_type_label === "pc" ? "PC" : "TELNET");
    const endpoint = dev?.connection_type === "SERIAL" ? (dev.serial_port || "COM1") : (dev?.ip ? `${dev.ip}:${dev.port || 23}` : "127.0.0.1");

    if (dev && dev.connected) {
        badge.className = "badge badge-success";
        badge.style.background = "#065f46";
        badge.style.borderColor = "#10b981";
        badge.style.color = "#6ee7b7";
        badge.style.cursor = "default";
        badge.title = "Connected (Online)";
        badge.onclick = null;
        badge.textContent = `● ${connType} ${endpoint}`;
    } else {
        badge.className = "badge badge-warning";
        badge.style.background = "#374151";
        badge.style.borderColor = "#6b7280";
        badge.style.color = "#9ca3af";
        badge.style.cursor = "pointer";
        badge.title = "Click to Reconnect Session";
        badge.onclick = (e) => reconnectActiveCli(e);
        badge.textContent = `○ ${connType} (OFFLINE — Click to Reconnect)`;
    }
}

function selectActiveDevice(deviceId, forceRefresh = true) {
    if (typeof deviceId === "string" && (deviceId.startsWith("Net ") || deviceId.startsWith("Net_"))) return;

    const dev = inventoryDevices.find(d => d.id === deviceId || d.name === deviceId || String(d.id) === String(deviceId));
    const newId = dev ? dev.id : deviceId;

    if (activeDeviceId && activeDeviceId !== newId) {
        saveCurrentDeviceTerminalState();
    }
    activeDeviceId = newId;

    const sel = document.getElementById("active-device-select");
    if (sel && dev) sel.value = dev.id;
    const connSel = document.getElementById("conn-device-select");
    if (connSel && dev) connSel.value = dev.id;

    cliCustomHostname = null;
    restoreDeviceTerminalState(activeDeviceId);
    updateActiveInventoryHighlight();
    updateInterfaceOptions();
    refreshInterfaceTable(forceRefresh);

    if (typeof visNodes !== "undefined" && visNodes) {
        try {
            visNodes.update(visNodes.get().map(n => ({
                id: n.id,
                borderWidth: n.id === activeDeviceId ? 3 : 1.5,
            })));
        } catch (e) {}
    }

    // Auto-reconnect / auto-connect if device is currently disconnected
    if (dev && !dev.connected) {
        const connType = (dev.connection_type || "SSH").toUpperCase();
        const dtype = (dev.device_type_label || "").toLowerCase();
        if (dtype !== "network" && dtype !== "cloud" && !(dtype === "pc" && connType === "PC")) {
            autoConnectDevice(dev.id);
        }
    }
}

function onActiveDeviceChange() {
    const newId = document.getElementById("active-device-select").value;
    selectActiveDevice(newId);
}

function updateActiveInventoryHighlight() {
    const list = document.getElementById("inventory-list");
    if (!list) return;
    const items = list.querySelectorAll(".inventory-item");
    inventoryDevices.forEach((dev, idx) => {
        if (items[idx]) {
            if (dev.id === activeDeviceId) {
                items[idx].classList.add("active");
            } else {
                items[idx].classList.remove("active");
            }
        }
    });
}

let cliDirectPrompt = "";

function setCliDirectPrompt(prompt) {
    if (!prompt) return;
    cliDirectPrompt = prompt.trim();
    const promptEl = document.getElementById("cli-prompt");
    if (promptEl) promptEl.textContent = getCliPrompt();

    if (!cliIsPasswordMode && !cliDirectPrompt.toLowerCase().includes("password")) {
        const match = cliDirectPrompt.match(/^([A-Za-z0-9_\-\.]+)/);
        if (match) {
            cliCustomHostname = match[1];
            const winTitle = document.getElementById("cli-window-title");
            if (winTitle) {
                winTitle.innerHTML = `<i class="fa-solid fa-terminal"></i> Console - ${cliCustomHostname}`;
            }
        }
    }
}

async function refreshDeviceCliPrompt() {
    try {
        const res = await fetch("/api/cli/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_id: activeDeviceId,
                command: ""
            })
        });
        const data = await res.json();
        if (data.prompt) {
            setCliDirectPrompt(data.prompt);
        }
        if (data.is_password) {
            cliIsPasswordMode = true;
            const input = document.getElementById("cli-input");
            if (input) input.type = "password";
        }
    } catch (e) {}
}

function getCliHostname() {
    if (cliCustomHostname) return cliCustomHostname;
    const dev = inventoryDevices.find(d => d.id === activeDeviceId);
    return dev ? (dev.name || dev.id) : (activeDeviceId || "Router");
}

function getCliPrompt() {
    if (cliDirectPrompt) {
        const p = cliDirectPrompt.trim();
        return p.endsWith(" ") ? p : p + " ";
    }
    const dev = inventoryDevices.find(d => d.id === activeDeviceId);
    const isLinux = dev && (dev.device_type_label === "pc" || (dev.model || "").toLowerCase().includes("linux") || (dev.model || "").toLowerCase().includes("ubuntu"));
    if (isLinux) {
        const user = dev.username || "ubuntu";
        const host = (dev.name || dev.id || "pc1").toLowerCase();
        return `${user}@${host}:~$ `;
    }
    const host = getCliHostname();
    if (cliMode === "user") return `${host}> `;
    if (cliMode === "config") return `${host}(config)# `;
    if (cliMode === "config_if") return `${host}(config-if)# `;
    if (cliMode === "config_router") return `${host}(config-router)# `;
    return `${host}# `;
}

function updatePromptLabel() {
    const host = getCliHostname();
    const promptEl = document.getElementById("cli-prompt");
    if (promptEl) promptEl.textContent = getCliPrompt();

    const winTitle = document.getElementById("cli-window-title");
    if (winTitle) {
        winTitle.innerHTML = `<i class="fa-solid fa-terminal"></i> Console - ${host}`;
    }
}

function toggleInventoryPanel() {
    const list = document.getElementById("inventory-list");
    if (list) list.classList.toggle("d-none");
}

function openAddDeviceModal() { document.getElementById("add-device-modal").classList.add("active"); }

async function submitAddDevice(e) {
    e.preventDefault();
    const dtype = document.getElementById("ad-type").value;
    const proto = document.getElementById("ad-proto").value || (dtype === "pc" ? "SSH" : "TELNET");
    const isSerial = proto === "SERIAL";

    const payload = {
        name: document.getElementById("ad-name").value,
        model: document.getElementById("ad-model").value,
        device_type_label: dtype,
        connection_type: proto,
        ip: isSerial ? "" : document.getElementById("ad-ip").value,
        port: isSerial ? 0 : (parseInt(document.getElementById("ad-port").value) || (proto === "TELNET" ? 23 : 22)),
        serial_port: isSerial ? (document.getElementById("ad-serial-port")?.value || "COM1") : undefined,
        baudrate: isSerial ? (parseInt(document.getElementById("ad-baud")?.value) || 9600) : undefined,
        username: isSerial ? "" : document.getElementById("ad-user").value,
        password: isSerial ? "" : document.getElementById("ad-pass").value,
        mask: document.getElementById("ad-mask")?.value || "255.255.255.0",
        gateway: document.getElementById("ad-gateway")?.value || "",
    };
    const res = await fetch("/api/inventory", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
        closeModal("add-device-modal");
        document.getElementById("add-device-form").reset();
        onAddDeviceProtoChange();
        await loadInventory();
        showNotification(`Added device: ${payload.name}`, "success");
    } else {
        showNotification(data.message, "error");
    }
}

async function deleteDevice(deviceId) {
    if (!confirm(`Remove ${deviceId} from inventory?`)) return;
    const res = await fetch(`/api/inventory/${deviceId}`, { method: "DELETE" });
    const data = await res.json();
    if (data.success) {
        if (activeDeviceId === deviceId && inventoryDevices.length) {
            activeDeviceId = inventoryDevices.find(d => d.id !== deviceId)?.id || "";
        }
        await loadInventory();
        showNotification(`Removed ${deviceId}`, "success");
    } else {
        showNotification(data.message || "ลบ device ไม่สำเร็จ", "error");
    }
}

function onAddDeviceTypeChange() {
    const dtype = document.getElementById("ad-type").value;
    const isPc = dtype === "pc";
    const isNet = dtype === "network";
    document.getElementById("ad-pc-fields")?.classList.toggle("d-none", !isPc);
    document.getElementById("ad-cred-fields")?.classList.toggle("d-none", isNet);
    const protoSel = document.getElementById("ad-proto");
    if (protoSel) protoSel.closest(".form-group")?.classList.toggle("d-none", isNet);
    onAddDeviceProtoChange();
}

async function onAddDeviceProtoChange() {
    const proto = document.getElementById("ad-proto")?.value;
    const isSerial = proto === "SERIAL";
    const isTelnet = proto === "TELNET";
    
    const ipPortRow = document.getElementById("ad-ip-port-row");
    const serialRow = document.getElementById("ad-serial-row");
    const credFields = document.getElementById("ad-cred-fields");
    const hintEl = document.getElementById("ad-proto-hint");
    const portInp = document.getElementById("ad-port");

    if (ipPortRow) ipPortRow.classList.toggle("d-none", isSerial);
    if (serialRow) serialRow.classList.toggle("d-none", !isSerial);
    if (credFields) credFields.classList.toggle("d-none", isSerial);

    if (isSerial) {
        if (hintEl) hintEl.innerHTML = `<span style="color:#38bdf8"><i class="fa-solid fa-plug"></i> Serial Console</span>: ใช้ COM Port เช่น COM1, COM7 กับ Baud Rate 9600 (ไม่ต้องระบุ IP Address)<br><span style="color:#fbbf24"><i class="fa-solid fa-triangle-exclamation"></i> <strong>ข้อควรระวัง:</strong> หากเป็น Console บน EVE-NG (เช่น พอร์ต 32769) ให้เลือก Protocol เป็น <strong>Telnet</strong></span>`;
        // Try auto-detecting COM ports on machine
        try {
            const r = await fetch("/api/serial/ports");
            const d = await r.json();
            if (d.success && d.ports && d.ports.length) {
                const sPort = document.getElementById("ad-serial-port");
                if (sPort && (!sPort.value || sPort.value === "COM1")) {
                    sPort.value = d.ports[0].port;
                }
                if (hintEl) hintEl.innerHTML += `<br><span style="color:#34d399"><i class="fa-solid fa-check"></i> ตรวจพบพอร์ตบนเครื่อง: <strong>${d.ports.map(p => `${p.port} (${p.description})`).join(', ')}</strong></span>`;
            }
        } catch (_) {}
    } else if (isTelnet) {
        if (portInp && (portInp.value === "22" || !portInp.value)) portInp.value = "23";
        if (hintEl) hintEl.innerHTML = `<span style="color:#38bdf8"><i class="fa-solid fa-network-wired"></i> Telnet</span>: พอร์ต <code>23</code> หรือหากเป็น EVE-NG ให้ใส่ IP ของ EVE-NG และ Port เช่น <code>32769</code>`;
    } else {
        if (portInp && (portInp.value === "23" || !portInp.value)) portInp.value = "22";
        if (hintEl) hintEl.innerHTML = `<span style="color:#38bdf8"><i class="fa-solid fa-shield-halved"></i> SSH</span>: พอร์ตมาตรฐาน <code>22</code>`;
    }
}

// =============================================================================
// CONNECTION MANAGEMENT
// =============================================================================
function onConnDeviceSelect() {
    const connResult = document.getElementById("conn-result");
    if (connResult) connResult.classList.add("d-none");
    const sel = document.getElementById("conn-device-select");
    const devId = sel.value;
    const dev = inventoryDevices.find(d => d.id === devId);
    if (!dev) return;
    document.getElementById("conn-proto").value = dev.connection_type || "SSH";
    document.getElementById("conn-ip").value = dev.ip || "";
    document.getElementById("conn-port").value = dev.port || (dev.connection_type === "SSH" ? 22 : 23);
    document.getElementById("conn-user").value = dev.username !== undefined ? dev.username : "";
    document.getElementById("conn-pass").value = dev.password !== undefined ? dev.password : "";
    const sPortInp = document.getElementById("conn-serial-port");
    if (sPortInp) sPortInp.value = dev.serial_port || "COM1";
    const baudInp = document.getElementById("conn-baud");
    if (baudInp) baudInp.value = dev.baudrate || 9600;
    const secretInp = document.getElementById("conn-secret");
    if (secretInp) {
        secretInp.value = dev.secret || dev.password || "";
    }
    onConnProtoChange();
}

function applyQuickPreset(preset) {
    const protoSel = document.getElementById("conn-proto");
    const portInp = document.getElementById("conn-port");
    const userInp = document.getElementById("conn-user");
    const passInp = document.getElementById("conn-pass");

    if (preset === "eveng-console") {
        protoSel.value = "TELNET";
        portInp.value = "32769";
        userInp.value = "";
        passInp.value = "";
        showNotification("ตั้งค่าพรีเซ็ต EVE-NG Console (Telnet Port 32xxx, ไม่ต้องใส่ User/Pass)", "info");
    } else if (preset === "cisco-ssh") {
        protoSel.value = "SSH";
        portInp.value = "22";
        userInp.value = "cisco";
        passInp.value = "cisco";
        showNotification("ตั้งค่าพรีเซ็ต Cisco SSH (Port 22, User: cisco)", "info");
    } else if (preset === "cisco-telnet") {
        protoSel.value = "TELNET";
        portInp.value = "23";
        userInp.value = "cisco";
        passInp.value = "cisco";
        showNotification("ตั้งค่าพรีเซ็ต Cisco Telnet (Port 23, User: cisco)", "info");
    }
    onConnProtoChange();
}

function onConnProtoChange() {
    const proto = document.getElementById("conn-proto").value;
    const isSerial = proto === "SERIAL";
    document.getElementById("ip-conn-fields").classList.toggle("d-none", isSerial);
    document.getElementById("serial-conn-fields").classList.toggle("d-none", !isSerial);
    const portEl = document.getElementById("conn-port");
    if (!isSerial && portEl) {
        if (proto === "SSH" && (!portEl.value || portEl.value === "23")) {
            portEl.value = "22";
        } else if (proto === "TELNET" && (!portEl.value || portEl.value === "22")) {
            portEl.value = "23";
        }
    }
}

async function testPing() {
    const ip = document.getElementById("conn-ip").value;
    if (!ip) { showNotification("กรอก IP address ก่อน", "error"); return; }
    const btn = document.getElementById("btn-test-ping") || event.target.closest("button");
    const originalHtml = btn ? btn.innerHTML : '<i class="fa-solid fa-satellite-dish"></i> Test Ping';
    if (btn) {
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> กำลัง Ping...';
        btn.disabled = true;
    }
    try {
        const res = await fetch("/api/ping", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip })
        });
        const data = await res.json();
        const box = document.getElementById("ping-result");
        if (box) {
            box.textContent = data.message;
            box.className = "ping-result-box " + (data.reachable ? "success" : "fail");
            box.classList.remove("d-none");
        }
    } finally {
        if (btn) {
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        }
    }
}

async function submitConnection(e) {
    e.preventDefault();
    const btnConnect = document.getElementById("btn-connect");
    const btnPing = document.getElementById("btn-test-ping");
    const connResult = document.getElementById("conn-result");
    const pingResult = document.getElementById("ping-result");
    const statusText = document.getElementById("status-text");
    const statusPill = document.getElementById("global-status");

    const proto = document.getElementById("conn-proto").value;
    const devId = document.getElementById("conn-device-select").value || "custom";
    const dev = inventoryDevices.find(d => d.id === devId);
    const devName = dev ? (dev.name || dev.id) : devId;

    const payload = {
        connection_type: proto,
        ip: document.getElementById("conn-ip").value,
        port: parseInt(document.getElementById("conn-port").value) || (proto === "SSH" ? 22 : 23),
        username: document.getElementById("conn-user").value,
        password: document.getElementById("conn-pass").value,
        secret: document.getElementById("conn-secret").value,
        serial_port: document.getElementById("conn-serial-port").value,
        baudrate: parseInt(document.getElementById("conn-baud").value) || 9600,
        skip_ping: false,
    };

    const targetDetail = proto === "SERIAL"
        ? (payload.serial_port || "COM Port")
        : `${payload.ip || devName}:${payload.port}`;

    if (pingResult) pingResult.classList.add("d-none");

    // 1. ระหว่างรอ connect: แสดงสถานะว่า "กำลังเชื่อมต่อ..."
    if (btnConnect) {
        btnConnect.disabled = true;
        btnConnect.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> กำลังเชื่อมต่อ...';
    }
    if (btnPing) btnPing.disabled = true;

    if (connResult) {
        connResult.className = "conn-result-box connecting";
        connResult.innerHTML = `
            <i class="fa-solid fa-circle-notch fa-spin"></i>
            <div>
                <div style="font-weight:600">กำลังเชื่อมต่อ...</div>
                <div style="font-size:12px;opacity:0.9">กำลังเชื่อมต่อไปยัง <strong>${devName}</strong> (${targetDetail}) ผ่าน ${proto} กรุณารอสักครู่</div>
            </div>
        `;
        connResult.classList.remove("d-none");
    }

    if (statusText) statusText.textContent = `กำลังเชื่อมต่อ ${devName}...`;
    if (statusPill) {
        statusPill.style.background = "rgba(59, 130, 246, 0.15)";
        statusPill.style.borderColor = "rgba(59, 130, 246, 0.4)";
        statusPill.style.color = "#60a5fa";
    }

    showNotification(`กำลังเชื่อมต่อกับ ${devName} (${targetDetail})...`, "info");

    try {
        const res = await fetch(`/api/connect/${devId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            // 2. เชื่อมต่อได้แล้ว!
            if (connResult) {
                connResult.className = "conn-result-box success";
                connResult.innerHTML = `
                    <i class="fa-solid fa-circle-check"></i>
                    <div>
                        <div style="font-weight:600">เชื่อมต่อได้แล้ว!</div>
                        <div style="font-size:12px;opacity:0.9">${data.message || 'เชื่อมต่ออุปกรณ์สำเร็จ'}</div>
                    </div>
                `;
            }
            if (btnConnect) {
                btnConnect.innerHTML = '<i class="fa-solid fa-check"></i> เชื่อมต่อได้แล้ว';
            }
            showNotification(`เชื่อมต่อได้แล้ว! (${devName})`, "success");

            await loadInventory();
            await loadActiveConnections();
            if (dev && dev.id) {
                selectActiveDevice(dev.id);
            }
        } else {
            // 3. เชื่อมต่อผิดพลาด
            const errorMsg = data.message || "ไม่สามารถเชื่อมต่ออุปกรณ์ได้";
            if (connResult) {
                connResult.className = "conn-result-box fail";
                connResult.innerHTML = `
                    <i class="fa-solid fa-circle-xmark"></i>
                    <div>
                        <div style="font-weight:600">เชื่อมต่อผิดพลาด</div>
                        <div style="font-size:12px;opacity:0.9">${errorMsg}</div>
                    </div>
                `;
            }
            if (btnConnect) {
                btnConnect.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> เชื่อมต่อผิดพลาด';
            }
            showNotification(`เชื่อมต่อผิดพลาด: ${errorMsg}`, "error");
            await loadActiveConnections();
        }
    } catch (err) {
        // Network / Server error
        const errorMsg = err.message || "ไม่สามารถติดต่อ Server ได้";
        if (connResult) {
            connResult.className = "conn-result-box fail";
            connResult.innerHTML = `
                <i class="fa-solid fa-circle-xmark"></i>
                <div>
                    <div style="font-weight:600">เชื่อมต่อผิดพลาด</div>
                    <div style="font-size:12px;opacity:0.9">${errorMsg}</div>
                </div>
            `;
        }
        if (btnConnect) {
            btnConnect.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> เชื่อมต่อผิดพลาด';
        }
        showNotification(`เชื่อมต่อผิดพลาด: ${errorMsg}`, "error");
        await loadActiveConnections();
    } finally {
        if (btnConnect) {
            btnConnect.disabled = false;
            setTimeout(() => {
                btnConnect.innerHTML = '<i class="fa-solid fa-plug"></i> Connect';
            }, 3500);
        }
        if (btnPing) btnPing.disabled = false;
    }
}

async function loadActiveConnections() {
    try {
        const res = await fetch("/api/connections");
        const data = await res.json();
        const list = document.getElementById("active-connections-list");
        const statusPill = document.getElementById("global-status");
        const statusText = document.getElementById("status-text");

        if (!data.connected || !data.connected.length) {
            if (list) list.innerHTML = '<div style="font-size:12px;color:var(--text-dim)">No active connections (Simulation Mode)</div>';
            if (statusText) statusText.textContent = "Simulation Mode (No Live Device)";
            if (statusPill) {
                statusPill.style.background = "rgba(100, 116, 139, 0.15)";
                statusPill.style.borderColor = "rgba(100, 116, 139, 0.3)";
                statusPill.style.color = "var(--text-muted)";
            }
            return;
        }

        const count = data.connected.length;
        if (statusText) statusText.textContent = `Live Connected (${count} ${count > 1 ? 'Devices' : 'Device'})`;
        if (statusPill) {
            statusPill.style.background = "rgba(16, 185, 129, 0.15)";
            statusPill.style.borderColor = "rgba(16, 185, 129, 0.4)";
            statusPill.style.color = "var(--success)";
        }

        if (!list) return;
        list.innerHTML = "";
        data.connected.forEach(c => {
            const item = document.createElement("div");
            item.className = "active-conn-item";
            item.innerHTML = `
                <span><i class="fa-solid fa-circle text-success" style="font-size:8px"></i> <strong>${c.id}</strong> — ${c.type}</span>
                <button class="btn btn-sm btn-outline" onclick="disconnectDevice('${c.id}')">Disconnect</button>
            `;
            list.appendChild(item);
        });
    } catch (e) { }
}

async function disconnectDevice(deviceId) {
    const res = await fetch(`/api/disconnect/${deviceId}`, { method: "POST" });
    const data = await res.json();
    showNotification(data.message, data.success ? "success" : "error");
    const connResult = document.getElementById("conn-result");
    if (connResult) {
        connResult.className = "conn-result-box";
        connResult.classList.add("d-none");
    }
    await loadInventory();
    await loadActiveConnections();
}

// =============================================================================
// TOPOLOGY — vis-network (Bonus)
// =============================================================================
async function runAutoDiscovery() {
    const loading = document.getElementById("topo-loading");
    if (loading) loading.classList.remove("d-none");
    try {
        const res = await fetch("/api/topology/json?refresh=1");
        const data = await res.json();
        if (data.success) {
            renderVisNetwork(data.nodes || [], data.edges || []);
            const nodeBadge = document.getElementById("node-count-badge");
            const edgeBadge = document.getElementById("edge-count-badge");
            if (nodeBadge) nodeBadge.textContent = `${(data.nodes || []).length} Devices`;
            if (edgeBadge) edgeBadge.textContent = `${(data.edges || []).length} Links`;
            showNotification(`Auto-Discover สำเร็จ (${(data.nodes || []).length} Devices, ${(data.edges || []).length} Links)`, "success");
        } else {
            showNotification("Auto-Discovery ไม่พบข้อมูล", "warning");
        }
    } catch (e) {
        console.error("Auto-discovery failed:", e);
        showNotification(`Auto-Discovery ล้มเหลว: ${e.message}`, "error");
    } finally {
        if (loading) loading.classList.add("d-none");
    }
}

async function refreshTopology() {
    const btn = document.getElementById("btn-refresh-topo");
    const loading = document.getElementById("topo-loading");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i> Refreshing...';
    }
    if (loading) loading.classList.remove("d-none");
    try {
        const res = await fetch("/api/topology/json?refresh=1");
        const data = await res.json();
        if (data.success) {
            renderVisNetwork(data.nodes || [], data.edges || []);
            const nodeBadge = document.getElementById("node-count-badge");
            const edgeBadge = document.getElementById("edge-count-badge");
            if (nodeBadge) nodeBadge.textContent = `${(data.nodes || []).length} Devices`;
            if (edgeBadge) edgeBadge.textContent = `${(data.edges || []).length} Links`;
            showNotification(`รีเฟรช Topology สำเร็จ (${(data.nodes || []).length} Devices, ${(data.edges || []).length} Links)`, "success");
        } else {
            showNotification("ไม่สามารถรีเฟรช Topology ได้", "error");
        }
    } catch (e) {
        console.error("Refresh topology failed:", e);
        showNotification(`รีเฟรช Topology ล้มเหลว: ${e.message}`, "error");
    } finally {
        if (loading) loading.classList.add("d-none");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Refresh';
        }
    }
}

function renderVisNetwork(nodes, edges) {
    const container = document.getElementById("topology-container");
    if (!container || typeof vis === "undefined") return;

    const nodeColor = (type) => {
        if (type === "router") return { background: "#1e3a5f", border: "#3b82f6", highlight: { background: "#2563eb", border: "#60a5fa" } };
        if (type === "switch") return { background: "#1a3a2a", border: "#10b981", highlight: { background: "#059669", border: "#34d399" } };
        if (type === "network" || type === "cloud") return { background: "#1e293b", border: "#38bdf8", highlight: { background: "#334155", border: "#7dd3fc" } };
        return { background: "#2d1a3a", border: "#a855f7", highlight: { background: "#7c3aed", border: "#c084fc" } };
    };

    const visNodes = new vis.DataSet(nodes.map(n => {
        const isNet = (n.type === "network" || n.type === "cloud");
        const nodeObj = {
            id: n.id,
            label: `${n.name}\n${n.ip || ''}`,
            shape: n.type === "switch" ? "database" : (isNet ? "box" : "hexagon"),
            color: nodeColor(n.type),
            font: { color: "#f8fafc", size: isNet ? 11 : 12, face: "Inter" },
            borderWidth: n.id === activeDeviceId ? 3 : 1.5,
            shadow: { enabled: true, color: "rgba(0,0,0,0.5)", size: 8 },
        };
        if (isNet) {
            nodeObj.margin = 12;
            nodeObj.shapeProperties = { borderRadius: 6 };
        }
        return nodeObj;
    }));

    const formatPort = (p) => {
        if (!p) return "";
        return p.replace("GigabitEthernet", "Gi")
                .replace("FastEthernet", "Fa")
                .replace("Ethernet", "e")
                .replace("Serial", "Se");
    };

    const visEdges = new vis.DataSet(edges.map((e, idx) => {
        let label = "";
        let fromPart = formatPort(e.from_port);
        let toPart = formatPort(e.to_port);

        if (fromPart && toPart) {
            // Direct router-to-router link: e.g. e0/1 ↔ e0/1
            label = `${fromPart} ↔ ${toPart}`;
            if (e.from_ip && e.to_ip) {
                label += `\n${e.from_ip} ↔ ${e.to_ip}`;
            }
        } else if (fromPart) {
            // Router-to-Network link: e.g. e0/0
            label = fromPart;
            if (e.from_ip) {
                label += ` (${e.from_ip})`;
            }
        }

        // Tooltip title
        let title = `${e.from} ↔ ${e.to}`;
        if (e.subnet) title += `\nSubnet: ${e.subnet}`;
        if (e.method) title += `\nDiscovery: ${e.method}`;
        return {
            id: `edge_${e.from}_${e.to}_${idx}`,
            from: e.from, to: e.to,
            label: label,
            title: title,
            color: { color: e.status === "up" ? "#10b981" : "#ef4444", highlight: "#38bdf8" },
            dashes: Boolean(e.from_port && e.from_port.includes("Serial")),
            width: 2.5,
            smooth: { enabled: true, type: 'curvedCW', roundness: 0.15 * (idx % 2 === 0 ? 1 : -1) },
            font: {
                color: "#cbd5e1",
                size: 9.5,
                align: "middle",
                background: "#0f172a", // Dark badge behind edge label so line doesn't cross text
                strokeWidth: 0,
            },
        };
    }));

    const options = {
        physics: {
            enabled: true,
            solver: "repulsion",
            repulsion: {
                nodeDistance: 170,
                springLength: 170,
                springConstant: 0.05,
                damping: 0.09,
            },
            stabilization: {
                iterations: 100,
            }
        },
        interaction: { hover: true, tooltipDelay: 200, zoomView: true, dragView: true },
        nodes: { size: 30 },
        edges: {
            smooth: {
                type: "continuous",
                roundness: 0.2
            }
        },
        background: { color: "transparent" },
    };

    if (topoNetwork) { topoNetwork.destroy(); }
    topoNetwork = new vis.Network(container, { nodes: visNodes, edges: visEdges }, options);

    topoNetwork.once("stabilizationIterationsDone", () => {
        topoNetwork.fit({ animation: { duration: 500, easingFunction: "easeInOutQuad" } });
    });

    // Click on node → switch active device
    topoNetwork.on("click", (params) => {
        if (params.nodes.length > 0) {
            selectActiveDevice(params.nodes[0]);
            // Highlight selected node
            visNodes.update(nodes.map(n => ({
                id: n.id,
                borderWidth: n.id === params.nodes[0] ? 3 : 1.5,
            })));
        }
    });
    // Double-click → open device drawer (Packet Tracer style)
    topoNetwork.on("doubleClick", (params) => {
        if (params.nodes.length > 0) {
            selectActiveDevice(params.nodes[0]);
            openDeviceDrawer(params.nodes[0]);
        }
    });
}

// =============================================================================
// INTERFACE CONFIGURATION
// =============================================================================
function updateInterfaceOptions() {
    // ใช้ cache จากข้อมูลที่ดึงมาแล้ว — ไม่ต้องไปเรียก Router ซ้ำ
    const sel = document.getElementById("if-select");
    if (!sel) return;

    const cached = cachedInterfaces[activeDeviceId];
    if (cached && cached.length > 0) {
        // มี cache → populate dropdown จาก cache ทันที
        sel.innerHTML = "";
        cached.forEach(iface => {
            const opt = document.createElement("option");
            opt.value = iface.name;
            opt.textContent = iface.name;
            if (iface.name === selectedInterfaceName) opt.selected = true;
            sel.appendChild(opt);
        });
        updateIfPreview();
    } else {
        // ยังไม่มี cache → fallback hardcoded
        const dev = inventoryDevices.find(d => d.id === activeDeviceId);
        const isSwitch = dev && dev.device_type_label === "switch";
        const ifList = isSwitch
            ? ["FastEthernet0/1", "FastEthernet0/2", "FastEthernet0/3", "FastEthernet0/4", "GigabitEthernet0/1", "Vlan1", "Vlan10", "Vlan20"]
            : ["Ethernet0/0", "Ethernet0/1", "Ethernet0/2", "Ethernet0/3", "Loopback0"];
        sel.innerHTML = "";
        ifList.forEach(name => {
            const opt = document.createElement("option");
            opt.value = name; opt.textContent = name;
            sel.appendChild(opt);
        });
        updateIfPreview();
    }
}

function toggleIpMode(mode) {
    const radio = document.querySelector(`input[name='if-ip-mode'][value='${mode}']`);
    if (radio) radio.checked = true;

    const ipInput = document.getElementById("if-ip");
    const maskInput = document.getElementById("if-mask");
    const maskGroup = document.getElementById("if-mask-group");

    if (mode === "dhcp") {
        if (ipInput) {
            ipInput.value = "DHCP";
            ipInput.readOnly = true;
            ipInput.style.backgroundColor = "rgba(56, 189, 248, 0.08)";
            ipInput.style.color = "#38bdf8";
            ipInput.style.fontWeight = "600";
        }
        if (maskInput) {
            maskInput.disabled = true;
            maskInput.value = "";
            maskInput.placeholder = "Auto via DHCP";
        }
        if (maskGroup) {
            maskGroup.style.opacity = "0.4";
            maskGroup.style.pointerEvents = "none";
        }
    } else if (mode === "none") {
        if (ipInput) {
            ipInput.value = "no ip address";
            ipInput.readOnly = true;
            ipInput.style.backgroundColor = "rgba(239, 68, 68, 0.08)";
            ipInput.style.color = "#f87171";
            ipInput.style.fontWeight = "600";
        }
        if (maskInput) {
            maskInput.disabled = true;
            maskInput.value = "";
            maskInput.placeholder = "Disabled (no ip)";
        }
        if (maskGroup) {
            maskGroup.style.opacity = "0.4";
            maskGroup.style.pointerEvents = "none";
        }
    } else {
        if (ipInput) {
            const v = ipInput.value.toLowerCase().trim();
            if (v === "dhcp" || v.startsWith("no ip")) {
                ipInput.value = "";
            }
            ipInput.readOnly = false;
            ipInput.style.backgroundColor = "";
            ipInput.style.color = "";
            ipInput.style.fontWeight = "";
            ipInput.placeholder = "192.168.1.1";
        }
        if (maskInput) {
            maskInput.disabled = false;
            if (!maskInput.value) maskInput.value = "255.255.255.0";
            maskInput.placeholder = "255.255.255.0";
        }
        if (maskGroup) {
            maskGroup.style.opacity = "1";
            maskGroup.style.pointerEvents = "auto";
        }
    }
    updateIfPreview();
}

function onIpAddressInput() {
    const ipInput = document.getElementById("if-ip");
    const val = ipInput?.value?.trim().toLowerCase();
    if (val === "dhcp") {
        toggleIpMode("dhcp");
    } else if (val === "no" || val === "no ip" || val === "no ip add" || val === "no ip address") {
        toggleIpMode("none");
    } else {
        const currentMode = document.querySelector("input[name='if-ip-mode']:checked")?.value;
        if (currentMode === "dhcp" || currentMode === "none") {
            const staticRadio = document.querySelector("input[name='if-ip-mode'][value='static']");
            if (staticRadio) staticRadio.checked = true;
            const maskInput = document.getElementById("if-mask");
            if (maskInput) {
                maskInput.disabled = false;
                if (!maskInput.value) maskInput.value = "255.255.255.0";
            }
            const maskGroup = document.getElementById("if-mask-group");
            if (maskGroup) {
                maskGroup.style.opacity = "1";
                maskGroup.style.pointerEvents = "auto";
            }
        }
        updateIfPreview();
    }
}

function updateIfPreview() {
    const iface = document.getElementById("if-select")?.value || "Ethernet0/0";
    const ip = document.getElementById("if-ip")?.value?.trim() || "";
    const mask = document.getElementById("if-mask")?.value?.trim() || "255.255.255.0";
    const desc = document.getElementById("if-desc")?.value || "";
    const stateEl = document.querySelector("input[name='if-state']:checked");
    const state = stateEl ? stateEl.value : "up";
    const mode = document.querySelector("input[name='if-ip-mode']:checked")?.value || (ip.toLowerCase() === "dhcp" ? "dhcp" : (ip.toLowerCase().startsWith("no ip") ? "none" : "static"));

    let lines = ["configure terminal", `interface ${iface}`];
    if (desc) lines.push(` description ${desc}`);
    if (mode === "dhcp" || ip.toLowerCase() === "dhcp") {
        lines.push(" ip address dhcp");
    } else if (mode === "none" || ip.toLowerCase() === "no ip address" || ip.toLowerCase() === "no ip add" || ip.toLowerCase() === "no") {
        lines.push(" no ip address");
    } else if (ip) {
        lines.push(` ip address ${ip} ${mask}`);
    }
    lines.push(state === "up" ? " no shutdown" : " shutdown");
    lines.push("end");

    const pre = document.getElementById("if-cli-preview");
    if (pre) pre.textContent = lines.join("\n");
}

async function submitInterfaceConfig(e) {
    e.preventDefault();
    const btn = document.querySelector("#tab-if button[type='submit']") || document.getElementById("btn-deploy-if");
    const origText = btn ? btn.innerHTML : "";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Deploying...`;
    }

    const ifSelect = document.getElementById("if-select");
    const mode = document.querySelector("input[name='if-ip-mode']:checked")?.value;
    const ipVal = document.getElementById("if-ip")?.value?.trim() || "";
    const isDhcp = mode === "dhcp" || ipVal.toLowerCase() === "dhcp";
    const isNoIp = mode === "none" || ipVal.toLowerCase().startsWith("no ip") || ipVal.toLowerCase() === "no";

    const payload = {
        device_id: activeDeviceId,
        interface: ifSelect ? ifSelect.value : "",
        ip: isDhcp ? "dhcp" : (isNoIp ? "no ip address" : ipVal),
        mask: (isDhcp || isNoIp) ? "" : (document.getElementById("if-mask")?.value || "255.255.255.0"),
        description: document.getElementById("if-desc")?.value || "",
        state: document.querySelector("input[name='if-state']:checked")?.value || "up",
    };

    try {
        const res = await fetch("/api/config/interface", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showNotification(data.message || `Interface ${payload.interface} configured!`, "success");
            appendConsole(data.output || data.message, "output-line");
            await refreshInterfaceTable(true);
            runAutoDiscovery();
        } else {
            showNotification(data.message || data.output || "Config failed", "error");
            appendConsole(data.output || data.message, "error-line");
            await refreshInterfaceTable(true);
        }
    } catch (err) {
        showNotification("Request error: " + err, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origText;
        }
    }
}

// =============================================================================
// ROUTING PROTOCOL — Dynamic Network Rows
// =============================================================================
function initRoutingRows() {
    addNetworkRow("rip");
    addNetworkRow("eigrp");
    addNetworkRow("ospf");
    addNetworkRow("bgp");
    addNeighborRow();
    setRoutingType("static");
}

function setRoutingType(type) {
    document.querySelectorAll(".route-type-btn").forEach(btn => {
        btn.classList.toggle("active", btn.textContent.toLowerCase().startsWith(type));
    });
    document.getElementById("routing-type-input").value = type;
    document.querySelectorAll(".routing-fields").forEach(d => d.classList.add("d-none"));
    const fields = document.getElementById(`routing-fields-${type}`);
    if (fields) fields.classList.remove("d-none");
    toggleRedistributionPanel(type);
    updateRoutingPreview();
}

function addNetworkRow(proto) {
    const container = document.getElementById(`${proto}-networks-container`);
    if (!container) return;
    const row = document.createElement("div");
    row.className = "network-row";
    if (proto === "rip") {
        row.innerHTML = `
            <input type="text" class="form-control rip-net" placeholder="10.1.1.0" oninput="updateRoutingPreview()">
            <button type="button" class="remove-row-btn" onclick="removeRow(this)"><i class="fa-solid fa-minus"></i></button>`;
    } else if (proto === "eigrp") {
        row.innerHTML = `
            <input type="text" class="form-control eigrp-net" placeholder="10.1.1.0" oninput="updateRoutingPreview()">
            <input type="text" class="form-control eigrp-wild" placeholder="0.0.0.255" oninput="updateRoutingPreview()" style="max-width:130px">
            <button type="button" class="remove-row-btn" onclick="removeRow(this)"><i class="fa-solid fa-minus"></i></button>`;
    } else if (proto === "ospf") {
        row.innerHTML = `
            <input type="text" class="form-control ospf-net" placeholder="10.1.1.0" oninput="updateRoutingPreview()">
            <input type="text" class="form-control ospf-wild" placeholder="0.0.0.3" oninput="updateRoutingPreview()" style="max-width:100px">
            <input type="number" class="form-control ospf-area" placeholder="0" value="0" oninput="updateRoutingPreview()" style="max-width:60px">
            <button type="button" class="remove-row-btn" onclick="removeRow(this)"><i class="fa-solid fa-minus"></i></button>`;
    } else if (proto === "bgp") {
        row.innerHTML = `
            <input type="text" class="form-control bgp-net" placeholder="192.168.1.0" oninput="updateRoutingPreview()">
            <input type="text" class="form-control bgp-net-mask" placeholder="255.255.255.0" oninput="updateRoutingPreview()" style="max-width:140px">
            <button type="button" class="remove-row-btn" onclick="removeRow(this)"><i class="fa-solid fa-minus"></i></button>`;
    }
    container.appendChild(row);
    updateRoutingPreview();
}

function addNeighborRow() {
    const container = document.getElementById("bgp-neighbors-container");
    if (!container) return;
    const row = document.createElement("div");
    row.className = "network-row";
    row.innerHTML = `
        <input type="text" class="form-control bgp-neigh-ip" placeholder="10.1.1.2" oninput="updateRoutingPreview()">
        <input type="number" class="form-control bgp-neigh-as" placeholder="65002" oninput="updateRoutingPreview()" style="max-width:100px">
        <button type="button" class="remove-row-btn" onclick="removeRow(this)"><i class="fa-solid fa-minus"></i></button>`;
    container.appendChild(row);
    updateRoutingPreview();
}

function removeRow(btn) {
    btn.closest(".network-row").remove();
    updateRoutingPreview();
}

function updateRoutingPreview() {
    const type = document.getElementById("routing-type-input")?.value || "static";
    let lines = ["configure terminal"];

    if (type === "static") {
        const net = document.getElementById("st-net")?.value || "10.2.2.0";
        const mask = document.getElementById("st-mask")?.value || "255.255.255.0";
        const next = document.getElementById("st-next")?.value || "10.1.1.2";
        lines.push(`ip route ${net} ${mask} ${next}`);
    } else if (type === "default") {
        const next = document.getElementById("def-next")?.value || "192.168.1.1";
        lines.push(`ip route 0.0.0.0 0.0.0.0 ${next}`);
    } else if (type === "rip") {
        lines.push("router rip", " version 2");
        document.querySelectorAll(".rip-net").forEach(el => {
            if (el.value.trim()) lines.push(` network ${el.value.trim()}`);
        });
        lines.push(" no auto-summary");
    } else if (type === "eigrp") {
        const as = document.getElementById("eigrp-as")?.value || "100";
        lines.push(`router eigrp ${as}`);
        document.querySelectorAll("#eigrp-networks-container .network-row").forEach(row => {
            const net = row.querySelector(".eigrp-net")?.value.trim();
            const wild = row.querySelector(".eigrp-wild")?.value.trim() || "0.0.0.255";
            if (net) lines.push(` network ${net} ${wild}`);
        });
        lines.push(" no auto-summary");
    } else if (type === "ospf") {
        const pid = document.getElementById("ospf-pid")?.value || "1";
        const rid = document.getElementById("ospf-rid")?.value.trim();
        lines.push(`router ospf ${pid}`);
        if (rid) lines.push(` router-id ${rid}`);
        document.querySelectorAll("#ospf-networks-container .network-row").forEach(row => {
            const net = row.querySelector(".ospf-net")?.value.trim();
            const wild = row.querySelector(".ospf-wild")?.value.trim() || "0.0.0.255";
            const area = row.querySelector(".ospf-area")?.value || "0";
            if (net) lines.push(` network ${net} ${wild} area ${area}`);
        });
    } else if (type === "bgp") {
        const as = document.getElementById("bgp-as")?.value || "65001";
        lines.push(`router bgp ${as}`);
        document.querySelectorAll("#bgp-neighbors-container .network-row").forEach(row => {
            const ip = row.querySelector(".bgp-neigh-ip")?.value.trim();
            const ras = row.querySelector(".bgp-neigh-as")?.value.trim();
            if (ip && ras) lines.push(` neighbor ${ip} remote-as ${ras}`);
        });
        document.querySelectorAll("#bgp-networks-container .network-row").forEach(row => {
            const net = row.querySelector(".bgp-net")?.value.trim();
            const mask = row.querySelector(".bgp-net-mask")?.value.trim() || "255.255.255.0";
            if (net) lines.push(` network ${net} mask ${mask}`);
        });
    }

    if (["rip", "eigrp", "ospf", "bgp"].includes(type)) {
        const redist = getRedistributePayload() || [];
        redist.forEach(entry => {
            let cmd = ` redistribute ${entry.source}`;
            if (type === "ospf" && entry.subnets) cmd += " subnets";
            if (entry.metric) cmd += ` metric ${entry.metric}`;
            lines.push(cmd);
        });
        const defOrig = getDefaultOriginatePayload();
        if (defOrig) {
            let cmd = " default-information originate";
            if (type === "ospf" && defOrig.always) cmd += " always";
            if (type === "bgp") cmd = " network 0.0.0.0 mask 0.0.0.0";
            lines.push(cmd);
        }
        lines.push("exit");
    }
    lines.push("end");
    const pre = document.getElementById("routing-cli-preview");
    if (pre) pre.textContent = lines.join("\n");
}

async function submitRoutingConfig(e) {
    e.preventDefault();
    const type = document.getElementById("routing-type-input").value;
    let payload = { device_id: activeDeviceId, route_type: type };

    if (type === "static") {
        payload.network = document.getElementById("st-net").value;
        payload.mask = document.getElementById("st-mask").value;
        payload.next_hop = document.getElementById("st-next").value;
    } else if (type === "default") {
        payload.next_hop = document.getElementById("def-next").value;
    } else if (type === "rip") {
        payload.networks = Array.from(document.querySelectorAll(".rip-net")).map(el => el.value.trim()).filter(Boolean);
    } else if (type === "eigrp") {
        payload.as_num = parseInt(document.getElementById("eigrp-as").value) || 100;
        payload.networks = Array.from(document.querySelectorAll("#eigrp-networks-container .network-row")).map(row => ({
            network: row.querySelector(".eigrp-net")?.value.trim(),
            wildcard: row.querySelector(".eigrp-wild")?.value.trim() || "0.0.0.255",
        })).filter(n => n.network);
    } else if (type === "ospf") {
        payload.process_id = parseInt(document.getElementById("ospf-pid").value) || 1;
        payload.router_id = document.getElementById("ospf-rid").value.trim();
        payload.networks = Array.from(document.querySelectorAll("#ospf-networks-container .network-row")).map(row => ({
            network: row.querySelector(".ospf-net")?.value.trim(),
            wildcard: row.querySelector(".ospf-wild")?.value.trim() || "0.0.0.255",
            area: parseInt(row.querySelector(".ospf-area")?.value) || 0,
        })).filter(n => n.network);
    } else if (type === "bgp") {
        payload.as_num = parseInt(document.getElementById("bgp-as").value) || 65001;
        payload.neighbors = Array.from(document.querySelectorAll("#bgp-neighbors-container .network-row")).map(row => ({
            ip: row.querySelector(".bgp-neigh-ip")?.value.trim(),
            remote_as: parseInt(row.querySelector(".bgp-neigh-as")?.value) || 0,
        })).filter(n => n.ip && n.remote_as);
        payload.networks = Array.from(document.querySelectorAll("#bgp-networks-container .network-row")).map(row => ({
            network: row.querySelector(".bgp-net")?.value.trim(),
            mask: row.querySelector(".bgp-net-mask")?.value.trim() || "255.255.255.0",
        })).filter(n => n.network);
    }

    if (["rip", "eigrp", "ospf", "bgp"].includes(type)) {
        const redist = getRedistributePayload();
        if (redist) payload.redistribute = redist;
        const defOrig = getDefaultOriginatePayload();
        if (defOrig) payload.default_originate = defOrig;
    }

    const res = await fetch("/api/config/routing", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
        showNotification(`${type.toUpperCase()} routing deployed!`, "success");
        appendConsole(data.output, "output-line");
    } else {
        showNotification(data.message || "Routing config failed", "error");
        appendConsole(data.output || data.message, "error-line");
    }
}

// =============================================================================
// SHOW COMMANDS
// =============================================================================
async function runShow(cmd) {
    const outputBox = document.getElementById("show-output-box");
    outputBox.textContent = `Running '${cmd}' on ${activeDeviceId}...`;
    const res = await fetch("/api/show", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: activeDeviceId, command: cmd })
    });
    const data = await res.json();
    outputBox.textContent = data.output || data.message || "No output";
}

function copyShowOutput() {
    navigator.clipboard.writeText(document.getElementById("show-output-box").textContent);
    showNotification("Copied to clipboard!", "success");
}

// =============================================================================
// CISCO IOS & LINUX PC REALTIME CLI & HELP GUIDE ENGINE
// =============================================================================
let cliMode = "exec"; // "exec", "user", "config", "config_if", "config_router"
let cliContext = [];  // context stack e.g. ["interface Ethernet0/0"]
let cliSubmodeLabel = "";
let cliCustomHostname = null;

function isCurrentDeviceLinux() {
    const dev = inventoryDevices.find(d => d.id === activeDeviceId);
    return !!(dev && (dev.device_type_label === "pc" || (dev.model || "").toLowerCase().includes("linux") || (dev.model || "").toLowerCase().includes("ubuntu")));
}

const LINUX_HELP_DATABASE = {
    title: "Linux / Ubuntu system & network commands:",
    commands: [
        { cmd: "ip", desc: "Show / manipulate routing, network devices, interfaces" },
        { cmd: "ifconfig", desc: "Configure a network interface (net-tools)" },
        { cmd: "ping", desc: "Send ICMP ECHO_REQUEST to network hosts" },
        { cmd: "traceroute", desc: "Print the route packets trace to network host" },
        { cmd: "sudo", desc: "Execute a command as another user / superuser" },
        { cmd: "apt", desc: "Command-line package manager (install, update)" },
        { cmd: "systemctl", desc: "Control the systemd system and service manager" },
        { cmd: "cat", desc: "Concatenate files and print on the standard output" },
        { cmd: "uname", desc: "Print system information (-a for kernel)" },
        { cmd: "whoami", desc: "Print effective user ID" },
        { cmd: "hostname", desc: "Show or set the system's host name (-I for IPs)" },
        { cmd: "ss", desc: "Another utility to investigate sockets (-tuln)" },
        { cmd: "netstat", desc: "Print network connections, routing tables" },
        { cmd: "df", desc: "Report file system disk space usage (-h)" },
        { cmd: "free", desc: "Display amount of free and used memory in the system (-m)" },
        { cmd: "ps", desc: "Report a snapshot of the current processes (aux)" },
        { cmd: "top", desc: "Display Linux processes" },
        { cmd: "ls", desc: "List directory contents (-la)" },
        { cmd: "pwd", desc: "Print name of current/working directory" },
        { cmd: "clear", desc: "Clear the terminal screen" }
    ],
    sub: {
        "ip": [
            { cmd: "addr", desc: "Protocol address management (ip a / ip addr)" },
            { cmd: "-br addr", desc: "Brief network addresses and status" },
            { cmd: "route", desc: "Routing table management (ip r / ip route)" },
            { cmd: "link", desc: "Network device configuration (ip link)" },
            { cmd: "neigh", desc: "Neighbour / ARP table (ip neigh)" }
        ],
        "sudo": [
            { cmd: "apt update", desc: "Update list of available packages" },
            { cmd: "apt install net-tools", desc: "Install network utilities" },
            { cmd: "systemctl status ssh", desc: "Check status of SSH daemon" },
            { cmd: "systemctl restart ssh", desc: "Restart SSH service" },
            { cmd: "-i", desc: "Simulate initial login (root shell)" }
        ],
        "cat": [
            { cmd: "/etc/os-release", desc: "Operating system distribution information" },
            { cmd: "/etc/netplan/*.yaml", desc: "Netplan network configuration file" },
            { cmd: "/etc/resolv.conf", desc: "DNS resolver configuration" }
        ],
        "systemctl": [
            { cmd: "status ssh", desc: "Check SSH server status" },
            { cmd: "restart ssh", desc: "Restart SSH daemon" },
            { cmd: "status networking", desc: "Check networking status" }
        ]
    }
};

function resolveLinuxHelp(buffer) {
    let clean = (buffer || "").replace(/\?$/, "");
    const trimmed = clean.trim();
    if (!trimmed) {
        return { title: LINUX_HELP_DATABASE.title, items: LINUX_HELP_DATABASE.commands };
    }
    const hasTrailingSpace = clean.endsWith(" ");
    const lowerTrim = trimmed.toLowerCase();
    if (LINUX_HELP_DATABASE.sub && LINUX_HELP_DATABASE.sub[lowerTrim]) {
        return { title: `Options for "${trimmed}":`, items: LINUX_HELP_DATABASE.sub[lowerTrim] };
    }
    if (LINUX_HELP_DATABASE.sub) {
        for (const [key, items] of Object.entries(LINUX_HELP_DATABASE.sub)) {
            if (lowerTrim === key || (hasTrailingSpace && lowerTrim.startsWith(key))) {
                return { title: `Options for "${key}":`, items };
            }
        }
    }
    if (!hasTrailingSpace) {
        const lastWord = lowerTrim.split(/\s+/).pop();
        const matches = LINUX_HELP_DATABASE.commands.filter(c => c.cmd.toLowerCase().startsWith(lastWord));
        if (matches.length > 0) {
            return { title: `Commands starting with "${lastWord}":`, items: matches };
        }
    }
    return {
        title: "Available parameters:",
        items: [
            { cmd: "<cr>", desc: "Execute command" }
        ]
    };
}

const CISCO_HELP_DATABASE = {
    exec: {
        title: "Exec commands:",
        commands: [
            { cmd: "clear", desc: "Reset functions" },
            { cmd: "clock", desc: "Manage the system clock" },
            { cmd: "configure", desc: "Enter configuration mode" },
            { cmd: "connect", desc: "Open a terminal connection" },
            { cmd: "copy", desc: "Copy from one file to another" },
            { cmd: "debug", desc: "Debugging functions" },
            { cmd: "delete", desc: "Delete a file" },
            { cmd: "dir", desc: "List files on a filesystem" },
            { cmd: "disable", desc: "Turn off privileged commands" },
            { cmd: "disconnect", desc: "Disconnect an existing network connection" },
            { cmd: "enable", desc: "Turn on privileged commands" },
            { cmd: "exit", desc: "Exit from the EXEC" },
            { cmd: "help", desc: "Description of the interactive help system" },
            { cmd: "ping", desc: "Send echo messages" },
            { cmd: "reload", desc: "Halt and perform a cold restart" },
            { cmd: "resume", desc: "Resume an active network connection" },
            { cmd: "show", desc: "Show running system information" },
            { cmd: "ssh", desc: "Open a secure shell client connection" },
            { cmd: "telnet", desc: "Open a telnet connection" },
            { cmd: "terminal", desc: "Set terminal line parameters" },
            { cmd: "traceroute", desc: "Trace route to destination" },
            { cmd: "undebug", desc: "Disable debugging functions" },
            { cmd: "write", desc: "Write running configuration to memory, network, or terminal" }
        ],
        sub: {
            "show": [
                { cmd: "arp", desc: "ARP table" },
                { cmd: "cdp", desc: "CDP information" },
                { cmd: "clock", desc: "Display the system clock" },
                { cmd: "debugging", desc: "State of each debugging option" },
                { cmd: "history", desc: "Display the session command history" },
                { cmd: "interfaces", desc: "Interface status and configuration" },
                { cmd: "ip", desc: "IP information" },
                { cmd: "lldp", desc: "LLDP information" },
                { cmd: "protocols", desc: "Active network protocols" },
                { cmd: "running-config", desc: "Current operating configuration" },
                { cmd: "startup-config", desc: "Contents of startup configuration" },
                { cmd: "users", desc: "Display information about terminal lines" },
                { cmd: "version", desc: "System hardware and software status" },
                { cmd: "vlan", desc: "VLAN status" }
            ],
            "sh": [
                { cmd: "interfaces", desc: "Interface status and configuration" },
                { cmd: "ip", desc: "IP information" },
                { cmd: "running-config", desc: "Current operating configuration" },
                { cmd: "route", desc: "IP routing table" },
                { cmd: "version", desc: "System hardware and software status" }
            ],
            "show ip": [
                { cmd: "arp", desc: "IP ARP table" },
                { cmd: "bgp", desc: "BGP information" },
                { cmd: "dhcp", desc: "DHCP information" },
                { cmd: "eigrp", desc: "IP-EIGRP show commands" },
                { cmd: "interface", desc: "IP interface status and configuration" },
                { cmd: "ospf", desc: "OSPF information" },
                { cmd: "protocols", desc: "IP routing protocol process information" },
                { cmd: "rip", desc: "RIP information" },
                { cmd: "route", desc: "IP routing table" }
            ],
            "sh ip": [
                { cmd: "bgp", desc: "BGP information" },
                { cmd: "eigrp", desc: "IP-EIGRP show commands" },
                { cmd: "interface", desc: "IP interface status and configuration" },
                { cmd: "ospf", desc: "OSPF information" },
                { cmd: "route", desc: "IP routing table" }
            ],
            "show ip interface": [
                { cmd: "brief", desc: "Brief summary of IP status and configuration" },
                { cmd: "Ethernet0/0", desc: "Ethernet interface 0/0" },
                { cmd: "Ethernet0/1", desc: "Ethernet interface 0/1" },
                { cmd: "<cr>", desc: "" }
            ],
            "show ip int": [
                { cmd: "brief", desc: "Brief summary of IP status and configuration" },
                { cmd: "<cr>", desc: "" }
            ],
            "sh ip int": [
                { cmd: "brief", desc: "Brief summary of IP status and configuration" },
                { cmd: "<cr>", desc: "" }
            ],
            "show ip route": [
                { cmd: "bgp", desc: "Border Gateway Protocol (BGP)" },
                { cmd: "connected", desc: "Connected routes" },
                { cmd: "eigrp", desc: "Enhanced Interior Gateway Routing Protocol (EIGRP)" },
                { cmd: "ospf", desc: "Open Shortest Path First (OSPF)" },
                { cmd: "rip", desc: "Routing Information Protocol (RIP)" },
                { cmd: "static", desc: "Static routes" },
                { cmd: "<cr>", desc: "" }
            ],
            "show ip ospf": [
                { cmd: "database", desc: "Database summary" },
                { cmd: "interface", desc: "Interface information" },
                { cmd: "neighbor", desc: "Neighbor list" }
            ],
            "show ip eigrp": [
                { cmd: "interfaces", desc: "IP-EIGRP interfaces" },
                { cmd: "neighbors", desc: "IP-EIGRP neighbors" },
                { cmd: "topology", desc: "IP-EIGRP topology table" }
            ],
            "show ip bgp": [
                { cmd: "neighbors", desc: "Detailed information on TCP and BGP neighbors" },
                { cmd: "summary", desc: "Summary of BGP neighbor status" }
            ],
            "configure": [
                { cmd: "terminal", desc: "Configure from the EXEC terminal" },
                { cmd: "<cr>", desc: "" }
            ],
            "conf": [
                { cmd: "terminal", desc: "Configure from the EXEC terminal" }
            ],
            "copy": [
                { cmd: "running-config", desc: "Copy from current operating configuration" },
                { cmd: "startup-config", desc: "Copy from startup configuration" }
            ],
            "copy running-config": [
                { cmd: "startup-config", desc: "Copy to startup configuration" }
            ],
            "clock": [
                { cmd: "set", desc: "Set the time and date" }
            ],
            "ping": [
                { cmd: "WORD", desc: "Ping destination IP address or hostname (e.g. 192.168.74.132)" }
            ],
            "traceroute": [
                { cmd: "WORD", desc: "Trace destination IP address or hostname" }
            ],
            "write": [
                { cmd: "erase", desc: "Erase NVRAM configuration" },
                { cmd: "memory", desc: "Write configuration to memory" },
                { cmd: "terminal", desc: "Display configuration to terminal" },
                { cmd: "<cr>", desc: "" }
            ],
            "wr": [
                { cmd: "erase", desc: "Erase NVRAM configuration" },
                { cmd: "memory", desc: "Write configuration to memory" },
                { cmd: "<cr>", desc: "" }
            ]
        }
    },
    config: {
        title: "Configure commands:",
        commands: [
            { cmd: "banner", desc: "Define a login banner" },
            { cmd: "boot", desc: "Modify system boot parameters" },
            { cmd: "default", desc: "Set a command to its defaults" },
            { cmd: "do", desc: "To run exec commands in config mode" },
            { cmd: "enable", desc: "Modify enable password parameters" },
            { cmd: "end", desc: "Exit to privileged EXEC mode" },
            { cmd: "exit", desc: "Exit from configure mode" },
            { cmd: "hostname", desc: "Set system network name" },
            { cmd: "interface", desc: "Select an interface to configure" },
            { cmd: "ip", desc: "Global IP configuration subcommands" },
            { cmd: "line", desc: "Configure a terminal line" },
            { cmd: "no", desc: "Negate a command or set its defaults" },
            { cmd: "router", desc: "Enable a routing process" },
            { cmd: "service", desc: "Modify use of network based services" },
            { cmd: "username", desc: "Establish User Name Authentication" }
        ],
        sub: {
            "interface": [
                { cmd: "Ethernet0/0", desc: "IEEE 802.3 Ethernet" },
                { cmd: "Ethernet0/1", desc: "IEEE 802.3 Ethernet" },
                { cmd: "FastEthernet0/0", desc: "FastEthernet IEEE 802.3" },
                { cmd: "GigabitEthernet0/0", desc: "GigabitEthernet IEEE 802.3z" },
                { cmd: "Loopback0", desc: "Loopback interface" },
                { cmd: "Serial0/0", desc: "Serial interface" }
            ],
            "int": [
                { cmd: "Ethernet0/0", desc: "IEEE 802.3 Ethernet" },
                { cmd: "Ethernet0/1", desc: "IEEE 802.3 Ethernet" },
                { cmd: "Loopback0", desc: "Loopback interface" }
            ],
            "ip": [
                { cmd: "default-gateway", desc: "Specify default gateway" },
                { cmd: "domain-name", desc: "Define default domain name" },
                { cmd: "route", desc: "Establish static routes" }
            ],
            "ip route": [
                { cmd: "A.B.C.D", desc: "Destination prefix mask (e.g. 10.0.0.0 255.0.0.0 192.168.1.1)" }
            ],
            "router": [
                { cmd: "bgp", desc: "Border Gateway Protocol (BGP)" },
                { cmd: "eigrp", desc: "Enhanced Interior Gateway Routing Protocol (EIGRP)" },
                { cmd: "ospf", desc: "Open Shortest Path First (OSPF)" },
                { cmd: "rip", desc: "Routing Information Protocol (RIP)" }
            ],
            "router ospf": [
                { cmd: "<1-65535>", desc: "Process ID number (e.g. 1)" }
            ],
            "router eigrp": [
                { cmd: "<1-65535>", desc: "Autonomous system number (e.g. 100)" }
            ],
            "router bgp": [
                { cmd: "<1-65535>", desc: "Autonomous system number (e.g. 65000)" }
            ],
            "no": [
                { cmd: "ip", desc: "Global IP configuration subcommands" },
                { cmd: "router", desc: "Enable a routing process" },
                { cmd: "shutdown", desc: "Restart an interface" }
            ],
            "do": [
                { cmd: "show", desc: "Show running system information" },
                { cmd: "ping", desc: "Send echo messages" },
                { cmd: "write", desc: "Write running configuration" }
            ]
        }
    },
    config_if: {
        title: "Interface configuration commands:",
        commands: [
            { cmd: "bandwidth", desc: "Set bandwidth informational parameter" },
            { cmd: "clock", desc: "Configure serial interface clock" },
            { cmd: "description", desc: "Interface specific description" },
            { cmd: "do", desc: "To run exec commands in config mode" },
            { cmd: "duplex", desc: "Configure duplex operation" },
            { cmd: "encapsulation", desc: "Set encapsulation type for an interface" },
            { cmd: "end", desc: "Exit to privileged EXEC mode" },
            { cmd: "exit", desc: "Exit from configure mode" },
            { cmd: "ip", desc: "Interface Internet Protocol config commands" },
            { cmd: "mac-address", desc: "Assign a MAC address to an interface" },
            { cmd: "mtu", desc: "Set the interface Maximum Transmission Unit (MTU)" },
            { cmd: "no", desc: "Negate a command or set its defaults" },
            { cmd: "shutdown", desc: "Shutdown the selected interface" },
            { cmd: "speed", desc: "Configure speed operation" }
        ],
        sub: {
            "ip": [
                { cmd: "address", desc: "Set the IP address of an interface" }
            ],
            "ip address": [
                { cmd: "A.B.C.D", desc: "IP address (e.g. 192.168.1.1 255.255.255.0)" },
                { cmd: "dhcp", desc: "IP Address negotiated via DHCP" }
            ],
            "no": [
                { cmd: "description", desc: "Remove interface description" },
                { cmd: "ip", desc: "Interface Internet Protocol config commands" },
                { cmd: "shutdown", desc: "Restart the selected interface" }
            ],
            "no ip": [
                { cmd: "address", desc: "Remove IP address from interface" }
            ],
            "do": [
                { cmd: "show", desc: "Show running system information" },
                { cmd: "ping", desc: "Send echo messages" }
            ]
        }
    },
    config_router: {
        title: "Router configuration commands:",
        commands: [
            { cmd: "auto-summary", desc: "Enable automatic network number summarization" },
            { cmd: "default-information", desc: "Control distribution of default information" },
            { cmd: "do", desc: "To run exec commands in config mode" },
            { cmd: "end", desc: "Exit to privileged EXEC mode" },
            { cmd: "exit", desc: "Exit from configure mode" },
            { cmd: "neighbor", desc: "Specify a neighbor router" },
            { cmd: "network", desc: "Enable routing on an IP network" },
            { cmd: "no", desc: "Negate a command or set its defaults" },
            { cmd: "redistribute", desc: "Redistribute information from another routing protocol" },
            { cmd: "version", desc: "Set routing protocol version" }
        ],
        sub: {
            "network": [
                { cmd: "A.B.C.D", desc: "Network number (e.g. 192.168.1.0)" }
            ],
            "no": [
                { cmd: "auto-summary", desc: "Disable automatic network summarization" },
                { cmd: "neighbor", desc: "Remove neighbor" },
                { cmd: "network", desc: "Remove network" }
            ],
            "do": [
                { cmd: "show", desc: "Show running system information" }
            ]
        }
    }
};

function focusCliInput() {
    const input = document.getElementById("cli-input");
    if (input) input.focus();
}

function resolveCiscoHelp(buffer, mode) {
    const mData = CISCO_HELP_DATABASE[mode] || CISCO_HELP_DATABASE.exec;
    let clean = (buffer || "").replace(/\?$/, "");
    const trimmed = clean.trim();
    
    if (!trimmed) {
        return { title: mData.title, items: mData.commands };
    }

    const hasTrailingSpace = clean.endsWith(" ");
    const lowerTrim = trimmed.toLowerCase();

    // Check subcommands exact match
    if (mData.sub && mData.sub[lowerTrim]) {
        return { title: `Options for "${trimmed}":`, items: mData.sub[lowerTrim] };
    }

    // Check alias normalization (e.g. "sh" -> "show")
    if (mData.sub) {
        for (const [key, items] of Object.entries(mData.sub)) {
            if (lowerTrim === key || (hasTrailingSpace && lowerTrim.startsWith(key))) {
                return { title: `Options for "${key}":`, items };
            }
        }
    }

    // Prefix search within commands
    if (!hasTrailingSpace) {
        const lastWord = lowerTrim.split(/\s+/).pop();
        const matches = mData.commands.filter(c => c.cmd.toLowerCase().startsWith(lastWord));
        if (matches.length > 0) {
            return { title: `Commands starting with "${lastWord}":`, items: matches };
        }
    }

    return {
        title: "Available parameters:",
        items: [
            { cmd: "<cr>", desc: "Carriage return (Execute command)" }
        ]
    };
}

function formatCiscoHelpTerminal(helpResult) {
    let lines = [];
    if (helpResult.title) lines.push(helpResult.title);
    const maxCmdLen = Math.min(22, Math.max(12, ...helpResult.items.map(it => it.cmd.length + 2)));
    helpResult.items.forEach(it => {
        const padded = it.cmd.padEnd(maxCmdLen, " ");
        lines.push(`  ${padded}  ${it.desc}`);
    });
    return lines.join("\n");
}

function formatCiscoHelpTerminal(helpResult) {
    let lines = [];
    if (helpResult.title) lines.push(helpResult.title);
    const maxCmdLen = Math.min(22, Math.max(12, ...helpResult.items.map(it => it.cmd.length + 2)));
    helpResult.items.forEach(it => {
        const padded = it.cmd.padEnd(maxCmdLen, " ");
        lines.push(`  ${padded}  ${it.desc}`);
    });
    return lines.join("\n");
}

function printCiscoHelpInline(currentBuffer) {
    const prompt = getCliPrompt();
    const input = document.getElementById("cli-input");
    
    // In real Cisco IOS, typing '?' prints prompt + buffer + '?' on that line
    appendCliLine(`${prompt}${currentBuffer}?`);
    
    const helpResult = resolveCiscoHelp(currentBuffer, cliMode);
    const formatted = formatCiscoHelpTerminal(helpResult);
    appendCliOutput(formatted);
    
    // Keep typed buffer intact so user can continue typing seamlessly
    if (input) {
        input.value = currentBuffer;
    }
    
    scrollToBottom();
    focusCliInput();
}

function appendCliLine(text) {
    const linesContainer = document.getElementById("cli-lines");
    if (!linesContainer) return;
    const div = document.createElement("div");
    div.className = "cli-line";
    div.textContent = text;
    linesContainer.appendChild(div);
}

function appendConsole(text, cssClass = "output-line") {
    if (text === undefined || text === null || text === "") return;
    const linesContainer = document.getElementById("cli-lines");
    if (!linesContainer) return;
    const str = String(text);
    const lines = str.split("\n");
    lines.forEach(l => {
        const div = document.createElement("div");
        div.className = "cli-line " + (cssClass || "output-line");
        div.textContent = l;
        linesContainer.appendChild(div);
    });
    scrollToBottom();
}

function appendCliOutput(text) {
    if (text === undefined || text === null) return;
    const linesContainer = document.getElementById("cli-lines");
    if (!linesContainer) return;
    const str = String(text);
    const lines = str.split("\n");
    lines.forEach(l => {
        const div = document.createElement("div");
        div.className = "cli-line";
        div.textContent = l;
        linesContainer.appendChild(div);
    });
    scrollToBottom();
}

function scrollToBottom() {
    const vp = document.getElementById("console-output");
    if (vp) vp.scrollTop = vp.scrollHeight;
}

function focusCliInput() {
    const input = document.getElementById("cli-input");
    if (input) input.focus();
}

function copyConsoleOutput(e) {
    if (e) e.stopPropagation();
    const body = document.getElementById("console-output");
    if (!body) return;
    navigator.clipboard.writeText(body.innerText).then(() => {
        showNotification("Terminal output copied to clipboard", "success");
    }).catch(() => {
        showNotification("Failed to copy", "error");
    });
}

function handleTabAutocomplete() {
    const input = document.getElementById("cli-input");
    if (!input) return;
    const val = input.value.trim();
    if (!val) return;

    if (isCurrentDeviceLinux()) {
        const linuxAlias = {
            "ip a": "ip addr",
            "ip r": "ip route",
            "ip l": "ip link",
            "ifc": "ifconfig",
            "sudo apt up": "sudo apt update",
            "sudo apt in": "sudo apt install -y ",
            "sys": "systemctl status ssh",
            "cat os": "cat /etc/os-release"
        };
        if (linuxAlias[val.toLowerCase()]) {
            input.value = linuxAlias[val.toLowerCase()];
            return;
        }
        const matches = LINUX_HELP_DATABASE.commands.filter(c => c.cmd.toLowerCase().startsWith(val.toLowerCase()));
        if (matches.length === 1) {
            input.value = matches[0].cmd + " ";
            return;
        }
    }

    const aliasMap = {
        "sh": "show ",
        "sh ip": "show ip ",
        "sh ip int": "show ip interface ",
        "sh ip int br": "show ip interface brief",
        "sh run": "show running-config",
        "sh ver": "show version",
        "sh ip ro": "show ip route",
        "conf": "configure terminal",
        "conf t": "configure terminal",
        "int": "interface ",
        "no sh": "no shutdown",
        "ip add": "ip address ",
        "wr": "write memory",
        "wr mem": "write memory"
    };

    if (aliasMap[val.toLowerCase()]) {
        input.value = aliasMap[val.toLowerCase()];
        return;
    }

    const mData = CISCO_HELP_DATABASE[cliMode] || CISCO_HELP_DATABASE.exec;
    const matches = mData.commands.filter(c => c.cmd.toLowerCase().startsWith(val.toLowerCase()));
    if (matches.length === 1) {
        input.value = matches[0].cmd + " ";
    }
}

function handleCliKey(e) {
    const input = document.getElementById("cli-input");
    if (!input) return;

    if (e.key === "?" && !cliIsPasswordMode) {
        e.preventDefault();
        const currentVal = input.value;
        const prompt = getCliPrompt();
        appendCliLine(`${prompt}${currentVal}?`);

        if (isCurrentDeviceLinux()) {
            const helpResult = resolveLinuxHelp(currentVal);
            const formatted = formatCiscoHelpTerminal(helpResult);
            appendCliOutput(formatted);
            input.value = currentVal;
            scrollToBottom();
            focusCliInput();
            return;
        }

        fetch("/api/cli/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_id: activeDeviceId,
                command: `${currentVal}?`
            })
        }).then(r => r.json()).then(data => {
            if (data.output) {
                appendCliOutput(data.output);
            } else if (!data.success) {
                const helpResult = resolveCiscoHelp(currentVal, cliMode);
                const formatted = formatCiscoHelpTerminal(helpResult);
                appendCliOutput(formatted);
            }
            if (data.prompt) setCliDirectPrompt(data.prompt);
            input.value = currentVal;
            scrollToBottom();
            focusCliInput();
        }).catch(() => {
            const helpResult = resolveCiscoHelp(currentVal, cliMode);
            const formatted = formatCiscoHelpTerminal(helpResult);
            appendCliOutput(formatted);
            input.value = currentVal;
            scrollToBottom();
            focusCliInput();
        });
        return;
    }
    if (e.key === "Enter") {
        e.preventDefault();
        sendConsoleCmd();
        return;
    }
    if (e.key === "Tab" && !cliIsPasswordMode) {
        e.preventDefault();
        handleTabAutocomplete();
        return;
    }
    if (e.key === "c" && e.ctrlKey) {
        e.preventDefault();
        sendBreakSignal(e);
        return;
    }
    if (e.key === "z" && e.ctrlKey) {
        e.preventDefault();
        const prompt = getCliPrompt();
        appendCliLine(`${prompt}^Z`);
        input.value = "";
        fetch("/api/cli/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_id: activeDeviceId,
                command: "end"
            })
        }).then(r => r.json()).then(data => {
            if (data.output) appendCliOutput(data.output);
            if (data.prompt) setCliDirectPrompt(data.prompt);
            scrollToBottom();
            focusCliInput();
        }).catch(() => {});
        return;
    }
    if (e.key === "ArrowUp") {
        e.preventDefault();
        if (cliHistory.length === 0 || cliIsPasswordMode) return;
        cliHistoryIdx = Math.min(cliHistoryIdx + 1, cliHistory.length - 1);
        input.value = cliHistory[cliHistory.length - 1 - cliHistoryIdx] || "";
        return;
    }
    if (e.key === "ArrowDown") {
        e.preventDefault();
        if (cliIsPasswordMode) return;
        cliHistoryIdx = Math.max(cliHistoryIdx - 1, -1);
        input.value = cliHistoryIdx < 0 ? "" : (cliHistory[cliHistory.length - 1 - cliHistoryIdx] || "");
        return;
    }
}

async function sendConsoleCmd() {
    const input = document.getElementById("cli-input");
    if (!input) return;
    const rawVal = input.value;
    const trimmed = rawVal.trim();
    const prompt = getCliPrompt();

    if (cliIsPasswordMode) {
        // ในโหมด Password: ไม่ echo ตัวอักษรรหัสผ่านลงหน้าจอ (Section 44 ของ spec)
        appendCliLine(`${prompt}`);
        input.value = "";
    } else {
        // บันทึกคำสั่งลงประวัติ (History)
        if (trimmed && (cliHistory.length === 0 || cliHistory[cliHistory.length - 1] !== trimmed)) {
            cliHistory.push(trimmed);
        }
        cliHistoryIdx = -1;

        // Echo คำสั่งพร้อม prompt ปัจจุบันบนหน้าจอ (เหมือน Tera Term / PuTTY)
        appendCliLine(`${prompt}${rawVal}`);
        input.value = "";
    }

    // Built-in commands & mode navigation
    const lower = trimmed.toLowerCase();
    if (!cliIsPasswordMode && (lower === "clear" || lower === "cls")) {
        clearConsole();
        return;
    }

    // ส่งคำสั่งไปยังเซสชันจริงของ Router/Switch
    try {
        const res = await fetch("/api/cli/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_id: activeDeviceId,
                command: rawVal
            })
        });
        const data = await res.json();
        if (data.output) {
            appendCliOutput(data.output);
        } else if (data.message && !data.success) {
            appendCliOutput(`% ${data.message}`);
        }
        if (data.prompt) {
            setCliDirectPrompt(data.prompt);
        }

        // จัดการสถานะ Password mode
        if (data.is_password || (data.prompt && data.prompt.toLowerCase().includes("password"))) {
            cliIsPasswordMode = true;
            input.type = "password";
            if (data.prompt) {
                const promptEl = document.getElementById("cli-prompt");
                if (promptEl) promptEl.textContent = data.prompt.endsWith(" ") ? data.prompt : data.prompt + " ";
            }
        } else {
            cliIsPasswordMode = false;
            input.type = "text";
        }
    } catch (err) {
        appendCliOutput(`% Communication error: ${err.message}`);
    }

    scrollToBottom();
    focusCliInput();
}

function clearConsole(e) {
    if (e) e.stopPropagation();
    const lines = document.getElementById("cli-lines");
    if (lines) lines.innerHTML = "";
    const input = document.getElementById("cli-input");
    if (input) input.value = "";
    if (deviceTerminalState[activeDeviceId]) {
        deviceTerminalState[activeDeviceId].html = "";
    }
    scrollToBottom();
    focusCliInput();
}

async function sendBreakSignal(e) {
    if (e) e.stopPropagation();
    const prompt = getCliPrompt();
    const input = document.getElementById("cli-input");
    const currentVal = input ? input.value : "";
    if (input) input.value = "";

    appendCliLine(`${prompt}${currentVal}^C`);
    try {
        const res = await fetch("/api/cli/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_id: activeDeviceId,
                command: "\x03"
            })
        });
        const data = await res.json();
        if (data.output) appendCliOutput(data.output);
        if (data.prompt) setCliDirectPrompt(data.prompt);
        cliIsPasswordMode = false;
        if (input) input.type = "text";
    } catch (err) {}
    scrollToBottom();
    focusCliInput();
}

async function reconnectActiveCli(e) {
    if (e) e.stopPropagation();
    appendCliOutput(`[Connecting to ${activeDeviceId} console...]`);
    updateInventoryDot(activeDeviceId, "connecting");
    try {
        const res = await fetch("/api/cli/reconnect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device_id: activeDeviceId })
        });
        const data = await res.json();
        if (data.success) {
            appendCliOutput(`[Connected to ${activeDeviceId}]`);
            if (data.prompt) setCliDirectPrompt(data.prompt);
            const dev = inventoryDevices.find(d => d.id === activeDeviceId || d.name === activeDeviceId);
            if (dev) dev.connected = true;
            updateInventoryDot(activeDeviceId, "connected");
        } else {
            appendCliOutput(`% Reconnect failed: ${data.message}`);
            const dev = inventoryDevices.find(d => d.id === activeDeviceId || d.name === activeDeviceId);
            if (dev) dev.connected = false;
            updateInventoryDot(activeDeviceId, "disconnected");
        }
        updateCliConnectionBadge();
    } catch (err) {
        appendCliOutput(`% Connection error: ${err.message}`);
        updateInventoryDot(activeDeviceId, "disconnected");
    }
    scrollToBottom();
    focusCliInput();
}

// =============================================================================
// PORT FRONT-PANEL MODAL (Bonus)
// =============================================================================
async function openPortModal() {
    document.getElementById("port-modal").classList.add("active");
    try {
        const res = await fetch(`/api/ports/${activeDeviceId}`);
        const data = await res.json();
        if (!data.success) return;
        document.getElementById("modal-device-name").textContent = `${data.device.name} — Port Front Panel`;
        document.getElementById("modal-device-model").textContent = data.device.model;
        document.getElementById("chassis-model-text").textContent = `${data.device.model} (${data.device.ip})`;

        // Render port sockets
        const matrix = document.getElementById("ports-matrix-container");
        matrix.innerHTML = "";
        data.ports.forEach(port => {
            const sock = document.createElement("div");
            sock.className = `port-socket ${port.status}`;
            const iconClass = port.type === "serial" ? "fa-plug" : port.type === "virtual" ? "fa-network-wired" : "fa-ethernet";
            sock.innerHTML = `
                <div class="port-led-indicator ${port.led}"></div>
                <i class="fa-solid ${iconClass} port-icon"></i>
                <span class="port-label">${port.short_name}</span>
                <span class="port-ip">${port.ip !== "unassigned" ? port.ip : port.speed}</span>
            `;
            matrix.appendChild(sock);
        });

        // Render detail table
        const tbody = document.getElementById("modal-ports-table-body");
        tbody.innerHTML = "";
        data.ports.forEach(port => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${port.name}</strong></td>
                <td>${port.type.toUpperCase()}</td>
                <td><span class="badge ${port.status === 'up' ? 'badge-success' : ''}">${port.status.toUpperCase()}</span></td>
                <td><code>${port.ip}</code></td>
                <td>${port.mask || "—"}</td>
                <td>${port.speed}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) { console.error("Front panel load error:", e); }
}

// =============================================================================
// MODAL HELPERS
// =============================================================================
function closeModal(id) { document.getElementById(id).classList.remove("active"); }

// Close modal on backdrop click
document.addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) {
        e.target.classList.remove("active");
    }
});

// =============================================================================
// EVE-NG MODAL & TOPOLOGY IMPORT
// =============================================================================
function openEvengModal() {
    const modal = document.getElementById("eveng-modal");
    if (modal) modal.classList.add("active");
    const hostInp = document.getElementById("eveng-host");
    if (hostInp && (!hostInp.value || hostInp.value === "192.168.1.50")) {
        // Auto-fill from inventory if device has IP
        const devWithIp = inventoryDevices.find(d => d.ip && d.ip !== "127.0.0.1" && d.ip !== "localhost");
        if (devWithIp) {
            hostInp.value = devWithIp.ip;
        }
    }
    // Auto-scan labs in background if host is available
    if (hostInp && hostInp.value) {
        fetchEvengLabs(false);
    }
}

async function fetchEvengLabs(showNotify = true) {
    const host = document.getElementById("eveng-host")?.value.trim();
    const user = document.getElementById("eveng-user")?.value.trim() || "admin";
    const pass = document.getElementById("eveng-pass")?.value || "eve";
    const btn = document.getElementById("btn-fetch-labs");
    const labSel = document.getElementById("eveng-lab-select");

    if (!host) {
        if (showNotify) showNotification("กรุณาระบุ EVE-NG Host ก่อน", "error");
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ค้นหา...';
    }

    try {
        const res = await fetch(`/api/eveng/labs?host=${encodeURIComponent(host)}&username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}`);
        const data = await res.json();
        if (data.success && data.labs && data.labs.length > 0) {
            if (labSel) {
                labSel.innerHTML = '<option value="">— เลือก Lab จากรายการที่พบ —</option>';
                data.labs.forEach(lab => {
                    const opt = document.createElement("option");
                    const pathVal = lab.path || lab.file;
                    opt.value = pathVal.replace(/^\/+/, '');
                    opt.textContent = `${lab.file} (${lab.mtime || ''})`;
                    labSel.appendChild(opt);
                });
                labSel.classList.remove("d-none");
                // Auto select first lab
                labSel.value = (data.labs[0].path || data.labs[0].file).replace(/^\/+/, '');
                onEvengLabSelectChange();
            }
            if (showNotify) showNotification(`พบ ${data.labs.length} Lab ใน EVE-NG (${host})`, "success");
        } else {
            if (showNotify) showNotification("ไม่พบ Lab ในโฟลเดอร์เริ่มต้นของ EVE-NG", "info");
        }
    } catch (e) {
        if (showNotify) showNotification(`ค้นหา Lab ไม่สำเร็จ: ${e.message}`, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> ค้นหา Lab';
        }
    }
}

function onEvengLabSelectChange() {
    const labSel = document.getElementById("eveng-lab-select");
    const labInp = document.getElementById("eveng-lab");
    if (labSel && labInp && labSel.value) {
        labInp.value = labSel.value;
    }
}

async function importEvengTopology() {
    const host = document.getElementById("eveng-host")?.value.trim();
    const labPath = document.getElementById("eveng-lab")?.value.trim();
    const username = document.getElementById("eveng-user")?.value.trim() || "admin";
    const password = document.getElementById("eveng-pass")?.value || "eve";
    const btn = document.getElementById("btn-eveng-import");
    const statusBox = document.getElementById("eveng-import-status");

    if (!host || !labPath) {
        showNotification("กรุณาระบุ EVE-NG Host และ Lab Path (เช่น Test.unl)", "error");
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> กำลังนำเข้า Topology...';
    }
    if (statusBox) {
        statusBox.className = "conn-result-box connecting";
        statusBox.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>กำลังดึง Topology และ Nodes จาก EVE-NG (${host} / ${labPath})...</span>`;
        statusBox.classList.remove("d-none");
    }
    showNotification(`กำลังดึง Topology จาก EVE-NG (${host})...`, "info");

    try {
        const res = await fetch("/api/eveng/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ host, lab_path: labPath, username, password })
        });
        const data = await res.json();
        if (data.success) {
            if (statusBox) {
                statusBox.className = "conn-result-box success";
                statusBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> <span>นำเข้าสำเร็จ! พบ ${(data.nodes || []).length} Nodes, ${(data.edges || []).length} Links</span>`;
            }
            await loadInventory();
            renderVisNetwork(data.nodes || [], data.edges || []);
            const nodeBadge = document.getElementById("node-count-badge");
            const edgeBadge = document.getElementById("edge-count-badge");
            if (nodeBadge) nodeBadge.textContent = `${(data.nodes || []).length} Devices (EVE-NG)`;
            if (edgeBadge) edgeBadge.textContent = `${(data.edges || []).length} Links`;
            if (data.nodes && data.nodes.length > 0) {
                selectActiveDevice(data.nodes[0].name || data.nodes[0].id);
            }
            showNotification(`นำเข้า Topology จาก EVE-NG สำเร็จ (${(data.nodes || []).length} Nodes) — เพิ่มในรายการอุปกรณ์แล้ว`, "success");
            setTimeout(() => {
                closeModal("eveng-modal");
                if (statusBox) statusBox.classList.add("d-none");
            }, 1200);
        } else {
            const err = data.message || "นำเข้า EVE-NG ล้มเหลว";
            if (statusBox) {
                statusBox.className = "conn-result-box fail";
                statusBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> <span>${err}</span>`;
            }
            showNotification(err, "error");
        }
    } catch (err) {
        const errMsg = `เชื่อมต่อ EVE-NG API ไม่ได้: ${err.message}`;
        if (statusBox) {
            statusBox.className = "conn-result-box fail";
            statusBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> <span>${errMsg}</span>`;
        }
        showNotification(errMsg, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-download"></i> Import Topology';
        }
    }
}

// =============================================================================
// TOAST NOTIFICATIONS
// =============================================================================
function showNotification(message, type = "info") {
    // 1. Browser DevTools console log (never pollute the authentic Cisco CLI terminal screen)
    const prefix = type === "success" ? "[OK]" : type === "error" ? "[ERROR]" : "[INFO]";
    console.log(`${prefix} ${message}`);

    // 2. Floating toast UI
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.style.cssText = "position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    const bg = type === "success" ? "#065f46" : type === "error" ? "#7f1d1d" : "#1e3a8a";
    const border = type === "success" ? "#10b981" : type === "error" ? "#ef4444" : "#3b82f6";
    const icon = type === "success" ? "fa-circle-check" : type === "error" ? "fa-triangle-exclamation" : "fa-circle-info";

    toast.style.cssText = `background:${bg};border:1px solid ${border};color:#f9fafb;padding:10px 16px;border-radius:8px;font-size:12px;font-weight:500;box-shadow:0 8px 24px rgba(0,0,0,0.5);display:flex;align-items:center;gap:10px;pointer-events:auto;min-width:240px;max-width:380px;animation:slideIn 0.25s ease-out;`;
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(20px)";
        toast.style.transition = "all 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// =============================================================================
// INTERFACE TABLE — Refresh, Select, Up/Down
// =============================================================================
function selectInterfaceRow(iface) {
    if (!iface) return;
    selectedInterfaceName = iface.name;
    const tbody = document.getElementById("interface-table-body");
    if (tbody) {
        tbody.querySelectorAll("tr").forEach(r => {
            r.classList.toggle("active-row", r.dataset.ifName === iface.name);
        });
    }
    const ifSelect = document.getElementById("if-select");
    if (ifSelect) ifSelect.value = iface.name;

    const ipInput = document.getElementById("if-ip");
    const maskInput = document.getElementById("if-mask");
    if (iface.ip && (iface.ip.toLowerCase().includes("dhcp") || iface.method === "DHCP")) {
        toggleIpMode("dhcp");
    } else if (iface.ip && iface.ip !== "unassigned") {
        toggleIpMode("static");
        if (ipInput) ipInput.value = iface.ip;
        if (maskInput) maskInput.value = iface.mask || "255.255.255.0";
    } else {
        toggleIpMode("static");
        if (ipInput) ipInput.value = "";
        if (maskInput) maskInput.value = "255.255.255.0";
    }

    const descInput = document.getElementById("if-desc");
    if (descInput) descInput.value = iface.description || "";

    const stateRadio = document.querySelector(`input[name='if-state'][value='${iface.status === "up" ? "up" : "down"}']`);
    if (stateRadio) stateRadio.checked = true;

    updateIfPreview();
}

async function refreshInterfaceTable(force = false) {
    const tbody = document.getElementById("interface-table-body");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="4" class="text-muted"><i class="fa-solid fa-spinner fa-spin"></i> Loading interfaces...</td></tr>';
    try {
        const url = `/api/devices/${activeDeviceId}/interfaces${force ? '?force=1' : ''}`;
        const res = await fetch(url);
        const data = await res.json();
        if (!data.success || !data.interfaces || !data.interfaces.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No interface data available</td></tr>';
            return;
        }
        tbody.innerHTML = "";
        // บันทึก cache สำหรับอุปกรณ์นี้
        cachedInterfaces[activeDeviceId] = data.interfaces;
        const ifSelect = document.getElementById("if-select");
        if (ifSelect) {
            ifSelect.innerHTML = "";
        }

        // Determine which interface to select (preserve selected name if it exists on new device, otherwise pick first)
        let activeIface = data.interfaces.find(i => i.name === selectedInterfaceName);
        if (!activeIface) {
            activeIface = data.interfaces[0];
        }
        selectedInterfaceName = activeIface ? activeIface.name : "";

        data.interfaces.forEach(iface => {
            // Add table row
            const tr = document.createElement("tr");
            tr.dataset.ifName = iface.name;
            tr.className = (iface.name === selectedInterfaceName) ? "active-row" : "";
            const statusClass = iface.status === "up" ? "text-success" : "text-danger";
            const protocolClass = (iface.protocol || "down") === "up" ? "text-success" : "text-danger";
            tr.innerHTML = `
                <td><strong>${iface.name}</strong></td>
                <td><code>${iface.ip || 'unassigned'}</code></td>
                <td><span class="${statusClass}">${(iface.status || 'down').toUpperCase()}</span></td>
                <td><span class="${protocolClass}">${(iface.protocol || 'down').toUpperCase()}</span></td>
            `;
            tr.addEventListener("click", () => {
                selectInterfaceRow(iface);
            });
            tbody.appendChild(tr);

            // Populate dropdown
            if (ifSelect) {
                const opt = document.createElement("option");
                opt.value = iface.name;
                opt.textContent = iface.name;
                if (iface.name === selectedInterfaceName) opt.selected = true;
                ifSelect.appendChild(opt);
            }
        });

        // Auto-select and populate form with the active interface immediately!
        if (activeIface) {
            selectInterfaceRow(activeIface);
        } else {
            updateIfPreview();
        }
    } catch (e) {
        console.error("Interface table refresh error:", e);
        tbody.innerHTML = '<tr><td colspan="4" class="text-danger">Failed to load interfaces</td></tr>';
    }
}

async function applyInterfaceState(state) {
    const ifName = selectedInterfaceName || document.getElementById("if-select")?.value;
    if (!ifName) {
        showNotification("กรุณาเลือก Interface จากตารางก่อน", "error");
        return;
    }
    const verifyEl = document.getElementById("if-state-verify");
    if (verifyEl) verifyEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Applying ${state}...`;

    try {
        const res = await fetch("/api/config/interface/state", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_id: activeDeviceId,
                interface: ifName,
                state: state
            })
        });
        const data = await res.json();
        if (data.success) {
            showNotification(`${ifName} → ${state.toUpperCase()} สำเร็จ`, "success");
            if (data.output) appendConsole(data.output, "output-line");
            if (verifyEl) {
                const statusText = data.current_status || state;
                const isUp = statusText === "up";
                verifyEl.innerHTML = `<span class="${isUp ? 'text-success' : 'text-danger'}">${statusText.toUpperCase()}</span>`;
            }
            // Refresh table after state change
            setTimeout(() => refreshInterfaceTable(true), 500);
        } else {
            showNotification(data.message || "State change failed", "error");
            if (verifyEl) verifyEl.innerHTML = `<span class="text-danger">FAILED</span>`;
        }
    } catch (e) {
        showNotification("Connection error", "error");
        if (verifyEl) verifyEl.innerHTML = "";
    }
}

function syncSelectedInterfaceRow() {
    const ifName = document.getElementById("if-select")?.value;
    if (!ifName) return;
    const cached = cachedInterfaces[activeDeviceId] || [];
    const iface = cached.find(i => i.name === ifName);
    if (iface) {
        selectInterfaceRow(iface);
    } else {
        selectedInterfaceName = ifName;
        const tbody = document.getElementById("interface-table-body");
        if (tbody) {
            tbody.querySelectorAll("tr").forEach(tr => {
                tr.classList.toggle("active-row", tr.dataset.ifName === ifName);
            });
        }
        updateIfPreview();
    }
}

// =============================================================================
// CLI SHORTCUT BUTTONS
// =============================================================================
function runShowShortcut(cmd) {
    const input = document.getElementById("cli-input");
    if (input) input.value = cmd;
    sendConsoleCmd();
}

// =============================================================================
// SSH SETUP WIZARD
// =============================================================================
async function runSshSetupWizard() {
    const domain = document.getElementById("ssh-domain")?.value?.trim();
    const keySize = document.getElementById("ssh-key-size")?.value || "1024";
    if (!domain) {
        showNotification("กรุณาระบุ Domain Name ก่อน (เช่น lab.local)", "error");
        return;
    }
    const outputEl = document.getElementById("ssh-setup-output");
    if (outputEl) {
        outputEl.classList.remove("d-none");
        outputEl.textContent = "Running SSH setup wizard...";
    }
    try {
        const res = await fetch("/api/config/ssh-setup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_id: activeDeviceId,
                domain_name: domain,
                key_size: parseInt(keySize),
                username: document.getElementById("conn-user")?.value || "cisco",
                password: document.getElementById("conn-pass")?.value || "cisco"
            })
        });
        const data = await res.json();
        if (outputEl) outputEl.textContent = data.output || data.message || "Done";
        showNotification(
            data.success ? "SSH Setup สำเร็จ!" : (data.message || "SSH Setup ล้มเหลว"),
            data.success ? "success" : "error"
        );
        if (data.output) appendConsole(data.output, data.success ? "output-line" : "error-line");
    } catch (e) {
        if (outputEl) outputEl.textContent = "Error: " + e.message;
        showNotification("SSH Setup connection error", "error");
    }
}

// =============================================================================
// REDISTRIBUTION PANEL
// =============================================================================
function toggleRedistributionPanel(type) {
    const panel = document.getElementById("redistribution-panel");
    if (!panel) return;
    // Show redistribution for dynamic protocols only
    const dynamic = ["rip", "eigrp", "ospf", "bgp"];
    panel.classList.toggle("d-none", !dynamic.includes(type));
}

function addRedistributeRow() {
    const container = document.getElementById("redistribute-rows");
    if (!container) return;
    const row = document.createElement("div");
    row.className = "network-row";
    row.innerHTML = `
        <select class="form-control redistribute-source" onchange="updateRoutingPreview()" style="max-width:140px">
            <option value="static">Static</option>
            <option value="connected">Connected</option>
            <option value="rip">RIP</option>
            <option value="eigrp">EIGRP</option>
            <option value="ospf">OSPF</option>
            <option value="bgp">BGP</option>
        </select>
        <input type="text" class="form-control redistribute-metric" placeholder="metric (optional)" oninput="updateRoutingPreview()" style="max-width:120px">
        <label class="checkbox-label" style="font-size:11px;white-space:nowrap">
            <input type="checkbox" class="redistribute-subnets" onchange="updateRoutingPreview()"> subnets
        </label>
        <button type="button" class="remove-row-btn" onclick="removeRow(this)"><i class="fa-solid fa-minus"></i></button>
    `;
    container.appendChild(row);
    updateRoutingPreview();
}

function toggleDefaultOriginateAlways() {
    const type = document.getElementById("routing-type-input")?.value;
    const alwaysWrap = document.getElementById("default-originate-always-wrap");
    const enabled = document.getElementById("default-originate-enable")?.checked;
    if (alwaysWrap) {
        alwaysWrap.classList.toggle("d-none", !enabled || type !== "ospf");
    }
}

function getRedistributePayload() {
    const rows = document.querySelectorAll("#redistribute-rows .network-row");
    const result = [];
    rows.forEach(r => {
        const source = r.querySelector(".redistribute-source")?.value;
        const metric = r.querySelector(".redistribute-metric")?.value?.trim();
        const subnets = r.querySelector(".redistribute-subnets")?.checked;
        if (source) {
            const item = { source: source, subnets: !!subnets };
            if (metric) item.metric = metric;
            result.push(item);
        }
    });
    return result.length > 0 ? result : null;
}

function getDefaultOriginatePayload() {
    const enabled = document.getElementById("default-originate-enable")?.checked;
    if (!enabled) return null;
    const always = document.getElementById("default-originate-always")?.checked;
    return { enabled: true, always: !!always };
}

// =============================================================================
// DEVICE DRAWER (Packet Tracer Style)
// =============================================================================
function openDeviceDrawer(deviceId) {
    drawerDeviceId = deviceId || activeDeviceId;
    const dev = inventoryDevices.find(d => d.id === drawerDeviceId);
    const drawer = document.getElementById("device-drawer");
    if (!drawer) return;

    drawer.classList.remove("d-none");
    document.getElementById("drawer-device-title").textContent = dev?.name || drawerDeviceId;
    document.getElementById("drawer-device-model").textContent = dev?.model || "";
    document.getElementById("drawer-cli-prompt").textContent = `${drawerDeviceId}#`;

    // Load physical panel (port front panel mini)
    loadDrawerPhysicalPanel();

    // If PC, pre-fill PC config
    if (dev && (dev.device_type_label || "").toLowerCase() === "pc") {
        document.getElementById("drawer-pc-ip").value = dev.ip || "";
        document.getElementById("drawer-pc-mask").value = dev.mask || "255.255.255.0";
        document.getElementById("drawer-pc-gw").value = dev.gateway || "";
    }

    switchDrawerTab("physical");
}

function closeDeviceDrawer() {
    const drawer = document.getElementById("device-drawer");
    if (drawer) drawer.classList.add("d-none");
    drawerDeviceId = null;
}

function switchDrawerTab(tabName) {
    document.querySelectorAll(".drawer-tab").forEach(t => {
        t.classList.toggle("active", t.dataset.drawerTab === tabName);
    });
    document.querySelectorAll(".drawer-panel").forEach(p => p.classList.remove("active"));
    const panel = document.getElementById(`drawer-panel-${tabName}`);
    if (panel) panel.classList.add("active");
}

async function loadDrawerPhysicalPanel() {
    const panel = document.getElementById("drawer-panel-physical");
    if (!panel || !drawerDeviceId) return;
    panel.innerHTML = '<div style="padding:12px;color:var(--text-muted)"><i class="fa-solid fa-spinner fa-spin"></i> Loading ports...</div>';
    try {
        const res = await fetch(`/api/ports/${drawerDeviceId}`);
        const data = await res.json();
        if (!data.success) {
            panel.innerHTML = '<div style="padding:12px;color:var(--text-dim)">No port data</div>';
            return;
        }
        let html = '<div class="drawer-ports-grid">';
        data.ports.forEach(port => {
            const iconClass = port.type === "serial" ? "fa-plug" : port.type === "virtual" ? "fa-network-wired" : "fa-ethernet";
            html += `
                <div class="port-socket ${port.status}" style="width:90px;padding:7px">
                    <div class="port-led-indicator ${port.led}"></div>
                    <i class="fa-solid ${iconClass} port-icon" style="font-size:14px"></i>
                    <span class="port-label">${port.short_name}</span>
                    <span class="port-ip">${port.ip !== "unassigned" ? port.ip : port.speed}</span>
                </div>
            `;
        });
        html += '</div>';
        panel.innerHTML = html;
    } catch (e) {
        panel.innerHTML = '<div style="padding:12px;color:var(--text-dim)">Error loading ports</div>';
    }
}

async function sendDrawerCli() {
    const input = document.getElementById("drawer-cli-input");
    const output = document.getElementById("drawer-console-output");
    if (!input || !output || !drawerDeviceId) return;
    const cmd = input.value.trim();
    if (!cmd) return;

    // Add command to output
    const cmdLine = document.createElement("div");
    cmdLine.className = "line prompt-line";
    cmdLine.textContent = `${drawerDeviceId}# ${cmd}`;
    output.appendChild(cmdLine);
    input.value = "";

    try {
        const res = await fetch("/api/cli/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ device_id: drawerDeviceId, command: cmd })
        });
        const data = await res.json();
        const resultLine = document.createElement("div");
        resultLine.className = "line output-line";
        resultLine.textContent = data.output || data.message || "";
        output.appendChild(resultLine);
    } catch (e) {
        const errLine = document.createElement("div");
        errLine.className = "line error-line";
        errLine.textContent = "Error: " + e.message;
        output.appendChild(errLine);
    }
    output.scrollTop = output.scrollHeight;
}

async function saveDrawerPcConfig() {
    if (!drawerDeviceId) return;
    const ip = document.getElementById("drawer-pc-ip")?.value || "";
    const mask = document.getElementById("drawer-pc-mask")?.value || "255.255.255.0";
    const gateway = document.getElementById("drawer-pc-gw")?.value || "";

    try {
        const res = await fetch(`/api/pc/${drawerDeviceId}/config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip, mask, gateway })
        });
        const data = await res.json();
        showNotification(data.message || (data.success ? "Saved" : "Failed"), data.success ? "success" : "error");
        if (data.success) await loadInventory();
    } catch (e) {
        showNotification("Error saving PC config", "error");
    }
}

async function pingFromDrawerPc() {
    if (!drawerDeviceId) return;
    const target = document.getElementById("drawer-pc-ping-target")?.value?.trim();
    const outputEl = document.getElementById("drawer-pc-ping-out");
    if (!target) {
        showNotification("ระบุ Target IP ก่อน", "error");
        return;
    }
    if (outputEl) outputEl.textContent = `Pinging ${target}...`;
    try {
        const res = await fetch(`/api/pc/${drawerDeviceId}/ping`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target })
        });
        const data = await res.json();
        if (outputEl) outputEl.textContent = data.output || data.message || "Done";
    } catch (e) {
        if (outputEl) outputEl.textContent = "Error: " + e.message;
    }
}


// =============================================================================
// DEVICE TYPE → MODEL DROPDOWN (spec v3 section 3)
// =============================================================================
function onDeviceTypeChange() {
    const type = document.getElementById("ad-type").value;
    const modelSel = document.getElementById("ad-model");
    modelSel.innerHTML = "";

    const models = {
        router: [
            { value: "Cisco 4331", label: "Cisco 4331" },
            { value: "Cisco 2901", label: "Cisco 2901" },
            { value: "Cisco 1941", label: "Cisco 1941" },
            { value: "Cisco 2911", label: "Cisco 2911" },
        ],
        switch: [
            { value: "Cisco Catalyst 2960", label: "Cisco Catalyst 2960" },
            { value: "Cisco Catalyst 3560", label: "Cisco Catalyst 3560" },
            { value: "Cisco Catalyst 3750", label: "Cisco Catalyst 3750" },
        ],
    };

    const list = models[type] || models.router;
    list.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.value;
        opt.textContent = m.label;
        modelSel.appendChild(opt);
    });
}


// =============================================================================
// ADD INTERFACE MODAL (spec v3 section 3.2)
// =============================================================================
function openAddInterfaceModal() {
    document.getElementById("add-interface-modal").classList.add("active");
}

async function submitAddInterface() {
    const ifType = document.getElementById("add-if-type").value;
    const ifNum = parseInt(document.getElementById("add-if-number").value) || 0;

    try {
        const res = await fetch(`/api/devices/${activeDeviceId}/interfaces`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: ifType, number: ifNum })
        });
        const data = await res.json();
        if (data.success) {
            showNotification(`Added ${data.interface.name} to ${activeDeviceId}`, "success");
            closeModal("add-interface-modal");
            updateInterfaceOptions();
        } else {
            showNotification(data.message, "error");
        }
    } catch (e) {
        showNotification("Failed to add interface", "error");
    }
}


// =============================================================================
// CONFIG FILE LIFECYCLE (spec v3 section 19)
// =============================================================================
async function exportConfig(type) {
    // type = "running" or "startup"
    const outputEl = document.getElementById("config-lifecycle-output");
    outputEl.textContent = `Exporting ${type} config from ${activeDeviceId}...`;

    try {
        const res = await fetch(`/api/config/${activeDeviceId}/${type}`);
        const data = await res.json();
        if (data.success) {
            outputEl.textContent = data.config;
            // Also trigger file download
            const blob = new Blob([data.config], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${activeDeviceId}-${type}-config.txt`;
            a.click();
            URL.revokeObjectURL(url);
            showNotification(`Exported ${type} config for ${activeDeviceId}`, "success");
        }
    } catch (e) {
        outputEl.textContent = `Error: ${e.message}`;
        showNotification("Export failed", "error");
    }
}

async function mergeConfig() {
    const configText = document.getElementById("merge-config-text").value;
    const outputEl = document.getElementById("config-lifecycle-output");
    if (!configText.trim()) {
        showNotification("กรุณาใส่ config text ก่อน", "error");
        return;
    }
    outputEl.textContent = `Merging config to ${activeDeviceId}...`;
    try {
        const res = await fetch(`/api/config/${activeDeviceId}/merge`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ config: configText })
        });
        const data = await res.json();
        outputEl.textContent = data.output || data.message || "Done";
        showNotification(data.success ? "Config merged successfully" : (data.message || "Merge failed"),
                         data.success ? "success" : "error");
    } catch (e) {
        outputEl.textContent = `Error: ${e.message}`;
    }
}

async function saveConfig() {
    const outputEl = document.getElementById("config-lifecycle-output");
    outputEl.textContent = `Saving running → startup on ${activeDeviceId}...`;
    try {
        const res = await fetch(`/api/config/${activeDeviceId}/save`, { method: "POST" });
        const data = await res.json();
        outputEl.textContent = data.output || data.message || "Done";
        showNotification(data.success ? "Config saved (write memory)" : "Save failed",
                         data.success ? "success" : "error");
    } catch (e) {
        outputEl.textContent = `Error: ${e.message}`;
    }
}

// Background Keepalive: ป้องกัน Telnet session บน Switch / Router หลุดจาก idle timeout
setInterval(() => {
    fetch("/api/connections/keepalive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: activeDeviceId })
    }).catch(() => {});
}, 45000);


