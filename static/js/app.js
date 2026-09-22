/* ==========================================================================
   NetConfig Tracer Studio v2 — Frontend Application Logic
   ========================================================================== */

// ─── State ────────────────────────────────────────────────────────────────
let activeDeviceId = "R1";
let topoNetwork = null;  // vis-network instance
let inventoryDevices = [];
let cliHistory = [];     // command history buffer
let cliHistoryIdx = -1;  // history navigation index


// ─── Init ─────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadInventory();
    initRoutingRows();
    updateIfPreview();
    updateRoutingPreview();
    loadActiveConnections();
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
        item.className = "inventory-item";
        item.innerHTML = `
            <span class="inv-status-dot ${dev.connected ? 'connected' : 'disconnected'}"></span>
            <span class="inv-name">${dev.name || dev.id}</span>
            <span class="inv-ip">${dev.ip || dev.serial_port || ''}</span>
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
    activeDeviceId = deviceId;
    const sel = document.getElementById("active-device-select");
    if (sel) sel.value = deviceId;
    updatePromptLabel();
    updateInterfaceOptions();
}

function onActiveDeviceChange() {
    activeDeviceId = document.getElementById("active-device-select").value;
    updatePromptLabel();
    updateInterfaceOptions();
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
    const payload = {
        name: document.getElementById("ad-name").value,
        model: document.getElementById("ad-model").value,
        device_type_label: document.getElementById("ad-type").value,
        connection_type: document.getElementById("ad-proto").value,
        ip: document.getElementById("ad-ip").value,
        port: parseInt(document.getElementById("ad-port").value) || 22,
        username: document.getElementById("ad-user").value,
        password: document.getElementById("ad-pass").value,
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
    if (data.success) { await loadInventory(); }
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

function onConnProtoChange() {
    const proto = document.getElementById("conn-proto").value;
    const isSerial = proto === "SERIAL";
    document.getElementById("ip-conn-fields").classList.toggle("d-none", isSerial);
    document.getElementById("serial-conn-fields").classList.toggle("d-none", !isSerial);
    if (!isSerial) {
        document.getElementById("conn-port").value = proto === "SSH" ? 22 : 23;
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
        if (!list) return;
        if (!data.connected || !data.connected.length) {
            list.innerHTML = '<div style="font-size:12px;color:var(--text-dim)">No active connections (Simulation Mode)</div>';
            return;
        }
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
    } catch (e) {}
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
        return { background: "#2d1a3a", border: "#a855f7", highlight: { background: "#7c3aed", border: "#c084fc" } };
    };

    const visNodes = new vis.DataSet(nodes.map(n => ({
        id: n.id,
        label: `${n.name}\n${n.ip || ''}`,
        shape: n.type === "switch" ? "database" : "hexagon",
        color: nodeColor(n.type),
        font: { color: "#f3f4f6", size: 12, face: "Inter" },
        borderWidth: n.id === activeDeviceId ? 3 : 1.5,
        shadow: { enabled: true, color: "rgba(0,0,0,0.5)", size: 8 },
    })));

    const visEdges = new vis.DataSet(edges.map(e => ({
        from: e.from, to: e.to,
        label: e.from_port ? e.from_port.replace("GigabitEthernet", "Gi").replace("FastEthernet", "Fa").replace("Serial", "Se") : "",
        color: { color: e.status === "up" ? "#10b981" : "#ef4444", highlight: "#3b82f6" },
        dashes: e.from_port && e.from_port.includes("Serial"),
        width: 2, font: { color: "#6b7280", size: 9, align: "middle" },
    })));

    const options = {
        physics: { enabled: true, solver: "repulsion", repulsion: { nodeDistance: 150, springLength: 200 } },
        interaction: { hover: true, tooltipDelay: 200 },
        nodes: { size: 28 },
        edges: { smooth: { type: "curvedCW", roundness: 0.15 } },
        background: { color: "transparent" },
    };

    if (topoNetwork) { topoNetwork.destroy(); }
    topoNetwork = new vis.Network(container, { nodes: visNodes, edges: visEdges }, options);

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
    // Double-click → open port front panel
    topoNetwork.on("doubleClick", (params) => {
        if (params.nodes.length > 0) { openPortModal(); }
    });
}

// =============================================================================
// INTERFACE CONFIGURATION
// =============================================================================
function updateInterfaceOptions() {
    const sel = document.getElementById("if-select");
    if (!sel) return;
    const dev = inventoryDevices.find(d => d.id === activeDeviceId);
    const isSwitch = dev && dev.device_type_label === "switch";
    const ifList = isSwitch
        ? ["FastEthernet0/1","FastEthernet0/2","FastEthernet0/3","FastEthernet0/4","GigabitEthernet0/1","Vlan1","Vlan10","Vlan20"]
        : ["GigabitEthernet0/0/0","GigabitEthernet0/0/1","GigabitEthernet0/0/2","Serial0/1/0","Loopback0"];
    sel.innerHTML = "";
    ifList.forEach(name => {
        const opt = document.createElement("option");
        opt.value = name; opt.textContent = name;
        sel.appendChild(opt);
    });
    updateIfPreview();
}

function updateIfPreview() {
    const iface = document.getElementById("if-select")?.value || "GigabitEthernet0/0/0";
    const ip = document.getElementById("if-ip")?.value || "";
    const mask = document.getElementById("if-mask")?.value || "255.255.255.0";
    const desc = document.getElementById("if-desc")?.value || "";
    const stateEl = document.querySelector("input[name='if-state']:checked");
    const state = stateEl ? stateEl.value : "up";

    let lines = ["configure terminal", `interface ${iface}`];
    if (desc) lines.push(` description ${desc}`);
    if (ip) lines.push(` ip address ${ip} ${mask}`);
    lines.push(state === "up" ? " no shutdown" : " shutdown");
    lines.push("end");

    const pre = document.getElementById("if-cli-preview");
    if (pre) pre.textContent = lines.join("\n");
}

async function submitInterfaceConfig(e) {
    e.preventDefault();
    const payload = {
        device_id: activeDeviceId,
        interface: document.getElementById("if-select").value,
        ip: document.getElementById("if-ip").value,
        mask: document.getElementById("if-mask").value,
        description: document.getElementById("if-desc").value,
        state: document.querySelector("input[name='if-state']:checked").value,
    };
    const res = await fetch("/api/config/interface", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
        showNotification(`Interface ${payload.interface} configured!`, "success");
        appendConsole(data.output, "output-line");
    } else {
        showNotification(data.message || "Config failed", "error");
        appendConsole(data.output || data.message, "error-line");
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
        lines.push(" no auto-summary", "exit");
    } else if (type === "eigrp") {
        const as = document.getElementById("eigrp-as")?.value || "100";
        lines.push(`router eigrp ${as}`);
        document.querySelectorAll("#eigrp-networks-container .network-row").forEach(row => {
            const net = row.querySelector(".eigrp-net")?.value.trim();
            const wild = row.querySelector(".eigrp-wild")?.value.trim() || "0.0.0.255";
            if (net) lines.push(` network ${net} ${wild}`);
        });
        lines.push(" no auto-summary", "exit");
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
        lines.push("exit");
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
// NOTIFICATION
// =============================================================================
function showNotification(message, type = "info") {
    // Simple console-based notification (can be upgraded to toast)
    const color = type === "success" ? "#10b981" : type === "error" ? "#ef4444" : "#3b82f6";
    const prefix = type === "success" ? "[OK]" : type === "error" ? "[ERROR]" : "[INFO]";
    appendConsole(`${prefix} ${message}`, type === "error" ? "error-line" : "comment");
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

