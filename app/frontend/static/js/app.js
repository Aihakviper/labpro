import { apiRequest, clearTokens, hasSession, jsonBody, login, logout } from "./api.js";

const state = {
  user: null,
  modalHandler: null,
  currentRoute: "dashboard",
  cache: {},
};

const loginView = document.querySelector("#login-view");
const appView = document.querySelector("#app-view");
const pageContent = document.querySelector("#page-content");
const modalElement = document.querySelector("#form-modal");
const modal = window.bootstrap ? new bootstrap.Modal(modalElement) : null;

const navItems = [
  { route: "dashboard", label: "Dashboard", icon: "DB", roles: ["admin", "librarian", "member"] },
  { route: "books", label: "Books", icon: "BK", roles: ["admin", "librarian", "member"] },
  { route: "members", label: "Members", icon: "MB", roles: ["admin", "librarian"] },
  { route: "loans", label: "Loans", icon: "LN", roles: ["admin", "librarian"] },
  { route: "fines", label: "Fines", icon: "FN", roles: ["admin", "librarian", "member"] },
  { route: "reservations", label: "Reservations", icon: "RS", roles: ["admin", "librarian", "member"] },
  { route: "reports", label: "Reports", icon: "RP", roles: ["admin", "librarian"] },
  { route: "notifications", label: "Notifications", icon: "NT", roles: ["member"] },
  { route: "users", label: "Users & Roles", icon: "UR", roles: ["admin"] },
];

const pageMeta = {
  dashboard: ["Overview", "Dashboard"],
  books: ["Catalog", "Book management"],
  members: ["People", "Member management"],
  loans: ["Circulation", "Borrowing & returns"],
  fines: ["Accounts", "Fine management"],
  reservations: ["Circulation", "Reservation queue"],
  reports: ["Insights", "Reports & analytics"],
  notifications: ["Updates", "Notifications"],
  users: ["Administration", "Users & roles"],
};

const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const formatDate = (value, withTime = false) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return new Intl.DateTimeFormat("en-NG", withTime
    ? { dateStyle: "medium", timeStyle: "short" }
    : { dateStyle: "medium" }).format(date);
};

const formatMoney = (value) => new Intl.NumberFormat("en-NG", {
  style: "currency",
  currency: "NGN",
  maximumFractionDigits: 2,
}).format(Number(value || 0));

const initials = (name = "") => name.split(/\s+/).filter(Boolean).slice(0, 2)
  .map((part) => part[0].toUpperCase()).join("") || "LP";

const statusBadge = (status) => {
  const style = {
    active: "success", available: "success", returned: "success", paid: "success",
    ready: "info", fulfilled: "info",
    waiting: "warning", borrowed: "warning", outstanding: "warning",
    inactive: "danger", unavailable: "danger", overdue: "danger",
    cancelled: "neutral",
  }[String(status).toLowerCase()] || "neutral";
  return `<span class="badge-soft badge-${style}">${escapeHtml(status)}</span>`;
};

function showToast(message, type = "success") {
  const id = `toast-${Date.now()}`;
  const color = type === "danger" ? "text-bg-danger" : "text-bg-success";
  document.querySelector("#toast-container").insertAdjacentHTML("beforeend", `
    <div id="${id}" class="toast ${color}" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">${escapeHtml(message)}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`);
  const element = document.querySelector(`#${id}`);
  const instance = new bootstrap.Toast(element, { delay: 3500 });
  element.addEventListener("hidden.bs.toast", () => element.remove());
  instance.show();
}

function setLoading() {
  pageContent.innerHTML = `
    <div class="loading-state">
      <span class="spinner-border spinner-border-sm" aria-hidden="true"></span>
      Loading workspace…
    </div>`;
}

function emptyRow(columns, message = "No records found") {
  return `<tr><td colspan="${columns}" class="empty-state">${escapeHtml(message)}</td></tr>`;
}

function pageHeading(title, subtitle, actions = "") {
  return `<div class="page-heading">
    <div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(subtitle)}</p></div>
    <div class="page-actions">${actions}</div>
  </div>`;
}

function metric(label, value, note = "") {
  return `<article class="metric-card"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong><span>${escapeHtml(note)}</span></article>`;
}

function modalField({ label, name, type = "text", value = "", required = false, options = null, min = null }) {
  if (options) {
    return `<div class="mb-3"><label class="form-label" for="field-${name}">${escapeHtml(label)}</label>
      <select class="form-select" id="field-${name}" name="${name}" ${required ? "required" : ""}>
        ${options.map(([optionValue, optionLabel]) => `<option value="${escapeHtml(optionValue)}" ${String(value) === String(optionValue) ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`).join("")}
      </select></div>`;
  }
  return `<div class="mb-3"><label class="form-label" for="field-${name}">${escapeHtml(label)}</label>
    <input class="form-control" id="field-${name}" name="${name}" type="${type}" value="${escapeHtml(value ?? "")}" ${required ? "required" : ""} ${min !== null ? `min="${min}"` : ""}>
  </div>`;
}

function openModal({ title, eyebrow = "Manage", fields, submitLabel = "Save", onSubmit }) {
  document.querySelector("#modal-title").textContent = title;
  document.querySelector("#modal-eyebrow").textContent = eyebrow;
  document.querySelector("#modal-body").innerHTML = fields;
  document.querySelector("#modal-submit").textContent = submitLabel;
  state.modalHandler = onSubmit;
  modal.show();
}

document.querySelector("#modal-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.modalHandler) return;
  const button = document.querySelector("#modal-submit");
  button.disabled = true;
  try {
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    await state.modalHandler(data);
    modal.hide();
  } catch (error) {
    showToast(error.message, "danger");
  } finally {
    button.disabled = false;
  }
});

function renderNavigation() {
  const role = state.user.role;
  document.querySelector("#sidebar-nav").innerHTML = navItems
    .filter((item) => item.roles.includes(role))
    .map((item) => `<a class="nav-item-link" data-route="${item.route}" href="#${item.route}">
      <span class="nav-icon">${item.icon}</span><span>${item.label}</span>
    </a>`).join("");
  const userInitials = initials(state.user.full_name);
  document.querySelector("#sidebar-user-name").textContent = state.user.full_name;
  document.querySelector("#sidebar-user-role").textContent = state.user.role;
  document.querySelector("#user-initials").textContent = userInitials;
  document.querySelector("#topbar-avatar").textContent = userInitials;
  document.querySelector("#notification-button").classList.toggle("d-none", role !== "member");
}

function setActiveRoute(route) {
  document.querySelectorAll("[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });
  const [eyebrow, title] = pageMeta[route] || ["Workspace", "Librarian Pro"];
  document.querySelector("#page-eyebrow").textContent = eyebrow;
  document.querySelector("#page-title").textContent = title;
  document.querySelector("#sidebar").classList.remove("open");
}

async function updateNotificationCount() {
  if (state.user?.role !== "member") return;
  try {
    const payload = await apiRequest("/notifications/unread-count");
    document.querySelector("#notification-count").textContent = payload.count;
  } catch {
    document.querySelector("#notification-count").textContent = "0";
  }
}

async function renderDashboard() {
  if (state.user.role === "member") return renderMemberDashboard();
  const [inventory, loans, overdue, fines, members] = await Promise.all([
    apiRequest("/reports/inventory"),
    apiRequest("/reports/borrowed-books?loan_status=borrowed"),
    apiRequest("/reports/overdue-items"),
    apiRequest("/reports/fines?fine_status=outstanding"),
    apiRequest("/members?limit=5&active_only=true"),
  ]);
  pageContent.innerHTML = `
    ${pageHeading("Library overview", "Live operational status across your library.")}
    <section class="metric-grid">
      ${metric("Book titles", inventory.total_titles, `${inventory.available_copies} copies available`)}
      ${metric("Active loans", loans.active_loans, `${overdue.total_overdue} overdue`)}
      ${metric("Active members", members.length, "Showing latest records")}
      ${metric("Outstanding fines", formatMoney(fines.total_outstanding), `${fines.outstanding_fines} unpaid`)}
    </section>
    <section class="dashboard-grid">
      <article class="panel-card table-card">
        <div class="table-toolbar"><div><h3 class="panel-title">Current overdue items</h3><p class="panel-subtitle">Items requiring immediate follow-up.</p></div><a class="btn btn-sm btn-light" href="#reports">View reports</a></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Book</th><th>Member</th><th>Due</th><th>Overdue</th></tr></thead>
        <tbody>${overdue.items.length ? overdue.items.slice(0, 6).map((item) => `<tr>
          <td><span class="cell-title">${escapeHtml(item.book_title)}</span></td>
          <td><span class="cell-title">${escapeHtml(item.member_name)}</span><span class="cell-subtitle d-block">${escapeHtml(item.membership_id)}</span></td>
          <td>${formatDate(item.due_at)}</td><td>${statusBadge(`${item.overdue_days} days`)}</td>
        </tr>`).join("") : emptyRow(4, "No overdue items")}</tbody></table></div>
      </article>
      <aside class="panel-card">
        <h3 class="panel-title">Quick actions</h3><p class="panel-subtitle">Common librarian workflows.</p>
        <div class="quick-actions">
          <a href="#loans" class="quick-action"><span>Issue or return a book</span><b>→</b></a>
          <a href="#members" class="quick-action"><span>Register a member</span><b>→</b></a>
          <a href="#books" class="quick-action"><span>Add catalog record</span><b>→</b></a>
          <a href="#reports" class="quick-action"><span>Generate reports</span><b>→</b></a>
        </div>
      </aside>
    </section>`;
}

async function renderMemberDashboard() {
  const [profile, books, fines, reservations, notifications] = await Promise.all([
    apiRequest("/members/me"),
    apiRequest("/books?limit=6&available_only=true"),
    apiRequest("/fines/me?outstanding_only=true"),
    apiRequest("/reservations/me"),
    apiRequest("/notifications?limit=5"),
  ]);
  const outstanding = fines.reduce((sum, fine) => sum + Number(fine.outstanding_amount), 0);
  const activeReservations = reservations.filter((item) => ["waiting", "ready"].includes(item.status));
  pageContent.innerHTML = `
    ${pageHeading(`Welcome, ${state.user.full_name.split(" ")[0]}`, `Membership ID: ${profile.membership_id}`)}
    <section class="metric-grid">
      ${metric("Available titles", books.length, "Browse the catalog")}
      ${metric("Active reservations", activeReservations.length, `${activeReservations.filter((item) => item.status === "ready").length} ready`)}
      ${metric("Outstanding fines", formatMoney(outstanding), `${fines.length} fine records`)}
      ${metric("Unread updates", notifications.filter((item) => !item.is_read).length, "Recent notifications")}
    </section>
    <section class="dashboard-grid">
      <article class="panel-card table-card">
        <div class="table-toolbar"><div><h3 class="panel-title">Available books</h3><p class="panel-subtitle">Titles ready to borrow.</p></div><a class="btn btn-sm btn-light" href="#books">Browse catalog</a></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Title</th><th>Author</th><th>Category</th><th>Copies</th></tr></thead>
        <tbody>${books.length ? books.map((book) => `<tr><td class="cell-title">${escapeHtml(book.title)}</td><td>${escapeHtml(book.author)}</td><td>${escapeHtml(book.category)}</td><td>${book.available_copies}</td></tr>`).join("") : emptyRow(4)}</tbody></table></div>
      </article>
      <aside class="panel-card">
        <h3 class="panel-title">Recent updates</h3>
        <div class="quick-actions">${notifications.length ? notifications.map((item) => `<a href="#notifications" class="quick-action"><span><b>${escapeHtml(item.title)}</b><small class="d-block text-secondary">${formatDate(item.created_at, true)}</small></span><b>→</b></a>`).join("") : '<p class="text-secondary mt-3">No notifications yet.</p>'}</div>
      </aside>
    </section>`;
}

async function renderBooks() {
  const isStaff = state.user.role !== "member";
  pageContent.innerHTML = `
    ${pageHeading("Book catalog", "Search and manage library titles.", isStaff ? '<button id="add-book" class="btn btn-primary">Add book</button>' : "")}
    <section class="panel-card table-card">
      <div class="table-toolbar">
        <div class="input-group" style="max-width:420px"><input id="book-search" class="form-control" placeholder="Search title, author or ISBN"><button id="book-search-button" class="btn btn-outline-secondary">Search</button></div>
        <label class="form-check"><input id="available-filter" class="form-check-input" type="checkbox"><span class="form-check-label">Available only</span></label>
      </div>
      <div class="table-responsive"><table class="table"><thead><tr><th>Book</th><th>ISBN</th><th>Category</th><th>Availability</th><th></th></tr></thead><tbody id="books-table"></tbody></table></div>
    </section>`;

  async function loadBooks() {
    const query = encodeURIComponent(document.querySelector("#book-search").value.trim());
    const available = document.querySelector("#available-filter").checked;
    const books = await apiRequest(`/books?limit=100${query ? `&q=${query}` : ""}${available ? "&available_only=true" : ""}`);
    state.cache.books = books;
    document.querySelector("#books-table").innerHTML = books.length ? books.map((book) => `<tr>
      <td><span class="cell-title">${escapeHtml(book.title)}</span><span class="cell-subtitle d-block">${escapeHtml(book.author)}</span></td>
      <td>${escapeHtml(book.isbn)}</td><td>${escapeHtml(book.category)}</td>
      <td>${statusBadge(book.is_available ? `${book.available_copies} available` : "unavailable")}<span class="cell-subtitle d-block">${book.total_copies} total</span></td>
      <td class="text-end">${isStaff
        ? `<button class="btn btn-sm btn-light" data-edit-book="${book.id}">Edit</button> <button class="btn btn-sm btn-outline-danger" data-delete-book="${book.id}">Delete</button>`
        : (!book.is_available ? `<button class="btn btn-sm btn-primary" data-reserve-book="${book.id}">Reserve</button>` : "")}</td>
    </tr>`).join("") : emptyRow(5);
  }

  document.querySelector("#book-search-button").addEventListener("click", loadBooks);
  document.querySelector("#book-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadBooks();
  });
  document.querySelector("#available-filter").addEventListener("change", loadBooks);

  if (isStaff) {
    document.querySelector("#add-book").addEventListener("click", () => showBookForm());
    pageContent.onclick = async (event) => {
      const editId = event.target.dataset.editBook;
      const deleteId = event.target.dataset.deleteBook;
      if (editId) showBookForm(state.cache.books.find((book) => book.id === editId));
      if (deleteId && confirm("Delete this book record?")) {
        try {
          await apiRequest(`/books/${deleteId}`, { method: "DELETE" });
          showToast("Book deleted");
          await loadBooks();
        } catch (error) { showToast(error.message, "danger"); }
      }
    };
  } else {
    pageContent.onclick = async (event) => {
      const bookId = event.target.dataset.reserveBook;
      if (!bookId) return;
      try {
        await apiRequest("/reservations", { method: "POST", body: jsonBody({ book_id: bookId }) });
        showToast("Reservation added to the queue");
      } catch (error) { showToast(error.message, "danger"); }
    };
  }
  await loadBooks();
}

function showBookForm(book = null) {
  openModal({
    title: book ? "Update book" : "Add book",
    eyebrow: "Catalog",
    fields: [
      modalField({ label: "Title", name: "title", value: book?.title, required: true }),
      modalField({ label: "Author", name: "author", value: book?.author, required: true }),
      modalField({ label: "ISBN", name: "isbn", value: book?.isbn, required: true }),
      modalField({ label: "Category", name: "category", value: book?.category, required: true }),
      modalField({ label: "Publication year", name: "publication_year", type: "number", value: book?.publication_year }),
      modalField({ label: "Total copies", name: "total_copies", type: "number", value: book?.total_copies ?? 1, required: true, min: 0 }),
      `<div class="mb-3"><label class="form-label" for="field-description">Description</label><textarea class="form-control" id="field-description" name="description" rows="3">${escapeHtml(book?.description || "")}</textarea></div>`,
    ].join(""),
    onSubmit: async (data) => {
      data.total_copies = Number(data.total_copies);
      data.publication_year = data.publication_year ? Number(data.publication_year) : null;
      await apiRequest(book ? `/books/${book.id}` : "/books", {
        method: book ? "PATCH" : "POST", body: jsonBody(data),
      });
      showToast(book ? "Book updated" : "Book added");
      await renderBooks();
    },
  });
}

async function renderMembers() {
  const members = await apiRequest("/members?limit=100");
  state.cache.members = members;
  pageContent.innerHTML = `
    ${pageHeading("Members", "Register members and manage library access.", '<button id="add-member" class="btn btn-primary">Register member</button>')}
    <section class="panel-card table-card"><div class="table-toolbar"><input id="member-filter" class="form-control" style="max-width:380px" placeholder="Filter by name, email or membership ID"></div>
    <div class="table-responsive"><table class="table"><thead><tr><th>Member</th><th>Membership ID</th><th>Contact</th><th>Status</th><th></th></tr></thead><tbody id="members-table"></tbody></table></div></section>`;
  const draw = (filter = "") => {
    const query = filter.toLowerCase();
    const filtered = members.filter((member) => [member.user.full_name, member.user.email, member.membership_id].some((value) => value.toLowerCase().includes(query)));
    document.querySelector("#members-table").innerHTML = filtered.length ? filtered.map((member) => `<tr>
      <td><span class="cell-title">${escapeHtml(member.user.full_name)}</span><span class="cell-subtitle d-block">${escapeHtml(member.user.email)}</span></td>
      <td>${escapeHtml(member.membership_id)}</td><td>${escapeHtml(member.phone_number)}<span class="cell-subtitle d-block">${escapeHtml(member.address || "")}</span></td>
      <td>${statusBadge(member.is_active ? "active" : "inactive")}</td>
      <td class="text-end"><button class="btn btn-sm btn-light" data-edit-member="${member.id}">Edit</button> ${member.is_active ? `<button class="btn btn-sm btn-outline-danger" data-deactivate-member="${member.id}">Deactivate</button>` : ""}</td>
    </tr>`).join("") : emptyRow(5);
  };
  draw();
  document.querySelector("#member-filter").addEventListener("input", (event) => draw(event.target.value));
  document.querySelector("#add-member").addEventListener("click", () => showMemberForm());
  pageContent.onclick = async (event) => {
    const editId = event.target.dataset.editMember;
    const deactivateId = event.target.dataset.deactivateMember;
    if (editId) showMemberForm(members.find((member) => member.id === editId));
    if (deactivateId && confirm("Deactivate this member and revoke their sessions?")) {
      try {
        await apiRequest(`/members/${deactivateId}/deactivate`, { method: "POST" });
        showToast("Member deactivated");
        await renderMembers();
      } catch (error) { showToast(error.message, "danger"); }
    }
  };
}

function showMemberForm(member = null) {
  openModal({
    title: member ? "Update member" : "Register member",
    eyebrow: "Membership",
    fields: [
      modalField({ label: "Full name", name: "full_name", value: member?.user.full_name, required: true }),
      modalField({ label: "Email", name: "email", type: "email", value: member?.user.email, required: true }),
      ...(!member ? [modalField({ label: "Temporary password", name: "password", type: "password", required: true })] : []),
      modalField({ label: "Phone number", name: "phone_number", value: member?.phone_number, required: true }),
      modalField({ label: "Address", name: "address", value: member?.address }),
    ].join(""),
    onSubmit: async (data) => {
      await apiRequest(member ? `/members/${member.id}` : "/members", {
        method: member ? "PATCH" : "POST", body: jsonBody(data),
      });
      showToast(member ? "Member updated" : "Member registered");
      await renderMembers();
    },
  });
}

async function renderLoans() {
  const [loans, members, books] = await Promise.all([
    apiRequest("/loans?limit=100"),
    apiRequest("/members?limit=100&active_only=true"),
    apiRequest("/books?limit=100"),
  ]);
  state.cache.loans = loans;
  pageContent.innerHTML = `
    ${pageHeading("Loans", "Issue books and process returns.", '<button id="issue-book" class="btn btn-primary">Issue book</button>')}
    <section class="panel-card table-card"><div class="table-toolbar"><select id="loan-status-filter" class="form-select" style="max-width:220px"><option value="">All loans</option><option value="borrowed">Active loans</option><option value="returned">Returned loans</option></select></div>
    <div class="table-responsive"><table class="table"><thead><tr><th>Loan</th><th>Member</th><th>Book</th><th>Dates</th><th>Status</th><th></th></tr></thead><tbody id="loans-table"></tbody></table></div></section>`;
  const memberMap = Object.fromEntries(members.map((member) => [member.id, member]));
  const bookMap = Object.fromEntries(books.map((book) => [book.id, book]));
  const draw = (status = "") => {
    const filtered = status ? loans.filter((loan) => loan.status === status) : loans;
    document.querySelector("#loans-table").innerHTML = filtered.length ? filtered.map((loan) => `<tr>
      <td><span class="cell-title">${loan.id.slice(0, 8)}</span></td>
      <td>${escapeHtml(memberMap[loan.member_id]?.user.full_name || loan.member_id.slice(0, 8))}</td>
      <td>${escapeHtml(bookMap[loan.book_id]?.title || loan.book_id.slice(0, 8))}</td>
      <td><span class="cell-subtitle d-block">Borrowed ${formatDate(loan.borrowed_at)}</span><span class="cell-subtitle d-block">Due ${formatDate(loan.due_at)}</span></td>
      <td>${statusBadge(loan.status)}</td><td class="text-end">${loan.status === "borrowed" ? `<button class="btn btn-sm btn-primary" data-return-loan="${loan.id}">Return</button>` : ""}</td>
    </tr>`).join("") : emptyRow(6);
  };
  draw();
  document.querySelector("#loan-status-filter").addEventListener("change", (event) => draw(event.target.value));
  document.querySelector("#issue-book").addEventListener("click", () => {
    openModal({
      title: "Issue book", eyebrow: "Circulation",
      fields: [
        modalField({ label: "Member", name: "member_id", required: true, options: members.map((member) => [member.id, `${member.user.full_name} — ${member.membership_id}`]) }),
        modalField({ label: "Book", name: "book_id", required: true, options: books.map((book) => [book.id, `${book.title} — ${book.available_copies} generally available`]) }),
        modalField({ label: "Due date (optional)", name: "due_at", type: "datetime-local" }),
      ].join(""),
      onSubmit: async (data) => {
        if (!data.due_at) delete data.due_at;
        else data.due_at = new Date(data.due_at).toISOString();
        await apiRequest("/loans", { method: "POST", body: jsonBody(data) });
        showToast("Book issued successfully");
        await renderLoans();
      },
    });
  });
  pageContent.onclick = async (event) => {
    const loanId = event.target.dataset.returnLoan;
    if (!loanId || !confirm("Confirm this book return?")) return;
    try {
      await apiRequest(`/loans/${loanId}/return`, { method: "POST" });
      showToast("Book returned successfully");
      await renderLoans();
    } catch (error) { showToast(error.message, "danger"); }
  };
}

async function renderFines() {
  const isMember = state.user.role === "member";
  const fines = await apiRequest(isMember ? "/fines/me" : "/fines?limit=100");
  const outstanding = fines.reduce((sum, fine) => sum + Number(fine.outstanding_amount), 0);
  pageContent.innerHTML = `
    ${pageHeading("Fines", isMember ? "View your assessed fines and payments." : "Track balances and record payments.", state.user.role === "admin" ? '<button id="fine-config" class="btn btn-light">Fine rate</button>' : "")}
    <section class="metric-grid">${metric("Fine records", fines.length)}${metric("Outstanding", formatMoney(outstanding))}${metric("Paid fines", fines.filter((fine) => fine.status === "paid").length)}${metric("Unpaid fines", fines.filter((fine) => fine.status === "outstanding").length)}</section>
    <section class="panel-card table-card"><div class="table-responsive"><table class="table"><thead><tr><th>Fine</th><th>Overdue</th><th>Assessed</th><th>Paid</th><th>Balance</th><th>Status</th><th></th></tr></thead><tbody>
      ${fines.length ? fines.map((fine) => `<tr><td>${fine.id.slice(0, 8)}</td><td>${fine.overdue_days} days</td><td>${formatMoney(fine.amount)}</td><td>${formatMoney(fine.amount_paid)}</td><td class="cell-title">${formatMoney(fine.outstanding_amount)}</td><td>${statusBadge(fine.status)}</td><td class="text-end">${!isMember && fine.status === "outstanding" ? `<button class="btn btn-sm btn-primary" data-pay-fine="${fine.id}" data-balance="${fine.outstanding_amount}">Record payment</button>` : ""}</td></tr>`).join("") : emptyRow(7)}
    </tbody></table></div></section>`;
  if (!isMember) {
    document.querySelector("#fine-config")?.addEventListener("click", async () => {
      try {
        const config = await apiRequest("/fines/config");
        openModal({
          title: "Configure fine rate", eyebrow: "Fine policy",
          fields: modalField({ label: "Daily rate (NGN)", name: "daily_rate", type: "number", value: config.daily_rate, required: true, min: 0 }),
          onSubmit: async (data) => {
            await apiRequest("/fines/config", { method: "PATCH", body: jsonBody({ daily_rate: data.daily_rate }) });
            showToast("Fine rate updated");
          },
        });
      } catch (error) { showToast(error.message, "danger"); }
    });
    pageContent.onclick = (event) => {
      const fineId = event.target.dataset.payFine;
      if (!fineId) return;
      openModal({
        title: "Record fine payment", eyebrow: "Payment",
        fields: modalField({ label: `Amount (maximum ${formatMoney(event.target.dataset.balance)})`, name: "amount", type: "number", required: true, min: 0.01 }),
        submitLabel: "Record payment",
        onSubmit: async (data) => {
          await apiRequest(`/fines/${fineId}/payments`, { method: "POST", body: jsonBody({ amount: data.amount }) });
          showToast("Payment recorded");
          await renderFines();
        },
      });
    };
  }
}

async function renderReservations() {
  const isMember = state.user.role === "member";
  const reservations = await apiRequest(isMember ? "/reservations/me" : "/reservations?limit=100");
  pageContent.innerHTML = `
    ${pageHeading("Reservations", isMember ? "Track your reservation queue." : "Manage the reservation queue.")}
    <section class="panel-card table-card"><div class="table-responsive"><table class="table"><thead><tr><th>Reservation</th><th>Member</th><th>Book</th><th>Queue</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>
      ${reservations.length ? reservations.map((item) => `<tr><td>${item.id.slice(0, 8)}</td><td>${item.member_id.slice(0, 8)}</td><td>${item.book_id.slice(0, 8)}</td><td>${item.queue_position ?? "—"}</td><td>${statusBadge(item.status)}</td><td>${formatDate(item.created_at)}</td><td class="text-end">${["waiting", "ready"].includes(item.status) ? `<button class="btn btn-sm btn-outline-danger" data-cancel-reservation="${item.id}">Cancel</button>` : ""}</td></tr>`).join("") : emptyRow(7)}
    </tbody></table></div></section>`;
  pageContent.onclick = async (event) => {
    const reservationId = event.target.dataset.cancelReservation;
    if (!reservationId || !confirm("Cancel this reservation?")) return;
    try {
      await apiRequest(`/reservations/${reservationId}`, { method: "DELETE" });
      showToast("Reservation cancelled");
      await renderReservations();
    } catch (error) { showToast(error.message, "danger"); }
  };
}

async function renderNotifications() {
  const notifications = await apiRequest("/notifications?limit=100");
  pageContent.innerHTML = `
    ${pageHeading("Notifications", "Your library updates and transaction alerts.", '<button id="read-all" class="btn btn-light">Mark all as read</button>')}
    <section class="panel-card"><div class="quick-actions">
      ${notifications.length ? notifications.map((item) => `<button class="quick-action text-start w-100 ${item.is_read ? "" : "border border-success"}" data-read-notification="${item.id}" type="button">
        <span><b>${escapeHtml(item.title)}</b><small class="d-block text-secondary mt-1">${escapeHtml(item.message)}</small><small class="d-block text-secondary mt-1">${formatDate(item.created_at, true)}</small></span>${item.is_read ? statusBadge("read") : statusBadge("new")}
      </button>`).join("") : '<p class="text-secondary">No notifications yet.</p>'}
    </div></section>`;
  document.querySelector("#read-all").addEventListener("click", async () => {
    await apiRequest("/notifications/read-all", { method: "POST" });
    showToast("All notifications marked as read");
    await updateNotificationCount();
    await renderNotifications();
  });
  pageContent.onclick = async (event) => {
    const button = event.target.closest("[data-read-notification]");
    if (!button) return;
    await apiRequest(`/notifications/${button.dataset.readNotification}/read`, { method: "POST" });
    await updateNotificationCount();
    await renderNotifications();
  };
}

async function renderUsers() {
  const users = await apiRequest("/users?limit=100");
  pageContent.innerHTML = `
    ${pageHeading("Users & roles", "Manage administrator and librarian accounts.", '<button id="add-user" class="btn btn-primary">Create user</button>')}
    <section class="panel-card table-card"><div class="table-responsive"><table class="table"><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>
      ${users.length ? users.map((user) => `<tr><td><span class="cell-title">${escapeHtml(user.full_name)}</span><span class="cell-subtitle d-block">${escapeHtml(user.email)}</span></td><td>${statusBadge(user.role)}</td><td>${statusBadge(user.is_active ? "active" : "inactive")}</td><td>${formatDate(user.created_at)}</td><td class="text-end"><button class="btn btn-sm btn-light" data-edit-user="${user.id}">Edit</button></td></tr>`).join("") : emptyRow(5)}
    </tbody></table></div></section>`;
  const showUserForm = (user = null) => openModal({
    title: user ? "Update user" : "Create user", eyebrow: "Administration",
    fields: [
      modalField({ label: "Full name", name: "full_name", value: user?.full_name, required: true }),
      ...(!user ? [
        modalField({ label: "Email", name: "email", type: "email", required: true }),
        modalField({ label: "Password", name: "password", type: "password", required: true }),
      ] : []),
      modalField({ label: "Role", name: "role", value: user?.role || "librarian", required: true, options: [["admin", "Administrator"], ["librarian", "Librarian"]] }),
      ...(user ? [modalField({ label: "Status", name: "is_active", value: String(user.is_active), options: [["true", "Active"], ["false", "Inactive"]] })] : []),
    ].join(""),
    onSubmit: async (data) => {
      if (user) data.is_active = data.is_active === "true";
      await apiRequest(user ? `/users/${user.id}` : "/users", { method: user ? "PATCH" : "POST", body: jsonBody(data) });
      showToast(user ? "User updated" : "User created");
      await renderUsers();
    },
  });
  document.querySelector("#add-user").addEventListener("click", () => showUserForm());
  pageContent.onclick = (event) => {
    const userId = event.target.dataset.editUser;
    if (userId) showUserForm(users.find((user) => user.id === userId));
  };
}

async function renderReports() {
  pageContent.innerHTML = `
    ${pageHeading("Reports & analytics", "Operational summaries generated from live data.", '<button id="print-report" class="btn btn-light">Print report</button>')}
    <div class="report-tabs">
      <button class="btn btn-light report-tab active" data-report="borrowed-books">Borrowed books</button>
      <button class="btn btn-light report-tab" data-report="overdue-items">Overdue</button>
      <button class="btn btn-light report-tab" data-report="member-activities">Members</button>
      <button class="btn btn-light report-tab" data-report="fines">Fines</button>
      <button class="btn btn-light report-tab" data-report="inventory">Inventory</button>
    </div>
    <section id="report-output"></section>`;
  document.querySelector("#print-report").addEventListener("click", () => window.print());
  document.querySelectorAll("[data-report]").forEach((button) => button.addEventListener("click", async () => {
    document.querySelectorAll("[data-report]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    await loadReport(button.dataset.report);
  }));
  await loadReport("borrowed-books");
}

async function loadReport(type) {
  const output = document.querySelector("#report-output");
  output.innerHTML = '<div class="loading-state"><span class="spinner-border spinner-border-sm"></span>Generating report…</div>';
  if (type === "borrowed-books") {
    const report = await apiRequest("/reports/borrowed-books");
    output.innerHTML = `<section class="metric-grid">${metric("Total loans", report.total_loans)}${metric("Active", report.active_loans)}${metric("Returned", report.returned_loans)}</section>
      ${reportTable(["Book", "Member", "Borrowed", "Due", "Status"], report.items.map((item) => [item.book_title, `${item.member_name}<small class="cell-subtitle d-block">${item.membership_id}</small>`, formatDate(item.borrowed_at), formatDate(item.due_at), statusBadge(item.status)]))}`;
  } else if (type === "overdue-items") {
    const report = await apiRequest("/reports/overdue-items");
    output.innerHTML = `<section class="metric-grid">${metric("Overdue items", report.total_overdue)}</section>
      ${reportTable(["Book", "Member", "Due", "Overdue"], report.items.map((item) => [item.book_title, item.member_name, formatDate(item.due_at), statusBadge(`${item.overdue_days} days`)]))}`;
  } else if (type === "member-activities") {
    const report = await apiRequest("/reports/member-activities");
    output.innerHTML = `<section class="metric-grid">${metric("Members", report.total_members)}${metric("Active members", report.active_members)}${metric("With active loans", report.members_with_active_loans)}</section>
      ${reportTable(["Member", "Loans", "Active", "Reservations", "Outstanding fines"], report.items.map((item) => [`${item.member_name}<small class="cell-subtitle d-block">${item.membership_id}</small>`, item.total_loans, item.active_loans, item.total_reservations, formatMoney(item.outstanding_fines)]))}`;
  } else if (type === "fines") {
    const report = await apiRequest("/reports/fines");
    output.innerHTML = `<section class="metric-grid">${metric("Assessed", formatMoney(report.total_assessed))}${metric("Paid", formatMoney(report.total_paid))}${metric("Outstanding", formatMoney(report.total_outstanding))}</section>
      ${reportTable(["Member", "Assessed", "Paid", "Balance", "Status"], report.items.map((item) => [item.member_name, formatMoney(item.amount), formatMoney(item.amount_paid), formatMoney(item.outstanding_amount), statusBadge(item.status)]))}`;
  } else {
    const report = await apiRequest("/reports/inventory");
    output.innerHTML = `<section class="metric-grid">${metric("Titles", report.total_titles)}${metric("Total copies", report.total_copies)}${metric("Available", report.available_copies)}${metric("Borrowed", report.borrowed_copies)}</section>
      ${reportTable(["Book", "Category", "Total", "Available", "Borrowed", "Status"], report.items.map((item) => [`${item.title}<small class="cell-subtitle d-block">${item.author}</small>`, item.category, item.total_copies, item.available_copies, item.borrowed_copies, statusBadge(item.is_available ? "available" : "unavailable")]))}`;
  }
}

function reportTable(headers, rows) {
  return `<section class="panel-card table-card"><div class="table-responsive"><table class="table"><thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("") : emptyRow(headers.length)}</tbody></table></div></section>`;
}

const renderers = {
  dashboard: renderDashboard,
  books: renderBooks,
  members: renderMembers,
  loans: renderLoans,
  fines: renderFines,
  reservations: renderReservations,
  reports: renderReports,
  notifications: renderNotifications,
  users: renderUsers,
};

async function navigate() {
  if (!state.user) return;
  const requested = window.location.hash.slice(1) || "dashboard";
  const allowed = navItems.some((item) => item.route === requested && item.roles.includes(state.user.role));
  const route = allowed ? requested : "dashboard";
  state.currentRoute = route;
  setActiveRoute(route);
  pageContent.onclick = null;
  setLoading();
  try {
    await renderers[route]();
    pageContent.focus({ preventScroll: true });
  } catch (error) {
    if (error.status === 401) return showLogin();
    pageContent.innerHTML = `<div class="panel-card empty-state"><h2>Unable to load this page</h2><p>${escapeHtml(error.message)}</p><button class="btn btn-primary" onclick="location.reload()">Retry</button></div>`;
  }
}

function showLogin() {
  clearTokens();
  state.user = null;
  appView.classList.add("d-none");
  loginView.classList.remove("d-none");
}

async function showApp() {
  state.user = await apiRequest("/auth/me");
  loginView.classList.add("d-none");
  appView.classList.remove("d-none");
  renderNavigation();
  await updateNotificationCount();
  await navigate();
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.querySelector("#login-button");
  const errorElement = document.querySelector("#login-error");
  button.disabled = true;
  errorElement.textContent = "";
  try {
    const data = new FormData(event.currentTarget);
    await login(data.get("email"), data.get("password"));
    window.location.hash = "dashboard";
    await showApp();
  } catch (error) {
    errorElement.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  await logout();
  showLogin();
});
document.querySelector("#sidebar-toggle").addEventListener("click", () => document.querySelector("#sidebar").classList.toggle("open"));
document.querySelector("#refresh-page").addEventListener("click", navigate);
window.addEventListener("hashchange", navigate);

async function boot() {
  if (!hasSession()) return showLogin();
  try {
    await showApp();
  } catch {
    showLogin();
  }
}

boot();
