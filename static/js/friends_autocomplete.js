// Autocomplete for friend request username input with avatar display

document.addEventListener('DOMContentLoaded', function() {
    const input = document.querySelector('input[name="username"]');
    if (!input) return;
    const form = input.closest('form');
    // Create suggestion box
    const suggestionBox = document.createElement('div');
    suggestionBox.className = 'autocomplete-suggestions card shadow-sm';
    suggestionBox.style.position = 'absolute';
    suggestionBox.style.zIndex = '1000';
    suggestionBox.style.width = input.offsetWidth + 'px';
    suggestionBox.style.top = (input.offsetTop + input.offsetHeight) + 'px';
    suggestionBox.style.left = input.offsetLeft + 'px';
    suggestionBox.style.background = '#fff';
    suggestionBox.style.borderRadius = '8px';
    suggestionBox.style.display = 'none';
    suggestionBox.style.maxHeight = '300px';
    suggestionBox.style.overflowY = 'auto';
    input.parentNode.appendChild(suggestionBox);

    let lastQuery = '';
    input.addEventListener('input', function() {
        const query = input.value.trim();
        if (!query) {
            suggestionBox.style.display = 'none';
            return;
        }
        lastQuery = query;
        fetch(`/api/user_search?q=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(users => {
                suggestionBox.innerHTML = '';
                if (users.length === 0) {
                    suggestionBox.style.display = 'none';
                    return;
                }
                users.forEach(user => {
                    const item = document.createElement('div');
                    item.className = 'autocomplete-item d-flex align-items-center p-2';
                    item.style.cursor = 'pointer';
                    item.innerHTML = `
                        <img src="${user.avatar}" class="rounded-circle border me-2" width="36" height="36" style="object-fit:cover; border:2px solid #2575fc;">
                        <span style="font-weight:600; color:#2575fc;">${user.username}</span>
                    `;
                    item.addEventListener('mousedown', function(e) {
                        e.preventDefault();
                        input.value = user.username;
                        suggestionBox.style.display = 'none';
                    });
                    suggestionBox.appendChild(item);
                });
                suggestionBox.style.display = 'block';
            });
    });
    // Hide suggestions on blur
    input.addEventListener('blur', function() {
        setTimeout(() => suggestionBox.style.display = 'none', 150);
    });
    // Show suggestions on focus if input has value
    input.addEventListener('focus', function() {
        if (input.value.trim()) {
            input.dispatchEvent(new Event('input'));
        }
    });
});
