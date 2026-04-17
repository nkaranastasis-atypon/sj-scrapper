document.addEventListener("DOMContentLoaded", (event) => {
    document.querySelectorAll('button.expand-all')?.forEach?.(button => {
        button.addEventListener('click', () => {
            const isExpanded = button.getAttribute('aria-expanded') === 'true';
            document.querySelectorAll('div.collapse.bs-accordion__content').forEach(el => {
                if (isExpanded) {
                    el.classList.remove('show');
                } else {
                    el.classList.add('show');
                }
            });
            document.querySelectorAll('button.bs-accordion__control').forEach(el => {
               el.click();
            });
            button.setAttribute('aria-expanded', !isExpanded);
            button.querySelector('span').textContent = isExpanded ? 'Show all sections' : 'Hide all sections';
            button.querySelector('img').setAttribute('src', isExpanded ?'../assets/show.svg': '../assets/hide.svg');
        });
    });

    document.querySelectorAll('button.bs-accordion__control').forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-target').substring(1);
            const targetElement = document.getElementById(targetId);
            const isExpanded = button.getAttribute('aria-expanded') === 'true';
            if (isExpanded) {
                targetElement.classList.remove('show');
                button.classList.add('collapsed');
                button.setAttribute('aria-expanded', 'false');
            } else {
                targetElement.classList.add('show');
                button.classList.remove('collapsed');
                button.setAttribute('aria-expanded', 'true');
            }
        });
    });
});   