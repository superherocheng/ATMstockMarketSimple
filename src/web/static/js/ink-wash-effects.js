/* ══════════════════════════════════════════════════
   ATMstockMarket — 江南水墨效果
   Ink Wash Painting Effects
   ══════════════════════════════════════════════════ */

(function() {
    'use strict';
    
    /* ══════════════════════════════════════════════════
       水墨晕染效果
       ══════════════════════════════════════════════════ */
    
    class InkWashEffect {
        constructor() {
            this.init();
        }
        
        init() {
            this.addRippleEffect();
            this.addParallaxEffect();
            this.addInkSpreadEffect();
            this.addScrollAnimations();
        }
        
        /* 涟漪效果 */
        addRippleEffect() {
            const rippleElements = document.querySelectorAll('.ripple-effect, .btn, .nav-link');
            
            rippleElements.forEach(el => {
                el.addEventListener('click', (e) => {
                    const rect = el.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    
                    const ripple = document.createElement('span');
                    ripple.className = 'ripple';
                    ripple.style.left = x + 'px';
                    ripple.style.top = y + 'px';
                    
                    el.appendChild(ripple);
                    
                    setTimeout(() => {
                        ripple.remove();
                    }, 600);
                });
            });
        }
        
        /* 视差滚动效果 */
        addParallaxEffect() {
            const parallaxElements = document.querySelectorAll('.ink-wash-bg, .hero-section');
            
            if (parallaxElements.length === 0) return;
            
            let ticking = false;
            
            const updateParallax = () => {
                const scrollY = window.pageYOffset;
                
                parallaxElements.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const speed = el.dataset.parallaxSpeed || 0.5;
                    const yPos = -(scrollY * speed);
                    
                    el.style.transform = `translate3d(0, ${yPos}px, 0)`;
                });
                
                ticking = false;
            };
            
            window.addEventListener('scroll', () => {
                if (!ticking) {
                    requestAnimationFrame(updateParallax);
                    ticking = true;
                }
            }, { passive: true });
        }
        
        /* 水墨扩散效果 */
        addInkSpreadEffect() {
            const cards = document.querySelectorAll('.card, .glass, .ink-card, .screen-card');
            
            const observer = new IntersectionObserver((entries) => {
                entries.forEach((entry, index) => {
                    if (entry.isIntersecting) {
                        setTimeout(() => {
                            entry.target.classList.add('ink-spread-visible');
                        }, index * 100);
                    }
                });
            }, {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            });
            
            cards.forEach(card => {
                observer.observe(card);
            });
        }
        
        /* 滚动动画 */
        addScrollAnimations() {
            const sections = document.querySelectorAll('section');
            
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('section-visible');
                    }
                });
            }, {
                threshold: 0.1
            });
            
            sections.forEach(section => {
                section.classList.add('section-hidden');
                observer.observe(section);
            });
        }
    }
    
    /* ══════════════════════════════════════════════════
       水墨粒子效果
       ══════════════════════════════════════════════════ */
    
    class InkParticleEffect {
        constructor(container) {
            this.container = container;
            this.particles = [];
            this.maxParticles = 20;
            this.init();
        }
        
        init() {
            if (!this.container) return;
            
            this.createCanvas();
            this.animate();
        }
        
        createCanvas() {
            this.canvas = document.createElement('canvas');
            this.canvas.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                opacity: 0.3;
            `;
            this.ctx = this.canvas.getContext('2d');
            this.container.appendChild(this.canvas);
            
            this.resize();
            window.addEventListener('resize', () => this.resize());
        }
        
        resize() {
            this.canvas.width = this.container.offsetWidth;
            this.canvas.height = this.container.offsetHeight;
        }
        
        createParticle() {
            return {
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                radius: Math.random() * 2 + 1,
                opacity: Math.random() * 0.5 + 0.2,
                speedX: (Math.random() - 0.5) * 0.5,
                speedY: (Math.random() - 0.5) * 0.5,
                color: Math.random() > 0.5 ? '#3d7a8c' : '#a67c52'
            };
        }
        
        animate() {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            
            if (this.particles.length < this.maxParticles) {
                this.particles.push(this.createParticle());
            }
            
            this.particles.forEach((p, index) => {
                p.x += p.speedX;
                p.y += p.speedY;
                
                if (p.x < 0 || p.x > this.canvas.width || 
                    p.y < 0 || p.y > this.canvas.height) {
                    this.particles[index] = this.createParticle();
                }
                
                this.ctx.beginPath();
                this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                this.ctx.fillStyle = p.color;
                this.ctx.globalAlpha = p.opacity;
                this.ctx.fill();
            });
            
            this.ctx.globalAlpha = 1;
            
            requestAnimationFrame(() => this.animate());
        }
    }
    
    /* ══════════════════════════════════════════════════
       水墨文字效果
       ══════════════════════════════════════════════════ */
    
    class InkTextEffect {
        constructor() {
            this.init();
        }
        
        init() {
            const titles = document.querySelectorAll('h1, h2, h3, .calligraphy-title');
            
            titles.forEach(title => {
                title.addEventListener('mouseenter', () => {
                    title.style.textShadow = '2px 2px 4px rgba(45, 45, 45, 0.1)';
                });
                
                title.addEventListener('mouseleave', () => {
                    title.style.textShadow = 'none';
                });
            });
        }
    }
    
    /* ══════════════════════════════════════════════════
       平滑滚动
       ══════════════════════════════════════════════════ */
    
    class SmoothScroll {
        constructor() {
            this.init();
        }
        
        init() {
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', (e) => {
                    e.preventDefault();
                    const target = document.querySelector(anchor.getAttribute('href'));
                    if (target) {
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                });
            });
        }
    }
    
    /* ══════════════════════════════════════════════════
       初始化
       ══════════════════════════════════════════════════ */
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new InkWashEffect();
            new InkTextEffect();
            new SmoothScroll();
            
            const heroSection = document.querySelector('.hero-section');
            if (heroSection) {
                new InkParticleEffect(heroSection);
            }
        });
    } else {
        new InkWashEffect();
        new InkTextEffect();
        new SmoothScroll();
        
        const heroSection = document.querySelector('.hero-section');
        if (heroSection) {
            new InkParticleEffect(heroSection);
        }
    }
    
    /* ══════════════════════════════════════════════════
       CSS 样式注入
       ══════════════════════════════════════════════════ */
    
    const style = document.createElement('style');
    style.textContent = `
        .section-hidden {
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.6s ease, transform 0.6s ease;
        }
        
        .section-visible {
            opacity: 1;
            transform: translateY(0);
        }
        
        .ink-spread-visible {
            animation: inkSpread 0.6s ease forwards;
        }
        
        @keyframes inkSpread {
            from {
                opacity: 0;
                transform: scale(0.95);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }
    `;
    document.head.appendChild(style);
    
})();
