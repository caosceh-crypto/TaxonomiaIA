const container = document.getElementById("results-container");
const btnBuscar = document.getElementById("btnBuscar");
const inputBuscar = document.getElementById("searchId");
const chatBox = document.getElementById("chat-box");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");

let sampleIDActivo = null; // <<< ID seleccionado automáticamente

// Detectar backend
const API_URL =
  window.location.hostname.includes("localhost") ||
  window.location.hostname.includes("127.0.0.1")
    ? "http://127.0.0.1:8000"
    : "https://taxonomiaia.onrender.com";

// Loader principal
function mostrarLoader() {
  container.innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <p>📡 Cargando resultados...</p>
    </div>
  `;
}

// ==========================
// CARGA DE RESULTADOS
// ==========================
async function cargarResultados(id = "") {
  mostrarLoader();

  try {
    const url = id
      ? `${API_URL}/api/samples/${id}/result`
      : `${API_URL}/api/samples`;

    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok) throw new Error(data?.detail || "Error en la solicitud");

    container.innerHTML = "";

    if (id) {
      if (!data || Object.keys(data).length === 0) {
        container.innerHTML = `<p>⚠️ No se encontró la muestra <b>${id}</b>.</p>`;
        return;
      }

      sampleIDActivo = id; // <<< Activamos la muestra
      mostrarResultado({
        sample_id: id,
        result: data.result || data,
      });

      return;
    }

    if (!data.samples || data.samples.length === 0) {
      container.innerHTML = `<p>⚠️ No hay muestras registradas.</p>`;
      return;
    }

    // <<< Activamos primera muestra automáticamente
    sampleIDActivo = data.samples[0].sample_id;

    data.samples.forEach((r, i) =>
      setTimeout(() => mostrarResultado(r), i * 80)
    );

  } catch (err) {
    console.error("Error:", err);
    container.innerHTML = `
      <div class="error-message">
        <p>❌ Error al conectar con el servidor.</p>
        <small>${err.message}</small>
      </div>
    `;
  }
}

// Render de tarjetas
function mostrarResultado(r) {
  const card = document.createElement("div");
  card.className = "result-card fade-in";

  const res = r.result || {};

  const classificationMarkdown = res.classification || "(Sin resultados aún)";
  const classificationHTML = marked.parse(classificationMarkdown);

  card.innerHTML = `
    <div class="result-header">🧬 <strong>ID:</strong> ${r.sample_id}</div>
    <div class="result-body">
      <h3>🔬 Clasificación</h3>
      <div class="classification markdown">${classificationHTML}</div>
      <hr>
      <p><strong>Confianza:</strong> ${res.confidence ?? "—"}</p>
      <p><strong>Evidencia:</strong> ${res.evidence ?? "—"}</p>
    </div>
  `;

  container.appendChild(card);
}

// Buscar por ID
btnBuscar.addEventListener("click", () => {
  const id = inputBuscar.value.trim();
  if (id) sampleIDActivo = id;
  cargarResultados(id);
});

// Enter para buscar
inputBuscar.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    btnBuscar.click();
  }
});

// Cargar al inicio
cargarResultados();

/* ============================================================
   🤖 CHAT IA
   ============================================================ */

// Loader "escribiendo..."
function crearLoaderMensaje() {
  const loader = document.createElement("div");
  loader.className = "chat-message chat-ai fade-in";

  loader.innerHTML = `
      <div class="typing-indicator">
        <span></span><span></span><span></span>
      </div>
  `;

  chatBox.appendChild(loader);
  chatBox.scrollTop = chatBox.scrollHeight;
  return loader;
}

// Crear burbuja de mensaje
function agregarMensaje(texto, tipo = "user") {
  const div = document.createElement("div");
  const clase = tipo === "user" ? "chat-user" : "chat-ai";

  div.className = `chat-message ${clase} fade-in`;

  // 🔥 Convertir markdown a HTML
  div.innerHTML = marked.parse(texto);

  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// Enviar mensaje al backend IA
async function enviarMensajeIA(mensaje) {

  if (!sampleIDActivo) {
    agregarMensaje("⚠️ No hay ninguna muestra para analizar.", "ai");
    return;
  }

  const loader = crearLoaderMensaje();

  try {
    const form = new FormData();
    form.append("question", mensaje);

    const res = await fetch(`${API_URL}/api/chat/${sampleIDActivo}`, {
      method: "POST",
      body: form,
    });

    const data = await res.json();
    loader.remove();

    if (data.answer) {
      agregarMensaje(data.answer, "ai");
    } else {
      agregarMensaje("⚠️ La IA no generó respuesta.", "ai");
    }

  } catch (err) {
    loader.remove();
    agregarMensaje("❌ Error al conectar con la IA.", "ai");
  }
}

// Lógica de enviar
function enviar() {
  const texto = chatInput.value.trim();
  if (!texto) return;

  agregarMensaje(texto, "user");
  chatInput.value = "";

  enviarMensajeIA(texto);
}

chatSendBtn?.addEventListener("click", (e) => {
  e.preventDefault();
  enviar();
});

// <<< 🚫 Eliminar duplicados y evitar doble envío
chatInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault(); 
    enviar();
  }
});