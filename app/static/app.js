// API Base URL
const API_URL = "";

// State Management
let token = localStorage.getItem("token") || "";
let currentUser = null;
let currentSettings = JSON.parse(localStorage.getItem("user_settings")) || { provider: "gemini", api_key: "" };

// Simple Toast System
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `card`;
    toast.style.padding = "0.75rem 1.25rem";
    toast.style.margin = "0";
    toast.style.borderLeft = `4px solid ${type === "success" ? "var(--accent)" : "var(--accent-red)"}`;
    toast.style.boxShadow = "var(--glass-shadow)";
    toast.style.display = "flex";
    toast.style.alignItems = "center";
    toast.style.gap = "0.5rem";
    toast.style.fontSize = "0.9rem";
    toast.style.minWidth = "250px";
    toast.style.animation = "pulse 0.5s ease";

    const icon = document.createElement("i");
    icon.className = type === "success" ? "fa-solid fa-circle-check" : "fa-solid fa-circle-exclamation";
    icon.style.color = type === "success" ? "var(--accent)" : "var(--accent-red)";

    const text = document.createElement("span");
    text.textContent = message;

    toast.appendChild(icon);
    toast.appendChild(text);
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transition = "opacity 0.5s ease";
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}

// Check Authentication
function checkAuth() {
    if (token) {
        document.getElementById("auth-view").style.display = "none";
        document.getElementById("app-view").style.display = "flex";
        fetchUserProfile();
        fetchReportsHistory();
    } else {
        document.getElementById("auth-view").style.display = "flex";
        document.getElementById("app-view").style.display = "none";
    }
}

// Fetch Profile
async function fetchUserProfile() {
    try {
        const res = await fetch(`${API_URL}/api/auth/me`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            currentUser = await res.json();
            document.getElementById("profile-full-name").textContent = currentUser.full_name || currentUser.email;
            document.getElementById("avatar-letter").textContent = (currentUser.full_name || currentUser.email).charAt(0).toUpperCase();
        } else {
            logout();
        }
    } catch (err) {
        console.error("Profile fetch error:", err);
    }
}

// Fetch Reports History
async function fetchReportsHistory() {
    try {
        const res = await fetch(`${API_URL}/api/reports`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const reports = await res.json();
            renderReportsHistory(reports);
        }
    } catch (err) {
        console.error("Reports history error:", err);
    }
}

function renderReportsHistory(reports) {
    const container = document.getElementById("recent-reports-container");
    container.innerHTML = "";
    
    if (reports.length === 0) {
        container.innerHTML = `<p style="color: var(--text-muted); font-style: italic;">No analyses generated yet.</p>`;
        return;
    }

    // Sort by creation date descending
    reports.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    // Update Top Match on Dashboard
    const completed = reports.filter(r => r.status === "COMPLETED" && r.match_score !== null);
    if (completed.length > 0) {
        const maxScore = Math.max(...completed.map(r => r.match_score));
        document.getElementById("dashboard-score-val").textContent = `${maxScore}%`;
        document.getElementById("dashboard-score-ring").style.setProperty("--score-percent", `${maxScore}%`);
        document.getElementById("dashboard-score-desc").textContent = `Max compatibility score matched across ${completed.length} runs.`;
    }

    reports.forEach(report => {
        const item = document.createElement("div");
        item.className = "interactive-list-item";
        
        let scoreBadge = `<span class="badge badge-warning">Pending</span>`;
        if (report.status === "COMPLETED") {
            scoreBadge = `<span class="badge badge-success">${report.match_score || 0}% Match</span>`;
        } else if (report.status === "FAILED") {
            scoreBadge = `<span class="badge" style="background: rgba(239, 68, 68, 0.15); color: var(--accent-red);">Failed</span>`;
        } else if (report.status === "RUNNING") {
            scoreBadge = `<span class="badge badge-info"><i class="fa-solid fa-spinner fa-spin"></i> Running</span>`;
        }

        const dateStr = new Date(report.created_at).toLocaleDateString(undefined, {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });

        item.innerHTML = `
            <div>
                <p style="font-weight: 600; font-family: 'Outfit'; font-size: 0.95rem;">Analysis #${report.id}</p>
                <p style="font-size: 0.8rem; color: var(--text-muted); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    JD: ${report.job_description}
                </p>
                <span style="font-size: 0.75rem; color: var(--text-muted);"><i class="fa-regular fa-calendar"></i> ${dateStr}</span>
            </div>
            <div>${scoreBadge}</div>
        `;
        
        item.onclick = () => {
            if (report.status === "COMPLETED") {
                displayReportResult(report);
                switchTab("analyzer");
            } else if (report.status === "RUNNING") {
                showToast("This analysis is currently running. Please wait.", "info");
                trackProgress(report.id);
                switchTab("analyzer");
            } else {
                showToast("This analysis failed or is empty.", "error");
            }
        };
        
        container.appendChild(item);
    });
}

// Display Report Content
function displayReportResult(report) {
    document.getElementById("analyzer-form").style.display = "none";
    document.getElementById("analysis-progress-card").style.display = "none";
    
    document.getElementById("analysis-result-view").style.display = "block";
    document.getElementById("result-ats-val").textContent = `${report.match_score}%`;
    document.getElementById("result-ats-ring").style.setProperty("--score-percent", `${report.match_score}%`);
    
    // Very simple Markdown to HTML parsing fallback (enough to make headers, lists, tables look good)
    let parsedHTML = formatMarkdownToHTML(report.full_report || "# Complete Report Details Missing");
    document.getElementById("report-markdown-body").innerHTML = parsedHTML;
}

// Form Submission - Auth
document.getElementById("login-form").onsubmit = async (e) => {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    
    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);

    try {
        const res = await fetch(`${API_URL}/api/auth/login`, {
            method: "POST",
            body: formData
        });
        if (res.ok) {
            const data = await res.json();
            token = data.access_token;
            localStorage.setItem("token", token);
            showToast("Successfully authenticated.");
            checkAuth();
        } else {
            const err = await res.json();
            showToast(err.detail || "Authentication failed.", "error");
        }
    } catch (err) {
        showToast("Server connection error.", "error");
    }
};

document.getElementById("signup-form").onsubmit = async (e) => {
    e.preventDefault();
    const full_name = document.getElementById("signup-name").value;
    const email = document.getElementById("signup-email").value;
    const password = document.getElementById("signup-password").value;

    try {
        const res = await fetch(`${API_URL}/api/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, full_name })
        });
        if (res.ok) {
            showToast("Account created! Please log in.");
            toggleAuthForm(false);
        } else {
            const err = await res.json();
            showToast(err.detail || "Registration failed.", "error");
        }
    } catch (err) {
        showToast("Server connection error.", "error");
    }
};

// Form Submission - Settings
document.getElementById("settings-form").onsubmit = (e) => {
    e.preventDefault();
    const provider = document.getElementById("settings-provider").value;
    const api_key = document.getElementById("settings-api-key").value;
    
    currentSettings = { provider, api_key };
    localStorage.setItem("user_settings", JSON.stringify(currentSettings));
    showToast("Settings and API key saved successfully.");
};

// Form Submission - Analyzer Upload
document.getElementById("analyzer-form").onsubmit = async (e) => {
    e.preventDefault();
    
    if (!currentSettings.api_key) {
        showToast("Please enter an LLM API Key in Settings first.", "error");
        switchTab("settings");
        return;
    }

    const jd = document.getElementById("analyzer-jd").value;
    const fileInput = document.getElementById("analyzer-file");
    
    if (fileInput.files.length === 0) {
        showToast("Please select a resume file to upload.", "error");
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);
    formData.append("job_description", jd);

    // Show progress loader
    document.getElementById("analyzer-form").style.display = "none";
    document.getElementById("analysis-progress-card").style.display = "block";
    document.getElementById("analysis-progress-bar").style.width = "10%";
    document.getElementById("progress-status-msg").textContent = "Uploading resume file...";

    try {
        const res = await fetch(`${API_URL}/api/reports/analyze`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "X-LLM-Provider": currentSettings.provider,
                "X-LLM-Key": currentSettings.api_key
            },
            body: formData
        });

        if (res.ok) {
            const report = await res.json();
            trackProgress(report.id);
        } else {
            const err = await res.json();
            showToast(err.detail || "Analysis startup failed.", "error");
            document.getElementById("analyzer-form").style.display = "block";
            document.getElementById("analysis-progress-card").style.display = "none";
        }
    } catch (err) {
        showToast("Server connection error during upload.", "error");
        document.getElementById("analyzer-form").style.display = "block";
        document.getElementById("analysis-progress-card").style.display = "none";
    }
};

// Poll progress of running Crew
let pollInterval = null;
function trackProgress(reportId) {
    if (pollInterval) clearInterval(pollInterval);
    
    let progressVal = 15;
    document.getElementById("analysis-progress-bar").style.width = `${progressVal}%`;
    document.getElementById("progress-status-msg").textContent = "CrewAI initializing 11 specialized agents...";
    
    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`${API_URL}/api/reports/${reportId}`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (res.ok) {
                const report = await res.json();
                
                if (report.status === "COMPLETED") {
                    clearInterval(pollInterval);
                    document.getElementById("analysis-progress-bar").style.width = "100%";
                    showToast("Analysis completed successfully!");
                    displayReportResult(report);
                    fetchReportsHistory();
                } else if (report.status === "FAILED") {
                    clearInterval(pollInterval);
                    showToast(report.error_message || "Analysis failed.", "error");
                    document.getElementById("analyzer-form").style.display = "block";
                    document.getElementById("analysis-progress-card").style.display = "none";
                } else {
                    // Update dummy progress increment to look realistic
                    if (progressVal < 90) progressVal += 5;
                    document.getElementById("analysis-progress-bar").style.width = `${progressVal}%`;
                    
                    if (progressVal < 35) {
                        document.getElementById("progress-status-msg").textContent = "Agents Parsing Resume details...";
                    } else if (progressVal < 55) {
                        document.getElementById("progress-status-msg").textContent = "Keyword & ATS score evaluation...";
                    } else if (progressVal < 75) {
                        document.getElementById("progress-status-msg").textContent = "Recruiter review & bullet rewrites...";
                    } else {
                        document.getElementById("progress-status-msg").textContent = "Report compiler compiling final report...";
                    }
                }
            }
        } catch (err) {
            console.error("Polling error:", err);
        }
    }, 4000);
}

// Form Submission - Career Roadmap
document.getElementById("roadmap-form").onsubmit = async (e) => {
    e.preventDefault();
    if (!currentSettings.api_key) {
        showToast("Please enter an LLM API Key in Settings first.", "error");
        switchTab("settings");
        return;
    }

    const role = document.getElementById("roadmap-role").value;
    const industry = document.getElementById("roadmap-industry").value;
    const skills = document.getElementById("roadmap-skills").value;

    document.getElementById("roadmap-form").style.display = "none";
    document.getElementById("roadmap-progress-card").style.display = "block";

    try {
        const res = await fetch(`${API_URL}/api/coaching/roadmap`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`,
                "X-LLM-Provider": currentSettings.provider,
                "X-LLM-Key": currentSettings.api_key
            },
            body: JSON.stringify({ role_title: role, target_industry: industry, current_skills: skills })
        });

        if (res.ok) {
            const data = await res.json();
            document.getElementById("roadmap-progress-card").style.display = "none";
            document.getElementById("roadmap-result-card").style.display = "block";
            document.getElementById("roadmap-result-body").innerHTML = formatMarkdownToHTML(data.output_data);
            showToast("Roadmap generated!");
        } else {
            const err = await res.json();
            showToast(err.detail || "Roadmap generation failed.", "error");
            document.getElementById("roadmap-form").style.display = "block";
            document.getElementById("roadmap-progress-card").style.display = "none";
        }
    } catch (err) {
        showToast("Server connection error.", "error");
        document.getElementById("roadmap-form").style.display = "block";
        document.getElementById("roadmap-progress-card").style.display = "none";
    }
};

// Form Submission - Interview Prep
document.getElementById("interview-form").onsubmit = async (e) => {
    e.preventDefault();
    if (!currentSettings.api_key) {
        showToast("Please enter an LLM API Key in Settings first.", "error");
        switchTab("settings");
        return;
    }

    const jd = document.getElementById("interview-jd").value;
    const role = document.getElementById("interview-role").value;

    document.getElementById("interview-form").style.display = "none";
    document.getElementById("interview-progress-card").style.display = "block";

    try {
        const res = await fetch(`${API_URL}/api/coaching/interview`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`,
                "X-LLM-Provider": currentSettings.provider,
                "X-LLM-Key": currentSettings.api_key
            },
            body: JSON.stringify({ role_title: role, job_description: jd })
        });

        if (res.ok) {
            const data = await res.json();
            document.getElementById("interview-progress-card").style.display = "none";
            document.getElementById("interview-result-card").style.display = "block";
            document.getElementById("interview-result-body").innerHTML = formatMarkdownToHTML(data.output_data);
            showToast("Interview prep sheet generated!");
        } else {
            const err = await res.json();
            showToast(err.detail || "Generation failed.", "error");
            document.getElementById("interview-form").style.display = "block";
            document.getElementById("interview-progress-card").style.display = "none";
        }
    } catch (err) {
        showToast("Server connection error.", "error");
        document.getElementById("interview-form").style.display = "block";
        document.getElementById("interview-progress-card").style.display = "none";
    }
};

// Print/Export functionality
function printReport() {
    const reportBody = document.getElementById("report-markdown-body").innerHTML;
    const scoreVal = document.getElementById("result-ats-val").textContent;
    
    const printWindow = window.open("", "_blank");
    printWindow.document.write(`
        <html>
        <head>
            <title>Resume Analysis Report - ${scoreVal} Match</title>
            <style>
                body { font-family: sans-serif; padding: 2rem; color: #333; line-height: 1.5; }
                h1, h2, h3 { color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.25rem; }
                table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
                th, td { border: 1px solid #cbd5e1; padding: 0.5rem; text-align: left; }
                th { background: #f1f5f9; }
                blockquote { border-left: 4px solid #6366f1; padding-left: 1rem; color: #475569; font-style: italic; }
            </style>
        </head>
        <body>
            <h1>Resume Analysis & Career Alignment</h1>
            <p><strong>ATS Compatibility Match Score:</strong> ${scoreVal}</p>
            <hr>
            <div>${reportBody}</div>
            <script>window.print();</script>
        </body>
        </html>
    `);
    printWindow.document.close();
}

// Toggle Auth Form login vs signup
function toggleAuthForm(showSignup) {
    if (showSignup) {
        document.getElementById("login-form").style.display = "none";
        document.getElementById("signup-form").style.display = "block";
    } else {
        document.getElementById("login-form").style.display = "block";
        document.getElementById("signup-form").style.display = "none";
    }
}

document.getElementById("toggle-to-signup").onclick = (e) => { e.preventDefault(); toggleAuthForm(true); };
document.getElementById("toggle-to-login").onclick = (e) => { e.preventDefault(); toggleAuthForm(false); };

// Switch Navigation Tabs
function switchTab(tabName) {
    // Nav highlights
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => item.classList.remove("active"));
    
    // Find active anchor item
    const targetItem = Array.from(navItems).find(item => item.getAttribute("onclick").includes(tabName));
    if (targetItem) targetItem.classList.add("active");

    // Sections
    const sections = document.querySelectorAll(".tab-content");
    sections.forEach(sec => sec.classList.remove("active"));
    
    const targetSec = document.getElementById(`tab-${tabName}`);
    if (targetSec) targetSec.classList.add("active");

    // Reset Analyzer view if going back
    if (tabName === "analyzer") {
        document.getElementById("analyzer-form").style.display = "block";
        document.getElementById("analysis-progress-card").style.display = "none";
        document.getElementById("analysis-result-view").style.display = "none";
    }
}

// Logout
function logout() {
    token = "";
    localStorage.removeItem("token");
    currentUser = null;
    showToast("Logged out successfully.");
    checkAuth();
}

// Theme Toggle
function toggleTheme() {
    const isLight = document.body.classList.toggle("light-mode");
    const icon = document.getElementById("theme-icon");
    if (isLight) {
        icon.className = "fa-solid fa-sun";
    } else {
        icon.className = "fa-solid fa-moon";
    }
}

// Pre-fill local settings inputs
if (currentSettings) {
    document.getElementById("settings-provider").value = currentSettings.provider;
    document.getElementById("settings-api-key").value = currentSettings.api_key;
}

// Helper: Basic Markdown Parser for display rendering
function formatMarkdownToHTML(md) {
    let html = md;
    
    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    
    // Italics
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
    
    // Blockquotes
    html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');
    
    // Line breaks
    html = html.replace(/\n$/gim, '<br />');

    // Lists (unordered)
    html = html.replace(/^\s*\-\s+(.*$)/gim, '<ul><li>$1</li></ul>');
    // Combine sequential <ul><li> tags
    html = html.replace(/<\/ul>\s*<ul>/gim, '');

    // Tables
    // Simply detect table separator lines like |---|
    // Note: This is a basic formatter, but enough for markdown display.
    const lines = html.split('\n');
    let inTable = false;
    let tableHtml = '';
    
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trim();
        if (line.startsWith('|') && line.endsWith('|')) {
            if (!inTable) {
                inTable = true;
                tableHtml += '<table>';
            }
            // Skip header separator row like |---|---|
            if (line.includes('---') || line.includes('- -')) {
                continue;
            }
            const cols = line.split('|').map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
            const tag = tableHtml.includes('<thead>') ? 'td' : 'th';
            tableHtml += `<tr>${cols.map(c => `<${tag}>${c}</${tag}>`).join('')}</tr>`;
        } else {
            if (inTable) {
                inTable = false;
                tableHtml += '</table>';
                lines[i] = tableHtml + '\n' + lines[i];
                tableHtml = '';
            }
        }
    }
    
    html = lines.join('\n');
    
    return html;
}

// Initialize on page load
checkAuth();
