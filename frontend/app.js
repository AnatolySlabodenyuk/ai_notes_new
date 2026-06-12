const state = {
    month: "2026-06",
    childId: "",
    snapshot: null,
    admin: {children: [], directions: [], childDirections: [], goals: [], visits: []},
};
const $ = (id) => document.getElementById(id);
const ROUTES = {overview: "#/overview", calendar: "#/calendar", direction: "#/direction/", admin: "#/admin"};

const STATUS_LABELS = {
    scheduled: "Запланировано",
    completed: "Проведено полностью",
    partial: "Проведено частично",
    cancelled: "Отменено",
    absent: "Ребёнок отсутствовал",
    rescheduled: "Перенесено",
    active: "В работе",
    progress: "Есть прогресс",
    achieved: "Достигнута",
    paused: "Приостановлена",
};

const REASON_LABELS = {
    early_pickup: "Забрали раньше",
    late_arrival: "Опоздание",
    specialist_unavailable: "Специалист недоступен",
    child_absent: "Ребёнок отсутствовал",
    family_request: "По просьбе семьи",
};

function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function input(name, value, type = "text") {
    const element = document.createElement("input");
    element.name = name;
    element.type = type;
    element.value = value ?? "";
    return element;
}

function button(text, className, onClick) {
    const element = node("button", className, text);
    element.type = "button";
    element.addEventListener("click", onClick);
    return element;
}

function formatMinutes(minutes) {
    const sign = minutes < 0 ? "-" : "";
    const absolute = Math.abs(minutes);
    const hours = Math.floor(absolute / 60);
    const rest = absolute % 60;
    if (!rest) return `${sign}${hours} ч`;
    if (!hours) return `${sign}${rest} мин`;
    return `${sign}${hours} ч ${rest} мин`;
}

function formatGoalCount(count) {
    const tail = count % 100;
    const last = count % 10;
    if (tail >= 11 && tail <= 14) return `${count} целей`;
    if (last === 1) return `${count} цель`;
    if (last >= 2 && last <= 4) return `${count} цели`;
    return `${count} целей`;
}

function formatDate(value) {
    return new Intl.DateTimeFormat("ru-RU", {day: "numeric", month: "long", weekday: "short"})
        .format(new Date(value));
}

function formatTime(value) {
    return new Intl.DateTimeFormat("ru-RU", {hour: "2-digit", minute: "2-digit"}).format(new Date(value));
}

function empty(message) {
    return node("div", "empty-state", message);
}

async function api(path, options = {}) {
    const response = await fetch(path, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.error?.message || "Не удалось выполнить запрос.");
    return payload;
}

async function mutate(path, method, payload) {
    return api(path, {
        method,
        headers: {"Content-Type": "application/json; charset=utf-8"},
        body: payload === undefined ? undefined : JSON.stringify(payload),
    });
}

function formData(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    Object.keys(data).forEach((key) => {
        if (data[key] === "") data[key] = null;
    });
    return data;
}

function toSchoolIso(value) {
    if (!value) return "";
    return `${value}:00+03:00`;
}

function toLocalInput(value) {
    if (!value) return "";
    return value.slice(0, 16);
}

function currentRoute() {
    const hash = window.location.hash || ROUTES.overview;
    const [path, query = ""] = hash.slice(1).split("?");
    return {path, params: new URLSearchParams(query)};
}

function navigate(hash) {
    window.location.hash = hash;
}

async function loadJournal() {
    $("errorBox").hidden = true;
    try {
        const childQuery = state.childId ? `&child_id=${encodeURIComponent(state.childId)}` : "";
        state.snapshot = await api(`/api/journal?month=${encodeURIComponent(state.month)}${childQuery}`);
        state.childId = state.snapshot.child.id;
        $("journalChildSelect").value = state.childId;
        render();
    } catch (error) {
        $("errorBox").textContent = error.message;
        $("errorBox").hidden = false;
    }
}

async function loadAdmin() {
    const [childrenPayload, directionsPayload] = await Promise.all([
        api("/api/admin/children"),
        api("/api/admin/directions"),
    ]);
    state.admin.children = childrenPayload.children;
    state.admin.directions = directionsPayload.directions;
    const activeChildren = state.admin.children.filter((child) => !child.archived_at);
    if (!state.childId && activeChildren.length) state.childId = activeChildren[0].id;
    renderChildSelectors();
    await loadAdminChildData();
}

async function loadAdminChildData() {
    if (!state.childId) {
        state.admin.childDirections = [];
        state.admin.goals = [];
        state.admin.visits = [];
        render();
        return;
    }
    const [directionsPayload, goalsPayload, visitsPayload] = await Promise.all([
        api(`/api/admin/children/${encodeURIComponent(state.childId)}/directions`),
        api(`/api/admin/children/${encodeURIComponent(state.childId)}/goals`),
        api(`/api/admin/children/${encodeURIComponent(state.childId)}/visits`),
    ]);
    state.admin.childDirections = directionsPayload.child_directions;
    state.admin.goals = goalsPayload.goals;
    state.admin.visits = visitsPayload.visits;
    render();
}

function renderChildSelectors() {
    const activeChildren = state.admin.children.filter((child) => !child.archived_at);
    const options = activeChildren.map((child) => {
        const option = document.createElement("option");
        option.value = child.id;
        option.textContent = child.display_name;
        return option;
    });
    $("journalChildSelect").replaceChildren(...options.map((option) => option.cloneNode(true)));
    $("adminChildSelect").replaceChildren(...options);
    $("journalChildSelect").value = state.childId;
    $("adminChildSelect").value = state.childId;
}

function directionBySlug(slug) {
    return state.snapshot?.directions.find((direction) => direction.slug === slug);
}

function directionById(directionId) {
    return state.admin.directions.find((direction) => direction.id === directionId);
}

function activeAssignedDirections() {
    const activeIds = new Set(
        state.admin.childDirections
            .filter((assignment) => !assignment.archived_at)
            .map((assignment) => assignment.direction_id)
    );
    return state.admin.directions.filter((direction) => !direction.archived_at && activeIds.has(direction.id));
}

function badge(status) {
    return node("span", `badge status-${status}`, STATUS_LABELS[status] || status);
}

function visitCard(visit, direction, modifier = "") {
    const card = node("article", `visit-card ${modifier}`.trim());
    const top = node("div", "visit-top");
    const title = node("strong", "", direction?.title || "Занятие");
    if (direction?.color) title.style.color = direction.color;
    top.append(title, badge(visit.status));
    const time = node(
        "p",
        "muted",
        `${formatDate(visit.scheduled_start)} · ${formatTime(visit.scheduled_start)}–${formatTime(visit.scheduled_end)}`
    );
    card.append(top, time);
    if (visit.actual_minutes) card.append(node("p", "", `Фактически: ${formatMinutes(visit.actual_minutes)}`));
    if (visit.reason_code) card.append(node("p", "reason", REASON_LABELS[visit.reason_code] || visit.reason_code));
    return card;
}

function renderProfile() {
    if (!state.snapshot) return;
    const child = state.snapshot.child;
    $("childName").textContent = child.display_name;
    $("childMeta").textContent = `${child.age_label} · ${child.focus}`;
}

function renderOverview() {
    const cards = state.snapshot.directions.map((direction) => {
        const card = node("button", "direction-card");
        card.type = "button";
        card.dataset.slug = direction.slug;
        card.style.borderTopColor = direction.color;
        card.append(
            node("span", "direction-title", direction.title),
            node("strong", "direction-hours", `${formatMinutes(direction.actual_minutes)} из ${formatMinutes(direction.planned_minutes)}`),
            node("span", "muted", `${formatGoalCount(direction.goals.length)} · открыть ->`)
        );
        card.addEventListener("click", () => navigate(`#/direction/${direction.slug}?month=${state.month}&from=overview`));
        return card;
    });
    $("directionGrid").replaceChildren(...cards);
}

function renderCalendar() {
    $("calendarLegend").replaceChildren(
        ...state.snapshot.directions.map((direction) => {
            const item = node("span", "legend-item");
            const dot = node("i", "legend-dot");
            dot.style.background = direction.color;
            item.append(dot, document.createTextNode(direction.title));
            return item;
        })
    );
    const days = state.snapshot.calendar.map((day) => {
        const block = node("section", "calendar-day");
        const heading = node("div", "calendar-day-heading");
        heading.append(
            node("h3", "", formatDate(`${day.date}T12:00:00+03:00`)),
            node("span", "muted", `${day.visits.length} ${day.visits.length === 1 ? "занятие" : "занятия"}`),
        );
        block.append(heading);
        day.visits.forEach((visit) => {
            const direction = state.snapshot.directions.find((item) => item.id === visit.direction_id);
            const item = node("button", "calendar-visit");
            item.type = "button";
            item.style.borderLeftColor = direction.color;
            item.append(
                node("span", "calendar-time", `${formatTime(visit.scheduled_start)}–${formatTime(visit.scheduled_end)}`),
                node("strong", "", direction.title),
                badge(visit.status)
            );
            item.addEventListener("click", () => navigate(`#/direction/${direction.slug}?month=${state.month}&date=${day.date}&from=calendar`));
            block.append(item);
        });
        return block;
    });
    $("calendarList").replaceChildren(...(days.length ? days : [empty("В этом месяце занятий нет.")]));
}

function sparkline(updates) {
    const values = updates.map((item) => item.metric_value).filter((value) => value !== null && value !== undefined);
    const graph = node("div", "sparkline");
    if (!values.length) return graph;
    const max = Math.max(...values, 1);
    values.forEach((value) => {
        const bar = node("i", "spark-bar");
        bar.style.height = `${Math.max(12, (value / max) * 100)}%`;
        bar.title = String(value);
        graph.append(bar);
    });
    return graph;
}

function goalCard(goal) {
    const card = node("article", "goal-card");
    const top = node("div", "visit-top");
    top.append(node("h3", "", goal.title), badge(goal.status));
    card.append(top, node("p", "goal-lead", goal.description));
    if (goal.metric_label && goal.latest_update?.metric_value !== null && goal.latest_update?.metric_value !== undefined) {
        const metric = node("div", "metric-panel");
        metric.append(node("strong", "metric-value", `${goal.latest_update.metric_value} / ${goal.metric_target}`), node("span", "muted", goal.metric_label), sparkline(goal.updates));
        card.append(metric);
    }
    const history = node("div", "goal-history");
    goal.updates.slice().reverse().forEach((update) => {
        const item = node("article", "goal-update");
        item.append(
            node("time", "muted", formatDate(update.updated_at)),
            node("p", "", update.comment),
        );
        history.append(item);
    });
    card.append(history);
    return card;
}

function renderDirection(route) {
    const slug = route.path.split("/")[2];
    const direction = directionBySlug(slug);
    if (!direction) {
        navigate(ROUTES.overview);
        return;
    }
    $("directionTitle").textContent = direction.title;
    $("directionHours").textContent = `Получено ${formatMinutes(direction.actual_minutes)} из ${formatMinutes(direction.planned_minutes)}`;
    const delta = direction.comparison.actual_minutes_delta;
    $("directionComparison").textContent = `К прошлому месяцу: ${delta >= 0 ? "+" : ""}${formatMinutes(delta)}`;
    const selectedDate = route.params.get("date");
    const directionSource = route.params.get("from") === "calendar" ? "calendar" : "overview";
    $("backButton").textContent = directionSource === "calendar" ? "← Вернуться к календарю" : "← Вернуться к обзору";
    $("backButton").onclick = () => navigate(`#/${directionSource}?month=${state.month}`);
    const visits = selectedDate ? direction.visits.filter((visit) => visit.date === selectedDate) : direction.visits;
    $("directionVisits").replaceChildren(
        ...(visits.length ? visits.map((visit) => visitCard(visit, direction)) : [empty("Занятий в этом месяце нет.")])
    );
    $("goalList").replaceChildren(
        ...(direction.goals.length ? direction.goals.map(goalCard) : [empty("Цели пока не добавлены.")])
    );
}

function adminSelectOptions(select, directions) {
    select.replaceChildren(...directions.map((direction) => {
        const option = document.createElement("option");
        option.value = direction.id;
        option.textContent = direction.title;
        return option;
    }));
}

function adminRow(title, archivedAt) {
    const row = node("article", archivedAt ? "admin-row archived" : "admin-row");
    row.append(node("strong", "", title), node("span", "muted", archivedAt ? "В архиве" : "Активно"));
    return row;
}

function renderChildrenAdmin() {
    const rows = state.admin.children.map((child) => {
        const row = adminRow(child.display_name, child.archived_at);
        const name = input("display_name", child.display_name);
        const age = input("age_label", child.age_label);
        const focus = input("focus", child.focus);
        row.append(name, age, focus);
        row.append(button("Сохранить", "", async () => {
            await mutate(`/api/admin/children/${child.id}`, "PUT", {
                display_name: name.value,
                age_label: age.value,
                focus: focus.value,
            });
            await reloadAll();
        }));
        row.append(button(child.archived_at ? "Вернуть" : "Архивировать", "", async () => {
            await mutate(`/api/admin/children/${child.id}/${child.archived_at ? "restore" : "archive"}`, "POST", {});
            await reloadAll();
        }));
        return row;
    });
    $("childrenAdminList").replaceChildren(...(rows.length ? rows : [empty("Детей пока нет.")]));
}

function renderDirectionsAdmin() {
    const rows = state.admin.directions.map((direction) => {
        const row = adminRow(direction.title, direction.archived_at);
        const title = input("title", direction.title);
        const slug = input("slug", direction.slug);
        const color = input("color", direction.color);
        const sort = input("sort_order", direction.sort_order, "number");
        row.append(title, slug, color, sort);
        row.append(button("Сохранить", "", async () => {
            await mutate(`/api/admin/directions/${direction.id}`, "PUT", {
                title: title.value,
                slug: slug.value,
                color: color.value,
                sort_order: sort.value,
            });
            await reloadAll();
        }));
        row.append(button(direction.archived_at ? "Вернуть" : "Архивировать", "", async () => {
            await mutate(`/api/admin/directions/${direction.id}/${direction.archived_at ? "restore" : "archive"}`, "POST", {});
            await reloadAll();
        }));
        return row;
    });
    $("directionsAdminList").replaceChildren(...(rows.length ? rows : [empty("Направлений пока нет.")]));
}

function renderChildDirectionsAdmin() {
    const assigned = state.admin.childDirections.filter((item) => !item.archived_at);
    const assignedIds = new Set(assigned.map((item) => item.direction_id));
    const available = state.admin.directions.filter((direction) => !direction.archived_at && !assignedIds.has(direction.id));
    adminSelectOptions($("assignDirectionForm").elements.direction_id, available);
    adminSelectOptions($("goalForm").elements.direction_id, activeAssignedDirections());
    adminSelectOptions($("visitForm").elements.direction_id, activeAssignedDirections());
    const rows = assigned.map((assignment) => {
        const direction = directionById(assignment.direction_id);
        const row = adminRow(direction?.title || assignment.direction_id, assignment.archived_at);
        row.append(button("Убрать", "", async () => {
            await mutate(`/api/admin/children/${state.childId}/directions/${assignment.direction_id}`, "DELETE");
            await reloadAll();
        }));
        return row;
    });
    $("childDirectionsAdminList").replaceChildren(...(rows.length ? rows : [empty("Направления ребёнку пока не подключены.")]));
}

function renderGoalsAdmin() {
    const rows = state.admin.goals.filter((goal) => !goal.archived_at).map((goal) => {
        const row = adminRow(goal.title, goal.archived_at);
        const title = input("title", goal.title);
        const description = input("description", goal.description);
        const status = document.createElement("select");
        ["active", "progress", "achieved", "paused"].forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = STATUS_LABELS[value];
            status.append(option);
        });
        status.value = goal.status;
        row.append(node("span", "muted", directionById(goal.direction_id)?.title || goal.direction_id), title, description, status);
        row.append(button("Сохранить", "", async () => {
            await mutate(`/api/admin/children/${state.childId}/goals/${goal.id}`, "PUT", {
                direction_id: goal.direction_id,
                title: title.value,
                description: description.value,
                status: status.value,
                metric_label: goal.metric_label,
                metric_target: goal.metric_target,
                sort_order: goal.sort_order,
            });
            await reloadAll();
        }));
        row.append(button("Архивировать", "", async () => {
            await mutate(`/api/admin/children/${state.childId}/goals/${goal.id}`, "DELETE");
            await reloadAll();
        }));
        return row;
    });
    $("goalsAdminList").replaceChildren(...(rows.length ? rows : [empty("Цели пока не добавлены.")]));
}

function renderVisitsAdmin() {
    const rows = state.admin.visits.filter((visit) => !visit.archived_at).map((visit) => {
        const row = adminRow(directionById(visit.direction_id)?.title || visit.direction_id, visit.archived_at);
        const start = input("scheduled_start", toLocalInput(visit.scheduled_start), "datetime-local");
        const end = input("scheduled_end", toLocalInput(visit.scheduled_end), "datetime-local");
        const status = document.createElement("select");
        ["scheduled", "completed", "partial", "cancelled", "absent", "rescheduled"].forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = STATUS_LABELS[value];
            status.append(option);
        });
        status.value = visit.status;
        row.append(start, end, status);
        row.append(button("Сохранить", "", async () => {
            await mutate(`/api/admin/children/${state.childId}/visits/${visit.id}`, "PUT", {
                direction_id: visit.direction_id,
                scheduled_start: toSchoolIso(start.value),
                scheduled_end: toSchoolIso(end.value),
                status: status.value,
                actual_start: visit.actual_start,
                actual_end: visit.actual_end,
                reason_code: visit.reason_code,
            });
            await reloadAll();
        }));
        row.append(button("Архивировать", "", async () => {
            await mutate(`/api/admin/children/${state.childId}/visits/${visit.id}`, "DELETE");
            await reloadAll();
        }));
        return row;
    });
    $("visitsAdminList").replaceChildren(...(rows.length ? rows : [empty("Занятия пока не добавлены.")]));
}

function renderAdmin() {
    renderChildrenAdmin();
    renderDirectionsAdmin();
    renderChildDirectionsAdmin();
    renderGoalsAdmin();
    renderVisitsAdmin();
}

function render() {
    const route = currentRoute();
    const isAdmin = route.path === "/admin";
    const isCalendar = route.path === "/calendar";
    const isDirection = route.path.startsWith("/direction/");
    const directionSource = isDirection && route.params.get("from") === "calendar" ? "calendar" : "overview";
    const isCalendarContext = isCalendar || (isDirection && directionSource === "calendar");

    $("overviewTab").href = `#/overview?month=${state.month}`;
    $("calendarTab").href = `#/calendar?month=${state.month}`;
    $("adminTab").href = "#/admin";
    $("profileCard").hidden = isAdmin || !state.snapshot;
    $("overviewView").hidden = isAdmin || isCalendar || isDirection || !state.snapshot;
    $("calendarView").hidden = !isCalendar || isAdmin || !state.snapshot;
    $("directionView").hidden = !isDirection || isAdmin || !state.snapshot;
    $("adminView").hidden = !isAdmin;
    $("profileCard").style.display = $("profileCard").hidden ? "none" : "";
    $("overviewView").style.display = $("overviewView").hidden ? "none" : "";
    $("calendarView").style.display = $("calendarView").hidden ? "none" : "";
    $("directionView").style.display = $("directionView").hidden ? "none" : "";
    $("adminView").style.display = $("adminView").hidden ? "none" : "";
    $("overviewTab").classList.toggle("active", !isAdmin && !isCalendarContext);
    $("calendarTab").classList.toggle("active", !isAdmin && isCalendarContext);
    $("adminTab").classList.toggle("active", isAdmin);

    if (state.snapshot && !isAdmin) renderProfile();
    if (isAdmin) renderAdmin();
    else if (isCalendar && state.snapshot) renderCalendar();
    else if (isDirection && state.snapshot) renderDirection(route);
    else if (state.snapshot) renderOverview();
}

async function reloadAll() {
    await loadAdmin();
    await loadJournal();
}

$("monthSelect").addEventListener("change", (event) => {
    const selectedMonth = event.target.value;
    const route = currentRoute();
    route.params.set("month", selectedMonth);
    route.params.delete("date");
    navigate(`#${route.path}?${route.params}`);
});

$("journalChildSelect").addEventListener("change", async (event) => {
    state.childId = event.target.value;
    $("adminChildSelect").value = state.childId;
    await loadAdminChildData();
    await loadJournal();
});

$("adminChildSelect").addEventListener("change", async (event) => {
    state.childId = event.target.value;
    $("journalChildSelect").value = state.childId;
    await loadAdminChildData();
    await loadJournal();
});

$("childForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const child = await mutate("/api/admin/children", "POST", formData(event.currentTarget));
    state.childId = child.id;
    event.currentTarget.reset();
    await reloadAll();
});

$("directionForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await mutate("/api/admin/directions", "POST", formData(event.currentTarget));
    event.currentTarget.reset();
    event.currentTarget.elements.sort_order.value = "10";
    await reloadAll();
});

$("assignDirectionForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await mutate(`/api/admin/children/${state.childId}/directions`, "POST", formData(event.currentTarget));
    await reloadAll();
});

$("goalForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await mutate(`/api/admin/children/${state.childId}/goals`, "POST", formData(event.currentTarget));
    event.currentTarget.reset();
    await reloadAll();
});

$("visitForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.currentTarget);
    data.scheduled_start = toSchoolIso(data.scheduled_start);
    data.scheduled_end = toSchoolIso(data.scheduled_end);
    await mutate(`/api/admin/children/${state.childId}/visits`, "POST", data);
    event.currentTarget.reset();
    await reloadAll();
});

window.addEventListener("hashchange", () => {
    const routeMonth = currentRoute().params.get("month");
    if (routeMonth && routeMonth !== state.month) {
        state.month = routeMonth;
        $("monthSelect").value = state.month;
        loadJournal();
    } else {
        render();
    }
});

const initialMonth = currentRoute().params.get("month");
if (initialMonth) {
    state.month = initialMonth;
    $("monthSelect").value = initialMonth;
}
if (!window.location.hash) window.location.hash = `${ROUTES.overview}?month=${state.month}`;

loadAdmin()
    .then(loadJournal)
    .catch((error) => {
        $("errorBox").textContent = error.message;
        $("errorBox").hidden = false;
    });
