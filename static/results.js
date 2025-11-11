const container = document.getElementById("results-container");
const btnBuscar = document.getElementById("btnBuscar");
const inputBuscar = document.getElementById("searchId");

// 🌐 Detecta si estamos en local o en producción
const API_URL = window.location.hostname.includes("localhost") || window.location.hostname.includes("127.0.0.1")
  ? "http://127.0.0.1:8000"
  : "https://taxonomiaia.onrender.com/"; // 👈 cambia esto por tu URL real de Render

// 🔄 Loader visual
function mostrarLoader() {
  container.innerHTML = `
    <div class="loading">
      <div class="spinner"></div>
      <p>📡 Cargando resultados...</p>
    </div>
  `;
}

// ⚙️ Carga resultados (por ID o todos)
async function cargarResultados(id = "") {
  mostrarLoader();

  try {
    const url = id
      ? `${API_URL}/api/samples/${id}/result`
      : `${API_URL}/api/samples`;

    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data?.detail || "Error en la solicitud");
    }

    container.innerHTML = "";

    // 🔍 Búsqueda por ID específico
    if (id) {
      if (!data || Object.keys(data).length === 0) {
        container.innerHTML = `<p>⚠️ No se encontró ninguna muestra con el ID <b>${id}</b>.</p>`;
        return;
      }

      mostrarResultado({
        sample_id: id,
        result: data.result || data,
      });
      return;
    }

    // 📋 Mostrar todas las muestras
    if (!data.samples || data.samples.length === 0) {
      container.innerHTML = `<p>⚠️ No hay muestras registradas aún.</p>`;
      return;
    }

    // Animación de entrada escalonada
    data.samples.forEach((r, i) =>
      setTimeout(() => mostrarResultado(r), i * 80)
    );

  } catch (err) {
    console.error("Error:", err);
    container.innerHTML = `
      <div class="error-message">
        <p>❌ Error al conectar con el servidor o procesar la respuesta.</p>
        <small>${err.message}</small>
      </div>
    `;
  }
}

// 🎨 Renderiza cada tarjeta de resultado (con Markdown)
function mostrarResultado(r) {
  const card = document.createElement("div");
  card.className = "result-card fade-in";

  const result = r.result || {};

  // ✅ Convertir Markdown → HTML limpio
  const classificationMarkdown = result.classification || "(Sin resultados aún)";
  const classificationHTML = marked.parse(classificationMarkdown);

  const confidence = result.confidence ?? "—";
  const evidence = result.evidence ?? "—";

  card.innerHTML = `
    <div class="result-header">
      🧬 <strong>Muestra:</strong> ${r.sample_id}
    </div>

    <div class="result-body">
      <h3>🔬 Clasificación</h3>
      <div class="classification markdown">${classificationHTML}</div>

      <hr>
      <p><strong>Confianza:</strong> ${confidence}</p>
      <p><strong>Evidencia:</strong> ${evidence}</p>
    </div>
  `;

  container.appendChild(card);
}

// 🔍 Buscar por ID
btnBuscar.addEventListener("click", () => {
  const id = inputBuscar.value.trim();
  cargarResultados(id);
});

// ⌨️ Enter para buscar
inputBuscar.addEventListener("keypress", (e) => {
  if (e.key === "Enter") btnBuscar.click();
});

// 🚀 Cargar al inicio
cargarResultados();
