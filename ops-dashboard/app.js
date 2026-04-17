/* ═══════════════════════════════════════════════════════════════════════════
   OPS COMMAND CENTER — Application Logic
   Live-polling dashboard with animated gauges & status tracking
   ═══════════════════════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    // ─── Configuration ──────────────────────────────────────────────────────
    const DEFAULT_CONFIG = {
        apiUrl: '/internal/ops/status/',
        refreshInterval: 15,      // seconds
        maxActivityItems: 30,
        latencyHistorySize: 20,
    };

    let config = { ...DEFAULT_CONFIG };
    let pollTimer = null;
    let isPolling = false;
    let previousState = null;
    let activityLog = [];
    let latencyHistory = { redis: [], postgres: [], celery: [] };
    let fetchCount = 0;
    let lastData = null;

    // ─── DOM Cache ──────────────────────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        // Header
        connectionStatus: $('#connectionStatus'),
        lastUpdated: $('#lastUpdated'),
        serverHost: $('#serverHost'),
        refreshBtn: $('#refreshBtn'),
        settingsBtn: $('#settingsBtn'),
        pollIntervalDisplay: $('#pollIntervalDisplay'),
        footerStatus: $('#footerStatus'),

        // Settings
        settingsPanel: $('#settingsPanel'),
        apiUrlInput: $('#apiUrlInput'),
        refreshIntervalInput: $('#refreshInterval'),
        saveSettingsBtn: $('#saveSettingsBtn'),
        cancelSettingsBtn: $('#cancelSettingsBtn'),

        // Health banner
        healthRing: $('#healthRing'),
        healthRingFill: $('#healthRingFill'),
        healthScore: $('#healthScore'),
        healthStatus: $('#healthStatus'),
        healthDetail: $('#healthDetail'),

        // Vitals
        cpuValue: $('#cpuValue'),
        cpuRing: $('#cpuRing'),
        memoryValue: $('#memoryValue'),
        memoryRing: $('#memoryRing'),
        memoryDetail: $('#memoryDetail'),
        diskValue: $('#diskValue'),
        diskRing: $('#diskRing'),
        diskDetail: $('#diskDetail'),
        uptimeValue: $('#uptimeValue'),

        // Grids
        containerGrid: $('#containerGrid'),
        containerCount: $('#containerCount'),
        servicesGrid: $('#servicesGrid'),
        endpointsList: $('#endpointsList'),
        activityFeed: $('#activityFeed'),
    };

    // ─── Initialization ─────────────────────────────────────────────────────
    function init() {
        loadConfig();
        bindEvents();
        showDemoOnFirstLoad();
        startPolling();
    }

    function loadConfig() {
        try {
            const saved = localStorage.getItem('ops-dashboard-config');
            if (saved) {
                const parsed = JSON.parse(saved);
                config = { ...DEFAULT_CONFIG, ...parsed };
            }
        } catch (e) { /* ignore */ }

        dom.apiUrlInput.value = config.apiUrl;
        dom.refreshIntervalInput.value = config.refreshInterval;
        dom.pollIntervalDisplay.textContent = config.refreshInterval;
    }

    function saveConfig() {
        config.apiUrl = dom.apiUrlInput.value.trim() || DEFAULT_CONFIG.apiUrl;
        config.refreshInterval = Math.max(5, Math.min(300, parseInt(dom.refreshIntervalInput.value) || 15));

        localStorage.setItem('ops-dashboard-config', JSON.stringify({
            apiUrl: config.apiUrl,
            refreshInterval: config.refreshInterval,
        }));

        dom.pollIntervalDisplay.textContent = config.refreshInterval;
        restartPolling();
        closeSettings();
    }

    function bindEvents() {
        dom.refreshBtn.addEventListener('click', () => fetchStatus(true));
        dom.settingsBtn.addEventListener('click', toggleSettings);
        dom.saveSettingsBtn.addEventListener('click', saveConfig);
        dom.cancelSettingsBtn.addEventListener('click', closeSettings);

        // Close settings on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeSettings();
        });
    }

    function toggleSettings() {
        dom.settingsPanel.classList.toggle('open');
    }

    function closeSettings() {
        dom.settingsPanel.classList.remove('open');
    }

    // ─── Polling ────────────────────────────────────────────────────────────
    function startPolling() {
        fetchStatus(true);
        pollTimer = setInterval(() => fetchStatus(false), config.refreshInterval * 1000);
    }

    function restartPolling() {
        if (pollTimer) clearInterval(pollTimer);
        startPolling();
    }

    async function fetchStatus(manual = false) {
        if (isPolling) return;
        isPolling = true;

        if (manual) {
            dom.refreshBtn.classList.add('spinning');
        }

        try {
            const resp = await fetch(config.apiUrl, {
                headers: { 'Accept': 'application/json' },
                signal: AbortSignal.timeout(12000),
            });

            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();
            fetchCount++;
            lastData = data;

            setConnectionStatus('connected');
            updateDashboard(data);
            detectChanges(data);
            previousState = data;

            dom.lastUpdated.textContent = new Date().toLocaleTimeString();
            dom.footerStatus.textContent = `Last fetch: ${new Date().toLocaleTimeString()} (${fetchCount} total)`;

        } catch (err) {
            console.warn('Fetch failed:', err.message);
            setConnectionStatus('error', err.message);

            // On first load failure, show demo data
            if (fetchCount === 0) {
                updateDashboard(getDemoData());
                dom.footerStatus.textContent = 'Using demo data — configure API URL in settings';
                addActivity('amber', 'Dashboard', `API unreachable: ${err.message}. Showing demo data.`);
            } else {
                addActivity('red', 'Connection', `Failed to reach API: ${err.message}`);
                dom.footerStatus.textContent = `Error: ${err.message}`;
            }
        } finally {
            isPolling = false;
            dom.refreshBtn.classList.remove('spinning');
        }
    }

    // ─── Connection Status ──────────────────────────────────────────────────
    function setConnectionStatus(state, message) {
        const statusEl = dom.connectionStatus;
        const dot = statusEl.querySelector('.pulse-dot');
        const text = statusEl.querySelector('.header__status-text');

        statusEl.classList.remove('header__status--error');
        dot.className = 'pulse-dot';

        if (state === 'connected') {
            dot.classList.add('pulse-dot--green');
            text.textContent = 'Connected';
        } else {
            statusEl.classList.add('header__status--error');
            dot.classList.add('pulse-dot--red');
            text.textContent = 'Disconnected';
        }
    }

    // ─── Dashboard Update ───────────────────────────────────────────────────
    function updateDashboard(data) {
        updateHealthBanner(data);
        updateVitals(data.server);
        updateContainers(data.containers);
        updateServices(data.services);
        updateEndpoints(data.endpoints);
    }

    // ─── Health Banner ──────────────────────────────────────────────────────
    function updateHealthBanner(data) {
        let score = 100;
        let issues = [];

        // Deduct for container problems
        const containers = data.containers || [];
        const downContainers = containers.filter(c =>
            c.state !== 'running' && c.name !== 'outfi-certbot'
        );
        score -= downContainers.length * 20;
        downContainers.forEach(c => issues.push(`${c.name} is ${c.state}`));

        // Deduct for unhealthy containers
        const unhealthy = containers.filter(c => c.health === 'unhealthy');
        score -= unhealthy.length * 10;
        unhealthy.forEach(c => issues.push(`${c.name} unhealthy`));

        // Deduct for service problems
        const services = data.services || {};
        Object.entries(services).forEach(([name, svc]) => {
            if (svc.status === 'down') {
                score -= 25;
                issues.push(`${name} is down`);
            } else if (svc.status === 'degraded') {
                score -= 10;
                issues.push(`${name} degraded`);
            }
        });

        // Deduct for endpoint problems
        const endpoints = data.endpoints || [];
        endpoints.forEach(ep => {
            if (!ep.ok) {
                score -= 15;
                issues.push(`${ep.label || ep.url} unreachable`);
            }
        });

        // Deduct for high resource usage
        const server = data.server || {};
        if (server.cpu_percent > 90) { score -= 10; issues.push('CPU above 90%'); }
        if (server.memory?.percent > 90) { score -= 10; issues.push('Memory above 90%'); }
        if (server.disk?.percent > 90) { score -= 10; issues.push('Disk above 90%'); }

        score = Math.max(0, Math.min(100, score));

        // Update ring
        const circumference = 339.29;
        const offset = circumference - (score / 100) * circumference;
        dom.healthRingFill.style.strokeDashoffset = offset;

        // Color the ring
        dom.healthRing.className = 'health-ring';
        if (score >= 80) {
            dom.healthRing.classList.add('health-ring--ok');
        } else if (score >= 50) {
            dom.healthRing.classList.add('health-ring--warning');
        } else {
            dom.healthRing.classList.add('health-ring--critical');
        }

        dom.healthScore.textContent = score;

        // Status text
        if (score >= 90) {
            dom.healthStatus.textContent = 'All Systems Operational';
            dom.healthDetail.textContent = `${containers.filter(c => c.state === 'running').length} containers running · All services healthy`;
        } else if (score >= 70) {
            dom.healthStatus.textContent = 'Minor Issues Detected';
            dom.healthDetail.textContent = issues.slice(0, 2).join(' · ');
        } else if (score >= 50) {
            dom.healthStatus.textContent = 'Degraded Performance';
            dom.healthDetail.textContent = issues.slice(0, 3).join(' · ');
        } else {
            dom.healthStatus.textContent = 'Critical Issues';
            dom.healthDetail.textContent = issues.slice(0, 3).join(' · ');
        }
    }

    // ─── System Vitals ──────────────────────────────────────────────────────
    function updateVitals(server) {
        if (!server) return;

        // CPU
        animateRing(dom.cpuRing, server.cpu_percent);
        dom.cpuValue.textContent = `${Math.round(server.cpu_percent)}%`;
        setRingLevel(dom.cpuRing, server.cpu_percent);

        // Memory
        const mem = server.memory || {};
        animateRing(dom.memoryRing, mem.percent || 0);
        dom.memoryValue.textContent = `${Math.round(mem.percent || 0)}%`;
        dom.memoryDetail.textContent = `${mem.used_mb || 0} / ${mem.total_mb || 0} MB`;
        setRingLevel(dom.memoryRing, mem.percent || 0);

        // Disk
        const disk = server.disk || {};
        animateRing(dom.diskRing, disk.percent || 0);
        dom.diskValue.textContent = `${Math.round(disk.percent || 0)}%`;
        dom.diskDetail.textContent = `${disk.used_gb || 0} / ${disk.total_gb || 0} GB`;
        setRingLevel(dom.diskRing, disk.percent || 0);

        // Uptime
        dom.uptimeValue.textContent = server.uptime || '--';

        // Server host
        dom.serverHost.textContent = server.hostname || '54.81.148.134';
    }

    function animateRing(el, percent) {
        const circumference = 263.89;
        const offset = circumference - (Math.min(100, percent) / 100) * circumference;
        el.style.strokeDashoffset = offset;
    }

    function setRingLevel(el, percent) {
        el.removeAttribute('data-level');
        if (percent > 85) el.setAttribute('data-level', 'critical');
        else if (percent > 65) el.setAttribute('data-level', 'warning');
    }

    // ─── Docker Containers ──────────────────────────────────────────────────
    function updateContainers(containers) {
        if (!containers || !containers.length) return;

        dom.containerCount.textContent = containers.length;

        // Container icon mapping
        const icons = {
            'outfi-api':     '🚀',
            'outfi-db':      '🐘',
            'outfi-redis':   '⚡',
            'outfi-celery':  '🌿',
            'outfi-nginx':   '🌐',
            'outfi-certbot': '🔒',
        };

        dom.containerGrid.innerHTML = containers.map((c, i) => {
            const healthClass = getHealthClass(c);
            const statusLabel = c.health === 'healthy' ? 'Healthy' :
                               c.state === 'running' ? 'Running' :
                               c.state === 'exited' ? 'Exited' :
                               c.health || c.state || 'Unknown';

            return `
                <div class="container-card glass-card" style="animation-delay: ${i * 0.05}s">
                    <div class="container-card__header">
                        <span class="container-card__name">${icons[c.name] || '📦'} ${c.name}</span>
                        <span class="container-card__status container-card__status--${healthClass}">
                            <span class="pulse-dot pulse-dot--${healthClass === 'running' || healthClass === 'healthy' ? 'green' : healthClass === 'exited' ? 'red' : 'amber'}"></span>
                            ${statusLabel}
                        </span>
                    </div>
                    <div class="container-card__meta">
                        <div class="container-card__row">
                            <span class="container-card__row-label">Status</span>
                            <span class="container-card__row-value">${c.status || '--'}</span>
                        </div>
                        ${c.ports ? `
                        <div class="container-card__row">
                            <span class="container-card__row-label">Ports</span>
                            <span class="container-card__row-value">${truncate(c.ports, 30)}</span>
                        </div>` : ''}
                    </div>
                    <div class="container-card__image">${c.image || ''}</div>
                </div>
            `;
        }).join('');
    }

    function getHealthClass(container) {
        if (container.health === 'healthy') return 'healthy';
        if (container.health === 'unhealthy') return 'unhealthy';
        if (container.state === 'running') return 'running';
        if (container.state === 'exited') return 'exited';
        return 'unknown';
    }

    // ─── Service Health ─────────────────────────────────────────────────────
    function updateServices(services) {
        if (!services) return;

        const serviceConfig = {
            redis: { icon: '⚡', label: 'Redis', iconClass: 'redis' },
            postgres: { icon: '🐘', label: 'PostgreSQL', iconClass: 'postgres' },
            celery: { icon: '🌿', label: 'Celery Worker', iconClass: 'celery' },
        };

        // Update latency history
        Object.entries(services).forEach(([key, svc]) => {
            if (!latencyHistory[key]) latencyHistory[key] = [];
            latencyHistory[key].push(svc.latency_ms || 0);
            if (latencyHistory[key].length > config.latencyHistorySize) {
                latencyHistory[key].shift();
            }
        });

        dom.servicesGrid.innerHTML = Object.entries(services).map(([key, svc]) => {
            const cfg = serviceConfig[key] || { icon: '🔧', label: key, iconClass: key };
            const stateClass = svc.status === 'ok' ? 'ok' : svc.status === 'degraded' ? 'degraded' : 'down';
            const history = latencyHistory[key] || [];
            const maxLatency = Math.max(...history, 1);

            // Build latency mini-bars
            const bars = history.map(v => {
                const height = Math.max(2, (v / maxLatency) * 24);
                const level = v > 100 ? 'critical' : v > 50 ? 'warning' : '';
                return `<div class="latency-bar" style="height: ${height}px" data-level="${level}"></div>`;
            }).join('');

            let extraMetrics = '';
            if (key === 'celery') {
                extraMetrics = `
                    <div class="service-card__metric">
                        <div class="service-card__metric-value">${svc.workers ?? '--'}</div>
                        <div class="service-card__metric-label">Workers</div>
                    </div>
                    <div class="service-card__metric">
                        <div class="service-card__metric-value">${svc.active_tasks ?? '--'}</div>
                        <div class="service-card__metric-label">Active Tasks</div>
                    </div>
                `;
            }

            return `
                <div class="service-card glass-card">
                    <div class="service-card__header">
                        <div class="service-card__icon service-card__icon--${cfg.iconClass}">
                            ${cfg.icon}
                        </div>
                        <div class="service-card__info">
                            <div class="service-card__name">${cfg.label}</div>
                            <div class="service-card__state service-card__state--${stateClass}">
                                ${svc.status === 'ok' ? '● Operational' : svc.status === 'degraded' ? '◐ Degraded' : '○ Down'}
                            </div>
                        </div>
                    </div>
                    <div class="service-card__metrics">
                        <div class="service-card__metric">
                            <div class="service-card__metric-value">${svc.latency_ms >= 0 ? svc.latency_ms + 'ms' : '--'}</div>
                            <div class="service-card__metric-label">Latency</div>
                        </div>
                        ${extraMetrics}
                    </div>
                    <div class="latency-bar-container">${bars}</div>
                </div>
            `;
        }).join('');
    }

    // ─── Endpoint Monitor ───────────────────────────────────────────────────
    function updateEndpoints(endpoints) {
        if (!endpoints || !endpoints.length) return;

        dom.endpointsList.innerHTML = endpoints.map((ep, i) => {
            const isOk = ep.ok;
            const dotClass = isOk ? 'green' : 'red';
            const statusClass = isOk ? 'ok' : 'error';

            return `
                <div class="endpoint-row glass-card" style="animation-delay: ${i * 0.08}s">
                    <span class="endpoint-row__dot pulse-dot pulse-dot--${dotClass}"></span>
                    <div class="endpoint-row__info">
                        <div class="endpoint-row__label">${ep.label || 'Endpoint'}</div>
                        <div class="endpoint-row__url">${ep.url}</div>
                    </div>
                    <div class="endpoint-row__metrics">
                        <span class="endpoint-row__status-code endpoint-row__status-code--${statusClass}">
                            ${ep.status || 'ERR'}
                        </span>
                        <span class="endpoint-row__latency">
                            ${ep.latency_ms >= 0 ? ep.latency_ms + 'ms' : 'timeout'}
                        </span>
                    </div>
                </div>
            `;
        }).join('');
    }

    // ─── Change Detection & Activity Feed ───────────────────────────────────
    function detectChanges(data) {
        if (!previousState) return;

        // Container status changes
        const prevContainers = {};
        (previousState.containers || []).forEach(c => prevContainers[c.name] = c);

        (data.containers || []).forEach(c => {
            const prev = prevContainers[c.name];
            if (!prev) {
                addActivity('blue', c.name, 'New container detected');
            } else if (prev.state !== c.state) {
                if (c.state === 'running') {
                    addActivity('green', c.name, `Container started (was: ${prev.state})`);
                } else {
                    addActivity('red', c.name, `Container ${c.state} (was: ${prev.state})`);
                }
            } else if (prev.health !== c.health && c.health === 'unhealthy') {
                addActivity('amber', c.name, 'Container became unhealthy');
            }
        });

        // Service status changes
        const prevServices = previousState.services || {};
        const currServices = data.services || {};

        Object.entries(currServices).forEach(([key, svc]) => {
            const prev = prevServices[key];
            if (prev && prev.status !== svc.status) {
                if (svc.status === 'ok') {
                    addActivity('green', key, 'Service recovered');
                } else if (svc.status === 'down') {
                    addActivity('red', key, 'Service went down');
                } else {
                    addActivity('amber', key, `Service status: ${svc.status}`);
                }
            }
        });

        // Endpoint changes
        const prevEndpoints = {};
        (previousState.endpoints || []).forEach(ep => prevEndpoints[ep.url] = ep);

        (data.endpoints || []).forEach(ep => {
            const prev = prevEndpoints[ep.url];
            if (prev && prev.ok !== ep.ok) {
                if (ep.ok) {
                    addActivity('green', ep.label || ep.url, `Endpoint recovered (${ep.status})`);
                } else {
                    addActivity('red', ep.label || ep.url, `Endpoint down (${ep.status || 'unreachable'})`);
                }
            }
        });
    }

    function addActivity(color, source, message) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        activityLog.unshift({ color, source, message, time: timeStr, timestamp: now.getTime() });

        // Trim
        if (activityLog.length > config.maxActivityItems) {
            activityLog = activityLog.slice(0, config.maxActivityItems);
        }

        renderActivity();
    }

    function renderActivity() {
        if (activityLog.length === 0) {
            dom.activityFeed.innerHTML = `
                <div class="activity-feed__empty">
                    <p>Monitoring started — events will appear here</p>
                </div>
            `;
            return;
        }

        dom.activityFeed.innerHTML = activityLog.map(item => `
            <div class="activity-item">
                <span class="activity-item__time">${item.time}</span>
                <span class="activity-item__dot activity-item__dot--${item.color}"></span>
                <span class="activity-item__text"><strong>${item.source}</strong> — ${item.message}</span>
            </div>
        `).join('');
    }

    // ─── Demo Data ──────────────────────────────────────────────────────────
    function showDemoOnFirstLoad() {
        // Show loading state initially
        dom.healthStatus.textContent = 'Connecting to server...';
        dom.healthDetail.textContent = 'Fetching system status from API';
    }

    function getDemoData() {
        return {
            server: {
                hostname: 'ip-172-31-89-42',
                uptime: 'up 14 days, 3 hours',
                cpu_percent: 23.4,
                memory: { total_mb: 2048, used_mb: 1180, percent: 57.6 },
                disk: { total_gb: 20, used_gb: 8, percent: 41 },
            },
            containers: [
                { name: 'outfi-api', image: 'outfi-api:latest', state: 'running', status: 'Up 3 days (healthy)', health: 'healthy', ports: '8000/tcp' },
                { name: 'outfi-db', image: 'postgres:16-alpine', state: 'running', status: 'Up 14 days (healthy)', health: 'healthy', ports: '5432/tcp' },
                { name: 'outfi-redis', image: 'redis:7-alpine', state: 'running', status: 'Up 14 days (healthy)', health: 'healthy', ports: '6379/tcp' },
                { name: 'outfi-celery', image: 'outfi-celery:latest', state: 'running', status: 'Up 3 days (healthy)', health: 'healthy', ports: '' },
                { name: 'outfi-nginx', image: 'outfi-nginx:latest', state: 'running', status: 'Up 14 days', health: 'running', ports: '0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp' },
                { name: 'outfi-certbot', image: 'certbot/certbot', state: 'running', status: 'Up 14 days', health: 'running', ports: '' },
            ],
            services: {
                redis: { status: 'ok', latency_ms: 1.2 },
                postgres: { status: 'ok', latency_ms: 3.8 },
                celery: { status: 'ok', latency_ms: 250, workers: 1, active_tasks: 0 },
            },
            endpoints: [
                { url: 'https://outfi.ai', label: 'Outfi Landing', status: 200, latency_ms: 142, ok: true },
                { url: 'https://api.outfi.ai/api/v1/health/', label: 'API Health', status: 200, latency_ms: 85, ok: true },
            ],
            timestamp: new Date().toISOString(),
        };
    }

    // ─── Utilities ──────────────────────────────────────────────────────────
    function truncate(str, max) {
        if (!str) return '';
        return str.length > max ? str.substring(0, max) + '…' : str;
    }

    // ─── Boot ───────────────────────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
