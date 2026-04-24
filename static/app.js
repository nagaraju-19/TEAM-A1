const app = document.querySelector("#app");
const toast = document.querySelector("#toast");

const state = {
  user: null,
  loginRole: "faculty",
  view: "attendance",
  dashboard: null,
  attendanceDate: new Date().toISOString().slice(0, 10),
  attendanceRows: [],
  students: [],
  facultyUsers: [],
  studentDashboard: null,
  notificationMode: "simulation",
  sidebarOpen: false,
};

const icons = {
  calendar:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M8 2v4M16 2v4M3 10h18"/><rect x="3" y="4" width="18" height="18" rx="2"/></svg>',
  users:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  phone:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M22 16.92v3a2 2 0 0 1-2.18 2A19.86 19.86 0 0 1 11.19 19a19.5 19.5 0 0 1-6-6A19.86 19.86 0 0 1 2.08 4.18 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.12.91.32 1.8.57 2.65a2 2 0 0 1-.45 2.11L7.91 9.75a16 16 0 0 0 6.34 6.34l1.27-1.27a2 2 0 0 1 2.11-.45c.85.25 1.74.45 2.65.57A2 2 0 0 1 22 16.92z"/></svg>',
  message:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 15a4 4 0 0 1-4 4H7l-4 4V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/></svg>',
  save:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg>',
  plus:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 5v14M5 12h14"/></svg>',
  edit:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
  logout:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></svg>',
  menu:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 6h16M4 12h16M4 18h16"/></svg>',
  check:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="m20 6-11 11-5-5"/></svg>',
  alert:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
};

function icon(name) {
  return icons[name] || "";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 3400);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "";
  const parsed = new Date(`${value}T00:00:00`);
  return parsed.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

function initial(name) {
  return (name || "U").trim().slice(0, 1).toUpperCase();
}

function render() {
  if (!state.user) {
    renderLogin();
  } else if (state.user.role === "faculty") {
    renderFaculty();
  } else {
    renderStudent();
  }
}

function renderLogin() {
  app.className = "app-shell";
  app.innerHTML = `
    <main class="auth-layout">
      <section class="auth-visual" aria-label="College attendance">
        <div class="auth-copy">
          <div class="brand-row">
            <span class="brand-mark">CA</span>
            <span><strong>College Attendance</strong></span>
          </div>
          <h1>Attendance control room</h1>
          <p>Faculty record daily attendance, student profiles stay organized, and parent alerts are triggered automatically when an absence is saved.</p>
        </div>
      </section>
      <section class="auth-panel-wrap">
        <div class="auth-panel">
          <p class="eyebrow">Secure login</p>
          <h2>${state.loginRole === "faculty" ? "Faculty dashboard" : "Student portal"}</h2>
          <p class="subcopy">${state.loginRole === "faculty" ? "Manage attendance, student details, and parent notification logs." : "Check attendance percentage and daily records."}</p>
          <div class="segmented" role="tablist" aria-label="Login type">
            <button class="${state.loginRole === "faculty" ? "active" : ""}" data-login-role="faculty" type="button">Faculty</button>
            <button class="${state.loginRole === "student" ? "active" : ""}" data-login-role="student" type="button">Student</button>
          </div>
          <form id="loginForm" class="field-grid">
            <div class="field">
              <label for="username">Username</label>
              <input id="username" name="username" autocomplete="username" placeholder="${state.loginRole === "faculty" ? "Faculty username" : "Student username"}" required />
            </div>
            <div class="field">
              <label for="password">Password</label>
              <input id="password" name="password" type="password" autocomplete="current-password" placeholder="Password" required />
            </div>
            <button class="btn btn-primary" type="submit">${icon("check")} Login</button>
          </form>
          <div class="hint-row">
            <span><strong>Faculty:</strong> faculty / faculty123</span>
            <span><strong>Student:</strong> cse001 / student123</span>
          </div>
        </div>
      </section>
    </main>
  `;

  app.querySelectorAll("[data-login-role]").forEach((button) => {
    button.addEventListener("click", () => {
      state.loginRole = button.dataset.loginRole;
      renderLogin();
    });
  });
  app.querySelector("#loginForm").addEventListener("submit", handleLogin);
}

async function handleLogin(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    const payload = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        role: state.loginRole,
        username: form.get("username"),
        password: form.get("password"),
      }),
    });
    state.user = payload.user;
    state.notificationMode = payload.notificationMode;
    if (state.user.role === "faculty") {
      await loadFacultyDashboard();
    } else {
      await loadStudentDashboard();
    }
    showToast(`Welcome, ${state.user.display_name}`);
  } catch (error) {
    showToast(error.message);
  }
}

async function logout() {
  await api("/api/logout", { method: "POST", body: "{}" }).catch(() => {});
  state.user = null;
  state.dashboard = null;
  state.studentDashboard = null;
  state.view = "attendance";
  render();
}

async function loadFacultyDashboard() {
  const payload = await api("/api/faculty/dashboard");
  state.dashboard = payload;
  state.students = payload.students;
  state.facultyUsers = payload.facultyUsers || [];
  state.attendanceDate = payload.today;
  state.attendanceRows = payload.attendance;
  state.notificationMode = payload.notificationMode;
  render();
}

async function loadAttendanceForDate(date) {
  const payload = await api(`/api/attendance?date=${encodeURIComponent(date)}`);
  state.attendanceDate = payload.date;
  state.attendanceRows = payload.attendance;
  if (state.dashboard) {
    state.dashboard.summary = payload.summary;
  }
  render();
}

async function refreshStudentData() {
  const studentsPayload = await api("/api/students");
  state.students = studentsPayload.students;
  if (state.dashboard) {
    state.dashboard.students = studentsPayload.students;
  }
  const attendancePayload = await api(`/api/attendance?date=${encodeURIComponent(state.attendanceDate)}`);
  state.attendanceRows = attendancePayload.attendance;
  if (state.dashboard) {
    state.dashboard.summary = attendancePayload.summary;
  }
}

async function refreshFacultyUsers() {
  const payload = await api("/api/faculty/users");
  state.facultyUsers = payload.facultyUsers;
  if (state.dashboard) {
    state.dashboard.facultyUsers = payload.facultyUsers;
  }
}

async function loadStudentDashboard() {
  state.studentDashboard = await api("/api/student/dashboard");
  render();
}

function dashboardChrome(content) {
  const nav = state.user.role === "faculty"
      ? [
        ["attendance", "calendar", "Attendance"],
        ["students", "users", "Students"],
        ["facultyUsers", "users", "Faculty"],
        ["alerts", "message", "Alerts"],
      ]
    : [["student", "calendar", "My Attendance"]];

  return `
    <main class="dashboard">
      <aside class="sidebar ${state.sidebarOpen ? "open" : ""}" id="sidebar">
        <div class="brand-row">
          <span class="brand-mark">CA</span>
          <span><strong>College</strong><span>Attendance</span></span>
        </div>
        <nav class="nav-list">
          ${nav
            .map(
              ([view, iconName, label]) => `
                <button class="nav-item ${state.view === view ? "active" : ""}" data-view="${view}" type="button">
                  ${icon(iconName)} <span>${label}</span>
                </button>
              `,
            )
            .join("")}
        </nav>
        <div class="sidebar-footer">
          <small>SMS & call mode</small>
          <strong>${state.notificationMode === "live" ? "Live Twilio delivery" : "Simulation log"}</strong>
        </div>
      </aside>
      <section class="main">
        <header class="topbar">
          <div>
            <button class="btn btn-icon mobile-menu" id="menuToggle" type="button" title="Menu">${icon("menu")}</button>
          </div>
          <div class="user-pill">
            <span class="avatar">${initial(state.user.display_name)}</span>
            <div>
              <strong>${escapeHtml(state.user.display_name)}</strong><br />
              <small>${escapeHtml(state.user.role)}</small>
            </div>
            <button class="btn btn-icon" id="logoutBtn" type="button" title="Logout">${icon("logout")}</button>
          </div>
        </header>
        ${content}
      </section>
    </main>
  `;
}

function renderFaculty() {
  const content = state.view === "students"
    ? renderStudentsView()
    : state.view === "facultyUsers"
      ? renderFacultyUsersView()
    : state.view === "alerts"
      ? renderAlertsView()
      : renderAttendanceView();
  app.className = "app-shell";
  app.innerHTML = dashboardChrome(content);
  bindChrome();
  if (state.view === "attendance") bindAttendanceView();
  if (state.view === "students") bindStudentsView();
  if (state.view === "facultyUsers") bindFacultyUsersView();
}

function bindChrome() {
  app.querySelector("#logoutBtn")?.addEventListener("click", logout);
  app.querySelector("#menuToggle")?.addEventListener("click", () => {
    state.sidebarOpen = !state.sidebarOpen;
    render();
  });
  app.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.view = button.dataset.view;
      state.sidebarOpen = false;
      if (state.view === "alerts") await refreshNotifications();
      if (state.view === "students") await refreshStudentData();
      if (state.view === "facultyUsers") await refreshFacultyUsers();
      render();
    });
  });
}

function renderAttendanceView() {
  const summary = state.dashboard?.summary || {};
  return `
    <section class="section-title">
      <p class="eyebrow">Faculty dashboard</p>
      <h2>Daily attendance</h2>
      <p>Save today’s class status. Absent entries trigger parent SMS and call automatically.</p>
    </section>
    <div class="toolbar">
      <div class="date-control">
        ${icon("calendar")}
        <input id="attendanceDate" type="date" value="${escapeHtml(state.attendanceDate)}" />
      </div>
      <div class="toolbar-actions">
        <button class="btn btn-secondary" id="markAllPresent" type="button">${icon("check")} Mark all present</button>
        <button class="btn btn-primary" id="saveAttendance" type="button">${icon("save")} Save attendance</button>
      </div>
    </div>
    <div class="stats-grid">
      ${statCard("Students", summary.students || 0)}
      ${statCard("Marked", summary.marked || 0)}
      ${statCard("Present", summary.present || 0)}
      ${statCard("Absent", summary.absent || 0)}
    </div>
    <div class="content-grid" style="margin-top: 14px;">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h3>Attendance sheet</h3>
            <p>${formatDate(state.attendanceDate)}</p>
          </div>
          <span class="status-chip ${state.notificationMode === "live" ? "sent" : "simulated"}">${state.notificationMode === "live" ? "Live alerts" : "Simulation mode"}</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Class</th>
                <th>Parent phone</th>
                <th>Status</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              ${state.attendanceRows.map(attendanceRow).join("") || `<tr><td colspan="5" class="empty">No students found.</td></tr>`}
            </tbody>
          </table>
        </div>
      </section>
      <aside class="panel">
        <div class="panel-header">
          <div>
            <h3>Recent parent alerts</h3>
            <p>SMS and call attempts</p>
          </div>
        </div>
        ${renderActivityList(state.dashboard?.notifications || [])}
      </aside>
    </div>
  `;
}

function statCard(label, value) {
  return `
    <div class="stat">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function attendanceRow(row) {
  const status = row.status || "present";
  return `
    <tr data-student-id="${row.student_id}">
      <td>
        <div class="student-cell">
          <strong>${escapeHtml(row.name)}</strong>
          <span>Roll ${escapeHtml(row.roll_no)}</span>
        </div>
      </td>
      <td>${escapeHtml(row.class_name)}</td>
      <td>${escapeHtml(row.parent_phone)}</td>
      <td>
        <div class="status-control">
          ${["present", "absent", "late"]
            .map(
              (item) => `<button type="button" data-status="${item}" class="${status === item ? "active" : ""}">${item[0].toUpperCase()}</button>`,
            )
            .join("")}
        </div>
      </td>
      <td><input class="note-input" value="${escapeHtml(row.note || "")}" placeholder="Optional note" /></td>
    </tr>
  `;
}

function bindAttendanceView() {
  app.querySelector("#attendanceDate").addEventListener("change", (event) => {
    loadAttendanceForDate(event.target.value).catch((error) => showToast(error.message));
  });
  app.querySelector("#markAllPresent").addEventListener("click", () => {
    state.attendanceRows = state.attendanceRows.map((row) => ({ ...row, status: "present" }));
    render();
  });
  app.querySelector("#saveAttendance").addEventListener("click", saveAttendance);
  app.querySelectorAll(".status-control button").forEach((button) => {
    button.addEventListener("click", () => {
      const rowEl = button.closest("tr");
      const studentId = Number(rowEl.dataset.studentId);
      state.attendanceRows = state.attendanceRows.map((row) =>
        row.student_id === studentId ? { ...row, status: button.dataset.status } : row,
      );
      rowEl.querySelectorAll(".status-control button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
    });
  });
}

async function saveAttendance() {
  const records = [...app.querySelectorAll("tbody tr[data-student-id]")].map((rowEl) => {
    const studentId = Number(rowEl.dataset.studentId);
    const active = rowEl.querySelector(".status-control button.active");
    return {
      student_id: studentId,
      status: active?.dataset.status || "present",
      note: rowEl.querySelector(".note-input").value,
    };
  });
  try {
    const result = await api("/api/attendance/bulk", {
      method: "POST",
      body: JSON.stringify({ date: state.attendanceDate, records }),
    });
    state.attendanceRows = result.attendance;
    state.dashboard.summary = result.summary;
    await refreshNotifications();
    const alertCount = result.notifications?.length || 0;
    showToast(alertCount ? `Saved. ${alertCount} parent alert attempt(s) started.` : "Attendance saved.");
    render();
  } catch (error) {
    showToast(error.message);
  }
}

function renderActivityList(items) {
  if (!items.length) {
    return `<div class="empty">No alerts yet.</div>`;
  }
  return `
    <div class="activity-list">
      ${items
        .map(
          (item) => `
            <div class="activity-item">
              <strong>${escapeHtml(item.name)} · ${escapeHtml(item.channel).toUpperCase()}</strong>
              <span>${escapeHtml(item.roll_no)} · ${formatDate(item.attendance_date)} · ${escapeHtml(item.status)}</span>
              <span>${escapeHtml(item.destination)}</span>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

async function refreshNotifications() {
  const payload = await api("/api/notifications");
  if (!state.dashboard) state.dashboard = {};
  state.dashboard.notifications = payload.notifications;
}

function renderStudentsView() {
  return `
    <section class="section-title">
      <p class="eyebrow">Student information</p>
      <h2>Directory management</h2>
      <p>Add students, update parent phone numbers, and keep class information ready for attendance.</p>
    </section>
    <div class="toolbar">
      <div></div>
      <button class="btn btn-primary" id="addStudent" type="button">${icon("plus")} Add student</button>
    </div>
    <section class="panel">
      <div class="panel-header">
        <div>
          <h3>Active students</h3>
          <p>${state.students.length} records</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Roll no</th>
              <th>Name</th>
              <th>Class</th>
              <th>Parent</th>
              <th>Phone</th>
              <th>Login</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${state.students
              .map(
                (student) => `
                  <tr>
                    <td>${escapeHtml(student.roll_no)}</td>
                    <td>${escapeHtml(student.name)}</td>
                    <td>${escapeHtml(student.class_name)}</td>
                    <td>${escapeHtml(student.parent_name)}</td>
                    <td>${escapeHtml(student.parent_phone)}</td>
                    <td>${escapeHtml(student.login_username)}</td>
                    <td><button class="btn btn-icon" data-edit-student="${student.id}" type="button" title="Edit student">${icon("edit")}</button></td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function bindStudentsView() {
  app.querySelector("#addStudent").addEventListener("click", () => openStudentDialog());
  app.querySelectorAll("[data-edit-student]").forEach((button) => {
    button.addEventListener("click", () => {
      const student = state.students.find((item) => item.id === Number(button.dataset.editStudent));
      openStudentDialog(student);
    });
  });
}

function openStudentDialog(student = null) {
  const backdrop = document.createElement("div");
  backdrop.className = "dialog-backdrop";
  backdrop.innerHTML = `
    <div class="dialog" role="dialog" aria-modal="true">
      <div class="panel-header">
        <div>
          <h3>${student ? "Edit student" : "Add student"}</h3>
          <p>${student ? "Update student information and login details." : "Create the student profile and their own login details."}</p>
        </div>
      </div>
      <form id="studentForm">
        <div class="form-grid">
          ${field("roll_no", "Roll no", student?.roll_no || "", true)}
          ${field("name", "Student name", student?.name || "", true)}
          <div class="field">
            <label for="gender">Parent relation word</label>
            <select id="gender" name="gender">
              <option value="son" ${student?.gender === "son" ? "selected" : ""}>son</option>
              <option value="daughter" ${student?.gender === "daughter" ? "selected" : ""}>daughter</option>
              <option value="student" ${!student || student?.gender === "student" ? "selected" : ""}>son/daugther</option>
            </select>
          </div>
          ${field("class_name", "Class", student?.class_name || "CSE-A", true)}
          ${field("email", "Email", student?.email || "", false, "email")}
          ${field("parent_name", "Parent name", student?.parent_name || "", true)}
          ${field("parent_phone", "Parent phone", student?.parent_phone || "", true)}
          ${field("login_username", "Student login username", student?.login_username || "", true)}
          ${field(
            "login_password",
            student ? "New student password" : "Student login password",
            "",
            !student,
            "password",
            student ? "Leave blank to keep password" : "Set password",
          )}
        </div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" id="closeDialog" type="button">Cancel</button>
          <button class="btn btn-primary" type="submit">${icon("save")} Save</button>
        </div>
      </form>
    </div>
  `;
  document.body.append(backdrop);
  backdrop.querySelector("#closeDialog").addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  backdrop.querySelector("#studentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const path = student ? `/api/students/${student.id}` : "/api/students";
      const method = student ? "PUT" : "POST";
      await api(path, { method, body: JSON.stringify(form) });
      await refreshStudentData();
      backdrop.remove();
      showToast("Student information saved.");
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
}

function field(name, label, value, required, type = "text", placeholder = "") {
  return `
    <div class="field">
      <label for="${name}">${label}</label>
      <input id="${name}" name="${name}" type="${type}" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}" ${required ? "required" : ""} />
    </div>
  `;
}

function renderFacultyUsersView() {
  return `
    <section class="section-title">
      <p class="eyebrow">Faculty login</p>
      <h2>Faculty accounts</h2>
      <p>Create usernames and passwords for each faculty member who can manage attendance.</p>
    </section>
    <div class="toolbar">
      <div></div>
      <button class="btn btn-primary" id="addFaculty" type="button">${icon("plus")} Add faculty</button>
    </div>
    <section class="panel">
      <div class="panel-header">
        <div>
          <h3>Active faculty</h3>
          <p>${state.facultyUsers.length} accounts</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Username</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${state.facultyUsers
              .map(
                (faculty) => `
                  <tr>
                    <td>${escapeHtml(faculty.display_name)}</td>
                    <td>${escapeHtml(faculty.username)}</td>
                    <td>${escapeHtml(faculty.created_at ? faculty.created_at.slice(0, 10) : "")}</td>
                    <td><button class="btn btn-icon" data-edit-faculty="${faculty.id}" type="button" title="Edit faculty">${icon("edit")}</button></td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function bindFacultyUsersView() {
  app.querySelector("#addFaculty").addEventListener("click", () => openFacultyDialog());
  app.querySelectorAll("[data-edit-faculty]").forEach((button) => {
    button.addEventListener("click", () => {
      const faculty = state.facultyUsers.find((item) => item.id === Number(button.dataset.editFaculty));
      openFacultyDialog(faculty);
    });
  });
}

function openFacultyDialog(faculty = null) {
  const backdrop = document.createElement("div");
  backdrop.className = "dialog-backdrop";
  backdrop.innerHTML = `
    <div class="dialog" role="dialog" aria-modal="true">
      <div class="panel-header">
        <div>
          <h3>${faculty ? "Edit faculty" : "Add faculty"}</h3>
          <p>${faculty ? "Change username or set a new password." : "Create a faculty login with their own password."}</p>
        </div>
      </div>
      <form id="facultyForm">
        <div class="form-grid">
          ${field("display_name", "Faculty name", faculty?.display_name || "", true)}
          ${field("username", "Faculty login username", faculty?.username || "", true)}
          ${field(
            "password",
            faculty ? "New password" : "Faculty login password",
            "",
            !faculty,
            "password",
            faculty ? "Leave blank to keep password" : "Set password",
          )}
        </div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" id="closeDialog" type="button">Cancel</button>
          <button class="btn btn-primary" type="submit">${icon("save")} Save</button>
        </div>
      </form>
    </div>
  `;
  document.body.append(backdrop);
  backdrop.querySelector("#closeDialog").addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) backdrop.remove();
  });
  backdrop.querySelector("#facultyForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const path = faculty ? `/api/faculty/users/${faculty.id}` : "/api/faculty/users";
      const method = faculty ? "PUT" : "POST";
      await api(path, { method, body: JSON.stringify(form) });
      await refreshFacultyUsers();
      backdrop.remove();
      showToast("Faculty login saved.");
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
}

function renderAlertsView() {
  const notifications = state.dashboard?.notifications || [];
  return `
    <section class="section-title">
      <p class="eyebrow">Parent communication</p>
      <h2>SMS and call log</h2>
      <p>Every automatic absence notification is stored with delivery status and message content.</p>
    </section>
    <section class="panel" style="margin-top: 20px;">
      <div class="panel-header">
        <div>
          <h3>Notification history</h3>
          <p>${state.notificationMode === "live" ? "Twilio delivery is enabled." : "Simulation mode is active until Twilio credentials are configured."}</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Date</th>
              <th>Channel</th>
              <th>Status</th>
              <th>Destination</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            ${notifications
              .map(
                (item) => `
                  <tr>
                    <td><div class="student-cell"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.roll_no)}</span></div></td>
                    <td>${formatDate(item.attendance_date)}</td>
                    <td>${escapeHtml(item.channel).toUpperCase()}</td>
                    <td><span class="status-chip ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></td>
                    <td>${escapeHtml(item.destination)}</td>
                    <td>${escapeHtml(item.message || "")}</td>
                  </tr>
                `,
              )
              .join("") || `<tr><td colspan="6" class="empty">No notification records yet.</td></tr>`}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderStudent() {
  const payload = state.studentDashboard;
  if (!payload) {
    app.innerHTML = `<div class="loading-screen"><div class="loading-mark"></div><p>Loading student portal...</p></div>`;
    return;
  }
  const student = payload.student;
  const stats = payload.stats;
  app.innerHTML = dashboardChrome(`
    <section class="student-profile">
      <div class="profile-band">
        <span class="eyebrow">Student portal</span>
        <h2>${escapeHtml(student.name)}</h2>
        <p>Roll ${escapeHtml(student.roll_no)} · ${escapeHtml(student.class_name)}</p>
      </div>
      <div class="panel progress-ring">
        <div class="ring" style="--pct: ${stats.percentage}">
          <div class="ring-inner">
            <div>
              <strong>${stats.percentage}%</strong><br />
              <span>Attendance</span>
            </div>
          </div>
        </div>
      </div>
    </section>
    <div class="stats-grid" style="margin: 14px 0;">
      ${statCard("Total days", stats.total)}
      ${statCard("Present", stats.present)}
      ${statCard("Late", stats.late)}
      ${statCard("Absent", stats.absent)}
    </div>
    <section class="panel">
      <div class="panel-header">
        <div>
          <h3>Attendance record</h3>
          <p>Latest 90 marked days</p>
        </div>
      </div>
      ${
        payload.records.length
          ? `<div class="record-list">${payload.records
              .map(
                (record) => `
                  <div class="record-item">
                    <strong>${formatDate(record.attendance_date)}</strong>
                    <span><span class="status-chip ${record.status}">${record.status}</span> ${escapeHtml(record.note || "")}</span>
                  </div>
                `,
              )
              .join("")}</div>`
          : `<div class="empty">Attendance has not been marked yet.</div>`
      }
    </section>
  `);
  bindChrome();
}

async function boot() {
  try {
    const payload = await api("/api/me");
    state.user = payload.user;
    state.notificationMode = payload.notificationMode;
    if (state.user.role === "faculty") {
      await loadFacultyDashboard();
    } else {
      await loadStudentDashboard();
    }
  } catch {
    renderLogin();
  }
}

boot();
