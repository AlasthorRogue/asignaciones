(function () {
    'use strict';

    var navStack = [window.location.href];
    var currentUrl = window.location.href;
    var isNavigating = false;

    history.replaceState({ idx: 0, url: currentUrl }, '', currentUrl);

    window.addEventListener('popstate', function (e) {
        if (!e.state || e.state.idx === undefined) return;
        var targetUrl = navStack[e.state.idx];
        if (targetUrl && targetUrl !== currentUrl) {
            loadContent(targetUrl, false);
            navStack = navStack.slice(0, e.state.idx + 1);
            currentUrl = targetUrl;
        }
    });

    function isNative(el) {
        return el.getAttribute('data-hgt-native') === 'true' ||
            el.getAttribute('data-hgt-no-ajax') === 'true' ||
            el.classList.contains('dt-button') ||
            el.closest('.dt-buttons') ||
            el.closest('.dataTables_filter');
    }

    function isDownload(url) {
        if (!url) return false;
        var lower = url.toLowerCase();
        return lower.includes('/static/') ||
            lower.includes('export') ||
            lower.includes('template') ||
            lower.includes('/pdf/') ||
            lower.endsWith('.xlsx') ||
            lower.endsWith('.pdf');
    }

    function isMultipart(form) {
        return form.getAttribute('enctype') === 'multipart/form-data';
    }

    function updateActiveSidebar(url) {
        var links = document.querySelectorAll('.nav-menu a');
        links.forEach(function (link) {
            link.classList.remove('active');
            if (link.href === url) {
                link.classList.add('active');
            }
        });
    }

    function executeScripts(container) {
        var scripts = container.querySelectorAll('script');
        scripts.forEach(function (oldScript) {
            if (oldScript.type && oldScript.type !== 'text/javascript') return;

            if (oldScript.src) {
                var newScript = document.createElement('script');
                newScript.src = oldScript.src;
                newScript.async = false;
                if (oldScript.type) newScript.type = oldScript.type;
                document.body.appendChild(newScript);
                document.body.removeChild(newScript);
            } else if (oldScript.textContent.trim()) {
                var s = document.createElement('script');
                s.textContent = oldScript.textContent;
                document.body.appendChild(s);
                document.body.removeChild(s);
            }
        });
    }

    function fireDCL() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function once() {
                document.removeEventListener('DOMContentLoaded', once);
                document.dispatchEvent(new Event('DOMContentLoaded'));
            });
        } else {
            document.dispatchEvent(new Event('DOMContentLoaded'));
        }
    }

    document.addEventListener('click', function (e) {
        var link = e.target.closest('a');
        if (!link || !link.href) return;
        if (isNative(link)) return;
        if (isDownload(link.href)) return;
        if (link.href.startsWith('javascript:')) return;
        if (link.href.startsWith('#')) return;
        if (!link.href.startsWith(window.location.origin) && !link.href.startsWith('/')) return;

        var sidebarLink = link.closest('.nav-menu');
        if (sidebarLink) {
            e.preventDefault();
            var url = link.href;
            if (url !== currentUrl && !isNavigating) {
                navigateTo(url);
            }
            var mobileSidebar = document.getElementById('sidebar');
            var overlay = document.getElementById('sidebarOverlay');
            if (mobileSidebar) mobileSidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('visible');
            return;
        }

        var insideMain = link.closest('.main-content');
        if (insideMain) {
            var href = link.getAttribute('href');
            if (href && !href.startsWith('http') && !href.startsWith('//') && !href.startsWith('javascript:') && !href.startsWith('#') && !isDownload(href)) {
                e.preventDefault();
                var url2 = link.href;
                if (url2 !== currentUrl && !isNavigating) {
                    navigateTo(url2);
                }
            }
        }
    });

    document.addEventListener('submit', function (e) {
        if (e.defaultPrevented) return;
        var form = e.target;
        if (isNative(form)) return;
        if (form.method && form.method.toLowerCase() === 'get') return;
        if (isMultipart(form)) return;

        var insideMain = form.closest('.main-content');
        if (!insideMain) return;

        e.preventDefault();
        submitForm(form);
    });

    function navigateTo(url) {
        isNavigating = true;
        currentUrl = url;
        loadContent(url, true);
    }

    async function loadContent(url, addToHistory) {
        var mainEl = document.querySelector('.main-content');
        if (!mainEl) {
            window.location.href = url;
            return;
        }

        mainEl.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;padding:4rem"><i class="fa-solid fa-spinner fa-spin" style="font-size:2rem;color:var(--hgt-orange)"></i></div>';

        try {
            var response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-HGT-AJAX': 'true'
                }
            });

            if (!response.ok) {
                window.location.href = url;
                return;
            }

            var html = await response.text();
            var parser = new DOMParser();
            var doc = parser.parseFromString(html, 'text/html');

            var newContent = doc.querySelector('.main-content');
            if (!newContent) {
                window.location.href = url;
                return;
            }

            mainEl.innerHTML = newContent.innerHTML;

            var titleTag = doc.querySelector('title');
            if (titleTag) {
                document.title = titleTag.textContent;
            }

            executeScripts(mainEl);

            updateActiveSidebar(url);

            if (addToHistory) {
                navStack.push(url);
                history.replaceState({ idx: navStack.length - 1 }, '', url);
            }

            if (typeof initSearchableSelects === 'function') {
                initSearchableSelects();
            }

            fireDCL();

            isNavigating = false;
        } catch (error) {
            console.error('HGT Nav error:', error);
            window.location.href = url;
        }
    }

    async function submitForm(form) {
        var formData = new FormData(form);
        var method = form.method || 'POST';
        var action = form.getAttribute('action') || currentUrl;

        var mainEl = document.querySelector('.main-content');
        if (mainEl) {
            mainEl.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;padding:4rem"><i class="fa-solid fa-spinner fa-spin" style="font-size:2rem;color:var(--hgt-orange)"></i></div>';
        }

        try {
            var response = await fetch(action, {
                method: method,
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-HGT-AJAX': 'true'
                }
            });

            if (!response.ok) {
                form.submit();
                return;
            }

            var contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                if (mainEl) {
                    mainEl.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;padding:4rem"><i class="fa-solid fa-spinner fa-spin" style="font-size:2rem;color:var(--hgt-orange)"></i></div>';
                }
                navigateTo(currentUrl);
                return;
            }

            var html = await response.text();

            if (html.length < 50 || html.indexOf('<html') === -1) {
                navigateTo(response.url || currentUrl);
                return;
            }

            var parser = new DOMParser();
            var doc = parser.parseFromString(html, 'text/html');

            var newContent = doc.querySelector('.main-content');
            if (!newContent || !newContent.innerHTML.trim()) {
                navigateTo(response.url || window.location.href);
                return;
            }

            if (mainEl) {
                mainEl.innerHTML = newContent.innerHTML;
            }

            var titleTag = doc.querySelector('title');
            if (titleTag) {
                document.title = titleTag.textContent;
            }

            if (mainEl) executeScripts(mainEl);

            var finalUrl = response.url;
            if (finalUrl && finalUrl !== currentUrl) {
                currentUrl = finalUrl;
                navStack.push(finalUrl);
                history.replaceState({ idx: navStack.length - 1 }, '', finalUrl);
                updateActiveSidebar(finalUrl);
            }

            if (typeof initSearchableSelects === 'function') {
                initSearchableSelects();
            }

            fireDCL();
        } catch (error) {
            console.error('HGT Form error:', error);
            form.submit();
        }
    }
})();
