// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// Mobile menu toggle
const mobileToggle = document.querySelector('.mobile-menu-toggle');
const navMenu = document.querySelector('.nav-menu');

function closeMenu() {
    navMenu.classList.remove('active');
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'false');
}

if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
        const isOpen = navMenu.classList.toggle('active');
        mobileToggle.setAttribute('aria-expanded', String(isOpen));
    });

    // Escape key closes menu
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && navMenu.classList.contains('active')) {
            closeMenu();
            mobileToggle.focus();
        }
    });
}

// Close mobile menu when clicking a link
document.querySelectorAll('.nav-menu a').forEach(link => {
    link.addEventListener('click', closeMenu);
});

// Scroll animations with Intersection Observer
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

// Observe elements for animation
document.addEventListener('DOMContentLoaded', () => {
    const animatedElements = document.querySelectorAll('.qualification-card, .expertise-item, .achievement-item, .publication-item, .timeline-item');
    animatedElements.forEach(el => {
        el.classList.add('fade-in');
        observer.observe(el);
    });
});

// FAQ Accordion
document.querySelectorAll('.faq-question').forEach(button => {
    button.addEventListener('click', () => {
        const item = button.parentElement;
        const isOpen = item.classList.contains('active');
        document.querySelectorAll('.faq-item.active').forEach(openItem => {
            openItem.classList.remove('active');
            openItem.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
        });
        if (!isOpen) {
            item.classList.add('active');
            button.setAttribute('aria-expanded', 'true');
        }
    });
});

// Active navigation highlighting — passive + rAF throttled
let scrollTicking = false;
const navSections = Array.from(document.querySelectorAll('section[id]'));
const navLinks = Array.from(document.querySelectorAll('.nav-menu a'));

window.addEventListener('scroll', () => {
    if (!scrollTicking) {
        requestAnimationFrame(() => {
            const scrollPosition = window.scrollY + 100;
            navSections.forEach(section => {
                if (scrollPosition >= section.offsetTop &&
                    scrollPosition < section.offsetTop + section.offsetHeight) {
                    const sectionId = section.getAttribute('id');
                    navLinks.forEach(link => {
                        link.classList.toggle('active', link.getAttribute('href') === `#${sectionId}`);
                    });
                }
            });
            scrollTicking = false;
        });
        scrollTicking = true;
    }
}, { passive: true });
