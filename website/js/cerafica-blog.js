/**
 * Cerafica Blog Integration
 * Fetches blog posts from the Kyanite API and renders them.
 * API: https://kyanitelabs.tech/api/cerafica/content/blog-posts
 */
(function() {
    'use strict';

    const API_BASE = 'https://kyanitelabs.tech/api/cerafica';

    async function loadBlogIndex(containerSelector) {
        const container = document.querySelector(containerSelector);
        if (!container) return;

        container.innerHTML = '<p class="blog-loading">Loading journal entries...</p>';

        try {
            const res = await fetch(`${API_BASE}/content/blog-posts`);
            const data = await res.json();

            if (!res.ok || !data.posts) {
                throw new Error(data.error || 'Failed to load posts');
            }

            if (data.posts.length === 0) {
                container.innerHTML = '<p class="blog-empty">No journal entries yet. Check back soon.</p>';
                return;
            }

            container.innerHTML = data.posts.map(post => `
                <article class="blog-card">
                    <h2 class="blog-card__title">
                        <a href="blog-post.html?slug=${encodeURIComponent(post.slug)}">${escapeHtml(post.title)}</a>
                    </h2>
                    <p class="blog-card__meta">${formatDate(post.created_at)}</p>
                    <p class="blog-card__excerpt">${escapeHtml(post.meta_description || '')}</p>
                    <a class="blog-card__link" href="blog-post.html?slug=${encodeURIComponent(post.slug)}">Read entry →</a>
                </article>
            `).join('');
        } catch (err) {
            container.innerHTML = `<p class="blog-error">Could not load journal: ${escapeHtml(err.message)}</p>`;
        }
    }

    async function loadBlogPost(slug, containerSelector, titleSelector) {
        const container = document.querySelector(containerSelector);
        if (!container) return;

        container.innerHTML = '<p class="blog-loading">Loading entry...</p>';

        try {
            const res = await fetch(`${API_BASE}/content/blog-posts/${encodeURIComponent(slug)}/html`);
            if (!res.ok) throw new Error('Entry not found');

            const html = await res.text();
            container.innerHTML = `<article class="blog-post__article">${html}</article>`;

            // Update page title if possible
            const titleEl = document.querySelector(titleSelector);
            if (titleEl) {
                const h1 = container.querySelector('h1, h2');
                if (h1) titleEl.textContent = h1.textContent + ' — Journal';
            }
        } catch (err) {
            container.innerHTML = `<p class="blog-error">Could not load entry: ${escapeHtml(err.message)}</p>`;
        }
    }

    function escapeHtml(str) {
        return (str || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    function formatDate(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    }

    // Auto-init based on page
    const path = window.location.pathname;
    const params = new URLSearchParams(window.location.search);

    if (path.includes('blog.html') || path.includes('journal.html')) {
        document.addEventListener('DOMContentLoaded', () => loadBlogIndex('.blog-posts'));
    }

    if (path.includes('blog-post.html')) {
        const slug = params.get('slug');
        if (slug) {
            document.addEventListener('DOMContentLoaded', () => loadBlogPost(slug, '.blog-post__content', '.page-title'));
        }
    }

    // Expose for manual use
    window.CeraficaBlog = { loadBlogIndex, loadBlogPost };
})();
