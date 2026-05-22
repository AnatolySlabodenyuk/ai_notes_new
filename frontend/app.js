const state = {
  data: null,
  childId: null,
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

function selectedChild() {
  return state.data.children.find((child) => child.id === state.childId);
}

function renderChildren() {
  const select = $("childSelect");
  select.replaceChildren();
  state.data.children.forEach((child) => {
    const option = document.createElement("option");
    option.value = child.id;
    option.textContent = child.display_name;
    select.appendChild(option);
  });
  if (!state.childId) state.childId = state.data.children[0]?.id;
  select.value = state.childId;
  renderChild();
}

function renderChild() {
  const child = selectedChild();
  if (!child) return;
  const profile = $("childProfile");
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
  profile.replaceChildren(name, document.createElement("br"), age, document.createElement("br"), focus, goals);

  const history = $("historyList");
  history.replaceChildren(
    ...(child.sessions || [])
      .slice()
      .reverse()
      .map((session) => {
        const article = document.createElement("article");
        const time = document.createElement("time");
        const text = document.createElement("div");
        article.className = "history-item";
        time.textContent = session.created_at || "";
        text.textContent = session.history_update || session.internal_note || "";
        article.append(time, text);
        return article;
      })
  );
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

async function processAudio() {
  if (!state.audioFile) {
    showStatus("Выберите аудиофайл занятия.", true);
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
      body: JSON.stringify({ child_id: state.childId, audio_base64 }),
    });
    $("transcript").value = transcription.transcript;
    setPipeline("generate", ["audio", "asr"]);
    showStatus("Готовим внутреннюю заметку, сообщение родителю и обновление истории...");
    const result = await api("/api/generate", {
      method: "POST",
      body: JSON.stringify({ child_id: state.childId, transcript: transcription.transcript }),
    });
    $("internalNote").value = result.drafts.internal_note;
    $("parentMessage").value = result.drafts.parent_message;
    $("historyUpdate").value = result.drafts.history_update;
    state.drafts = result.drafts;
    setPipeline(null, ["audio", "asr", "generate"]);
    showStatus("Черновики готовы. Проверьте и подтвердите перед сохранением.");
  } catch (error) {
    showStatus(error.message, true);
    setPipeline(null, []);
  }
}

async function saveSession() {
  try {
    setPipeline("save", ["audio", "asr", "generate"]);
    showStatus("Сохраняем подтверждённую заметку в обезличенную историю...");
    const result = await api("/api/save-session", {
      method: "POST",
      body: JSON.stringify({
        child_id: state.childId,
        transcript: $("transcript").value,
        internal_note: $("internalNote").value,
        parent_message: $("parentMessage").value,
        history_update: $("historyUpdate").value,
      }),
    });
    state.data = result.data;
    renderChildren();
    setPipeline(null, ["audio", "asr", "generate", "save"]);
    showStatus("Сохранено. История ребёнка обновлена.");
  } catch (error) {
    showStatus(error.message, true);
  }
}

async function askHistory() {
  try {
    $("answerBox").textContent = "Готовим ответ по истории...";
    const result = await api("/api/ask-history", {
      method: "POST",
      body: JSON.stringify({ child_id: state.childId, question: $("questionInput").value }),
    });
    $("answerBox").textContent = result.answer || "История не содержит достаточно данных для ответа.";
  } catch (error) {
    $("answerBox").textContent = error.message;
  }
}

$("childSelect").addEventListener("change", (event) => {
  state.childId = event.target.value;
  renderChild();
});

$("audioInput").addEventListener("change", (event) => {
  state.audioFile = event.target.files[0] || null;
  $("audioName").textContent = state.audioFile ? state.audioFile.name : "Файл не выбран";
});

$("processBtn").addEventListener("click", processAudio);
$("saveBtn").addEventListener("click", saveSession);
$("askBtn").addEventListener("click", askHistory);
$("resetBtn").addEventListener("click", async () => {
  state.data = await api("/api/reset", { method: "POST", body: "{}" });
  renderChildren();
  showStatus("Демо-история сброшена.");
});

loadInitialData().catch((error) => showStatus(error.message, true));
