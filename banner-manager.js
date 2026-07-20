/**
 * Banner Notification Manager
 * Config-driven floating banner system with auto-expiry for time-sensitive announcements.
 * Banners are defined in banners.json and automatically shown/hidden based on date range.
 */

class BannerManager {
    constructor() {
        this.container = null;
        this.init();
    }

    async init() {
        try {
            const response = await fetch('/banners.json');
            if (!response.ok) return;
            const data = await response.json();
            if (!data.banners || !data.banners.length) return;

            const activeBanners = this.filterActive(data.banners);
            if (!activeBanners.length) return;

            this.createContainer();
            activeBanners.forEach(banner => this.render(banner));
        } catch (e) {
            // Fail silently — banners are non-critical
        }
    }

    filterActive(banners) {
        const now = new Date();
        const page = location.pathname.split('/').pop() || 'index.html';

        return banners.filter(b => {
            if (new Date(b.endDate) <= now) return false;
            if (new Date(b.startDate) > now) return false;
            if (b.pages && !b.pages.includes('all') && !b.pages.includes(page)) return false;
            if (b.dismissible && localStorage.getItem('banner-dismissed-' + b.id)) return false;
            return true;
        });
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.className = 'banner-container';
        this.container.setAttribute('role', 'region');
        this.container.setAttribute('aria-label', 'Announcements');
        document.body.appendChild(this.container);
    }

    render(banner) {
        const el = document.createElement('div');
        el.className = 'site-banner site-banner--' + this.escapeAttr(banner.style || 'info');
        el.setAttribute('role', 'alert');

        let html = '<div class="banner-content">';
        html += '<span class="banner-message">' + this.escapeHtml(banner.message) + '</span>';

        if (banner.details) {
            html += '<span class="banner-details">' + this.escapeHtml(banner.details) + '</span>';
        }

        if (banner.ctaText && banner.ctaUrl) {
            html += '<a class="banner-cta" href="' + this.escapeAttr(banner.ctaUrl) + '" target="_blank" rel="noopener noreferrer">' + this.escapeHtml(banner.ctaText) + '</a>';
        }

        html += '</div>';

        if (banner.dismissible) {
            html += '<button class="banner-dismiss" aria-label="Dismiss announcement" title="Dismiss">&times;</button>';
        }

        el.innerHTML = html;

        if (banner.dismissible) {
            el.querySelector('.banner-dismiss').addEventListener('click', () => {
                localStorage.setItem('banner-dismissed-' + banner.id, '1');
                el.style.animation = 'bannerSlideOut 0.25s ease-in forwards';
                el.addEventListener('animationend', () => el.remove());
            });
        }

        this.container.appendChild(el);
    }

    escapeHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    escapeAttr(str) {
        return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new BannerManager());
} else {
    new BannerManager();
}
