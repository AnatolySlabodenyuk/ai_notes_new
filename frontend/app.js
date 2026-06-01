const state = {
    data: null,
    childId: null,
    parentChildId: null,
    mode: "admin",
    audioFile: null,
    drafts: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    });
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload?.error?.message || "Request failed");
    }
    return payload;
}

function setPipeline(active, done = []) {
    document.querySelectorAll(".step").forEach((step) => {
        const name = step.dataset.step;
        step.classList.toggle("active", name === active);
        step.classList.toggle("done", done.includes(name));
    });
}

function showStatus(message, isError = false) {
    const box = $("statusBox");
    box.hidden = false;
    box.textContent = message;
    box.classList.toggle("error", isError);
}

function children() {
    return state.data?.children || [];
}

function selectedChild() {
    return children().find((child) => child.id === state.childId);
}

function parentChild() {
    return children().find((child) => child.id === state.parentChildId) || children()[0];
}

function appendChildProfile(target, child) {
    const name = document.createElement("strong");
    const age = document.createElement("span");
    const focus = document.createElement("span");
    const goals = document.createElement("ul");

    name.textContent = child.display_name;
    age.textContent = child.age_label || "";
    focus.textContent = child.focus || "";
    goals.className = "goal";
    (child.goals || []).forEach((goal) => {
        const item = document.createElement("li");
        item.textContent = goal;
        goals.appendChild(item);
    });
    target.replaceChildren(name, document.createElement("br"), age, document.createElement("br"), focus, goals);
}

function createSessionCard(session) {
    const article = document.createElement("article");
    const time = document.createElement("time");
    article.className = "history-item session-card";
    time.textContent = session.published_at || session.created_at || "";
    article.append(time);

    [
        ["Что делали", session.what_we_did],
        ["Что получилось", session.what_changed],
        ["Что попробовать дома", session.home_practice],
    ].forEach(([label, value]) => {
        const block = document.createElement("div");
        const title = document.createElement("strong");
        const text = document.createElement("p");
        block.className = "session-block";
        title.textContent = label;
        text.textContent = value || "Пока нет данных.";
        block.append(title, text);
        article.append(block);
    });

    return article;
}

function renderAdminMode() {
    $("adminModeBtn").classList.add("active");
    $("parentModeBtn").classList.remove("active");
    $("adminRail").hidden = false;
    $("adminFlow").hidden = false;
    $("draftPanel").hidden = false;
    $("parentCabinet").hidden = true;
}

function renderParentMode() {
    const child = parentChild();
    $("adminModeBtn").classList.remove("active");
    $("parentModeBtn").classList.add("active");
    $("adminRail").hidden = true;
    $("adminFlow").hidden = true;
    $("draftPanel").hidden = true;
    $("parentCabinet").hidden = false;

    if (!child) return;
    $("parentLabel").textContent = child.parent_label || "Родитель";
    appendChildProfile($("parentProfile"), child);
    renderParentFeed();
}

function renderMode() {
    if (state.mode === "parent") {
        renderParentMode();
    } else {
        renderAdminMode();
    }
}

function renderChildren() {
    const select = $("childSelect");
    select.replaceChildren();
    children().forEach((child) => {
        const option = document.createElement("option");
        option.value = child.id;
        option.textContent = child.display_name;
        select.appendChild(option);
    });
    if (!state.childId) state.childId = children()[0]?.id;
    if (!state.parentChildId) state.parentChildId = children()[0]?.id;
    if (!children().some((child) => child.id === state.childId)) {
        state.childId = children()[0]?.id;
    }
    if (!children().some((child) => child.id === state.parentChildId)) {
        state.parentChildId = children()[0]?.id;
    }
    select.value = state.childId;
    renderChild();
    renderParentFeed();
    renderMode();
}

function renderChild() {
    const child = selectedChild();
    const profile = $("childProfile");
    const history = $("historyList");
    if (!child) {
        profile.replaceChildren();
        history.replaceChildren();
        return;
    }
    appendChildProfile($("childProfile"), child);

    const sessions = (child.sessions || []).slice().reverse();
    if (!sessions.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Опубликованных записей пока нет.";
        history.replaceChildren(empty);
        return;
    }
    history.replaceChildren(...sessions.map(createSessionCard));
}

function renderParentFeed() {
    const child = parentChild();
    const feed = $("parentFeed");
    if (!child || !feed) return;
    const sessions = (child.sessions || []).slice().reverse();
    if (!sessions.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "В карточке пока нет опубликованных занятий.";
        feed.replaceChildren(empty);
        return;
    }
    feed.replaceChildren(...sessions.map(createSessionCard));
}

function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

async function loadInitialData() {
    state.data = await api("/api/children");
    renderChildren();
    try {
        const health = await api("/api/health");
        $("health").textContent = `Ollama: ${health.model} · local`;
    } catch {
        $("health").textContent = "Локальный backend активен";
    }
}

function applyDrafts(drafts) {
    $("whatWeDid").value = drafts.what_we_did || "";
    $("whatChanged").value = drafts.what_changed || "";
    $("homePractice").value = drafts.home_practice || "";
    state.drafts = drafts;
}

async function generateFromTranscript() {
    const transcript = $("transcript").value.trim();
    if (!transcript) {
        showStatus("Вставьте транскрипт или обработайте аудио.", true);
        return;
    }
    try {
        setPipeline("generate", ["audio", "asr"]);
        showStatus("Готовим три родительских блока...");
        const result = await api("/api/generate", {
            method: "POST",
            body: JSON.stringify({child_id: state.childId, transcript}),
        });
        applyDrafts(result.drafts);
        setPipeline(null, ["audio", "asr", "generate"]);
        showStatus("Черновик готов. Проверьте текст перед публикацией.");
    } catch (error) {
        showStatus(error.message, true);
        setPipeline(null, []);
    }
}

async function processAudio() {
    if (!state.audioFile) {
        showStatus("Выберите аудиофайл или вставьте транскрипт вручную.", true);
        return;
    }
    try {
        setPipeline("audio", []);
        showStatus("Читаем аудиофайл...");
        const audio_base64 = await fileToDataUrl(state.audioFile);
        setPipeline("asr", ["audio"]);
        showStatus("Распознаём речь локальной ASR-моделью...");
        const transcription = await api("/api/transcribe", {
            method: "POST",
            body: JSON.stringify({child_id: state.childId, audio_base64}),
        });
        $("transcript").value = transcription.transcript;
        await generateFromTranscript();
    } catch (error) {
        showStatus(`${error.message} Можно вставить транскрипт вручную.`, true);
        setPipeline(null, []);
    }
}

async function saveSession() {
    try {
        setPipeline("save", ["audio", "asr", "generate"]);
        showStatus("Публикуем запись в карточку ребёнка...");
        const result = await api("/api/save-session", {
            method: "POST",
            body: JSON.stringify({
                child_id: state.childId,
                transcript: $("transcript").value,
                what_we_did: $("whatWeDid").value,
                what_changed: $("whatChanged").value,
                home_practice: $("homePractice").value,
            }),
        });
        state.data = result.data;
        state.parentChildId = state.childId;
        renderChildren();
        setPipeline(null, ["audio", "asr", "generate", "save"]);
        showStatus("Опубликовано. Запись появилась в родительской карточке.");
    } catch (error) {
        showStatus(error.message, true);
    }
}

async function addChild() {
    const addChildDisclosure = $("addChildDisclosure");
    const display_name = $("childNameInput").value.trim();
    if (!display_name) {
        addChildDisclosure.open = true;
        showStatus("Введите имя или обезличенную метку ребёнка.", true);
        $("childNameInput").focus();
        return;
    }
    const goals = $("childGoalsInput").value
        .split("\n")
        .map((goal) => goal.trim())
        .filter(Boolean);
    try {
        showStatus("Добавляем ребёнка в локальную базу...");
        const result = await api("/api/children", {
            method: "POST",
            body: JSON.stringify({
                display_name,
                age_label: $("childAgeInput").value,
                focus: $("childFocusInput").value,
                goals,
            }),
        });
        state.data = result.data;
        state.childId = result.child.id;
        state.parentChildId = result.child.id;
        $("childNameInput").value = "";
        $("childAgeInput").value = "";
        $("childFocusInput").value = "";
        $("childGoalsInput").value = "";
        renderChildren();
        addChildDisclosure.open = false;
        showStatus("Ребёнок добавлен.");
    } catch (error) {
        showStatus(error.message, true);
    }
}

async function resetCurrentChildHistory() {
    if (!state.childId) {
        showStatus("Сначала выберите ребёнка.", true);
        return;
    }
    try {
        const childId = state.childId;
        state.data = await api("/api/reset-child", {
            method: "POST",
            body: JSON.stringify({child_id: childId}),
        });
        state.childId = childId;
        state.parentChildId = childId;
        renderChildren();
        showStatus("История выбранного ребёнка очищена.");
    } catch (error) {
        showStatus(error.message, true);
    }
}

$("adminModeBtn").addEventListener("click", () => {
    state.mode = "admin";
    renderMode();
});

$("parentModeBtn").addEventListener("click", () => {
    state.mode = "parent";
    renderMode();
});

$("childSelect").addEventListener("change", (event) => {
    state.childId = event.target.value;
    renderChild();
});

$("audioInput").addEventListener("change", (event) => {
    state.audioFile = event.target.files[0] || null;
    $("audioName").textContent = state.audioFile ? state.audioFile.name : "Файл не выбран";
});

$("processBtn").addEventListener("click", processAudio);
$("generateBtn").addEventListener("click", generateFromTranscript);
$("saveBtn").addEventListener("click", saveSession);
$("addChildBtn").addEventListener("click", addChild);
$("resetBtn").addEventListener("click", resetCurrentChildHistory);

loadInitialData().catch((error) => showStatus(error.message, true));
