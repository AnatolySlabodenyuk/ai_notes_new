const state = {month: "2026-06", snapshot: null};
const $ = (id) => document.getElementById(id);
const ROUTES = {overview: "#/overview", calendar: "#/calendar", direction: "#/direction/"};

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

async function api(path) {
    const response = await fetch(path);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.error?.message || "Не удалось загрузить журнал.");
    return payload;
}

async function loadJournal() {
    $("errorBox").hidden = true;
    try {
        state.snapshot = await api(`/api/journal?month=${encodeURIComponent(state.month)}`);
        render();
    } catch (error) {
        $("errorBox").textContent = error.message;
        $("errorBox").hidden = false;
    }
}

function currentRoute() {
    const hash = window.location.hash || ROUTES.overview;
    const [path, query = ""] = hash.slice(1).split("?");
    return {path, params: new URLSearchParams(query)};
}

function navigate(hash) {
    window.location.hash = hash;
}

function directionBySlug(slug) {
    return state.snapshot?.directions.find((direction) => direction.slug === slug);
}

function badge(status) {
    return node("span", `badge status-${status}`, STATUS_LABELS[status] || status);
}

function visitCard(visit, direction) {
    const card = node("article", "visit-card");
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
    const child = state.snapshot.child;
    $("childName").textContent = child.display_name;
    $("childMeta").textContent = `${child.age_label} · ${child.focus}`;
}

function summaryCard(label, value, detail) {
    const card = node("article", "summary-card panel");
    card.append(node("span", "eyebrow", label), node("strong", "summary-value", value), node("small", "muted", detail));
    return card;
}

function renderOverview() {
    const overview = state.snapshot.overview;
    const delta = overview.comparison.actual_minutes_delta;
    $("summaryGrid").replaceChildren(
        summaryCard("План на месяц", formatMinutes(overview.planned_minutes), "По всем направлениям"),
        summaryCard("Получено", formatMinutes(overview.actual_minutes), "Фактически посещённые занятия"),
        summaryCard("Динамика", `${delta >= 0 ? "+" : ""}${formatMinutes(delta)}`, "К прошлому месяцу"),
        summaryCard("Направления", String(state.snapshot.directions.length), "Активный маршрут ребёнка"),
    );

    const attention = overview.attention_items.map((visit) => {
        const direction = state.snapshot.directions.find((item) => item.id === visit.direction_id);
        return visitCard(visit, direction);
    });
    $("attentionList").replaceChildren(...(attention.length ? attention : [empty("Отклонений за месяц нет.")]));

    const upcoming = overview.upcoming_visits.map((visit) => {
        const direction = state.snapshot.directions.find((item) => item.id === visit.direction_id);
        return visitCard(visit, direction);
    });
    $("upcomingList").replaceChildren(...(upcoming.length ? upcoming : [empty("Ближайших занятий пока нет.")]));

    const cards = state.snapshot.directions.map((direction) => {
        const card = node("button", "direction-card");
        card.type = "button";
        card.dataset.slug = direction.slug;
        card.style.borderTopColor = direction.color;
        card.append(
            node("span", "direction-title", direction.title),
            node("strong", "direction-hours", `${formatMinutes(direction.actual_minutes)} из ${formatMinutes(direction.planned_minutes)}`),
            node("span", "muted", `${formatGoalCount(direction.goals.length)} · открыть →`)
        );
        card.addEventListener("click", () => navigate(`#/direction/${direction.slug}?month=${state.month}`));
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
        block.append(node("h3", "", formatDate(`${day.date}T12:00:00+03:00`)));
        day.visits.forEach((visit) => {
            const direction = state.snapshot.directions.find((item) => item.id === visit.direction_id);
            const button = node("button", "calendar-visit");
            button.type = "button";
            button.style.borderLeftColor = direction.color;
            button.append(
                node("strong", "", direction.title),
                node("span", "muted", `${formatTime(visit.scheduled_start)}–${formatTime(visit.scheduled_end)}`),
                badge(visit.status)
            );
            button.addEventListener("click", () => navigate(`#/direction/${direction.slug}?month=${state.month}&date=${day.date}`));
            block.append(button);
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
    card.append(top, node("p", "", goal.description));
    if (goal.metric_label && goal.latest_update?.metric_value !== null && goal.latest_update?.metric_value !== undefined) {
        card.append(
            node("strong", "metric-value", `${goal.latest_update.metric_value} / ${goal.metric_target} · ${goal.metric_label}`),
            sparkline(goal.updates)
        );
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
    const visits = selectedDate ? direction.visits.filter((visit) => visit.date === selectedDate) : direction.visits;
    $("directionVisits").replaceChildren(
        ...(visits.length ? visits.map((visit) => visitCard(visit, direction)) : [empty("Занятий в этом месяце нет.")])
    );
    $("goalList").replaceChildren(
        ...(direction.goals.length ? direction.goals.map(goalCard) : [empty("Цели пока не добавлены.")])
    );
}

function render() {
    if (!state.snapshot) return;
    renderProfile();
    const route = currentRoute();
    $("overviewTab").href = `#/overview?month=${state.month}`;
    $("calendarTab").href = `#/calendar?month=${state.month}`;
    const isCalendar = route.path === "/calendar";
    const isDirection = route.path.startsWith("/direction/");
    $("overviewView").hidden = isCalendar || isDirection;
    $("calendarView").hidden = !isCalendar;
    $("directionView").hidden = !isDirection;
    $("overviewTab").classList.toggle("active", !isCalendar && !isDirection);
    $("calendarTab").classList.toggle("active", isCalendar);
    if (isCalendar) renderCalendar();
    else if (isDirection) renderDirection(route);
    else renderOverview();
}

$("monthSelect").addEventListener("change", (event) => {
    const selectedMonth = event.target.value;
    const route = currentRoute();
    navigate(`#${route.path}?month=${selectedMonth}`);
});
$("backButton").addEventListener("click", () => navigate(ROUTES.overview));
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
loadJournal();
