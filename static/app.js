const sampleIdInput = document.getElementById("sample_id");
const genomeFileInput = document.getElementById("genome_file");
const imageFileInput = document.getElementById("image_file");
const btnEnviar = document.getElementById("btnEnviar");
const mensaje = document.getElementById("mensaje");
const genomePreview = document.getElementById("genome_preview");
const imagePreview = document.getElementById("image_preview");

// 🌍 Detectar si estamos en local o en producción (Render)
const API_URL = window.location.hostname.includes("localhost") || window.location.hostname.includes("127.0.0.1")
  ? "http://127.0.0.1:8000"
  : "https://taxonomiaia.onrender.com";

// 🧬 Previsualización de genoma
genomeFileInput.addEventListener("change", () => {
  const file = genomeFileInput.files[0];
  if (!file) return;
  genomePreview.textContent = `Archivo seleccionado: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
});

// 🧫 Previsualización de imagen
imageFileInput.addEventListener("change", () => {
  const file = imageFileInput.files[0];
  if (!file) {
    imagePreview.innerHTML = "";
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    imagePreview.innerHTML = `<img src="${e.target.result}" alt="Previsualización de la colonia">`;
  };
  reader.readAsDataURL(file);
});

btnEnviar.addEventListener("click", async () => {
  const qrCode = sampleIdInput.value.trim();
  const genomeFile = genomeFileInput.files[0];
  const imageFile = imageFileInput.files[0];

  if (!qrCode || !genomeFile) {
    mensaje.textContent = "❌ Debes ingresar un ID y un archivo de genoma.";
    mensaje.style.color = "red";
    return;
  }

  btnEnviar.disabled = true;
  mensaje.innerHTML = `<span class="spinner"></span> Enviando muestra...`;
  mensaje.style.color = "black";

  try {
    // 🧩 Crear muestra
    const createResponse = await fetch(`${API_URL}/api/samples`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ qr_code: qrCode }),
    });

    const createData = await createResponse.json();
    if (!createResponse.ok) throw new Error(createData.detail || "Error al crear muestra.");

    const sampleId = createData.sample_id;

    // 📤 Subir archivos
    const formData = new FormData();
    formData.append("genome_file", genomeFile);
    if (imageFile) formData.append("image_file", imageFile);

    const uploadResponse = await fetch(`${API_URL}/api/samples/${sampleId}/upload`, {
      method: "POST",
      body: formData,
    });

    const uploadData = await uploadResponse.json();
    if (!uploadResponse.ok) throw new Error(uploadData.detail || "Error al subir archivos.");

    // ✅ Mostrar mensaje inicial
    mostrarMensaje(`✅ ${uploadData.message}<br>🔬 Analizando muestra...`, "black");

    // ⏳ Iniciar polling del resultado
    const intervalo = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/samples/${sampleId}/result`);
        const data = await res.json();
        console.log("📦 Datos recibidos del backend:", data);

        // ⏳ Si aún está procesando
        if (data.status === "processing") {
          mostrarMensaje(`⏳ ${data.message || "Análisis en progreso..."}`, "gray");
          return;
        }

        // ✅ Si ya hay resultado
        if (data.classification) {
          clearInterval(intervalo);

          mostrarMensaje(
            `✅ Análisis completado.<br><br>
             <strong>Confianza:</strong> ${data.confidence || "—"}<br>
             <strong>Evidencia:</strong> ${data.evidence || "—"}<br><br>
             <a href="results.html?id=${sampleId}" class="btn-ver">🔍 Ver resultado completo</a>`,
            "green"
          );
        }
      } catch (err) {
        console.error("Error al consultar resultado:", err);
      }
    }, 5000); // cada 5 segundos
  } catch (err) {
    console.error(err);
    mostrarMensaje("❌ No se pudo conectar con el backend.", "red");
  } finally {
    btnEnviar.disabled = false;
  }
});

// 🔔 Función auxiliar para mostrar mensajes
function mostrarMensaje(texto, color) {
  mensaje.innerHTML = texto;
  mensaje.style.color = color;
}
