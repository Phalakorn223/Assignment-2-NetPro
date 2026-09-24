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
    document.getElementById(tabId).classList.add("active");
    const btnId = "btn-" + tabId;
    const btn = document.getElementById(btnId);
    if (btn) btn.classList.add("active");
    if (tabId === "tab-if") {
        refreshInterfaceTable();
    }
}

// =============================================================================
// DEVICE INVENTORY
// =============================================================================
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
        // Show IP:Port for EVE-NG console devices (port > 1000 and same IP pattern)
        const port = dev.port || 0;
        const ipDisplay = dev.ip
            ? (port > 1000 ? `${dev.ip}:${port}` : dev.ip)
            : (dev.serial_port || '');
        item.innerHTML = `
            <span class="inv-status-dot ${dev.connected ? 'connected' : 'disconnected'}"></span>
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

function selectActiveDevice(deviceId) {
    const dev = inventoryDevices.find(d => d.id === deviceId || d.name === deviceId || String(d.id) === String(deviceId));
    if (dev) {
        activeDeviceId = dev.id;
    } else {
        activeDeviceId = deviceId;
    }
    const sel = document.getElementById("active-device-select");
    if (sel && dev) sel.value = dev.id;
    updatePromptLabel();
    updateInterfaceOptions();
}

function onActiveDeviceChange() {
    activeDeviceId = document.getElementById("active-device-select").value;
    updatePromptLabel();
    updateInterfaceOptions();
    refreshInterfaceTable();
    appendConsole(`# Switched target to ${activeDeviceId}`, "comment");
}

function updatePromptLabel() {
    const dev = inventoryDevices.find(d => d.id === activeDeviceId);
    const name = dev ? (dev.name || dev.id) : activeDeviceId;
    const promptEl = document.getElementById("cli-prompt");
    const labelEl = document.getElementById("cli-target-label");
    if (promptEl) promptEl.textContent = `${activeDeviceId}#`;
    if (labelEl) labelEl.innerHTML = `<i class="fa-solid fa-server"></i> Target: ${name}`;
}

function toggleInventoryPanel() {
    const list = document.getElementById("inventory-list");
    if (list) list.classList.toggle("d-none");
}

function openAddDeviceModal() { document.getElementById("add-device-modal").classList.add("active"); }

async function submitAddDevice(e) {
    e.preventDefault();
    const dtype = document.getElementById("ad-type").value;
    const payload = {
        name: document.getElementById("ad-name").value,
        model: document.getElementById("ad-model").value,
        device_type_label: dtype,
        connection_type: dtype === "pc" ? "PC" : document.getElementById("ad-proto").value,
        ip: document.getElementById("ad-ip").value,
        port: parseInt(document.getElementById("ad-port").value) || 22,
        username: document.getElementById("ad-user").value,
        password: document.getElementById("ad-pass").value,
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
    const isPc = document.getElementById("ad-type").value === "pc";
    document.getElementById("ad-pc-fields")?.classList.toggle("d-none", !isPc);
    document.getElementById("ad-cred-fields")?.classList.toggle("d-none", isPc);
    const protoSel = document.getElementById("ad-proto");
    if (protoSel) protoSel.closest(".form-group")?.classList.toggle("d-none", isPc);
}

// =============================================================================
// CONNECTION MANAGEMENT
// =============================================================================
function onConnDeviceSelect() {
    const sel = document.getElementById("conn-device-select");
    const devId = sel.value;
    const dev = inventoryDevices.find(d => d.id === devId);
    if (!dev) return;
    document.getElementById("conn-proto").value = dev.connection_type || "SSH";
    document.getElementById("conn-ip").value = dev.ip || "";
    document.getElementById("conn-port").value = dev.port || 22;
    document.getElementById("conn-user").value = dev.username || "cisco";
    document.getElementById("conn-pass").value = dev.password || "cisco";
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
    const btn = event.target.closest("button");
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Pinging...';
    btn.disabled = true;
    try {
        const res = await fetch("/api/ping", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ip })
        });
        const data = await res.json();
        const box = document.getElementById("ping-result");
        box.textContent = data.message;
        box.className = "ping-result-box " + (data.reachable ? "success" : "fail");
        box.classList.remove("d-none");
    } finally {
        btn.innerHTML = '<i class="fa-solid fa-satellite-dish"></i> Test Ping';
        btn.disabled = false;
    }
}

async function submitConnection(e) {
    e.preventDefault();
    const proto = document.getElementById("conn-proto").value;
    const devId = document.getElementById("conn-device-select").value || "custom";
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
    showNotification(`Connecting to ${payload.ip || payload.serial_port}...`, "info");
    const res = await fetch(`/api/connect/${devId}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    showNotification(data.message, data.success ? "success" : "error");
    if (data.success) {
        await loadInventory();
        await loadActiveConnections();
        document.getElementById("status-text").textContent = "Live Connection Active";
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
        const res = await fetch("/api/topology/json");
        const data = await res.json();
        if (data.success) {
            renderVisNetwork(data.nodes, data.edges);
            document.getElementById("node-count-badge").textContent = `${data.nodes.length} Devices`;
            document.getElementById("edge-count-badge").textContent = `${data.edges.length} Links`;
        }
    } catch (e) { console.error("Auto-discovery failed:", e); }
    finally { if (loading) loading.classList.add("d-none"); }
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

    const visEdges = new vis.DataSet(edges.map(e => {
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
            from: e.from, to: e.to,
            label: label,
            title: title,
            color: { color: e.status === "up" ? "#10b981" : "#ef4444", highlight: "#38bdf8" },
            dashes: Boolean(e.from_port && e.from_port.includes("Serial")),
            width: 2.5,
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
    } else {
        if (ipInput) {
            if (ipInput.value.toLowerCase().trim() === "dhcp") {
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
    } else {
        const currentMode = document.querySelector("input[name='if-ip-mode']:checked")?.value;
        if (currentMode === "dhcp") {
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
    const mode = document.querySelector("input[name='if-ip-mode']:checked")?.value || (ip.toLowerCase() === "dhcp" ? "dhcp" : "static");

    let lines = ["configure terminal", `interface ${iface}`];
    if (desc) lines.push(` description ${desc}`);
    if (mode === "dhcp" || ip.toLowerCase() === "dhcp") {
        lines.push(" ip address dhcp");
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

    const payload = {
        device_id: activeDeviceId,
        interface: ifSelect ? ifSelect.value : "",
        ip: isDhcp ? "dhcp" : ipVal,
        mask: isDhcp ? "" : (document.getElementById("if-mask")?.value || "255.255.255.0"),
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
// CLI TERMINAL + AUTOCOMPLETE
// =============================================================================
function handleCliKey(e) {
    const input = document.getElementById("cli-input");
    if (e.key === "Enter") {
        e.preventDefault();
        closeAutocomplete();
        sendConsoleCmd();
    } else if (e.key === "Escape") {
        closeAutocomplete();
    } else if (e.key === "Tab") {
        e.preventDefault();
        const first = document.querySelector(".autocomplete-item");
        if (first) { input.value = first.textContent; closeAutocomplete(); }
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (cliHistory.length === 0) return;
        cliHistoryIdx = Math.min(cliHistoryIdx + 1, cliHistory.length - 1);
        input.value = cliHistory[cliHistory.length - 1 - cliHistoryIdx] || "";
        closeAutocomplete();
    } else if (e.key === "ArrowDown") {
        e.preventDefault();
        cliHistoryIdx = Math.max(cliHistoryIdx - 1, -1);
        input.value = cliHistoryIdx < 0 ? "" : (cliHistory[cliHistory.length - 1 - cliHistoryIdx] || "");
        closeAutocomplete();
    }
}

async function fetchSuggestions(partial) {
    if (!partial || partial.length < 2) { closeAutocomplete(); return; }
    try {
        const res = await fetch(`/api/suggestions?q=${encodeURIComponent(partial)}`);
        const data = await res.json();
        if (data.success && data.suggestions.length) {
            renderAutocomplete(data.suggestions);
        } else { closeAutocomplete(); }
    } catch (e) { closeAutocomplete(); }
}

function renderAutocomplete(suggestions) {
    const dropdown = document.getElementById("autocomplete-dropdown");
    dropdown.innerHTML = "";
    suggestions.forEach(s => {
        const item = document.createElement("div");
        item.className = "autocomplete-item";
        item.textContent = s;
        item.addEventListener("mousedown", (e) => {
            e.preventDefault();
            document.getElementById("cli-input").value = s;
            closeAutocomplete();
        });
        dropdown.appendChild(item);
    });
    dropdown.classList.remove("d-none");
}

function closeAutocomplete() {
    const dd = document.getElementById("autocomplete-dropdown");
    if (dd) dd.classList.add("d-none");
}

// Close autocomplete when clicking outside
document.addEventListener("click", (e) => {
    if (!e.target.closest(".autocomplete-wrapper")) closeAutocomplete();
});

async function sendConsoleCmd() {
    const input = document.getElementById("cli-input");
    const cmd = input.value.trim();
    if (!cmd) return;
    closeAutocomplete();
    // Save to history (avoid duplicates)
    if (cliHistory[cliHistory.length - 1] !== cmd) {
        cliHistory.push(cmd);
        if (cliHistory.length > 50) cliHistory.shift();
    }
    cliHistoryIdx = -1;
    appendConsole(`${activeDeviceId}# ${cmd}`, "prompt-line");
    input.value = "";
    const res = await fetch("/api/cli/execute", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: activeDeviceId, command: cmd })
    });
    const data = await res.json();
    appendConsole(data.output || data.message || "", "output-line");
}


function appendConsole(text, cssClass) {
    const body = document.getElementById("console-output");
    if (!body || !text) return;
    const lines = String(text).split("\n");
    lines.forEach(line => {
        const el = document.createElement("div");
        el.className = "line " + (cssClass || "output-line");
        el.textContent = line;
        body.appendChild(el);
    });
    body.scrollTop = body.scrollHeight;
}

function clearConsole() {
    const body = document.getElementById("console-output");
    if (body) body.innerHTML = `<div class="line comment"># Console cleared</div>`;
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
}

async function importEvengTopology() {
    const host = document.getElementById("eveng-host")?.value.trim();
    const labPath = document.getElementById("eveng-lab")?.value.trim();
    const username = document.getElementById("eveng-user")?.value.trim() || "admin";
    const password = document.getElementById("eveng-pass")?.value || "eve";

    if (!host || !labPath) {
        showNotification("กรุณาระบุ EVE-NG Host และ Lab Path (เช่น /lab1.unl)", "error");
        return;
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
            closeModal("eveng-modal");
            await loadInventory();
            renderVisNetwork(data.nodes || [], data.edges || []);
            document.getElementById("node-count-badge").textContent = `${(data.nodes || []).length} Devices (EVE-NG)`;
            document.getElementById("edge-count-badge").textContent = `${(data.edges || []).length} Links`;
            if (data.nodes && data.nodes.length > 0) {
                selectActiveDevice(data.nodes[0].name || data.nodes[0].id);
            }
            showNotification(`นำเข้า Topology จาก EVE-NG สำเร็จ (${(data.nodes || []).length} Nodes) — เพิ่มในรายการอุปกรณ์แล้ว`, "success");
        } else {
            showNotification(data.message || "นำเข้า EVE-NG ล้มเหลว", "error");
        }
    } catch (err) {
        showNotification(`เชื่อมต่อ EVE-NG API ไม่ได้: ${err.message}`, "error");
    }
}

// =============================================================================
// TOAST NOTIFICATIONS
// =============================================================================
function showNotification(message, type = "info") {
    // 1. Console log
    const prefix = type === "success" ? "[OK]" : type === "error" ? "[ERROR]" : "[INFO]";
    appendConsole(`${prefix} ${message}`, type === "error" ? "error-line" : "comment");

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
                selectedInterfaceName = iface.name;
                // Highlight this row
                tbody.querySelectorAll("tr").forEach(r => r.classList.remove("active-row"));
                tr.classList.add("active-row");
                // Sync dropdown
                if (ifSelect) ifSelect.value = iface.name;
                // Pre-fill IP/mask or DHCP
                const ipInput = document.getElementById("if-ip");
                const maskInput = document.getElementById("if-mask");
                if (iface.ip && (iface.ip.toLowerCase().includes("dhcp") || iface.method === "DHCP")) {
                    toggleIpMode("dhcp");
                } else if (iface.ip && iface.ip !== "unassigned") {
                    toggleIpMode("static");
                    if (ipInput) ipInput.value = iface.ip;
                    if (maskInput) maskInput.value = "255.255.255.0";
                } else {
                    toggleIpMode("static");
                    if (ipInput) ipInput.value = "";
                }
                // Set state radio
                const stateRadio = document.querySelector(`input[name='if-state'][value='${iface.status === "up" ? "up" : "down"}']`);
                if (stateRadio) stateRadio.checked = true;
                updateIfPreview();
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
        updateIfPreview();
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
            setTimeout(() => refreshInterfaceTable(), 500);
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
    selectedInterfaceName = ifName;
    const tbody = document.getElementById("interface-table-body");
    if (tbody) {
        tbody.querySelectorAll("tr").forEach(tr => {
            tr.classList.toggle("active-row", tr.dataset.ifName === ifName);
        });
    }
    updateIfPreview();
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
