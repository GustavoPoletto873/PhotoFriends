(function () {
    'use strict';

    // Target: .hero (landing) or .page-anim (app pages)
    const hero = document.querySelector('.hero');
    const pageAnim = document.querySelector('.page-anim');
    const target = hero || pageAnim;

    if (!target) return;

    const isFullscreen = !hero;

    if (!isFullscreen) {
        target.style.position = 'relative';
    }

    const canvas = document.createElement('canvas');
    canvas.id = 'hero-liquid-swarm';
    canvas.style.position = isFullscreen ? 'fixed' : 'absolute';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.zIndex = isFullscreen ? '0' : '-1';
    canvas.style.pointerEvents = 'none';

    if (isFullscreen) {
        document.body.insertBefore(canvas, document.body.firstChild);
    } else {
        target.appendChild(canvas);
    }

    const ctx = canvas.getContext('2d');

    const CONFIG = {
        particleCount: 1500,
        dashWidth: 3.5,
        dashHeight: 10,
        baseRadius: 600,
        rotationSpeed: 0.003,
        swarmInertia: 0.04,
        minEase: 0.02,
        maxEase: 0.08,
        stretchFactor: 0.8,
        colors: [
            { hex: '#fbbf24', weight: 0.30 },
            { hex: '#f43f8e', weight: 0.40 },
            { hex: '#a855f7', weight: 0.30 }
        ]
    };

    let particles = [];
    let canvasWidth, canvasHeight;
    let mouse = { x: 0, y: 0, active: false };
    let swarmCenter = { x: 0, y: 0 };
    let swarmVelocity = 0;
    let time = 0;
    let seed = 13579;

    function seededRandom() {
        seed = (seed * 9301 + 49297) % 233280;
        return seed / 233280;
    }

    function getColor() {
        const r = seededRandom();
        if (r < CONFIG.colors[0].weight) return CONFIG.colors[0].hex;
        if (r < CONFIG.colors[0].weight + CONFIG.colors[1].weight) return CONFIG.colors[1].hex;
        return CONFIG.colors[2].hex;
    }

    class Particle {
        constructor(index) {
            this.index = index;
            this.init(true);
        }

        init(isInitial = false) {
            this.angle = seededRandom() * Math.PI * 2;
            this.radiusMult = Math.sqrt(seededRandom());
            this.ease = CONFIG.minEase + seededRandom() * (CONFIG.maxEase - CONFIG.minEase);
            this.noiseOffset = seededRandom() * 100;
            if (isInitial) {
                this.x = canvasWidth / 2;
                this.y = canvasHeight / 2;
            }
            this.baseOpacity = 0.4 + seededRandom() * 0.6;
            this.sizeVar = 0.8 + seededRandom() * 0.5;
            this.color = getColor();
            this.life = seededRandom();
            this.lifeSpeed = 0.001 + seededRandom() * 0.002;
            // Wave / undulation params
            this.wavePhase  = seededRandom() * Math.PI * 2;
            this.waveFreq   = 0.4 + seededRandom() * 1.2;   // speed of wave cycle
            this.waveAmp    = 0.10 + seededRandom() * 0.22;  // radial oscillation depth
            this.wave2Phase = seededRandom() * Math.PI * 2;  // secondary lateral wave
            this.wave2Freq  = 0.3 + seededRandom() * 0.8;
            this.wave2Amp   = 0.06 + seededRandom() * 0.10;
        }

        update() {
            const wave  = Math.sin(time * this.waveFreq  + this.wavePhase);
            const wave2 = Math.cos(time * this.wave2Freq + this.wave2Phase);

            // Rotation speed varies with wave — creates clustering/spreading feel
            this.angle += CONFIG.rotationSpeed * (1 + wave * 0.45);

            this.life += this.lifeSpeed;
            if (this.life > 1) this.life = 0;
            const breath = Math.sin(this.life * Math.PI);

            const dynamicRadius = CONFIG.baseRadius * (1 + swarmVelocity * CONFIG.stretchFactor);

            // Radius oscillates (radial wave — particles breathe in/out)
            const r = this.radiusMult * dynamicRadius * (1 + wave * this.waveAmp);

            // Lateral angular offset (secondary wave — gives sinuous trail)
            const angularWobble = wave2 * this.wave2Amp;

            const tx = swarmCenter.x + Math.cos(this.angle + angularWobble) * r;
            const ty = swarmCenter.y + Math.sin(this.angle + angularWobble) * r;
            this.x += (tx - this.x) * this.ease;
            this.y += (ty - this.y) * this.ease;
            this.currentOpacity = this.baseOpacity * breath;
        }

        draw() {
            ctx.save();
            ctx.translate(this.x, this.y);
            ctx.rotate(this.angle + Math.PI / 2);
            ctx.globalAlpha = this.currentOpacity;
            ctx.fillStyle = this.color;
            ctx.fillRect(
                -CONFIG.dashWidth * this.sizeVar / 2,
                -CONFIG.dashHeight * this.sizeVar / 2,
                CONFIG.dashWidth * this.sizeVar,
                CONFIG.dashHeight * this.sizeVar
            );
            ctx.restore();
        }
    }

    function handleResize() {
        const dpr = window.devicePixelRatio || 1;
        const rect = isFullscreen
            ? { width: window.innerWidth, height: window.innerHeight }
            : target.getBoundingClientRect();

        canvasWidth = rect.width;
        canvasHeight = rect.height;
        canvas.width = canvasWidth * dpr;
        canvas.height = canvasHeight * dpr;
        ctx.scale(dpr, dpr);
        swarmCenter.x = canvasWidth / 2;
        swarmCenter.y = canvasHeight / 2;
        seed = 13579;
        particles = [];
        for (let i = 0; i < CONFIG.particleCount; i++) {
            particles.push(new Particle(i));
        }
    }

    function animate() {
        ctx.clearRect(0, 0, canvasWidth, canvasHeight);
        time += 0.01;

        let destX = canvasWidth / 2;
        let destY = canvasHeight / 2;
        if (mouse.active) { destX = mouse.x; destY = mouse.y; }

        const prevX = swarmCenter.x;
        const prevY = swarmCenter.y;
        swarmCenter.x += (destX - swarmCenter.x) * CONFIG.swarmInertia;
        swarmCenter.y += (destY - swarmCenter.y) * CONFIG.swarmInertia;

        const dx = swarmCenter.x - prevX;
        const dy = swarmCenter.y - prevY;
        swarmVelocity += (Math.sqrt(dx * dx + dy * dy) * 0.1 - swarmVelocity) * 0.1;

        particles.forEach(p => { p.update(); p.draw(); });
        requestAnimationFrame(animate);
    }

    handleResize();
    window.addEventListener('resize', handleResize);

    // Mouse tracking — use window for fullscreen, target for landing
    const mouseTarget = isFullscreen ? window : target;
    mouseTarget.addEventListener('mousemove', (e) => {
        if (isFullscreen) {
            mouse.x = e.clientX;
            mouse.y = e.clientY;
        } else {
            const rect = target.getBoundingClientRect();
            mouse.x = e.clientX - rect.left;
            mouse.y = e.clientY - rect.top;
        }
        mouse.active = true;
    });
    mouseTarget.addEventListener('mouseleave', () => { mouse.active = false; });

    animate();

    document.querySelectorAll('canvas[id^="hero-particle"]').forEach(c => {
        if (c.id !== 'hero-liquid-swarm') c.remove();
    });

})();

// ── SPINNING GLOW (runs on every page) ──────────────────────────────────
(function initSpinGlow() {
    function attachGlow() {
        document.querySelectorAll('.btn-primary, .btn--primary').forEach(function(btn) {
            if (btn.parentElement && btn.parentElement.classList.contains('btn-glow-wrap')) return;
            var wrap = document.createElement('span');
            wrap.className = 'btn-glow-wrap';
            btn.parentNode.insertBefore(wrap, btn);
            wrap.appendChild(btn);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachGlow);
    } else {
        attachGlow();
    }
})();
