// Animación de ADN 3D
const dnaBackground = document.getElementById('dna-background');
const nucleotides = [];
const numPoints = 100;  // Número de puntos en la hélice

for (let i = 0; i < numPoints; i++) {
    const dot = document.createElement('div');
    dot.classList.add('nucleotide');
    dnaBackground.appendChild(dot);
    nucleotides.push(dot);
}

let angle = 0;

function animateDNA() {
    const radius = 120; // radio de la hélice
    const height = 600; // altura total
    const speed = 0.02;

    nucleotides.forEach((dot, i) => {
        const t = i / numPoints;
        const y = (t - 0.5) * height;
        const x = radius * Math.cos(4 * Math.PI * t + angle);
        const z = radius * Math.sin(4 * Math.PI * t + angle);

        dot.style.transform = `translate3d(${x}px, ${y}px, ${z}px)`;
        const hue = 200 + 50 * Math.sin(4 * Math.PI * t + angle);
        dot.style.background = `hsl(${hue}, 80%, 50%)`;
    });

    angle += speed;
    requestAnimationFrame(animateDNA);
}

animateDNA();
