/**
 * Professional Animation Controller for Medical Website
 * Handles scroll-triggered animations with IntersectionObserver for performance
 */

class AnimationController {
    constructor() {
        this.observerOptions = {
            root: null,
            rootMargin: '0px 0px -100px 0px', // Trigger 100px before element enters viewport
            threshold: 0.15 // Trigger when 15% of element is visible
        };

        this.init();
    }

    init() {
        // Check if user prefers reduced motion
        if (this.prefersReducedMotion()) {
            console.log('Reduced motion preferred - animations disabled');
            return;
        }

        // Initialize intersection observer
        this.observer = new IntersectionObserver(
            this.handleIntersection.bind(this),
            this.observerOptions
        );

        // Observe all elements with animation classes
        this.observeElements();

        // Add special animations
        this.initHeroAnimation();
        this.initCounterAnimations();
    }

    prefersReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    observeElements() {
        const animatedSelectors = [
            '.fade-in-up',
            '.scale-in',
            '.slide-in-left',
            '.slide-in-right',
            '.animate-card'
        ];

        animatedSelectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => this.observer.observe(el));
        });
    }

    handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                // Unobserve after animation to improve performance
                this.observer.unobserve(entry.target);
            }
        });
    }

    initHeroAnimation() {
        // Animate hero image on page load
        const heroImage = document.querySelector('.hero-image');
        if (heroImage) {
            heroImage.classList.add('hero-image-animate');
        }

        // Add subtle pulse to primary CTA
        const primaryCTA = document.querySelector('.hero-cta .btn-primary');
        if (primaryCTA) {
            primaryCTA.classList.add('pulse-subtle');
        }
    }

    initCounterAnimations() {
        // Animate statistics/numbers when they come into view
        const statNumbers = document.querySelectorAll('.impact-number, .highlight-number');

        statNumbers.forEach(number => {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('animate-count');
                        observer.unobserve(entry.target);
                    }
                });
            }, this.observerOptions);

            observer.observe(number);
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new AnimationController());
} else {
    new AnimationController();
}
