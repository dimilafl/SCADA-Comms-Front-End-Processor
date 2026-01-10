// Canvas setup
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

// Set canvas size
function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
resizeCanvas();
window.addEventListener('resize', resizeCanvas);

// Particle class
class Particle {
    constructor(x, y, color, velocity, size) {
        this.x = x;
        this.y = y;
        this.color = color;
        this.velocity = velocity;
        this.size = size;
        this.life = 1.0; // 1.0 = fully alive, 0.0 = dead
        this.decay = Math.random() * 0.015 + 0.005; // Random decay rate
        this.gravity = 0.1;
        this.friction = 0.99;
    }

    update(settings) {
        // Apply gravity if enabled
        if (settings.gravity) {
            this.velocity.y += this.gravity;
        }

        // Apply friction
        this.velocity.x *= this.friction;
        this.velocity.y *= this.friction;

        // Update position
        this.x += this.velocity.x;
        this.y += this.velocity.y;

        // Bounce off walls if enabled
        if (settings.bounce) {
            if (this.x < 0 || this.x > canvas.width) {
                this.velocity.x *= -0.8;
                this.x = Math.max(0, Math.min(canvas.width, this.x));
            }
            if (this.y > canvas.height) {
                this.velocity.y *= -0.8;
                this.y = canvas.height;
            }
        }

        // Decay life
        this.life -= this.decay;
    }

    draw(settings) {
        ctx.save();

        // Apply glow effect if enabled
        if (settings.glow) {
            ctx.shadowBlur = 15;
            ctx.shadowColor = this.color;
        }

        ctx.globalAlpha = this.life;
        ctx.fillStyle = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size * this.life, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
    }

    isDead() {
        return this.life <= 0;
    }
}

// Trail particle for mouse trail
class TrailParticle {
    constructor(x, y, color, size) {
        this.x = x;
        this.y = y;
        this.color = color;
        this.size = size;
        this.life = 1.0;
        this.decay = 0.05;
    }

    update() {
        this.life -= this.decay;
    }

    draw(settings) {
        ctx.save();
        if (settings.glow) {
            ctx.shadowBlur = 10;
            ctx.shadowColor = this.color;
        }
        ctx.globalAlpha = this.life * 0.6;
        ctx.fillStyle = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }

    isDead() {
        return this.life <= 0;
    }
}

// Color palettes for different modes
const colorPalettes = {
    rainbow: ['#FF0080', '#FF8C00', '#FFD700', '#00FF00', '#00CED1', '#4169E1', '#9400D3'],
    fire: ['#FF4500', '#FF6347', '#FF7F50', '#FFA500', '#FFD700', '#FFFF00'],
    ice: ['#00FFFF', '#00CED1', '#4682B4', '#87CEEB', '#B0E0E6', '#E0FFFF'],
    galaxy: ['#FF1493', '#9400D3', '#4B0082', '#0000FF', '#00FFFF', '#FFFFFF'],
    electric: ['#00FFFF', '#00FF00', '#FFFF00', '#FFFFFF', '#00CED1'],
    neon: ['#FF00FF', '#00FFFF', '#FF00AA', '#00FF99', '#FFFF00', '#FF0099']
};

// State
const state = {
    particles: [],
    trailParticles: [],
    mouse: { x: 0, y: 0, prevX: 0, prevY: 0 },
    isMouseDown: false,
    mode: 'rainbow',
    settings: {
        particleCount: 100,
        explosionForce: 10,
        particleSize: 3,
        trailLength: 20,
        mouseTrail: true,
        gravity: true,
        bounce: false,
        glow: true
    },
    fps: 60,
    lastTime: performance.now(),
    frameCount: 0
};

// Create explosion at position
function createExplosion(x, y) {
    const colors = colorPalettes[state.mode];
    const particleCount = state.settings.particleCount;
    const force = state.settings.explosionForce;
    const size = state.settings.particleSize;

    for (let i = 0; i < particleCount; i++) {
        const angle = (Math.PI * 2 * i) / particleCount + Math.random() * 0.5;
        const speed = Math.random() * force + force * 0.5;
        const velocity = {
            x: Math.cos(angle) * speed,
            y: Math.sin(angle) * speed
        };
        const color = colors[Math.floor(Math.random() * colors.length)];
        const particleSize = size * (0.5 + Math.random() * 0.5);

        state.particles.push(new Particle(x, y, color, velocity, particleSize));
    }
}

// Create trail particle
function createTrailParticle(x, y) {
    if (!state.settings.mouseTrail) return;

    const colors = colorPalettes[state.mode];
    const color = colors[Math.floor(Math.random() * colors.length)];
    const size = state.settings.particleSize * 0.7;

    state.trailParticles.push(new TrailParticle(x, y, color, size));
}

// Animation loop
function animate() {
    requestAnimationFrame(animate);

    // Calculate FPS
    state.frameCount++;
    const currentTime = performance.now();
    if (currentTime >= state.lastTime + 1000) {
        state.fps = Math.round((state.frameCount * 1000) / (currentTime - state.lastTime));
        state.frameCount = 0;
        state.lastTime = currentTime;
        document.getElementById('fps').textContent = state.fps;
    }

    // Clear canvas with fade effect for trail
    ctx.fillStyle = 'rgba(10, 15, 25, 0.15)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Update and draw trail particles
    for (let i = state.trailParticles.length - 1; i >= 0; i--) {
        const particle = state.trailParticles[i];
        particle.update();
        particle.draw(state.settings);

        if (particle.isDead()) {
            state.trailParticles.splice(i, 1);
        }
    }

    // Update and draw particles
    for (let i = state.particles.length - 1; i >= 0; i--) {
        const particle = state.particles[i];
        particle.update(state.settings);
        particle.draw(state.settings);

        if (particle.isDead()) {
            state.particles.splice(i, 1);
        }
    }

    // Update particle count display
    document.getElementById('particleCount-stat').textContent = state.particles.length;

    // Create continuous explosions when mouse is dragged
    if (state.isMouseDown && state.frameCount % 3 === 0) {
        createExplosion(state.mouse.x, state.mouse.y);
    }

    // Create trail particles if mouse is moving
    if (state.settings.mouseTrail) {
        const dx = state.mouse.x - state.mouse.prevX;
        const dy = state.mouse.y - state.mouse.prevY;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 5) {
            createTrailParticle(state.mouse.x, state.mouse.y);
        }
    }

    state.mouse.prevX = state.mouse.x;
    state.mouse.prevY = state.mouse.y;
}

// Event listeners for mouse/touch
canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    createExplosion(x, y);
});

canvas.addEventListener('mousedown', (e) => {
    state.isMouseDown = true;
    const rect = canvas.getBoundingClientRect();
    state.mouse.x = e.clientX - rect.left;
    state.mouse.y = e.clientY - rect.top;
});

canvas.addEventListener('mouseup', () => {
    state.isMouseDown = false;
});

canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    state.mouse.x = e.clientX - rect.left;
    state.mouse.y = e.clientY - rect.top;
});

canvas.addEventListener('mouseleave', () => {
    state.isMouseDown = false;
});

// Touch events for mobile
canvas.addEventListener('touchstart', (e) => {
    e.preventDefault();
    state.isMouseDown = true;
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches[0];
    const x = touch.clientX - rect.left;
    const y = touch.clientY - rect.top;
    state.mouse.x = x;
    state.mouse.y = y;
    createExplosion(x, y);
});

canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches[0];
    state.mouse.x = touch.clientX - rect.left;
    state.mouse.y = touch.clientY - rect.top;
});

canvas.addEventListener('touchend', (e) => {
    e.preventDefault();
    state.isMouseDown = false;
});

// UI Controls
document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.mode = btn.dataset.mode;
    });
});

// Checkboxes
document.getElementById('mouseTrail').addEventListener('change', (e) => {
    state.settings.mouseTrail = e.target.checked;
});

document.getElementById('gravity').addEventListener('change', (e) => {
    state.settings.gravity = e.target.checked;
});

document.getElementById('bounce').addEventListener('change', (e) => {
    state.settings.bounce = e.target.checked;
});

document.getElementById('glow').addEventListener('change', (e) => {
    state.settings.glow = e.target.checked;
});

// Sliders
document.getElementById('particleCount').addEventListener('input', (e) => {
    state.settings.particleCount = parseInt(e.target.value);
    document.getElementById('particleCountValue').textContent = e.target.value;
});

document.getElementById('explosionForce').addEventListener('input', (e) => {
    state.settings.explosionForce = parseInt(e.target.value);
    document.getElementById('explosionForceValue').textContent = e.target.value;
});

document.getElementById('particleSize').addEventListener('input', (e) => {
    state.settings.particleSize = parseFloat(e.target.value);
    document.getElementById('particleSizeValue').textContent = e.target.value;
});

document.getElementById('trailLength').addEventListener('input', (e) => {
    state.settings.trailLength = parseInt(e.target.value);
    document.getElementById('trailLengthValue').textContent = e.target.value;
});

// Clear button
document.getElementById('clearBtn').addEventListener('click', () => {
    state.particles = [];
    state.trailParticles = [];
    ctx.fillStyle = '#0a0f19';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
});

// Start animation
animate();

// Initial canvas fill
ctx.fillStyle = '#0a0f19';
ctx.fillRect(0, 0, canvas.width, canvas.height);
